# -*- coding: utf-8 -*-
"""
Komut satırı arayüzü
====================

``python -m karelaj <komut>`` biçiminde çalışır. Komutlar:

``uret``       Karelaj üret ve dosyaları yaz (varsayılan komut)
``sistemler``  Tanımlı koordinat sistemlerini listele
``kaynaklar``  Kot kaynaklarını ve veri kümelerini listele
``donustur``   Tek nokta koordinat dönüşümü
``onbellek``   Kot önbelleğini görüntüle / temizle
``arayuz``     Tarayıcıda harita üzerinden alan seçme arayüzünü başlat
"""

from __future__ import annotations

import argparse
import errno
import io
import os
import shlex
import sys
import time
from typing import List, Optional, Sequence

from . import bicim
from .geodezi import (
    UC_DERECE_DILIMLER,
    dilim_orta_meridyeni,
    otomatik_sistem,
    sistem_bul,
    sistem_listesi,
)
from .geometri import Alan, alan_oku, alan_sinir_kutusundan
from .hacim import hacim_hesapla
from .izgara import (
    KarelajAyari,
    NumaralandirmaAyari,
    karelaj_uret,
    nokta_sayisi_tahmini,
)
from .kaynaklar import (
    KAYNAK_ADLARI,
    OPENTOPODATA_VERI_KUMELERI,
    KaynakHatasi,
    kaynak_olustur,
    kotlari_doldur,
)
from .kontur import kontur_uret
from .onbellek import KotOnbellegi, varsayilan_onbellek_yolu
from .yazicilar import (
    AYIRACLAR,
    NCN_PROFILLERI,
    SUTUN_BASLIKLARI,
    csv_yaz,
    dxf_yaz,
    geojson_yaz,
    kml_yaz,
    ncn_yaz,
    profil_coz,
    rapor_yaz,
    xyz_yaz,
)

BICIMLER = ("ncn", "csv", "xyz", "dxf", "kml", "geojson", "rapor")
VARSAYILAN_BICIMLER = "ncn,kml,rapor"


_penceresiz: Optional[bool] = None


def penceresiz_durumunu_sabitle() -> bool:
    """
    Konsolsuz çalışıp çalışmadığımızı saptar ve saklar.

    Bu saptama, çıktı akışları değiştirilmeden **önce** yapılmak
    zorundadır: pencere kipinin tek belirtisi ``sys.stdout`` ve
    ``sys.stderr`` değerlerinin ``None`` olmasıdır ve bu akışlar hemen
    ardından günlük dosyasıyla değiştirildiğinde belirti kaybolur.
    ``main`` her çağrıldığında yeniden saptanır.
    """
    global _penceresiz
    _penceresiz = sys.stdout is None or sys.stderr is None
    return _penceresiz


def penceresiz_mi() -> bool:
    """
    Uygulama konsolsuz (pencere kipinde) mi çalışıyor?

    Akışlar **şu anda** boşsa kesinlikle pencere kipindeyiz. Değilse,
    ``penceresiz_durumunu_sabitle`` ile önceden saptanmış değer geçerlidir:
    pencere kipinde akışlar günlük dosyasıyla değiştirildiği için sonradan
    bakıldığında boş görünmezler.
    """
    if sys.stdout is None or sys.stderr is None:
        return True
    if _penceresiz is not None:
        return _penceresiz
    return False


def gunluk_dosyasi_yolu() -> str:
    """Penceresiz çalışmada ekran çıktısının yazılacağı günlük dosyası."""
    klasor = varsayilan_cikti_klasoru()
    if not os.path.isabs(klasor):
        klasor = os.path.abspath(klasor)
    return os.path.join(klasor, "kot-karelaji-gunluk.txt")


def cikti_akislarini_hazirla() -> Optional[str]:
    """
    Konsolsuz çalışmada ``stdout``/``stderr`` yerine günlük dosyası açar.

    Pencere kipinde bu akışlar ``None`` olduğundan her ``print`` çağrısı
    hata verir. Çıktı bir dosyaya yönlendirilerek hem çökme önlenir hem de
    bir sorun çıktığında kullanıcıya gösterilecek bir kayıt kalır.

    Günlük dosyasının yolunu, açılabildiyse döndürür.
    """
    if not penceresiz_mi():
        return None
    try:
        yol = gunluk_dosyasi_yolu()
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        dosya = open(yol, "a", encoding="utf-8", errors="replace", buffering=1)
        dosya.write(f"\n{'=' * 60}\n{time.strftime('%d.%m.%Y %H:%M:%S')} - başlatıldı\n")
        sys.stdout = dosya
        sys.stderr = dosya
        return yol
    except OSError:
        # Günlük açılamazsa da program çalışmaya devam etmeli
        bos = open(os.devnull, "w", encoding="utf-8")
        sys.stdout = bos
        sys.stderr = bos
        return None


def cikti_kodlamasini_ayarla() -> None:
    """
    Ekran çıktısının Türkçe karakterlerde çökmemesini sağlar.

    Windows'ta çıktı bir konsola değil de dosyaya ya da boruya (pipe)
    yönlendirildiğinde Python, sistemin yerel kod sayfasını kullanır.
    Türkçe olmayan bir kod sayfasında (örn. cp1252) ``ğ``, ``ş``, ``İ``
    gibi harfler kodlanamaz ve ``UnicodeEncodeError`` yükselir. Bu hata
    ``ValueError`` alt sınıfı olduğundan sessizce "kullanım hatası" gibi
    görünür.

    Akışlar UTF-8'e ve ``replace`` hata davranışına ayarlanarak bu
    tamamen önlenir. Windows konsolu zaten UTF-8 ile çalıştığı için
    konsol çıktısında bir değişiklik olmaz.
    """
    for akis in (sys.stdout, sys.stderr):
        if akis is None:
            continue
        try:
            akis.reconfigure(encoding="utf-8", errors="replace")
            continue
        except (AttributeError, ValueError, OSError):
            pass
        # reconfigure yoksa akışı yeniden sarmalamayı dene
        try:
            tampon = getattr(akis, "buffer", None)
            if tampon is None:
                continue
            sarmal = io.TextIOWrapper(
                tampon, encoding="utf-8", errors="replace", line_buffering=True
            )
            if akis is sys.stdout:
                sys.stdout = sarmal
            else:
                sys.stderr = sarmal
        except (AttributeError, ValueError, OSError):
            pass


def paketlenmis_mi() -> bool:
    """Program, PyInstaller ile tek dosyalık bir uygulama olarak mı çalışıyor?"""
    return bool(getattr(sys, "frozen", False))


def varsayilan_cikti_klasoru() -> str:
    """
    Çıktıların yazılacağı varsayılan klasör.

    Kaynak koddan çalışırken bulunulan klasörün altındaki ``cikti``
    kullanılır. Paketlenmiş uygulamada ise program Masaüstünden ya da
    Program Files içinden çalıştırılabileceği için, kullanıcının
    Belgeler klasörü altında sabit ve yazılabilir bir yer seçilir.
    """
    if not paketlenmis_mi():
        return "cikti"
    ev = os.path.expanduser("~")
    for ad in ("Documents", "Belgeler"):
        aday = os.path.join(ev, ad)
        if os.path.isdir(aday):
            return os.path.join(aday, "Kot Karelaji")
    return os.path.join(ev, "Kot Karelaji")


class KullanimHatasi(Exception):
    """Kullanıcı girdisi hatalı olduğunda."""


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------


def _yaz(ileti: str, sessiz: bool = False, akis=None) -> None:
    if not sessiz:
        print(ileti, file=akis or sys.stderr)


class _Ilerleme:
    """Tek satırlık ilerleme göstergesi."""

    def __init__(self, sessiz: bool = False) -> None:
        self.sessiz = sessiz
        self._son = 0.0
        self._yazildi = False

    def __call__(self, tamamlanan: int, toplam: int, ileti: str) -> None:
        if self.sessiz or not toplam:
            return
        simdi = time.time()
        bitti = tamamlanan >= toplam
        if not bitti and simdi - self._son < 0.2:
            return
        self._son = simdi
        oran = min(1.0, tamamlanan / toplam)
        dolu = int(oran * 28)
        cubuk = "#" * dolu + "-" * (28 - dolu)
        sys.stderr.write(
            f"\r  Kot okunuyor [{cubuk}] %{oran * 100:5.1f} "
            f"({bicim.tam_sayi(min(tamamlanan, toplam))}/{bicim.tam_sayi(toplam)}) {ileti[:24]:<24}"
        )
        sys.stderr.flush()
        self._yazildi = True
        if bitti:
            sys.stderr.write("\n")
            sys.stderr.flush()

    def bitir(self) -> None:
        if self._yazildi and not self.sessiz:
            sys.stderr.write("\n")
            sys.stderr.flush()
            self._yazildi = False


def _sinir_ayristir(metin: str) -> Alan:
    parcalar = [p.strip() for p in metin.replace(";", ",").split(",") if p.strip()]
    if len(parcalar) != 4:
        raise KullanimHatasi(
            "--sinir dört değer bekler: enlem1,boylam1,enlem2,boylam2 "
            "(güneybatı ve kuzeydoğu köşeleri). Örnek: "
            "--sinir 40.7530,29.9301,40.7602,29.9443"
        )
    try:
        sayilar = [float(p.replace(",", ".")) for p in parcalar]
    except ValueError as hata:
        raise KullanimHatasi(f"--sinir değerleri sayı olmalıdır: {metin!r}") from hata
    enlem1, boylam1, enlem2, boylam2 = sayilar
    for enlem in (enlem1, enlem2):
        if not -90.0 <= enlem <= 90.0:
            raise KullanimHatasi(f"Enlem -90 ile +90 arasında olmalıdır: {enlem}")
    for boylam in (boylam1, boylam2):
        if not -180.0 <= boylam <= 180.0:
            raise KullanimHatasi(f"Boylam -180 ile +180 arasında olmalıdır: {boylam}")
    if enlem1 == enlem2 or boylam1 == boylam2:
        raise KullanimHatasi(
            "--sinir ile verilen köşeler bir alan oluşturmuyor "
            "(enlem veya boylam değerleri aynı)."
        )
    return alan_sinir_kutusundan(enlem1, boylam1, enlem2, boylam2)


def _alani_coz(secenekler) -> Alan:
    if secenekler.alan and secenekler.sinir:
        raise KullanimHatasi("--alan ve --sinir birlikte kullanılamaz.")
    if secenekler.alan:
        kaynak_sistem = (
            sistem_bul(secenekler.sinir_sistemi) if secenekler.sinir_sistemi else None
        )
        return alan_oku(
            secenekler.alan,
            kaynak_sistem=kaynak_sistem,
            katman=secenekler.alan_katman,
            metin_sirasi=secenekler.metin_sirasi,
            ncn_duzen=secenekler.sinir_ncn_duzen,
        )
    if secenekler.sinir:
        return _sinir_ayristir(secenekler.sinir)
    raise KullanimHatasi(
        "Çalışma alanı belirtilmedi. --sinir ile köşe koordinatlarını veya "
        "--alan ile bir poligon dosyası (GeoJSON/KML/KMZ/WKT/CSV/NCN) verin."
    )


def _sistemi_coz(secenekler, alan: Alan):
    if secenekler.dilim:
        if secenekler.dilim not in UC_DERECE_DILIMLER:
            raise KullanimHatasi(
                f"Geçersiz dilim: {secenekler.dilim}. Türkiye için 9-15 arası "
                f"olmalıdır (27°-45° orta meridyenler)."
            )
        aile = (secenekler.sistem or "ITRF96").upper()
        om = dilim_orta_meridyeni(secenekler.dilim)
        kod = {
            "ITRF96": f"ITRF96-TM{om}",
            "TUREF": f"ITRF96-TM{om}",
            "ITRF96-GK": f"ITRF96-GK{secenekler.dilim}",
            "ED50": f"ED50-TM{om}",
            "ED50-GK": f"ED50-GK{secenekler.dilim}",
        }.get(aile)
        if not kod:
            raise KullanimHatasi(
                f"--dilim ile birlikte --sistem yalnızca sistem ailesi olabilir: "
                f"ITRF96, ITRF96-GK, ED50, ED50-GK"
            )
        return sistem_bul(kod)
    if not secenekler.sistem or secenekler.sistem.lower() in ("otomatik", "auto"):
        merkez_boylam, _ = alan.merkez()
        return otomatik_sistem(merkez_boylam, "ITRF96")
    if secenekler.sistem.upper() in ("ITRF96", "TUREF", "ED50", "ITRF96-GK", "ED50-GK", "UTM", "ED50-UTM"):
        merkez_boylam, _ = alan.merkez()
        return otomatik_sistem(merkez_boylam, secenekler.sistem)
    return sistem_bul(secenekler.sistem)


def _bicimleri_coz(metin: str) -> List[str]:
    if metin.strip().lower() in ("hepsi", "tumu", "all"):
        return list(BICIMLER)
    secilen = [p.strip().lower() for p in metin.split(",") if p.strip()]
    bilinmeyen = [b for b in secilen if b not in BICIMLER]
    if bilinmeyen:
        raise KullanimHatasi(
            f"Bilinmeyen çıktı biçimi: {', '.join(bilinmeyen)}. "
            f"Seçenekler: {', '.join(BICIMLER)} (veya 'hepsi')"
        )
    if not secilen:
        raise KullanimHatasi("En az bir çıktı biçimi seçilmelidir.")
    return secilen


def _dosya_adi(secenekler, alan: Alan) -> str:
    if secenekler.ad:
        return secenekler.ad
    if alan.kaynak and alan.kaynak != "sınır kutusu":
        return os.path.splitext(os.path.basename(alan.kaynak))[0]
    return "karelaj"


# ---------------------------------------------------------------------------
# uret komutu
# ---------------------------------------------------------------------------


def komut_uret(secenekler) -> int:
    sessiz = secenekler.sessiz
    alan = _alani_coz(secenekler)
    sistem = _sistemi_coz(secenekler, alan)

    _yaz(f"Çalışma alanı : {alan.ozet()}", sessiz)
    _yaz(f"Koordinat sis.: {sistem.tanim()}", sessiz)

    numaralandirma = NumaralandirmaAyari(
        profil=secenekler.no_profil,
        onek=secenekler.no_onek,
        baslangic=secenekler.no_baslangic,
        basamak=secenekler.no_basamak,
        ayirac=secenekler.no_ayirac,
    )
    ayar = KarelajAyari(
        aralik=secenekler.aralik,
        aralik_yukari=secenekler.aralik_yukari,
        hizalama=secenekler.hizalama,
        donme_acisi=secenekler.donme,
        kirp=not secenekler.kirpma_yok,
        tampon=secenekler.tampon,
        kenar_noktalari=secenekler.kose_noktalari,
        siralama=secenekler.siralama,
        numaralandirma=numaralandirma,
        nokta_kodu=secenekler.kod,
        azami_nokta=secenekler.azami_nokta,
    )

    tahmin = nokta_sayisi_tahmini(alan, sistem, ayar)
    _yaz(
        f"Karelaj       : {bicim.sayi(ayar.aralik, 2)} m aralık, "
        f"yaklaşık {bicim.tam_sayi(tahmin)} nokta (kırpma öncesi)",
        sessiz,
    )

    karelaj = karelaj_uret(alan, sistem, ayar)
    _yaz(
        f"Üretilen      : {bicim.tam_sayi(len(karelaj.noktalar))} nokta "
        f"({karelaj.satir_sayisi} satır x {karelaj.sutun_sayisi} sütun)",
        sessiz,
    )

    kaynak_ozeti = None
    if not secenekler.kot_yok:
        kaynak_ozeti = _kotlari_oku(secenekler, karelaj, sessiz)

    konturlar = None
    if secenekler.kontur:
        konturlar = kontur_uret(karelaj, aralik=secenekler.kontur, temel=secenekler.kontur_temel)
        _yaz(
            f"Eş yükselti   : {bicim.sayi(secenekler.kontur, 2)} m aralıkla "
            f"{bicim.tam_sayi(len(konturlar))} eğri parçası",
            sessiz,
        )

    hacim = None
    if secenekler.hacim_kotu is not None:
        hacim = hacim_hesapla(karelaj, secenekler.hacim_kotu, secenekler.hacim_alt_bolme)
        _yaz(
            f"Hacim         : kazı {bicim.hacim_metni(hacim.kazi_m3)}, "
            f"dolgu {bicim.hacim_metni(hacim.dolgu_m3)}",
            sessiz,
        )

    dosyalar = _dosyalari_yaz(secenekler, karelaj, konturlar, sessiz)

    if "rapor" in _bicimleri_coz(secenekler.bicim):
        temel = _dosya_adi(secenekler, alan)
        rapor_yolu = os.path.join(secenekler.cikti, f"{temel}-rapor.txt")
        rapor_yaz(
            rapor_yolu,
            karelaj,
            kaynak_ozeti=kaynak_ozeti,
            hacim=hacim,
            konturlar=konturlar,
            uretilen_dosyalar=dosyalar,
            kot_kaydirma=secenekler.kot_kaydirma,
            komut=_komut_metni(),
        )
        dosyalar.append(rapor_yolu)
        _yaz(f"  {os.path.basename(rapor_yolu)}", sessiz)

    _yaz("", sessiz)
    _yaz(
        f"Tamamlandı. {bicim.tam_sayi(len(dosyalar))} dosya '{secenekler.cikti}' "
        f"klasörüne yazıldı.",
        sessiz,
    )
    eksik = karelaj.eksik_kot_sayisi()
    if eksik:
        _yaz(
            f"UYARI: {bicim.tam_sayi(eksik)} noktanın kotu okunamadı. "
            f"Kaynağın kapsama alanını denetleyin.",
            sessiz,
        )
    return 0


def _kotlari_oku(secenekler, karelaj, sessiz: bool):
    sym_sistemi = sistem_bul(secenekler.dem_sistemi) if secenekler.dem_sistemi else None
    try:
        kaynak = kaynak_olustur(
            secenekler.kaynak,
            veri_kumesi=secenekler.veri_kumesi,
            sunucu=secenekler.sunucu,
            sym_yolu=secenekler.sym,
            sym_sistemi=sym_sistemi,
            ornekleme=secenekler.ornekleme,
            google_anahtari=secenekler.google_anahtar,
            toplu_boyut=secenekler.toplu,
            zaman_asimi=secenekler.zaman_asimi,
            yeniden_deneme=secenekler.yeniden_deneme,
            istek_araligi=secenekler.istek_araligi,
        )
    except KaynakHatasi as hata:
        raise KullanimHatasi(str(hata)) from hata

    _yaz(f"Kot kaynağı   : {kaynak.tanim()}", sessiz)
    if kaynak.cevrimici:
        istek = (len(karelaj.noktalar) + kaynak.toplu_boyut - 1) // kaynak.toplu_boyut
        _yaz(
            f"                {bicim.tam_sayi(istek)} istek gerekecek "
            f"(istek başına {bicim.tam_sayi(kaynak.toplu_boyut)} nokta)",
            sessiz,
        )

    onbellek = KotOnbellegi(
        secenekler.onbellek or varsayilan_onbellek_yolu(),
        etkin=not secenekler.onbellek_yok,
    )
    ilerleme = _Ilerleme(sessiz)
    try:
        ozet = kotlari_doldur(
            karelaj.noktalar,
            kaynak,
            onbellek=onbellek,
            ilerleme=ilerleme,
            kot_kaydirma=secenekler.kot_kaydirma,
        )
    finally:
        ilerleme.bitir()
        onbellek.kapat()
        kaynak.kapat()

    _yaz(f"Kot okuma     : {ozet.ozet_satiri()}", sessiz)
    for uyari in ozet.uyarilar:
        _yaz(f"  ! {uyari}", sessiz)
    istatistik = karelaj.kot_istatistikleri()
    if istatistik:
        _yaz(
            f"Kot aralığı   : {bicim.sayi(istatistik['en_dusuk'], 2)} m - "
            f"{bicim.sayi(istatistik['en_yuksek'], 2)} m "
            f"(fark {bicim.sayi(istatistik['yukseklik_farki'], 2)} m)",
            sessiz,
        )
    return ozet


def _dosyalari_yaz(secenekler, karelaj, konturlar, sessiz: bool) -> List[str]:
    bicimler = _bicimleri_coz(secenekler.bicim)
    temel = _dosya_adi(secenekler, karelaj.alan)
    os.makedirs(secenekler.cikti, exist_ok=True)
    dosyalar: List[str] = []
    _yaz("", sessiz)
    _yaz("Yazılan dosyalar:", sessiz)

    if "ncn" in bicimler:
        # Kot okunmadıysa varsayılan "kotsuz noktayı atla" davranışı dosyayı
        # tamamen boşaltırdı; bu durumda kot sütununa sıfır yazılır.
        kotsuz = secenekler.ncn_kotsuz
        if kotsuz is None and karelaj.eksik_kot_sayisi() == len(karelaj.noktalar):
            kotsuz = "sifir"
        ayar = profil_coz(
            secenekler.ncn_profil,
            sutunlar=secenekler.ncn_sutun,
            ayirac=secenekler.ncn_ayirac,
            ondalik_xy=secenekler.ncn_ondalik,
            ondalik_z=secenekler.ncn_ondalik_z,
            baslik=True if secenekler.ncn_baslik else None,
            kotsuz=kotsuz,
            kodlama=secenekler.ncn_kodlama,
            satir_sonu=secenekler.ncn_satir_sonu,
            tirnak=secenekler.ncn_tirnak,
            kod_no=secenekler.ncn_kod_no,
        )
        yol = os.path.join(secenekler.cikti, f"{temel}.ncn")
        adet = ncn_yaz(yol, karelaj.noktalar, ayar)
        dosyalar.append(yol)
        _yaz(
            f"  {os.path.basename(yol)}  ({bicim.tam_sayi(adet)} nokta, "
            f"düzen: {' '.join(ayar.sutunlar)})",
            sessiz,
        )
        if adet == 0 and karelaj.noktalar:
            _yaz(
                "  ! NCN dosyası boş: noktaların hiçbirinin kotu okunamadı ve "
                "kotsuz noktalar atlanıyor. --ncn-kotsuz sifir seçeneğini kullanın.",
                sessiz,
            )
        elif adet < len(karelaj.noktalar):
            _yaz(
                f"  ! {bicim.tam_sayi(len(karelaj.noktalar) - adet)} nokta kotu "
                f"okunamadığı için NCN dosyasına yazılmadı "
                f"(--ncn-kotsuz sifir ile yazdırabilirsiniz).",
                sessiz,
            )

    if "csv" in bicimler:
        yol = os.path.join(secenekler.cikti, f"{temel}.csv")
        adet = csv_yaz(yol, karelaj.noktalar, ingilizce=secenekler.csv_ingilizce)
        dosyalar.append(yol)
        _yaz(f"  {os.path.basename(yol)}  ({bicim.tam_sayi(adet)} satır)", sessiz)

    if "xyz" in bicimler:
        yol = os.path.join(secenekler.cikti, f"{temel}.xyz")
        adet = xyz_yaz(yol, karelaj.noktalar)
        dosyalar.append(yol)
        _yaz(f"  {os.path.basename(yol)}  ({bicim.tam_sayi(adet)} satır)", sessiz)

    if "dxf" in bicimler:
        yol = os.path.join(secenekler.cikti, f"{temel}.dxf")
        dxf_yaz(
            yol,
            karelaj,
            kot_yazisi=not secenekler.dxf_kot_yazisi_yok,
            nokta_numarasi=secenekler.dxf_nokta_no,
            izgara_cizgileri=not secenekler.dxf_izgara_yok,
            konturlar=konturlar,
            yazi_yuksekligi=secenekler.dxf_yazi_yuksekligi,
        )
        dosyalar.append(yol)
        _yaz(f"  {os.path.basename(yol)}", sessiz)

    if "kml" in bicimler:
        yol = os.path.join(secenekler.cikti, f"{temel}.kml")
        kml_yaz(yol, karelaj, konturlar=konturlar, baslik=karelaj.alan.ad)
        dosyalar.append(yol)
        _yaz(f"  {os.path.basename(yol)}  (Google Earth ile açılabilir)", sessiz)

    if "geojson" in bicimler:
        yol = os.path.join(secenekler.cikti, f"{temel}.geojson")
        geojson_yaz(yol, karelaj, konturlar=konturlar)
        dosyalar.append(yol)
        _yaz(f"  {os.path.basename(yol)}", sessiz)

    return dosyalar


# Raporda gizlenmesi gereken seçenekler
GIZLI_SECENEKLER = ("--google-anahtar",)


def _komut_metni() -> str:
    """
    Çalıştırılan komutu rapora yazmak üzere biçimlendirir.

    API anahtarı gibi gizli değerler maskelenir; rapor dosyası proje
    klasöründe saklandığı, paylaşıldığı ve arşivlendiği için anahtarın
    dosyaya düşmemesi gerekir.
    """
    parcalar: List[str] = []
    gizle_sonraki = False
    for parca in sys.argv:
        if gizle_sonraki:
            parcalar.append("***")
            gizle_sonraki = False
            continue
        if parca in GIZLI_SECENEKLER:
            parcalar.append(parca)
            gizle_sonraki = True
            continue
        gizli_esit = next(
            (s for s in GIZLI_SECENEKLER if parca.startswith(s + "=")), None
        )
        if gizli_esit:
            parcalar.append(f"{gizli_esit}=***")
            continue
        parcalar.append(shlex.quote(parca))
    return " ".join(parcalar)


# ---------------------------------------------------------------------------
# Diğer komutlar
# ---------------------------------------------------------------------------


def komut_sistemler(secenekler) -> int:
    print(f"{'Kod':<16} {'EPSG':<8} {'Dilim':<6} Ad")
    print("-" * 92)
    for sistem in sistem_listesi():
        print(
            f"{sistem.kod:<16} "
            f"{('EPSG:' + str(sistem.epsg)) if sistem.epsg else '-':<8} "
            f"{sistem.dilim if sistem.dilim else '-':<6} {sistem.ad}"
        )
    print()
    print("Kullanım: --sistem ITRF96-TM30   ya da   --sistem EPSG:5254")
    print("Yalnızca aile verilirse dilim alanın orta boylamından seçilir:")
    print("  --sistem ITRF96 | ITRF96-GK | ED50 | ED50-GK | UTM | ED50-UTM")
    print("Dilim doğrudan verilebilir: --dilim 10 (30° orta meridyen)")
    return 0


def komut_kaynaklar(secenekler) -> int:
    print("KOT KAYNAKLARI")
    print("=" * 76)
    print()
    print("opentopodata   Açık, anahtar gerektirmez (varsayılan).")
    print("               Açık sunucu kotası: 100 nokta/istek, 1 istek/sn, 1000 istek/gün.")
    print("               Kurum içi sunucu için: --sunucu http://sunucu:5000")
    print("               Veri kümeleri (--veri-kumesi):")
    for ad, (aciklama, cozunurluk, datum) in sorted(OPENTOPODATA_VERI_KUMELERI.items()):
        print(f"                 {ad:<12} {aciklama}")
        print(f"                 {'':<12} çözünürlük {cozunurluk}, düşey datum: {datum}")
    print()
    print("open-elevation Açık, kotasız, yalnızca SRTM 30 m. Kararlılığı düşüktür.")
    print()
    print("google         Google Maps Elevation API. Google Earth'ün arazi verisidir.")
    print("               API anahtarı ve faturalandırma gerekir:")
    print("               --google-anahtar ANAHTAR  veya  GOOGLE_ELEVATION_ANAHTARI")
    print()
    print("yerel          Kurumun kendi sayısal yükseklik modeli (en doğru seçenek).")
    print("               --sym dosya.tif   veya   --sym karolar_klasoru/")
    print("               Biçimler: GeoTIFF (.tif), ESRI ASCII Grid (.asc), SRTM (.hgt)")
    print("               Koordinat sistemi dosyadan okunur; yoksa --dem-sistemi verin.")
    print()
    print("Örnekleme yöntemi (--ornekleme): en-yakin | bilineer (varsayılan) | bikubik")
    return 0


def komut_donustur(secenekler) -> int:
    kaynak = sistem_bul(secenekler.kaynak_sistem)
    hedef = sistem_bul(secenekler.hedef_sistem)
    try:
        birinci, ikinci = [float(p.replace(",", ".")) for p in secenekler.koordinat.replace(";", ",").split(",")[:2]]
    except ValueError as hata:
        raise KullanimHatasi(
            "Koordinat iki sayı olmalıdır. Coğrafi sistemde 'enlem,boylam', "
            "izdüşümlü sistemde 'sağa,yukarı' verin."
        ) from hata

    if kaynak.cografi:
        enlem, boylam = birinci, ikinci
    else:
        enlem, boylam = kaynak.wgs84e(birinci, ikinci)
    if hedef.cografi:
        cikti_1, cikti_2 = boylam, enlem
        etiketler = ("Boylam", "Enlem")
        basamak = 8
    else:
        cikti_1, cikti_2 = hedef.wgs84ten(enlem, boylam)
        etiketler = ("Y (sağa)", "X (yukarı)")
        basamak = 3

    print(f"Kaynak : {kaynak.tanim()}")
    print(f"Hedef  : {hedef.tanim()}")
    print()
    print(f"  WGS84 enlem/boylam : {bicim.sayi(enlem, 8)}, {bicim.sayi(boylam, 8)}")
    print(f"  {etiketler[0]:<18} : {bicim.sayi(cikti_1, basamak)}")
    print(f"  {etiketler[1]:<18} : {bicim.sayi(cikti_2, basamak)}")
    if hedef.projeksiyon is not None:
        print()
        print(
            f"  Ölçek faktörü      : "
            f"{bicim.sayi(hedef.projeksiyon.olcek_faktoru(enlem, boylam), 8)}"
        )
        yakinsama = hedef.projeksiyon.meridyen_yakinsamasi(enlem, boylam)
        print(
            f"  Meridyen yakınsama : "
            f"{'+' if yakinsama >= 0 else '-'}{bicim.sayi(abs(yakinsama), 6)}°"
        )
    return 0


def komut_onbellek(secenekler) -> int:
    yol = secenekler.onbellek or varsayilan_onbellek_yolu()
    onbellek = KotOnbellegi(yol)
    try:
        if secenekler.temizle:
            silinen = onbellek.temizle(secenekler.kaynak_kimlik)
            print(f"{bicim.tam_sayi(silinen)} kayıt silindi.")
        else:
            var = os.path.exists(yol)
            print(f"Önbellek dosyası : {yol}")
            print(f"Durum            : {'var' if var else 'henüz oluşturulmadı'}")
            if var:
                print(f"Kayıt sayısı     : {bicim.tam_sayi(onbellek.kayit_sayisi())}")
                print(
                    f"Dosya boyutu     : "
                    f"{bicim.sayi(os.path.getsize(yol) / 1024.0, 1)} KB"
                )
            print()
            print("Temizlemek için: python -m karelaj onbellek --temizle")
    finally:
        onbellek.kapat()
    return 0


def komut_arayuz(secenekler) -> int:
    from .sunucu import arayuzu_baslat

    return arayuzu_baslat(
        adres=secenekler.adres,
        kapi=secenekler.kapi,
        tarayici_ac=not secenekler.tarayici_yok,
        cikti_klasoru=secenekler.cikti,
        penceresiz=penceresiz_mi(),
        gunluk_yolu=getattr(secenekler, "_gunluk_yolu", None),
    )


# ---------------------------------------------------------------------------
# Argüman çözümleyici
# ---------------------------------------------------------------------------


def _uret_seceneklerini_ekle(a: argparse.ArgumentParser) -> None:
    g = a.add_argument_group("Çalışma alanı")
    g.add_argument(
        "--sinir",
        metavar="E1,B1,E2,B2",
        help="Sınır kutusu köşeleri: enlem1,boylam1,enlem2,boylam2 "
        "(Google Earth'ün gösterdiği sıra).",
    )
    g.add_argument(
        "--alan",
        metavar="DOSYA",
        help="Poligon dosyası: .geojson, .json, .kml, .kmz, .wkt, .csv, .txt, .ncn",
    )
    g.add_argument(
        "--alan-katman",
        metavar="AD",
        help="KML/KMZ içinde kullanılacak yer işaretinin (Placemark) adı.",
    )
    g.add_argument(
        "--sinir-sistemi",
        metavar="SISTEM",
        help="İzdüşümlü sınır dosyalarının (NCN, izdüşümlü CSV) koordinat sistemi.",
    )
    g.add_argument(
        "--metin-sirasi",
        choices=("enlem-boylam", "boylam-enlem"),
        default="enlem-boylam",
        help="Düz metin/CSV sınır dosyalarındaki sütun sırası (varsayılan: enlem-boylam).",
    )
    g.add_argument(
        "--sinir-ncn-duzen",
        default="no,y,x,z,kod",
        metavar="LISTE",
        help="NCN sınır dosyasının sütun sırası (varsayılan: no,y,x,z,kod).",
    )

    g = a.add_argument_group("Karelaj")
    g.add_argument(
        "--aralik", type=float, default=25.0, metavar="M",
        help="Karelaj aralığı, metre (varsayılan: 25).",
    )
    g.add_argument(
        "--aralik-yukari", type=float, default=None, metavar="M",
        help="Kuzey-güney yönünde farklı aralık (dikdörtgen karelaj).",
    )
    g.add_argument(
        "--sistem", default="otomatik", metavar="SISTEM",
        help="Koordinat sistemi kodu (ITRF96-TM30), EPSG numarası (EPSG:5254) veya "
        "sistem ailesi (ITRF96, ED50, UTM). Varsayılan: otomatik.",
    )
    g.add_argument(
        "--dilim", type=int, default=None, metavar="N",
        help="3 derecelik dilim numarası (9-15). Orta meridyeni sabitler.",
    )
    g.add_argument(
        "--hizalama", choices=("tam-kat", "alan"), default="tam-kat",
        help="Izgara başlangıcı: aralığın tam katlarına oturt (varsayılan) veya "
        "alanın güneybatı köşesinden başlat.",
    )
    g.add_argument(
        "--donme", type=float, default=0.0, metavar="DERECE",
        help="Karelajı alan merkezi etrafında döndür (saat yönünün tersi pozitif).",
    )
    g.add_argument("--kirpma-yok", action="store_true", help="Alan sınırına kırpma.")
    g.add_argument(
        "--tampon", type=float, default=0.0, metavar="M",
        help="Kırpmada sınıra eklenecek tampon (negatif değer içeri daraltır).",
    )
    g.add_argument(
        "--kose-noktalari", action="store_true",
        help="Poligon köşe noktalarını da çıktıya ekle.",
    )
    g.add_argument(
        "--siralama", choices=("kuzey-guney", "guney-kuzey"), default="kuzey-guney",
        help="Satır sırası (varsayılan: kuzeyden güneye).",
    )
    g.add_argument(
        "--no-profil", choices=("sira", "satir-sutun", "sutun-satir"), default="sira",
        help="Nokta numarası biçimi (varsayılan: sıra numarası).",
    )
    g.add_argument("--no-onek", default="", metavar="METIN", help="Nokta numarası öneki.")
    g.add_argument("--no-baslangic", type=int, default=1, metavar="N", help="İlk nokta numarası.")
    g.add_argument(
        "--no-basamak", type=int, default=0, metavar="N",
        help="Numara basamak sayısı (sıfır dolgulu). 0 = dolgu yok.",
    )
    g.add_argument(
        "--no-ayirac", default="-", metavar="KARAKTER",
        help="satir-sutun/sutun-satir numaralarında ayırıcı (varsayılan: -). "
             "Netcad kesit numaralarında / kullanılır.",
    )
    g.add_argument("--kod", default="", metavar="METIN", help="Tüm noktalara yazılacak nokta kodu.")
    g.add_argument(
        "--azami-nokta", type=int, default=500000, metavar="N",
        help="Güvenlik sınırı: üretilecek azami nokta sayısı (varsayılan: 500.000).",
    )

    g = a.add_argument_group("Kot kaynağı")
    g.add_argument(
        "--kaynak", default="opentopodata", choices=list(KAYNAK_ADLARI),
        help="Yükseklik kaynağı (varsayılan: opentopodata).",
    )
    g.add_argument(
        "--veri-kumesi", default="srtm30m", metavar="AD",
        help="OpenTopoData veri kümesi (varsayılan: srtm30m).",
    )
    g.add_argument("--sunucu", default=None, metavar="URL", help="Kendi kurduğunuz servis adresi.")
    g.add_argument("--sym", default=None, metavar="YOL", help="Yerel SYM dosyası veya karo klasörü.")
    g.add_argument("--dem-sistemi", default=None, metavar="SISTEM", help="SYM dosyasının koordinat sistemi.")
    g.add_argument(
        "--ornekleme", choices=("en-yakin", "bilineer", "bikubik"), default="bilineer",
        help="Yükseklik ara değer yöntemi (varsayılan: bilineer).",
    )
    g.add_argument("--google-anahtar", default=None, metavar="ANAHTAR", help="Google Elevation API anahtarı.")
    g.add_argument(
        "--kot-kaydirma", type=float, default=0.0, metavar="M",
        help="Okunan her kota eklenecek düşey kaydırma (düşey datum farkı düzeltmesi).",
    )
    g.add_argument("--toplu", type=int, default=None, metavar="N", help="İstek başına nokta sayısı.")
    g.add_argument("--zaman-asimi", type=float, default=30.0, metavar="SN", help="İstek zaman aşımı.")
    g.add_argument("--yeniden-deneme", type=int, default=4, metavar="N", help="Başarısız istek için deneme sayısı.")
    g.add_argument("--istek-araligi", type=float, default=None, metavar="SN", help="İstekler arası en az bekleme.")
    g.add_argument("--onbellek", default=None, metavar="YOL", help="Kot önbelleği dosyası.")
    g.add_argument("--onbellek-yok", action="store_true", help="Önbelleği kullanma.")
    g.add_argument("--kot-yok", action="store_true", help="Kot okuma; yalnızca nokta konumlarını üret.")

    g = a.add_argument_group("Çıktı")
    g.add_argument(
        "-c", "--cikti", default=varsayilan_cikti_klasoru(), metavar="KLASOR",
        help=f"Çıktı klasörü (varsayılan: {varsayilan_cikti_klasoru()}).",
    )
    g.add_argument("--ad", default=None, metavar="AD", help="Çıktı dosyalarının temel adı.")
    g.add_argument(
        "--bicim", default=VARSAYILAN_BICIMLER, metavar="LISTE",
        help=f"Virgülle ayrılmış çıktı biçimleri: {', '.join(BICIMLER)} veya 'hepsi' "
        f"(varsayılan: {VARSAYILAN_BICIMLER}).",
    )
    g.add_argument(
        "--kontur", type=float, default=None, metavar="M",
        help="Eş yükselti eğrisi aralığı (m). Verilirse DXF/KML/GeoJSON çıktılarına eklenir.",
    )
    g.add_argument("--kontur-temel", type=float, default=0.0, metavar="M", help="Eş yükseltilerin hizalanacağı taban kot.")
    g.add_argument("--hacim-kotu", type=float, default=None, metavar="M", help="Bu proje kotuna göre kazı/dolgu hacmi hesapla.")
    g.add_argument("--hacim-alt-bolme", type=int, default=8, metavar="N", help="Hacimde kare başına alt bölme sayısı (varsayılan: 8).")

    g = a.add_argument_group("Netcad NCN biçimi")
    g.add_argument(
        "--ncn-profil", default="netcad", choices=list(NCN_PROFILLERI),
        help="Hazır sütun düzeni (varsayılan: netcad = NoktaNo,Y,X,Z,Kod).",
    )
    g.add_argument(
        "--ncn-sutun", default=None, metavar="LISTE",
        help=f"Sütun düzenini elle belirle. Kullanılabilir: {', '.join(SUTUN_BASLIKLARI)}",
    )
    g.add_argument(
        "--ncn-ayirac", default=None, metavar="AYIRAC",
        help=f"Alan ayırıcı: {', '.join(AYIRACLAR)} veya doğrudan karakter.",
    )
    g.add_argument("--ncn-ondalik", type=int, default=None, metavar="N", help="Koordinat ondalık basamağı (varsayılan: 3).")
    g.add_argument("--ncn-ondalik-z", type=int, default=None, metavar="N", help="Kot ondalık basamağı (varsayılan: 3).")
    g.add_argument("--ncn-baslik", action="store_true", help="Dosyaya sütun başlığı satırı ekle.")
    g.add_argument(
        "--ncn-kotsuz", choices=("atla", "sifir", "bos"), default=None,
        help="Kotu okunamayan noktalar: atla (varsayılan), sıfır yaz veya boş bırak.",
    )
    g.add_argument(
        "--ncn-tirnak", default=None, metavar="KARAKTER",
        help="Metin sütunlarını saracak tırnak karakteri; 'yok' ile kapatılır.",
    )
    g.add_argument(
        "--ncn-kod-no", type=int, default=None, metavar="N",
        help="NCN'deki sayısal kod alanına yazılacak değer (varsayılan: 0).",
    )
    g.add_argument("--ncn-kodlama", default=None, metavar="KODLAMA", help="Dosya kodlaması (varsayılan: cp1254).")
    g.add_argument("--ncn-satir-sonu", default=None, choices=("crlf", "lf"), help="Satır sonu (varsayılan: crlf).")

    g = a.add_argument_group("Diğer çıktı ayarları")
    g.add_argument("--csv-ingilizce", action="store_true", help="CSV'yi nokta ondalıklı ve virgül ayırıcılı yaz.")
    g.add_argument("--dxf-kot-yazisi-yok", action="store_true", help="DXF'e kot yazılarını ekleme.")
    g.add_argument("--dxf-nokta-no", action="store_true", help="DXF'e nokta numaralarını ekle.")
    g.add_argument("--dxf-izgara-yok", action="store_true", help="DXF'e karelaj çizgilerini ekleme.")
    g.add_argument("--dxf-yazi-yuksekligi", type=float, default=None, metavar="M", help="DXF yazı yüksekliği.")

    a.add_argument("--sessiz", action="store_true", help="Ekran çıktısını bastır.")


def cozumleyici_olustur() -> argparse.ArgumentParser:
    ana = argparse.ArgumentParser(
        prog="karelaj",
        description="Seçilen alandan belirli aralıklarla kot karelajı üretir ve "
        "noktaları Netcad NCN biçiminde dışa aktarır.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Örnekler:
  # Sınır kutusundan 25 m karelaj, ITRF96 3° TM30, NCN + KML + rapor
  python -m karelaj uret --sinir 40.7530,29.9301,40.7602,29.9443 --aralik 25

  # Google Earth'ten kaydedilmiş KML poligonu, 10 m karelaj, tüm çıktılar
  python -m karelaj uret --alan saha.kml --aralik 10 --bicim hepsi

  # Kurumun kendi SYM verisinden, eş yükselti ve hacim hesabıyla
  python -m karelaj uret --alan saha.kml --aralik 5 --kaynak yerel \\
      --sym /veri/sym/kocaeli.tif --kontur 1 --hacim-kotu 42.5

  # Google Elevation API ile (Google Earth arazi verisi)
  python -m karelaj uret --alan saha.kml --kaynak google --google-anahtar ANAHTAR

  # Tarayıcıda harita üzerinden alan seçmek için
  python -m karelaj arayuz
""",
    )
    altlar = ana.add_subparsers(dest="komut")

    uret = altlar.add_parser("uret", help="Karelaj üret (varsayılan komut).")
    _uret_seceneklerini_ekle(uret)
    uret.set_defaults(islev=komut_uret)

    sistemler = altlar.add_parser("sistemler", help="Tanımlı koordinat sistemlerini listele.")
    sistemler.set_defaults(islev=komut_sistemler)

    kaynaklar = altlar.add_parser("kaynaklar", help="Kot kaynaklarını ve veri kümelerini listele.")
    kaynaklar.set_defaults(islev=komut_kaynaklar)

    donustur = altlar.add_parser("donustur", help="Tek nokta koordinat dönüşümü.")
    donustur.add_argument("koordinat", help="Coğrafi sistemde 'enlem,boylam'; izdüşümlüde 'sağa,yukarı'.")
    donustur.add_argument("--kaynak-sistem", default="WGS84", help="Kaynak sistem (varsayılan: WGS84).")
    donustur.add_argument("--hedef-sistem", default="ITRF96-TM30", help="Hedef sistem (varsayılan: ITRF96-TM30).")
    donustur.set_defaults(islev=komut_donustur)

    onbellek = altlar.add_parser("onbellek", help="Kot önbelleğini görüntüle veya temizle.")
    onbellek.add_argument("--onbellek", default=None, metavar="YOL", help="Önbellek dosyası.")
    onbellek.add_argument("--temizle", action="store_true", help="Kayıtları sil.")
    onbellek.add_argument("--kaynak-kimlik", default=None, metavar="KIMLIK", help="Yalnızca bu kaynağın kayıtlarını sil.")
    onbellek.set_defaults(islev=komut_onbellek)

    arayuz = altlar.add_parser("arayuz", help="Tarayıcıda harita üzerinden alan seçme arayüzünü başlat.")
    arayuz.add_argument("--kapi", type=int, default=8777, metavar="N", help="Dinlenecek kapı (varsayılan: 8777).")
    arayuz.add_argument("--adres", default="127.0.0.1", metavar="ADRES", help="Dinlenecek adres (varsayılan: 127.0.0.1).")
    arayuz.add_argument("--tarayici-yok", action="store_true", help="Tarayıcıyı kendiliğinden açma.")
    arayuz.add_argument(
        "-c", "--cikti", default=varsayilan_cikti_klasoru(), metavar="KLASOR",
        help="Çıktı klasörü.",
    )
    arayuz.set_defaults(islev=komut_arayuz)

    return ana


def _boru_kapandi() -> None:
    """
    Çıktı borusu erken kapandığında kapanış uyarısını bastırır.

    ``KotKarelaji.exe sistemler | more`` gibi bir kullanımda okuyan taraf
    ilk sayfadan sonra çıkabilir. O noktadan sonra yazmaya çalışmak hata
    verir ve Python, program kapanırken "Exception ignored" uyarısı basar.
    Standart çıktı boş aygıta yönlendirilerek bu önlenir.
    """
    try:
        bos = os.open(os.devnull, os.O_WRONLY)
        os.dup2(bos, sys.stdout.fileno())
    except (OSError, ValueError, AttributeError):
        pass


def _boru_hatasi_mi(hata: BaseException) -> bool:
    """Hata, çıktı borusunun kapanmasından mı kaynaklanıyor?"""
    if isinstance(hata, BrokenPipeError):
        return True
    # Windows kapanan boruyu bazen EINVAL ile bildirir
    return isinstance(hata, OSError) and hata.errno in (errno.EPIPE, errno.EINVAL)


def _hatayi_bildir(ileti: str, gunluk_yolu: Optional[str] = None) -> None:
    """
    Hatayı kullanıcıya ulaştırır.

    Konsol varsa yazdırır; pencere kipinde okunacak bir konsol olmadığı
    için Windows uyarı kutusu gösterir.
    """
    print(f"\nHATA: {ileti}\n", file=sys.stderr)
    if not penceresiz_mi():
        return
    from .sunucu import _pencere_uyarisi

    tam = ileti
    if gunluk_yolu:
        tam += f"\n\nAyrıntılar için günlük dosyası:\n{gunluk_yolu}"
    _pencere_uyarisi("Kot Karelajı - hata", tam)


def _pencereyi_acik_tut() -> None:
    """
    Paketlenmiş uygulamada hata iletisinin okunabilmesi için bekler.

    Çift tıklayarak açılan bir konsol penceresi, program bitince hemen
    kapanır ve kullanıcı hatayı göremez.
    """
    if not paketlenmis_mi() or penceresiz_mi():
        return
    try:
        input("\nKapatmak için Enter tuşuna basın... ")
    except (EOFError, KeyboardInterrupt):
        pass


def main(argumanlar: Optional[Sequence[str]] = None) -> int:
    # Akışlar değiştirilmeden önce pencere kipi saptanmalıdır.
    penceresiz_durumunu_sabitle()
    gunluk_yolu = cikti_akislarini_hazirla()
    cikti_kodlamasini_ayarla()
    ham = list(argumanlar if argumanlar is not None else sys.argv[1:])
    bilinen_komutlar = {"uret", "sistemler", "kaynaklar", "donustur", "onbellek", "arayuz"}
    if not ham and paketlenmis_mi():
        # Uygulamaya çift tıklandığında doğrudan harita arayüzünü aç
        ham = ["arayuz"]
    elif ham and ham[0].startswith("-") and ham[0] not in ("-h", "--help"):
        ham.insert(0, "uret")  # komut verilmediyse 'uret' varsay

    cozumleyici = cozumleyici_olustur()
    secenekler = cozumleyici.parse_args(ham)
    setattr(secenekler, "_gunluk_yolu", gunluk_yolu)
    if not getattr(secenekler, "islev", None):
        cozumleyici.print_help()
        return 1
    try:
        return secenekler.islev(secenekler)
    except KullanimHatasi as hata:
        _hatayi_bildir(str(hata), gunluk_yolu)
        _pencereyi_acik_tut()
        return 2
    except UnicodeEncodeError as hata:
        # Buraya normalde düşülmez; cikti_kodlamasini_ayarla() bunu önler.
        # Yine de olursa, iletinin kendisi de yazılamayabileceği için
        # yalnızca ASCII karakterlerle uyarılır.
        print(
            "\nHATA: Ekran ciktisi kodlanamadi "
            f"({hata.encoding}). Cikti kodlamasini UTF-8 yapin: "
            "set PYTHONIOENCODING=utf-8\n",
            file=sys.stderr,
        )
        _pencereyi_acik_tut()
        return 2
    except (ValueError, KaynakHatasi) as hata:
        _hatayi_bildir(str(hata), gunluk_yolu)
        _pencereyi_acik_tut()
        return 2
    except FileNotFoundError as hata:
        _hatayi_bildir(f"Dosya bulunamadı: {hata}", gunluk_yolu)
        _pencereyi_acik_tut()
        return 2
    except KeyboardInterrupt:
        print("\nİşlem kullanıcı tarafından durduruldu.", file=sys.stderr)
        return 130
    except Exception as hata:  # paketlenmiş uygulamada izlemeyi göster
        if _boru_hatasi_mi(hata):
            _boru_kapandi()
            return 0
        import traceback

        traceback.print_exc()
        _hatayi_bildir(f"Beklenmeyen hata: {hata}", gunluk_yolu)
        _pencereyi_acik_tut()
        return 1
