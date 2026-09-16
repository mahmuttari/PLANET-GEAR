# -*- coding: utf-8 -*-
"""
Eş yükselti eğrileri (kontur)
=============================

Karelaj matrisinden "yürüyen kareler" (marching squares) yöntemiyle eş
yükselti eğrileri üretir. Üretilen eğriler DXF ve KML çıktılarında
kullanılabilir; böylece karelaj noktalarının yanında araziyi okunur kılan
bir yüzey gösterimi de elde edilir.

Yöntem, her kare hücrenin dört köşesindeki kotları eşik değeriyle
karşılaştırır, kenarlar üzerinde doğrusal ara değerle kesişim noktalarını
bulur ve bu parçaları uç uca ekleyerek sürekli eğriler oluşturur. Köşesi
eksik (kot okunamamış veya alan dışında kalmış) hücreler atlanır.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

__all__ = ["KonturEgrisi", "kontur_uret", "kontur_kotlari"]

Nokta2B = Tuple[float, float]


@dataclass
class KonturEgrisi:
    """Tek bir eş yükselti eğrisi parçası."""

    kot: float
    noktalar: List[Nokta2B]
    kapali: bool = False

    @property
    def uzunluk(self) -> float:
        toplam = 0.0
        for i in range(len(self.noktalar) - 1):
            (x1, y1), (x2, y2) = self.noktalar[i], self.noktalar[i + 1]
            toplam += math.hypot(x2 - x1, y2 - y1)
        return toplam


def kontur_kotlari(
    en_dusuk: float, en_yuksek: float, aralik: float, temel: float = 0.0
) -> List[float]:
    """Verilen kot aralığını kapsayan eş yükselti değerlerini üretir."""
    if aralik <= 0:
        raise ValueError("Eş yükselti aralığı sıfırdan büyük olmalıdır.")
    ilk = math.ceil((en_dusuk - temel) / aralik) * aralik + temel
    kotlar: List[float] = []
    deger = ilk
    while deger <= en_yuksek + 1e-9:
        kotlar.append(round(deger, 6))
        deger += aralik
    return kotlar


def kontur_uret(
    karelaj,
    aralik: float = 1.0,
    temel: float = 0.0,
    en_az_nokta: int = 2,
) -> List[KonturEgrisi]:
    """
    Karelajdan eş yükselti eğrilerini üretir.

    ``aralik`` eş yükselti aralığı (m), ``temel`` ise eğrilerin
    hizalanacağı taban kottur (örn. 0 m).
    """
    istatistik = karelaj.kot_istatistikleri()
    if not istatistik:
        return []
    kotlar = kontur_kotlari(istatistik["en_dusuk"], istatistik["en_yuksek"], aralik, temel)
    egriler: List[KonturEgrisi] = []
    for kot in kotlar:
        egriler.extend(_tek_kot(karelaj, kot, en_az_nokta))
    return egriler


def _tek_kot(karelaj, kot: float, en_az_nokta: int) -> List[KonturEgrisi]:
    parcalar = _parcalari_bul(karelaj, kot)
    return [
        e for e in _parcalari_birlestir(parcalar, kot) if len(e.noktalar) >= en_az_nokta
    ]


def _parcalari_bul(karelaj, kot: float) -> List[Tuple[Nokta2B, Nokta2B]]:
    parcalar: List[Tuple[Nokta2B, Nokta2B]] = []
    matris = karelaj.matris
    for i in range(len(matris) - 1):
        ust = matris[i]
        alt = matris[i + 1]
        for j in range(min(len(ust), len(alt)) - 1):
            # Hücre köşeleri: sol üst, sağ üst, sağ alt, sol alt
            su, sag_u = ust[j], ust[j + 1]
            sa, sag_a = alt[j], alt[j + 1]
            if not (su and sag_u and sa and sag_a):
                continue
            if any(k.kot is None for k in (su, sag_u, sa, sag_a)):
                continue
            koseler = [
                ((su.saga, su.yukari), su.kot),
                ((sag_u.saga, sag_u.yukari), sag_u.kot),
                ((sag_a.saga, sag_a.yukari), sag_a.kot),
                ((sa.saga, sa.yukari), sa.kot),
            ]
            parcalar.extend(_hucre_parcalari(koseler, kot))
    return parcalar


def _hucre_parcalari(
    koseler: Sequence[Tuple[Nokta2B, float]], kot: float
) -> List[Tuple[Nokta2B, Nokta2B]]:
    """Bir hücredeki eş yükselti parçalarını (0, 1 veya 2 adet) döndürür."""
    kesisimler: List[Nokta2B] = []
    n = len(koseler)
    for i in range(n):
        (p1, k1) = koseler[i]
        (p2, k2) = koseler[(i + 1) % n]
        if (k1 < kot) == (k2 < kot):
            continue
        if k2 == k1:
            continue
        t = (kot - k1) / (k2 - k1)
        kesisimler.append((p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1])))
    if len(kesisimler) == 2:
        return [(kesisimler[0], kesisimler[1])]
    if len(kesisimler) == 4:
        # Eyer (saddle) durumu: hücre ortalamasına göre bağlantı seçilir
        ortalama = sum(k for _p, k in koseler) / 4.0
        if ortalama >= kot:
            return [(kesisimler[0], kesisimler[1]), (kesisimler[2], kesisimler[3])]
        return [(kesisimler[1], kesisimler[2]), (kesisimler[3], kesisimler[0])]
    return []


def _anahtar(nokta: Nokta2B) -> Tuple[int, int]:
    return (int(round(nokta[0] * 1000.0)), int(round(nokta[1] * 1000.0)))


def _parcalari_birlestir(
    parcalar: Sequence[Tuple[Nokta2B, Nokta2B]], kot: float
) -> List[KonturEgrisi]:
    """Kopuk parçaları uç uca ekleyerek sürekli eğriler oluşturur."""
    komsuluk: Dict[Tuple[int, int], List[int]] = {}
    for indis, (a, b) in enumerate(parcalar):
        komsuluk.setdefault(_anahtar(a), []).append(indis)
        komsuluk.setdefault(_anahtar(b), []).append(indis)

    kullanildi = [False] * len(parcalar)
    egriler: List[KonturEgrisi] = []

    def diger_uc(indis: int, uc: Nokta2B) -> Nokta2B:
        a, b = parcalar[indis]
        return b if _anahtar(a) == _anahtar(uc) else a

    def zinciri_uzat(bas: Nokta2B, ilk_indis: int) -> List[Nokta2B]:
        zincir = [bas]
        simdiki_uc = bas
        simdiki_indis = ilk_indis
        while True:
            kullanildi[simdiki_indis] = True
            simdiki_uc = diger_uc(simdiki_indis, simdiki_uc)
            zincir.append(simdiki_uc)
            adaylar = [
                i
                for i in komsuluk.get(_anahtar(simdiki_uc), [])
                if not kullanildi[i]
            ]
            if not adaylar:
                return zincir
            simdiki_indis = adaylar[0]

    for indis in range(len(parcalar)):
        if kullanildi[indis]:
            continue
        a, b = parcalar[indis]
        ileri = zinciri_uzat(a, indis)
        # Diğer yönde de uzat (açık eğrilerin baş tarafı)
        geri: List[Nokta2B] = []
        adaylar = [i for i in komsuluk.get(_anahtar(a), []) if not kullanildi[i]]
        if adaylar:
            geri = zinciri_uzat(a, adaylar[0])
        noktalar = list(reversed(geri[1:])) + ileri if geri else ileri
        kapali = len(noktalar) > 2 and _anahtar(noktalar[0]) == _anahtar(noktalar[-1])
        egriler.append(KonturEgrisi(kot=kot, noktalar=noktalar, kapali=kapali))
    return egriler
