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
        headless: !ayarlar.GORUNUR,
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

    // Teşhis: hazır olana kadar geçen aşamaları görünür kıl
    istemci.on('loading_screen', (yuzde, mesaj) => {
        console.log(`  ... yükleniyor: %${yuzde} ${mesaj || ''}`);
    });
    istemci.on('change_state', (durum) => console.log(`  ... bağlantı durumu: ${durum}`));
    istemci.on('disconnected', (neden) => console.log(`✖ Bağlantı koptu: ${neden}`));

    // "ready" 10 dakika içinde gelmezse kullanıcıyı bilgilendir
    let hazirOldu = false;
    setTimeout(() => {
        if (!hazirOldu) {
            console.log('\nUYARI: 10 dakikadır "hazır" sinyali gelmedi. Programı Ctrl+C ile');
            console.log('durdurup şu şekilde görünür tarayıcı ile yeniden başlatın ve');
            console.log('WhatsApp Web ekranında ne yazdığına bakın:');
            console.log('  $env:GORUNUR = "1"');
            console.log('  npm start');
        }
    }, 10 * 60 * 1000).unref();

    istemci.on('ready', async () => {
        hazirOldu = true;
        console.log('✔ WhatsApp Web hazır.');
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

/**
 * Sohbet listesini WhatsApp Web'in iç deposundan HAM olarak okur.
 * Kütüphanenin getChats() işlevi, hesaptaki tek bir sorunlu sohbet (kanal,
 * topluluk, bozuk kayıt vb.) yüzünden tümden çökebildiğinden, burada her
 * sohbet tek tek ve hata korumalı işlenir; yalnızca grup adı + kimliği alınır.
 */
async function gruplariHamListele(istemci) {
    return await istemci.pupPage.evaluate(() => {
        const sonuc = [];
        try {
            // whatsapp-web.js 1.34+ : window.require('WAWebCollections').Chat
            // daha eski sürümler    : window.Store.Chat
            let koleksiyon = null;
            try {
                koleksiyon = window.require && window.require('WAWebCollections').Chat;
            } catch (e) {
                /* aşağıdaki yedek yola düş */
            }
            if (!koleksiyon && window.Store && window.Store.Chat) koleksiyon = window.Store.Chat;
            const modeller = koleksiyon && koleksiyon.getModelsArray ? koleksiyon.getModelsArray() : [];
            for (const c of modeller) {
                try {
                    const id = c.id && (c.id._serialized || String(c.id));
                    if (!id || !id.endsWith('@g.us')) continue; // yalnızca gruplar
                    const ad =
                        c.formattedTitle ||
                        c.name ||
                        (c.contact && (c.contact.name || c.contact.pushname)) ||
                        '';
                    sonuc.push({ id, ad: String(ad) });
                } catch (e) {
                    /* tek sohbetteki hata tüm listeyi bozmasın */
                }
            }
        } catch (e) {
            /* depo hazır değilse boş liste döner */
        }
        return sonuc;
    });
}

/**
 * Grubun tüm mesaj geçmişini WhatsApp Web içinde parça parça (en eskiye
 * doğru) yükler ve yalnızca resim/belge mesajlarının özetini döndürür.
 * Kütüphanenin fetchMessages'ı tek bozuk mesajda tüm listeyi kaybettirdiği
 * için burada her mesaj tek tek, hata korumalı işlenir.
 */
async function medyaMesajlariniTopla(istemci, grupId) {
    const sayiAl = () =>
        istemci.pupPage.evaluate(async (id) => {
            const chat = await window.WWebJS.getChat(id, { getAsModel: false });
            return chat.msgs.getModelsArray().length;
        }, grupId);

    let toplam = await sayiAl();
    console.log(`  Bellekte ${toplam} mesaj var; daha eski mesajlar yükleniyor...`);

    let sonRapor = Date.now();
    while (toplam < ayarlar.AZAMI_MESAJ_SAYISI) {
        const sonuc = await istemci.pupPage.evaluate(async (id) => {
            const chat = await window.WWebJS.getChat(id, { getAsModel: false });
            const yukleyici = window.require('WAWebChatLoadMessages');
            for (let i = 0; i < 5; i++) {
                let parti = null;
                try {
                    parti = await yukleyici.loadEarlierMsgs({ chat });
                } catch (e) {
                    return { bitti: true, hata: String((e && e.message) || e) };
                }
                if (!parti || !parti.length) return { bitti: true };
            }
            return { bitti: false };
        }, grupId);

        toplam = await sayiAl();
        if (Date.now() - sonRapor > 4000) {
            console.log(`  ... ${toplam} mesaj yüklendi`);
            sonRapor = Date.now();
        }
        if (sonuc.bitti) {
            if (sonuc.hata) console.log(`  (daha eski mesaj yüklenemedi: ${sonuc.hata})`);
            break;
        }
    }
    console.log(`✔ Toplam ${toplam} mesaj yüklendi (ulaşılabilen en eski mesaja kadar).`);

    const ozetler = await istemci.pupPage.evaluate(async (id) => {
        const chat = await window.WWebJS.getChat(id, { getAsModel: false });
        const sonuc = [];
        for (const m of chat.msgs.getModelsArray()) {
            try {
                if (m.isNotification) continue;
                const tur = m.type;
                if (tur !== 'image' && tur !== 'document') continue;
                const gonderen =
                    (m.author && m.author._serialized) || (m.from && m.from._serialized) || '';
                let gonderenAd = '';
                try {
                    const s = m.senderObj;
                    gonderenAd = (s && (s.pushname || s.name || s.formattedName)) || m.notifyName || '';
                } catch (e) {
                    /* ad alınamazsa boş kalır */
                }
                sonuc.push({
                    id: m.id._serialized,
                    t: m.t,
                    tur,
                    mimetype: m.mimetype || '',
                    dosyaAdi: m.filename || '',
                    gonderen,
                    gonderenAd: String(gonderenAd || ''),
                });
            } catch (e) {
                /* tek mesajdaki hata tüm listeyi bozmasın */
            }
        }
        sonuc.sort((a, b) => a.t - b.t);
        return sonuc;
    }, grupId);

    if (ozetler.length > 0) {
        console.log(`  En eski medya : ${tarihBilgisi(ozetler[0].t).okunur}`);
        console.log(`  En yeni medya : ${tarihBilgisi(ozetler[ozetler.length - 1].t).okunur}`);
    }
    return ozetler;
}

async function grubuIsleyip_indir(istemci) {
    console.log('\nGrup listesi alınıyor...');

    // Depo bazen "hazır" sinyalinden hemen sonra dolu olmaz; birkaç kez dene.
    let gruplar = [];
    for (let deneme = 1; deneme <= 6; deneme++) {
        gruplar = await gruplariHamListele(istemci);
        if (gruplar.length > 0) break;
        console.log(`  ... grup listesi henüz boş (deneme ${deneme}/6), 5 sn bekleniyor`);
        await bekle(5000);
    }
    if (gruplar.length === 0) {
        console.error('✖ Hiç grup bulunamadı. WhatsApp Web eşitlemesi tamamlanmamış olabilir;');
        console.error('  birkaç dakika sonra programı yeniden çalıştırın.');
        return;
    }
    console.log(`✔ ${gruplar.length} grup bulundu.`);

    const hedefAd = ayarlar.GRUP_ADI.trim().toLocaleLowerCase('tr-TR');
    const hedef = gruplar.find((g) => g.ad.trim().toLocaleLowerCase('tr-TR') === hedefAd);

    if (!hedef) {
        console.error(`✖ "${ayarlar.GRUP_ADI}" adında bir grup bulunamadı.`);
        console.error('  Üyesi olduğunuz gruplar:');
        gruplar.forEach((g) => console.error(`   - ${g.ad}`));
        return;
    }

    console.log(`✔ Grup bulundu: "${hedef.ad}" (${hedef.id})`);
    console.log('\nGrubun kurulduğu ilk günden itibaren TÜM mesaj geçmişi yükleniyor.');
    console.log('(Mesaj sayısına göre bu işlem uzun sürebilir, lütfen bekleyin...)\n');

    const medyaliMesajlar = await medyaMesajlariniTopla(istemci, hedef.id);
    console.log(`✔ ${medyaliMesajlar.length} adet resim/belge içeren mesaj tespit edildi.\n`);

    const durum = durumOku();
    const raporSatirlari = [];
    let indirilen = 0;
    let atlanan = 0;
    let basarisiz = 0;
    let kapsamDisi = 0;

    for (let i = 0; i < medyaliMesajlar.length; i++) {
        const ozet = medyaliMesajlar[i];
        const mesajId = ozet.id || `bilinmeyen_${i}`;
        const tarih = tarihBilgisi(ozet.t);
        const ilerleme = `[${i + 1}/${medyaliMesajlar.length}]`;

        // Daha önce indirilmişse atla
        if (durum.indirilenler[mesajId]) {
            atlanan++;
            continue;
        }

        // Gönderen bilgisi (ham özetten; yoksa telefon numarası)
        const gonderen =
            ozet.gonderenAd ||
            (ozet.gonderen ? ozet.gonderen.replace(/@.*$/, '') : '') ||
            'Bilinmeyen';

        // Mesaj nesnesini tek başına al ve medyayı indir (başarısız olursa yeniden dene)
        let medya = null;
        let sonHata = '';
        for (let deneme = 1; deneme <= ayarlar.YENIDEN_DENEME_SAYISI; deneme++) {
            try {
                const mesaj = await istemci.getMessageById(mesajId);
                if (!mesaj) throw new Error('Mesaj nesnesi alınamadı');
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
                tur: ozet.tur,
                hata: sonHata,
            };
            console.log(`${ilerleme} ✖ İNDİRİLEMEDİ | ${tarih.okunur} | ${gonderen} | ${sonHata}`);
            raporSatirlari.push([tarih.okunur, gonderen, ozet.tur, '', 'BAŞARISIZ', sonHata]);
            durumYaz(durum);
            continue;
        }

        // Yalnızca resim ve PDF kabul et (ör. Word/Excel belgeleri kapsam dışı)
        if (!mimeKabulEdiliyorMu(medya.mimetype)) {
            kapsamDisi++;
            console.log(`${ilerleme} – Kapsam dışı tür atlandı (${medya.mimetype}) | ${tarih.okunur}`);
            raporSatirlari.push([tarih.okunur, gonderen, ozet.tur, medya.filename || '', 'KAPSAM DIŞI', medya.mimetype]);
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
        raporSatirlari.push([tarih.okunur, gonderen, ozet.tur, path.relative(ayarlar.INDIRME_KLASORU, hedefYol), 'İNDİRİLDİ', '']);

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
