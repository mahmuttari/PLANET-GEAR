# -*- coding: utf-8 -*-
"""
Yerel harita arayüzü sunucusu
=============================

``python -m karelaj arayuz`` komutuyla başlatılır. Bilgisayarda yalnızca
yerel ağ arayüzünü (127.0.0.1) dinleyen küçük bir HTTP sunucusu açar ve
tarayıcıda uydu görüntüsü üzerinde alan çizip karelaj üretilmesini sağlar.

Güvenlik notları
----------------

* Sunucu varsayılan olarak yalnızca ``127.0.0.1`` adresini dinler; kurum
  ağındaki başka bilgisayarlar erişemez.
* İndirme uç noktası yalnızca bu oturumda üretilmiş dosyaları, çıktı
  klasörünün içinden verir; klasör dışına çıkan yollar reddedilir.
* Dışarıya hiçbir veri gönderilmez; kot sorguları yalnızca kullanıcının
  seçtiği kaynağa gider.
"""

from __future__ import annotations

import json
import os
import posixpath
import sys
import threading
import traceback
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional

from . import bicim
from .geodezi import otomatik_sistem, sistem_bul, sistem_listesi
from .geometri import Alan
from .hacim import hacim_hesapla
from .izgara import KarelajAyari, NumaralandirmaAyari, karelaj_uret, nokta_sayisi_tahmini
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
    NCN_PROFILLERI,
    csv_yaz,
    dxf_yaz,
    geojson_yaz,
    kml_yaz,
    ncn_yaz,
    profil_coz,
    rapor_metni,
    rapor_yaz,
    xyz_yaz,
)

ONIZLEME_AZAMI_NOKTA = 6000
URETIM_AZAMI_NOKTA = 200000


class ArayuzHatasi(Exception):
    """Arayüzden gelen istek geçersiz olduğunda."""


def _web_dosyasi(ad: str) -> str:
    """
    Arayüz dosyasının tam yolunu verir.

    PyInstaller ile tek dosyalık ``.exe`` hâline getirildiğinde paketin
    içeriği geçici bir klasöre açılır ve bu klasörün yolu ``sys._MEIPASS``
    ile bildirilir. Kaynak koddan çalışırken böyle bir değişken olmadığı
    için modülün kendi klasörüne bakılır.
    """
    paket_koku = getattr(sys, "_MEIPASS", None)
    if paket_koku:
        aday = os.path.join(paket_koku, "karelaj", "web", ad)
        if os.path.exists(aday):
            return aday
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", ad)


# ---------------------------------------------------------------------------
# İstek işleyici
# ---------------------------------------------------------------------------


class _Isleyici(BaseHTTPRequestHandler):
    server_version = "karelaj/1.0"
    cikti_klasoru = "cikti"

    def log_message(self, bicim_metni: str, *argumanlar) -> None:
        # Varsayılan gürültülü günlüğü bastır; yalnızca hataları yaz.
        pass

    # -- yanıt yardımcıları ------------------------------------------------

    def _json_yanit(self, veri: Dict[str, Any], kod: int = 200) -> None:
        ham = json.dumps(veri, ensure_ascii=False).encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(ham)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(ham)

    def _dosya_yanit(self, yol: str, tur: str, indirme_adi: Optional[str] = None) -> None:
        try:
            with open(yol, "rb") as f:
                ham = f.read()
        except OSError:
            self._json_yanit({"hata": "Dosya okunamadı."}, 404)
            return
        self.send_response(200)
        self.send_header("Content-Type", tur)
        self.send_header("Content-Length", str(len(ham)))
        if indirme_adi:
            guvenli_ad = urllib.parse.quote(indirme_adi)
            self.send_header(
                "Content-Disposition", f"attachment; filename*=UTF-8''{guvenli_ad}"
            )
        self.end_headers()
        self.wfile.write(ham)

    def _govde_oku(self) -> Dict[str, Any]:
        uzunluk = int(self.headers.get("Content-Length") or 0)
        if uzunluk <= 0:
            return {}
        if uzunluk > 64 * 1024 * 1024:
            raise ArayuzHatasi("İstek gövdesi çok büyük.")
        ham = self.rfile.read(uzunluk)
        try:
            veri = json.loads(ham.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as hata:
            raise ArayuzHatasi(f"İstek gövdesi çözümlenemedi: {hata}") from hata
        if not isinstance(veri, dict):
            raise ArayuzHatasi("İstek gövdesi bir JSON nesnesi olmalıdır.")
        return veri

    # -- yönlendirme --------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 (http.server arayüzü)
        parcali = urllib.parse.urlparse(self.path)
        yol = parcali.path
        try:
            if yol in ("/", "/index.html"):
                self._dosya_yanit(_web_dosyasi("index.html"), "text/html; charset=utf-8")
            elif yol == "/api/baslangic":
                self._json_yanit(_baslangic_verisi())
            elif yol == "/indir":
                self._indir(urllib.parse.parse_qs(parcali.query))
            else:
                self._json_yanit({"hata": "Bulunamadı."}, 404)
        except ArayuzHatasi as hata:
            self._json_yanit({"hata": str(hata)}, 400)
        except Exception as hata:  # pragma: no cover
            traceback.print_exc()
            self._json_yanit({"hata": f"Beklenmeyen hata: {hata}"}, 500)

    def do_POST(self) -> None:  # noqa: N802
        parcali = urllib.parse.urlparse(self.path)
        try:
            govde = self._govde_oku()
            if parcali.path == "/api/onizleme":
                self._json_yanit(_onizleme(govde))
            elif parcali.path == "/api/uret":
                self._json_yanit(_uret(govde, self.cikti_klasoru))
            else:
                self._json_yanit({"hata": "Bulunamadı."}, 404)
        except (ArayuzHatasi, ValueError, KaynakHatasi) as hata:
            self._json_yanit({"hata": str(hata)}, 400)
        except Exception as hata:  # pragma: no cover
            traceback.print_exc()
            self._json_yanit({"hata": f"Beklenmeyen hata: {hata}"}, 500)

    def _indir(self, sorgu: Dict[str, List[str]]) -> None:
        ad = (sorgu.get("dosya") or [""])[0]
        if not ad:
            raise ArayuzHatasi("İndirilecek dosya belirtilmedi.")
        # Yol geçişi (path traversal) koruması
        temiz = posixpath.normpath("/" + ad.replace("\\", "/")).lstrip("/")
        kok = os.path.abspath(self.cikti_klasoru)
        tam = os.path.abspath(os.path.join(kok, temiz))
        if os.path.commonpath([kok, tam]) != kok or not os.path.isfile(tam):
            raise ArayuzHatasi("Geçersiz dosya yolu.")
        turler = {
            ".ncn": "text/plain; charset=windows-1254",
            ".csv": "text/csv; charset=windows-1254",
            ".xyz": "text/plain; charset=utf-8",
            ".dxf": "application/dxf",
            ".kml": "application/vnd.google-earth.kml+xml",
            ".geojson": "application/geo+json",
            ".txt": "text/plain; charset=utf-8",
        }
        uzanti = os.path.splitext(tam)[1].lower()
        self._dosya_yanit(
            tam, turler.get(uzanti, "application/octet-stream"), os.path.basename(tam)
        )


# ---------------------------------------------------------------------------
# API uçları
# ---------------------------------------------------------------------------


def _baslangic_verisi() -> Dict[str, Any]:
    return {
        "sistemler": [
            {
                "kod": s.kod,
                "ad": s.ad,
                "epsg": s.epsg,
                "dilim": s.dilim,
                "cografi": s.cografi,
            }
            for s in sistem_listesi()
            if not s.cografi
        ],
        "veri_kumeleri": [
            {"kod": kod, "ad": bilgi[0], "cozunurluk": bilgi[1], "datum": bilgi[2]}
            for kod, bilgi in sorted(OPENTOPODATA_VERI_KUMELERI.items())
        ],
        "kaynaklar": list(KAYNAK_ADLARI),
        "ncn_profilleri": [
            {"kod": kod, "duzen": " ".join(ayar.sutunlar), "ayirac": ayar.ayirac}
            for kod, ayar in NCN_PROFILLERI.items()
        ],
        "onbellek_yolu": varsayilan_onbellek_yolu(),
        "onizleme_azami": ONIZLEME_AZAMI_NOKTA,
    }


def _alani_al(govde: Dict[str, Any]) -> Alan:
    halkalar = govde.get("halkalar")
    if not halkalar or not isinstance(halkalar, list):
        raise ArayuzHatasi(
            "Çalışma alanı çizilmedi. Harita üzerinde dikdörtgen veya poligon çizin."
        )
    temiz: List[List[tuple]] = []
    for halka in halkalar:
        noktalar = []
        for nokta in halka:
            try:
                boylam, enlem = float(nokta[0]), float(nokta[1])
            except (TypeError, ValueError, IndexError) as hata:
                raise ArayuzHatasi("Alan köşeleri sayısal olmalıdır.") from hata
            if not (-180.0 <= boylam <= 180.0 and -90.0 <= enlem <= 90.0):
                raise ArayuzHatasi("Alan köşeleri geçerli enlem/boylam olmalıdır.")
            noktalar.append((boylam, enlem))
        if len(noktalar) >= 3:
            temiz.append(noktalar)
    if not temiz:
        raise ArayuzHatasi("Alan en az 3 köşe noktası içermelidir.")
    return Alan(temiz, ad=str(govde.get("ad") or "Çalışma alanı"))


def _sayi_al(
    govde: Dict[str, Any],
    anahtar: str,
    varsayilan: Optional[float],
    etiket: str,
    tam_sayi: bool = False,
) -> Optional[float]:
    """
    Gövdeden sayı okur.

    Alanın hiç verilmemesi, ``None`` ya da boş metin olması "belirtilmedi"
    sayılır ve varsayılan döner. **Sıfır geçerli bir değerdir**; sıfırı
    "belirtilmedi" saymak, kullanıcının 0 yazdığı aralığın sessizce
    varsayılana dönmesine yol açacağı için özellikle ayrıştırılmıştır.
    """
    ham = govde.get(anahtar)
    if ham is None or (isinstance(ham, str) and not ham.strip()):
        return varsayilan
    try:
        return int(ham) if tam_sayi else float(ham)
    except (TypeError, ValueError) as hata:
        raise ArayuzHatasi(f"{etiket} sayı olmalıdır (verilen: {ham!r}).") from hata


def _ayari_al(govde: Dict[str, Any], azami: int) -> KarelajAyari:
    aralik = _sayi_al(govde, "aralik", 25.0, "Karelaj aralığı")
    if aralik is None or aralik <= 0:
        raise ArayuzHatasi("Karelaj aralığı sıfırdan büyük olmalıdır.")
    aralik_yukari = _sayi_al(govde, "aralik_yukari", None, "Kuzey-güney aralığı")
    if aralik_yukari is not None and aralik_yukari <= 0:
        raise ArayuzHatasi("Kuzey-güney karelaj aralığı sıfırdan büyük olmalıdır.")
    baslangic = _sayi_al(govde, "no_baslangic", 1, "İlk nokta numarası", tam_sayi=True)
    basamak = _sayi_al(govde, "no_basamak", 0, "Numara basamak sayısı", tam_sayi=True)
    return KarelajAyari(
        aralik=aralik,
        aralik_yukari=aralik_yukari,
        hizalama=govde.get("hizalama") or "tam-kat",
        donme_acisi=_sayi_al(govde, "donme", 0.0, "Döndürme açısı"),
        kirp=bool(govde.get("kirp", True)),
        tampon=_sayi_al(govde, "tampon", 0.0, "Tampon mesafesi"),
        kenar_noktalari=bool(govde.get("kose_noktalari", False)),
        siralama=govde.get("siralama") or "kuzey-guney",
        numaralandirma=NumaralandirmaAyari(
            profil=govde.get("no_profil") or "sira",
            onek=str(govde.get("no_onek") or ""),
            baslangic=int(baslangic),
            basamak=int(basamak),
        ),
        nokta_kodu=str(govde.get("kod") or ""),
        azami_nokta=azami,
    )


def _sistemi_al(govde: Dict[str, Any], alan: Alan):
    kod = (govde.get("sistem") or "otomatik").strip()
    if kod.lower() in ("otomatik", "auto", ""):
        merkez_boylam, _ = alan.merkez()
        return otomatik_sistem(merkez_boylam, "ITRF96")
    return sistem_bul(kod)


def _onizleme(govde: Dict[str, Any]) -> Dict[str, Any]:
    alan = _alani_al(govde)
    sistem = _sistemi_al(govde, alan)
    ayar = _ayari_al(govde, ONIZLEME_AZAMI_NOKTA * 40)

    tahmin = nokta_sayisi_tahmini(alan, sistem, ayar)
    if tahmin > ONIZLEME_AZAMI_NOKTA * 40:
        return {
            "nokta_sayisi": tahmin,
            "noktalar": [],
            "sistem": sistem.tanim(),
            "alan_m2": alan.alan_m2(),
            "uyari": (
                f"Yaklaşık {bicim.tam_sayi(tahmin)} nokta oluşur; önizleme için çok "
                f"fazla. Aralığı büyütün veya alanı küçültün."
            ),
        }

    karelaj = karelaj_uret(alan, sistem, ayar)
    toplam = len(karelaj.noktalar)
    adim = max(1, (toplam + ONIZLEME_AZAMI_NOKTA - 1) // ONIZLEME_AZAMI_NOKTA)
    noktalar = [
        [round(n.boylam, 7), round(n.enlem, 7)] for n in karelaj.noktalar[::adim]
    ]
    return {
        "nokta_sayisi": toplam,
        "gosterilen": len(noktalar),
        "seyreltme": adim,
        "noktalar": noktalar,
        "satir": karelaj.satir_sayisi,
        "sutun": karelaj.sutun_sayisi,
        "sistem": sistem.tanim(),
        "sistem_kod": sistem.kod,
        "alan_m2": alan.alan_m2(),
        "uyari": "",
    }


def _uret(govde: Dict[str, Any], cikti_klasoru: str) -> Dict[str, Any]:
    alan = _alani_al(govde)
    sistem = _sistemi_al(govde, alan)
    ayar = _ayari_al(govde, URETIM_AZAMI_NOKTA)
    karelaj = karelaj_uret(alan, sistem, ayar)

    kaynak_ozeti = None
    kot_kaydirma = _sayi_al(govde, "kot_kaydirma", 0.0, "Düşey kaydırma")
    if not govde.get("kot_yok"):
        kaynak = kaynak_olustur(
            govde.get("kaynak") or "opentopodata",
            veri_kumesi=govde.get("veri_kumesi") or "srtm30m",
            sunucu=govde.get("sunucu") or None,
            sym_yolu=govde.get("sym") or None,
            sym_sistemi=sistem_bul(govde["dem_sistemi"]) if govde.get("dem_sistemi") else None,
            ornekleme=govde.get("ornekleme") or "bilineer",
            google_anahtari=govde.get("google_anahtar") or None,
        )
        onbellek = KotOnbellegi(
            varsayilan_onbellek_yolu(), etkin=not govde.get("onbellek_yok")
        )
        try:
            kaynak_ozeti = kotlari_doldur(
                karelaj.noktalar, kaynak, onbellek=onbellek, kot_kaydirma=kot_kaydirma
            )
        finally:
            onbellek.kapat()
            kaynak.kapat()

    kontur_araligi = _sayi_al(govde, "kontur", None, "Eş yükselti aralığı")
    konturlar = None
    if kontur_araligi is not None:
        if kontur_araligi <= 0:
            raise ArayuzHatasi("Eş yükselti aralığı sıfırdan büyük olmalıdır.")
        konturlar = kontur_uret(karelaj, aralik=kontur_araligi)

    hacim_kotu = _sayi_al(govde, "hacim_kotu", None, "Hacim referans kotu")
    hacim = None if hacim_kotu is None else hacim_hesapla(karelaj, hacim_kotu)

    temel = _guvenli_ad(str(govde.get("ad") or "karelaj"))
    os.makedirs(cikti_klasoru, exist_ok=True)
    bicimler = govde.get("bicimler") or ["ncn", "kml", "rapor"]
    dosyalar: List[str] = []

    if "ncn" in bicimler:
        ncn_kotsuz = govde.get("ncn_kotsuz") or None
        if ncn_kotsuz is None and karelaj.eksik_kot_sayisi() == len(karelaj.noktalar):
            ncn_kotsuz = "sifir"  # kot hiç okunmadıysa dosya boş kalmasın
        ncn_ayari = profil_coz(
            govde.get("ncn_profil") or "netcad",
            sutunlar=govde.get("ncn_sutun") or None,
            ayirac=govde.get("ncn_ayirac") or None,
            kotsuz=ncn_kotsuz,
        )
        yol = os.path.join(cikti_klasoru, f"{temel}.ncn")
        ncn_yaz(yol, karelaj.noktalar, ncn_ayari)
        dosyalar.append(yol)
    if "csv" in bicimler:
        yol = os.path.join(cikti_klasoru, f"{temel}.csv")
        csv_yaz(yol, karelaj.noktalar)
        dosyalar.append(yol)
    if "xyz" in bicimler:
        yol = os.path.join(cikti_klasoru, f"{temel}.xyz")
        xyz_yaz(yol, karelaj.noktalar)
        dosyalar.append(yol)
    if "dxf" in bicimler:
        dosyalar.append(
            dxf_yaz(os.path.join(cikti_klasoru, f"{temel}.dxf"), karelaj, konturlar=konturlar)
        )
    if "kml" in bicimler:
        dosyalar.append(
            kml_yaz(os.path.join(cikti_klasoru, f"{temel}.kml"), karelaj, konturlar=konturlar,
                    baslik=alan.ad)
        )
    if "geojson" in bicimler:
        dosyalar.append(
            geojson_yaz(os.path.join(cikti_klasoru, f"{temel}.geojson"), karelaj, konturlar=konturlar)
        )

    rapor = rapor_metni(
        karelaj,
        kaynak_ozeti=kaynak_ozeti,
        hacim=hacim,
        konturlar=konturlar,
        uretilen_dosyalar=dosyalar,
        kot_kaydirma=kot_kaydirma,
    )
    if "rapor" in bicimler:
        yol = os.path.join(cikti_klasoru, f"{temel}-rapor.txt")
        rapor_yaz(
            yol,
            karelaj,
            kaynak_ozeti=kaynak_ozeti,
            hacim=hacim,
            konturlar=konturlar,
            uretilen_dosyalar=dosyalar,
            kot_kaydirma=kot_kaydirma,
        )
        dosyalar.append(yol)

    istatistik = karelaj.kot_istatistikleri()
    return {
        "nokta_sayisi": len(karelaj.noktalar),
        "satir": karelaj.satir_sayisi,
        "sutun": karelaj.sutun_sayisi,
        "sistem": sistem.tanim(),
        "alan_m2": alan.alan_m2(),
        "istatistik": {a: round(b, 3) for a, b in istatistik.items()},
        "eksik_kot": karelaj.eksik_kot_sayisi(),
        "okuma_ozeti": kaynak_ozeti.ozet_satiri() if kaynak_ozeti else "",
        "uyarilar": kaynak_ozeti.uyarilar if kaynak_ozeti else [],
        "kontur_sayisi": len(konturlar) if konturlar else 0,
        "hacim": hacim.ozet() if hacim else [],
        "rapor": rapor,
        "dosyalar": [
            {
                "ad": os.path.basename(d),
                "boyut": os.path.getsize(d),
                "baglanti": "/indir?dosya=" + urllib.parse.quote(os.path.basename(d)),
            }
            for d in dosyalar
        ],
        "klasor": os.path.abspath(cikti_klasoru),
    }


def _guvenli_ad(ad: str) -> str:
    """Dosya adından yol ayırıcıları ve sorunlu karakterleri temizler."""
    temiz = "".join(
        karakter if karakter.isalnum() or karakter in "-_ğüşıöçĞÜŞİÖÇ " else "-"
        for karakter in ad.strip()
    ).strip("-. ")
    return (temiz or "karelaj")[:80]


# ---------------------------------------------------------------------------
# Başlatma
# ---------------------------------------------------------------------------


def arayuzu_baslat(
    adres: str = "127.0.0.1",
    kapi: int = 8777,
    tarayici_ac: bool = True,
    cikti_klasoru: str = "cikti",
) -> int:
    """Yerel arayüz sunucusunu başlatır ve Ctrl+C'ye kadar çalıştırır."""
    if not os.path.exists(_web_dosyasi("index.html")):
        print(
            "HATA: Arayüz dosyası bulunamadı (karelaj/web/index.html).",
            file=sys.stderr,
        )
        return 2
    os.makedirs(cikti_klasoru, exist_ok=True)

    isleyici = type("_YapilandirilmisIsleyici", (_Isleyici,), {"cikti_klasoru": cikti_klasoru})
    try:
        sunucu = ThreadingHTTPServer((adres, kapi), isleyici)
    except OSError as hata:
        print(
            f"HATA: {adres}:{kapi} dinlenemedi ({hata}). "
            f"Başka bir kapı deneyin: --kapi 8778",
            file=sys.stderr,
        )
        return 2

    baglanti = f"http://{adres}:{sunucu.server_address[1]}/"
    print("=" * 66)
    print("  KOT KARELAJI - harita arayüzü")
    print("=" * 66)
    print(f"  Adres        : {baglanti}")
    print(f"  Çıktı klasörü: {os.path.abspath(cikti_klasoru)}")
    print("  Durdurmak için Ctrl+C")
    print("=" * 66)
    # Paketlenmiş uygulamada ya da çıktı bir dosyaya yönlendirildiğinde
    # arabellek nedeniyle adresin geç görünmemesi için hemen boşaltılır.
    sys.stdout.flush()

    if tarayici_ac:
        threading.Timer(0.6, lambda: webbrowser.open(baglanti)).start()
    try:
        sunucu.serve_forever()
    except KeyboardInterrupt:
        print("\nArayüz kapatıldı.")
    finally:
        sunucu.server_close()
    return 0
