# -*- coding: utf-8 -*-
"""
Yerel sayısal yükseklik modeli (SYM/DEM) kot kaynağı
====================================================

Kurumun kendi hâlihazır harita / fotogrametrik SYM verisinden kot okur.
Tek bir dosya ya da karolardan oluşan bir klasör verilebilir; klasör
verildiğinde her nokta için kapsamına giren karo kendiliğinden seçilir.

Kurum verisi kullanmak, çevrimiçi küresel modellere göre iki büyük
üstünlük sağlar:

* **Doğruluk:** 30 m çözünürlüklü SRTM'nin düşey karesel ortalama hatası
  Türkiye arazisinde metre mertebesindeyken, 1/1000 hâlihazır haritadan
  üretilen SYM'de bu değer desimetre altına iner.
* **Düşey datum:** Kurum verisi zaten TUDKA-99 ortometrik kotlarındadır;
  jeoit dönüşümü gerekmez.
"""

from __future__ import annotations

import os
from typing import List, Optional, Sequence, Tuple

from ..geodezi import KoordinatSistemi, sistem_bul
from ..raster import Raster, RasterHatasi, raster_ac
from .temel import KaynakHatasi, KotKaynagi, Koordinat

__all__ = ["YerelSym", "SYM_UZANTILARI"]

SYM_UZANTILARI = (".tif", ".tiff", ".gtif", ".gtiff", ".asc", ".grd", ".agr", ".hgt")


class YerelSym(KotKaynagi):
    """Yerel SYM dosyası veya karo klasöründen kot okur."""

    cevrimici = False
    toplu_boyut = 4096

    def __init__(
        self,
        yol: str,
        sistem: Optional[KoordinatSistemi] = None,
        yontem: str = "bilineer",
        azami_acik_dosya: int = 8,
    ) -> None:
        self.yol = yol
        self.yontem = yontem
        self.azami_acik_dosya = max(1, azami_acik_dosya)
        self._acik: dict = {}
        self._sira: List[str] = []
        self.kimlik = f"yerel:{os.path.abspath(yol)}"
        self.dusey_datum = "dosyanın kendi düşey datumu (genellikle TUDKA-99 ortometrik)"

        self.dosyalar = self._dosyalari_bul(yol)
        if not self.dosyalar:
            raise KaynakHatasi(
                f"{yol}: desteklenen SYM dosyası bulunamadı "
                f"(aranan uzantılar: {', '.join(SYM_UZANTILARI)})."
            )

        self._sinirlar: List[Tuple[str, Tuple[float, float, float, float]]] = []
        epsg_kumesi = set()
        ilk_aciklama = ""
        for dosya in self.dosyalar:
            try:
                raster = self._ac(dosya)
            except RasterHatasi as hata:
                raise KaynakHatasi(str(hata)) from hata
            self._sinirlar.append((dosya, raster.bilgi.sinir))
            epsg_kumesi.add(raster.bilgi.epsg)
            if not ilk_aciklama:
                ilk_aciklama = raster.bilgi.aciklama
            self._cozunurluk_ornegi = raster.bilgi

        if len(epsg_kumesi) > 1:
            raise KaynakHatasi(
                f"{yol}: karoların koordinat sistemleri farklı "
                f"({sorted(str(e) for e in epsg_kumesi)}). Tek sistemde bir veri "
                f"kümesi verin veya --dem-sistemi ile sistemi sabitleyin."
            )

        dosya_epsg = next(iter(epsg_kumesi))
        self.sistem = sistem or self._sistemi_coz(dosya_epsg)
        b = self._cozunurluk_ornegi
        birim = "derece" if self.sistem.cografi else "m"
        self.cozunurluk = f"{abs(b.piksel_x):g} x {abs(b.piksel_y):g} {birim}"
        # Coğrafi rasterda dereceyi metreye yaklaşık çevir (orta enlemde)
        self.cozunurluk_m = (
            abs(b.piksel_x) * 111320.0 * 0.77 if self.sistem.cografi else abs(b.piksel_x)
        )
        self.ad = (
            f"Yerel SYM: {os.path.basename(os.path.abspath(yol))}"
            f" ({len(self.dosyalar)} dosya, {self.sistem.kod})"
        )

    # -- kurulum yardımcıları ----------------------------------------------

    @staticmethod
    def _dosyalari_bul(yol: str) -> List[str]:
        if os.path.isfile(yol):
            return [yol]
        if not os.path.isdir(yol):
            raise KaynakHatasi(f"SYM yolu bulunamadı: {yol}")
        bulunan: List[str] = []
        for kok, _klasorler, dosyalar in os.walk(yol):
            for ad in sorted(dosyalar):
                if ad.lower().endswith(SYM_UZANTILARI):
                    bulunan.append(os.path.join(kok, ad))
        return bulunan

    def _sistemi_coz(self, epsg: Optional[int]) -> KoordinatSistemi:
        if epsg is None:
            raise KaynakHatasi(
                f"{self.yol}: dosyada koordinat sistemi bilgisi yok. "
                f"--dem-sistemi ile sistemi belirtin (örn. ITRF96-TM30)."
            )
        try:
            return sistem_bul(f"EPSG:{epsg}")
        except ValueError as hata:
            raise KaynakHatasi(
                f"{self.yol}: dosyanın koordinat sistemi (EPSG:{epsg}) katalogda "
                f"tanımlı değil. --dem-sistemi ile eşdeğer sistemi belirtin."
            ) from hata

    def _ac(self, dosya: str) -> Raster:
        raster = self._acik.get(dosya)
        if raster is not None:
            self._sira.remove(dosya)
            self._sira.append(dosya)
            return raster
        raster = raster_ac(dosya)
        self._acik[dosya] = raster
        self._sira.append(dosya)
        while len(self._sira) > self.azami_acik_dosya:
            eski = self._sira.pop(0)
            self._acik.pop(eski).kapat()
        return raster

    # -- okuma --------------------------------------------------------------

    def toplu_oku(self, koordinatlar: Sequence[Koordinat]) -> List[Optional[float]]:
        sonuc: List[Optional[float]] = []
        for enlem, boylam in koordinatlar:
            x, y = self.sistem.wgs84ten(enlem, boylam)
            sonuc.append(self._nokta_oku(x, y))
        return sonuc

    def _nokta_oku(self, x: float, y: float) -> Optional[float]:
        for dosya, (min_x, min_y, max_x, max_y) in self._sinirlar:
            if min_x <= x <= max_x and min_y <= y <= max_y:
                try:
                    raster = self._ac(dosya)
                except RasterHatasi:
                    continue
                deger = raster.deger(x, y, self.yontem)
                if deger is not None:
                    return deger
        return None

    def kapsam_disi_sayisi(self, koordinatlar: Sequence[Koordinat]) -> int:
        """Kaç nokta SYM kapsamının tamamen dışında kalıyor?"""
        sayac = 0
        for enlem, boylam in koordinatlar:
            x, y = self.sistem.wgs84ten(enlem, boylam)
            if not any(
                min_x <= x <= max_x and min_y <= y <= max_y
                for _d, (min_x, min_y, max_x, max_y) in self._sinirlar
            ):
                sayac += 1
        return sayac

    def kapsam_ozeti(self) -> str:
        if not self._sinirlar:
            return "kapsam bilinmiyor"
        min_x = min(s[1][0] for s in self._sinirlar)
        min_y = min(s[1][1] for s in self._sinirlar)
        max_x = max(s[1][2] for s in self._sinirlar)
        max_y = max(s[1][3] for s in self._sinirlar)
        if self.sistem.cografi:
            return (
                f"boylam {min_x:.6f}..{max_x:.6f}, enlem {min_y:.6f}..{max_y:.6f}"
            )
        return f"sağa {min_x:.2f}..{max_x:.2f}, yukarı {min_y:.2f}..{max_y:.2f}"

    def kapat(self) -> None:
        for raster in self._acik.values():
            raster.kapat()
        self._acik.clear()
        self._sira.clear()
