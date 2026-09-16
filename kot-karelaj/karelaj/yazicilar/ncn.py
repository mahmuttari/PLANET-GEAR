# -*- coding: utf-8 -*-
"""
Netcad NCN nokta dosyası yazıcısı
=================================

Netcad'in nokta dosyası (``.ncn``), her satırı bir nokta olan düz metin
bir dosyadır. Netcad'in **Nokta > Dosyadan Nokta Oku** penceresi sütun
düzenini kullanıcıya seçtirdiği için, yaygın kullanılan tek bir düzen
yerine bu yazıcı düzeni ayarlanabilir kılar.

Varsayılan düzen, Netcad'in kendi yazdığı nokta dosyalarıyla aynıdır::

    NoktaNo  Y(sağa)  X(yukarı)  Z(kot)  KodNo  "Kod"  ""  ""
    1/4 429903.20 4064858.18 636.44 0 "YPA1" "" ""

Alanlar tek boşlukla ayrılır, koordinatlar ve kot iki ondalık basamakla
yazılır, metin alanları çift tırnak içine alınır. ``KodNo`` alanı Netcad'in
sayısal kod alanıdır ve varsayılan olarak ``0`` yazılır. Sondaki iki boş
tırnaklı alan Netcad'in ayırdığı ek açıklama alanlarıdır.

Virgülle ayrılmış eski düzen ``netcad-virgul`` profiliyle üretilir::

    1,494200.000,4513900.000,181.399,KARELAJ

Burada **Y sağa değer (easting)**, **X yukarı değer (northing)** anlamına
gelir; bu, ülkemizdeki ölçme geleneğine ve EPSG'nin Türkiye TM sistemleri
için tanımladığı eksen adlandırmasına uygundur.

Netcad'iniz farklı bir düzen bekliyorsa ``--ncn-sutun`` ile sütun sırası,
``--ncn-ayirac`` ile ayırıcı serbestçe değiştirilebilir.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

__all__ = ["NcnAyari", "NCN_PROFILLERI", "ncn_yaz", "ncn_satirlari"]

# Kullanılabilir sütun anahtarları ve başlık adları
SUTUN_BASLIKLARI: Dict[str, str] = {
    "no": "NoktaNo",
    "y": "Y(Saga)",
    "x": "X(Yukari)",
    "z": "Z(Kot)",
    "kod": "Kod",
    "enlem": "Enlem",
    "boylam": "Boylam",
    "satir": "Satir",
    "sutun": "Sutun",
    "aciklama": "Aciklama",
    "kodno": "KodNo",
    "bos": "Bos",
}

# Tırnak kullanıldığında tırnağa alınacak (metin) sütunlar
TIRNAKLANACAK = ("kod", "aciklama", "bos")

AYIRACLAR: Dict[str, str] = {
    "virgul": ",",
    "bosluk": " ",
    "sekme": "\t",
    "noktali-virgul": ";",
}


@dataclass
class NcnAyari:
    """Netcad NCN yazım ayarları."""

    sutunlar: List[str] = field(
        default_factory=lambda: ["no", "y", "x", "z", "kodno", "kod", "bos", "bos"]
    )
    ayirac: str = " "
    ondalik_xy: int = 2
    ondalik_z: int = 2
    ondalik_derece: int = 8
    baslik_satiri: bool = False
    sabit_genislik: bool = False
    satir_sonu: str = "\r\n"
    kotsuz_davranis: str = "atla"
    """``"atla"`` (varsayılan), ``"sifir"`` (0.000 yaz) veya ``"bos"``."""
    kodsuz_metin: str = ""
    tirnak: str = '"' 
    """Metin sütunlarını saracak tırnak karakteri. Boş bırakılırsa tırnak
    kullanılmaz. Netcad'in yazdığı dosyalarda çift tırnak kullanılır."""
    kod_no: int = 0
    """``kodno`` sütununa yazılacak tamsayı (Netcad'in sayısal kod alanı)."""
    kodlama: str = "cp1254"
    """Netcad Windows Türkçe (cp1254) kodlamasını bekler; ``utf-8`` de seçilebilir."""

    def dogrula(self) -> None:
        if not self.sutunlar:
            raise ValueError("NCN sütun listesi boş olamaz.")
        bilinmeyen = [s for s in self.sutunlar if s not in SUTUN_BASLIKLARI]
        if bilinmeyen:
            raise ValueError(
                f"Bilinmeyen NCN sütunu: {', '.join(bilinmeyen)}. "
                f"Kullanılabilir sütunlar: {', '.join(SUTUN_BASLIKLARI)}"
            )
        if self.kotsuz_davranis not in ("atla", "sifir", "bos"):
            raise ValueError(
                f"Geçersiz kotsuz nokta davranışı: {self.kotsuz_davranis!r}. "
                f"'atla', 'sifir' veya 'bos' olmalıdır."
            )
        if self.ondalik_xy < 0 or self.ondalik_z < 0:
            raise ValueError("Ondalık basamak sayısı negatif olamaz.")


# Hazır profiller
def _virgullu(sutunlar: List[str], **ekler) -> NcnAyari:
    """Virgülle ayrılmış, üç ondalıklı, tırnaksız klasik düzen."""
    temel = dict(
        sutunlar=sutunlar, ayirac=",", ondalik_xy=3, ondalik_z=3, tirnak=""
    )
    temel.update(ekler)
    return NcnAyari(**temel)


NCN_PROFILLERI: Dict[str, NcnAyari] = {
    # Netcad'in kendi yazdığı düzen (varsayılan):
    #   1/4 429903.20 4064858.18 636.44 0 "YPA1" "" ""
    "netcad": NcnAyari(),
    "netcad-virgul": _virgullu(["no", "y", "x", "z", "kod"]),
    "netcad-bosluk": _virgullu(
        ["no", "y", "x", "z", "kod"], ayirac=" ", sabit_genislik=True
    ),
    "no-y-x-z": _virgullu(["no", "y", "x", "z"]),
    "no-x-y-z-kod": _virgullu(["no", "x", "y", "z", "kod"]),
    "y-x-z": _virgullu(["y", "x", "z"]),
    "x-y-z": _virgullu(["x", "y", "z"]),
    "ayrintili": _virgullu(
        ["no", "y", "x", "z", "kod", "enlem", "boylam"], baslik_satiri=True
    ),
}


def _hucre(nokta, sutun: str, ayar: NcnAyari) -> str:
    if sutun == "no":
        return str(nokta.no)
    if sutun == "y":
        return f"{nokta.saga:.{ayar.ondalik_xy}f}"
    if sutun == "x":
        return f"{nokta.yukari:.{ayar.ondalik_xy}f}"
    if sutun == "z":
        if nokta.kot is None:
            return "" if ayar.kotsuz_davranis == "bos" else f"{0.0:.{ayar.ondalik_z}f}"
        return f"{nokta.kot:.{ayar.ondalik_z}f}"
    if sutun == "kod":
        return nokta.kod or ayar.kodsuz_metin
    if sutun == "enlem":
        return f"{nokta.enlem:.{ayar.ondalik_derece}f}"
    if sutun == "boylam":
        return f"{nokta.boylam:.{ayar.ondalik_derece}f}"
    if sutun == "satir":
        return str(nokta.satir + 1)
    if sutun == "sutun":
        return str(nokta.sutun + 1)
    if sutun == "aciklama":
        return nokta.kaynak or ""
    if sutun == "kodno":
        return str(ayar.kod_no)
    if sutun == "bos":
        return ""
    raise ValueError(f"Bilinmeyen NCN sütunu: {sutun!r}")


def _hucre_bicimli(nokta, sutun: str, ayar: NcnAyari) -> str:
    """Hücreyi üretir ve gerekiyorsa tırnağa alır."""
    deger = _hucre(nokta, sutun, ayar)
    if ayar.tirnak and sutun in TIRNAKLANACAK:
        return f"{ayar.tirnak}{deger}{ayar.tirnak}"
    return deger


def ncn_satirlari(noktalar: Sequence, ayar: Optional[NcnAyari] = None) -> List[str]:
    """NCN dosyasının satırlarını (satır sonu olmadan) üretir."""
    ayar = ayar or NcnAyari()
    ayar.dogrula()

    yazilacak = [
        n
        for n in noktalar
        if n.kot is not None or ayar.kotsuz_davranis != "atla" or "z" not in ayar.sutunlar
    ]

    tablo: List[List[str]] = [
        [_hucre_bicimli(n, s, ayar) for s in ayar.sutunlar] for n in yazilacak
    ]

    if ayar.sabit_genislik and tablo:
        genislikler = [
            max(len(satir[i]) for satir in tablo) for i in range(len(ayar.sutunlar))
        ]
        if ayar.baslik_satiri:
            genislikler = [
                max(g, len(SUTUN_BASLIKLARI[ayar.sutunlar[i]]))
                for i, g in enumerate(genislikler)
            ]
        sayisal = {"y", "x", "z", "satir", "sutun", "kodno"}
        def bicimle(satir: List[str]) -> str:
            parcalar = []
            for i, deger in enumerate(satir):
                if ayar.sutunlar[i] in sayisal:
                    parcalar.append(deger.rjust(genislikler[i]))
                else:
                    parcalar.append(deger.ljust(genislikler[i]))
            return ayar.ayirac.join(parcalar).rstrip()
    else:
        def bicimle(satir: List[str]) -> str:
            return ayar.ayirac.join(satir)

    satirlar: List[str] = []
    if ayar.baslik_satiri:
        basliklar = [SUTUN_BASLIKLARI[s] for s in ayar.sutunlar]
        satirlar.append(bicimle(basliklar))
    satirlar.extend(bicimle(satir) for satir in tablo)
    return satirlar


def ncn_yaz(
    yol: str,
    noktalar: Sequence,
    ayar: Optional[NcnAyari] = None,
) -> int:
    """
    Noktaları NCN dosyasına yazar ve yazılan nokta sayısını döndürür.

    Dosya varsayılan olarak Windows satır sonu (CRLF) ve Türkçe Windows
    kod sayfası (cp1254) ile yazılır; Netcad'in beklediği biçim budur.
    Kodlamada temsil edilemeyen karakterler en yakın ASCII karşılığına
    indirgenir.
    """
    ayar = ayar or NcnAyari()
    satirlar = ncn_satirlari(noktalar, ayar)
    klasor = os.path.dirname(os.path.abspath(yol))
    if klasor:
        os.makedirs(klasor, exist_ok=True)
    icerik = ayar.satir_sonu.join(satirlar) + (ayar.satir_sonu if satirlar else "")
    try:
        ham = icerik.encode(ayar.kodlama)
    except (UnicodeEncodeError, LookupError):
        ham = icerik.encode(ayar.kodlama, errors="replace")
    with open(yol, "wb") as f:
        f.write(ham)
    return len(satirlar) - (1 if ayar.baslik_satiri else 0)


def profil_coz(
    profil: str,
    sutunlar: Optional[str] = None,
    ayirac: Optional[str] = None,
    ondalik_xy: Optional[int] = None,
    ondalik_z: Optional[int] = None,
    baslik: Optional[bool] = None,
    kotsuz: Optional[str] = None,
    kodlama: Optional[str] = None,
    satir_sonu: Optional[str] = None,
    tirnak: Optional[str] = None,
    kod_no: Optional[int] = None,
) -> NcnAyari:
    """Komut satırı seçeneklerinden ``NcnAyari`` üretir."""
    temel = NCN_PROFILLERI.get(profil)
    if temel is None:
        raise ValueError(
            f"Bilinmeyen NCN profili: {profil!r}. "
            f"Seçenekler: {', '.join(NCN_PROFILLERI)}"
        )
    ayar = NcnAyari(
        sutunlar=list(temel.sutunlar),
        ayirac=temel.ayirac,
        ondalik_xy=temel.ondalik_xy,
        ondalik_z=temel.ondalik_z,
        ondalik_derece=temel.ondalik_derece,
        baslik_satiri=temel.baslik_satiri,
        sabit_genislik=temel.sabit_genislik,
        satir_sonu=temel.satir_sonu,
        kotsuz_davranis=temel.kotsuz_davranis,
        tirnak=temel.tirnak,
        kod_no=temel.kod_no,
        kodlama=temel.kodlama,
    )
    if sutunlar:
        ayar.sutunlar = [s.strip().lower() for s in sutunlar.split(",") if s.strip()]
    if ayirac:
        ayar.ayirac = AYIRACLAR.get(ayirac, ayirac)
    if ondalik_xy is not None:
        ayar.ondalik_xy = ondalik_xy
    if ondalik_z is not None:
        ayar.ondalik_z = ondalik_z
    if baslik is not None:
        ayar.baslik_satiri = baslik
    if kotsuz:
        ayar.kotsuz_davranis = kotsuz
    if kodlama:
        ayar.kodlama = kodlama
    if satir_sonu:
        ayar.satir_sonu = {"crlf": "\r\n", "lf": "\n"}.get(satir_sonu.lower(), satir_sonu)
    if tirnak is not None:
        ayar.tirnak = "" if tirnak in ("yok", "none") else tirnak
    if kod_no is not None:
        ayar.kod_no = kod_no
    ayar.dogrula()
    return ayar
