#!/usr/bin/env node
// WhatsApp "baca aralığı" botu — ana akış.
//
// Belirtilen tarihten bugüne kadar bir WhatsApp grubundaki fotoğrafları tarar,
// her fotoğrafın altına yazılan "baca aralığı adı"nı (örn. A20-A19) resmin
// üzerine yazar ve bir klasöre kaydeder.
//
// Kullanım:
//   node src/index.js --group "Grup Adı" --since 2026-06-27
//   node src/index.js --group "Grup Adı" --since 2026-06-27 --out ./output --limit 8000
//   node src/index.js --list-groups        (grup adlarını listeler)

import fs from 'node:fs';
import path from 'node:path';
import { createClient, findGroup, listGroups, fetchMessages } from './whatsapp.js';
import { annotateImage } from './annotate.js';

// --- Sabitler ---
const FALLBACK_WINDOW_SEC = 90; // caption yoksa, bu süre içindeki komşu metni ad kabul et

function printHelp() {
  console.log(`
WhatsApp baca aralığı botu

Kullanım:
  node src/index.js --group "Grup Adı" --since YYYY-MM-DD [--out ./output] [--limit 5000]
  node src/index.js --list-groups

Argümanlar:
  --group        Taranacak WhatsApp grubunun adı (kısmi eşleşme yeterli)
  --since        Bu tarihten (dahil) bugüne kadar taranır. Biçim: YYYY-MM-DD
  --out          Çıktı klasörü (varsayılan: ./output)
  --limit        Taranacak en fazla mesaj sayısı (varsayılan: 5000)
  --list-groups  Sadece grupları listeler ve çıkar
  --help, -h     Bu yardımı gösterir
`);
}

function parseArgs() {
  const args = process.argv.slice(2);
  const opt = { group: null, since: null, out: './output', limit: 5000, listGroups: false };
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === '--group') opt.group = args[++i];
    else if (a === '--since') opt.since = args[++i];
    else if (a === '--out') opt.out = args[++i];
    else if (a === '--limit') opt.limit = parseInt(args[++i], 10);
    else if (a === '--list-groups') opt.listGroups = true;
    else if (a === '--help' || a === '-h') { printHelp(); process.exit(0); }
    else { console.error(`Bilinmeyen argüman: ${a}`); printHelp(); process.exit(1); }
  }
  return opt;
}

/** YYYY-MM-DD -> Unix saniye (yerel gün başı). */
function dateToUnixSeconds(dateStr) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
    throw new Error(`--since biçimi hatalı: "${dateStr}" (YYYY-MM-DD olmalı)`);
  }
  const d = new Date(dateStr + 'T00:00:00');
  if (isNaN(d.getTime())) throw new Error(`--since geçersiz tarih: "${dateStr}"`);
  return Math.floor(d.getTime() / 1000);
}

/** Dosya adı için güvenli hale getir (harf, rakam, tire, alt çizgi korunur). */
function safeName(s) {
  return (s || '').replace(/[^\p{L}\p{N}_-]+/gu, '_').replace(/^_+|_+$/g, '').slice(0, 60);
}

/** CSV alanını (noktalı virgül ayraç) güvenli hale getirir. */
function csvField(v) {
  const s = v == null ? '' : String(v);
  return /[";\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}

/** timestamp (sn) -> "YYYY-MM-DD_HH-MM-SS" */
function stamp(tsSec) {
  const d = new Date(tsSec * 1000);
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}_` +
    `${p(d.getHours())}-${p(d.getMinutes())}-${p(d.getSeconds())}`;
}

/**
 * Bir fotoğraf mesajı için "baca aralığı adı"nı belirler:
 *  1) Fotoğrafın kendi caption'ı (msg.body) — örn. "A20-A19"
 *  2) Yoksa, aynı kişiden ±FALLBACK_WINDOW_SEC içinde gönderilmiş en yakın metin
 */
function resolveCaption(msg, index, allMessages) {
  const own = (msg.body || '').trim();
  if (own) return own;

  let best = null;
  let bestDist = Infinity;
  for (let j = 0; j < allMessages.length; j++) {
    if (j === index) continue;
    const m = allMessages[j];
    if (m.type !== 'chat') continue;                // sadece metin mesajları
    if (!(m.body || '').trim()) continue;
    if (m.author !== msg.author) continue;          // aynı gönderici (grup içi)
    const dist = Math.abs(m.timestamp - msg.timestamp);
    if (dist <= FALLBACK_WINDOW_SEC && dist < bestDist) {
      bestDist = dist;
      best = m.body.trim();
    }
  }
  return best; // bulunamazsa null
}

async function run() {
  const opt = parseArgs();
  const client = createClient();

  await new Promise((resolve, reject) => {
    client.once('ready', resolve);
    client.once('auth_failure', reject);
    client.initialize().catch(reject);
  });

  try {
    if (opt.listGroups) {
      const names = await listGroups(client);
      console.log('\n📋 Gruplar:');
      names.forEach((n) => console.log('   - ' + n));
      return;
    }

    if (!opt.group || !opt.since) {
      printHelp();
      throw new Error('--group ve --since zorunludur.');
    }

    const sinceTs = dateToUnixSeconds(opt.since);
    fs.mkdirSync(opt.out, { recursive: true });

    console.log(`\n🔎 "${opt.group}" grubu aranıyor...`);
    const chat = await findGroup(client, opt.group);
    console.log(`   Bulundu: ${chat.name}`);

    console.log(`📥 Mesaj geçmişi çekiliyor (limit: ${opt.limit})...`);
    const all = await fetchMessages(chat, opt.limit);
    console.log(`   ${all.length} mesaj yüklendi.`);

    const images = all.filter(
      (m) => m.timestamp >= sinceTs && m.type === 'image' && m.hasMedia
    );
    console.log(`🖼️  ${opt.since} tarihinden itibaren ${images.length} fotoğraf bulundu.\n`);

    let saved = 0;
    let skipped = 0;
    const rows = []; // CSV özeti için
    for (let i = 0; i < images.length; i++) {
      const msg = images[i];
      const globalIndex = all.indexOf(msg);
      const caption = resolveCaption(msg, globalIndex, all);

      if (!caption) {
        skipped++;
        console.log(`   ⏭️  [${i + 1}/${images.length}] ${stamp(msg.timestamp)} — baca aralığı adı yok, atlandı.`);
        continue;
      }

      try {
        const media = await msg.downloadMedia();
        if (!media || !media.data) {
          skipped++;
          console.log(`   ⚠️  [${i + 1}/${images.length}] medya indirilemedi, atlandı.`);
          continue;
        }
        const buffer = Buffer.from(media.data, 'base64');
        const who = safeName((msg.author || '').split('@')[0]);
        const ad = caption.replace(/\s+/g, ' ').trim(); // baca aralığı adı, örn. "A20-A19"

        // Dosya adı: adı öne al -> A20-A19_2026-06-27_12-00-00[_gonderen].jpg
        const nameParts = [];
        const adSafe = safeName(ad);
        if (adSafe) nameParts.push(adSafe);
        nameParts.push(stamp(msg.timestamp));
        if (who) nameParts.push(who);
        const fname = nameParts.join('_') + '.jpg';
        const outPath = path.join(opt.out, fname);

        // Baca aralığı adını resmin üzerine yaz
        await annotateImage(buffer, ad, outPath);
        saved++;

        rows.push([stamp(msg.timestamp), who, ad, fname]);
        console.log(`   ✅ [${i + 1}/${images.length}] ${fname}  («${ad}»)`);
      } catch (e) {
        skipped++;
        console.log(`   ❌ [${i + 1}/${images.length}] hata: ${e.message}`);
      }
    }

    // Excel uyumlu CSV özeti (UTF-8 BOM + noktalı virgül ayraç)
    if (rows.length) {
      const BOM = String.fromCharCode(0xfeff);
      const header = ['tarih', 'gonderen', 'baca_araligi_adi', 'dosya'];
      const csv = BOM +
        [header, ...rows].map((r) => r.map(csvField).join(';')).join('\r\n') + '\r\n';
      const csvPath = path.join(opt.out, 'ozet.csv');
      fs.writeFileSync(csvPath, csv, 'utf8');
      console.log(`\n📑 Özet CSV: ${csvPath}`);
    }

    console.log(`\n🏁 Bitti. Kaydedilen: ${saved}, atlanan: ${skipped}. Klasör: ${path.resolve(opt.out)}`);
  } finally {
    await client.destroy();
  }
}

run().catch((e) => {
  console.error('\n💥 Hata:', e.message);
  process.exit(1);
});
