// WhatsApp Web bağlantısı ve mesaj tarama katmanı.
// whatsapp-web.js, telefonunuzu WhatsApp Web üzerinden bağlayarak GEÇMİŞ
// grup mesajlarını okumanıza izin verir (resmi Cloud API bunu yapamaz).

import pkg from 'whatsapp-web.js';
const { Client, LocalAuth } = pkg;
import qrcode from 'qrcode-terminal';

/**
 * WhatsApp istemcisini oluşturur. LocalAuth sayesinde QR yalnızca ilk
 * çalıştırmada gösterilir; oturum .wwebjs_auth altında saklanır.
 */
export function createClient() {
  const client = new Client({
    authStrategy: new LocalAuth({ dataPath: './.wwebjs_auth' }),
    puppeteer: {
      headless: true,
      // Çok sayıda geçmiş mesaj yüklenirken/medya indirilirken tek bir Puppeteer
      // komutu uzun sürebilir; varsayılan 180 sn sınırını 10 dakikaya çıkarıyoruz.
      protocolTimeout: 600000,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
      ],
    },
  });

  client.on('qr', (qr) => {
    console.log('\n📱 Telefonunuzdan WhatsApp > Bağlı Cihazlar > Cihaz Bağla');
    console.log('   ile aşağıdaki QR kodu okutun:\n');
    qrcode.generate(qr, { small: true });
  });

  client.on('authenticated', () => console.log('✅ Kimlik doğrulandı.'));
  client.on('auth_failure', (m) => console.error('❌ Kimlik doğrulama hatası:', m));
  client.on('ready', () => console.log('✅ WhatsApp bağlantısı hazır.'));

  return client;
}

/** Tüm grupları listeler (isim keşfi için). */
export async function listGroups(client) {
  const chats = await client.getChats();
  return chats.filter((c) => c.isGroup).map((c) => c.name);
}

/**
 * Adı verilen grubu bulur. Önce tam eşleşme, sonra kısmi (içeren) eşleşme
 * dener; büyük/küçük harf duyarsızdır.
 */
export async function findGroup(client, groupName) {
  const chats = await client.getChats();
  const groups = chats.filter((c) => c.isGroup);
  const target = groupName.toLowerCase().trim();

  let g = groups.find((c) => (c.name || '').toLowerCase().trim() === target);
  if (!g) g = groups.find((c) => (c.name || '').toLowerCase().includes(target));

  if (!g) {
    console.error(`\n❌ "${groupName}" adlı grup bulunamadı. Mevcut gruplar:`);
    groups.forEach((c) => console.error('   - ' + c.name));
    throw new Error('Grup bulunamadı.');
  }
  return g;
}

/**
 * Gruptan mesaj geçmişini çeker. whatsapp-web.js, limit kadar mesajı
 * (gerekirse eski mesajları yükleyerek) kronolojik sırada döndürür.
 * timestamp saniye cinsindendir.
 */
export async function fetchMessages(chat, limit) {
  return chat.fetchMessages({ limit });
}
