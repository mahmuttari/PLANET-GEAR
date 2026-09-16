# -*- coding: utf-8 -*-
"""
Teknik özet raporu
==================

Üretilen karelajın teknik dökümünü, mühendislik evrakına eklenebilecek
düzende bir metin dosyası olarak yazar. Rapor; çalışma alanı, koordinat
sistemi ve datum bilgisi, karelaj parametreleri, kot kaynağı ve düşey
datum uyarısı, kot istatistikleri ile (istenmişse) hacim hesabını içerir.
"""

from __future__ import annotations

import datetime as _dt
import os
from typing import List, Optional, Sequence

from .. import bicim

__all__ = ["rapor_metni", "rapor_yaz"]

_CIZGI = "=" * 72
_ALT_CIZGI = "-" * 72


def rapor_metni(
    karelaj,
    kaynak_ozeti=None,
    hacim=None,
    konturlar: Optional[Sequence] = None,
    uretilen_dosyalar: Optional[Sequence[str]] = None,
    kot_kaydirma: float = 0.0,
    komut: str = "",
) -> str:
    sistem = karelaj.sistem
    ayar = karelaj.ayar
    alan = karelaj.alan
    kutu = alan.sinir_kutusu()
    istatistik = karelaj.kot_istatistikleri()

    s: List[str] = []
    s.append(_CIZGI)
    s.append("KOT KARELAJI TEKNİK ÖZET RAPORU".center(72))
    s.append(_CIZGI)
    s.append(f"Rapor tarihi          : {_dt.datetime.now().strftime('%d.%m.%Y %H:%M')}")
    s.append(f"Çalışma alanı         : {alan.ad}")
    if alan.kaynak and alan.kaynak != "sınır kutusu":
        s.append(f"Alan kaynağı          : {alan.kaynak}")
    s.append("")

    s.append("1. ÇALIŞMA ALANI")
    s.append(_ALT_CIZGI)
    s.append(f"Sınır köşe sayısı     : {bicim.tam_sayi(sum(len(h) for h in alan.halkalar))}")
    s.append(f"İç boşluk (ada) sayısı: {len(alan.ic_halkalar)}")
    s.append(
        f"Coğrafi sınırlar      : "
        f"enlem {bicim.sayi(kutu.min_enlem, 6)}° - {bicim.sayi(kutu.max_enlem, 6)}°, "
        f"boylam {bicim.sayi(kutu.min_boylam, 6)}° - {bicim.sayi(kutu.max_boylam, 6)}°"
    )
    s.append(f"Elipsoidal yüzey alanı: {bicim.alan_metni(alan.alan_m2())}")
    merkez_boylam, merkez_enlem = alan.merkez()
    s.append(f"Alan ağırlık merkezi  : {bicim.sayi(merkez_enlem, 6)}° K, {bicim.sayi(merkez_boylam, 6)}° D")
    s.append("")

    s.append("2. KOORDİNAT SİSTEMİ")
    s.append(_ALT_CIZGI)
    s.append(f"Sistem                : {sistem.ad}")
    s.append(f"Kod / EPSG            : {sistem.kod}" + (f" / EPSG:{sistem.epsg}" if sistem.epsg else ""))
    s.append(f"Datum                 : {sistem.datum.ad}")
    s.append(f"Elipsoit              : {sistem.datum.elipsoit.ad} "
             f"(a = {bicim.sayi(sistem.datum.elipsoit.a, 1)} m, "
             f"1/f = {bicim.sayi(sistem.datum.elipsoit.ters_basiklik, 9)})")
    if sistem.projeksiyon is not None:
        p = sistem.projeksiyon
        s.append(f"İzdüşüm               : Transverse Mercator (Gauss-Krüger)")
        s.append(f"Orta meridyen         : {p.orta_meridyen:g}°" +
                 (f"  (3° dilim {sistem.dilim})" if sistem.dilim and sistem.dilim <= 15 else ""))
        s.append(f"Ölçek faktörü (k0)    : {p.olcek:g}")
        s.append(f"Sağa kaydırma         : {bicim.sayi(p.saga_kaydirma, 1)} m")
        try:
            olcek = p.olcek_faktoru(merkez_enlem, merkez_boylam)
            yakinsama = p.meridyen_yakinsamasi(merkez_enlem, merkez_boylam)
            s.append(f"Alan merkezinde nokta ölçek faktörü : {bicim.sayi(olcek, 8)}")
            s.append(f"Alan merkezinde meridyen yakınsaması: "
                     f"{'+' if yakinsama >= 0 else '-'}{bicim.sayi(abs(yakinsama), 6)}° "
                     f"({'+' if yakinsama >= 0 else '-'}{bicim.sayi(abs(yakinsama) * 60, 2)}')")
        except Exception:
            pass
    if sistem.datum.not_:
        s.append(f"Datum notu            : {sistem.datum.not_}")
    if not sistem.datum.wgs84_helmert.birim_yok:
        s.append(f"WGS84 dönüşümü        : {sistem.datum.wgs84_helmert.aciklama()}")
    s.append("")

    s.append("3. KARELAJ PARAMETRELERİ")
    s.append(_ALT_CIZGI)
    aralik_y = ayar.etkin_aralik_yukari()
    if abs(aralik_y - ayar.aralik) < 1e-9:
        s.append(f"Karelaj aralığı       : {ayar.aralik:g} m x {ayar.aralik:g} m")
    else:
        s.append(f"Karelaj aralığı       : {ayar.aralik:g} m (doğu-batı) x {aralik_y:g} m (kuzey-güney)")
    s.append(f"Hizalama              : " + (
        "aralığın tam katlarına oturtuldu" if ayar.hizalama == "tam-kat"
        else "alanın güneybatı köşesinden başlatıldı"))
    s.append(f"Döndürme açısı        : {ayar.donme_acisi:g}°")
    s.append(f"Alan sınırına kırpma  : " + ("evet" if ayar.kirp else "hayır"))
    if ayar.tampon:
        s.append(f"Tampon mesafesi       : {ayar.tampon:g} m")
    s.append(f"Satır x sütun         : {karelaj.satir_sayisi} x {karelaj.sutun_sayisi}")
    s.append(f"Üretilen nokta sayısı : "
             f"{bicim.tam_sayi(karelaj.satir_sayisi * karelaj.sutun_sayisi)} "
             f"(kırpma sonrası {bicim.tam_sayi(len(karelaj.noktalar))})")
    s.append(f"Nokta numaralandırma  : {ayar.numaralandirma.profil}"
             + (f", önek '{ayar.numaralandirma.onek}'" if ayar.numaralandirma.onek else ""))
    s.append(f"Bir karenin alanı     : {bicim.sayi(ayar.aralik * aralik_y)} m²")
    s.append("")

    s.append("4. KOT KAYNAĞI VE DÜŞEY DATUM")
    s.append(_ALT_CIZGI)
    if kaynak_ozeti is not None:
        s.append(f"Kaynak                : {kaynak_ozeti.kaynak_tanimi}")
        s.append(f"Okuma özeti           : {kaynak_ozeti.ozet_satiri()}")
        for uyari in kaynak_ozeti.uyarilar:
            s.append(f"  ! Uyarı: {uyari}")
    else:
        s.append("Kaynak                : (kot okunmadı)")
    if kot_kaydirma:
        s.append(f"Uygulanan kot kaydırması: {'+' if kot_kaydirma >= 0 else '-'}{bicim.sayi(abs(kot_kaydirma), 3)} m")
    s.append("")
    s.append("UYARI: Çevrimiçi küresel yükseklik modelleri (SRTM, ASTER, Copernicus)")
    s.append("EGM96/EGM2008 jeoidine dayalı ortometrik kot verir. Türkiye Ulusal Düşey")
    s.append("Kontrol Ağı (TUDKA-99) kotlarıyla aralarında bölgesel olarak desimetre")
    s.append("mertebesinde sistematik fark bulunabilir. Kesin proje kotu gerektiren")
    s.append("işlerde bu fark, sahadaki nivelman/RS noktalarından belirlenip")
    s.append("--kot-kaydirma ile uygulanmalı; mümkünse kurumun kendi hâlihazır")
    s.append("SYM verisi (--kaynak yerel) kullanılmalıdır.")
    s.append("")

    s.append("5. KOT İSTATİSTİKLERİ")
    s.append(_ALT_CIZGI)
    if istatistik:
        s.append(f"Kotlu nokta sayısı    : {bicim.tam_sayi(int(istatistik['adet']))}")
        s.append(f"En düşük kot          : {bicim.sayi(istatistik['en_dusuk'], 3)} m")
        s.append(f"En yüksek kot         : {bicim.sayi(istatistik['en_yuksek'], 3)} m")
        s.append(f"Yükseklik farkı       : {bicim.sayi(istatistik['yukseklik_farki'], 3)} m")
        s.append(f"Ortalama kot          : {bicim.sayi(istatistik['ortalama'], 3)} m")
        s.append(f"Ortanca kot           : {bicim.sayi(istatistik['ortanca'], 3)} m")
        s.append(f"Standart sapma        : {bicim.sayi(istatistik['standart_sapma'], 3)} m")
        eksik = karelaj.eksik_kot_sayisi()
        if eksik:
            s.append(f"Kot okunamayan nokta  : {bicim.tam_sayi(eksik)}")
    else:
        s.append("Kot okunmadı.")
    s.append("")

    if konturlar:
        kotlar = sorted({e.kot for e in konturlar})
        s.append("6. EŞ YÜKSELTİ EĞRİLERİ")
        s.append(_ALT_CIZGI)
        s.append(f"Eğri parçası sayısı   : {bicim.tam_sayi(len(konturlar))}")
        s.append(f"Eş yükselti sayısı    : {bicim.tam_sayi(len(kotlar))}")
        if kotlar:
            s.append(f"Kot aralığı           : {bicim.sayi(kotlar[0])} m - "
                     f"{bicim.sayi(kotlar[-1])} m")
            toplam = sum(e.uzunluk for e in konturlar)
            s.append(f"Toplam eğri uzunluğu  : {bicim.sayi(toplam)} m")
        s.append("")

    if hacim is not None:
        s.append(("7." if konturlar else "6.") + " KARELAJ YÖNTEMİYLE HACİM HESABI")
        s.append(_ALT_CIZGI)
        s.extend(hacim.ozet())
        s.append("")
        s.append("Not: Kazı ve dolgu hacimleri, her karenin alt bölmelere ayrılıp köşe")
        s.append(f"kotlarından çift doğrusal ara değerle ({hacim.alt_bolme}x{hacim.alt_bolme} alt kare)")
        s.append("hesaplanmasıyla bulunmuştur. Klasik karelaj (ortalama yükseklik)")
        s.append("yöntemi yalnızca net hacmi doğru verir; karışık karelerde kazı ve")
        s.append("dolguyu ayırmaz, bu nedenle karşılaştırma amacıyla ayrıca yazılmıştır.")
        s.append("")

    if uretilen_dosyalar:
        s.append("ÜRETİLEN DOSYALAR")
        s.append(_ALT_CIZGI)
        for dosya in uretilen_dosyalar:
            try:
                boyut = os.path.getsize(dosya)
                s.append(f"  {os.path.basename(dosya)}  ({bicim.sayi(boyut / 1024.0, 1)} KB)")
            except OSError:
                s.append(f"  {os.path.basename(dosya)}")
        s.append("")

    if komut:
        s.append("ÇALIŞTIRILAN KOMUT")
        s.append(_ALT_CIZGI)
        s.append(komut)
        s.append("")

    s.append(_CIZGI)
    return "\n".join(s) + "\n"


def rapor_yaz(yol: str, *args, **kwargs) -> str:
    """``rapor_metni`` çıktısını dosyaya yazar."""
    metin = rapor_metni(*args, **kwargs)
    klasor = os.path.dirname(os.path.abspath(yol))
    if klasor:
        os.makedirs(klasor, exist_ok=True)
    with open(yol, "wb") as f:
        f.write(metin.encode("utf-8"))
    return yol
