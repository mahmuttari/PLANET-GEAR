# -*- coding: utf-8 -*-
"""
Saf Python raster (sayısal yükseklik modeli) okuyucu
====================================================

Harici kütüphane gerektirmeden yerel SYM/DEM dosyalarından kot okur.
Kurum ağlarında GDAL/rasterio kurulumu çoğu zaman mümkün olmadığından
okuyucu yalnızca Python standart kütüphanesini kullanır.

Desteklenen biçimler
--------------------

``.tif`` / ``.tiff``
    GeoTIFF. Şeritli (strip) ve karo (tile) düzenler; sıkıştırmasız,
    LZW, Deflate/ZIP ve PackBits sıkıştırmaları; 1 ve 2 numaralı
    (yatay fark) ve 3 numaralı (kayan nokta) öngörücüler; ``int16``,
    ``uint16``, ``int32``, ``uint32``, ``float32``, ``float64`` ve
    ``int8``/``uint8`` örnek türleri. BigTIFF de okunur.
``.asc`` / ``.grd``
    ESRI ASCII Grid.
``.hgt``
    SRTM ham yükseklik karosu (1201x1201 veya 3601x3601, big-endian
    int16). Dosya adı köşe koordinatını verir (``N40E029.hgt``).

Okuma tembeldir: yalnızca gereken şerit/karo çözülür ve çözülen bloklar
sınırlı bir önbellekte tutulur. Böylece birkaç GB'lık il genelindeki
SYM dosyalarından tek tek nokta okunabilir.
"""

from __future__ import annotations

import math
import os
import re
import struct
import zlib
from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

__all__ = ["Raster", "raster_ac", "RasterHatasi"]


class RasterHatasi(Exception):
    """Raster dosyası okunamadığında yükseltilir."""


# ---------------------------------------------------------------------------
# Ortak arayüz
# ---------------------------------------------------------------------------


@dataclass
class RasterBilgi:
    genislik: int
    yukseklik: int
    piksel_x: float
    piksel_y: float
    sol_ust_x: float
    sol_ust_y: float
    epsg: Optional[int] = None
    cografi: bool = True
    veri_yok: Optional[float] = None
    piksel_merkezli: bool = False
    aciklama: str = ""

    @property
    def sinir(self) -> Tuple[float, float, float, float]:
        """
        Verinin kapsadığı alan: ``(min_x, min_y, max_x, max_y)``.

        Piksel alanı (``PixelIsArea``) kayıtlı rasterlarda hücre kenarları,
        nokta (``PixelIsPoint``) kayıtlı rasterlarda ise ilk ve son piksel
        merkezleri sınırı belirler. SRTM karoları nokta kayıtlıdır; bu
        ayrım yapılmazsa karo sınırı yarım hücre kayar.
        """
        x0 = self.sol_ust_x
        y0 = self.sol_ust_y
        if self.piksel_merkezli:
            x1 = x0 + (self.genislik - 1) * self.piksel_x
            y1 = y0 - (self.yukseklik - 1) * abs(self.piksel_y)
        else:
            x1 = x0 + self.genislik * self.piksel_x
            y1 = y0 - self.yukseklik * abs(self.piksel_y)
        return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

    def icinde_mi(self, x: float, y: float, tolerans: float = 0.0) -> bool:
        """(x, y) raster kapsamı içinde mi?"""
        min_x, min_y, max_x, max_y = self.sinir
        return (
            min_x - tolerans <= x <= max_x + tolerans
            and min_y - tolerans <= y <= max_y + tolerans
        )


class Raster:
    """Raster dosyası için ortak okuma arayüzü."""

    bilgi: RasterBilgi
    yol: str

    def piksel_oku(self, sutun: int, satir: int) -> Optional[float]:
        raise NotImplementedError

    def kapat(self) -> None:
        pass

    def __enter__(self) -> "Raster":
        return self

    def __exit__(self, *_) -> None:
        self.kapat()

    # -- koordinat <-> piksel ----------------------------------------------

    def koordinattan_piksele(self, x: float, y: float) -> Tuple[float, float]:
        """Raster koordinatından kesirli piksel indisine (sütun, satır)."""
        b = self.bilgi
        kayma = 0.0 if b.piksel_merkezli else 0.5
        sutun = (x - b.sol_ust_x) / b.piksel_x - kayma
        satir = (b.sol_ust_y - y) / abs(b.piksel_y) - kayma
        return sutun, satir

    def deger(
        self, x: float, y: float, yontem: str = "bilineer"
    ) -> Optional[float]:
        """
        Raster koordinatında (x, y) yükseklik değeri.

        ``yontem``: ``"en-yakin"``, ``"bilineer"`` (varsayılan) veya
        ``"bikubik"``.
        """
        sutun, satir = self.koordinattan_piksele(x, y)
        if yontem == "en-yakin":
            return self.piksel_oku(int(round(sutun)), int(round(satir)))
        if yontem == "bilineer":
            return self._bilineer(sutun, satir)
        if yontem == "bikubik":
            return self._bikubik(sutun, satir)
        raise ValueError(
            f"Bilinmeyen örnekleme yöntemi: {yontem!r}. "
            f"'en-yakin', 'bilineer' veya 'bikubik' olmalıdır."
        )

    def _bilineer(self, sutun: float, satir: float) -> Optional[float]:
        s0 = math.floor(sutun)
        r0 = math.floor(satir)
        ds = sutun - s0
        dr = satir - r0
        d00 = self.piksel_oku(s0, r0)
        d10 = self.piksel_oku(s0 + 1, r0)
        d01 = self.piksel_oku(s0, r0 + 1)
        d11 = self.piksel_oku(s0 + 1, r0 + 1)
        degerler = [d00, d10, d01, d11]
        if any(d is None for d in degerler):
            # Kenarda veya veri boşluğunda: en yakın geçerli değere düş
            gecerli = [d for d in degerler if d is not None]
            if not gecerli:
                return None
            return self.piksel_oku(int(round(sutun)), int(round(satir))) or (
                sum(gecerli) / len(gecerli)
            )
        ust = d00 * (1 - ds) + d10 * ds
        alt = d01 * (1 - ds) + d11 * ds
        return ust * (1 - dr) + alt * dr

    def _bikubik(self, sutun: float, satir: float) -> Optional[float]:
        s0 = math.floor(sutun)
        r0 = math.floor(satir)
        ds = sutun - s0
        dr = satir - r0
        satirlar: List[float] = []
        for dy in range(-1, 3):
            noktalar: List[Optional[float]] = [
                self.piksel_oku(s0 + dx, r0 + dy) for dx in range(-1, 3)
            ]
            if any(p is None for p in noktalar):
                return self._bilineer(sutun, satir)
            satirlar.append(_kubik(noktalar, ds))  # type: ignore[arg-type]
        return _kubik(satirlar, dr)


def _kubik(p: Sequence[float], t: float) -> float:
    """Catmull-Rom kübik ara değer."""
    return p[1] + 0.5 * t * (
        p[2] - p[0]
        + t * (2.0 * p[0] - 5.0 * p[1] + 4.0 * p[2] - p[3]
               + t * (3.0 * (p[1] - p[2]) + p[3] - p[0]))
    )


def raster_ac(yol: str, epsg: Optional[int] = None) -> Raster:
    """Uzantıya göre uygun okuyucuyu açar."""
    if not os.path.exists(yol):
        raise RasterHatasi(f"SYM dosyası bulunamadı: {yol}")
    uzanti = os.path.splitext(yol)[1].lower()
    if uzanti in (".tif", ".tiff", ".gtif", ".gtiff"):
        return GeoTiffRaster(yol, epsg)
    if uzanti in (".asc", ".grd", ".agr"):
        return AsciiGridRaster(yol, epsg)
    if uzanti == ".hgt":
        return HgtRaster(yol)
    raise RasterHatasi(
        f"Desteklenmeyen SYM biçimi: {uzanti!r}. "
        f"GeoTIFF (.tif), ESRI ASCII Grid (.asc) veya SRTM (.hgt) kullanın."
    )


# ---------------------------------------------------------------------------
# GeoTIFF
# ---------------------------------------------------------------------------

# TIFF alan türü -> (struct kodu, bayt sayısı)
_TIFF_TURLERI: Dict[int, Tuple[str, int]] = {
    1: ("B", 1),    # BYTE
    2: ("c", 1),    # ASCII
    3: ("H", 2),    # SHORT
    4: ("I", 4),    # LONG
    5: ("II", 8),   # RATIONAL
    6: ("b", 1),    # SBYTE
    7: ("B", 1),    # UNDEFINED
    8: ("h", 2),    # SSHORT
    9: ("i", 4),    # SLONG
    10: ("ii", 8),  # SRATIONAL
    11: ("f", 4),   # FLOAT
    12: ("d", 8),   # DOUBLE
    16: ("Q", 8),   # LONG8 (BigTIFF)
    17: ("q", 8),   # SLONG8
    18: ("Q", 8),   # IFD8
}

ETIKET_GENISLIK = 256
ETIKET_YUKSEKLIK = 257
ETIKET_BIT_SAYISI = 258
ETIKET_SIKISTIRMA = 259
ETIKET_SERIT_KONUM = 273
ETIKET_ORNEK_SAYISI = 277
ETIKET_SATIR_SERIT = 278
ETIKET_SERIT_BOYUT = 279
ETIKET_PLANAR = 284
ETIKET_ONGORUCU = 317
ETIKET_KARO_GENISLIK = 322
ETIKET_KARO_YUKSEKLIK = 323
ETIKET_KARO_KONUM = 324
ETIKET_KARO_BOYUT = 325
ETIKET_ORNEK_BICIM = 339
ETIKET_PIKSEL_OLCEK = 33550
ETIKET_BAGLAMA = 33922
ETIKET_DONUSUM = 34264
ETIKET_GEOKEY = 34735
ETIKET_GEO_DOUBLE = 34736
ETIKET_GEO_ASCII = 34737
ETIKET_GDAL_VERIYOK = 42113


class GeoTiffRaster(Raster):
    """Tembel (lazy) GeoTIFF okuyucu."""

    def __init__(self, yol: str, epsg: Optional[int] = None, onbellek_blok: int = 24) -> None:
        self.yol = yol
        self._dosya = open(yol, "rb")
        self._onbellek: "OrderedDict[int, bytes]" = OrderedDict()
        self._onbellek_sinir = max(2, onbellek_blok)
        try:
            self._basligi_oku()
        except RasterHatasi:
            self._dosya.close()
            raise
        except Exception as hata:  # pragma: no cover - bozuk dosya
            self._dosya.close()
            raise RasterHatasi(f"{yol}: GeoTIFF çözümlenemedi ({hata}).") from hata
        if epsg is not None:
            self.bilgi.epsg = epsg
            self.bilgi.cografi = epsg in (4326, 4258, 4230, 4269)

    # -- başlık ------------------------------------------------------------

    def _basligi_oku(self) -> None:
        f = self._dosya
        f.seek(0)
        bayt_sirasi = f.read(2)
        if bayt_sirasi == b"II":
            self._e = "<"
        elif bayt_sirasi == b"MM":
            self._e = ">"
        else:
            raise RasterHatasi(f"{self.yol}: geçerli bir TIFF dosyası değil.")
        sihir = struct.unpack(self._e + "H", f.read(2))[0]
        if sihir == 42:
            self._buyuk = False
            ilk_ifd = struct.unpack(self._e + "I", f.read(4))[0]
        elif sihir == 43:
            self._buyuk = True
            adres_boyu = struct.unpack(self._e + "H", f.read(2))[0]
            f.read(2)
            if adres_boyu != 8:
                raise RasterHatasi(f"{self.yol}: desteklenmeyen BigTIFF adres boyu.")
            ilk_ifd = struct.unpack(self._e + "Q", f.read(8))[0]
        else:
            raise RasterHatasi(f"{self.yol}: bilinmeyen TIFF sürümü ({sihir}).")

        self._etiketler = self._ifd_oku(ilk_ifd)
        self._alanlari_coz()

    def _ifd_oku(self, konum: int) -> Dict[int, object]:
        f = self._dosya
        f.seek(konum)
        if self._buyuk:
            sayi = struct.unpack(self._e + "Q", f.read(8))[0]
            giris_boyu = 20
        else:
            sayi = struct.unpack(self._e + "H", f.read(2))[0]
            giris_boyu = 12
        ham = f.read(sayi * giris_boyu)
        etiketler: Dict[int, object] = {}
        for i in range(sayi):
            giris = ham[i * giris_boyu : (i + 1) * giris_boyu]
            if self._buyuk:
                etiket, tur, adet = struct.unpack(self._e + "HHQ", giris[:12])
                deger_ham = giris[12:20]
                deger_boyu = 8
            else:
                etiket, tur, adet = struct.unpack(self._e + "HHI", giris[:8])
                deger_ham = giris[8:12]
                deger_boyu = 4
            etiketler[etiket] = self._alan_degeri(tur, adet, deger_ham, deger_boyu)
        return etiketler

    def _alan_degeri(self, tur: int, adet: int, deger_ham: bytes, deger_boyu: int):
        if tur not in _TIFF_TURLERI:
            return None
        kod, boyut = _TIFF_TURLERI[tur]
        toplam = boyut * adet
        if toplam <= deger_boyu:
            ham = deger_ham[:toplam]
        else:
            if self._buyuk:
                konum = struct.unpack(self._e + "Q", deger_ham)[0]
            else:
                konum = struct.unpack(self._e + "I", deger_ham[:4])[0]
            simdiki = self._dosya.tell()
            self._dosya.seek(konum)
            ham = self._dosya.read(toplam)
            self._dosya.seek(simdiki)
        if tur == 2:
            return ham.split(b"\x00")[0].decode("latin-1")
        if tur in (5, 10):
            alt = "I" if tur == 5 else "i"
            sayilar = struct.unpack(self._e + alt * (2 * adet), ham)
            return [
                (sayilar[2 * i] / sayilar[2 * i + 1]) if sayilar[2 * i + 1] else 0.0
                for i in range(adet)
            ]
        degerler = list(struct.unpack(self._e + kod * adet, ham))
        return degerler[0] if adet == 1 else degerler

    @staticmethod
    def _liste(deger, varsayilan=None) -> List:
        if deger is None:
            return list(varsayilan) if varsayilan is not None else []
        if isinstance(deger, (list, tuple)):
            return list(deger)
        return [deger]

    def _alanlari_coz(self) -> None:
        e = self._etiketler
        genislik = e.get(ETIKET_GENISLIK)
        yukseklik = e.get(ETIKET_YUKSEKLIK)
        if not genislik or not yukseklik:
            raise RasterHatasi(f"{self.yol}: görüntü boyutu okunamadı.")
        self.genislik = int(genislik)
        self.yukseklik = int(yukseklik)
        self.ornek_sayisi = int(e.get(ETIKET_ORNEK_SAYISI) or 1)
        bit_listesi = self._liste(e.get(ETIKET_BIT_SAYISI), [8])
        self.bit_sayisi = int(bit_listesi[0])
        bicim_listesi = self._liste(e.get(ETIKET_ORNEK_BICIM), [1])
        self.ornek_bicim = int(bicim_listesi[0])
        self.sikistirma = int(e.get(ETIKET_SIKISTIRMA) or 1)
        self.ongorucu = int(e.get(ETIKET_ONGORUCU) or 1)
        planar = int(e.get(ETIKET_PLANAR) or 1)
        if planar != 1 and self.ornek_sayisi > 1:
            raise RasterHatasi(
                f"{self.yol}: ayrık düzlemli (planar) TIFF desteklenmiyor."
            )
        if self.bit_sayisi % 8 != 0:
            raise RasterHatasi(
                f"{self.yol}: {self.bit_sayisi} bitlik örnekler desteklenmiyor."
            )
        self.bayt_ornek = self.bit_sayisi // 8
        self._struct_kod = self._ornek_struct_kodu()

        self.karo_genislik = e.get(ETIKET_KARO_GENISLIK)
        if self.karo_genislik:
            self.karolu = True
            self.karo_genislik = int(self.karo_genislik)
            self.karo_yukseklik = int(e.get(ETIKET_KARO_YUKSEKLIK) or 0)
            self._blok_konumlari = [int(v) for v in self._liste(e.get(ETIKET_KARO_KONUM))]
            self._blok_boyutlari = [int(v) for v in self._liste(e.get(ETIKET_KARO_BOYUT))]
            if not self.karo_yukseklik:
                raise RasterHatasi(f"{self.yol}: karo yüksekliği okunamadı.")
            self.karo_sutun_sayisi = (self.genislik + self.karo_genislik - 1) // self.karo_genislik
        else:
            self.karolu = False
            self.satir_serit = int(e.get(ETIKET_SATIR_SERIT) or self.yukseklik)
            if self.satir_serit <= 0:
                self.satir_serit = self.yukseklik
            self._blok_konumlari = [int(v) for v in self._liste(e.get(ETIKET_SERIT_KONUM))]
            self._blok_boyutlari = [int(v) for v in self._liste(e.get(ETIKET_SERIT_BOYUT))]
        if not self._blok_konumlari:
            raise RasterHatasi(f"{self.yol}: veri blokları bulunamadı.")

        if self.sikistirma not in (1, 5, 8, 32946, 32773):
            raise RasterHatasi(
                f"{self.yol}: {self.sikistirma} numaralı sıkıştırma desteklenmiyor "
                f"(sıkıştırmasız, LZW, Deflate ve PackBits okunabilir)."
            )

        self.bilgi = self._cografi_bilgi()

    def _ornek_struct_kodu(self) -> str:
        bicim = self.ornek_bicim
        boyut = self.bayt_ornek
        if bicim == 3:
            if boyut == 4:
                return "f"
            if boyut == 8:
                return "d"
            raise RasterHatasi(f"{self.yol}: {boyut * 8} bitlik kayan nokta desteklenmiyor.")
        isaretli = bicim == 2
        harita = {1: "b", 2: "h", 4: "i", 8: "q"}
        if boyut not in harita:
            raise RasterHatasi(f"{self.yol}: {boyut * 8} bitlik tamsayı desteklenmiyor.")
        kod = harita[boyut]
        return kod if isaretli else kod.upper()

    def _cografi_bilgi(self) -> RasterBilgi:
        e = self._etiketler
        olcek = self._liste(e.get(ETIKET_PIKSEL_OLCEK))
        baglama = self._liste(e.get(ETIKET_BAGLAMA))
        donusum = self._liste(e.get(ETIKET_DONUSUM))

        if len(olcek) >= 2 and len(baglama) >= 6:
            piksel_x = float(olcek[0])
            piksel_y = float(olcek[1])
            i, j = float(baglama[0]), float(baglama[1])
            x, y = float(baglama[3]), float(baglama[4])
            sol_ust_x = x - i * piksel_x
            sol_ust_y = y + j * piksel_y
        elif len(donusum) >= 16:
            piksel_x = float(donusum[0])
            piksel_y = -float(donusum[5])
            sol_ust_x = float(donusum[3])
            sol_ust_y = float(donusum[7])
            if abs(float(donusum[1])) > 1e-12 or abs(float(donusum[4])) > 1e-12:
                raise RasterHatasi(
                    f"{self.yol}: döndürülmüş/eğik raster dönüşümü desteklenmiyor."
                )
        else:
            raise RasterHatasi(
                f"{self.yol}: coğrafi konumlandırma etiketleri (ModelPixelScale / "
                f"ModelTiepoint) bulunamadı. Dosya coğrafi referanslı değil."
            )

        epsg, piksel_merkezli, aciklama = self._geokey_coz()
        veri_yok = self._veri_yok_coz()
        cografi = bool(epsg in (4326, 4258, 4230, 4269)) if epsg else (
            abs(piksel_x) < 0.01
        )
        return RasterBilgi(
            genislik=self.genislik,
            yukseklik=self.yukseklik,
            piksel_x=piksel_x,
            piksel_y=piksel_y,
            sol_ust_x=sol_ust_x,
            sol_ust_y=sol_ust_y,
            epsg=epsg,
            cografi=cografi,
            veri_yok=veri_yok,
            piksel_merkezli=piksel_merkezli,
            aciklama=aciklama,
        )

    def _geokey_coz(self) -> Tuple[Optional[int], bool, str]:
        anahtarlar = self._liste(self._etiketler.get(ETIKET_GEOKEY))
        if len(anahtarlar) < 4:
            return None, False, ""
        sayi = int(anahtarlar[3])
        sozluk: Dict[int, int] = {}
        for i in range(sayi):
            temel = 4 + i * 4
            if temel + 3 >= len(anahtarlar):
                break
            anahtar = int(anahtarlar[temel])
            konum_etiketi = int(anahtarlar[temel + 1])
            deger = int(anahtarlar[temel + 3])
            if konum_etiketi == 0:
                sozluk[anahtar] = deger
        epsg = sozluk.get(3072) or sozluk.get(2048)
        if epsg in (0, 32767):
            epsg = None
        piksel_merkezli = sozluk.get(1025) == 2  # RasterPixelIsPoint
        aciklama = str(self._etiketler.get(ETIKET_GEO_ASCII) or "").strip("|").strip()
        return epsg, piksel_merkezli, aciklama

    def _veri_yok_coz(self) -> Optional[float]:
        ham = self._etiketler.get(ETIKET_GDAL_VERIYOK)
        if ham is None:
            return None
        try:
            return float(str(ham).strip())
        except (TypeError, ValueError):
            return None

    # -- veri erişimi ------------------------------------------------------

    def _blok_verisi(self, indis: int) -> bytes:
        if indis in self._onbellek:
            self._onbellek.move_to_end(indis)
            return self._onbellek[indis]
        if indis < 0 or indis >= len(self._blok_konumlari):
            raise IndexError(indis)
        konum = self._blok_konumlari[indis]
        boyut = self._blok_boyutlari[indis] if indis < len(self._blok_boyutlari) else 0
        self._dosya.seek(konum)
        ham = self._dosya.read(boyut)
        cozulmus = self._coz(ham)
        cozulmus = self._ongorucuyu_geri_al(cozulmus, indis)
        self._onbellek[indis] = cozulmus
        if len(self._onbellek) > self._onbellek_sinir:
            self._onbellek.popitem(last=False)
        return cozulmus

    def _coz(self, ham: bytes) -> bytes:
        if self.sikistirma == 1:
            return ham
        if self.sikistirma in (8, 32946):
            return zlib.decompress(ham)
        if self.sikistirma == 5:
            return _lzw_coz(ham)
        if self.sikistirma == 32773:
            return _packbits_coz(ham)
        raise RasterHatasi(f"Desteklenmeyen sıkıştırma: {self.sikistirma}")

    def _blok_genisligi(self, indis: int) -> int:
        if self.karolu:
            return self.karo_genislik
        return self.genislik

    def _blok_satir_sayisi(self, indis: int) -> int:
        if self.karolu:
            return self.karo_yukseklik
        baslangic = indis * self.satir_serit
        return max(0, min(self.satir_serit, self.yukseklik - baslangic))

    def _ongorucuyu_geri_al(self, veri: bytes, indis: int) -> bytes:
        if self.ongorucu == 1:
            return veri
        genislik = self._blok_genisligi(indis)
        satir_sayisi = self._blok_satir_sayisi(indis)
        adim = self.ornek_sayisi
        satir_bayt = genislik * adim * self.bayt_ornek
        if satir_bayt == 0:
            return veri
        tampon = bytearray(veri)
        if self.ongorucu == 2:
            kod = self._struct_kod
            maske = (1 << self.bit_sayisi) - 1
            for s in range(satir_sayisi):
                temel = s * satir_bayt
                if temel + satir_bayt > len(tampon):
                    break
                dilim = list(
                    struct.unpack(
                        self._e + kod * (genislik * adim),
                        bytes(tampon[temel : temel + satir_bayt]),
                    )
                )
                # Yatay fark öngörücüsü yalnızca tamsayı örneklerde geçerlidir;
                # toplama, örnek genişliğinde taşmalı (modüler) yapılır.
                for i in range(adim, genislik * adim):
                    dilim[i] = (dilim[i] + dilim[i - adim]) & maske
                # İşaretli türlerde ikiye tümleyen gösterimine geri dön
                if kod in "bhiq":
                    isaret = 1 << (self.bit_sayisi - 1)
                    dilim = [((v & maske) ^ isaret) - isaret for v in dilim]
                tampon[temel : temel + satir_bayt] = struct.pack(
                    self._e + kod * (genislik * adim), *dilim
                )
            return bytes(tampon)
        if self.ongorucu == 3:
            bayt_ornek = self.bayt_ornek
            for s in range(satir_sayisi):
                temel = s * satir_bayt
                if temel + satir_bayt > len(tampon):
                    break
                for i in range(temel + adim, temel + satir_bayt):
                    tampon[i] = (tampon[i] + tampon[i - adim]) & 0xFF
                ornek_sayisi = genislik * adim
                gecici = bytes(tampon[temel : temel + satir_bayt])
                duzen = bytearray(satir_bayt)
                for c in range(ornek_sayisi):
                    for b in range(bayt_ornek):
                        duzen[bayt_ornek * c + b] = gecici[b * ornek_sayisi + c]
                if self._e == "<":
                    # Kayan nokta öngörücüsü bayt düzlemlerini daima MSB-önce
                    # dizer; little-endian dosyada örnek başına ters çevrilir.
                    for c in range(ornek_sayisi):
                        parca = duzen[bayt_ornek * c : bayt_ornek * (c + 1)]
                        duzen[bayt_ornek * c : bayt_ornek * (c + 1)] = parca[::-1]
                tampon[temel : temel + satir_bayt] = duzen
            return bytes(tampon)
        raise RasterHatasi(f"{self.yol}: {self.ongorucu} numaralı öngörücü desteklenmiyor.")

    def piksel_oku(self, sutun: int, satir: int) -> Optional[float]:
        if sutun < 0 or satir < 0 or sutun >= self.genislik or satir >= self.yukseklik:
            return None
        if self.karolu:
            karo_s = sutun // self.karo_genislik
            karo_r = satir // self.karo_yukseklik
            indis = karo_r * self.karo_sutun_sayisi + karo_s
            ic_s = sutun % self.karo_genislik
            ic_r = satir % self.karo_yukseklik
            satir_bayt = self.karo_genislik * self.ornek_sayisi * self.bayt_ornek
        else:
            indis = satir // self.satir_serit
            ic_s = sutun
            ic_r = satir % self.satir_serit
            satir_bayt = self.genislik * self.ornek_sayisi * self.bayt_ornek
        try:
            veri = self._blok_verisi(indis)
        except (IndexError, zlib.error, struct.error) as hata:
            raise RasterHatasi(f"{self.yol}: veri bloğu okunamadı ({hata}).") from hata
        kayma = ic_r * satir_bayt + ic_s * self.ornek_sayisi * self.bayt_ornek
        if kayma + self.bayt_ornek > len(veri):
            return None
        # Öngörücü 3 çözülürken baytlar dosyanın kendi sırasına döndürülür,
        # bu yüzden burada ayrı bir bayt sırası gerekmez.
        deger = float(struct.unpack_from(self._e + self._struct_kod, veri, kayma)[0])
        if self.bilgi.veri_yok is not None and _yaklasik_esit(deger, self.bilgi.veri_yok):
            return None
        if deger != deger or deger in (float("inf"), float("-inf")):
            return None
        return deger

    def kapat(self) -> None:
        try:
            self._dosya.close()
        except Exception:  # pragma: no cover
            pass


def _yaklasik_esit(a: float, b: float) -> bool:
    return abs(a - b) <= max(1e-9, abs(b) * 1e-9)


# -- Sıkıştırma çözücüler ---------------------------------------------------


def _packbits_coz(ham: bytes) -> bytes:
    cikti = bytearray()
    i = 0
    n = len(ham)
    while i < n:
        deger = ham[i]
        i += 1
        if deger == 128:
            continue
        if deger < 128:
            adet = deger + 1
            cikti += ham[i : i + adet]
            i += adet
        else:
            adet = 257 - deger
            if i < n:
                cikti += bytes([ham[i]]) * adet
                i += 1
    return bytes(cikti)


def _lzw_coz(ham: bytes) -> bytes:
    """
    TIFF LZW çözücü (erken değişim / early change kuralıyla).

    Kod genişliği 9 bitte başlar; 511, 1023 ve 2047 numaralı kodlardan bir
    önce artar. 256 temizleme (Clear), 257 bitiş (EOI) kodudur.
    """
    TEMIZLE = 256
    BITIS = 257
    cikti = bytearray()
    sozluk: List[bytes] = [bytes([i]) for i in range(256)] + [b"", b""]
    kod_boyu = 9
    sonraki = 258
    onceki: Optional[bytes] = None
    bit_tamponu = 0
    bit_sayisi = 0
    for bayt in ham:
        bit_tamponu = (bit_tamponu << 8) | bayt
        bit_sayisi += 8
        while bit_sayisi >= kod_boyu:
            kod = (bit_tamponu >> (bit_sayisi - kod_boyu)) & ((1 << kod_boyu) - 1)
            bit_sayisi -= kod_boyu
            if kod == BITIS:
                return bytes(cikti)
            if kod == TEMIZLE:
                sozluk = [bytes([i]) for i in range(256)] + [b"", b""]
                kod_boyu = 9
                sonraki = 258
                onceki = None
                continue
            if kod < len(sozluk) and (kod < 256 or sozluk[kod]):
                giris = sozluk[kod]
            elif onceki is not None:
                giris = onceki + onceki[:1]
            else:
                raise RasterHatasi("LZW akışı bozuk: geçersiz kod.")
            cikti += giris
            if onceki is not None:
                sozluk.append(onceki + giris[:1])
                sonraki += 1
            onceki = giris
            # Erken değişim: bir sonraki kod eklenmeden genişlik artar
            if sonraki + 1 >= (1 << kod_boyu) and kod_boyu < 12:
                kod_boyu += 1
    return bytes(cikti)


# ---------------------------------------------------------------------------
# ESRI ASCII Grid
# ---------------------------------------------------------------------------


class AsciiGridRaster(Raster):
    """ESRI ASCII Grid (.asc) okuyucu. Dosya bellekte tutulur."""

    def __init__(self, yol: str, epsg: Optional[int] = None) -> None:
        self.yol = yol
        basliklar: Dict[str, float] = {}
        degerler: List[float] = []
        beklenen = {"ncols", "nrows", "cellsize"}
        with open(yol, "r", encoding="utf-8-sig", errors="replace") as f:
            for satir in f:
                s = satir.strip()
                if not s:
                    continue
                parcalar = s.split()
                anahtar = parcalar[0].lower()
                if anahtar in (
                    "ncols", "nrows", "xllcorner", "yllcorner",
                    "xllcenter", "yllcenter", "cellsize", "nodata_value", "dx", "dy",
                ) and len(parcalar) >= 2:
                    try:
                        basliklar[anahtar] = float(parcalar[1].replace(",", "."))
                        continue
                    except ValueError:
                        pass
                for p in parcalar:
                    try:
                        degerler.append(float(p.replace(",", ".")))
                    except ValueError:
                        continue
        eksik = beklenen - set(basliklar)
        if eksik:
            raise RasterHatasi(
                f"{yol}: ASCII Grid başlığında eksik alan(lar): {', '.join(sorted(eksik))}"
            )
        genislik = int(basliklar["ncols"])
        yukseklik = int(basliklar["nrows"])
        hucre = basliklar["cellsize"]
        hucre_y = basliklar.get("dy", hucre)
        if len(degerler) < genislik * yukseklik:
            raise RasterHatasi(
                f"{yol}: beklenen {genislik * yukseklik} değer yerine {len(degerler)} "
                f"değer bulundu."
            )
        self._veri = degerler[: genislik * yukseklik]
        merkezli = "xllcenter" in basliklar
        sol = basliklar.get("xllcorner", basliklar.get("xllcenter", 0.0))
        alt = basliklar.get("yllcorner", basliklar.get("yllcenter", 0.0))
        self.genislik = genislik
        self.yukseklik = yukseklik
        self.bilgi = RasterBilgi(
            genislik=genislik,
            yukseklik=yukseklik,
            piksel_x=hucre,
            piksel_y=hucre_y,
            sol_ust_x=sol,
            sol_ust_y=alt + yukseklik * hucre_y,
            epsg=epsg,
            cografi=(epsg in (4326, 4258, 4230)) if epsg else hucre < 0.01,
            veri_yok=basliklar.get("nodata_value"),
            piksel_merkezli=merkezli,
            aciklama="ESRI ASCII Grid",
        )

    def piksel_oku(self, sutun: int, satir: int) -> Optional[float]:
        if sutun < 0 or satir < 0 or sutun >= self.genislik or satir >= self.yukseklik:
            return None
        deger = self._veri[satir * self.genislik + sutun]
        if self.bilgi.veri_yok is not None and _yaklasik_esit(deger, self.bilgi.veri_yok):
            return None
        return deger


# ---------------------------------------------------------------------------
# SRTM .hgt
# ---------------------------------------------------------------------------

_HGT_ADI = re.compile(r"([NS])(\d{2})([EW])(\d{3})", re.IGNORECASE)


class HgtRaster(Raster):
    """SRTM ham yükseklik karosu (.hgt)."""

    def __init__(self, yol: str) -> None:
        self.yol = yol
        ad = os.path.basename(yol)
        eslesme = _HGT_ADI.search(ad)
        if not eslesme:
            raise RasterHatasi(
                f"{ad}: SRTM dosya adı köşe koordinatı içermiyor (örn. N40E029.hgt)."
            )
        enlem_isaret = 1 if eslesme.group(1).upper() == "N" else -1
        boylam_isaret = 1 if eslesme.group(3).upper() == "E" else -1
        alt_enlem = enlem_isaret * int(eslesme.group(2))
        sol_boylam = boylam_isaret * int(eslesme.group(4))

        boyut = os.path.getsize(yol)
        kenar = int(round(math.sqrt(boyut / 2.0)))
        if kenar * kenar * 2 != boyut or kenar not in (1201, 3601, 601, 7201):
            raise RasterHatasi(
                f"{ad}: beklenmeyen dosya boyutu ({boyut} bayt); "
                f"1201x1201 veya 3601x3601 bekleniyordu."
            )
        self._kenar = kenar
        self.genislik = kenar
        self.yukseklik = kenar
        with open(yol, "rb") as f:
            self._veri = f.read()
        adim = 1.0 / (kenar - 1)
        self.bilgi = RasterBilgi(
            genislik=kenar,
            yukseklik=kenar,
            piksel_x=adim,
            piksel_y=adim,
            sol_ust_x=float(sol_boylam),
            sol_ust_y=float(alt_enlem + 1),
            epsg=4326,
            cografi=True,
            veri_yok=-32768.0,
            piksel_merkezli=True,
            aciklama=f"SRTM {kenar}x{kenar} ({'1' if kenar == 3601 else '3'} yay saniyesi)",
        )

    def piksel_oku(self, sutun: int, satir: int) -> Optional[float]:
        if sutun < 0 or satir < 0 or sutun >= self._kenar or satir >= self._kenar:
            return None
        kayma = (satir * self._kenar + sutun) * 2
        deger = struct.unpack_from(">h", self._veri, kayma)[0]
        if deger == -32768:
            return None
        return float(deger)
