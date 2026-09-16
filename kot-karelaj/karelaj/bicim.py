# -*- coding: utf-8 -*-
"""
Türkçe sayı biçimlendirme
=========================

Resmî yazışma ve teknik rapor metinlerinde sayılar Türkçe yazım
kurallarına göre gösterilir: binlik ayırıcı **nokta**, ondalık ayırıcı
**virgül** (örn. ``13.372.016,98``).

Bu kural yalnızca insanın okuyacağı metinler (rapor, ekran çıktısı) için
geçerlidir. NCN, XYZ ve DXF gibi makine tarafından okunan dosyalarda
ondalık ayırıcı daima **nokta** kalır; Netcad ve CAD yazılımları bunu
bekler.
"""

from __future__ import annotations

__all__ = ["sayi", "tam_sayi", "alan_metni", "hacim_metni"]


def sayi(deger: float, basamak: int = 2) -> str:
    """Sayıyı Türkçe biçimde döndürür (``13.372.016,98``)."""
    if deger is None:
        return "-"
    metin = f"{deger:,.{basamak}f}"
    # Önce geçici bir imle değiştirip ayırıcıları takas et
    return metin.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def tam_sayi(deger: int) -> str:
    """Tam sayıyı binlik ayırıcıyla döndürür (``56.865``)."""
    return f"{int(deger):,}".replace(",", ".")


def alan_metni(m2: float) -> str:
    """Alanı m² ve hektar olarak birlikte yazar."""
    return f"{sayi(m2)} m² ({sayi(m2 / 10000.0, 4)} ha)"


def hacim_metni(m3: float) -> str:
    return f"{sayi(m3)} m³"
