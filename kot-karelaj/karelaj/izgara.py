# -*- coding: utf-8 -*-
"""
Karelaj (ızgara) üretimi
========================

Çalışma alanını hedef koordinat sistemine izdüşürür, istenen metrik
aralıkta düzenli bir nokta ağı (karelaj) üretir ve isteğe bağlı olarak
alan sınırına kırpar.

Öne çıkan özellikler:

* **Metrik aralık:** Karelaj aralığı izdüşüm düzleminde metre cinsindendir
  (10 m, 25 m, 50 m ...). Coğrafi derece aralığı kullanılmaz; bu sayede
  kareler arazide gerçekten kare olur.
* **Tam katlara hizalama:** Varsayılan olarak ızgara, koordinatları
  aralığın tam katlarına gelecek şekilde oturtulur (örn. 25 m aralıkta
  sağa değerler ...475, 500, 525...). Harita mühendisliğinde beklenen
  davranış budur; paftalar arasında karelaj süreklidir.
* **Döndürme:** Karelaj, alanın ağırlık merkezi etrafında istenen açıyla
  döndürülebilir (örn. bir kollektör hattı ekseni boyunca).
* **Kırpma:** Ağ, poligon sınırının dışına taşan noktalardan arındırılır;
  isteğe bağlı tampon (buffer) mesafesi uygulanabilir.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

from . import bicim
from .geodezi import KoordinatSistemi
from .geometri import Alan, nokta_poligon_icinde

__all__ = [
    "Nokta",
    "NumaralandirmaAyari",
    "KarelajAyari",
    "Karelaj",
    "karelaj_uret",
    "nokta_sayisi_tahmini",
]


# ---------------------------------------------------------------------------
# Nokta
# ---------------------------------------------------------------------------


@dataclass
class Nokta:
    """
    Karelaj noktası.

    ``saga``  : sağa değer (easting, Türkiye'de Y ekseni)
    ``yukari``: yukarı değer (northing, Türkiye'de X ekseni)
    ``kot``   : yükseklik (m). Kot kaynağından okunana kadar ``None``.
    """

    no: str
    saga: float
    yukari: float
    enlem: float
    boylam: float
    satir: int
    sutun: int
    kot: Optional[float] = None
    kod: str = ""
    kaynak: str = ""

    @property
    def kotlu(self) -> bool:
        return self.kot is not None


# ---------------------------------------------------------------------------
# Ayarlar
# ---------------------------------------------------------------------------


@dataclass
class NumaralandirmaAyari:
    """
    Nokta numaralandırma biçimi.

    ``profil``:
      * ``"sira"``        -> 1, 2, 3, ... (varsayılan)
      * ``"satir-sutun"`` -> S01-01, S01-02, ... (satır-sütun)
      * ``"sutun-satir"`` -> 01-S01 biçiminde ters sıralı
    """

    profil: str = "sira"
    onek: str = ""
    baslangic: int = 1
    basamak: int = 0
    ayirac: str = "-"

    def uret(self, sira: int, satir: int, sutun: int) -> str:
        if self.profil == "sira":
            n = self.baslangic + sira
            govde = str(n).zfill(self.basamak) if self.basamak else str(n)
        elif self.profil == "satir-sutun":
            b = self.basamak or 3
            govde = f"{str(satir + 1).zfill(b)}{self.ayirac}{str(sutun + 1).zfill(b)}"
        elif self.profil == "sutun-satir":
            b = self.basamak or 3
            govde = f"{str(sutun + 1).zfill(b)}{self.ayirac}{str(satir + 1).zfill(b)}"
        else:
            raise ValueError(f"Bilinmeyen numaralandırma profili: {self.profil!r}")
        return f"{self.onek}{govde}"


@dataclass
class KarelajAyari:
    """Karelaj üretim parametreleri."""

    aralik: float = 25.0
    """Karelaj aralığı (m). Kare ızgara için tek değer yeterlidir."""

    aralik_yukari: Optional[float] = None
    """Yukarı yöndeki aralık farklıysa (dikdörtgen ızgara) burada verilir."""

    hizalama: str = "tam-kat"
    """``"tam-kat"`` (aralığın tam katlarına oturt) veya ``"alan"`` (alanın
    güneybatı köşesinden başlat)."""

    donme_acisi: float = 0.0
    """Karelajın grid kuzeyine göre döndürme açısı (derece, saat yönünün
    tersi pozitif)."""

    kirp: bool = True
    """Alan sınırı dışındaki noktaları at."""

    tampon: float = 0.0
    """Kırpmada alan sınırına eklenecek tampon mesafesi (m). Negatif değer
    içeri daraltır."""

    kenar_noktalari: bool = False
    """Poligon köşe noktalarını da çıktıya ekle."""

    siralama: str = "kuzey-guney"
    """Satır sırası: ``"kuzey-guney"`` (ilk satır en kuzeyde, varsayılan)
    veya ``"guney-kuzey"``."""

    numaralandirma: NumaralandirmaAyari = field(default_factory=NumaralandirmaAyari)

    nokta_kodu: str = ""
    """Tüm noktalara yazılacak sabit kod (Netcad'de nokta kodu sütunu)."""

    azami_nokta: int = 500000
    """Güvenlik sınırı; aşılırsa üretim hata verir."""

    def etkin_aralik_yukari(self) -> float:
        """Yukarı yöndeki aralık; verilmemişse (None) kare ızgara varsayılır."""
        return self.aralik if self.aralik_yukari is None else self.aralik_yukari

    def dogrula(self) -> None:
        if self.aralik <= 0:
            raise ValueError("Karelaj aralığı sıfırdan büyük olmalıdır.")
        if self.etkin_aralik_yukari() <= 0:
            raise ValueError("Yukarı yöndeki karelaj aralığı sıfırdan büyük olmalıdır.")
        if self.hizalama not in ("tam-kat", "alan"):
            raise ValueError(
                f"Geçersiz hizalama: {self.hizalama!r}. 'tam-kat' veya 'alan' olmalıdır."
            )
        if self.siralama not in ("kuzey-guney", "guney-kuzey"):
            raise ValueError(
                f"Geçersiz sıralama: {self.siralama!r}. "
                f"'kuzey-guney' veya 'guney-kuzey' olmalıdır."
            )


# ---------------------------------------------------------------------------
# Karelaj sonucu
# ---------------------------------------------------------------------------


@dataclass
class Karelaj:
    """Üretilmiş karelaj: noktalar, matris düzeni ve üretim bilgileri."""

    noktalar: List[Nokta]
    matris: List[List[Optional[Nokta]]]
    sistem: KoordinatSistemi
    ayar: KarelajAyari
    alan: Alan
    baslangic_saga: float
    baslangic_yukari: float
    satir_sayisi: int
    sutun_sayisi: int
    izdusum_halkalari: List[List[Tuple[float, float]]] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.noktalar)

    def __iter__(self) -> Iterator[Nokta]:
        return iter(self.noktalar)

    @property
    def kotlu_noktalar(self) -> List[Nokta]:
        return [n for n in self.noktalar if n.kotlu]

    def kot_istatistikleri(self) -> Dict[str, float]:
        kotlar = [n.kot for n in self.noktalar if n.kot is not None]
        if not kotlar:
            return {}
        n = len(kotlar)
        ortalama = sum(kotlar) / n
        varyans = sum((k - ortalama) ** 2 for k in kotlar) / n if n > 1 else 0.0
        sirali = sorted(kotlar)
        return {
            "adet": float(n),
            "en_dusuk": sirali[0],
            "en_yuksek": sirali[-1],
            "ortalama": ortalama,
            "ortanca": sirali[n // 2] if n % 2 else (sirali[n // 2 - 1] + sirali[n // 2]) / 2.0,
            "standart_sapma": math.sqrt(varyans),
            "yukseklik_farki": sirali[-1] - sirali[0],
        }

    def kapsanan_alan_m2(self) -> float:
        """Karelaj noktalarının temsil ettiği yaklaşık alan (m²)."""
        return len(self.noktalar) * self.ayar.aralik * self.ayar.etkin_aralik_yukari()

    def eksik_kot_sayisi(self) -> int:
        return sum(1 for n in self.noktalar if not n.kotlu)


# ---------------------------------------------------------------------------
# Üretim
# ---------------------------------------------------------------------------


def nokta_sayisi_tahmini(alan: Alan, sistem: KoordinatSistemi, ayar: KarelajAyari) -> int:
    """Kırpma öncesi yaklaşık nokta sayısı (kullanıcıyı uyarmak için)."""
    halkalar = alan.izdusur(sistem)
    xs = [p[0] for p in halkalar[0]]
    ys = [p[1] for p in halkalar[0]]
    genislik = max(xs) - min(xs)
    yukseklik = max(ys) - min(ys)
    if ayar.donme_acisi:
        # Döndürülmüş ızgarada sınır kutusu büyür
        a = math.radians(abs(ayar.donme_acisi) % 90.0)
        genislik, yukseklik = (
            genislik * math.cos(a) + yukseklik * math.sin(a),
            genislik * math.sin(a) + yukseklik * math.cos(a),
        )
    sutun = int(genislik / ayar.aralik) + 2
    satir = int(yukseklik / ayar.etkin_aralik_yukari()) + 2
    return max(0, sutun) * max(0, satir)


def _dondur(x: float, y: float, aci_rad: float) -> Tuple[float, float]:
    c, s = math.cos(aci_rad), math.sin(aci_rad)
    return x * c - y * s, x * s + y * c


def karelaj_uret(
    alan: Alan,
    sistem: KoordinatSistemi,
    ayar: Optional[KarelajAyari] = None,
) -> Karelaj:
    """
    Alan ve koordinat sistemine göre karelaj noktalarını üretir.

    Kot değerleri bu aşamada doldurulmaz; ``karelaj.kaynaklar`` modülündeki
    bir kot kaynağı ile ayrıca okunur.
    """
    ayar = ayar or KarelajAyari()
    ayar.dogrula()
    if sistem.cografi:
        raise ValueError(
            "Karelaj metrik aralıkla üretildiğinden izdüşümlü bir koordinat "
            "sistemi gerekir (örn. ITRF96-TM30). Coğrafi sistem yalnızca çıktı "
            "sütunu olarak eklenebilir."
        )

    aralik_x = ayar.aralik
    aralik_y = ayar.etkin_aralik_yukari()
    aci = math.radians(ayar.donme_acisi)

    izdusum_halkalari = alan.izdusur(sistem)
    dis = izdusum_halkalari[0]
    if len(dis) < 3:
        raise ValueError("Alan sınırı en az 3 köşe noktası içermelidir.")

    # Döndürülmüş çerçevenin dayanak noktası: alanın izdüşümdeki merkezi
    merkez_boylam, merkez_enlem = alan.merkez()
    dayanak = sistem.wgs84ten(merkez_enlem, merkez_boylam)

    def gride(x: float, y: float) -> Tuple[float, float]:
        return _dondur(x - dayanak[0], y - dayanak[1], -aci)

    def griddens(u: float, v: float) -> Tuple[float, float]:
        dx, dy = _dondur(u, v, aci)
        return dx + dayanak[0], dy + dayanak[1]

    grid_kose = [gride(x, y) for x, y in dis]
    min_u = min(p[0] for p in grid_kose)
    max_u = max(p[0] for p in grid_kose)
    min_v = min(p[1] for p in grid_kose)
    max_v = max(p[1] for p in grid_kose)

    tampon = ayar.tampon
    if tampon > 0:
        min_u -= tampon
        max_u += tampon
        min_v -= tampon
        max_v += tampon

    if ayar.hizalama == "tam-kat":
        if ayar.donme_acisi:
            # Döndürülmüş çerçevede tam kat, dayanak noktasına göre tanımlıdır.
            baslangic_u = math.floor(min_u / aralik_x) * aralik_x
            baslangic_v = math.floor(min_v / aralik_y) * aralik_y
        else:
            mutlak_u = dayanak[0] + min_u
            mutlak_v = dayanak[1] + min_v
            baslangic_u = math.floor(mutlak_u / aralik_x) * aralik_x - dayanak[0]
            baslangic_v = math.floor(mutlak_v / aralik_y) * aralik_y - dayanak[1]
    else:
        baslangic_u = min_u
        baslangic_v = min_v

    sutun_sayisi = int(math.floor((max_u - baslangic_u) / aralik_x)) + 1
    satir_sayisi = int(math.floor((max_v - baslangic_v) / aralik_y)) + 1
    if sutun_sayisi < 1 or satir_sayisi < 1:
        raise ValueError(
            "Seçilen aralık alandan büyük; karelaj üretilemedi. "
            "Daha küçük bir aralık verin."
        )

    toplam = sutun_sayisi * satir_sayisi
    if toplam > ayar.azami_nokta:
        raise ValueError(
            f"Üretilecek nokta sayısı ({bicim.tam_sayi(toplam)}) güvenlik sınırını "
            f"({bicim.tam_sayi(ayar.azami_nokta)}) aşıyor. Aralığı büyütün, alanı "
            f"küçültün veya --azami-nokta ile sınırı yükseltin."
        )

    # Kırpma poligonları (izdüşüm düzleminde)
    kirpma_dis = dis if ayar.kirp else None
    kirpma_ic = izdusum_halkalari[1:] if ayar.kirp else []

    matris: List[List[Optional[Nokta]]] = []
    noktalar: List[Nokta] = []
    sira = 0

    satir_araligi = (
        range(satir_sayisi - 1, -1, -1)
        if ayar.siralama == "kuzey-guney"
        else range(satir_sayisi)
    )

    for satir_indis, j in enumerate(satir_araligi):
        satir_noktalari: List[Optional[Nokta]] = []
        v = baslangic_v + j * aralik_y
        for i in range(sutun_sayisi):
            u = baslangic_u + i * aralik_x
            saga, yukari = griddens(u, v)
            if kirpma_dis is not None:
                if not _alan_icinde(saga, yukari, kirpma_dis, kirpma_ic, tampon):
                    satir_noktalari.append(None)
                    continue
            enlem, boylam = sistem.wgs84e(saga, yukari)
            nokta = Nokta(
                no="",
                saga=saga,
                yukari=yukari,
                enlem=enlem,
                boylam=boylam,
                satir=satir_indis,
                sutun=i,
                kod=ayar.nokta_kodu,
            )
            satir_noktalari.append(nokta)
            noktalar.append(nokta)
        matris.append(satir_noktalari)

    for nokta in noktalar:
        nokta.no = ayar.numaralandirma.uret(sira, nokta.satir, nokta.sutun)
        sira += 1

    if not noktalar:
        raise ValueError(
            "Alan içinde hiç karelaj noktası kalmadı. Aralığı küçültün veya "
            "--kirpma-yok ile kırpmayı kapatın."
        )

    if ayar.kenar_noktalari:
        _kose_noktalarini_ekle(noktalar, alan, sistem, ayar, len(noktalar))

    baslangic_saga, baslangic_yukari = griddens(baslangic_u, baslangic_v)

    return Karelaj(
        noktalar=noktalar,
        matris=matris,
        sistem=sistem,
        ayar=ayar,
        alan=alan,
        baslangic_saga=baslangic_saga,
        baslangic_yukari=baslangic_yukari,
        satir_sayisi=satir_sayisi,
        sutun_sayisi=sutun_sayisi,
        izdusum_halkalari=izdusum_halkalari,
    )


def _alan_icinde(
    x: float,
    y: float,
    dis: Sequence[Tuple[float, float]],
    ic_halkalar: Sequence[Sequence[Tuple[float, float]]],
    tampon: float,
) -> bool:
    if tampon > 0:
        # Tampon: sınıra olan uzaklık tampon kadarsa da kabul et
        if not nokta_poligon_icinde(x, y, dis):
            if _poligona_uzaklik(x, y, dis) > tampon:
                return False
    else:
        if not nokta_poligon_icinde(x, y, dis):
            return False
        if tampon < 0 and _poligona_uzaklik(x, y, dis) < -tampon:
            return False
    for halka in ic_halkalar:
        if nokta_poligon_icinde(x, y, halka):
            return False
    return True


def _poligona_uzaklik(x: float, y: float, halka: Sequence[Tuple[float, float]]) -> float:
    """Noktanın poligon sınırına en kısa uzaklığı."""
    en_kisa = float("inf")
    n = len(halka)
    for i in range(n):
        x1, y1 = halka[i]
        x2, y2 = halka[(i + 1) % n]
        en_kisa = min(en_kisa, _dogru_parcasina_uzaklik(x, y, x1, y1, x2, y2))
    return en_kisa


def _dogru_parcasina_uzaklik(
    x: float, y: float, x1: float, y1: float, x2: float, y2: float
) -> float:
    dx, dy = x2 - x1, y2 - y1
    uzunluk2 = dx * dx + dy * dy
    if uzunluk2 == 0:
        return math.hypot(x - x1, y - y1)
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / uzunluk2))
    return math.hypot(x - (x1 + t * dx), y - (y1 + t * dy))


def _kose_noktalarini_ekle(
    noktalar: List[Nokta],
    alan: Alan,
    sistem: KoordinatSistemi,
    ayar: KarelajAyari,
    baslangic_sira: int,
) -> None:
    """Poligon köşelerini ayrı kodla karelaja ekler."""
    sira = baslangic_sira
    for halka_indis, halka in enumerate(alan.halkalar):
        for boylam, enlem in halka:
            saga, yukari = sistem.wgs84ten(enlem, boylam)
            no = ayar.numaralandirma.uret(sira, -1, halka_indis)
            noktalar.append(
                Nokta(
                    no=no,
                    saga=saga,
                    yukari=yukari,
                    enlem=enlem,
                    boylam=boylam,
                    satir=-1,
                    sutun=halka_indis,
                    kod=ayar.nokta_kodu or "SINIR",
                    kaynak="alan sınırı",
                )
            )
            sira += 1
