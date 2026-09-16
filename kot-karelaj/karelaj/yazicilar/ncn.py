# -*- coding: utf-8 -*-
"""
Netcad NCN nokta dosyası yazıcısı
=================================

Netcad'in nokta dosyası (``.ncn``), her satırı bir nokta olan düz metin
bir dosyadır. Netcad'in **Nokta > Dosyadan Nokta Oku** penceresi sütun
düzenini kullanıcıya seçtirdiği için, yaygın kullanılan tek bir düzen
yerine bu yazıcı düzeni ayarlanabilir kılar.

Varsayılan düzen, Türkiye'deki ölçme uygulamasında en yaygın olanıdır::

    NoktaNo , Y (sağa değer) , X (yukarı değer) , Z (kot) , Kod
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
}

AYIRACLAR: Dict[str, str] = {
    "virgul": ",",
    "bosluk": " ",
    "sekme": "\t",
    "noktali-virgul": ";",
}


@dataclass
class NcnAyari:
    """Netcad NCN yazım ayarları."""

    sutunlar: List[str] = field(default_factory=lambda: ["no", "y", "x", "z", "kod"])
    ayirac: str = ","
    ondalik_xy: int = 3
    ondalik_z: int = 3
    ondalik_derece: int = 8
    baslik_satiri: bool = False
    sabit_genislik: bool = False
    satir_sonu: str = "\r\n"
    kotsuz_davranis: str = "atla"
    """``"atla"`` (varsayılan), ``"sifir"`` (0.000 yaz) veya ``"bos"``."""
    kodsuz_metin: str = ""
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
NCN_PROFILLERI: Dict[str, NcnAyari] = {
    "netcad": NcnAyari(),
    "netcad-bosluk": NcnAyari(ayirac=" ", sabit_genislik=True),
    "no-y-x-z": NcnAyari(sutunlar=["no", "y", "x", "z"]),
    "no-x-y-z-kod": NcnAyari(sutunlar=["no", "x", "y", "z", "kod"]),
    "y-x-z": NcnAyari(sutunlar=["y", "x", "z"]),
    "x-y-z": NcnAyari(sutunlar=["x", "y", "z"]),
    "ayrintili": NcnAyari(
        sutunlar=["no", "y", "x", "z", "kod", "enlem", "boylam"], baslik_satiri=True
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
    raise ValueError(f"Bilinmeyen NCN sütunu: {sutun!r}")


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
        [_hucre(n, s, ayar) for s in ayar.sutunlar] for n in yazilacak
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
        sayisal = {"y", "x", "z", "satir", "sutun"}
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
    ayar.dogrula()
    return ayar
