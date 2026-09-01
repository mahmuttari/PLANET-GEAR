/**
 * Yapılandırma dosyası
 * Gerekirse ortam değişkenleri (environment variables) ile ezilebilir.
 */
const path = require('path');

module.exports = {
    // İndirilecek WhatsApp grubunun tam adı
    GRUP_ADI: process.env.GRUP_ADI || 'Dsi TBMM Termal Masraf',

    // İndirilen dosyaların kaydedileceği klasör
    INDIRME_KLASORU: process.env.INDIRME_KLASORU || path.join(__dirname, 'indirilenler'),

    // Oturum (QR ile giriş) bilgilerinin saklanacağı klasör.
    // Bu sayede her çalıştırmada yeniden QR okutmak gerekmez.
    OTURUM_KLASORU: process.env.OTURUM_KLASORU || path.join(__dirname, '.wwebjs_auth'),

    // Grubun kurulduğu ilk günden bu yana TÜM mesajlara ulaşabilmek için
    // çekilecek azami mesaj sayısı. Grubun toplam mesaj sayısından büyük
    // olduğu sürece tüm geçmiş taranır.
    AZAMI_MESAJ_SAYISI: parseInt(process.env.AZAMI_MESAJ_SAYISI || '1000000', 10),

    // Medya indirme denemesi başarısız olursa kaç kez yeniden denensin
    YENIDEN_DENEME_SAYISI: parseInt(process.env.YENIDEN_DENEME_SAYISI || '3', 10),

    // Yeniden denemeler arasındaki bekleme süresi (milisaniye)
    YENIDEN_DENEME_BEKLEME_MS: parseInt(process.env.YENIDEN_DENEME_BEKLEME_MS || '3000', 10),

    // Art arda indirmeler arasında bekleme (WhatsApp tarafında engellenmemek için)
    INDIRMELER_ARASI_BEKLEME_MS: parseInt(process.env.INDIRMELER_ARASI_BEKLEME_MS || '750', 10),

    // İsteğe bağlı: Sistemde kurulu Chrome/Chromium yolu.
    // Boş bırakılırsa whatsapp-web.js kendi Chromium'unu indirir/kullanır.
    // Örn: /usr/bin/google-chrome-stable veya /opt/pw-browsers/chromium
    CHROME_YOLU: process.env.CHROME_YOLU || '',

    // WhatsApp Web sürüm sabitleme (isteğe bağlı, varsayılan: kapalı).
    // Boş bırakılırsa WhatsApp'ın sunduğu güncel sürüm kullanılır (önerilen).
    // Eski bir sürüme sabitlemek WhatsApp'ın sayfayı zorla yeniden yüklemesine
    // ve "Execution context was destroyed" hatasına yol açabilir. Yine de
    // gerekirse arşivdeki bir sürüm yazılabilir (örn. '2.3000.1043250633-alpha'):
    //   https://github.com/wppconnect-team/wa-version/tree/main/html
    WEB_SURUMU: process.env.WEB_SURUMU || '',

    // GORUNUR=1 yapılırsa tarayıcı penceresi görünür şekilde açılır;
    // WhatsApp Web'in hangi ekranda takıldığını görmek için kullanışlıdır.
    GORUNUR: process.env.GORUNUR === '1',

    // Kabul edilen MIME türleri (resimler + PDF)
    KABUL_EDILEN_MIME_ONEKLERI: ['image/'],
    KABUL_EDILEN_MIME_TURLERI: ['application/pdf'],
};
