# -*- coding: utf-8 -*-
"""
Kot önbelleği
=============

Çevrimiçi yükseklik servislerine yapılan sorgular SQLite tabanlı bir
önbellekte saklanır. Böylece:

* Aynı alan için karelaj aralığı değiştirilip yeniden çalıştırıldığında
  daha önce sorgulanmış noktalar tekrar indirilmez.
* Yarıda kesilen bir iş kaldığı yerden sürer.
* Günlük istek kotası olan servislerde (OpenTopoData 1000 istek/gün)
  kota boşa harcanmaz.

Yalnızca **başarıyla okunmuş** kotlar saklanır. Başarısız istekler ve
veri boşlukları önbelleğe yazılmaz; böylece geçici bir sorun (kota, hız
sınırı, ağ) o noktaları kalıcı olarak kotsuz bırakmaz.

Önbellek anahtarı; kaynak kimliği ile 1 cm çözünürlüğe yuvarlanmış
enlem/boylam çiftidir.
"""

from __future__ import annotations

import os
import sqlite3
import time
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

__all__ = ["KotOnbellegi", "varsayilan_onbellek_yolu"]

_YUVARLAMA = 7  # ondalık basamak (~1,1 cm)


def varsayilan_onbellek_yolu() -> str:
    temel = os.environ.get("KARELAJ_ONBELLEK_DIZINI")
    if not temel:
        temel = os.path.join(os.path.expanduser("~"), ".karelaj")
    return os.path.join(temel, "kot-onbellek.sqlite")


class KotOnbellegi:
    """SQLite tabanlı kot önbelleği. Kapatılması gerekir (veya ``with``)."""

    def __init__(self, yol: Optional[str] = None, etkin: bool = True) -> None:
        self.etkin = etkin
        self.yol = yol or varsayilan_onbellek_yolu()
        self._baglanti: Optional[sqlite3.Connection] = None
        self.okuma_isabeti = 0
        self.yazma_sayisi = 0
        if not etkin:
            return
        klasor = os.path.dirname(os.path.abspath(self.yol))
        try:
            if klasor:
                os.makedirs(klasor, exist_ok=True)
            self._baglanti = sqlite3.connect(self.yol)
            self._baglanti.execute("PRAGMA journal_mode=WAL")
            self._baglanti.execute("PRAGMA synchronous=NORMAL")
            self._baglanti.execute(
                """
                CREATE TABLE IF NOT EXISTS kotlar (
                    kaynak TEXT NOT NULL,
                    enlem  INTEGER NOT NULL,
                    boylam INTEGER NOT NULL,
                    kot    REAL,
                    zaman  INTEGER NOT NULL,
                    PRIMARY KEY (kaynak, enlem, boylam)
                )
                """
            )
            # Eski sürümler başarısız istekleri de "kot yok" olarak kaydediyordu
            # ve bu noktalar bir daha hiç sorulmuyordu. Böyle kayıtlar açılışta
            # silinir; böylece eski önbellekler kendiliğinden iyileşir.
            self._baglanti.execute("DELETE FROM kotlar WHERE kot IS NULL")
            self._baglanti.commit()
        except (sqlite3.Error, OSError) as hata:
            # Önbellek hiçbir zaman işi durdurmamalıdır.
            self._baglanti = None
            self.etkin = False
            self.hata = str(hata)

    # -- anahtar ------------------------------------------------------------

    @staticmethod
    def _anahtar(enlem: float, boylam: float) -> Tuple[int, int]:
        carpan = 10 ** _YUVARLAMA
        return (int(round(enlem * carpan)), int(round(boylam * carpan)))

    # -- okuma / yazma ------------------------------------------------------

    def topluca_al(
        self, kaynak: str, koordinatlar: Sequence[Tuple[float, float]]
    ) -> Dict[int, Optional[float]]:
        """
        Önbellekte bulunan değerleri ``{indis: kot}`` olarak döndürür.
        Bulunmayan indisler sözlükte yer almaz.
        """
        if not self.etkin or self._baglanti is None or not koordinatlar:
            return {}
        sonuc: Dict[int, Optional[float]] = {}
        anahtarlar = [self._anahtar(e, b) for e, b in koordinatlar]
        benzersiz = list({a for a in anahtarlar})
        bulunan: Dict[Tuple[int, int], Optional[float]] = {}
        try:
            for i in range(0, len(benzersiz), 400):
                dilim = benzersiz[i : i + 400]
                yer_tutucu = ",".join(["(?,?)"] * len(dilim))
                parametreler: List[object] = [kaynak]
                for e, b in dilim:
                    parametreler.extend([e, b])
                imlec = self._baglanti.execute(
                    f"SELECT enlem, boylam, kot FROM kotlar "
                    f"WHERE kaynak = ? AND kot IS NOT NULL "
                    f"AND (enlem, boylam) IN ({yer_tutucu})",
                    parametreler,
                )
                for e, b, kot in imlec.fetchall():
                    bulunan[(e, b)] = kot
        except sqlite3.Error:
            return {}
        for indis, anahtar in enumerate(anahtarlar):
            if anahtar in bulunan:
                sonuc[indis] = bulunan[anahtar]
        self.okuma_isabeti += len(sonuc)
        return sonuc

    def topluca_yaz(
        self,
        kaynak: str,
        kayitlar: Iterable[Tuple[float, float, Optional[float]]],
    ) -> None:
        if not self.etkin or self._baglanti is None:
            return
        simdi = int(time.time())
        satirlar = []
        for enlem, boylam, kot in kayitlar:
            if kot is None:
                continue  # başarısızlık ya da veri boşluğu önbelleklenmez
            e, b = self._anahtar(enlem, boylam)
            satirlar.append((kaynak, e, b, kot, simdi))
        if not satirlar:
            return
        try:
            self._baglanti.executemany(
                "INSERT OR REPLACE INTO kotlar (kaynak, enlem, boylam, kot, zaman) "
                "VALUES (?, ?, ?, ?, ?)",
                satirlar,
            )
            self._baglanti.commit()
            self.yazma_sayisi += len(satirlar)
        except sqlite3.Error:
            pass

    def temizle(self, kaynak: Optional[str] = None) -> int:
        if not self.etkin or self._baglanti is None:
            return 0
        try:
            if kaynak:
                imlec = self._baglanti.execute(
                    "DELETE FROM kotlar WHERE kaynak = ?", (kaynak,)
                )
            else:
                imlec = self._baglanti.execute("DELETE FROM kotlar")
            self._baglanti.commit()
            return imlec.rowcount or 0
        except sqlite3.Error:
            return 0

    def kayit_sayisi(self) -> int:
        if not self.etkin or self._baglanti is None:
            return 0
        try:
            return int(
                self._baglanti.execute("SELECT COUNT(*) FROM kotlar").fetchone()[0]
            )
        except sqlite3.Error:
            return 0

    def kapat(self) -> None:
        if self._baglanti is not None:
            try:
                self._baglanti.close()
            except sqlite3.Error:
                pass
            self._baglanti = None

    def __enter__(self) -> "KotOnbellegi":
        return self

    def __exit__(self, *_) -> None:
        self.kapat()
