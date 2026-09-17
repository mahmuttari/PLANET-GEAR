# -*- coding: utf-8 -*-
"""
Kot kaynakları - ortak arayüz
=============================

Her kot kaynağı (çevrimiçi servis ya da yerel sayısal yükseklik modeli)
``KotKaynagi`` arayüzünü uygular. Okuma işini önbellek ve ilerleme
bildirimiyle birlikte ``kotlari_doldur`` yürütür.

Düşey datum uyarısı
-------------------

Kaynakların verdiği yükseklikler **ortometrik** (deniz seviyesinden)
kotlardır ancak dayandıkları jeoit modeli farklıdır (SRTM/ASTER için
EGM96, Copernicus için EGM2008, EU-DEM için EVRS2000). Türkiye Ulusal
Düşey Kontrol Ağı (TUDKA-99) kotlarıyla aralarında bölgesel olarak
onlarca santimetreye varan sistematik fark bulunur. Kesin proje
kotlarında bu fark, sahadaki nivelman noktalarından belirlenip
``--kot-kaydirma`` ile uygulanmalıdır.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

__all__ = [
    "KotKaynagi",
    "KaynakHatasi",
    "yogunluk_uyarisi",
    "OkumaOzeti",
    "kotlari_doldur",
    "IlerlemeGeriCagrisi",
]

Koordinat = Tuple[float, float]  # (enlem, boylam)
IlerlemeGeriCagrisi = Callable[[int, int, str], None]

# Bu kadar istek art arda başarısız olursa kaynağın geçici olarak
# erişilemez ya da kotasının dolmuş olduğu varsayılır ve okuma durdurulur.
ARDISIK_HATA_SINIRI = 3


class KaynakHatasi(Exception):
    """Kot kaynağı erişilemediğinde veya yanıt çözümlenemediğinde."""


def yogunluk_uyarisi(kaynak: "KotKaynagi", aralik_m: float, nokta_sayisi: int) -> Optional[str]:
    """
    Karelaj aralığı kaynağın çözünürlüğünden belirgin biçimde sıksa uyarır.

    30 m çözünürlüklü bir modelden 3 m aralıkla kot okumak yeni bilgi
    üretmez; aynı hücrenin ara değeri onlarca kez sorulur. Çevrimiçi
    kaynaklarda bu, istek sayısını ve kota tüketimini boşa katlar.
    """
    coz = kaynak.cozunurluk_m
    if not coz or aralik_m >= coz / 2.0:
        return None
    oran = coz / aralik_m
    istek = (nokta_sayisi + kaynak.toplu_boyut - 1) // kaynak.toplu_boyut
    ileti = (
        f"Karelaj aralığı ({aralik_m:g} m) kaynağın çözünürlüğünden ({coz:g} m) "
        f"yaklaşık {oran:.0f} kat daha sık. Bu, araziye dair yeni bilgi eklemez; "
        f"aynı verinin ara değerini tekrar tekrar okur."
    )
    if kaynak.cevrimici:
        ileti += (
            f" Bu iş için {istek} istek gerekiyor. Aralığı {coz / 2:g}-{coz:g} m "
            f"yapmak aynı doğrulukta sonucu çok daha az istekle verir; daha sık "
            f"karelaj gerekiyorsa kurumun kendi SYM verisini (--kaynak yerel) kullanın."
        )
    return ileti


class KotKaynagi:
    """Kot kaynağı arayüzü."""

    kimlik: str = "kaynak"
    ad: str = "Kot kaynağı"
    dusey_datum: str = "bilinmiyor"
    cozunurluk: str = "bilinmiyor"
    cozunurluk_m: Optional[float] = None
    """Kaynağın yaklaşık yatay çözünürlüğü (m); yoğunluk uyarısı için."""
    toplu_boyut: int = 100
    cevrimici: bool = False

    def toplu_oku(self, koordinatlar: Sequence[Koordinat]) -> List[Optional[float]]:
        """(enlem, boylam) listesi için kot listesi döndürür."""
        raise NotImplementedError

    def kapat(self) -> None:
        pass

    def __enter__(self) -> "KotKaynagi":
        return self

    def __exit__(self, *_) -> None:
        self.kapat()

    def tanim(self) -> str:
        return f"{self.ad} (düşey datum: {self.dusey_datum}, çözünürlük: {self.cozunurluk})"


@dataclass
class OkumaOzeti:
    """Kot okuma işinin sonucu."""

    toplam: int = 0
    okunan: int = 0
    onbellekten: int = 0
    eksik: int = 0
    istek_sayisi: int = 0
    sure_sn: float = 0.0
    kaynak_tanimi: str = ""
    uyarilar: List[str] = field(default_factory=list)

    def ozet_satiri(self) -> str:
        from .. import bicim

        return (
            f"{bicim.tam_sayi(self.okunan)}/{bicim.tam_sayi(self.toplam)} nokta okundu "
            f"({bicim.tam_sayi(self.onbellekten)} önbellekten, "
            f"{bicim.tam_sayi(self.istek_sayisi)} istek, {bicim.sayi(self.sure_sn, 1)} sn)"
            + (f", {bicim.tam_sayi(self.eksik)} nokta kotsuz" if self.eksik else "")
        )


def kotlari_doldur(
    noktalar: Sequence,
    kaynak: KotKaynagi,
    onbellek=None,
    ilerleme: Optional[IlerlemeGeriCagrisi] = None,
    kot_kaydirma: float = 0.0,
    eksikte_dur: bool = False,
) -> OkumaOzeti:
    """
    ``noktalar`` listesindeki her ``Nokta`` nesnesinin ``kot`` alanını
    doldurur.

    Önce önbellek sorgulanır, kalanlar kaynaktan toplu isteklerle okunur
    ve sonuçlar önbelleğe yazılır. ``kot_kaydirma`` okunan her kota
    eklenir (yerel düşey datum farkını gidermek için).
    """
    baslangic = time.time()
    ozet = OkumaOzeti(toplam=len(noktalar), kaynak_tanimi=kaynak.tanim())
    if not noktalar:
        return ozet

    koordinatlar: List[Koordinat] = [(n.enlem, n.boylam) for n in noktalar]

    onbellek_sonucu: Dict[int, Optional[float]] = {}
    if onbellek is not None and getattr(onbellek, "etkin", False) and kaynak.cevrimici:
        onbellek_sonucu = onbellek.topluca_al(kaynak.kimlik, koordinatlar)

    # Önbellekte değeri olmayan (None) kayıtlar "bilinmiyor" sayılır ve
    # yeniden sorulur. Aksi hâlde bir kez başarısız olan istek, o noktaları
    # sonsuza dek kotsuz bırakır.
    onbellek_sonucu = {i: k for i, k in onbellek_sonucu.items() if k is not None}

    kalan_indisler = [i for i in range(len(noktalar)) if i not in onbellek_sonucu]
    for indis, kot in onbellek_sonucu.items():
        noktalar[indis].kot = kot + kot_kaydirma
        noktalar[indis].kaynak = f"{kaynak.kimlik} (önbellek)"
    ozet.onbellekten = len(onbellek_sonucu)

    tamamlanan = ozet.onbellekten
    if ilerleme:
        ilerleme(tamamlanan, ozet.toplam, "önbellek tarandı")

    toplu = max(1, kaynak.toplu_boyut)
    yeni_kayitlar: List[Tuple[float, float, float]] = []
    ardisik_hata = 0
    son_hata = ""
    dilimler = [
        kalan_indisler[i : i + toplu] for i in range(0, len(kalan_indisler), toplu)
    ]

    for dilim_no, dilim in enumerate(dilimler):
        istek_koordinatlari = [koordinatlar[j] for j in dilim]
        try:
            kotlar = kaynak.toplu_oku(istek_koordinatlari)
            ardisik_hata = 0
        except KaynakHatasi as hata:
            if eksikte_dur:
                raise
            ardisik_hata += 1
            son_hata = str(hata)
            ozet.istek_sayisi += 1
            if ardisik_hata == 1:
                ozet.uyarilar.append(f"{len(dilim)} nokta okunamadı: {hata}")
            if ardisik_hata >= ARDISIK_HATA_SINIRI:
                # Kota dolmuş ya da servis erişilemez durumda: kalan her
                # dilim için yeniden deneyip saatlerce beklemek yerine durulur.
                kalan = sum(len(d) for d in dilimler[dilim_no + 1 :])
                ozet.uyarilar.append(
                    f"Art arda {ardisik_hata} istek başarısız oldu, okuma durduruldu. "
                    f"Kalan {kalan + len(dilim) - len(dilim)} nokta bu çalıştırmada "
                    f"kotsuz bırakıldı; sorun giderilince yeniden çalıştırıldığında "
                    f"yalnızca bu noktalar sorulur. Son hata: {son_hata}"
                )
                break
            continue
        ozet.istek_sayisi += 1
        if len(kotlar) != len(dilim):
            ozet.uyarilar.append(
                f"Kaynak {len(dilim)} nokta için {len(kotlar)} değer döndürdü; "
                f"eksik değerler boş bırakıldı."
            )
            kotlar = list(kotlar) + [None] * (len(dilim) - len(kotlar))
        for yerel_indis, genel_indis in enumerate(dilim):
            kot = kotlar[yerel_indis]
            if kot is None:
                # Kaynak bu nokta için değer vermedi; önbelleğe YAZILMAZ ki
                # bir sonraki çalıştırmada yeniden sorulabilsin.
                continue
            enlem, boylam = koordinatlar[genel_indis]
            yeni_kayitlar.append((enlem, boylam, kot))
            noktalar[genel_indis].kot = kot + kot_kaydirma
            noktalar[genel_indis].kaynak = kaynak.kimlik
        tamamlanan += len(dilim)
        if ilerleme:
            ilerleme(tamamlanan, ozet.toplam, kaynak.kimlik)

    if onbellek is not None and getattr(onbellek, "etkin", False) and kaynak.cevrimici:
        onbellek.topluca_yaz(kaynak.kimlik, yeni_kayitlar)

    ozet.okunan = sum(1 for n in noktalar if n.kot is not None)
    ozet.eksik = ozet.toplam - ozet.okunan
    ozet.sure_sn = time.time() - baslangic
    if ozet.eksik and kaynak.cevrimici and ozet.eksik >= max(50, ozet.toplam // 20):
        ozet.uyarilar.append(
            f"{ozet.eksik} nokta kotsuz kaldı. Çevrimiçi kaynaklarda bunun en sık "
            f"nedenleri günlük istek kotasının dolması, hız sınırı ve ağ kesintisidir. "
            f"Başarısız noktalar önbelleğe yazılmaz; sorun giderilince aynı komut "
            f"yeniden çalıştırıldığında yalnızca eksik noktalar sorulur."
        )
    return ozet
