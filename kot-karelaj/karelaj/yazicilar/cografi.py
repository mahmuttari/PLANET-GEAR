# -*- coding: utf-8 -*-
"""
KML ve GeoJSON çıktıları
========================

``kml_yaz``
    Google Earth'te açılabilen dosya üretir. Üretilen karelajın gerçekten
    istenen alana oturup oturmadığını gözle denetlemenin en hızlı yolu,
    bu dosyayı Google Earth'e sürüklemektir. Noktalar, çalışma alanı
    sınırı ve varsa eş yükselti eğrileri ayrı klasörlere yerleştirilir.

``geojson_yaz``
    CBS/GIS ortamına (QGIS, ArcGIS) doğrudan aktarım içindir. WGS84
    coğrafi koordinatlarda, her noktanın kotu ve izdüşüm koordinatları
    öznitelik olarak yazılır.
"""

from __future__ import annotations

import json
import os
from typing import Optional, Sequence
from xml.sax.saxutils import escape

__all__ = ["kml_yaz", "geojson_yaz"]


def kml_yaz(
    yol: str,
    karelaj,
    konturlar: Optional[Sequence] = None,
    baslik: str = "Kot karelajı",
    kot_etiketi: bool = False,
) -> str:
    """Karelajı KML olarak yazar."""
    sistem = karelaj.sistem
    parcalar = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        "<Document>",
        f"<name>{escape(baslik)}</name>",
        f"<description>{escape(_aciklama(karelaj))}</description>",
        '<Style id="karelajNoktasi"><IconStyle><scale>0.5</scale>'
        "<Icon><href>http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png</href></Icon>"
        "</IconStyle><LabelStyle><scale>0.7</scale></LabelStyle></Style>",
        '<Style id="alanSiniri"><LineStyle><color>ff0000ff</color><width>2</width></LineStyle>'
        "<PolyStyle><color>1a0000ff</color></PolyStyle></Style>",
        '<Style id="konturCizgisi"><LineStyle><color>ff00aaff</color><width>1</width></LineStyle></Style>',
    ]

    parcalar.append("<Folder><name>Çalışma alanı sınırı</name>")
    for indis, halka in enumerate(karelaj.alan.halkalar):
        koordinat = " ".join(f"{b:.8f},{e:.8f},0" for b, e in halka)
        if halka:
            koordinat += f" {halka[0][0]:.8f},{halka[0][1]:.8f},0"
        etiket = "Dış sınır" if indis == 0 else f"İç boşluk {indis}"
        parcalar.append(
            f"<Placemark><name>{escape(etiket)}</name>"
            f"<styleUrl>#alanSiniri</styleUrl><Polygon><outerBoundaryIs><LinearRing>"
            f"<coordinates>{koordinat}</coordinates>"
            f"</LinearRing></outerBoundaryIs></Polygon></Placemark>"
        )
    parcalar.append("</Folder>")

    parcalar.append(f"<Folder><name>Karelaj noktaları ({len(karelaj.noktalar)})</name>")
    for n in karelaj.noktalar:
        kot = n.kot if n.kot is not None else 0.0
        ad = f"{n.no}" + (f" ({n.kot:.2f} m)" if kot_etiketi and n.kot is not None else "")
        aciklama = (
            f"Nokta no: {n.no}\n"
            f"Y (sağa): {n.saga:.3f} m\n"
            f"X (yukarı): {n.yukari:.3f} m\n"
            f"Z (kot): {'-' if n.kot is None else f'{n.kot:.3f} m'}\n"
            f"Sistem: {sistem.ad}\n"
            f"Enlem/Boylam: {n.enlem:.8f}, {n.boylam:.8f}"
        )
        parcalar.append(
            f"<Placemark><name>{escape(ad)}</name>"
            f"<description>{escape(aciklama)}</description>"
            f"<styleUrl>#karelajNoktasi</styleUrl>"
            f"<Point><altitudeMode>clampToGround</altitudeMode>"
            f"<coordinates>{n.boylam:.8f},{n.enlem:.8f},{kot:.3f}</coordinates></Point>"
            f"</Placemark>"
        )
    parcalar.append("</Folder>")

    if konturlar:
        parcalar.append(f"<Folder><name>Eş yükselti eğrileri ({len(konturlar)})</name>")
        for egri in konturlar:
            koordinat = []
            for x, y in egri.noktalar:
                enlem, boylam = sistem.wgs84e(x, y)
                koordinat.append(f"{boylam:.8f},{enlem:.8f},{egri.kot:.3f}")
            parcalar.append(
                f"<Placemark><name>{egri.kot:.2f} m</name>"
                f"<styleUrl>#konturCizgisi</styleUrl>"
                f"<LineString><tessellate>1</tessellate>"
                f"<coordinates>{' '.join(koordinat)}</coordinates></LineString></Placemark>"
            )
        parcalar.append("</Folder>")

    parcalar.append("</Document></kml>")
    _yaz(yol, "\n".join(parcalar), "utf-8")
    return yol


def geojson_yaz(yol: str, karelaj, konturlar: Optional[Sequence] = None) -> str:
    """Karelajı GeoJSON olarak yazar (WGS84 coğrafi koordinatlar)."""
    sistem = karelaj.sistem
    ozellikler = []
    for n in karelaj.noktalar:
        ozellikler.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        round(n.boylam, 8),
                        round(n.enlem, 8),
                        round(n.kot, 3) if n.kot is not None else None,
                    ],
                },
                "properties": {
                    "nokta_no": n.no,
                    "y_saga": round(n.saga, 3),
                    "x_yukari": round(n.yukari, 3),
                    "kot": round(n.kot, 3) if n.kot is not None else None,
                    "kod": n.kod or None,
                    "satir": n.satir + 1 if n.satir >= 0 else None,
                    "sutun": n.sutun + 1,
                    "kaynak": n.kaynak or None,
                },
            }
        )

    ozellikler.append(
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[round(b, 8), round(e, 8)] for b, e in halka] + [[round(halka[0][0], 8), round(halka[0][1], 8)]]
                    for halka in karelaj.alan.halkalar
                    if halka
                ],
            },
            "properties": {"tur": "calisma_alani", "ad": karelaj.alan.ad},
        }
    )

    for egri in konturlar or []:
        cizgi = []
        for x, y in egri.noktalar:
            enlem, boylam = sistem.wgs84e(x, y)
            cizgi.append([round(boylam, 8), round(enlem, 8)])
        ozellikler.append(
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": cizgi},
                "properties": {"tur": "es_yukselti", "kot": egri.kot},
            }
        )

    belge = {
        "type": "FeatureCollection",
        "name": "kot_karelaji",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
        },
        "uretim": {
            "koordinat_sistemi": sistem.tanim(),
            "karelaj_araligi_m": karelaj.ayar.aralik,
            "nokta_sayisi": len(karelaj.noktalar),
        },
        "features": ozellikler,
    }
    _yaz(yol, json.dumps(belge, ensure_ascii=False, indent=1), "utf-8")
    return yol


def _aciklama(karelaj) -> str:
    istatistik = karelaj.kot_istatistikleri()
    satirlar = [
        f"Koordinat sistemi: {karelaj.sistem.tanim()}",
        f"Karelaj aralığı: {karelaj.ayar.aralik:g} m",
        f"Nokta sayısı: {len(karelaj.noktalar)}",
    ]
    if istatistik:
        satirlar.append(
            f"Kot aralığı: {istatistik['en_dusuk']:.2f} - {istatistik['en_yuksek']:.2f} m"
        )
    return "\n".join(satirlar)


def _yaz(yol: str, icerik: str, kodlama: str) -> None:
    klasor = os.path.dirname(os.path.abspath(yol))
    if klasor:
        os.makedirs(klasor, exist_ok=True)
    with open(yol, "wb") as f:
        f.write(icerik.encode(kodlama, errors="replace"))
