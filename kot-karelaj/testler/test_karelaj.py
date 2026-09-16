# -*- coding: utf-8 -*-
"""
Kot karelajı - test paketi
==========================

Çalıştırma::

    cd kot-karelaj
    python -m unittest discover -s testler -v
    # ya da
    python testler/test_karelaj.py

Testler yalnızca Python standart kütüphanesini kullanır; pyproj, numpy ya
da rasterio kurulu olmasa da çalışır.

İzdüşüm testlerindeki referans koordinatlar PROJ/pyproj ile üretilmiş,
gömülü GeoTIFF örnekleri ise GDAL ile yazılmıştır; böylece saf Python
uygulaması bağımsız bir gerçeklemeye karşı sınanmış olur.
"""

from __future__ import annotations

import base64
import io
import json
import math
import os
import struct
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from xml.etree import ElementTree

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from karelaj import bicim  # noqa: E402
from karelaj.geodezi import (  # noqa: E402
    DATUM_ED50,
    GRS80,
    Helmert,
    TransverseMercator,
    dilim_orta_meridyeni,
    elipsoidal_mesafe,
    otomatik_sistem,
    sistem_bul,
    sistem_listesi,
    uygun_dilim,
)
from karelaj.geometri import (  # noqa: E402
    Alan,
    alan_oku,
    alan_sinir_kutusundan,
    nokta_poligon_icinde,
)
from karelaj.hacim import hacim_hesapla  # noqa: E402
from karelaj.izgara import (  # noqa: E402
    KarelajAyari,
    Karelaj,
    Nokta,
    NumaralandirmaAyari,
    karelaj_uret,
    nokta_sayisi_tahmini,
)
from karelaj.kaynaklar import (  # noqa: E402
    KaynakHatasi,
    kaynak_olustur,
    kotlari_doldur,
)
from karelaj.kaynaklar.web import (  # noqa: E402
    GoogleElevation,
    OpenElevation,
    OpenTopoData,
    _sayiya,
)
from karelaj.kontur import kontur_kotlari, kontur_uret  # noqa: E402
from karelaj.onbellek import KotOnbellegi  # noqa: E402
from karelaj.raster import (  # noqa: E402
    RasterHatasi,
    _lzw_coz,
    _packbits_coz,
    raster_ac,
)
from karelaj.yazicilar import (  # noqa: E402
    NCN_PROFILLERI,
    csv_yaz,
    dxf_yaz,
    geojson_yaz,
    kml_yaz,
    ncn_satirlari,
    ncn_yaz,
    profil_coz,
    rapor_metni,
    xyz_yaz,
)

# ---------------------------------------------------------------------------
# Referans veriler
# ---------------------------------------------------------------------------

REFERANS_NOKTALAR = [
    ("Kocaeli / İzmit", 40.7654, 29.9408),
    ("İstanbul / Sultanahmet", 41.0056, 28.977),
    ("Ankara / Kızılay", 39.9208, 32.8542),
    ("İzmir / Konak", 38.4189, 27.1287),
    ("Van / Merkez", 38.4945, 43.38),
    ("Antalya / Kaleiçi", 36.8848, 30.7044),
]

# PROJ/pyproj ile üretilmiş referans izdüşüm koordinatları (sağa, yukarı)
REFERANS_KOORDINATLAR = {
    ("ITRF96-TM30", 0): (495001.5784, 4514522.2622),
    ("ITRF96-TM30", 1): (413936.3455, 4541699.3429),
    ("ITRF96-TM30", 2): (744030.5033, 4424637.4770),
    ("ITRF96-TM30", 3): (249223.8257, 4257902.6429),
    ("ITRF96-TM30", 5): (562794.7314, 4083958.1631),
    ("ITRF96-TM27", 0): (748316.2256, 4518683.6395),
    ("ITRF96-TM27", 1): (666325.8357, 4543078.4015),
    ("ITRF96-TM27", 3): (511239.4364, 4254003.9496),
    ("ITRF96-TM33", 2): (487535.2010, 4420745.3251),
    ("ITRF96-TM33", 5): (295341.5104, 4086188.0252),
    ("ITRF96-TM42", 4): (620393.0201, 4263290.6453),
    ("ITRF96-GK10", 0): (10495001.5784, 4514522.2622),
    ("ITRF96-GK10", 2): (10744030.5033, 4424637.4770),
    ("ED50-TM30", 0): (495036.6870, 4514708.4307),
    ("ED50-TM30", 1): (413971.0722, 4541885.7849),
    ("ED50-TM30", 2): (744066.8431, 4424822.8756),
    ("ED50-TM30", 3): (249257.0838, 4258087.7962),
    ("ED50-TM30", 5): (562829.6598, 4084141.7072),
    ("ED50-GK10", 0): (10495036.6870, 4514708.4307),
    ("ED50-UTM35N", 0): (748259.8091, 4517063.6766),
    ("ED50-UTM35N", 1): (666301.7898, 4541448.8909),
    ("ED50-UTM35N", 3): (511276.1658, 4252488.5509),
    ("WGS84-UTM35N", 0): (748216.8991, 4516876.1661),
    ("WGS84-UTM35N", 1): (666259.3054, 4541261.1703),
    ("WGS84-UTM35N", 3): (511234.9406, 4252302.3482),
}

# GDAL ile yazılmış örnek GeoTIFF'ler: 32x24 piksel, 10 m çözünürlük,
# sol üst köşe (494000, 4514000), EPSG:5254, değer = 100 + 2*sütun + 3*satır
GEOTIFF_LZW_P2 = (
    "SUkqAAgAAAARAAABAwABAAAAIAAAAAEBAwABAAAAGAAAAAIBAwABAAAAEAAAAAMBAwABAAAABQAA"
    "AAYBAwABAAAAAQAAABEBBAABAAAAfAEAABUBAwABAAAAAQAAABYBAwABAAAAGAAAABcBBAABAAAA"
    "gQAAABwBAwABAAAAAQAAAD0BAwABAAAAAgAAAFMBAwABAAAAAgAAAA6DDAADAAAA2gAAAIKEDAAG"
    "AAAA8gAAAK+HAwAgAAAAIgEAALGHAgAUAAAAYgEAAIGkAgAGAAAAdgEAAAAAAAAAAAAAAAAkQAAA"
    "AAAAACRAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwCYeQQAAAAA0OFFBAAAA"
    "AAAAAAABAAEAAAAHAAAEAAABAAEAAQQAAAEAAQACBLGHDQAAAAEIsYcGAA0ABggAAAEAjiMADAAA"
    "AQCGFAQMAAABACkjVFVSRUYgLyBUTTMwfFRVUkVGfAAtOTk5OQCAGQAAKBwWCQeDQmEQuFQ2GQ+G"
    "meHROIRWKReIGqMRuLR2OQU2x+PSORQ04SWSSmSnOUS2VRY7S6ZS+EnmZzeaHycTuSH+eT+LIKgU"
    "OGIWiUeCIikUdF0uaR5HU6hpGpU+JpSqz9L1mrQxNVydp2wV2CqCxzdR2eyKa1TJU22rQEA="
)
GEOTIFF_DEFLATE_P3 = (
    "SUkqAAgAAAASAAABAwABAAAAIAAAAAEBAwABAAAAGAAAAAIBAwABAAAAIAAAAAMBAwABAAAACAAA"
    "AAYBAwABAAAAAQAAABUBAwABAAAAAQAAABwBAwABAAAAAQAAAD0BAwABAAAAAwAAAEIBAwABAAAA"
    "EAAAAEMBAwABAAAAEAAAAEQBBAAEAAAA7gAAAEUBAwAEAAAA5gAAAFMBAwABAAAAAwAAAA6DDAAD"
    "AAAA/gAAAIKEDAAGAAAAFgEAAK+HAwAgAAAARgEAALGHAgAUAAAAhgEAAIGkAgAGAAAAmgEAAAAA"
    "AAClAGwASQBIAKABAABFAgAAsQIAAPoCAAAAAAAAAAAkQAAAAAAAACRAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAwCYeQQAAAAA0OFFBAAAAAAAAAAABAAEAAAAHAAAEAAABAAEA"
    "AQQAAAEAAQACBLGHDQAAAAEIsYcGAA0ABggAAAEAjiMADAAAAQCGFAQMAAABACkjVFVSRUYgLyBU"
    "TTMwfFRVUkVGfAAtOTk5OQB4nJXNMQeCURSH8XOft0/29tmampqampqampoaIiIiIiIiIiIiIiKR"
    "0jln6J77H+51hp+nFr0krYYZT/m/2nJpa13BI+6TiEhHx4F72Kf329Vx4Bb06fP3dBy4xvyXS1/H"
    "gUvEp9890HHgHPCKy1DHgVPWJ3OPdBw45rzlMq4wO2R8090T7PaFfur8rtDPnN8W+rnzm0K/cH5d"
    "6JfOrzL+BVDzIAF4nJXLQQpAUAAGYbmaEyullCIiIiIiopRSyhms3yzon90sPscyi22zzfrOwafw"
    "i+hz+En0Jfwg+hq+E30L34i+h69EP8IXop/hM9Gv8Inod/hI9Ad8KPoTPhD9Be+L/ob3RP/Auz/+"
    "BXRPIAF4nHNmQAUXmVDBOQb8wBmNfwVN/2kS9V9H03+CRP230PQfJVH/XTT9h0jU/wBN/34S9T9G"
    "07+HRP3P0PTvZBgFowA3AAC/EBABeJxzZkAFH5lQwToG/MAZjf8FTf9qEvV/R9O/gkT9v9D0LyVR"
    "/180/YtI1M+Apn8+ifqZ0fTPIVE/G5r+mQyjYBTgBgB+pw0B"
)

TIF_GENISLIK, TIF_YUKSEKLIK = 32, 24
TIF_SOL_UST = (494000.0, 4514000.0)
TIF_PIKSEL = 10.0


def tif_beklenen(sutun: int, satir: int) -> float:
    return 100.0 + 2.0 * sutun + 3.0 * satir


def gecici_dosya(klasor: str, ad: str, b64: str) -> str:
    yol = os.path.join(klasor, ad)
    with open(yol, "wb") as f:
        f.write(base64.b64decode(b64))
    return yol


# ---------------------------------------------------------------------------
# Geodezi
# ---------------------------------------------------------------------------


class GeodeziTesti(unittest.TestCase):
    def test_referans_koordinatlar(self):
        """İzdüşüm sonuçları PROJ referanslarıyla milimetre altında uyuşmalı."""
        for (kod, indis), (beklenen_saga, beklenen_yukari) in REFERANS_KOORDINATLAR.items():
            with self.subTest(sistem=kod, nokta=REFERANS_NOKTALAR[indis][0]):
                _ad, enlem, boylam = REFERANS_NOKTALAR[indis]
                saga, yukari = sistem_bul(kod).wgs84ten(enlem, boylam)
                fark = math.hypot(saga - beklenen_saga, yukari - beklenen_yukari)
                self.assertLess(fark, 0.001, f"{kod}: {fark * 1000:.4f} mm sapma")

    def test_ters_donusum(self):
        """İleri-geri dönüşüm başlangıç noktasına milimetre altında dönmeli."""
        for kod in ("ITRF96-TM30", "ITRF96-GK10", "ED50-TM30", "ED50-UTM35N", "WGS84-UTM35N"):
            for _ad, enlem, boylam in REFERANS_NOKTALAR[:4]:
                sistem = sistem_bul(kod)
                if abs(boylam - sistem.projeksiyon.orta_meridyen) > 3.5:
                    continue
                with self.subTest(sistem=kod, enlem=enlem):
                    saga, yukari = sistem.wgs84ten(enlem, boylam)
                    geri_enlem, geri_boylam = sistem.wgs84e(saga, yukari)
                    sapma = elipsoidal_mesafe(enlem, boylam, geri_enlem, geri_boylam)
                    self.assertLess(sapma, 0.002)

    def test_dilim_secimi(self):
        self.assertEqual(uygun_dilim(29.94), 10)
        self.assertEqual(uygun_dilim(28.98), 10)
        self.assertEqual(uygun_dilim(32.85), 11)
        self.assertEqual(uygun_dilim(27.13), 9)
        self.assertEqual(uygun_dilim(43.38), 14)
        self.assertEqual(dilim_orta_meridyeni(10), 30)
        self.assertEqual(uygun_dilim(29.94, 6), 35)
        self.assertEqual(otomatik_sistem(29.94).kod, "ITRF96-TM30")
        self.assertEqual(otomatik_sistem(29.94, "ED50").kod, "ED50-TM30")
        self.assertEqual(otomatik_sistem(29.94, "ITRF96-GK").kod, "ITRF96-GK10")
        self.assertEqual(otomatik_sistem(29.94, "UTM").kod, "WGS84-UTM35N")
        with self.assertRaises(ValueError):
            dilim_orta_meridyeni(8)

    def test_dilim_oneki(self):
        """Dilim numarası önekli sistemde sağa değer 10.000.000 fazla olmalı."""
        _ad, enlem, boylam = REFERANS_NOKTALAR[0]
        duz = sistem_bul("ITRF96-TM30").wgs84ten(enlem, boylam)
        onekli = sistem_bul("ITRF96-GK10").wgs84ten(enlem, boylam)
        self.assertAlmostEqual(onekli[0] - duz[0], 10000000.0, places=6)
        self.assertAlmostEqual(onekli[1], duz[1], places=6)

    def test_sistem_cozumleme(self):
        self.assertEqual(sistem_bul("EPSG:5254").kod, "ITRF96-TM30")
        self.assertEqual(sistem_bul("5254").kod, "ITRF96-TM30")
        self.assertEqual(sistem_bul("itrf96-tm30").kod, "ITRF96-TM30")
        self.assertEqual(sistem_bul("TUREF-TM30").kod, "ITRF96-TM30")
        with self.assertRaises(ValueError):
            sistem_bul("YOK-BOYLE")
        with self.assertRaises(ValueError):
            sistem_bul("EPSG:99999")
        self.assertGreaterEqual(len(sistem_listesi()), 30)

    def test_helmert_ters(self):
        """Helmert dönüşümü ve tersi birbirini götürmeli."""
        h = Helmert(dx=-84.1, dy=-101.8, dz=-129.7, rz=0.468, s=1.05)
        for nokta in [(4100000.0, 2300000.0, 4150000.0), (0.0, 0.0, 6300000.0)]:
            ileri = h.uygula(*nokta)
            geri = h.ters_uygula(*ileri)
            for a, b in zip(nokta, geri):
                self.assertAlmostEqual(a, b, places=6)

    def test_ed50_farki(self):
        """ED50 ile ITRF96 arasındaki fark Türkiye'de ~100 m mertebesinde olmalı."""
        _ad, enlem, boylam = REFERANS_NOKTALAR[0]
        itrf = sistem_bul("ITRF96-TM30").wgs84ten(enlem, boylam)
        ed50 = sistem_bul("ED50-TM30").wgs84ten(enlem, boylam)
        fark = math.hypot(ed50[0] - itrf[0], ed50[1] - itrf[1])
        self.assertGreater(fark, 100.0)
        self.assertLess(fark, 300.0)

    def test_olcek_ve_yakinsama(self):
        p = sistem_bul("ITRF96-TM30").projeksiyon
        # Orta meridyende ölçek faktörü k0, yakınsama sıfır olmalı
        self.assertAlmostEqual(p.olcek_faktoru(40.0, 30.0), 1.0, places=6)
        self.assertAlmostEqual(p.meridyen_yakinsamasi(40.0, 30.0), 0.0, places=5)
        # Dilim kenarında ölçek 1'den büyük, yakınsama doğuda pozitif
        self.assertGreater(p.olcek_faktoru(40.0, 31.4), 1.0)
        self.assertGreater(p.meridyen_yakinsamasi(40.0, 31.4), 0.0)
        self.assertLess(p.meridyen_yakinsamasi(40.0, 28.6), 0.0)

    def test_elipsoidal_mesafe(self):
        # Bir derece enlem farkı ~111 km
        d = elipsoidal_mesafe(40.0, 30.0, 41.0, 30.0)
        self.assertAlmostEqual(d, 110_996.0, delta=200.0)
        self.assertEqual(elipsoidal_mesafe(40.0, 30.0, 40.0, 30.0), 0.0)

    def test_tm_dogrudan(self):
        """TransverseMercator sınıfı UTM parametreleriyle doğrudan kullanılabilmeli."""
        tm = TransverseMercator(GRS80, orta_meridyen=27.0, olcek=0.9996, saga_kaydirma=500000.0)
        saga, yukari = tm.ileri(40.7654, 29.9408)
        beklenen = REFERANS_KOORDINATLAR[("WGS84-UTM35N", 0)]
        self.assertAlmostEqual(saga, beklenen[0], delta=0.001)
        self.assertAlmostEqual(yukari, beklenen[1], delta=0.001)


# ---------------------------------------------------------------------------
# Geometri
# ---------------------------------------------------------------------------


class GeometriTesti(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.mkdtemp()
        self.kare = [(29.90, 40.70), (30.00, 40.70), (30.00, 40.80), (29.90, 40.80)]

    def test_nokta_poligon_icinde(self):
        self.assertTrue(nokta_poligon_icinde(29.95, 40.75, self.kare))
        self.assertFalse(nokta_poligon_icinde(30.05, 40.75, self.kare))
        self.assertFalse(nokta_poligon_icinde(29.95, 40.85, self.kare))
        # Sınır üzerindeki nokta içeride sayılır
        self.assertTrue(nokta_poligon_icinde(29.90, 40.75, self.kare))
        self.assertTrue(nokta_poligon_icinde(29.95, 40.70, self.kare))

    def test_alan_hesabi(self):
        alan = Alan([self.kare])
        # 0,1° x 0,1° ~ 11,1 km x 8,4 km
        self.assertAlmostEqual(alan.alan_m2() / 1e6, 93.7, delta=1.0)

    def test_ic_bosluk(self):
        delik = [(29.94, 40.74), (29.96, 40.74), (29.96, 40.76), (29.94, 40.76)]
        alan = Alan([self.kare, delik])
        self.assertTrue(alan.icinde_mi(29.92, 40.72))
        self.assertFalse(alan.icinde_mi(29.95, 40.75))
        tam = Alan([self.kare]).alan_m2()
        self.assertLess(alan.alan_m2(), tam)

    def test_geojson_oku(self):
        yol = os.path.join(self.klasor, "a.geojson")
        with open(yol, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "properties": {},
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [[list(p) for p in self.kare] + [list(self.kare[0])]],
                            },
                        }
                    ],
                },
                f,
            )
        alan = alan_oku(yol)
        self.assertEqual(len(alan.dis_halka), 4)
        self.assertTrue(alan.icinde_mi(29.95, 40.75))

    def test_kml_oku(self):
        yol = os.path.join(self.klasor, "a.kml")
        koordinat = " ".join(f"{b},{e},0" for b, e in self.kare)
        with open(yol, "w", encoding="utf-8") as f:
            f.write(
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark>'
                "<name>Saha</name><Polygon><outerBoundaryIs><LinearRing>"
                f"<coordinates>{koordinat}</coordinates>"
                "</LinearRing></outerBoundaryIs></Polygon></Placemark></Document></kml>"
            )
        alan = alan_oku(yol)
        self.assertEqual(len(alan.dis_halka), 4)
        self.assertAlmostEqual(alan.dis_halka[0][0], 29.90, places=6)

    def test_kmz_oku(self):
        import zipfile

        kml = os.path.join(self.klasor, "icerik.kml")
        koordinat = " ".join(f"{b},{e},0" for b, e in self.kare)
        with open(kml, "w", encoding="utf-8") as f:
            f.write(
                '<kml xmlns="http://www.opengis.net/kml/2.2"><Placemark><Polygon>'
                f"<outerBoundaryIs><LinearRing><coordinates>{koordinat}</coordinates>"
                "</LinearRing></outerBoundaryIs></Polygon></Placemark></kml>"
            )
        yol = os.path.join(self.klasor, "a.kmz")
        with zipfile.ZipFile(yol, "w") as z:
            z.write(kml, "doc.kml")
        alan = alan_oku(yol)
        self.assertEqual(len(alan.dis_halka), 4)

    def test_wkt_oku(self):
        yol = os.path.join(self.klasor, "a.wkt")
        govde = ", ".join(f"{b} {e}" for b, e in self.kare + [self.kare[0]])
        with open(yol, "w", encoding="utf-8") as f:
            f.write(f"POLYGON (({govde}))")
        self.assertEqual(len(alan_oku(yol).dis_halka), 4)

    def test_csv_sira(self):
        yol = os.path.join(self.klasor, "a.csv")
        with open(yol, "w", encoding="utf-8") as f:
            f.write("# enlem,boylam\n")
            for b, e in self.kare:
                f.write(f"{e},{b}\n")
        alan = alan_oku(yol, metin_sirasi="enlem-boylam")
        self.assertAlmostEqual(alan.dis_halka[0][0], 29.90, places=6)
        self.assertAlmostEqual(alan.dis_halka[0][1], 40.70, places=6)

    def test_ncn_sinir_oku(self):
        sistem = sistem_bul("ITRF96-TM30")
        yol = os.path.join(self.klasor, "sinir.ncn")
        with open(yol, "w", encoding="utf-8") as f:
            for i, (b, e) in enumerate(self.kare, start=1):
                saga, yukari = sistem.wgs84ten(e, b)
                f.write(f"{i},{saga:.3f},{yukari:.3f},0.000,SINIR\n")
        alan = alan_oku(yol, kaynak_sistem=sistem)
        self.assertEqual(len(alan.dis_halka), 4)
        self.assertAlmostEqual(alan.dis_halka[0][0], 29.90, places=5)
        with self.assertRaises(ValueError):
            alan_oku(yol)  # sistem verilmeden okunamaz

    def test_olmayan_dosya(self):
        with self.assertRaises(FileNotFoundError):
            alan_oku(os.path.join(self.klasor, "yok.kml"))


# ---------------------------------------------------------------------------
# Karelaj
# ---------------------------------------------------------------------------


class IzgaraTesti(unittest.TestCase):
    def setUp(self):
        self.sistem = sistem_bul("ITRF96-TM30")
        self.alan = alan_sinir_kutusundan(40.750, 29.940, 40.760, 29.955)

    def _komsular(self, karelaj):
        for i in range(karelaj.satir_sayisi - 1):
            for j in range(karelaj.sutun_sayisi - 1):
                a = karelaj.matris[i][j]
                b = karelaj.matris[i][j + 1]
                c = karelaj.matris[i + 1][j]
                if a and b and c:
                    return a, b, c
        self.fail("Karelajda komşu üçlüsü bulunamadı.")

    def test_aralik_metrik(self):
        k = karelaj_uret(self.alan, self.sistem, KarelajAyari(aralik=50.0))
        a, b, c = self._komsular(k)
        self.assertAlmostEqual(math.hypot(b.saga - a.saga, b.yukari - a.yukari), 50.0, places=6)
        self.assertAlmostEqual(math.hypot(c.saga - a.saga, c.yukari - a.yukari), 50.0, places=6)

    def test_dikdortgen_izgara(self):
        k = karelaj_uret(self.alan, self.sistem, KarelajAyari(aralik=100.0, aralik_yukari=25.0))
        a, b, c = self._komsular(k)
        self.assertAlmostEqual(math.hypot(b.saga - a.saga, b.yukari - a.yukari), 100.0, places=6)
        self.assertAlmostEqual(math.hypot(c.saga - a.saga, c.yukari - a.yukari), 25.0, places=6)

    def test_tam_kat_hizalama(self):
        k = karelaj_uret(self.alan, self.sistem, KarelajAyari(aralik=25.0))
        for n in k.noktalar:
            self.assertAlmostEqual(n.saga % 25.0, 0.0, places=6)
            self.assertAlmostEqual(n.yukari % 25.0, 0.0, places=6)

    def test_alan_hizalamasi(self):
        k = karelaj_uret(self.alan, self.sistem, KarelajAyari(aralik=25.0, hizalama="alan"))
        tam_kat = all(abs(n.saga % 25.0) < 1e-6 for n in k.noktalar)
        self.assertFalse(tam_kat)

    def test_donme(self):
        k = karelaj_uret(self.alan, self.sistem, KarelajAyari(aralik=50.0, donme_acisi=30.0))
        a, b, c = self._komsular(k)
        self.assertAlmostEqual(math.hypot(b.saga - a.saga, b.yukari - a.yukari), 50.0, places=6)
        aci = math.degrees(math.atan2(b.yukari - a.yukari, b.saga - a.saga))
        self.assertAlmostEqual(aci, 30.0, places=4)

    def test_kirpma(self):
        ucgen = Alan([[(29.940, 40.750), (29.955, 40.750), (29.9475, 40.760)]])
        kirpik = karelaj_uret(ucgen, self.sistem, KarelajAyari(aralik=50.0))
        tam = karelaj_uret(ucgen, self.sistem, KarelajAyari(aralik=50.0, kirp=False))
        self.assertLess(len(kirpik.noktalar), len(tam.noktalar))
        # Üçgen, sınır kutusunun yarısı kadar: oran 0,40 - 0,60 arasında olmalı
        self.assertGreater(len(kirpik.noktalar) / len(tam.noktalar), 0.40)
        self.assertLess(len(kirpik.noktalar) / len(tam.noktalar), 0.60)

    def test_ic_bosluk_kirpmasi(self):
        delikli = Alan(
            [
                [(29.940, 40.750), (29.955, 40.750), (29.955, 40.760), (29.940, 40.760)],
                [(29.946, 40.753), (29.950, 40.753), (29.950, 40.757), (29.946, 40.757)],
            ]
        )
        tam = karelaj_uret(self.alan, self.sistem, KarelajAyari(aralik=50.0))
        delik = karelaj_uret(delikli, self.sistem, KarelajAyari(aralik=50.0))
        self.assertLess(len(delik.noktalar), len(tam.noktalar))

    def test_numaralandirma(self):
        k = karelaj_uret(
            self.alan,
            self.sistem,
            KarelajAyari(
                aralik=200.0,
                numaralandirma=NumaralandirmaAyari(profil="satir-sutun", onek="K", basamak=2),
            ),
        )
        self.assertTrue(all(n.no.startswith("K") for n in k.noktalar))
        self.assertRegex(k.noktalar[0].no, r"^K\d{2}-\d{2}$")

        k2 = karelaj_uret(
            self.alan,
            self.sistem,
            KarelajAyari(aralik=200.0, numaralandirma=NumaralandirmaAyari(baslangic=1000)),
        )
        self.assertEqual(k2.noktalar[0].no, "1000")
        self.assertEqual(k2.noktalar[1].no, "1001")

    def test_siralama(self):
        kg = karelaj_uret(self.alan, self.sistem, KarelajAyari(aralik=100.0))
        gk = karelaj_uret(
            self.alan, self.sistem, KarelajAyari(aralik=100.0, siralama="guney-kuzey")
        )
        ilk_kg = max(n.yukari for n in kg.noktalar if n.satir == min(p.satir for p in kg.noktalar))
        ilk_gk = max(n.yukari for n in gk.noktalar if n.satir == min(p.satir for p in gk.noktalar))
        self.assertGreater(ilk_kg, ilk_gk)

    def test_kose_noktalari(self):
        kose_yok = karelaj_uret(self.alan, self.sistem, KarelajAyari(aralik=200.0))
        kose_var = karelaj_uret(
            self.alan, self.sistem, KarelajAyari(aralik=200.0, kenar_noktalari=True)
        )
        self.assertEqual(len(kose_var.noktalar) - len(kose_yok.noktalar), 4)
        self.assertTrue(any(n.kod == "SINIR" for n in kose_var.noktalar))

    def test_hatali_parametreler(self):
        for ayar in (
            KarelajAyari(aralik=0),
            KarelajAyari(aralik=-5),
            KarelajAyari(aralik=50, aralik_yukari=0),
            KarelajAyari(aralik=50, hizalama="yanlis"),
            KarelajAyari(aralik=50, siralama="yanlis"),
        ):
            with self.assertRaises(ValueError):
                karelaj_uret(self.alan, self.sistem, ayar)

    def test_azami_nokta_siniri(self):
        with self.assertRaises(ValueError) as tutamac:
            karelaj_uret(self.alan, self.sistem, KarelajAyari(aralik=5, azami_nokta=100))
        self.assertIn("güvenlik sınırını", str(tutamac.exception))

    def test_cografi_sistem_reddi(self):
        with self.assertRaises(ValueError):
            karelaj_uret(self.alan, sistem_bul("WGS84"), KarelajAyari(aralik=50))

    def test_nokta_sayisi_tahmini(self):
        ayar = KarelajAyari(aralik=50.0)
        tahmin = nokta_sayisi_tahmini(self.alan, self.sistem, ayar)
        gercek = karelaj_uret(self.alan, self.sistem, ayar)
        self.assertGreaterEqual(tahmin, len(gercek.noktalar))
        self.assertLess(tahmin, len(gercek.noktalar) * 1.5)

    def test_cografi_koordinat_tutarli(self):
        """Her noktanın enlem/boylamı, izdüşüm koordinatıyla örtüşmeli."""
        k = karelaj_uret(self.alan, self.sistem, KarelajAyari(aralik=200.0))
        for n in k.noktalar:
            saga, yukari = self.sistem.wgs84ten(n.enlem, n.boylam)
            self.assertAlmostEqual(saga, n.saga, delta=0.005)
            self.assertAlmostEqual(yukari, n.yukari, delta=0.005)


# ---------------------------------------------------------------------------
# Raster
# ---------------------------------------------------------------------------


class RasterTesti(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.mkdtemp()

    def _denetle(self, yol):
        r = raster_ac(yol)
        try:
            b = r.bilgi
            self.assertEqual((b.genislik, b.yukseklik), (TIF_GENISLIK, TIF_YUKSEKLIK))
            self.assertAlmostEqual(b.piksel_x, TIF_PIKSEL, places=9)
            self.assertAlmostEqual(b.sol_ust_x, TIF_SOL_UST[0], places=4)
            self.assertAlmostEqual(b.sol_ust_y, TIF_SOL_UST[1], places=4)
            self.assertEqual(b.epsg, 5254)
            for satir in range(0, TIF_YUKSEKLIK, 5):
                for sutun in range(0, TIF_GENISLIK, 7):
                    self.assertAlmostEqual(
                        r.piksel_oku(sutun, satir), tif_beklenen(sutun, satir), places=3
                    )
            # Kapsam dışı
            self.assertIsNone(r.piksel_oku(-1, 0))
            self.assertIsNone(r.piksel_oku(0, TIF_YUKSEKLIK))
        finally:
            r.kapat()

    def test_geotiff_lzw_ongorucu2(self):
        self._denetle(gecici_dosya(self.klasor, "lzw.tif", GEOTIFF_LZW_P2))

    def test_geotiff_deflate_ongorucu3_karolu(self):
        self._denetle(gecici_dosya(self.klasor, "deflate.tif", GEOTIFF_DEFLATE_P3))

    def test_bilineer_ara_deger(self):
        """Düzlemsel yüzeyde bilineer ara değer tam sonuç vermeli."""
        yol = gecici_dosya(self.klasor, "lzw.tif", GEOTIFF_LZW_P2)
        r = raster_ac(yol)
        try:
            # Piksel merkezi (5,5) -> koordinat
            x = TIF_SOL_UST[0] + (5 + 0.5) * TIF_PIKSEL
            y = TIF_SOL_UST[1] - (5 + 0.5) * TIF_PIKSEL
            self.assertAlmostEqual(r.deger(x, y, "en-yakin"), tif_beklenen(5, 5), places=3)
            # İki piksel arası
            x2 = TIF_SOL_UST[0] + (5 + 1.0) * TIF_PIKSEL
            beklenen = (tif_beklenen(5, 5) + tif_beklenen(6, 5)) / 2.0
            self.assertAlmostEqual(r.deger(x2, y, "bilineer"), beklenen, places=3)
            self.assertAlmostEqual(r.deger(x2, y, "bikubik"), beklenen, places=3)
            with self.assertRaises(ValueError):
                r.deger(x, y, "yanlis-yontem")
        finally:
            r.kapat()

    def test_ascii_grid(self):
        yol = os.path.join(self.klasor, "a.asc")
        with open(yol, "w", encoding="utf-8") as f:
            f.write(
                "ncols 4\nnrows 3\nxllcorner 494000.0\nyllcorner 4513000.0\n"
                "cellsize 25.0\nNODATA_value -9999\n"
            )
            for satir in range(3):
                f.write(" ".join(str(100 + satir * 10 + sutun) for sutun in range(4)) + "\n")
        r = raster_ac(yol, epsg=5254)
        try:
            self.assertEqual(r.piksel_oku(0, 0), 100.0)
            self.assertEqual(r.piksel_oku(3, 2), 123.0)
            self.assertAlmostEqual(r.bilgi.sol_ust_y, 4513000.0 + 3 * 25.0, places=6)
            self.assertEqual(r.bilgi.veri_yok, -9999.0)
        finally:
            r.kapat()

    def test_ascii_grid_eksik_baslik(self):
        yol = os.path.join(self.klasor, "eksik.asc")
        with open(yol, "w", encoding="utf-8") as f:
            f.write("ncols 2\nnrows 2\n1 2\n3 4\n")
        with self.assertRaises(RasterHatasi):
            raster_ac(yol)

    def test_srtm_hgt(self):
        kenar = 601
        yol = os.path.join(self.klasor, "N40E029.hgt")
        with open(yol, "wb") as f:
            for satir in range(kenar):
                f.write(struct.pack(f">{kenar}h", *[(satir + sutun) % 3000 for sutun in range(kenar)]))
        r = raster_ac(yol)
        try:
            self.assertEqual(r.bilgi.epsg, 4326)
            self.assertTrue(r.bilgi.piksel_merkezli)
            self.assertEqual(r.piksel_oku(7, 5), 12.0)
            sinir = r.bilgi.sinir
            self.assertAlmostEqual(sinir[0], 29.0, places=6)
            self.assertAlmostEqual(sinir[3], 41.0, places=6)
            self.assertAlmostEqual(sinir[2], 30.0, places=6)
            self.assertAlmostEqual(sinir[1], 40.0, places=6)
        finally:
            r.kapat()

    def test_hgt_hatali_ad(self):
        yol = os.path.join(self.klasor, "gecersiz.hgt")
        with open(yol, "wb") as f:
            f.write(b"\x00" * (1201 * 1201 * 2))
        with self.assertRaises(RasterHatasi):
            raster_ac(yol)

    def test_desteklenmeyen_bicim(self):
        yol = os.path.join(self.klasor, "a.jpg")
        with open(yol, "wb") as f:
            f.write(b"x")
        with self.assertRaises(RasterHatasi):
            raster_ac(yol)

    def test_packbits_cozucu(self):
        # TIFF PackBits: 2 -> 3 hazır bayt, 254 -> sonraki baytı 3 kez, 0 -> 1 bayt
        self.assertEqual(_packbits_coz(bytes([2, 65, 66, 67, 254, 68, 0, 69])), b"ABCDDDE")
        self.assertEqual(_packbits_coz(bytes([128, 0, 65])), b"A")
        self.assertEqual(_packbits_coz(b""), b"")

    def test_lzw_cozucu(self):
        """Basit bir LZW akışı, sözlük genişlemesiyle birlikte çözülmeli."""
        # 256 = temizleme, 257 = bitiş kodu; 9 bitlik kodlar
        kodlar = [256, 65, 66, 65, 66, 258, 257]
        bit_dizisi = 0
        bit_sayisi = 0
        cikti = bytearray()
        for kod in kodlar:
            bit_dizisi = (bit_dizisi << 9) | kod
            bit_sayisi += 9
            while bit_sayisi >= 8:
                cikti.append((bit_dizisi >> (bit_sayisi - 8)) & 0xFF)
                bit_sayisi -= 8
        if bit_sayisi:
            cikti.append((bit_dizisi << (8 - bit_sayisi)) & 0xFF)
        self.assertEqual(_lzw_coz(bytes(cikti)), b"ABABAB")


# ---------------------------------------------------------------------------
# Kot kaynakları
# ---------------------------------------------------------------------------


class _SahteSunucu(BaseHTTPRequestHandler):
    """OpenTopoData / Open-Elevation / Google yanıtlarını taklit eder."""

    sayac = {"istek": 0, "kota_kalan": 2}

    def log_message(self, *_a):
        pass

    def _json(self, kod, govde):
        ham = json.dumps(govde).encode()
        self.send_response(kod)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(ham)))
        self.end_headers()
        self.wfile.write(ham)

    @staticmethod
    def _kot(metin):
        enlem, boylam = (float(v) for v in metin.split(","))
        return enlem * 10.0 + boylam

    def do_GET(self):
        type(self).sayac["istek"] += 1
        parcali = urllib.parse.urlparse(self.path)
        sorgu = urllib.parse.parse_qs(parcali.query)
        if parcali.path.startswith("/v1/hatali"):
            return self._json(200, {"status": "INVALID_REQUEST", "error": "veri kümesi yok"})
        if parcali.path.startswith("/v1/kota") and type(self).sayac["kota_kalan"] > 0:
            type(self).sayac["kota_kalan"] -= 1
            self.send_response(429)
            self.send_header("Retry-After", "0")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if parcali.path.startswith("/v1/"):
            konumlar = sorgu["locations"][0].split("|")
            return self._json(
                200,
                {"status": "OK", "results": [{"elevation": self._kot(k)} for k in konumlar]},
            )
        if parcali.path.startswith("/maps/api/elevation"):
            if sorgu.get("key", [""])[0] != "GECERLI":
                return self._json(200, {"status": "REQUEST_DENIED", "error_message": "anahtar"})
            konumlar = sorgu["locations"][0].split("|")
            return self._json(
                200, {"status": "OK", "results": [{"elevation": self._kot(k)} for k in konumlar]}
            )
        self._json(404, {})

    def do_POST(self):
        type(self).sayac["istek"] += 1
        uzunluk = int(self.headers.get("Content-Length", 0))
        veri = json.loads(self.rfile.read(uzunluk))
        self._json(
            200,
            {
                "results": [
                    {"elevation": p["latitude"] * 10.0 + p["longitude"]}
                    for p in veri["locations"]
                ]
            },
        )


class KaynakTesti(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sunucu = ThreadingHTTPServer(("127.0.0.1", 0), _SahteSunucu)
        cls.temel = f"http://127.0.0.1:{cls.sunucu.server_address[1]}"
        threading.Thread(target=cls.sunucu.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.sunucu.shutdown()

    def setUp(self):
        self.koordinatlar = [(40.75, 29.95), (40.76, 29.96), (41.00, 28.98)]
        self.beklenen = [e * 10.0 + b for e, b in self.koordinatlar]

    def test_opentopodata(self):
        kaynak = OpenTopoData("srtm30m", sunucu=self.temel, istekler_arasi_sn=0)
        sonuc = kaynak.toplu_oku(self.koordinatlar)
        for a, b in zip(sonuc, self.beklenen):
            self.assertAlmostEqual(a, b, places=4)

    def test_open_elevation(self):
        kaynak = OpenElevation(sunucu=self.temel, istekler_arasi_sn=0)
        sonuc = kaynak.toplu_oku(self.koordinatlar)
        for a, b in zip(sonuc, self.beklenen):
            self.assertAlmostEqual(a, b, places=4)

    def test_servis_hatasi(self):
        kaynak = OpenTopoData("hatali", sunucu=self.temel, istekler_arasi_sn=0)
        with self.assertRaises(KaynakHatasi) as tutamac:
            kaynak.toplu_oku(self.koordinatlar)
        self.assertIn("INVALID_REQUEST", str(tutamac.exception))

    def test_kota_sonrasi_yeniden_deneme(self):
        _SahteSunucu.sayac["kota_kalan"] = 2
        onceki = _SahteSunucu.sayac["istek"]
        kaynak = OpenTopoData("kota", sunucu=self.temel, istekler_arasi_sn=0, yeniden_deneme=3)
        sonuc = kaynak.toplu_oku(self.koordinatlar)
        self.assertEqual(_SahteSunucu.sayac["istek"] - onceki, 3)
        for a, b in zip(sonuc, self.beklenen):
            self.assertAlmostEqual(a, b, places=4)

    def test_baglanti_hatasi(self):
        kaynak = OpenTopoData(
            "srtm30m", sunucu="http://127.0.0.1:1", istekler_arasi_sn=0, yeniden_deneme=0
        )
        with self.assertRaises(KaynakHatasi) as tutamac:
            kaynak.toplu_oku(self.koordinatlar)
        self.assertIn("erişilemedi", str(tutamac.exception))

    def test_google_anahtarsiz(self):
        with self.assertRaises(KaynakHatasi):
            GoogleElevation("")

    def test_veri_bosluğu_suzgeci(self):
        self.assertIsNone(_sayiya(-32768))
        self.assertIsNone(_sayiya(None))
        self.assertIsNone(_sayiya("abc"))
        self.assertIsNone(_sayiya(float("nan")))
        self.assertEqual(_sayiya(123.5), 123.5)
        self.assertEqual(_sayiya("45"), 45.0)

    def test_yerel_sym(self):
        klasor = tempfile.mkdtemp()
        yol = gecici_dosya(klasor, "sym.tif", GEOTIFF_LZW_P2)
        kaynak = kaynak_olustur("yerel", sym_yolu=yol, ornekleme="en-yakin")
        try:
            sistem = sistem_bul("ITRF96-TM30")
            enlem, boylam = sistem.wgs84e(
                TIF_SOL_UST[0] + 5.5 * TIF_PIKSEL, TIF_SOL_UST[1] - 3.5 * TIF_PIKSEL
            )
            sonuc = kaynak.toplu_oku([(enlem, boylam)])
            self.assertAlmostEqual(sonuc[0], tif_beklenen(5, 3), places=3)
            # Kapsam dışı nokta
            self.assertEqual(kaynak.kapsam_disi_sayisi([(41.5, 31.5)]), 1)
            self.assertIn("sağa", kaynak.kapsam_ozeti())
        finally:
            kaynak.kapat()

    def test_yerel_sym_klasor(self):
        klasor = tempfile.mkdtemp()
        gecici_dosya(klasor, "a.tif", GEOTIFF_LZW_P2)
        kaynak = kaynak_olustur("yerel", sym_yolu=klasor)
        try:
            self.assertEqual(len(kaynak.dosyalar), 1)
        finally:
            kaynak.kapat()

    def test_kaynak_olustur_hatalari(self):
        with self.assertRaises(KaynakHatasi):
            kaynak_olustur("yok-boyle")
        with self.assertRaises(KaynakHatasi):
            kaynak_olustur("opentopodata", veri_kumesi="olmayan-kume")
        with self.assertRaises(KaynakHatasi):
            kaynak_olustur("yerel")
        with self.assertRaises(KaynakHatasi):
            kaynak_olustur("yerel", sym_yolu="/olmayan/yol.tif")

    def test_kotlari_doldur_ve_onbellek(self):
        klasor = tempfile.mkdtemp()
        onbellek = KotOnbellegi(os.path.join(klasor, "o.sqlite"))
        kaynak = OpenTopoData("srtm30m", sunucu=self.temel, istekler_arasi_sn=0)
        noktalar = [
            Nokta(no=str(i), saga=0.0, yukari=0.0, enlem=e, boylam=b, satir=0, sutun=i)
            for i, (e, b) in enumerate(self.koordinatlar)
        ]
        try:
            ozet = kotlari_doldur(noktalar, kaynak, onbellek=onbellek)
            self.assertEqual(ozet.okunan, 3)
            self.assertEqual(ozet.onbellekten, 0)
            self.assertEqual(ozet.istek_sayisi, 1)
            # İkinci tur tamamen önbellekten gelmeli
            noktalar2 = [
                Nokta(no=str(i), saga=0.0, yukari=0.0, enlem=e, boylam=b, satir=0, sutun=i)
                for i, (e, b) in enumerate(self.koordinatlar)
            ]
            ozet2 = kotlari_doldur(noktalar2, kaynak, onbellek=onbellek)
            self.assertEqual(ozet2.onbellekten, 3)
            self.assertEqual(ozet2.istek_sayisi, 0)
            # Kot kaydırması uygulanmalı
            noktalar3 = [
                Nokta(no="1", saga=0.0, yukari=0.0, enlem=40.75, boylam=29.95, satir=0, sutun=0)
            ]
            kotlari_doldur(noktalar3, kaynak, onbellek=onbellek, kot_kaydirma=-0.35)
            self.assertAlmostEqual(noktalar3[0].kot, self.beklenen[0] - 0.35, places=4)
        finally:
            onbellek.kapat()


class OnbellekTesti(unittest.TestCase):
    def test_yaz_oku_temizle(self):
        klasor = tempfile.mkdtemp()
        with KotOnbellegi(os.path.join(klasor, "o.sqlite")) as onbellek:
            onbellek.topluca_yaz("k", [(40.75, 29.95, 123.4), (40.76, 29.96, None)])
            sonuc = onbellek.topluca_al("k", [(40.75, 29.95), (40.76, 29.96), (40.77, 29.97)])
            self.assertEqual(sonuc[0], 123.4)
            self.assertIsNone(sonuc[1])
            self.assertNotIn(2, sonuc)
            self.assertEqual(onbellek.kayit_sayisi(), 2)
            self.assertEqual(onbellek.temizle("k"), 2)
            self.assertEqual(onbellek.kayit_sayisi(), 0)

    def test_devre_disi(self):
        onbellek = KotOnbellegi(etkin=False)
        onbellek.topluca_yaz("k", [(1.0, 2.0, 3.0)])
        self.assertEqual(onbellek.topluca_al("k", [(1.0, 2.0)]), {})
        onbellek.kapat()


# ---------------------------------------------------------------------------
# Yazıcılar
# ---------------------------------------------------------------------------


def ornek_karelaj(aralik=10.0, boyut=11, kot_islevi=None):
    """Sentetik, tam dolu bir karelaj üretir (yazıcı ve hacim testleri için)."""
    kot_islevi = kot_islevi or (lambda x, y: 100.0 + 0.1 * x)
    sistem = sistem_bul("ITRF96-TM30")
    matris = []
    noktalar = []
    for i in range(boyut):
        satir = []
        for j in range(boyut):
            x = 494000.0 + j * aralik
            y = 4514000.0 - i * aralik
            enlem, boylam = sistem.wgs84e(x, y)
            nokta = Nokta(
                no=f"{i + 1}-{j + 1}",
                saga=x,
                yukari=y,
                enlem=enlem,
                boylam=boylam,
                satir=i,
                sutun=j,
                kot=kot_islevi(j * aralik, i * aralik),
                kod="KARELAJ",
            )
            satir.append(nokta)
            noktalar.append(nokta)
        matris.append(satir)
    return Karelaj(
        noktalar=noktalar,
        matris=matris,
        sistem=sistem,
        ayar=KarelajAyari(aralik=aralik),
        alan=alan_sinir_kutusundan(40.75, 29.94, 40.76, 29.95),
        baslangic_saga=494000.0,
        baslangic_yukari=4514000.0 - (boyut - 1) * aralik,
        satir_sayisi=boyut,
        sutun_sayisi=boyut,
        izdusum_halkalari=[[(494000.0, 4513900.0), (494100.0, 4513900.0), (494100.0, 4514000.0), (494000.0, 4514000.0)]],
    )


class YaziciTesti(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.mkdtemp()
        self.karelaj = ornek_karelaj()
        self.noktalar = self.karelaj.noktalar[:3]
        self.noktalar[2].kot = None

    def test_ncn_varsayilan_duzen(self):
        satirlar = ncn_satirlari(self.noktalar)
        self.assertEqual(len(satirlar), 2)  # kotsuz nokta atlanır
        alanlar = satirlar[0].split(",")
        self.assertEqual(len(alanlar), 5)
        self.assertEqual(alanlar[0], "1-1")
        self.assertAlmostEqual(float(alanlar[1]), 494000.0, places=3)  # Y = sağa
        self.assertAlmostEqual(float(alanlar[2]), 4514000.0, places=3)  # X = yukarı
        self.assertEqual(alanlar[4], "KARELAJ")

    def test_ncn_profiller(self):
        for profil in NCN_PROFILLERI:
            with self.subTest(profil=profil):
                satirlar = ncn_satirlari(self.noktalar, NCN_PROFILLERI[profil])
                self.assertTrue(satirlar)

    def test_ncn_sutun_sirasi(self):
        ayar = profil_coz("netcad", sutunlar="no,x,y,z")
        alanlar = ncn_satirlari(self.noktalar, ayar)[0].split(",")
        self.assertAlmostEqual(float(alanlar[1]), 4514000.0, places=3)  # X önce
        self.assertAlmostEqual(float(alanlar[2]), 494000.0, places=3)

    def test_ncn_kotsuz_davranis(self):
        self.assertEqual(len(ncn_satirlari(self.noktalar, profil_coz("netcad", kotsuz="atla"))), 2)
        sifirli = ncn_satirlari(self.noktalar, profil_coz("netcad", kotsuz="sifir"))
        self.assertEqual(len(sifirli), 3)
        self.assertEqual(sifirli[2].split(",")[3], "0.000")
        bos = ncn_satirlari(self.noktalar, profil_coz("netcad", kotsuz="bos"))
        self.assertEqual(bos[2].split(",")[3], "")

    def test_ncn_dosya_yazimi(self):
        yol = os.path.join(self.klasor, "a.ncn")
        adet = ncn_yaz(yol, self.noktalar)
        self.assertEqual(adet, 2)
        with open(yol, "rb") as f:
            ham = f.read()
        self.assertIn(b"\r\n", ham)  # Netcad Windows satır sonu bekler
        self.assertTrue(ham.decode("cp1254").startswith("1-1,494000.000"))

    def test_ncn_hatali_ayar(self):
        with self.assertRaises(ValueError):
            profil_coz("netcad", sutunlar="no,olmayan")
        with self.assertRaises(ValueError):
            profil_coz("olmayan-profil")
        with self.assertRaises(ValueError):
            profil_coz("netcad", kotsuz="yanlis")

    def test_csv(self):
        yol = os.path.join(self.klasor, "a.csv")
        adet = csv_yaz(yol, self.noktalar)
        self.assertEqual(adet, 3)
        with open(yol, "rb") as f:
            metin = f.read().decode("cp1254")
        self.assertIn(";", metin)
        self.assertIn("494000,000", metin)  # Türkçe ondalık ayırıcı
        csv_yaz(yol, self.noktalar, ingilizce=True)
        with open(yol, "rb") as f:
            metin = f.read().decode("utf-8")
        self.assertIn("494000.000", metin)

    def test_xyz(self):
        yol = os.path.join(self.klasor, "a.xyz")
        adet = xyz_yaz(yol, self.noktalar)
        self.assertEqual(adet, 2)
        with open(yol, encoding="utf-8") as f:
            ilk = f.readline().split()
        self.assertEqual(len(ilk), 3)

    def test_dxf(self):
        egriler = kontur_uret(self.karelaj, aralik=2.0)
        yol = dxf_yaz(
            os.path.join(self.klasor, "a.dxf"), self.karelaj, konturlar=egriler, nokta_numarasi=True
        )
        with open(yol, "rb") as f:
            metin = f.read().decode("cp1254")
        self.assertTrue(metin.rstrip().endswith("EOF"))
        self.assertIn("AC1009", metin)
        self.assertIn("KARELAJ_NOKTA", metin)
        self.assertIn("KARELAJ_KONTUR", metin)
        self.assertEqual(metin.count("\nPOINT\n"), len(self.karelaj.noktalar))
        # Her POLYLINE bir SEQEND ile kapanmalı
        self.assertEqual(metin.count("\nPOLYLINE\n"), metin.count("\nSEQEND\n"))

    def test_kml(self):
        yol = kml_yaz(os.path.join(self.klasor, "a.kml"), self.karelaj)
        kok = ElementTree.parse(yol).getroot()
        ad = "{http://www.opengis.net/kml/2.2}"
        yer_isaretleri = list(kok.iter(ad + "Placemark"))
        self.assertGreaterEqual(len(yer_isaretleri), len(self.karelaj.noktalar))

    def test_geojson(self):
        yol = geojson_yaz(os.path.join(self.klasor, "a.geojson"), self.karelaj)
        with open(yol, encoding="utf-8") as f:
            veri = json.load(f)
        self.assertEqual(veri["type"], "FeatureCollection")
        noktalar = [o for o in veri["features"] if o["geometry"]["type"] == "Point"]
        self.assertEqual(len(noktalar), len(self.karelaj.noktalar))
        self.assertIn("kot", noktalar[0]["properties"])

    def test_rapor(self):
        metin = rapor_metni(self.karelaj, hacim=hacim_hesapla(self.karelaj, 105.0))
        for parca in (
            "KOT KARELAJI TEKNİK ÖZET RAPORU",
            "ÇALIŞMA ALANI",
            "KOORDİNAT SİSTEMİ",
            "TUDKA-99",
            "HACİM HESABI",
        ):
            self.assertIn(parca, metin)

    def test_turkce_sayi_bicimi(self):
        self.assertEqual(bicim.sayi(13372016.9812), "13.372.016,98")
        self.assertEqual(bicim.sayi(0.5, 3), "0,500")
        self.assertEqual(bicim.tam_sayi(56865), "56.865")
        self.assertIn("ha", bicim.alan_metni(10000.0))


# ---------------------------------------------------------------------------
# Kontur ve hacim
# ---------------------------------------------------------------------------


class KonturHacimTesti(unittest.TestCase):
    def test_kontur_kotlari(self):
        self.assertEqual(kontur_kotlari(100.0, 110.0, 2.0), [100.0, 102.0, 104.0, 106.0, 108.0, 110.0])
        self.assertEqual(kontur_kotlari(100.5, 104.0, 1.0), [101.0, 102.0, 103.0, 104.0])
        with self.assertRaises(ValueError):
            kontur_kotlari(0.0, 10.0, 0.0)

    def test_kontur_konumu(self):
        """z = 100 + 0,1x yüzeyinde eş yükselti eğrileri düşey doğrular olmalı."""
        karelaj = ornek_karelaj(aralik=10.0, boyut=11)
        egriler = kontur_uret(karelaj, aralik=2.0)
        self.assertGreaterEqual(len(egriler), 4)
        for egri in egriler:
            beklenen_x = 494000.0 + (egri.kot - 100.0) / 0.1
            for x, _y in egri.noktalar:
                self.assertAlmostEqual(x, beklenen_x, places=4)

    def test_hacim_analitik(self):
        """
        z = 100 + 0,1x düzlemi, referans 105 m, 100 m x 100 m alan.
        Sıfır çizgisi x = 50 m'de; kazı = dolgu = 12.500 m³.
        """
        karelaj = ornek_karelaj(aralik=10.0, boyut=11)
        sonuc = hacim_hesapla(karelaj, 105.0, alt_bolme=32)
        self.assertAlmostEqual(sonuc.kazi_m3, 12500.0, delta=1.0)
        self.assertAlmostEqual(sonuc.dolgu_m3, 12500.0, delta=1.0)
        self.assertAlmostEqual(sonuc.net_m3, 0.0, delta=1.0)
        self.assertAlmostEqual(sonuc.klasik_net_m3, 0.0, delta=1.0)
        self.assertAlmostEqual(sonuc.kazi_alani_m2, 5000.0, delta=50.0)
        self.assertEqual(sonuc.hesaplanan_kare, 100)
        self.assertEqual(sonuc.atlanan_kare, 0)

    def test_hacim_duz_yuzey(self):
        """Sabit kotlu yüzeyde hacim, kot farkı x alan olmalı."""
        karelaj = ornek_karelaj(aralik=10.0, boyut=11, kot_islevi=lambda x, y: 110.0)
        sonuc = hacim_hesapla(karelaj, 100.0, alt_bolme=4)
        self.assertAlmostEqual(sonuc.kazi_m3, 10.0 * 100.0 * 100.0, delta=0.5)
        self.assertAlmostEqual(sonuc.dolgu_m3, 0.0, delta=0.001)

    def test_hacim_eksik_kose(self):
        karelaj = ornek_karelaj(aralik=10.0, boyut=5)
        karelaj.matris[0][0].kot = None
        sonuc = hacim_hesapla(karelaj, 100.0)
        self.assertEqual(sonuc.atlanan_kare, 1)
        self.assertEqual(sonuc.hesaplanan_kare, 15)

    def test_hacim_hatali_alt_bolme(self):
        with self.assertRaises(ValueError):
            hacim_hesapla(ornek_karelaj(), 100.0, alt_bolme=0)


# ---------------------------------------------------------------------------
# Arayüz sunucusu
# ---------------------------------------------------------------------------


class SunucuTesti(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from karelaj import sunucu as sunucu_modulu

        cls.cikti = tempfile.mkdtemp()
        cls.sym = gecici_dosya(tempfile.mkdtemp(), "sym.tif", GEOTIFF_LZW_P2)
        isleyici = type(
            "_TestIsleyici", (sunucu_modulu._Isleyici,), {"cikti_klasoru": cls.cikti}
        )
        cls.sunucu = ThreadingHTTPServer(("127.0.0.1", 0), isleyici)
        cls.temel = f"http://127.0.0.1:{cls.sunucu.server_address[1]}"
        threading.Thread(target=cls.sunucu.serve_forever, daemon=True).start()

        sistem = sistem_bul("ITRF96-TM30")
        sol_ust = sistem.wgs84e(TIF_SOL_UST[0] + 20.0, TIF_SOL_UST[1] - 20.0)
        sag_alt = sistem.wgs84e(
            TIF_SOL_UST[0] + (TIF_GENISLIK - 2) * TIF_PIKSEL,
            TIF_SOL_UST[1] - (TIF_YUKSEKLIK - 2) * TIF_PIKSEL,
        )
        cls.halka = [
            [sol_ust[1], sol_ust[0]],
            [sag_alt[1], sol_ust[0]],
            [sag_alt[1], sag_alt[0]],
            [sol_ust[1], sag_alt[0]],
        ]

    @classmethod
    def tearDownClass(cls):
        cls.sunucu.shutdown()

    def _ortak(self, **ekler):
        temel = {
            "halkalar": [self.halka],
            "ad": "test",
            "aralik": 40.0,
            "kaynak": "yerel",
            "sym": self.sym,
        }
        temel.update(ekler)
        return temel

    def _gonder(self, uc, govde):
        istek = urllib.request.Request(
            self.temel + uc,
            data=json.dumps(govde).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(istek, timeout=60) as yanit:
                return yanit.status, json.loads(yanit.read())
        except urllib.error.HTTPError as hata:
            return hata.code, json.loads(hata.read())

    def _al(self, uc):
        try:
            with urllib.request.urlopen(self.temel + uc, timeout=30) as yanit:
                return yanit.status, yanit.read()
        except urllib.error.HTTPError as hata:
            return hata.code, hata.read()

    def test_ana_sayfa(self):
        kod, govde = self._al("/")
        self.assertEqual(kod, 200)
        self.assertIn(b"Kot Karelaj", govde)

    def test_baslangic_verisi(self):
        kod, govde = self._al("/api/baslangic")
        self.assertEqual(kod, 200)
        veri = json.loads(govde)
        self.assertGreater(len(veri["sistemler"]), 20)
        self.assertGreater(len(veri["veri_kumeleri"]), 3)
        self.assertGreater(len(veri["ncn_profilleri"]), 3)

    def test_bilinmeyen_uc(self):
        self.assertEqual(self._al("/olmayan")[0], 404)

    def test_onizleme(self):
        kod, veri = self._gonder("/api/onizleme", self._ortak())
        self.assertEqual(kod, 200)
        self.assertGreater(veri["nokta_sayisi"], 0)
        self.assertEqual(veri["sistem_kod"], "ITRF96-TM30")

    def test_uretim(self):
        kod, veri = self._gonder(
            "/api/uret",
            self._ortak(bicimler=["ncn", "csv", "kml", "geojson", "dxf", "xyz", "rapor"], hacim_kotu=120),
        )
        self.assertEqual(kod, 200)
        self.assertEqual(len(veri["dosyalar"]), 7)
        self.assertEqual(veri["eksik_kot"], 0)
        self.assertTrue(veri["hacim"])
        self.assertIn("KOT KARELAJI", veri["rapor"])
        kod, govde = self._al(veri["dosyalar"][0]["baglanti"])
        self.assertEqual(kod, 200)
        self.assertGreater(len(govde), 0)

    def test_gecersiz_girdiler(self):
        durumlar = [
            ({"halkalar": []}, "çizilmedi"),
            (self._ortak(aralik=0), "sıfırdan büyük"),
            (self._ortak(aralik="abc"), "sayı olmalı"),
            (self._ortak(aralik=-5), "sıfırdan büyük"),
            (self._ortak(kontur=0), "sıfırdan büyük"),
            (self._ortak(aralik_yukari=0), "sıfırdan büyük"),
            (self._ortak(sistem="YOK"), "Bilinmeyen koordinat"),
            (self._ortak(sym="/olmayan.tif"), "bulunamadı"),
        ]
        for govde, beklenen in durumlar:
            with self.subTest(beklenen=beklenen):
                kod, veri = self._gonder("/api/uret", govde)
                self.assertEqual(kod, 400)
                self.assertIn(beklenen, veri["hata"])

    def test_sifir_gecerli_deger(self):
        """Sıfır, 'verilmedi' sayılmamalı: hacim referans kotu 0 geçerlidir."""
        kod, veri = self._gonder("/api/uret", self._ortak(hacim_kotu=0, bicimler=["ncn"]))
        self.assertEqual(kod, 200)
        self.assertTrue(veri["hacim"])

    def test_yol_gecisi_engellenir(self):
        for kotu in ["../../../etc/passwd", "....//etc/passwd", "/etc/passwd", "..\\..\\win.ini"]:
            with self.subTest(yol=kotu):
                kod, _ = self._al("/indir?dosya=" + urllib.parse.quote(kotu, safe=""))
                self.assertNotEqual(kod, 200)

    def test_dosya_adi_temizlenir(self):
        kod, veri = self._gonder("/api/uret", self._ortak(ad="../../kotu ad", bicimler=["ncn"]))
        self.assertEqual(kod, 200)
        ad = veri["dosyalar"][0]["ad"]
        self.assertNotIn("..", ad)
        self.assertNotIn("/", ad)


# ---------------------------------------------------------------------------
# Komut satırı
# ---------------------------------------------------------------------------


class CliTesti(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.mkdtemp()
        self.sym = gecici_dosya(self.klasor, "sym.tif", GEOTIFF_LZW_P2)
        sistem = sistem_bul("ITRF96-TM30")
        self.sol_ust = sistem.wgs84e(TIF_SOL_UST[0] + 20.0, TIF_SOL_UST[1] - 20.0)
        self.sag_alt = sistem.wgs84e(
            TIF_SOL_UST[0] + (TIF_GENISLIK - 2) * TIF_PIKSEL,
            TIF_SOL_UST[1] - (TIF_YUKSEKLIK - 2) * TIF_PIKSEL,
        )

    def _sinir(self):
        return (
            f"{self.sol_ust[0]:.8f},{self.sol_ust[1]:.8f},"
            f"{self.sag_alt[0]:.8f},{self.sag_alt[1]:.8f}"
        )

    def test_uret(self):
        from karelaj.cli import main

        cikti = os.path.join(self.klasor, "cikti")
        kod = main(
            [
                "uret", "--sinir", self._sinir(), "--aralik", "40",
                "--kaynak", "yerel", "--sym", self.sym,
                "--bicim", "ncn,csv,rapor", "-c", cikti, "--ad", "deneme", "--sessiz",
            ]
        )
        self.assertEqual(kod, 0)
        for ad in ("deneme.ncn", "deneme.csv", "deneme-rapor.txt"):
            self.assertTrue(os.path.exists(os.path.join(cikti, ad)), ad)
        with open(os.path.join(cikti, "deneme.ncn"), "rb") as f:
            satirlar = f.read().decode("cp1254").strip().splitlines()
        self.assertGreater(len(satirlar), 3)
        self.assertEqual(len(satirlar[0].split(",")), 5)

    def test_kot_yok(self):
        from karelaj.cli import main

        cikti = os.path.join(self.klasor, "cikti2")
        kod = main(
            ["uret", "--sinir", self._sinir(), "--aralik", "40", "--kot-yok",
             "--bicim", "ncn", "--ncn-kotsuz", "sifir", "-c", cikti, "--ad", "a", "--sessiz"]
        )
        self.assertEqual(kod, 0)
        with open(os.path.join(cikti, "a.ncn"), "rb") as f:
            ilk = f.read().decode("cp1254").splitlines()[0]
        self.assertEqual(ilk.split(",")[3], "0.000")

    def test_hatali_sinir(self):
        from karelaj.cli import main

        self.assertEqual(main(["uret", "--sinir", "40,29", "--sessiz"]), 2)
        self.assertEqual(main(["uret", "--sinir", "40,29,41,abc", "--sessiz"]), 2)
        self.assertEqual(main(["uret", "--sinir", "999,29,41,30", "--sessiz"]), 2)
        self.assertEqual(main(["uret", "--sessiz"]), 2)

    def test_hatali_bicim_ve_sistem(self):
        from karelaj.cli import main

        self.assertEqual(
            main(["uret", "--sinir", self._sinir(), "--bicim", "olmayan", "--sessiz"]), 2
        )
        self.assertEqual(
            main(["uret", "--sinir", self._sinir(), "--sistem", "YOK-BOYLE", "--sessiz"]), 2
        )
        self.assertEqual(
            main(["uret", "--sinir", self._sinir(), "--dilim", "99", "--sessiz"]), 2
        )

    def test_alt_komutlar(self):
        from karelaj.cli import main

        self.assertEqual(main(["sistemler"]), 0)
        self.assertEqual(main(["kaynaklar"]), 0)
        self.assertEqual(main(["donustur", "40.7654,29.9408"]), 0)
        self.assertEqual(
            main(["onbellek", "--onbellek", os.path.join(self.klasor, "o.sqlite")]), 0
        )

    def test_dar_kodlamali_cikti(self):
        """
        Türkçe karakter taşımayan bir çıktı kodlamasında (Windows'ta çıktı
        dosyaya yönlendirildiğinde olduğu gibi) komutlar çökmemeli.
        """
        from karelaj.cli import main

        for komut in (["sistemler"], ["kaynaklar"], ["donustur", "40.7654,29.9408"]):
            with self.subTest(komut=komut[0]):
                tampon = io.BytesIO()
                dar = io.TextIOWrapper(tampon, encoding="cp1252", errors="strict")
                eski_cikti, eski_hata = sys.stdout, sys.stderr
                try:
                    sys.stdout = dar
                    sys.stderr = io.TextIOWrapper(
                        io.BytesIO(), encoding="cp1252", errors="strict"
                    )
                    kod = main(komut)
                finally:
                    sys.stdout, sys.stderr = eski_cikti, eski_hata
                self.assertEqual(kod, 0, f"{komut[0]} dar kodlamada başarısız oldu")

    def test_api_anahtari_rapora_yazilmaz(self):
        """Komut satırında verilen API anahtarı rapora düz metin girmemeli."""
        from karelaj.cli import _komut_metni

        eski = sys.argv
        try:
            sys.argv = [
                "karelaj", "uret", "--kaynak", "google",
                "--google-anahtar", "AIzaGIZLIANAHTAR123", "--aralik", "25",
            ]
            metin = _komut_metni()
            self.assertNotIn("AIzaGIZLIANAHTAR123", metin)
            self.assertIn("--google-anahtar ***", metin)
            self.assertIn("--aralik 25", metin)

            sys.argv = ["karelaj", "uret", "--google-anahtar=AIzaGIZLIANAHTAR123"]
            metin = _komut_metni()
            self.assertNotIn("AIzaGIZLIANAHTAR123", metin)
            self.assertIn("--google-anahtar=***", metin)
        finally:
            sys.argv = eski

    def test_boru_erken_kapanirsa(self):
        """
        Çıktı borusu erken kapandığında (``... | more`` gibi) program
        hata izlemesi basmadan sıfır dönmeli.
        """
        from karelaj.cli import main

        class _KapaliBoru(io.TextIOBase):
            def write(self, _metin):
                raise BrokenPipeError(32, "Broken pipe")

            def writable(self):
                return True

        eski_cikti = sys.stdout
        try:
            sys.stdout = _KapaliBoru()
            kod = main(["sistemler"])
        finally:
            sys.stdout = eski_cikti
        self.assertEqual(kod, 0)

    def test_komut_verilmeden(self):
        """Komut yazılmadan seçenek verilirse 'uret' varsayılmalı."""
        from karelaj.cli import main

        cikti = os.path.join(self.klasor, "cikti3")
        kod = main(
            ["--sinir", self._sinir(), "--aralik", "40", "--kot-yok",
             "--bicim", "ncn", "-c", cikti, "--ad", "b", "--sessiz"]
        )
        self.assertEqual(kod, 0)
        self.assertTrue(os.path.exists(os.path.join(cikti, "b.ncn")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
