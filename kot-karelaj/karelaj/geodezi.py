# -*- coding: utf-8 -*-
"""
Geodezi çekirdeği
=================

Saf Python (harici bağımlılık yok) jeodezik hesap katmanı:

* Elipsoit tanımları (GRS80 / WGS84 / Uluslararası 1924 - Hayford)
* Enlem-boylamdan Transverse Mercator (Gauss-Krüger) izdüşümü ve tersi.
  Karney (2011) "Transverse Mercator with an accuracy of a few nanometers"
  çalışmasındaki Krüger serisi 6. dereceye kadar kullanılmıştır; orta
  meridyenden +-4 derece içinde nanometre mertebesinde doğruluk verir.
* Helmert 7 parametreli datum dönüşümü (ED50 <-> WGS84 vb.)
* Türkiye'de kullanılan koordinat sistemleri kataloğu
  (ITRF96/TUREF 3 derece dilim, ED50 3 derece dilim, UTM 6 derece dilim)
* Elipsoit üzerinde mesafe ve alan hesabı

Terimler: sağa değer (easting, Y), yukarı değer (northing, X),
orta meridyen (central meridian), ölçek faktörü (scale factor),
meridyen yakınsaması (meridian convergence).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

__all__ = [
    "Elipsoit",
    "GRS80",
    "WGS84",
    "HAYFORD",
    "Helmert",
    "Datum",
    "DATUM_ITRF96",
    "DATUM_WGS84",
    "DATUM_ED50",
    "TransverseMercator",
    "KoordinatSistemi",
    "sistem_bul",
    "sistem_listesi",
    "dilim_orta_meridyeni",
    "uygun_dilim",
    "otomatik_sistem",
    "elipsoidal_mesafe",
    "poligon_alani_elipsoidal",
]


# ---------------------------------------------------------------------------
# Elipsoitler
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Elipsoit:
    """Dönel elipsoit (referans yüzey)."""

    ad: str
    a: float  # büyük yarı eksen (m)
    ters_basiklik: float  # 1/f

    @property
    def f(self) -> float:
        """Basıklık (flattening)."""
        return 1.0 / self.ters_basiklik

    @property
    def b(self) -> float:
        """Küçük yarı eksen (m)."""
        return self.a * (1.0 - self.f)

    @property
    def e2(self) -> float:
        """Birinci dışmerkezlik karesi e^2."""
        f = self.f
        return f * (2.0 - f)

    @property
    def e(self) -> float:
        return math.sqrt(self.e2)

    @property
    def es2(self) -> float:
        """İkinci dışmerkezlik karesi e'^2."""
        return self.e2 / (1.0 - self.e2)

    @property
    def n(self) -> float:
        """Üçüncü basıklık n = f / (2 - f)."""
        f = self.f
        return f / (2.0 - f)


GRS80 = Elipsoit("GRS 1980", 6378137.0, 298.257222101)
WGS84 = Elipsoit("WGS 84", 6378137.0, 298.257223563)
HAYFORD = Elipsoit("Uluslararası 1924 (Hayford)", 6378388.0, 297.0)

ELIPSOITLER: Dict[str, Elipsoit] = {
    "GRS80": GRS80,
    "WGS84": WGS84,
    "HAYFORD": HAYFORD,
    "INTL1924": HAYFORD,
}


# ---------------------------------------------------------------------------
# Datum ve Helmert dönüşümü
# ---------------------------------------------------------------------------

_ARCSEC = math.pi / (180.0 * 3600.0)


@dataclass(frozen=True)
class Helmert:
    """
    7 parametreli benzerlik (Helmert) dönüşümü.

    Öteleme (dx, dy, dz) metre, dönüklükler (rx, ry, rz) yay saniyesi,
    ölçek (s) ppm (milyonda bir) birimindedir.

    ``yontem`` iki değer alır:

    ``"position_vector"``
        EPSG 9606 - Konum vektörü dönüklüğü. EPSG'nin Türkiye için
        önerdiği ED50 -> WGS84 dönüşümü bu yöntemi kullanır.
    ``"coordinate_frame"``
        EPSG 9607 - Koordinat çatısı dönüklüğü. Dönüklüklerin işareti
        terstir (bazı kurum içi parametre takımları bu şekilde verilir).
    """

    dx: float = 0.0
    dy: float = 0.0
    dz: float = 0.0
    rx: float = 0.0
    ry: float = 0.0
    rz: float = 0.0
    s: float = 0.0
    yontem: str = "position_vector"

    @property
    def birim_yok(self) -> bool:
        return (
            self.dx == 0.0
            and self.dy == 0.0
            and self.dz == 0.0
            and self.rx == 0.0
            and self.ry == 0.0
            and self.rz == 0.0
            and self.s == 0.0
        )

    def _donukluk(self) -> Tuple[float, float, float]:
        rx = self.rx * _ARCSEC
        ry = self.ry * _ARCSEC
        rz = self.rz * _ARCSEC
        if self.yontem == "coordinate_frame":
            return -rx, -ry, -rz
        return rx, ry, rz

    def uygula(self, x: float, y: float, z: float) -> Tuple[float, float, float]:
        """Kaynak datumdan hedef datuma (ileri yön)."""
        rx, ry, rz = self._donukluk()
        m = 1.0 + self.s * 1e-6
        xs = self.dx + m * (x - rz * y + ry * z)
        ys = self.dy + m * (rz * x + y - rx * z)
        zs = self.dz + m * (-ry * x + rx * y + z)
        return xs, ys, zs

    def ters_uygula(self, x: float, y: float, z: float) -> Tuple[float, float, float]:
        """Hedef datumdan kaynak datuma (geri yön)."""
        rx, ry, rz = self._donukluk()
        m = 1.0 + self.s * 1e-6
        x0 = (x - self.dx) / m
        y0 = (y - self.dy) / m
        z0 = (z - self.dz) / m
        # Dönüklük matrisinin tersi ~ transpozu (küçük açı yaklaşımı yerine
        # 3x3 doğrusal sistemi doğrudan çözerek tam tersini alıyoruz).
        return _ters_donukluk(x0, y0, z0, rx, ry, rz)

    def aciklama(self) -> str:
        return (
            f"dX={self.dx:+.4f} m, dY={self.dy:+.4f} m, dZ={self.dz:+.4f} m, "
            f"rX={self.rx:+.6f}\", rY={self.ry:+.6f}\", rZ={self.rz:+.6f}\", "
            f"ölçek={self.s:+.6f} ppm ({self.yontem})"
        )


def _ters_donukluk(
    x: float, y: float, z: float, rx: float, ry: float, rz: float
) -> Tuple[float, float, float]:
    """R * v = (x, y, z) doğrusal sistemini v için çözer (3x3 Cramer)."""
    a11, a12, a13 = 1.0, -rz, ry
    a21, a22, a23 = rz, 1.0, -rx
    a31, a32, a33 = -ry, rx, 1.0
    det = (
        a11 * (a22 * a33 - a23 * a32)
        - a12 * (a21 * a33 - a23 * a31)
        + a13 * (a21 * a32 - a22 * a31)
    )
    vx = (
        x * (a22 * a33 - a23 * a32)
        - a12 * (y * a33 - a23 * z)
        + a13 * (y * a32 - a22 * z)
    ) / det
    vy = (
        a11 * (y * a33 - a23 * z)
        - x * (a21 * a33 - a23 * a31)
        + a13 * (a21 * z - y * a31)
    ) / det
    vz = (
        a11 * (a22 * z - y * a32)
        - a12 * (a21 * z - y * a31)
        + x * (a21 * a32 - a22 * a31)
    ) / det
    return vx, vy, vz


@dataclass(frozen=True)
class Datum:
    """Jeodezik datum: elipsoit + WGS84'e dönüşüm parametreleri."""

    ad: str
    elipsoit: Elipsoit
    wgs84_helmert: Helmert = field(default_factory=Helmert)
    not_: str = ""

    def cografiden_kartezyene(
        self, enlem_d: float, boylam_d: float, h: float = 0.0
    ) -> Tuple[float, float, float]:
        el = self.elipsoit
        lat = math.radians(enlem_d)
        lon = math.radians(boylam_d)
        sin_lat = math.sin(lat)
        cos_lat = math.cos(lat)
        n_egri = el.a / math.sqrt(1.0 - el.e2 * sin_lat * sin_lat)
        x = (n_egri + h) * cos_lat * math.cos(lon)
        y = (n_egri + h) * cos_lat * math.sin(lon)
        z = (n_egri * (1.0 - el.e2) + h) * sin_lat
        return x, y, z

    def kartezyenden_cografiye(
        self, x: float, y: float, z: float
    ) -> Tuple[float, float, float]:
        """Bowring'in kapalı çözümü + bir Newton düzeltmesi."""
        el = self.elipsoit
        a, b, e2, es2 = el.a, el.b, el.e2, el.es2
        lon = math.atan2(y, x)
        p = math.hypot(x, y)
        if p < 1e-12:
            lat = math.copysign(math.pi / 2.0, z)
            h = abs(z) - b
            return math.degrees(lat), math.degrees(lon), h
        theta = math.atan2(z * a, p * b)
        st, ct = math.sin(theta), math.cos(theta)
        lat = math.atan2(z + es2 * b * st * st * st, p - e2 * a * ct * ct * ct)
        for _ in range(3):
            sin_lat = math.sin(lat)
            n_egri = a / math.sqrt(1.0 - e2 * sin_lat * sin_lat)
            h = p / math.cos(lat) - n_egri
            lat_yeni = math.atan2(z, p * (1.0 - e2 * n_egri / (n_egri + h)))
            if abs(lat_yeni - lat) < 1e-14:
                lat = lat_yeni
                break
            lat = lat_yeni
        sin_lat = math.sin(lat)
        n_egri = a / math.sqrt(1.0 - e2 * sin_lat * sin_lat)
        h = p / math.cos(lat) - n_egri
        return math.degrees(lat), math.degrees(lon), h

    def wgs84e(
        self, enlem_d: float, boylam_d: float, h: float = 0.0
    ) -> Tuple[float, float, float]:
        if self.wgs84_helmert.birim_yok and self.elipsoit is WGS84:
            return enlem_d, boylam_d, h
        x, y, z = self.cografiden_kartezyene(enlem_d, boylam_d, h)
        x, y, z = self.wgs84_helmert.uygula(x, y, z)
        return DATUM_WGS84.kartezyenden_cografiye(x, y, z)

    def wgs84ten(
        self, enlem_d: float, boylam_d: float, h: float = 0.0
    ) -> Tuple[float, float, float]:
        if self.wgs84_helmert.birim_yok and self.elipsoit is WGS84:
            return enlem_d, boylam_d, h
        x, y, z = DATUM_WGS84.cografiden_kartezyene(enlem_d, boylam_d, h)
        x, y, z = self.wgs84_helmert.ters_uygula(x, y, z)
        return self.kartezyenden_cografiye(x, y, z)


DATUM_WGS84 = Datum("WGS 84", WGS84, Helmert(), "Küresel referans sistemi.")

# TUREF (ITRF96, 2005.0 epoğu) pratikte WGS84 ile birkaç desimetre
# mertebesinde örtüşür; EPSG bu ilişkiyi 1 m doğruluklu birim dönüşüm
# (null transformation) olarak tanımlar.
DATUM_ITRF96 = Datum(
    "TUREF / ITRF96 (2005.0)",
    GRS80,
    Helmert(),
    "TUREF, ITRF96 çatısında tanımlıdır. WGS84 ile farkı ~1 m'nin altındadır; "
    "EPSG birim dönüşüm önerir.",
)

# ED50 -> WGS84: EPSG "ED50 to WGS 84 (30)", Türkiye için tanımlı,
# konum vektörü yöntemi, beyan edilen doğruluk 2 m.
DATUM_ED50 = Datum(
    "European Datum 1950 (ED50)",
    HAYFORD,
    Helmert(
        dx=-84.1, dy=-101.8, dz=-129.7, rx=0.0, ry=0.0, rz=0.468, s=1.05,
        yontem="position_vector",
    ),
    "EPSG 'ED50 to WGS 84 (30)' Türkiye dönüşümü kullanılır (doğruluk ~2 m). "
    "Kuruma ait yerel dönüşüm parametreleri varsa --helmert ile verilmelidir.",
)

DATUMLAR: Dict[str, Datum] = {
    "WGS84": DATUM_WGS84,
    "ITRF96": DATUM_ITRF96,
    "TUREF": DATUM_ITRF96,
    "ED50": DATUM_ED50,
}


# ---------------------------------------------------------------------------
# Transverse Mercator (Gauss-Krüger) izdüşümü - Karney/Krüger serisi
# ---------------------------------------------------------------------------


def _alfa_katsayilari(n: float) -> List[float]:
    n2 = n * n
    n3 = n2 * n
    n4 = n3 * n
    n5 = n4 * n
    n6 = n5 * n
    return [
        (1.0 / 2.0) * n - (2.0 / 3.0) * n2 + (5.0 / 16.0) * n3
        + (41.0 / 180.0) * n4 - (127.0 / 288.0) * n5 + (7891.0 / 37800.0) * n6,
        (13.0 / 48.0) * n2 - (3.0 / 5.0) * n3 + (557.0 / 1440.0) * n4
        + (281.0 / 630.0) * n5 - (1983433.0 / 1935360.0) * n6,
        (61.0 / 240.0) * n3 - (103.0 / 140.0) * n4 + (15061.0 / 26880.0) * n5
        + (167603.0 / 181440.0) * n6,
        (49561.0 / 161280.0) * n4 - (179.0 / 168.0) * n5
        + (6601661.0 / 7257600.0) * n6,
        (34729.0 / 80640.0) * n5 - (3418889.0 / 1995840.0) * n6,
        (212378941.0 / 319334400.0) * n6,
    ]


def _beta_katsayilari(n: float) -> List[float]:
    n2 = n * n
    n3 = n2 * n
    n4 = n3 * n
    n5 = n4 * n
    n6 = n5 * n
    return [
        (1.0 / 2.0) * n - (2.0 / 3.0) * n2 + (37.0 / 96.0) * n3
        - (1.0 / 360.0) * n4 - (81.0 / 512.0) * n5 + (96199.0 / 604800.0) * n6,
        (1.0 / 48.0) * n2 + (1.0 / 15.0) * n3 - (437.0 / 1440.0) * n4
        + (46.0 / 105.0) * n5 - (1118711.0 / 3870720.0) * n6,
        (17.0 / 480.0) * n3 - (37.0 / 840.0) * n4 - (209.0 / 4480.0) * n5
        + (5569.0 / 90720.0) * n6,
        (4397.0 / 161280.0) * n4 - (11.0 / 504.0) * n5
        - (830251.0 / 7257600.0) * n6,
        (4583.0 / 161280.0) * n5 - (108847.0 / 3991680.0) * n6,
        (20648693.0 / 638668800.0) * n6,
    ]


class TransverseMercator:
    """
    Transverse Mercator (Gauss-Krüger) izdüşümü.

    Parametreler EPSG tanımlarıyla aynıdır:
    ``orta_meridyen`` (lon_0), ``olcek`` (k_0), ``sagaKaydirma`` (false
    easting / x_0), ``yukariKaydirma`` (false northing / y_0),
    ``baslangic_enlemi`` (lat_0).
    """

    def __init__(
        self,
        elipsoit: Elipsoit,
        orta_meridyen: float,
        olcek: float = 1.0,
        saga_kaydirma: float = 500000.0,
        yukari_kaydirma: float = 0.0,
        baslangic_enlemi: float = 0.0,
    ) -> None:
        self.elipsoit = elipsoit
        self.orta_meridyen = float(orta_meridyen)
        self.olcek = float(olcek)
        self.saga_kaydirma = float(saga_kaydirma)
        self.yukari_kaydirma = float(yukari_kaydirma)
        self.baslangic_enlemi = float(baslangic_enlemi)

        n = elipsoit.n
        self._n = n
        self._alfa = _alfa_katsayilari(n)
        self._beta = _beta_katsayilari(n)
        n2 = n * n
        self._A = (elipsoit.a / (1.0 + n)) * (
            1.0 + n2 / 4.0 + n2 * n2 / 64.0 + n2 * n2 * n2 / 256.0
        )
        self._e = elipsoit.e
        # Başlangıç enlemine karşılık gelen ksi (lat_0 != 0 durumları için)
        self._ksi0 = 0.0
        if self.baslangic_enlemi != 0.0:
            self._ksi0 = self._ksi_hesapla(math.radians(self.baslangic_enlemi))

    # -- yardımcılar --------------------------------------------------------

    def _tau_ustu(self, lat: float) -> float:
        """phi -> tau' (konform enlem tanjantı)."""
        tau = math.tan(lat)
        e = self._e
        sigma = math.sinh(e * math.atanh(e * tau / math.sqrt(1.0 + tau * tau)))
        return tau * math.sqrt(1.0 + sigma * sigma) - sigma * math.sqrt(
            1.0 + tau * tau
        )

    def _tau_coz(self, tau_ustu: float) -> float:
        """tau' -> tau (Newton yinelemesi, Karney 2011 denklem 21)."""
        e = self._e
        tau = tau_ustu / math.sqrt(1.0 - e * e) if abs(e) < 1.0 else tau_ustu
        for _ in range(8):
            sigma = math.sinh(e * math.atanh(e * tau / math.sqrt(1.0 + tau * tau)))
            tau_i = tau * math.sqrt(1.0 + sigma * sigma) - sigma * math.sqrt(
                1.0 + tau * tau
            )
            d_tau = (
                (tau_ustu - tau_i)
                * (1.0 + (1.0 - e * e) * tau * tau)
                / (
                    (1.0 - e * e)
                    * math.sqrt(1.0 + tau * tau)
                    * math.sqrt(1.0 + tau_i * tau_i)
                )
            )
            tau += d_tau
            if abs(d_tau) < 1e-14 * max(1.0, abs(tau)):
                break
        return tau

    def _ksi_hesapla(self, lat: float) -> float:
        tau_ustu = self._tau_ustu(lat)
        ksi_u = math.atan2(tau_ustu, 1.0)
        toplam = ksi_u
        for j, a_j in enumerate(self._alfa, start=1):
            toplam += a_j * math.sin(2.0 * j * ksi_u)
        return toplam

    # -- ileri / geri -------------------------------------------------------

    def ileri(self, enlem_d: float, boylam_d: float) -> Tuple[float, float]:
        """Enlem/boylam (derece) -> (sağa değer, yukarı değer) metre."""
        lat = math.radians(enlem_d)
        lam = math.radians(_boylam_normalize(boylam_d - self.orta_meridyen))

        tau_ustu = self._tau_ustu(lat)
        cos_lam = math.cos(lam)
        sin_lam = math.sin(lam)

        ksi_u = math.atan2(tau_ustu, cos_lam)
        payda = math.hypot(tau_ustu, cos_lam)
        eta_u = math.asinh(sin_lam / payda) if payda > 0 else 0.0

        ksi = ksi_u
        eta = eta_u
        for j, a_j in enumerate(self._alfa, start=1):
            ksi += a_j * math.sin(2.0 * j * ksi_u) * math.cosh(2.0 * j * eta_u)
            eta += a_j * math.cos(2.0 * j * ksi_u) * math.sinh(2.0 * j * eta_u)

        saga = self.olcek * self._A * eta + self.saga_kaydirma
        yukari = self.olcek * self._A * (ksi - self._ksi0) + self.yukari_kaydirma
        return saga, yukari

    def geri(self, saga: float, yukari: float) -> Tuple[float, float]:
        """(sağa değer, yukarı değer) metre -> enlem/boylam (derece)."""
        eta = (saga - self.saga_kaydirma) / (self.olcek * self._A)
        ksi = (yukari - self.yukari_kaydirma) / (self.olcek * self._A) + self._ksi0

        ksi_u = ksi
        eta_u = eta
        for j, b_j in enumerate(self._beta, start=1):
            ksi_u -= b_j * math.sin(2.0 * j * ksi) * math.cosh(2.0 * j * eta)
            eta_u -= b_j * math.cos(2.0 * j * ksi) * math.sinh(2.0 * j * eta)

        sinh_eta = math.sinh(eta_u)
        sin_ksi = math.sin(ksi_u)
        cos_ksi = math.cos(ksi_u)
        payda = math.hypot(sinh_eta, cos_ksi)
        tau_ustu = sin_ksi / payda if payda > 0 else 0.0
        tau = self._tau_coz(tau_ustu)

        lat = math.atan(tau)
        lam = math.atan2(sinh_eta, cos_ksi)
        boylam = self.orta_meridyen + math.degrees(lam)
        return math.degrees(lat), _boylam_normalize(boylam)

    # -- ek jeodezik büyüklükler -------------------------------------------

    def olcek_faktoru(self, enlem_d: float, boylam_d: float) -> float:
        """Noktasal ölçek faktörü (sayısal türevle)."""
        d = 1e-6  # derece (~0.11 m)
        x0, y0 = self.ileri(enlem_d, boylam_d)
        x1, y1 = self.ileri(enlem_d + d, boylam_d)
        izdusum_mesafe = math.hypot(x1 - x0, y1 - y0)
        gercek_mesafe = elipsoidal_mesafe(
            enlem_d, boylam_d, enlem_d + d, boylam_d, self.elipsoit
        )
        if gercek_mesafe == 0:
            return self.olcek
        return izdusum_mesafe / gercek_mesafe

    def meridyen_yakinsamasi(self, enlem_d: float, boylam_d: float) -> float:
        """
        Meridyen yakınsaması (grid convergence), derece.

        Ölçme uygulamasındaki alışılmış tanım kullanılır:
        ``grid semti = coğrafi semt - yakınsama``. Buna göre orta
        meridyenin **doğusunda pozitif**, batısında negatiftir ve
        yaklaşık değeri ``(boylam - orta meridyen) x sin(enlem)`` kadardır.

        Sayısal türevle hesaplanır: nokta kuzeye doğru çok küçük bir
        miktar kaydırılır, izdüşümdeki yer değiştirmenin grid semti
        bulunur. Bu semt coğrafi kuzeyin grid üzerindeki yönü olduğundan,
        yukarıdaki tanıma uyması için işareti ters çevrilir.
        """
        d = 1e-6
        x0, y0 = self.ileri(enlem_d, boylam_d)
        x1, y1 = self.ileri(enlem_d + d, boylam_d)
        return -math.degrees(math.atan2(x1 - x0, y1 - y0))


def _boylam_normalize(boylam: float) -> float:
    while boylam > 180.0:
        boylam -= 360.0
    while boylam < -180.0:
        boylam += 360.0
    return boylam


# ---------------------------------------------------------------------------
# Koordinat sistemi (datum + izdüşüm) ve Türkiye kataloğu
# ---------------------------------------------------------------------------


class KoordinatSistemi:
    """Datum ve izdüşümü birlikte tutan, WGS84 ile gidip gelen sarmalayıcı."""

    def __init__(
        self,
        kod: str,
        ad: str,
        datum: Datum,
        projeksiyon: Optional[TransverseMercator],
        epsg: Optional[int] = None,
        dilim: Optional[int] = None,
        birim: str = "m",
    ) -> None:
        self.kod = kod
        self.ad = ad
        self.datum = datum
        self.projeksiyon = projeksiyon
        self.epsg = epsg
        self.dilim = dilim
        self.birim = birim

    @property
    def cografi(self) -> bool:
        return self.projeksiyon is None

    def wgs84ten(
        self, enlem_d: float, boylam_d: float, h: float = 0.0
    ) -> Tuple[float, float]:
        """WGS84 enlem/boylam -> bu sistemin koordinatları."""
        lat, lon, _ = self.datum.wgs84ten(enlem_d, boylam_d, h)
        if self.projeksiyon is None:
            return lon, lat  # coğrafi çıktıda (boylam, enlem) sırası
        return self.projeksiyon.ileri(lat, lon)

    def wgs84e(self, birinci: float, ikinci: float, h: float = 0.0) -> Tuple[float, float]:
        """Bu sistemin koordinatları -> WGS84 (enlem, boylam)."""
        if self.projeksiyon is None:
            lat, lon = ikinci, birinci
        else:
            lat, lon = self.projeksiyon.geri(birinci, ikinci)
        lat, lon, _ = self.datum.wgs84e(lat, lon, h)
        return lat, lon

    def tanim(self) -> str:
        parcalar = [self.ad]
        if self.epsg:
            parcalar.append(f"EPSG:{self.epsg}")
        if self.projeksiyon is not None:
            parcalar.append(
                f"OM={self.projeksiyon.orta_meridyen:g}°, k0={self.projeksiyon.olcek:g}, "
                f"sağa kaydırma={self.projeksiyon.saga_kaydirma:g} m"
            )
        return " | ".join(parcalar)

    def __repr__(self) -> str:  # pragma: no cover - hata ayıklama kolaylığı
        return f"<KoordinatSistemi {self.kod}: {self.ad}>"


# Türkiye 3 derecelik dilim orta meridyenleri ve dilim numaraları
UC_DERECE_DILIMLER: Dict[int, int] = {9: 27, 10: 30, 11: 33, 12: 36, 13: 39, 14: 42, 15: 45}

# EPSG kodları (pyproj/EPSG kayıt defteriyle doğrulanmıştır)
_EPSG_TUREF_TM = {27: 5253, 30: 5254, 33: 5255, 36: 5256, 39: 5257, 42: 5258, 45: 5259}
_EPSG_TUREF_GK = {9: 5269, 10: 5270, 11: 5271, 12: 5272, 13: 5273, 14: 5274, 15: 5275}
_EPSG_ED50_TM = {27: 2319, 30: 2320, 33: 2321, 36: 2322, 39: 2323, 42: 2324, 45: 2325}
_EPSG_ED50_GK = {9: 2206, 10: 2207, 11: 2208, 12: 2209, 13: 2210, 14: 2211, 15: 2212}
_EPSG_ED50_UTM = {35: 23035, 36: 23036, 37: 23037, 38: 23038}
_EPSG_WGS84_UTM = {35: 32635, 36: 32636, 37: 32637, 38: 32638}


def dilim_orta_meridyeni(dilim: int) -> int:
    """3 derecelik dilim numarasından (9-15) orta meridyeni verir."""
    if dilim not in UC_DERECE_DILIMLER:
        raise ValueError(
            f"Geçersiz dilim numarası: {dilim}. Türkiye için geçerli dilimler: "
            f"{', '.join(str(k) for k in UC_DERECE_DILIMLER)}"
        )
    return UC_DERECE_DILIMLER[dilim]


def uygun_dilim(boylam: float, genislik: int = 3) -> int:
    """
    Verilen boylam için uygun dilimi verir.

    ``genislik=3`` -> Türkiye 3 derecelik dilim numarası (9-15)
    ``genislik=6`` -> UTM dilim numarası (1-60)
    """
    if genislik == 6:
        return int(math.floor((_boylam_normalize(boylam) + 180.0) / 6.0)) + 1
    om = int(round(_boylam_normalize(boylam) / 3.0) * 3)
    om = max(27, min(45, om))
    for dilim, orta in UC_DERECE_DILIMLER.items():
        if orta == om:
            return dilim
    raise ValueError(f"{boylam}° boylamı için 3 derecelik dilim bulunamadı.")


def _tm_sistem(
    kod: str,
    ad: str,
    datum: Datum,
    orta_meridyen: float,
    saga_kaydirma: float,
    epsg: Optional[int],
    dilim: Optional[int],
    olcek: float = 1.0,
) -> KoordinatSistemi:
    return KoordinatSistemi(
        kod,
        ad,
        datum,
        TransverseMercator(
            datum.elipsoit,
            orta_meridyen=orta_meridyen,
            olcek=olcek,
            saga_kaydirma=saga_kaydirma,
        ),
        epsg=epsg,
        dilim=dilim,
    )


def sistem_listesi() -> List[KoordinatSistemi]:
    """Katalogdaki tüm hazır koordinat sistemleri."""
    liste: List[KoordinatSistemi] = [
        KoordinatSistemi("WGS84", "WGS 84 coğrafi (enlem/boylam)", DATUM_WGS84, None, 4326, None, "derece"),
    ]
    for dilim, om in UC_DERECE_DILIMLER.items():
        liste.append(
            _tm_sistem(
                f"ITRF96-TM{om}",
                f"TUREF / ITRF96 3° dilim TM{om} (dilim {dilim})",
                DATUM_ITRF96,
                om,
                500000.0,
                _EPSG_TUREF_TM[om],
                dilim,
            )
        )
    for dilim, om in UC_DERECE_DILIMLER.items():
        liste.append(
            _tm_sistem(
                f"ITRF96-GK{dilim}",
                f"TUREF / ITRF96 3° dilim {dilim} (dilim numarası önekli sağa değer)",
                DATUM_ITRF96,
                om,
                dilim * 1000000.0 + 500000.0,
                _EPSG_TUREF_GK[dilim],
                dilim,
            )
        )
    for dilim, om in UC_DERECE_DILIMLER.items():
        liste.append(
            _tm_sistem(
                f"ED50-TM{om}",
                f"ED50 3° dilim TM{om} (dilim {dilim})",
                DATUM_ED50,
                om,
                500000.0,
                _EPSG_ED50_TM[om],
                dilim,
            )
        )
    for dilim, om in UC_DERECE_DILIMLER.items():
        liste.append(
            _tm_sistem(
                f"ED50-GK{dilim}",
                f"ED50 3° dilim {dilim} (dilim numarası önekli sağa değer)",
                DATUM_ED50,
                om,
                dilim * 1000000.0 + 500000.0,
                _EPSG_ED50_GK[dilim],
                dilim,
            )
        )
    for utm_dilim in (35, 36, 37, 38):
        om = utm_dilim * 6 - 183
        liste.append(
            _tm_sistem(
                f"ED50-UTM{utm_dilim}N",
                f"ED50 / UTM 6° dilim {utm_dilim}N",
                DATUM_ED50,
                om,
                500000.0,
                _EPSG_ED50_UTM[utm_dilim],
                utm_dilim,
                olcek=0.9996,
            )
        )
        liste.append(
            _tm_sistem(
                f"WGS84-UTM{utm_dilim}N",
                f"WGS 84 / UTM 6° dilim {utm_dilim}N",
                DATUM_WGS84,
                om,
                500000.0,
                _EPSG_WGS84_UTM[utm_dilim],
                utm_dilim,
                olcek=0.9996,
            )
        )
    return liste


_KATALOG: Optional[Dict[str, KoordinatSistemi]] = None


def _katalog() -> Dict[str, KoordinatSistemi]:
    global _KATALOG
    if _KATALOG is None:
        _KATALOG = {}
        for s in sistem_listesi():
            _KATALOG[s.kod.upper()] = s
            if s.epsg:
                _KATALOG[f"EPSG:{s.epsg}"] = s
                _KATALOG[str(s.epsg)] = s
    return _KATALOG


_EPSG_DESEN = re.compile(r"^(?:EPSG:)?(\d{4,6})$", re.IGNORECASE)


def sistem_bul(ad: str) -> KoordinatSistemi:
    """
    Kod, ad veya EPSG numarasından koordinat sistemi çözer.

    Örnekler: ``ITRF96-TM30``, ``EPSG:5254``, ``5254``, ``ED50-UTM35N``,
    ``WGS84``, ``ITRF96-GK10``.
    """
    if not ad:
        raise ValueError("Koordinat sistemi belirtilmedi.")
    anahtar = ad.strip().upper().replace(" ", "")
    katalog = _katalog()
    if anahtar in katalog:
        return katalog[anahtar]
    # TUREF eşanlamlısı
    esanlam = anahtar.replace("TUREF", "ITRF96")
    if esanlam in katalog:
        return katalog[esanlam]
    m = _EPSG_DESEN.match(anahtar)
    if m:
        raise ValueError(
            f"EPSG:{m.group(1)} katalogda tanımlı değil. "
            f"Tanımlı sistemler için 'python -m karelaj sistemler' komutunu çalıştırın."
        )
    raise ValueError(
        f"Bilinmeyen koordinat sistemi: {ad!r}. "
        f"Tanımlı sistemler için 'python -m karelaj sistemler' komutunu çalıştırın."
    )


def otomatik_sistem(boylam: float, aile: str = "ITRF96") -> KoordinatSistemi:
    """
    Alanın orta boylamına göre uygun 3 derecelik dilimi seçer.

    ``aile``: ``ITRF96`` (varsayılan), ``ITRF96-GK``, ``ED50``, ``ED50-GK``,
    ``UTM`` (WGS84 UTM) veya ``ED50-UTM``.
    """
    aile_u = aile.strip().upper()
    if aile_u in ("UTM", "WGS84-UTM"):
        return sistem_bul(f"WGS84-UTM{uygun_dilim(boylam, 6)}N")
    if aile_u == "ED50-UTM":
        return sistem_bul(f"ED50-UTM{uygun_dilim(boylam, 6)}N")
    dilim = uygun_dilim(boylam, 3)
    om = dilim_orta_meridyeni(dilim)
    if aile_u in ("ITRF96", "TUREF"):
        return sistem_bul(f"ITRF96-TM{om}")
    if aile_u in ("ITRF96-GK", "TUREF-GK"):
        return sistem_bul(f"ITRF96-GK{dilim}")
    if aile_u == "ED50":
        return sistem_bul(f"ED50-TM{om}")
    if aile_u == "ED50-GK":
        return sistem_bul(f"ED50-GK{dilim}")
    raise ValueError(f"Bilinmeyen sistem ailesi: {aile!r}")


# ---------------------------------------------------------------------------
# Elipsoit üzerinde mesafe ve alan
# ---------------------------------------------------------------------------


def elipsoidal_mesafe(
    enlem1: float,
    boylam1: float,
    enlem2: float,
    boylam2: float,
    elipsoit: Elipsoit = GRS80,
) -> float:
    """
    İki nokta arasındaki jeodezik mesafe (m). Vincenty ters problemi;
    yakınsamazsa büyük daire yaklaşımına düşer.
    """
    a = elipsoit.a
    b = elipsoit.b
    f = elipsoit.f
    L = math.radians(_boylam_normalize(boylam2 - boylam1))
    U1 = math.atan((1 - f) * math.tan(math.radians(enlem1)))
    U2 = math.atan((1 - f) * math.tan(math.radians(enlem2)))
    sinU1, cosU1 = math.sin(U1), math.cos(U1)
    sinU2, cosU2 = math.sin(U2), math.cos(U2)
    lam = L
    for _ in range(200):
        sin_lam, cos_lam = math.sin(lam), math.cos(lam)
        sin_sigma = math.sqrt(
            (cosU2 * sin_lam) ** 2 + (cosU1 * sinU2 - sinU1 * cosU2 * cos_lam) ** 2
        )
        if sin_sigma == 0:
            return 0.0
        cos_sigma = sinU1 * sinU2 + cosU1 * cosU2 * cos_lam
        sigma = math.atan2(sin_sigma, cos_sigma)
        sin_alfa = cosU1 * cosU2 * sin_lam / sin_sigma
        cos2_alfa = 1 - sin_alfa * sin_alfa
        cos2_sigma_m = (
            cos_sigma - 2 * sinU1 * sinU2 / cos2_alfa if cos2_alfa != 0 else 0.0
        )
        C = f / 16 * cos2_alfa * (4 + f * (4 - 3 * cos2_alfa))
        lam_onceki = lam
        lam = L + (1 - C) * f * sin_alfa * (
            sigma
            + C
            * sin_sigma
            * (cos2_sigma_m + C * cos_sigma * (-1 + 2 * cos2_sigma_m ** 2))
        )
        if abs(lam - lam_onceki) < 1e-12:
            break
    else:  # yakınsamadı (neredeyse karşıt noktalar)
        return _kuresel_mesafe(enlem1, boylam1, enlem2, boylam2, a)
    u2 = cos2_alfa * (a * a - b * b) / (b * b)
    A = 1 + u2 / 16384 * (4096 + u2 * (-768 + u2 * (320 - 175 * u2)))
    B = u2 / 1024 * (256 + u2 * (-128 + u2 * (74 - 47 * u2)))
    d_sigma = (
        B
        * sin_sigma
        * (
            cos2_sigma_m
            + B
            / 4
            * (
                cos_sigma * (-1 + 2 * cos2_sigma_m ** 2)
                - B
                / 6
                * cos2_sigma_m
                * (-3 + 4 * sin_sigma ** 2)
                * (-3 + 4 * cos2_sigma_m ** 2)
            )
        )
    )
    return b * A * (sigma - d_sigma)


def _kuresel_mesafe(
    enlem1: float, boylam1: float, enlem2: float, boylam2: float, r: float
) -> float:
    p1, p2 = math.radians(enlem1), math.radians(enlem2)
    dl = math.radians(_boylam_normalize(boylam2 - boylam1))
    return r * math.acos(
        max(-1.0, min(1.0, math.sin(p1) * math.sin(p2) + math.cos(p1) * math.cos(p2) * math.cos(dl)))
    )


def poligon_alani_elipsoidal(
    kose_noktalari: Sequence[Tuple[float, float]], elipsoit: Elipsoit = GRS80
) -> float:
    """
    Elipsoit üzerinde poligon alanı (m²). Girdi (boylam, enlem) çiftleridir.

    Yetkin (2011) / Chamberlain-Duquette yaklaşımıyla küresel fazla üzerinden
    hesaplanır; birkaç km ölçeğinde binde bir altında hata verir.
    """
    n = len(kose_noktalari)
    if n < 3:
        return 0.0
    # Otalik (authalic) yarıçap
    a, b, e = elipsoit.a, elipsoit.b, elipsoit.e
    if e > 0:
        r2 = 0.5 * a * a * (1.0 + ((1.0 - e * e) / e) * math.atanh(e))
    else:
        r2 = a * a
    r = math.sqrt(r2)
    toplam = 0.0
    for i in range(n):
        lon1, lat1 = kose_noktalari[i]
        lon2, lat2 = kose_noktalari[(i + 1) % n]
        dlon = math.radians(_boylam_normalize(lon2 - lon1))
        toplam += dlon * (2.0 + math.sin(math.radians(lat1)) + math.sin(math.radians(lat2)))
    return abs(toplam * r * r / 2.0)
