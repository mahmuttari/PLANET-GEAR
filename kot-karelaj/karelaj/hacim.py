# -*- coding: utf-8 -*-
"""
Karelaj yöntemiyle hacim hesabı
===============================

Düzenli karelaj ağı, klasik kazı/dolgu hacim hesabının temelidir. Bu
modül iki yaklaşım sunar:

**Klasik karelaj (ortalama yükseklik) yöntemi**
    Her tam karenin dört köşesindeki kot farklarının ortalaması, karenin
    alanıyla çarpılır::

        V = a² · (h₁ + h₂ + h₃ + h₄) / 4

    Bütün kareler toplandığında bu, her köşe kotunun ait olduğu kare
    sayısıyla ağırlıklandırılmasına (1-2-3-4 katsayıları) denktir. Sonuç
    **net** hacimdir: kazı ve dolgu birbirini götürür.

**Alt bölmeli (prizmatik) yöntem**
    Karışık kareler (bir kısmı kazı, bir kısmı dolgu olan kareler) klasik
    yöntemde hatalı ayrıştırılır. Bu yöntem her kareyi ``alt_bolme``
    sayıda alt kareye böler, köşe kotlarından çift doğrusal (bilinear)
    ara değerle yükseklik üretir ve kazı ile dolguyu **ayrı ayrı**
    toplar. Proje keşif ve metraj çalışmalarında kullanılması gereken
    değerler bunlardır.

Karşılaştırma kolaylığı için her iki sonuç birlikte raporlanır.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from . import bicim

__all__ = ["HacimSonucu", "hacim_hesapla"]


@dataclass
class HacimSonucu:
    """Hacim hesabı sonucu (tüm hacimler m³, alanlar m²)."""

    referans_kot: float
    kazi_m3: float = 0.0
    dolgu_m3: float = 0.0
    net_m3: float = 0.0
    klasik_net_m3: float = 0.0
    kazi_alani_m2: float = 0.0
    dolgu_alani_m2: float = 0.0
    hesaplanan_kare: int = 0
    atlanan_kare: int = 0
    kare_alani_m2: float = 0.0
    alt_bolme: int = 8

    @property
    def toplam_alan_m2(self) -> float:
        return self.hesaplanan_kare * self.kare_alani_m2

    def ozet(self) -> List[str]:
        return [
            f"Referans (proje) kotu        : {bicim.sayi(self.referans_kot, 3)} m",
            f"Hesaba giren kare sayısı     : {bicim.tam_sayi(self.hesaplanan_kare)} "
            f"(köşesi eksik olduğu için atlanan: {bicim.tam_sayi(self.atlanan_kare)})",
            f"Bir karenin alanı            : {bicim.sayi(self.kare_alani_m2, 3)} m²",
            f"Hesaba giren toplam alan     : {bicim.alan_metni(self.toplam_alan_m2)}",
            f"Kazı (referans üstü) hacmi   : {bicim.hacim_metni(self.kazi_m3)}",
            f"Dolgu (referans altı) hacmi  : {bicim.hacim_metni(self.dolgu_m3)}",
            f"Net hacim (kazı - dolgu)     : {bicim.hacim_metni(self.net_m3)}",
            f"Klasik karelaj yöntemiyle net: {bicim.hacim_metni(self.klasik_net_m3)}",
            f"Kazı alanı                   : {bicim.sayi(self.kazi_alani_m2)} m²",
            f"Dolgu alanı                  : {bicim.sayi(self.dolgu_alani_m2)} m²",
        ]


def hacim_hesapla(
    karelaj,
    referans_kot: float,
    alt_bolme: int = 8,
) -> HacimSonucu:
    """
    Karelajdan referans kota göre kazı/dolgu hacmini hesaplar.

    ``referans_kot`` proje (plan) kotudur. Arazi kotu bunun üstündeyse
    kazı, altındaysa dolgu sayılır.
    """
    if alt_bolme < 1:
        raise ValueError("Alt bölme sayısı en az 1 olmalıdır.")

    aralik_x = karelaj.ayar.aralik
    aralik_y = karelaj.ayar.etkin_aralik_yukari()
    kare_alani = aralik_x * aralik_y
    sonuc = HacimSonucu(
        referans_kot=referans_kot, kare_alani_m2=kare_alani, alt_bolme=alt_bolme
    )

    alt_alan = kare_alani / (alt_bolme * alt_bolme)
    matris = karelaj.matris

    for i in range(len(matris) - 1):
        ust = matris[i]
        alt = matris[i + 1]
        for j in range(min(len(ust), len(alt)) - 1):
            su, sag_u, sa, sag_a = ust[j], ust[j + 1], alt[j], alt[j + 1]
            if not (su and sag_u and sa and sag_a):
                sonuc.atlanan_kare += 1
                continue
            kotlar = [su.kot, sag_u.kot, sa.kot, sag_a.kot]
            if any(k is None for k in kotlar):
                sonuc.atlanan_kare += 1
                continue
            sonuc.hesaplanan_kare += 1

            # Köşe fark yükseklikleri (sol üst, sağ üst, sol alt, sağ alt)
            h_su = su.kot - referans_kot
            h_sagu = sag_u.kot - referans_kot
            h_sa = sa.kot - referans_kot
            h_saga = sag_a.kot - referans_kot

            sonuc.klasik_net_m3 += kare_alani * (h_su + h_sagu + h_sa + h_saga) / 4.0

            for a in range(alt_bolme):
                v = (a + 0.5) / alt_bolme  # üstten alta doğru
                for b in range(alt_bolme):
                    u = (b + 0.5) / alt_bolme  # soldan sağa doğru
                    ust_ara = h_su * (1.0 - u) + h_sagu * u
                    alt_ara = h_sa * (1.0 - u) + h_saga * u
                    h = ust_ara * (1.0 - v) + alt_ara * v
                    if h > 0:
                        sonuc.kazi_m3 += h * alt_alan
                        sonuc.kazi_alani_m2 += alt_alan
                    elif h < 0:
                        sonuc.dolgu_m3 += -h * alt_alan
                        sonuc.dolgu_alani_m2 += alt_alan

    sonuc.net_m3 = sonuc.kazi_m3 - sonuc.dolgu_m3
    return sonuc
