# -*- coding: utf-8 -*-
"""Sentetik bir 'kiriş detayı' üzerinde sta4fix doğrulaması.

Çalıştır: python -m sta4fix.tests.test_fixer
Yazıları kasıtlı olarak çizgilerin ve birbirinin üstüne koyar; fix_dxf
sonrasında hiçbir yazının geometriyle veya başka yazıyla çakışmadığını
doğrular.
"""

import ezdxf

from sta4fix.fixer import Rect, _entity_box, fix_dxf, LEADER_LAYER, TEXT_TYPES
from ezdxf import disassemble


def build_demo(path=None):
    """Kiriş detayına benzer, bilinçli çakışmalı bir DXF üretir."""
    doc = ezdxf.new("R2018", setup=True)
    msp = doc.modelspace()

    # kiriş gövdesi: yatay çift çizgi + etriye dikmeleri
    for y in (0, 60):
        msp.add_line((0, y), (400, y))
    for x in range(20, 400, 40):
        msp.add_line((x, 5), (x, 55))
    # boyuna donatı çizgileri
    for y in (8, 52):
        msp.add_line((5, y), (395, y))

    # ÇAKIŞAN yazılar: donatı ve etriye açıklamaları çizgilerin tam üstünde
    labels = [
        ("3Ø16 duz", (60, 50)),
        ("2Ø12 montaj", (60, 6)),
        ("Ø8/15 etriye", (140, 28)),
        ("K101 25/60", (140, 30)),      # bir öncekiyle de çakışır
        ("4Ø16 pilye", (260, 50)),
        ("L=385", (260, 52)),           # donatı çizgisi + üstteki yazı
    ]
    for txt, pos in labels:
        msp.add_text(txt, height=6, dxfattribs={"layer": "YAZI"}).set_placement(pos)

    if path:
        doc.saveas(path)
    return doc


def _collect_obstacle_prims(msp):
    prims = []
    for e in disassemble.recursive_decompose(msp):
        if e.dxftype() in TEXT_TYPES:
            continue
        if e.dxftype() == "LINE" and e.dxf.layer == LEADER_LAYER:
            continue
        prim = disassemble.make_primitive(e)
        pts = [(v.x, v.y) for v in prim.vertices()]
        if pts:
            prims.append(pts)
    return prims


def count_overlaps(doc, margin=0.0):
    """Kalan çakışma sayısı: yazı-geometri + yazı-yazı."""
    from sta4fix.fixer import Obstacle
    msp = doc.modelspace()
    texts = [e for e in msp if e.dxftype() in TEXT_TYPES]
    boxes = [(_entity_box(t) or Rect(0, 0, 0, 0)).inflate(margin) for t in texts]
    obstacles = []
    for pts in _collect_obstacle_prims(msp):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        obstacles.append(Obstacle(pts, Rect(min(xs), min(ys), max(xs), max(ys))))
    n = 0
    for i, b in enumerate(boxes):
        if any(o.collides(b) for o in obstacles):
            n += 1
            continue
        if any(j != i and boxes[j].intersects(b) for j in range(len(boxes))):
            n += 1
    return n


def main():
    doc = build_demo()
    before = count_overlaps(doc)
    assert before >= 5, f"demo çizim yeterince çakışmalı değil: {before}"

    report = fix_dxf(doc, margin=1.0)
    after = count_overlaps(doc)

    print(f"önce: {before} çakışan yazı | bulunan: {report.overlapping} | "
          f"taşınan: {report.moved} | sonra: {after} | "
          f"çözümsüz: {len(report.unresolved)}")
    assert report.moved > 0, "hiç yazı taşınmadı"
    assert after == 0, f"düzeltme sonrası {after} çakışma kaldı"
    print("TEST GEÇTİ")


if __name__ == "__main__":
    main()
