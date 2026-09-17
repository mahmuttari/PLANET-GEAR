# -*- coding: utf-8 -*-
"""
Kot kaynakları paketi
=====================

``kaynak_olustur`` ile komut satırı seçeneklerinden uygun kot kaynağı
üretilir.
"""

from __future__ import annotations

import os
from typing import Optional

from ..geodezi import KoordinatSistemi
from .temel import (
    IlerlemeGeriCagrisi,
    KaynakHatasi,
    KotKaynagi,
    OkumaOzeti,
    kotlari_doldur,
    yogunluk_uyarisi,
)
from .web import (
    OPENTOPODATA_VERI_KUMELERI,
    GoogleElevation,
    OpenElevation,
    OpenTopoData,
)
from .yerel import SYM_UZANTILARI, YerelSym

__all__ = [
    "KotKaynagi",
    "KaynakHatasi",
    "OkumaOzeti",
    "IlerlemeGeriCagrisi",
    "kotlari_doldur",
    "yogunluk_uyarisi",
    "kaynak_olustur",
    "OpenTopoData",
    "OpenElevation",
    "GoogleElevation",
    "YerelSym",
    "OPENTOPODATA_VERI_KUMELERI",
    "SYM_UZANTILARI",
    "KAYNAK_ADLARI",
]

KAYNAK_ADLARI = ("opentopodata", "open-elevation", "google", "yerel")


def kaynak_olustur(
    kaynak: str,
    veri_kumesi: str = "srtm30m",
    sunucu: Optional[str] = None,
    sym_yolu: Optional[str] = None,
    sym_sistemi: Optional[KoordinatSistemi] = None,
    ornekleme: str = "bilineer",
    google_anahtari: Optional[str] = None,
    toplu_boyut: Optional[int] = None,
    zaman_asimi: float = 30.0,
    yeniden_deneme: int = 4,
    istek_araligi: Optional[float] = None,
) -> KotKaynagi:
    """Kaynak adından uygun ``KotKaynagi`` nesnesini üretir."""
    ad = (kaynak or "").strip().lower()

    if ad in ("yerel", "sym", "dem", "dosya"):
        if not sym_yolu:
            raise KaynakHatasi(
                "Yerel SYM kaynağı için --sym ile dosya veya klasör yolu verilmelidir."
            )
        return YerelSym(sym_yolu, sistem=sym_sistemi, yontem=ornekleme)

    if ad in ("opentopodata", "otd"):
        if veri_kumesi not in OPENTOPODATA_VERI_KUMELERI and not sunucu:
            bilinen = ", ".join(sorted(OPENTOPODATA_VERI_KUMELERI))
            raise KaynakHatasi(
                f"Bilinmeyen OpenTopoData veri kümesi: {veri_kumesi!r}. "
                f"Seçenekler: {bilinen}"
            )
        ara_deger = {
            "en-yakin": "nearest",
            "bilineer": "bilinear",
            "bikubik": "cubic",
        }.get(ornekleme, "cubic")
        return OpenTopoData(
            veri_kumesi=veri_kumesi,
            sunucu=sunucu or "https://api.opentopodata.org",
            ara_deger=ara_deger,
            toplu_boyut=toplu_boyut or 100,
            zaman_asimi=zaman_asimi,
            yeniden_deneme=yeniden_deneme,
            istekler_arasi_sn=istek_araligi,
        )

    if ad in ("open-elevation", "openelevation"):
        return OpenElevation(
            sunucu=sunucu or "https://api.open-elevation.com",
            toplu_boyut=toplu_boyut or 200,
            zaman_asimi=max(zaman_asimi, 45.0),
            yeniden_deneme=yeniden_deneme,
            istekler_arasi_sn=istek_araligi if istek_araligi is not None else 0.3,
        )

    if ad in ("google", "google-elevation"):
        anahtar = google_anahtari or os.environ.get("GOOGLE_ELEVATION_ANAHTARI") or os.environ.get(
            "GOOGLE_ELEVATION_API_KEY"
        )
        return GoogleElevation(
            api_anahtari=anahtar or "",
            toplu_boyut=toplu_boyut or 300,
            zaman_asimi=zaman_asimi,
            yeniden_deneme=yeniden_deneme,
            istekler_arasi_sn=istek_araligi if istek_araligi is not None else 0.05,
        )

    raise KaynakHatasi(
        f"Bilinmeyen kot kaynağı: {kaynak!r}. "
        f"Seçenekler: {', '.join(KAYNAK_ADLARI)}"
    )
