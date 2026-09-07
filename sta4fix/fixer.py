# -*- coding: utf-8 -*-
"""
sta4fix.fixer — DXF çizimlerinde çakışan yazıları (TEXT/MTEXT) tespit edip
boş alana taşıyan çekirdek mantık.

Yaklaşım:
  1. Modelspace'teki TEXT/MTEXT varlıkları toplanır.
  2. Yazıya bağlı küçük semboller (poz dairesi/yarım dairesi, kot ⊕ işareti,
     döşeme etiket kutusu) birbirine değme ilişkisiyle KÜMELENİR; küme,
     dokunduğu bütün yazılarla birlikte tek bir KATI GRUP oluşturur —
     D103 kutusu + içindeki üç etiket, ya da ⊕ + iki kot değeri gibi.
  3. Geri kalan geometri (bloklar açılarak) nokta dizilerine indirgenir ve
     ızgara tabanlı uzamsal indekse yerleştirilir.
  4. Çakışan her grup, orijinal konumu merkez alan halka taramasıyla en
     yakın boş konuma bütün üyeleriyle birlikte taşınır; kayma büyükse
     orijinal noktaya kılavuz çizgisi çizilir.

Not: Yazının kapalı bir şeklin (ör. kolon dış hattı) tamamen İÇİNDE olması
çakışma sayılmaz — çakışma, kutuyu kesen çizgi/nokta ile tanımlıdır.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import ezdxf
from ezdxf import bbox as ezbbox
from ezdxf import disassemble

TEXT_TYPES = {"TEXT", "MTEXT"}
SYMBOL_TYPES = {"CIRCLE", "ARC", "LINE", "LWPOLYLINE", "SOLID"}
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

    def union(self, o: "Rect") -> "Rect":
        return Rect(min(self.x0, o.x0), min(self.y0, o.y0),
                    max(self.x1, o.x1), max(self.y1, o.y1))

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
    """Basit tekdüze ızgara uzamsal indeksi.

    Çok geniş alana yayılan varlıklar (ör. çizim sınırı, kesit çizgileri)
    ızgaraya milyonlarca hücre olarak yazılmasın diye ayrı bir doğrusal
    listede tutulur — MAX_CELLS bunun eşiğidir.
    """

    MAX_CELLS = 4096

    def __init__(self, cell: float):
        self.cell = max(cell, 1e-6)
        self.cells: dict = {}
        self.large: list = []

    def _range(self, box: Rect):
        c = self.cell
        return (
            range(int(box.x0 // c), int(box.x1 // c) + 1),
            range(int(box.y0 // c), int(box.y1 // c) + 1),
        )

    def add(self, item, box: Rect):
        if not all(map(math.isfinite, (box.x0, box.y0, box.x1, box.y1))):
            return
        xs, ys = self._range(box)
        if len(xs) * len(ys) > self.MAX_CELLS:
            self.large.append(item)
            return
        for i in xs:
            for j in ys:
                self.cells.setdefault((i, j), []).append(item)

    def query(self, box: Rect):
        yield from self.large
        xs, ys = self._range(box)
        seen = set()
        for i in xs:
            for j in ys:
                for it in self.cells.get((i, j), ()):
                    if id(it) not in seen:
                        seen.add(id(it))
                        yield it


# ----------------------------------------------------------------------
# Gruplama: yazı + bağlı semboller
# ----------------------------------------------------------------------
@dataclass
class Group:
    texts: list                    # [TEXT/MTEXT, ...]
    syms: list                     # [(entity, Rect), ...]
    box: Rect
    h: float                       # grubun karakteristik yazı yüksekliği


class _UF:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def _build_groups(msp, texts, boxes, height_of, med_h):
    """Yazıları ve onlara bağlı sembol kümelerini katı gruplara ayırır.

    - Sembol adayı: en büyük boyutu 5×h_med'i aşmayan CIRCLE/ARC/LINE/
      LWPOLYLINE/SOLID.
    - Adaylar, kutuları (0.1×h payla) birbirine değiyorsa aynı kümede
      birleşir; kümenin toplam kutusu 10×h_med'i aşarsa (etriye zinciri,
      donatı hattı gibi) sembol sayılmaz, sabit engel olarak kalır.
    - Küme; kutusu bir yazının 0.5×h şişirilmiş kutusuna değiyorsa o
      yazıya bağlanır. Aynı kümeye bağlanan bütün yazılar (D103 kutusu
      içindeki üç etiket gibi) tek grup olur ve birlikte taşınır.
    """
    lim = 5.0 * med_h
    touch = 0.1 * med_h

    cands = []
    for e in msp:
        if e.dxftype() not in SYMBOL_TYPES:
            continue
        if e.dxftype() == "LINE" and e.dxf.layer == LEADER_LAYER:
            continue
        b = _entity_box(e)
        if b is None:
            continue
        if max(b.x1 - b.x0, b.y1 - b.y0) <= lim:
            cands.append((e, b))

    # aday sembolleri birbirine değme ilişkisiyle kümele (ızgara hızlandırmalı)
    uf = _UF()
    cgrid = Grid(cell=2.0 * med_h)
    for i, (e, b) in enumerate(cands):
        for j in cgrid.query(b.inflate(touch)):
            if cands[j][1].inflate(touch).intersects(b):
                uf.union(i, j)
        cgrid.add(i, b)

    clusters: dict = {}
    for i in range(len(cands)):
        clusters.setdefault(uf.find(i), []).append(i)

    # küme → dokunduğu yazılar
    text_list = [t for t in texts if id(t) in boxes]
    tgrid = Grid(cell=4.0 * med_h)
    for k, t in enumerate(text_list):
        tgrid.add(k, boxes[id(t)])

    tuf = _UF()               # yazılar üzerinden grup birleşimi
    cluster_of_text: dict = {}   # kök yazı -> [(entity, box), ...]
    for members in clusters.values():
        cbox = cands[members[0]][1]
        for i in members[1:]:
            cbox = cbox.union(cands[i][1])
        if max(cbox.x1 - cbox.x0, cbox.y1 - cbox.y0) > 10.0 * med_h:
            continue                       # büyük zincir: sabit engel
        hit = set()
        probe = cbox.inflate(0.5 * med_h)
        for k in tgrid.query(probe):
            t = text_list[k]
            if boxes[id(t)].inflate(0.5 * height_of[id(t)]).intersects(cbox):
                hit.add(k)
        if not hit:
            continue                       # yazısız sembol: sabit engel
        hit = sorted(hit)
        for k in hit[1:]:
            tuf.union(id(text_list[k]), id(text_list[hit[0]]))
        root = id(text_list[hit[0]])
        cluster_of_text.setdefault(root, []).extend(
            (cands[i][0], cands[i][1]) for i in members
        )

    # grupları kur
    by_root: dict = {}
    for t in text_list:
        by_root.setdefault(tuf.find(id(t)), []).append(t)

    groups = []
    for root, tlist in by_root.items():
        syms = []
        for t in tlist:
            syms.extend(cluster_of_text.get(tuf.find(id(t)), ()))
        # cluster_of_text kökleri tuf birleşiminden ÖNCE atanmış olabilir;
        # bütün üye yazıların ilk kayıtlarını topla
        seen = set()
        syms2 = []
        for t in tlist:
            for s, sb in cluster_of_text.get(id(t), ()):
                if id(s) not in seen:
                    seen.add(id(s))
                    syms2.append((s, sb))
        for s, sb in syms:
            if id(s) not in seen:
                seen.add(id(s))
                syms2.append((s, sb))
        box = boxes[id(tlist[0])]
        for t in tlist[1:]:
            box = box.union(boxes[id(t)])
        for _, sb in syms2:
            box = box.union(sb)
        groups.append(Group(
            texts=tlist,
            syms=syms2,
            box=box,
            h=max(height_of[id(t)] for t in tlist),
        ))
    return groups


# ----------------------------------------------------------------------
# Ana düzeltici
# ----------------------------------------------------------------------
@dataclass
class FixReport:
    total_texts: int = 0
    overlapping: int = 0
    moved: int = 0
    grouped_symbols: int = 0   # yazılarla birlikte taşınabilir sembol sayısı
    groups: int = 0            # birden çok üyeli grup sayısı
    unresolved: list = field(default_factory=list)
    moves: list = field(default_factory=list)


def _entity_box(e) -> Rect | None:
    cache = ezbbox.Cache()
    box = ezbbox.extents([e], fast=True, cache=cache)
    if not box.has_data:
        return None
    return Rect(box.extmin.x, box.extmin.y, box.extmax.x, box.extmax.y)


def _text_height(e, box: Rect | None = None) -> float:
    """Etkin yazı yüksekliği.

    Sta4CAD gibi programlar TEXT yüksekliğini 0 bırakıp değeri yazı
    stilinin (STYLE) sabit yüksekliğinden alır; o da yoksa sınır
    kutusunun yüksekliğine düşülür.
    """
    if e.dxftype() == "TEXT":
        h = float(e.dxf.height)
    else:
        h = float(e.dxf.char_height)
    if h <= 1e-9:
        try:
            style = e.doc.styles.get(e.dxf.style)
            h = float(style.dxf.height)
        except Exception:
            h = 0.0
    if h <= 1e-9 and box is not None:
        h = box.y1 - box.y0
    return h if h > 1e-9 else 2.5


def fix_dxf(
    doc,
    margin: float | None = None,
    scale: float = 1.0,
    max_shift_factor: float = 12.0,
    add_leader: bool = True,
    layers: set | None = None,
    dry_run: bool = False,
) -> FixReport:
    """Bir ezdxf belgesindeki çakışan yazıları (bağlı sembolleriyle) düzeltir.

    margin           : yazı kutusuna eklenen pay, çizim birimi.
                       None = otomatik (medyan yazı yüksekliğinin 0.3'ü) —
                       böylece mm, cm veya m ölçekli çizimlerde aynı davranır.
    scale            : yazı yüksekliği çarpanı (ör. 0.8 → %20 küçült)
    max_shift_factor : arama yarıçapı üst sınırı = faktör × yazı yüksekliği
    add_leader       : 2 yazı yüksekliğinden uzun taşımalara kılavuz çizgisi
    layers           : yalnızca bu katmanlardaki yazıları düzelt (None = hepsi)

    Kapalı şekiller (aks balonu, kolon hattı gibi) yalnızca grubun ÇEKİRDEK
    kutusunu keserse çakışma sayılır; margin payı açık geometriye uygulanır.
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

    # yazı kutuları; dejenere (sıfır boyutlu) kutular atlanır
    boxes: dict = {}
    for t in texts:
        b = _entity_box(t)
        if b is not None and (b.x1 - b.x0) > 1e-9 and (b.y1 - b.y0) > 1e-9:
            boxes[id(t)] = b

    height_of = {id(t): _text_height(t, boxes[id(t)])
                 for t in texts if id(t) in boxes}
    heights = sorted(height_of.values())
    med_h = heights[len(heights) // 2] if heights else 2.5
    if margin is None:
        margin = 0.3 * med_h

    # --- gruplar: yazı(lar) + bağlı sembol kümeleri ---
    groups = _build_groups(msp, texts, boxes, height_of, med_h)
    grouped_ids = {id(s) for g in groups for s, _ in g.syms}
    report.grouped_symbols = len(grouped_ids)
    report.groups = sum(1 for g in groups if len(g.texts) + len(g.syms) > 1)

    # --- engel indeksi: yazı ve gruplanmış sembol OLMAYAN her şey ---
    grid = Grid(cell=med_h * 4.0)
    text_ids = {id(t) for t in texts}
    for e in disassemble.recursive_decompose(msp):
        if e.dxftype() in TEXT_TYPES and id(e) in text_ids:
            continue
        if id(e) in grouped_ids:
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

    gboxes = {i: g.box for i, g in enumerate(groups)}

    def collides(core: Rect, skip_gid=None) -> bool:
        """core: grubun kutusu; açık geometriye margin payı eklenir."""
        padded = core.inflate(margin)
        for ob in grid.query(padded):
            if ob.collides(core if ob.closed else padded):
                return True
        for gid, gb in gboxes.items():
            if gid != skip_gid and gb.intersects(padded):
                return True
        return False

    order = sorted(range(len(groups)), key=lambda i: -groups[i].h)

    for gid in order:
        g = groups[gid]
        if layers and not any(t.dxf.layer in layers for t in g.texts):
            continue
        box = gboxes[gid]
        if not collides(box, skip_gid=gid):
            continue
        report.overlapping += len(g.texts)

        best = None
        step = g.h * 0.6
        max_r = max_shift_factor * g.h
        r = step
        while r <= max_r and best is None:
            for k in range(16):
                ang = 2.0 * math.pi * k / 16.0 + (r / step) * 0.2
                dx, dy = r * math.cos(ang), r * math.sin(ang)
                if not collides(box.translated(dx, dy), skip_gid=gid):
                    best = (dx, dy)
                    break
            r += step

        if best is None:
            for t in g.texts:
                report.unresolved.append(
                    t.plain_text() if hasattr(t, "plain_text") else str(t))
            continue

        dx, dy = best
        report.moved += len(g.texts)
        report.moves.append((g, dx, dy))
        if dry_run:
            continue

        old_cx, old_cy = box.cx, box.cy
        for t in g.texts:
            t.translate(dx, dy, 0)
        for s, _ in g.syms:
            s.translate(dx, dy, 0)
        gboxes[gid] = box.translated(dx, dy)

        if add_leader and math.hypot(dx, dy) > 2.0 * g.h:
            if LEADER_LAYER not in doc.layers:
                doc.layers.add(LEADER_LAYER, color=6)
            nb = gboxes[gid]
            sx = nb.x0 if old_cx < nb.x0 else (nb.x1 if old_cx > nb.x1 else nb.cx)
            sy = nb.y0 if old_cy < nb.y0 else (nb.y1 if old_cy > nb.y1 else nb.cy)
            msp.add_line(
                (sx, sy), (old_cx, old_cy), dxfattribs={"layer": LEADER_LAYER}
            )

    return report
