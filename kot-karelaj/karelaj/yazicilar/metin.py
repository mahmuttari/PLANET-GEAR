# -*- coding: utf-8 -*-
"""
CSV ve XYZ çıktıları
====================

``csv_yaz``
    Excel ile doğrudan açılabilen nokta çizelgesi. Varsayılan ayarlar
    Türkçe Windows Excel'e göredir: alan ayırıcı noktalı virgül,
    ondalık ayırıcı virgül, kodlama cp1254. ``ingilizce=True`` ile
    uluslararası biçim (virgül ayırıcı, nokta ondalık, UTF-8) yazılır.

``xyz_yaz``
    Boşlukla ayrılmış ``Y X Z`` üçlüleri. Yüzey modelleme ve nokta bulutu
    araçlarının çoğu bu biçimi okur.
"""

from __future__ import annotations

import os
from typing import List, Optional, Sequence

__all__ = ["csv_yaz", "xyz_yaz"]

CSV_BASLIKLARI = [
    "NoktaNo",
    "Y_Saga",
    "X_Yukari",
    "Z_Kot",
    "Kod",
    "Enlem",
    "Boylam",
    "Satir",
    "Sutun",
    "Kaynak",
]


def _sayi(deger: Optional[float], basamak: int, ondalik: str) -> str:
    if deger is None:
        return ""
    metin = f"{deger:.{basamak}f}"
    return metin.replace(".", ondalik) if ondalik != "." else metin


def csv_yaz(
    yol: str,
    noktalar: Sequence,
    ingilizce: bool = False,
    ondalik_xy: int = 3,
    ondalik_z: int = 3,
) -> int:
    """Nokta çizelgesini CSV olarak yazar; yazılan satır sayısını döndürür."""
    if ingilizce:
        ayirac, ondalik, kodlama = ",", ".", "utf-8"
    else:
        ayirac, ondalik, kodlama = ";", ",", "cp1254"

    satirlar = [ayirac.join(CSV_BASLIKLARI)]
    for n in noktalar:
        satirlar.append(
            ayirac.join(
                [
                    str(n.no),
                    _sayi(n.saga, ondalik_xy, ondalik),
                    _sayi(n.yukari, ondalik_xy, ondalik),
                    _sayi(n.kot, ondalik_z, ondalik),
                    n.kod or "",
                    _sayi(n.enlem, 8, ondalik),
                    _sayi(n.boylam, 8, ondalik),
                    str(n.satir + 1) if n.satir >= 0 else "",
                    str(n.sutun + 1),
                    n.kaynak or "",
                ]
            )
        )
    _yaz(yol, "\r\n".join(satirlar) + "\r\n", kodlama)
    return len(satirlar) - 1


def xyz_yaz(
    yol: str,
    noktalar: Sequence,
    ondalik_xy: int = 3,
    ondalik_z: int = 3,
    kotsuz_atla: bool = True,
) -> int:
    """Y X Z üçlülerini boşlukla ayrılmış olarak yazar."""
    satirlar: List[str] = []
    for n in noktalar:
        if n.kot is None and kotsuz_atla:
            continue
        kot = 0.0 if n.kot is None else n.kot
        satirlar.append(
            f"{n.saga:.{ondalik_xy}f} {n.yukari:.{ondalik_xy}f} {kot:.{ondalik_z}f}"
        )
    _yaz(yol, "\n".join(satirlar) + ("\n" if satirlar else ""), "utf-8")
    return len(satirlar)


def _yaz(yol: str, icerik: str, kodlama: str) -> None:
    klasor = os.path.dirname(os.path.abspath(yol))
    if klasor:
        os.makedirs(klasor, exist_ok=True)
    with open(yol, "wb") as f:
        f.write(icerik.encode(kodlama, errors="replace"))
