# -*- coding: utf-8 -*-
"""
Çevrimiçi kot kaynakları
========================

Üç servis desteklenir:

``opentopodata``
    https://api.opentopodata.org - açık, anahtarsız. SRTM 30 m, ASTER 30 m,
    EU-DEM 25 m, Mapzen, GEBCO gibi veri kümelerini sunar. Açık sunucunun
    kotası: istek başına 100 nokta, saniyede 1 istek, günde 1000 istek.
    Kurum içine kurulmuş kendi sunucunuz varsa ``--sunucu`` ile adresini
    verip bu sınırları kaldırabilirsiniz.

``open-elevation``
    https://open-elevation.com - açık, anahtarsız, kotasız ancak
    kararlılığı düşüktür ve yalnızca SRTM 30 m sunar.

``google``
    Google Maps Elevation API - Google Earth'ün kullandığı arazi verisinin
    aynısıdır. API anahtarı ve faturalandırma gerektirir.
    https://developers.google.com/maps/documentation/elevation

Tüm istemciler hız sınırlaması, üstel bekleyişli yeniden deneme ve
ayrıntılı Türkçe hata iletisi sağlar. Ağ erişimi ``urllib`` üzerinden
yapılır; sistemdeki ``HTTPS_PROXY`` ayarları kendiliğinden kullanılır.
"""

from __future__ import annotations

import json
import random
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Sequence, Tuple

from .temel import KaynakHatasi, KotKaynagi, Koordinat

__all__ = [
    "OpenTopoData",
    "OpenElevation",
    "GoogleElevation",
    "OPENTOPODATA_VERI_KUMELERI",
]

KULLANICI_ARACISI = "karelaj/1.0 (+kot karelaj araci)"

# OpenTopoData veri kümeleri: kimlik -> (açıklama, çözünürlük, düşey datum)
OPENTOPODATA_VERI_KUMELERI: Dict[str, Tuple[str, str, str]] = {
    "srtm30m": ("NASA SRTM (30 m)", "~30 m", "EGM96 jeoidi (ortometrik)"),
    "srtm90m": ("NASA SRTM (90 m)", "~90 m", "EGM96 jeoidi (ortometrik)"),
    "aster30m": ("ASTER GDEM v3 (30 m)", "~30 m", "EGM96 jeoidi (ortometrik)"),
    "eudem25m": ("EU-DEM v1.1 (25 m)", "~25 m", "EVRS2000 (Amsterdam sıfırı)"),
    "mapzen": ("Mapzen birleşik arazi verisi", "değişken", "EGM96 jeoidi (ortometrik)"),
    "etopo1": ("ETOPO1 küresel (1,8 km)", "~1,8 km", "deniz seviyesi"),
    "gebco2020": ("GEBCO 2020 (450 m, batimetri dahil)", "~450 m", "deniz seviyesi"),
    "ned10m": ("USGS NED (yalnızca ABD)", "~10 m", "NAVD88"),
}


# Yoğunluk uyarısı için yaklaşık yatay çözünürlükler (m)
_VERI_KUMESI_COZUNURLUK_M: Dict[str, float] = {
    "srtm30m": 30.0, "srtm90m": 90.0, "aster30m": 30.0, "eudem25m": 25.0,
    "mapzen": 30.0, "etopo1": 1800.0, "gebco2020": 450.0, "ned10m": 10.0,
}


# ---------------------------------------------------------------------------
# Ortak HTTP yardımcıları
# ---------------------------------------------------------------------------


class _HttpKaynak(KotKaynagi):
    """Hız sınırlama ve yeniden deneme içeren HTTP tabanlı kaynak temeli."""

    cevrimici = True

    def __init__(
        self,
        zaman_asimi: float = 30.0,
        yeniden_deneme: int = 4,
        istekler_arasi_sn: float = 0.0,
    ) -> None:
        self.zaman_asimi = zaman_asimi
        self.yeniden_deneme = max(0, yeniden_deneme)
        self.istekler_arasi_sn = max(0.0, istekler_arasi_sn)
        self._son_istek = 0.0

    def _bekle(self) -> None:
        if self.istekler_arasi_sn <= 0:
            return
        gecen = time.time() - self._son_istek
        kalan = self.istekler_arasi_sn - gecen
        if kalan > 0:
            time.sleep(kalan)

    def _istek(
        self,
        adres: str,
        govde: Optional[bytes] = None,
        basliklar: Optional[Dict[str, str]] = None,
    ) -> dict:
        son_hata: Optional[str] = None
        for deneme in range(self.yeniden_deneme + 1):
            self._bekle()
            istek = urllib.request.Request(adres, data=govde)
            istek.add_header("User-Agent", KULLANICI_ARACISI)
            istek.add_header("Accept", "application/json")
            if govde is not None:
                istek.add_header("Content-Type", "application/json")
            for anahtar, deger in (basliklar or {}).items():
                istek.add_header(anahtar, deger)
            try:
                with urllib.request.urlopen(istek, timeout=self.zaman_asimi) as yanit:
                    ham = yanit.read()
                self._son_istek = time.time()
                try:
                    return json.loads(ham.decode("utf-8"))
                except (ValueError, UnicodeDecodeError) as hata:
                    raise KaynakHatasi(
                        f"{self.ad}: yanıt JSON olarak çözümlenemedi ({hata})."
                    ) from hata
            except urllib.error.HTTPError as hata:
                self._son_istek = time.time()
                govde_metni = ""
                try:
                    govde_metni = hata.read().decode("utf-8", "replace")[:300]
                except Exception:  # pragma: no cover
                    pass
                son_hata = f"HTTP {hata.code} {hata.reason}" + (
                    f" - {govde_metni}" if govde_metni else ""
                )
                if hata.code in (429, 500, 502, 503, 504) and deneme < self.yeniden_deneme:
                    self._geri_cekil(deneme, hata)
                    continue
                raise KaynakHatasi(f"{self.ad}: {son_hata}") from hata
            except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as hata:
                self._son_istek = time.time()
                son_hata = str(getattr(hata, "reason", hata))
                if deneme < self.yeniden_deneme:
                    self._geri_cekil(deneme, None)
                    continue
                raise KaynakHatasi(
                    f"{self.ad}: sunucuya erişilemedi ({son_hata}). "
                    f"İnternet bağlantısını ve kurum vekil sunucu (proxy) "
                    f"ayarlarını denetleyin."
                ) from hata
        raise KaynakHatasi(f"{self.ad}: istek başarısız ({son_hata}).")

    def _geri_cekil(self, deneme: int, hata: Optional[urllib.error.HTTPError]) -> None:
        bekleme = min(60.0, (2.0 ** deneme)) + random.uniform(0.0, 0.5)
        if hata is not None:
            basliktaki = hata.headers.get("Retry-After") if hata.headers else None
            if basliktaki:
                try:
                    bekleme = max(bekleme, min(120.0, float(basliktaki)))
                except ValueError:
                    pass
        time.sleep(bekleme)


# ---------------------------------------------------------------------------
# OpenTopoData
# ---------------------------------------------------------------------------


class OpenTopoData(_HttpKaynak):
    """OpenTopoData yükseklik servisi istemcisi."""

    def __init__(
        self,
        veri_kumesi: str = "srtm30m",
        sunucu: str = "https://api.opentopodata.org",
        ara_deger: str = "cubic",
        toplu_boyut: int = 100,
        zaman_asimi: float = 30.0,
        yeniden_deneme: int = 4,
        istekler_arasi_sn: Optional[float] = None,
    ) -> None:
        acik_sunucu = "api.opentopodata.org" in sunucu
        super().__init__(
            zaman_asimi=zaman_asimi,
            yeniden_deneme=yeniden_deneme,
            istekler_arasi_sn=(
                istekler_arasi_sn
                if istekler_arasi_sn is not None
                else (1.05 if acik_sunucu else 0.0)
            ),
        )
        self.veri_kumesi = veri_kumesi
        self.sunucu = sunucu.rstrip("/")
        self.ara_deger = ara_deger
        self.toplu_boyut = min(toplu_boyut, 100 if acik_sunucu else toplu_boyut)
        bilgi = OPENTOPODATA_VERI_KUMELERI.get(veri_kumesi)
        self.cozunurluk_m = _VERI_KUMESI_COZUNURLUK_M.get(veri_kumesi)
        self.kimlik = f"opentopodata:{veri_kumesi}"
        self.ad = f"OpenTopoData / {bilgi[0] if bilgi else veri_kumesi}"
        self.cozunurluk = bilgi[1] if bilgi else "bilinmiyor"
        self.dusey_datum = bilgi[2] if bilgi else "bilinmiyor"

    def toplu_oku(self, koordinatlar: Sequence[Koordinat]) -> List[Optional[float]]:
        if not koordinatlar:
            return []
        konum = "|".join(f"{e:.7f},{b:.7f}" for e, b in koordinatlar)
        parametreler = urllib.parse.urlencode(
            {"locations": konum, "interpolation": self.ara_deger}
        )
        adres = f"{self.sunucu}/v1/{self.veri_kumesi}?{parametreler}"
        veri = self._istek(adres)
        durum = str(veri.get("status", "")).upper()
        if durum and durum != "OK":
            raise KaynakHatasi(
                f"{self.ad}: servis '{durum}' döndürdü"
                + (f" - {veri.get('error')}" if veri.get("error") else "")
            )
        sonuclar = veri.get("results")
        if not isinstance(sonuclar, list):
            raise KaynakHatasi(f"{self.ad}: yanıtta 'results' alanı yok.")
        return [_sayiya(s.get("elevation")) for s in sonuclar]


# ---------------------------------------------------------------------------
# Open-Elevation
# ---------------------------------------------------------------------------


class OpenElevation(_HttpKaynak):
    """Open-Elevation servisi istemcisi (POST ile toplu sorgu)."""

    def __init__(
        self,
        sunucu: str = "https://api.open-elevation.com",
        toplu_boyut: int = 200,
        zaman_asimi: float = 45.0,
        yeniden_deneme: int = 4,
        istekler_arasi_sn: float = 0.3,
    ) -> None:
        super().__init__(zaman_asimi, yeniden_deneme, istekler_arasi_sn)
        self.sunucu = sunucu.rstrip("/")
        self.toplu_boyut = toplu_boyut
        self.kimlik = "open-elevation:srtm30m"
        self.cozunurluk_m = 30.0
        self.ad = "Open-Elevation (SRTM 30 m)"
        self.cozunurluk = "~30 m"
        self.dusey_datum = "EGM96 jeoidi (ortometrik)"

    def toplu_oku(self, koordinatlar: Sequence[Koordinat]) -> List[Optional[float]]:
        if not koordinatlar:
            return []
        govde = json.dumps(
            {
                "locations": [
                    {"latitude": round(e, 7), "longitude": round(b, 7)}
                    for e, b in koordinatlar
                ]
            }
        ).encode("utf-8")
        veri = self._istek(f"{self.sunucu}/api/v1/lookup", govde=govde)
        sonuclar = veri.get("results")
        if not isinstance(sonuclar, list):
            raise KaynakHatasi(f"{self.ad}: yanıtta 'results' alanı yok.")
        return [_sayiya(s.get("elevation")) for s in sonuclar]


# ---------------------------------------------------------------------------
# Google Maps Elevation API
# ---------------------------------------------------------------------------

_GOOGLE_DURUM_ACIKLAMA = {
    "INVALID_REQUEST": "İstek biçimi geçersiz.",
    "OVER_DAILY_LIMIT": "Günlük kota doldu ya da faturalandırma etkin değil; "
    "API anahtarınızı ve Google Cloud faturalandırma ayarlarını denetleyin.",
    "OVER_QUERY_LIMIT": "Saniyelik istek sınırı aşıldı; --istek-araligi değerini artırın.",
    "REQUEST_DENIED": "İstek reddedildi; Elevation API etkin mi ve anahtar kısıtları "
    "uygun mu denetleyin.",
    "UNKNOWN_ERROR": "Sunucu kaynaklı geçici hata.",
    "DATA_NOT_AVAILABLE": "Bu konum için yükseklik verisi yok.",
}


class GoogleElevation(_HttpKaynak):
    """
    Google Maps Elevation API istemcisi.

    Google Earth'te görülen arazi yüzeyinin kaynağı budur. Kullanımı için
    Google Cloud'da Elevation API etkinleştirilmiş, faturalandırması açık
    bir API anahtarı gerekir.
    """

    def __init__(
        self,
        api_anahtari: str,
        toplu_boyut: int = 300,
        zaman_asimi: float = 30.0,
        yeniden_deneme: int = 4,
        istekler_arasi_sn: float = 0.05,
    ) -> None:
        super().__init__(zaman_asimi, yeniden_deneme, istekler_arasi_sn)
        if not api_anahtari:
            raise KaynakHatasi(
                "Google Elevation API için anahtar gerekir. --google-anahtar "
                "seçeneğini veya GOOGLE_ELEVATION_ANAHTARI ortam değişkenini kullanın."
            )
        self.api_anahtari = api_anahtari
        self.toplu_boyut = max(1, min(toplu_boyut, 480))
        self.kimlik = "google:elevation"
        self.cozunurluk_m = 30.0  # Türkiye'de büyük ölçüde SRTM tabanlı
        self.ad = "Google Maps Elevation API"
        self.cozunurluk = "değişken (Google Earth arazi verisi)"
        self.dusey_datum = "yerel ortalama deniz seviyesi (EGM96'ya yakın)"

    def toplu_oku(self, koordinatlar: Sequence[Koordinat]) -> List[Optional[float]]:
        if not koordinatlar:
            return []
        konum = "|".join(f"{e:.7f},{b:.7f}" for e, b in koordinatlar)
        parametreler = urllib.parse.urlencode(
            {"locations": konum, "key": self.api_anahtari}
        )
        adres = f"https://maps.googleapis.com/maps/api/elevation/json?{parametreler}"
        veri = self._istek(adres)
        durum = str(veri.get("status", "")).upper()
        if durum != "OK":
            aciklama = _GOOGLE_DURUM_ACIKLAMA.get(durum, "")
            ileti = veri.get("error_message") or ""
            raise KaynakHatasi(
                f"{self.ad}: '{durum}'. {aciklama} {ileti}".strip()
            )
        sonuclar = veri.get("results")
        if not isinstance(sonuclar, list):
            raise KaynakHatasi(f"{self.ad}: yanıtta 'results' alanı yok.")
        return [_sayiya(s.get("elevation")) for s in sonuclar]

    def gizli_bilgi_maskele(self, metin: str) -> str:
        return metin.replace(self.api_anahtari, "***")


def _sayiya(deger) -> Optional[float]:
    if deger is None:
        return None
    try:
        sayi = float(deger)
    except (TypeError, ValueError):
        return None
    if sayi != sayi:  # NaN
        return None
    # Servisler veri boşluğunu bazen çok büyük negatif değerle bildirir
    if sayi <= -11000.0 or sayi >= 9500.0:
        return None
    return sayi
