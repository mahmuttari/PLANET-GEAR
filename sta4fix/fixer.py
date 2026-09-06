# -*- coding: utf-8 -*-
"""
sta4fix.fixer — DXF çizimlerinde çakışan yazıları (TEXT/MTEXT) tespit edip
boş alana taşıyan çekirdek mantık.

Yaklaşım:
  1. Modelspace'teki tüm TEXT/MTEXT varlıkları "yazı" olarak toplanır.
  2. Geri kalan geometri (bloklar dahil, recursive_decompose ile açılarak)
     nokta dizilerine (primitive) indirgenir ve ızgara tabanlı bir uzamsal
     indekse yerleştirilir.
  3. Her yazının (margin ile şişirilmiş) sınır kutusu; geometri parçaları,
     diğer yazılar ve daha önce taşınmış yazılarla çakışma testine sokulur.
  4. Çakışan yazı, orijinal konumu merkez alan halka taramasıyla en yakın
     boş konuma taşınır; kayma yazı yüksekliğini aşarsa orijinal noktaya
     kılavuz çizgisi (leader) çizilir.

Not: Yazının kapalı bir şeklin (ör. kolon dış hattı) tamamen İÇİNDE olması
çakışma sayılmaz — çakışma, yazı kutusunu kesen çizgi/nokta ile tanımlıdır.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import ezdxf
from ezdxf import bbox as ezbbox
from ezdxf import disassemble

TEXT_TYPES = {"TEXT", "MTEXT"}
LEADER_LAYER = "STA4FIX_LEADER"


# ----------------------------------------------------------------------
# Geometri yardımcıları
# ----------------------------------------------------------------------
@dataclass
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float

    def inflate(self, m: float) -> "Rect":
        return Rect(self.x0 - m, self.y0 - m, self.x1 + m, self.y1 + m)

    def translated(self, dx: float, dy: float) -> "Rect":
        return Rect(self.x0 + dx, self.y0 + dy, self.x1 + dx, self.y1 + dy)

    def intersects(self, o: "Rect") -> bool:
        return not (o.x1 < self.x0 or o.x0 > self.x1 or o.y1 < self.y0 or o.y0 > self.y1)

    def contains_point(self, x: float, y: float) -> bool:
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1

    @property
    def cx(self) -> float:
        return 0.5 * (self.x0 + self.x1)

    @property
    def cy(self) -> float:
        return 0.5 * (self.y0 + self.y1)


def _seg_intersects_rect(p1, p2, r: Rect) -> bool:
    """[p1,p2] doğru parçası dikdörtgeni kesiyor mu? (Liang-Barsky)"""
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    t0, t1 = 0.0, 1.0
    for p, q in (
        (-dx, x1 - r.x0),
        (dx, r.x1 - x1),
        (-dy, y1 - r.y0),
        (dy, r.y1 - y1),
    ):
        if abs(p) < 1e-12:
            if q < 0:
                return False
            continue
        t = q / p
        if p < 0:
            if t > t1:
                return False
            t0 = max(t0, t)
        else:
            if t < t0:
                return False
            t1 = min(t1, t)
    return t0 <= t1


@dataclass
class Obstacle:
    """Nokta dizisine indirgenmiş tek bir geometri parçası."""
    pts: list          # [(x, y), ...]
    box: Rect
    closed: bool = False

    def collides(self, r: Rect) -> bool:
        if not self.box.intersects(r):
            return False
        pts = self.pts
        if len(pts) == 1:
            return r.contains_point(*pts[0])
        for a, b in zip(pts, pts[1:]):
            if _seg_intersects_rect(a, b, r):
                return True
        return False


class Grid:
    """Basit tekdüze ızgara uzamsal indeksi."""

    def __init__(self, cell: float):
        self.cell = max(cell, 1e-6)
        self.cells: dict = {}

    def _range(self, box: Rect):
        c = self.cell
        return (
            range(int(box.x0 // c), int(box.x1 // c) + 1),
            range(int(box.y0 // c), int(box.y1 // c) + 1),
        )

    def add(self, item, box: Rect):
        xs, ys = self._range(box)
        for i in xs:
            for j in ys:
                self.cells.setdefault((i, j), []).append(item)

    def query(self, box: Rect):
        xs, ys = self._range(box)
        seen = set()
        for i in xs:
            for j in ys:
                for it in self.cells.get((i, j), ()):
                    if id(it) not in seen:
                        seen.add(id(it))
                        yield it


# ----------------------------------------------------------------------
# Ana düzeltici
# ----------------------------------------------------------------------
@dataclass
class FixReport:
    total_texts: int = 0
    overlapping: int = 0
    moved: int = 0
    unresolved: list = field(default_factory=list)   # taşınamayan yazı içerikleri
    moves: list = field(default_factory=list)        # (text, dx, dy)


def _entity_box(e) -> Rect | None:
    cache = ezbbox.Cache()
    box = ezbbox.extents([e], fast=True, cache=cache)
    if not box.has_data:
        return None
    return Rect(box.extmin.x, box.extmin.y, box.extmax.x, box.extmax.y)


def _text_height(e) -> float:
    if e.dxftype() == "TEXT":
        return float(e.dxf.height)
    return float(e.dxf.char_height)


def fix_dxf(
    doc,
    margin: float = 1.0,
    scale: float = 1.0,
    max_shift_factor: float = 12.0,
    add_leader: bool = True,
    layers: set | None = None,
    dry_run: bool = False,
) -> FixReport:
    """Bir ezdxf belgesindeki çakışan yazıları düzeltir.

    margin           : yazı kutusuna eklenen pay (çizim birimi)
    scale            : yazı yüksekliği çarpanı (ör. 0.8 → %20 küçült)
    max_shift_factor : arama yarıçapı üst sınırı = faktör × yazı yüksekliği
    add_leader       : yazı yüksekliğinden fazla kayan yazıya kılavuz çizgisi
    layers           : yalnızca bu katmanlardaki yazıları düzelt (None = hepsi)
    """
    msp = doc.modelspace()
    report = FixReport()

    texts = [e for e in msp if e.dxftype() in TEXT_TYPES]
    report.total_texts = len(texts)
    if not texts:
        return report

    if scale != 1.0 and not dry_run:
        for t in texts:
            if layers and t.dxf.layer not in layers:
                continue
            if t.dxftype() == "TEXT":
                t.dxf.height = t.dxf.height * scale
            else:
                t.dxf.char_height = t.dxf.char_height * scale

    heights = [_text_height(t) for t in texts]
    med_h = sorted(heights)[len(heights) // 2] if heights else 2.5

    # --- engel indeksini kur: yazı OLMAYAN her şey, bloklar açılarak ---
    grid = Grid(cell=max(med_h * 4.0, 1.0))
    text_ids = {id(t) for t in texts}
    for e in disassemble.recursive_decompose(msp):
        if e.dxftype() in TEXT_TYPES and id(e) in text_ids:
            continue
        if e.dxftype() == "LINE" and e.dxf.layer == LEADER_LAYER:
            continue
        try:
            prim = disassemble.make_primitive(e)
            pts = [(v.x, v.y) for v in prim.vertices()]
        except Exception:
            pts = []
        if not pts:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        box = Rect(min(xs), min(ys), max(xs), max(ys))
        closed = len(pts) > 2 and math.hypot(
            pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]
        ) < 1e-9
        grid.add(Obstacle(pts, box, closed), box)

    # --- yazı kutuları; yazılar birbirinin de engeli ---
    boxes: dict = {}
    for t in texts:
        b = _entity_box(t)
        if b is not None:
            boxes[id(t)] = b

    def collides(rect: Rect, skip_text_id=None) -> bool:
        for ob in grid.query(rect):
            if ob.collides(rect):
                return True
        for tid, tb in boxes.items():
            if tid != skip_text_id and tb.intersects(rect):
                return True
        return False

    # büyük yazılar önce yer bulsun
    order = sorted(
        (t for t in texts if id(t) in boxes),
        key=lambda t: -_text_height(t),
    )

    for t in order:
        if layers and t.dxf.layer not in layers:
            continue
        h = _text_height(t)
        box = boxes[id(t)].inflate(margin)
        if not collides(box, skip_text_id=id(t)):
            continue
        report.overlapping += 1

        # halka taraması: artan yarıçap, 16 yön
        best = None
        step = max(h * 0.6, 0.5)
        max_r = max_shift_factor * h
        r = step
        while r <= max_r and best is None:
            for k in range(16):
                ang = 2.0 * math.pi * k / 16.0 + (r / step) * 0.2
                dx, dy = r * math.cos(ang), r * math.sin(ang)
                cand = box.translated(dx, dy)
                if not collides(cand, skip_text_id=id(t)):
                    best = (dx, dy)
                    break
            r += step

        if best is None:
            report.unresolved.append(t.plain_text() if hasattr(t, "plain_text") else str(t))
            continue

        dx, dy = best
        report.moved += 1
        report.moves.append((t, dx, dy))
        if dry_run:
            continue

        old_cx, old_cy = boxes[id(t)].cx, boxes[id(t)].cy
        t.translate(dx, dy, 0)
        boxes[id(t)] = boxes[id(t)].translated(dx, dy)

        if add_leader and math.hypot(dx, dy) > h:
            if LEADER_LAYER not in doc.layers:
                doc.layers.add(LEADER_LAYER, color=1)
            nb = boxes[id(t)]
            # kutunun eski konuma bakan kenar orta noktasından çizgi çek
            sx = nb.x0 if old_cx < nb.x0 else (nb.x1 if old_cx > nb.x1 else nb.cx)
            sy = nb.y0 if old_cy < nb.y0 else (nb.y1 if old_cy > nb.y1 else nb.cy)
            msp.add_line(
                (sx, sy), (old_cx, old_cy), dxfattribs={"layer": LEADER_LAYER}
            )

    return report
