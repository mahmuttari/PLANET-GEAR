/**
 * WhatsApp "Sohbeti Dışa Aktar" Yedeği Ayıklayıcı
 * ------------------------------------------------
 * WhatsApp sunucularında süresi dolduğu için index.js ile indirilemeyen çok
 * eski medyalar, telefonda hâlâ mevcutsa şu yöntemle eksiksiz alınabilir:
 *
 *   Telefonda: Grup > Grup adına dokun > Sohbeti Dışa Aktar > "Medya Dahil"
 *   (iPhone: Grup > Grup adı > Sohbeti Dışa Aktar > Medya Ekle)
 *
 * Oluşan ZIP dosyasını bilgisayara aktarıp bir klasöre ÇIKARTIN, sonra:
 *
 *   node export-ayikla.js <çıkartılan-klasör-yolu> [hedef-klasör]
 *
 * Betik, klasördeki TÜM PDF ve resim dosyalarını bulur; sohbet dökümünden
 * (_chat.txt) tarih ve gönderen bilgisini eşleştirerek Yıl-Ay klasörlerine
 * anlamlı adlarla kopyalar ve rapor üretir.
 */

const fs = require('fs');
const path = require('path');

const RESIM_UZANTILARI = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tif', '.tiff', '.heic', '.heif'];
const PDF_UZANTILARI = ['.pdf'];
const KABUL_EDILEN = new Set([...RESIM_UZANTILARI, ...PDF_UZANTILARI]);

function dosyaAdiTemizle(ad) {
    return String(ad)
        .replace(/[\\/:*?"<>|\r\n\t]+/g, '_')
        .replace(/\s+/g, ' ')
        .trim()
        .slice(0, 120);
}

function csvAlan(deger) {
    const s = String(deger == null ? '' : deger);
    if (/[";\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
    return s;
}

/** Klasörü (alt klasörler dahil) gezerek tüm dosyaları döndürür. */
function dosyalariTara(klasor) {
    const sonuc = [];
    for (const girdi of fs.readdirSync(klasor, { withFileTypes: true })) {
        const tamYol = path.join(klasor, girdi.name);
        if (girdi.isDirectory()) sonuc.push(...dosyalariTara(tamYol));
        else sonuc.push(tamYol);
    }
    return sonuc;
}

/**
 * Sohbet dökümü (_chat.txt veya "WhatsApp ... .txt") satırlarından
 * "dosyaAdı -> { tarih, gönderen }" eşlemesi çıkarır.
 *
 * Desteklenen biçim örnekleri:
 *  Android : "12.05.2023 14:30 - Ahmet Yılmaz: IMG-20230512-WA0001.jpg (dosya ekli)"
 *  iOS     : "[12.05.2023 14:30:05] Ahmet Yılmaz: <ekli: 00000123-PHOTO-....jpg>"
 *  İngilizce: "... <attached: ...>" / "... (file attached)"
 */
function sohbetDokumunuIsle(dokumYolu, medyaAdlari) {
    const eslesme = new Map();
    if (!dokumYolu) return eslesme;

    const metin = fs.readFileSync(dokumYolu, 'utf8');
    // iOS dökümlerinde görünmez yön karakterleri bulunur, temizle
    const satirlar = metin.replace(/[\u200e\u200f\u202a-\u202e]/g, '').split(/\r?\n/);

    // Tarih ve gönderen yakalama: hem "[t] ad:" hem "t - ad:" biçimleri
    const satirDeseni = /^\[?(\d{1,2}[./]\d{1,2}[./]\d{2,4})[,\s]+(\d{1,2}[:.]\d{2}(?:[:.]\d{2})?)\]?\s*[-–]?\s*([^:]+):\s*(.*)$/;

    for (const satir of satirlar) {
        const e = satir.match(satirDeseni);
        if (!e) continue;
        const [, tarih, saat, gonderen, icerik] = e;
        // Satırda geçen medya dosya adlarını ara
        for (const ad of medyaAdlari) {
            if (icerik.includes(ad) && !eslesme.has(ad)) {
                eslesme.set(ad, { tarih, saat, gonderen: gonderen.trim() });
            }
        }
    }
    return eslesme;
}

/** "12.05.2023" + "14:30:05" -> "2023-05-12_14-30-05" ve "2023-05" üretir. */
function tarihDamgasi(tarih, saat) {
    const p = tarih.split(/[./]/).map(Number);
    let [gun, ay, yil] = p;
    if (yil < 100) yil += 2000;
    const s = (saat || '00:00').split(/[:.]/).map((x) => String(x).padStart(2, '0'));
    while (s.length < 3) s.push('00');
    const iki = (n) => String(n).padStart(2, '0');
    return {
        damga: `${yil}-${iki(ay)}-${iki(gun)}_${s[0]}-${s[1]}-${s[2]}`,
        yilAy: `${yil}-${iki(ay)}`,
    };
}

function main() {
    const kaynakKlasor = process.argv[2];
    const hedefKlasor = process.argv[3] || path.join(__dirname, 'indirilenler', 'yedekten');

    if (!kaynakKlasor) {
        console.error('Kullanım: node export-ayikla.js <çıkartılan-yedek-klasörü> [hedef-klasör]');
        console.error('Örnek   : node export-ayikla.js "C:\\Users\\ben\\Desktop\\WhatsApp Chat - Dsi TBMM Masraf"');
        process.exit(1);
    }
    if (!fs.existsSync(kaynakKlasor) || !fs.statSync(kaynakKlasor).isDirectory()) {
        console.error(`✖ Klasör bulunamadı: ${kaynakKlasor}`);
        console.error('  Not: ZIP dosyasını önce bir klasöre çıkartın, ZIP\'in kendisini değil');
        console.error('  çıkartılan klasörün yolunu verin.');
        process.exit(1);
    }

    console.log(`Kaynak: ${kaynakKlasor}`);
    console.log(`Hedef : ${hedefKlasor}\n`);

    const tumDosyalar = dosyalariTara(kaynakKlasor);
    const medyaDosyalari = tumDosyalar.filter((d) => KABUL_EDILEN.has(path.extname(d).toLowerCase()));
    const dokumYolu = tumDosyalar.find((d) => path.extname(d).toLowerCase() === '.txt');

    console.log(`✔ ${medyaDosyalari.length} adet PDF/resim dosyası bulundu.`);
    console.log(dokumYolu
        ? `✔ Sohbet dökümü bulundu: ${path.basename(dokumYolu)} (tarih/gönderen eşleştirilecek)`
        : '– Sohbet dökümü (.txt) bulunamadı; dosyalar özgün adlarıyla kopyalanacak.');

    const medyaAdlari = medyaDosyalari.map((d) => path.basename(d));
    const eslesme = sohbetDokumunuIsle(dokumYolu, medyaAdlari);

    const raporSatirlari = [];
    let kopyalanan = 0;

    for (const kaynakDosya of medyaDosyalari) {
        const ad = path.basename(kaynakDosya);
        const bilgi = eslesme.get(ad);

        let altKlasor = 'tarihsiz';
        let yeniAd = dosyaAdiTemizle(ad);
        if (bilgi) {
            const t = tarihDamgasi(bilgi.tarih, bilgi.saat);
            altKlasor = t.yilAy;
            yeniAd = `${t.damga}_${dosyaAdiTemizle(bilgi.gonderen)}_${dosyaAdiTemizle(path.parse(ad).name)}${path.extname(ad).toLowerCase()}`;
        }

        const hedefAltKlasor = path.join(hedefKlasor, altKlasor);
        fs.mkdirSync(hedefAltKlasor, { recursive: true });

        let hedefYol = path.join(hedefAltKlasor, yeniAd);
        let sayac = 1;
        while (fs.existsSync(hedefYol)) {
            const parcali = path.parse(yeniAd);
            hedefYol = path.join(hedefAltKlasor, `${parcali.name}_(${sayac})${parcali.ext}`);
            sayac++;
        }

        fs.copyFileSync(kaynakDosya, hedefYol);
        kopyalanan++;
        raporSatirlari.push([
            bilgi ? `${bilgi.tarih} ${bilgi.saat}` : '',
            bilgi ? bilgi.gonderen : '',
            ad,
            path.relative(hedefKlasor, hedefYol),
        ]);
        console.log(`✔ ${path.relative(hedefKlasor, hedefYol)}`);
    }

    const raporYolu = path.join(hedefKlasor, 'rapor.csv');
    const baslik = 'Tarih;Gönderen;Özgün Dosya Adı;Kopyalanan Dosya';
    const csv = [baslik, ...raporSatirlari.map((s) => s.map(csvAlan).join(';'))].join('\r\n');
    fs.mkdirSync(hedefKlasor, { recursive: true });
    fs.writeFileSync(raporYolu, '﻿' + csv, 'utf8');

    console.log('\n==========================================================');
    console.log(`  Kopyalanan PDF/resim : ${kopyalanan}`);
    console.log(`  Rapor                : ${raporYolu}`);
    console.log('==========================================================');
}

main();
