/**
 * WhatsApp Masraf Fiş/Dekont İndirici
 * ------------------------------------
 * "Dsi TBMM Termal Masraf" grubunda, grubun kurulduğu ilk günden bu yana paylaşılmış
 * TÜM PDF ve resim (fotoğraf) formatındaki masraf fişi/dekontlarını bulur ve
 * bilgisayara indirir.
 *
 * Çalışma mantığı:
 *  1. WhatsApp Web üzerinden QR kod ile oturum açılır (oturum kaydedilir,
 *     sonraki çalıştırmalarda QR gerekmez).
 *  2. Grup, adına göre bulunur.
 *  3. Grubun tüm mesaj geçmişi (en eskiden en yeniye) parça parça yüklenir.
 *  4. Resim ve PDF içeren mesajların medyaları indirilir; tarih + gönderen +
 *     orijinal dosya adı ile Yıl-Ay klasörlerine kaydedilir.
 *  5. Daha önce indirilenler durum dosyasında tutulur; betik tekrar
 *     çalıştırıldığında kaldığı yerden devam eder (yeniden indirmez).
 *  6. Sonuçlar "rapor.csv" dosyasına yazılır; indirilemeyen (süresi dolmuş)
 *     medyalar ayrıca listelenir.
 */

const fs = require('fs');
const path = require('path');
const qrcode = require('qrcode-terminal');
const { Client, LocalAuth } = require('whatsapp-web.js');
const ayarlar = require('./config');

// ---------------------------------------------------------------------------
// Yardımcı fonksiyonlar
// ---------------------------------------------------------------------------

function bekle(ms) {
    return new Promise((coz) => setTimeout(coz, ms));
}

/** Dosya adı olarak kullanılamayan karakterleri temizler. */
function dosyaAdiTemizle(ad) {
    return String(ad)
        .replace(/[\\/:*?"<>|\r\n\t]+/g, '_')
        .replace(/\s+/g, ' ')
        .trim()
        .slice(0, 120);
}

/** MIME türünden dosya uzantısı üretir. */
function mimeUzantisi(mime) {
    const tablo = {
        'application/pdf': 'pdf',
        'image/jpeg': 'jpg',
        'image/jpg': 'jpg',
        'image/png': 'png',
        'image/webp': 'webp',
        'image/gif': 'gif',
        'image/bmp': 'bmp',
        'image/tiff': 'tif',
        'image/heic': 'heic',
        'image/heif': 'heif',
    };
    if (tablo[mime]) return tablo[mime];
    if (mime && mime.startsWith('image/')) return mime.split('/')[1].split(';')[0];
    return 'bin';
}

/** Unix zaman damgasını (saniye) okunabilir bileşenlere çevirir. */
function tarihBilgisi(unixSaniye) {
    const t = new Date(unixSaniye * 1000);
    const iki = (n) => String(n).padStart(2, '0');
    return {
        yilAy: `${t.getFullYear()}-${iki(t.getMonth() + 1)}`,
        damga: `${t.getFullYear()}-${iki(t.getMonth() + 1)}-${iki(t.getDate())}_${iki(t.getHours())}-${iki(t.getMinutes())}-${iki(t.getSeconds())}`,
        okunur: t.toLocaleString('tr-TR'),
    };
}

/** MIME türü kabul listemizde mi? (resimler + PDF) */
function mimeKabulEdiliyorMu(mime) {
    if (!mime) return false;
    if (ayarlar.KABUL_EDILEN_MIME_TURLERI.includes(mime)) return true;
    return ayarlar.KABUL_EDILEN_MIME_ONEKLERI.some((onek) => mime.startsWith(onek));
}

/** CSV alanını güvenli hâle getirir. */
function csvAlan(deger) {
    const s = String(deger == null ? '' : deger);
    if (/[";\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
    return s;
}

// ---------------------------------------------------------------------------
// Durum (kaldığı yerden devam) yönetimi
// ---------------------------------------------------------------------------

const DURUM_DOSYASI = path.join(ayarlar.INDIRME_KLASORU, '.durum.json');

function durumOku() {
    try {
        return JSON.parse(fs.readFileSync(DURUM_DOSYASI, 'utf8'));
    } catch {
        return { indirilenler: {}, basarisizlar: {} };
    }
}

function durumYaz(durum) {
    fs.mkdirSync(ayarlar.INDIRME_KLASORU, { recursive: true });
    fs.writeFileSync(DURUM_DOSYASI, JSON.stringify(durum, null, 2), 'utf8');
}

// ---------------------------------------------------------------------------
// Ana akış
// ---------------------------------------------------------------------------

async function main() {
    const kutuphaneSurumu = require('whatsapp-web.js/package.json').version;
    console.log('==========================================================');
    console.log('  WhatsApp Masraf Fiş/Dekont İndirici');
    console.log(`  Hedef grup : "${ayarlar.GRUP_ADI}"`);
    console.log(`  Kayıt yeri : ${ayarlar.INDIRME_KLASORU}`);
    console.log(`  Kütüphane  : whatsapp-web.js ${kutuphaneSurumu}`);
    console.log('==========================================================\n');

    if (kutuphaneSurumu.startsWith('1.2')) {
        console.log('UYARI: whatsapp-web.js sürümünüz eski. Güncel WhatsApp Web ile');
        console.log('uyumsuzluk yaşarsanız şu komutla güncelleyin:');
        console.log('  npm install whatsapp-web.js@latest\n');
    }

    fs.mkdirSync(ayarlar.INDIRME_KLASORU, { recursive: true });

    const puppeteerAyarlari = {
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
    };
    if (ayarlar.CHROME_YOLU) {
        puppeteerAyarlari.executablePath = ayarlar.CHROME_YOLU;
    }

    const istemciAyarlari = {
        authStrategy: new LocalAuth({ dataPath: ayarlar.OTURUM_KLASORU }),
        puppeteer: puppeteerAyarlari,
    };
    if (ayarlar.WEB_SURUMU && ayarlar.WEB_SURUMU !== 'guncel') {
        console.log(`WhatsApp Web sürümü sabitlendi: ${ayarlar.WEB_SURUMU}\n`);
        istemciAyarlari.webVersion = ayarlar.WEB_SURUMU;
        istemciAyarlari.webVersionCache = {
            type: 'remote',
            remotePath: `https://raw.githubusercontent.com/wppconnect-team/wa-version/main/html/${ayarlar.WEB_SURUMU}.html`,
        };
    }
    const istemci = new Client(istemciAyarlari);

    istemci.on('qr', (qr) => {
        console.log('Telefonunuzdaki WhatsApp > Bağlı Cihazlar > Cihaz Bağla');
        console.log('menüsünden aşağıdaki QR kodu okutun:\n');
        qrcode.generate(qr, { small: true });
    });

    istemci.on('authenticated', () => console.log('✔ Oturum doğrulandı.'));
    istemci.on('auth_failure', (m) => {
        console.error('✖ Oturum açılamadı:', m);
        process.exit(1);
    });

    istemci.on('ready', async () => {
        try {
            await grubuIsleyip_indir(istemci);
        } catch (hata) {
            console.error('✖ Beklenmeyen hata:', hata);
        } finally {
            await istemci.destroy();
            process.exit(0);
        }
    });

    await istemci.initialize();
}

async function grubuIsleyip_indir(istemci) {
    console.log('\nSohbet listesi alınıyor...');

    // WhatsApp Web bazen "ready" olayından hemen sonra sohbet deposunu tam
    // yüklememiş olur; bu yüzden birkaç kez, aralıklı olarak deneriz.
    let sohbetler = null;
    let sonHata = null;
    for (let deneme = 1; deneme <= 5; deneme++) {
        try {
            sohbetler = await istemci.getChats();
            break;
        } catch (h) {
            sonHata = h;
            console.log(`  ... sohbet listesi henüz hazır değil (deneme ${deneme}/5), 5 sn bekleniyor`);
            await bekle(5000);
        }
    }
    if (!sohbetler) {
        console.error('✖ Sohbet listesi alınamadı:', sonHata && sonHata.message);
        console.error('  Bu hata genellikle whatsapp-web.js kütüphanesinin WhatsApp Web\'in');
        console.error('  güncel sürümüyle uyumsuz kalmasından kaynaklanır. Proje klasöründe');
        console.error('  şu komutu çalıştırıp tekrar deneyin: npm install whatsapp-web.js@latest');
        return;
    }

    const hedefAd = ayarlar.GRUP_ADI.trim().toLocaleLowerCase('tr-TR');
    const grup = sohbetler.find(
        (s) => s.isGroup && s.name && s.name.trim().toLocaleLowerCase('tr-TR') === hedefAd
    );

    if (!grup) {
        console.error(`✖ "${ayarlar.GRUP_ADI}" adında bir grup bulunamadı.`);
        console.error('  Üyesi olduğunuz gruplar:');
        sohbetler.filter((s) => s.isGroup).forEach((s) => console.error(`   - ${s.name}`));
        return;
    }

    console.log(`✔ Grup bulundu: "${grup.name}"`);
    console.log('\nGrubun kurulduğu ilk günden itibaren TÜM mesaj geçmişi yükleniyor.');
    console.log('(Mesaj sayısına göre bu işlem uzun sürebilir, lütfen bekleyin...)\n');

    // fetchMessages, verilen limite ulaşana ya da daha eski mesaj kalmayana
    // kadar geçmişi parça parça yükler. Limiti grubun toplam mesaj sayısından
    // büyük tuttuğumuz için ulaşılabilen en eski mesaja kadar gidilir.
    const mesajlar = await grup.fetchMessages({ limit: ayarlar.AZAMI_MESAJ_SAYISI });
    console.log(`✔ Toplam ${mesajlar.length} mesaj yüklendi.`);

    // En eskiden en yeniye sırala
    mesajlar.sort((a, b) => a.timestamp - b.timestamp);
    if (mesajlar.length > 0) {
        console.log(`  En eski mesaj  : ${tarihBilgisi(mesajlar[0].timestamp).okunur}`);
        console.log(`  En yeni mesaj  : ${tarihBilgisi(mesajlar[mesajlar.length - 1].timestamp).okunur}\n`);
    }

    // Yalnızca resim ve belge (PDF vb.) içeren mesajlar
    const medyaliMesajlar = mesajlar.filter(
        (m) => m.hasMedia && (m.type === 'image' || m.type === 'document')
    );
    console.log(`✔ ${medyaliMesajlar.length} adet resim/belge içeren mesaj tespit edildi.\n`);

    const durum = durumOku();
    const raporSatirlari = [];
    let indirilen = 0;
    let atlanan = 0;
    let basarisiz = 0;
    let kapsamDisi = 0;

    for (let i = 0; i < medyaliMesajlar.length; i++) {
        const mesaj = medyaliMesajlar[i];
        const mesajId = mesaj.id ? mesaj.id._serialized : `bilinmeyen_${i}`;
        const tarih = tarihBilgisi(mesaj.timestamp);
        const ilerleme = `[${i + 1}/${medyaliMesajlar.length}]`;

        // Daha önce indirilmişse atla
        if (durum.indirilenler[mesajId]) {
            atlanan++;
            continue;
        }

        // Gönderen bilgisi
        let gonderen = 'Bilinmeyen';
        try {
            const kisi = await mesaj.getContact();
            gonderen = kisi.pushname || kisi.name || kisi.number || 'Bilinmeyen';
        } catch {
            /* gönderen alınamazsa varsayılan kalır */
        }

        // Medyayı indir (başarısız olursa yeniden dene)
        let medya = null;
        let sonHata = '';
        for (let deneme = 1; deneme <= ayarlar.YENIDEN_DENEME_SAYISI; deneme++) {
            try {
                medya = await mesaj.downloadMedia();
                if (medya && medya.data) break;
                sonHata = 'Medya sunucudan boş döndü (süresi dolmuş olabilir)';
            } catch (h) {
                sonHata = h.message || String(h);
            }
            medya = null;
            if (deneme < ayarlar.YENIDEN_DENEME_SAYISI) {
                await bekle(ayarlar.YENIDEN_DENEME_BEKLEME_MS);
            }
        }

        if (!medya || !medya.data) {
            basarisiz++;
            durum.basarisizlar[mesajId] = {
                tarih: tarih.okunur,
                gonderen,
                tur: mesaj.type,
                hata: sonHata,
            };
            console.log(`${ilerleme} ✖ İNDİRİLEMEDİ | ${tarih.okunur} | ${gonderen} | ${sonHata}`);
            raporSatirlari.push([tarih.okunur, gonderen, mesaj.type, '', 'BAŞARISIZ', sonHata]);
            durumYaz(durum);
            continue;
        }

        // Yalnızca resim ve PDF kabul et (ör. Word/Excel belgeleri kapsam dışı)
        if (!mimeKabulEdiliyorMu(medya.mimetype)) {
            kapsamDisi++;
            console.log(`${ilerleme} – Kapsam dışı tür atlandı (${medya.mimetype}) | ${tarih.okunur}`);
            raporSatirlari.push([tarih.okunur, gonderen, mesaj.type, medya.filename || '', 'KAPSAM DIŞI', medya.mimetype]);
            continue;
        }

        // Dosya adını oluştur: Tarih_Gönderen_OrijinalAd.uzantı
        const uzanti = mimeUzantisi(medya.mimetype);
        const orijinalAd = medya.filename
            ? dosyaAdiTemizle(path.parse(medya.filename).name)
            : mesajId.slice(-12);
        const dosyaAdi = `${tarih.damga}_${dosyaAdiTemizle(gonderen)}_${orijinalAd}.${uzanti}`;

        // Yıl-Ay alt klasörüne kaydet
        const hedefKlasor = path.join(ayarlar.INDIRME_KLASORU, tarih.yilAy);
        fs.mkdirSync(hedefKlasor, { recursive: true });

        let hedefYol = path.join(hedefKlasor, dosyaAdi);
        let sayac = 1;
        while (fs.existsSync(hedefYol)) {
            hedefYol = path.join(hedefKlasor, `${path.parse(dosyaAdi).name}_(${sayac}).${uzanti}`);
            sayac++;
        }

        fs.writeFileSync(hedefYol, Buffer.from(medya.data, 'base64'));
        indirilen++;
        delete durum.basarisizlar[mesajId];
        durum.indirilenler[mesajId] = {
            dosya: path.relative(ayarlar.INDIRME_KLASORU, hedefYol),
            tarih: tarih.okunur,
            gonderen,
        };
        durumYaz(durum);

        console.log(`${ilerleme} ✔ ${path.basename(hedefYol)}`);
        raporSatirlari.push([tarih.okunur, gonderen, mesaj.type, path.relative(ayarlar.INDIRME_KLASORU, hedefYol), 'İNDİRİLDİ', '']);

        await bekle(ayarlar.INDIRMELER_ARASI_BEKLEME_MS);
    }

    // CSV raporu yaz
    const raporYolu = path.join(ayarlar.INDIRME_KLASORU, 'rapor.csv');
    const baslik = 'Tarih;Gönderen;Mesaj Türü;Dosya;Sonuç;Açıklama';
    const csv = [baslik, ...raporSatirlari.map((s) => s.map(csvAlan).join(';'))].join('\r\n');
    fs.writeFileSync(raporYolu, '﻿' + csv, 'utf8'); // BOM: Excel'de Türkçe karakterler için

    console.log('\n==========================================================');
    console.log('  SONUÇ ÖZETİ');
    console.log(`  İndirilen           : ${indirilen}`);
    console.log(`  Daha önce indirilmiş: ${atlanan}`);
    console.log(`  Kapsam dışı tür     : ${kapsamDisi}`);
    console.log(`  İndirilemeyen       : ${basarisiz}`);
    console.log(`  Rapor               : ${raporYolu}`);
    console.log('==========================================================');

    if (basarisiz > 0) {
        console.log('\nUYARI: Bazı eski medyaların süresi WhatsApp sunucularında dolmuş');
        console.log('olabilir. Bu dosyalar telefonunuzda hâlâ duruyorsa, telefondan');
        console.log('"Sohbeti dışa aktar (medya dahil)" yöntemiyle alıp bu depodaki');
        console.log('"export-ayikla.js" betiği ile ayıklayabilirsiniz (README\'ye bakın).');
        console.log('Betiği tekrar çalıştırmak da başarısız olanları yeniden dener.');
    }
}

main().catch((h) => {
    console.error('✖ Kritik hata:', h);
    process.exit(1);
});
