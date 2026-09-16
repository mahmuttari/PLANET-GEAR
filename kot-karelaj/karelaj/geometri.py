# -*- coding: utf-8 -*-
"""
Alan (çalışma sahası) tanımı ve geometri işlemleri
==================================================

Karelajı üretilecek alan şu yollarla tanımlanabilir:

* Sınır kutusu (bounding box) - enlem/boylam köşeleri
* Poligon dosyası: GeoJSON, KML, KMZ, WKT, CSV/TXT, Netcad NCN
* Doğrudan köşe listesi

Tüm iç gösterim **WGS84 coğrafi (boylam, enlem)** ikilileri üzerinedir.
Netcad NCN gibi izdüşümlü dosyalar okunurken kaynak koordinat sistemi
belirtilmelidir.
"""

from __future__ import annotations

import json
import os
import re
import zipfile
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple
from xml.etree import ElementTree

from .geodezi import GRS80, KoordinatSistemi, poligon_alani_elipsoidal

__all__ = [
    "Alan",
    "SinirKutusu",
    "alan_oku",
    "alan_sinir_kutusundan",
    "nokta_poligon_icinde",
    "halka_yonu_saat_yonu",
]

Nokta2B = Tuple[float, float]


# ---------------------------------------------------------------------------
# Sınır kutusu
# ---------------------------------------------------------------------------


@dataclass
class SinirKutusu:
    """Coğrafi sınır kutusu (derece)."""

    min_boylam: float
    min_enlem: float
    max_boylam: float
    max_enlem: float

    @property
    def merkez(self) -> Nokta2B:
        return (
            (self.min_boylam + self.max_boylam) / 2.0,
            (self.min_enlem + self.max_enlem) / 2.0,
        )

    def kose_noktalari(self) -> List[Nokta2B]:
        return [
            (self.min_boylam, self.min_enlem),
            (self.max_boylam, self.min_enlem),
            (self.max_boylam, self.max_enlem),
            (self.min_boylam, self.max_enlem),
        ]

    def genislet(self, derece: float) -> "SinirKutusu":
        return SinirKutusu(
            self.min_boylam - derece,
            self.min_enlem - derece,
            self.max_boylam + derece,
            self.max_enlem + derece,
        )

    def __str__(self) -> str:
        return (
            f"enlem {self.min_enlem:.6f}..{self.max_enlem:.6f}, "
            f"boylam {self.min_boylam:.6f}..{self.max_boylam:.6f}"
        )


# ---------------------------------------------------------------------------
# Alan
# ---------------------------------------------------------------------------


@dataclass
class Alan:
    """
    Çalışma sahası.

    ``halkalar`` listesindeki ilk halka dış sınır, sonrakiler (varsa)
    iç boşluklardır (ada / delik). Her halka (boylam, enlem) ikilileri
    listesidir ve kapalı kabul edilir (son nokta ilk noktaya eşit olmak
    zorunda değildir).
    """

    halkalar: List[List[Nokta2B]] = field(default_factory=list)
    ad: str = "Çalışma alanı"
    kaynak: str = ""

    # -- oluşturucular ------------------------------------------------------

    @classmethod
    def sinir_kutusundan(cls, kutu: SinirKutusu, ad: str = "Sınır kutusu") -> "Alan":
        return cls([kutu.kose_noktalari()], ad=ad, kaynak="sınır kutusu")

    # -- temel özellikler ---------------------------------------------------

    @property
    def dis_halka(self) -> List[Nokta2B]:
        if not self.halkalar:
            raise ValueError("Alan tanımı boş.")
        return self.halkalar[0]

    @property
    def ic_halkalar(self) -> List[List[Nokta2B]]:
        return self.halkalar[1:]

    def sinir_kutusu(self) -> SinirKutusu:
        boylamlar = [p[0] for p in self.dis_halka]
        enlemler = [p[1] for p in self.dis_halka]
        return SinirKutusu(min(boylamlar), min(enlemler), max(boylamlar), max(enlemler))

    def merkez(self) -> Nokta2B:
        """Alanın ağırlık merkezi (basit poligon centroid'i)."""
        halka = self.dis_halka
        n = len(halka)
        if n < 3:
            return self.sinir_kutusu().merkez
        a = 0.0
        cx = 0.0
        cy = 0.0
        for i in range(n):
            x1, y1 = halka[i]
            x2, y2 = halka[(i + 1) % n]
            capraz = x1 * y2 - x2 * y1
            a += capraz
            cx += (x1 + x2) * capraz
            cy += (y1 + y2) * capraz
        if abs(a) < 1e-15:
            return self.sinir_kutusu().merkez
        a *= 0.5
        return (cx / (6.0 * a), cy / (6.0 * a))

    def alan_m2(self) -> float:
        """Elipsoidal yüzey alanı (m²); iç halkalar düşülür."""
        toplam = poligon_alani_elipsoidal(self.dis_halka, GRS80)
        for halka in self.ic_halkalar:
            toplam -= poligon_alani_elipsoidal(halka, GRS80)
        return max(0.0, toplam)

    def icinde_mi(self, boylam: float, enlem: float) -> bool:
        if not nokta_poligon_icinde(boylam, enlem, self.dis_halka):
            return False
        for halka in self.ic_halkalar:
            if nokta_poligon_icinde(boylam, enlem, halka):
                return False
        return True

    def dikdortgen_mi(self) -> bool:
        """Alan, sınır kutusuyla aynı mı (yalnızca sınır kutusu verilmişse)?"""
        return self.kaynak == "sınır kutusu" and len(self.halkalar) == 1

    def izdusur(self, sistem: KoordinatSistemi) -> List[List[Nokta2B]]:
        """Halkaları hedef koordinat sistemine (sağa, yukarı) dönüştürür."""
        cikti = []
        for halka in self.halkalar:
            cikti.append([sistem.wgs84ten(enlem, boylam) for boylam, enlem in halka])
        return cikti

    def ozet(self) -> str:
        n = sum(len(h) for h in self.halkalar)
        delik = len(self.ic_halkalar)
        return (
            f"{self.ad}: {len(self.halkalar)} halka ({delik} iç boşluk), "
            f"{n} köşe noktası, alan ≈ {self.alan_m2() / 10000.0:.4f} ha"
        )


def alan_sinir_kutusundan(
    enlem1: float, boylam1: float, enlem2: float, boylam2: float
) -> Alan:
    kutu = SinirKutusu(
        min(boylam1, boylam2), min(enlem1, enlem2), max(boylam1, boylam2), max(enlem1, enlem2)
    )
    return Alan.sinir_kutusundan(kutu)


# ---------------------------------------------------------------------------
# Nokta - poligon ilişkisi
# ---------------------------------------------------------------------------


def nokta_poligon_icinde(x: float, y: float, halka: Sequence[Nokta2B]) -> bool:
    """
    Işın atma (ray casting) yöntemiyle nokta-poligon içinde testi.
    Sınır üzerindeki noktalar içeride sayılır.
    """
    n = len(halka)
    if n < 3:
        return False
    icinde = False
    j = n - 1
    for i in range(n):
        xi, yi = halka[i]
        xj, yj = halka[j]
        # Sınır üzerinde mi?
        if _nokta_dogru_parcasi_uzerinde(x, y, xi, yi, xj, yj):
            return True
        if (yi > y) != (yj > y):
            kesisim = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < kesisim:
                icinde = not icinde
        j = i
    return icinde


def _nokta_dogru_parcasi_uzerinde(
    x: float, y: float, x1: float, y1: float, x2: float, y2: float, tolerans: float = 1e-12
) -> bool:
    capraz = (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)
    uzunluk2 = (x2 - x1) ** 2 + (y2 - y1) ** 2
    if uzunluk2 == 0:
        return abs(x - x1) <= tolerans and abs(y - y1) <= tolerans
    if capraz * capraz > tolerans * tolerans * uzunluk2:
        return False
    nokta = (x - x1) * (x2 - x1) + (y - y1) * (y2 - y1)
    return -tolerans <= nokta <= uzunluk2 + tolerans


def halka_yonu_saat_yonu(halka: Sequence[Nokta2B]) -> bool:
    """Halka saat yönünde mi? (işaretli alan negatifse saat yönü)"""
    toplam = 0.0
    n = len(halka)
    for i in range(n):
        x1, y1 = halka[i]
        x2, y2 = halka[(i + 1) % n]
        toplam += (x2 - x1) * (y2 + y1)
    return toplam > 0


# ---------------------------------------------------------------------------
# Dosyadan alan okuma
# ---------------------------------------------------------------------------


def alan_oku(
    yol: str,
    kaynak_sistem: Optional[KoordinatSistemi] = None,
    katman: Optional[str] = None,
    metin_sirasi: str = "enlem-boylam",
    ncn_duzen: str = "no,y,x,z,kod",
) -> Alan:
    """
    Poligon dosyasından alan okur.

    Desteklenen biçimler (uzantıdan ve içerikten saptanır):
    ``.geojson`` / ``.json``, ``.kml``, ``.kmz``, ``.wkt``, ``.csv``,
    ``.txt``, ``.ncn``.

    ``kaynak_sistem`` yalnızca izdüşümlü dosyalar (NCN ve izdüşümlü CSV)
    için gereklidir; verilen koordinatlar bu sistemden WGS84'e çevrilir.

    ``metin_sirasi`` düz metin/CSV dosyalarındaki sütun sırasını belirler
    (``enlem-boylam`` veya ``boylam-enlem``); GeoJSON, KML ve WKT kendi
    standart sıralarıyla okunur. ``ncn_duzen`` ise NCN dosyalarındaki
    sütun sırasıdır.
    """
    if not os.path.exists(yol):
        raise FileNotFoundError(f"Alan dosyası bulunamadı: {yol}")
    uzanti = os.path.splitext(yol)[1].lower()

    if uzanti == ".kmz":
        halkalar = _kmz_oku(yol, katman)
    elif uzanti == ".kml":
        with open(yol, "rb") as f:
            halkalar = _kml_ayristir(f.read(), katman)
    elif uzanti in (".geojson", ".json"):
        with open(yol, "r", encoding="utf-8-sig") as f:
            halkalar = _geojson_ayristir(json.load(f))
    elif uzanti == ".wkt":
        with open(yol, "r", encoding="utf-8-sig") as f:
            halkalar = _wkt_ayristir(f.read())
    elif uzanti == ".ncn":
        halkalar = [_ncn_oku(yol, ncn_duzen)]
    elif uzanti in (".csv", ".txt", ".asc", ".dat"):
        sira = "boylam-enlem" if (kaynak_sistem is not None and not kaynak_sistem.cografi) else metin_sirasi
        halkalar = [_ayrik_metin_oku(yol, sira)]
    else:
        # İçerikten sapta
        with open(yol, "r", encoding="utf-8-sig", errors="replace") as f:
            icerik = f.read()
        halkalar = _icerikten_ayristir(icerik, metin_sirasi)

    if not halkalar or not halkalar[0]:
        raise ValueError(f"{yol} dosyasından poligon çıkarılamadı.")

    izdusumlu = uzanti in (".ncn",) or (
        kaynak_sistem is not None and not kaynak_sistem.cografi and uzanti in (".csv", ".txt", ".dat")
    )
    if izdusumlu:
        if kaynak_sistem is None:
            raise ValueError(
                "İzdüşümlü sınır dosyası için kaynak koordinat sistemi belirtilmelidir "
                "(--sinir-sistemi)."
            )
        donusturulmus = []
        for halka in halkalar:
            yeni = []
            for saga, yukari in halka:
                enlem, boylam = kaynak_sistem.wgs84e(saga, yukari)
                yeni.append((boylam, enlem))
            donusturulmus.append(yeni)
        halkalar = donusturulmus

    halkalar = [_halkayi_temizle(h) for h in halkalar]
    halkalar = [h for h in halkalar if len(h) >= 3]
    if not halkalar:
        raise ValueError(f"{yol}: en az 3 köşe noktası olan bir poligon bulunamadı.")

    return Alan(halkalar, ad=os.path.basename(yol), kaynak=yol)


def _halkayi_temizle(halka: List[Nokta2B]) -> List[Nokta2B]:
    """Kapanış noktasını ve ardışık tekrarları kaldırır."""
    temiz: List[Nokta2B] = []
    for p in halka:
        if temiz and abs(p[0] - temiz[-1][0]) < 1e-12 and abs(p[1] - temiz[-1][1]) < 1e-12:
            continue
        temiz.append(p)
    if len(temiz) > 1 and abs(temiz[0][0] - temiz[-1][0]) < 1e-12 and abs(temiz[0][1] - temiz[-1][1]) < 1e-12:
        temiz.pop()
    return temiz


def _icerikten_ayristir(icerik: str, metin_sirasi: str = "enlem-boylam") -> List[List[Nokta2B]]:
    kirp = icerik.lstrip()
    if kirp.startswith("{") or kirp.startswith("["):
        return _geojson_ayristir(json.loads(icerik))
    if kirp.lower().startswith(("polygon", "multipolygon", "linestring")):
        return _wkt_ayristir(icerik)
    if "<kml" in kirp[:2000].lower() or "<coordinates" in kirp.lower():
        return _kml_ayristir(icerik.encode("utf-8"), None)
    return [_metin_satirlarindan(icerik.splitlines(), metin_sirasi)]


# -- GeoJSON ----------------------------------------------------------------


def _geojson_ayristir(veri: dict) -> List[List[Nokta2B]]:
    halkalar: List[List[Nokta2B]] = []

    def geometri_isle(g: dict) -> None:
        if not isinstance(g, dict):
            return
        tur = (g.get("type") or "").lower()
        koord = g.get("coordinates")
        if tur == "polygon" and koord:
            for halka in koord:
                halkalar.append([(float(p[0]), float(p[1])) for p in halka])
        elif tur == "multipolygon" and koord:
            for poligon in koord:
                for i, halka in enumerate(poligon):
                    # Çoklu poligonda yalnızca dış halkaları ayrı alan olarak al
                    if i == 0 or not halkalar:
                        halkalar.append([(float(p[0]), float(p[1])) for p in halka])
        elif tur in ("linestring", "multipoint") and koord:
            halkalar.append([(float(p[0]), float(p[1])) for p in koord])
        elif tur == "multilinestring" and koord:
            for parca in koord:
                halkalar.append([(float(p[0]), float(p[1])) for p in parca])
        elif tur == "geometrycollection":
            for alt in g.get("geometries", []):
                geometri_isle(alt)

    tur = (veri.get("type") or "").lower()
    if tur == "featurecollection":
        for ozellik in veri.get("features", []):
            geometri_isle(ozellik.get("geometry") or {})
    elif tur == "feature":
        geometri_isle(veri.get("geometry") or {})
    else:
        geometri_isle(veri)
    return halkalar


# -- KML / KMZ --------------------------------------------------------------


def _etiket_adi(etiket: str) -> str:
    return etiket.split("}")[-1].lower()


def _kml_ayristir(ham: bytes, katman: Optional[str]) -> List[List[Nokta2B]]:
    kok = ElementTree.fromstring(ham)
    halkalar: List[List[Nokta2B]] = []

    def yer_isaretleri(dugum) -> Iterable:
        for alt in dugum.iter():
            if _etiket_adi(alt.tag) == "placemark":
                yield alt

    hedefler = list(yer_isaretleri(kok))
    if katman:
        sec = []
        for p in hedefler:
            for alt in p:
                if _etiket_adi(alt.tag) == "name" and (alt.text or "").strip() == katman:
                    sec.append(p)
        if sec:
            hedefler = sec
    if not hedefler:
        hedefler = [kok]

    for yer in hedefler:
        for dugum in yer.iter():
            ad = _etiket_adi(dugum.tag)
            if ad in ("linearring", "linestring"):
                for alt in dugum.iter():
                    if _etiket_adi(alt.tag) == "coordinates" and alt.text:
                        nokta = _kml_koordinat_ayristir(alt.text)
                        if len(nokta) >= 3:
                            halkalar.append(nokta)
    if not halkalar:
        for dugum in kok.iter():
            if _etiket_adi(dugum.tag) == "coordinates" and dugum.text:
                nokta = _kml_koordinat_ayristir(dugum.text)
                if len(nokta) >= 3:
                    halkalar.append(nokta)
    return halkalar


def _kml_koordinat_ayristir(metin: str) -> List[Nokta2B]:
    noktalar: List[Nokta2B] = []
    for parca in metin.replace("\n", " ").replace("\t", " ").split():
        alanlar = parca.split(",")
        if len(alanlar) >= 2:
            try:
                noktalar.append((float(alanlar[0]), float(alanlar[1])))
            except ValueError:
                continue
    return noktalar


def _kmz_oku(yol: str, katman: Optional[str]) -> List[List[Nokta2B]]:
    with zipfile.ZipFile(yol) as z:
        kml_adlari = [a for a in z.namelist() if a.lower().endswith(".kml")]
        if not kml_adlari:
            raise ValueError(f"{yol} içinde KML dosyası yok.")
        tercih = [a for a in kml_adlari if a.lower().endswith("doc.kml")] or kml_adlari
        return _kml_ayristir(z.read(tercih[0]), katman)


# -- WKT --------------------------------------------------------------------

_WKT_HALKA = re.compile(r"\(([^()]*)\)")


def _wkt_ayristir(metin: str) -> List[List[Nokta2B]]:
    halkalar: List[List[Nokta2B]] = []
    for eslesme in _WKT_HALKA.finditer(metin):
        noktalar: List[Nokta2B] = []
        for parca in eslesme.group(1).split(","):
            alanlar = parca.split()
            if len(alanlar) >= 2:
                try:
                    noktalar.append((float(alanlar[0]), float(alanlar[1])))
                except ValueError:
                    continue
        if len(noktalar) >= 3:
            halkalar.append(noktalar)
    return halkalar


# -- Düz metin / CSV / NCN --------------------------------------------------

def _sayilari_al(satir: str) -> List[float]:
    """
    Bir satırdaki sayıları çıkarır.

    Virgül hem alan ayırıcısı ("1,494000.000,...") hem de Türkçe ondalık
    ayırıcısı ("494000,000") olabildiği için önce **alan ayırıcısı**
    saptanır, sonra her alan sayıya çevrilir. Alanlara bölmeden doğrudan
    örüntü aramak, "1,494000.000" dizisini tek bir "1,494000" sayısı
    gibi okuyup koordinatları bozar.

    Ayırıcı önceliği: noktalı virgül, virgül, boşluk. Türkçe ondalık
    ayırıcısı kullanılacaksa alan ayırıcısı noktalı virgül olmalıdır
    (Excel'in Türkçe CSV çıktısı zaten böyledir).
    """
    if ";" in satir:
        alanlar = satir.split(";")
    elif "," in satir:
        alanlar = satir.split(",")
    else:
        alanlar = satir.split()

    parcalar: List[str] = []
    for alan in alanlar:
        parcalar.extend(alan.split())

    degerler: List[float] = []
    for parca in parcalar:
        temiz = parca.strip()
        if not temiz:
            continue
        try:
            degerler.append(float(temiz))
            continue
        except ValueError:
            pass
        try:
            degerler.append(float(temiz.replace(",", ".")))
        except ValueError:
            continue
    return degerler


def _ayrik_metin_oku(yol: str, sira: str = "enlem-boylam") -> List[Nokta2B]:
    with open(yol, "r", encoding="utf-8-sig", errors="replace") as f:
        return _metin_satirlarindan(f.readlines(), sira)


def _metin_satirlarindan(
    satirlar: Iterable[str], sira: str = "enlem-boylam"
) -> List[Nokta2B]:
    """
    Düz metin/CSV satırlarından koordinat çifti listesi üretir.

    Türkiye'de enlem (36-42) ve boylam (26-45) aralıkları çakıştığı için
    sıra sezgiyle saptanamaz; bu yüzden ``sira`` açıkça verilir:

    ``"enlem-boylam"``
        Google Earth'ün gösterdiği ve panoya kopyaladığı sıra (varsayılan).
    ``"boylam-enlem"``
        GeoJSON / WKT standardı ve izdüşümlü dosyalarda (sağa, yukarı) sırası.
    """
    if sira not in ("enlem-boylam", "boylam-enlem"):
        raise ValueError(
            f"Geçersiz koordinat sırası: {sira!r}. "
            f"'enlem-boylam' veya 'boylam-enlem' olmalıdır."
        )
    noktalar: List[Nokta2B] = []
    for satir in satirlar:
        s = satir.strip()
        if not s or s.startswith("#") or s.startswith("//") or s.startswith(";"):
            continue
        degerler = _sayilari_al(s)
        if len(degerler) < 2:
            continue
        a, b = degerler[0], degerler[1]
        if sira == "enlem-boylam":
            noktalar.append((b, a))  # (boylam, enlem) olarak sakla
        else:
            noktalar.append((a, b))
    return noktalar


def _ncn_oku(yol: str, duzen: str = "no,y,x,z,kod") -> List[Nokta2B]:
    """
    Netcad NCN nokta dosyasından sınır köşelerini okur.

    ``duzen`` sütun sırasını verir; varsayılan, yazıcının da ürettiği
    ``no,y,x,z,kod`` düzenidir (Y = sağa değer, X = yukarı değer).
    Netcad'inizdeki dosya farklı sıradaysa (örn. ``no,x,y,z,kod``) bu
    sıra ``--sinir-ncn-duzen`` ile verilmelidir.

    Dönen çiftler ``(sağa, yukarı)`` sırasındadır.
    """
    sutunlar = [p.strip().lower() for p in duzen.split(",") if p.strip()]
    if "y" not in sutunlar or "x" not in sutunlar:
        raise ValueError(
            f"NCN sütun düzeninde hem 'y' (sağa) hem 'x' (yukarı) bulunmalıdır: {duzen!r}"
        )
    # Sayısal olmayan sütunlar (no ve kod) sayı listesinde yer almayabilir;
    # bu yüzden yalnızca sayıya çevrilebilen sütunlar sayılır.
    sayisal_sutunlar = [s for s in sutunlar if s in ("no", "y", "x", "z", "satir", "sutun")]
    try:
        y_indis = sayisal_sutunlar.index("y")
        x_indis = sayisal_sutunlar.index("x")
    except ValueError as hata:  # pragma: no cover - yukarıda denetlendi
        raise ValueError(f"Geçersiz NCN sütun düzeni: {duzen!r}") from hata

    noktalar: List[Nokta2B] = []
    gereken = max(y_indis, x_indis) + 1
    with open(yol, "r", encoding="utf-8-sig", errors="replace") as f:
        for satir_no, satir in enumerate(f, start=1):
            s = satir.strip()
            if not s or s.startswith("#") or s.startswith(";") or s.startswith("//"):
                continue
            degerler = _sayilari_al(s)
            if len(degerler) < gereken:
                continue
            noktalar.append((degerler[y_indis], degerler[x_indis]))
    if not noktalar:
        raise ValueError(
            f"{yol}: NCN dosyasından nokta okunamadı. Sütun düzenini "
            f"--sinir-ncn-duzen ile denetleyin (verilen: {duzen})."
        )
    return noktalar
