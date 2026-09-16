# -*- coding: utf-8 -*-
"""
DXF çıktısı (AutoCAD R12)
=========================

Karelajı Netcad, AutoCAD, BricsCAD ve benzeri tüm CAD yazılımlarının
okuyabildiği R12 ASCII DXF olarak yazar. R12 sürümü bilinçli seçilmiştir:
en eski ve en geniş uyumlu DXF sürümüdür, hiçbir CAD yazılımı okurken
sürüm uyarısı vermez.

Katman düzeni
-------------

======================  ====================================================
``KARELAJ_NOKTA``       Karelaj noktaları (POINT, z = kot)
``KARELAJ_KOT``         Kot yazıları (TEXT)
``KARELAJ_NO``          Nokta numarası yazıları (TEXT)
``KARELAJ_IZGARA``      Karelaj çizgileri (LINE)
``KARELAJ_SINIR``       Çalışma alanı sınırı (POLYLINE)
``KARELAJ_KONTUR``      Eş yükselti eğrileri (3B POLYLINE)
======================  ====================================================
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence, Tuple

__all__ = ["dxf_yaz", "KATMANLAR"]

# katman adı -> AutoCAD renk numarası
KATMANLAR: Dict[str, int] = {
    "KARELAJ_NOKTA": 7,
    "KARELAJ_KOT": 3,
    "KARELAJ_NO": 4,
    "KARELAJ_IZGARA": 8,
    "KARELAJ_SINIR": 1,
    "KARELAJ_KONTUR": 2,
}


class _DxfYazici:
    def __init__(self) -> None:
        self.parcalar: List[str] = []
        self.min_x = self.min_y = self.min_z = float("inf")
        self.max_x = self.max_y = self.max_z = float("-inf")

    def kod(self, grup: int, deger) -> None:
        self.parcalar.append(f"{grup}\n{deger}\n")

    def sinir_guncelle(self, x: float, y: float, z: float = 0.0) -> None:
        self.min_x = min(self.min_x, x)
        self.max_x = max(self.max_x, x)
        self.min_y = min(self.min_y, y)
        self.max_y = max(self.max_y, y)
        self.min_z = min(self.min_z, z)
        self.max_z = max(self.max_z, z)

    def nokta(self, katman: str, x: float, y: float, z: float) -> None:
        self.kod(0, "POINT")
        self.kod(8, katman)
        self.kod(10, f"{x:.4f}")
        self.kod(20, f"{y:.4f}")
        self.kod(30, f"{z:.4f}")
        self.sinir_guncelle(x, y, z)

    def yazi(
        self, katman: str, x: float, y: float, z: float, metin: str, yukseklik: float
    ) -> None:
        self.kod(0, "TEXT")
        self.kod(8, katman)
        self.kod(10, f"{x:.4f}")
        self.kod(20, f"{y:.4f}")
        self.kod(30, f"{z:.4f}")
        self.kod(40, f"{yukseklik:.4f}")
        self.kod(1, metin)
        self.sinir_guncelle(x, y, z)

    def cizgi(
        self,
        katman: str,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        z: float = 0.0,
    ) -> None:
        self.kod(0, "LINE")
        self.kod(8, katman)
        self.kod(10, f"{x1:.4f}")
        self.kod(20, f"{y1:.4f}")
        self.kod(30, f"{z:.4f}")
        self.kod(11, f"{x2:.4f}")
        self.kod(21, f"{y2:.4f}")
        self.kod(31, f"{z:.4f}")
        self.sinir_guncelle(x1, y1, z)
        self.sinir_guncelle(x2, y2, z)

    def poli_cizgi(
        self,
        katman: str,
        noktalar: Sequence[Tuple[float, float]],
        z: float = 0.0,
        kapali: bool = False,
        uc_boyutlu: bool = False,
    ) -> None:
        if len(noktalar) < 2:
            return
        self.kod(0, "POLYLINE")
        self.kod(8, katman)
        self.kod(66, 1)
        self.kod(70, (1 if kapali else 0) | (8 if uc_boyutlu else 0))
        self.kod(10, "0.0")
        self.kod(20, "0.0")
        self.kod(30, f"{z:.4f}")
        for x, y in noktalar:
            self.kod(0, "VERTEX")
            self.kod(8, katman)
            self.kod(10, f"{x:.4f}")
            self.kod(20, f"{y:.4f}")
            self.kod(30, f"{z:.4f}")
            if uc_boyutlu:
                self.kod(70, 32)
            self.sinir_guncelle(x, y, z)
        self.kod(0, "SEQEND")
        self.kod(8, katman)

    def belge(self) -> str:
        if self.min_x == float("inf"):
            self.min_x = self.min_y = self.min_z = 0.0
            self.max_x = self.max_y = self.max_z = 0.0
        bas = _DxfYazici()
        bas.kod(0, "SECTION")
        bas.kod(2, "HEADER")
        bas.kod(9, "$ACADVER")
        bas.kod(1, "AC1009")
        bas.kod(9, "$INSBASE")
        bas.kod(10, "0.0")
        bas.kod(20, "0.0")
        bas.kod(30, "0.0")
        bas.kod(9, "$EXTMIN")
        bas.kod(10, f"{self.min_x:.4f}")
        bas.kod(20, f"{self.min_y:.4f}")
        bas.kod(30, f"{self.min_z:.4f}")
        bas.kod(9, "$EXTMAX")
        bas.kod(10, f"{self.max_x:.4f}")
        bas.kod(20, f"{self.max_y:.4f}")
        bas.kod(30, f"{self.max_z:.4f}")
        bas.kod(0, "ENDSEC")
        bas.kod(0, "SECTION")
        bas.kod(2, "TABLES")
        bas.kod(0, "TABLE")
        bas.kod(2, "LAYER")
        bas.kod(70, len(KATMANLAR))
        for ad, renk in KATMANLAR.items():
            bas.kod(0, "LAYER")
            bas.kod(2, ad)
            bas.kod(70, 0)
            bas.kod(62, renk)
            bas.kod(6, "CONTINUOUS")
        bas.kod(0, "ENDTAB")
        bas.kod(0, "ENDSEC")
        bas.kod(0, "SECTION")
        bas.kod(2, "ENTITIES")
        son = "0\nENDSEC\n0\nEOF\n"
        return "".join(bas.parcalar) + "".join(self.parcalar) + son


def dxf_yaz(
    yol: str,
    karelaj,
    kot_yazisi: bool = True,
    nokta_numarasi: bool = False,
    izgara_cizgileri: bool = True,
    sinir: bool = True,
    konturlar: Optional[Sequence] = None,
    yazi_yuksekligi: Optional[float] = None,
    ondalik_kot: int = 2,
) -> str:
    """Karelajı R12 DXF olarak yazar; yazılan dosyanın yolunu döndürür."""
    y = _DxfYazici()
    aralik = karelaj.ayar.aralik
    yukseklik = yazi_yuksekligi or max(0.5, aralik / 10.0)

    for nokta in karelaj.noktalar:
        kot = nokta.kot if nokta.kot is not None else 0.0
        y.nokta("KARELAJ_NOKTA", nokta.saga, nokta.yukari, kot)
        if kot_yazisi and nokta.kot is not None:
            y.yazi(
                "KARELAJ_KOT",
                nokta.saga + yukseklik * 0.3,
                nokta.yukari + yukseklik * 0.3,
                kot,
                f"{nokta.kot:.{ondalik_kot}f}",
                yukseklik,
            )
        if nokta_numarasi:
            y.yazi(
                "KARELAJ_NO",
                nokta.saga + yukseklik * 0.3,
                nokta.yukari - yukseklik * 1.3,
                kot,
                str(nokta.no),
                yukseklik * 0.8,
            )

    if izgara_cizgileri:
        _izgara_ciz(y, karelaj)

    if sinir and karelaj.izdusum_halkalari:
        for halka in karelaj.izdusum_halkalari:
            y.poli_cizgi("KARELAJ_SINIR", halka, z=0.0, kapali=True)

    for egri in konturlar or []:
        y.poli_cizgi(
            "KARELAJ_KONTUR",
            egri.noktalar,
            z=egri.kot,
            kapali=False,
            uc_boyutlu=True,
        )

    klasor = os.path.dirname(os.path.abspath(yol))
    if klasor:
        os.makedirs(klasor, exist_ok=True)
    with open(yol, "wb") as f:
        f.write(y.belge().encode("cp1254", errors="replace"))
    return yol


def _izgara_ciz(y: _DxfYazici, karelaj) -> None:
    """Komşu noktalar arasında karelaj çizgileri çizer."""
    matris = karelaj.matris
    for satir in matris:
        for j in range(len(satir) - 1):
            a, b = satir[j], satir[j + 1]
            if a and b:
                y.cizgi("KARELAJ_IZGARA", a.saga, a.yukari, b.saga, b.yukari)
    for i in range(len(matris) - 1):
        ust, alt = matris[i], matris[i + 1]
        for j in range(min(len(ust), len(alt))):
            a, b = ust[j], alt[j]
            if a and b:
                y.cizgi("KARELAJ_IZGARA", a.saga, a.yukari, b.saga, b.yukari)
