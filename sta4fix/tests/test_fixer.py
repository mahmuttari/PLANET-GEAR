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

    # poz balonu: daire içindeki poz numarası, etriye çizgisinin üstünde —
    # daire yazıyla BİRLİKTE taşınmalı
    msp.add_text("12", height=6, dxfattribs={"layer": "POZ"}).set_placement((100, 29))
    msp.add_circle((105.2, 31.1), radius=7.2, dxfattribs={"layer": "POZ"})

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
    msp = doc.modelspace()
    poz_text = next(e for e in msp if e.dxftype() == "TEXT" and e.dxf.text == "12")
    poz_circle = next(e for e in msp if e.dxftype() == "CIRCLE")
    rel_before = (poz_circle.dxf.center.x - poz_text.dxf.insert.x,
                  poz_circle.dxf.center.y - poz_text.dxf.insert.y)
    pos_before = (poz_text.dxf.insert.x, poz_text.dxf.insert.y)

    before = count_overlaps(doc)
    assert before >= 5, f"demo çizim yeterince çakışmalı değil: {before}"

    report = fix_dxf(doc, margin=1.0)
    after = count_overlaps(doc)

    # poz balonu yazıyla birlikte taşınmış olmalı
    moved_dist = abs(poz_text.dxf.insert.x - pos_before[0]) + \
                 abs(poz_text.dxf.insert.y - pos_before[1])
    rel_after = (poz_circle.dxf.center.x - poz_text.dxf.insert.x,
                 poz_circle.dxf.center.y - poz_text.dxf.insert.y)
    assert moved_dist > 1e-6, "poz yazısı hiç taşınmadı (çakışıktı)"
    assert abs(rel_after[0] - rel_before[0]) < 1e-6 and \
           abs(rel_after[1] - rel_before[1]) < 1e-6, \
           f"poz dairesi yazıyla birlikte taşınmadı: {rel_before} → {rel_after}"
    assert report.grouped_symbols >= 1, "hiç sembol gruplanmadı"
    print(f"poz balonu birlikte taşındı ✓ (gruplanan sembol: {report.grouped_symbols})")

    print(f"önce: {before} çakışan yazı | bulunan: {report.overlapping} | "
          f"taşınan: {report.moved} | sonra: {after} | "
          f"çözümsüz: {len(report.unresolved)}")
    assert report.moved > 0, "hiç yazı taşınmadı"
    assert after == 0, f"düzeltme sonrası {after} çakışma kaldı"
    print("TEST GEÇTİ")


if __name__ == "__main__":
    main()
