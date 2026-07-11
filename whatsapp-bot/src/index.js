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
import readline from 'node:readline';
import { exec } from 'node:child_process';
import { createClient, findGroup, listGroups, fetchMessages } from './whatsapp.js';
import { annotateImage } from './annotate.js';

// --- Sabitler ---
const FALLBACK_WINDOW_SEC = 90; // caption yoksa, bu süre içindeki komşu metni ad kabul et

function printHelp() {
  console.log(`
WhatsApp baca aralığı botu

Kullanım:
  node src/index.js --group "Grup Adı" --since YYYY-MM-DD [--out ./output] [--limit 20000]
  node src/index.js --list-groups

Argümanlar:
  --group        Taranacak WhatsApp grubunun adı (kısmi eşleşme yeterli)
  --since        Bu tarihten (dahil) bugüne kadar taranır. Biçim: YYYY-MM-DD
  --out          Çıktı klasörü (varsayılan: ./output)
  --limit        Taranacak en fazla mesaj sayısı (varsayılan: 20000)
  --list-groups  Sadece grupları listeler ve çıkar
  --help, -h     Bu yardımı gösterir
`);
}

function parseArgs() {
  const args = process.argv.slice(2);
  const opt = { group: null, since: null, out: './output', limit: 20000, listGroups: false };
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

/** Basit bekleme (ms). */
function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

/**
 * Medyayı birkaç kez deneyerek indirir. Özellikle eski fotoğraflarda ilk
 * deneme başarısız olabildiği için varsayılan 3 kez, artan beklemeyle dener.
 * Başarısız olursa null döner (mesaj çok eski veya telefonda/sunucuda yok).
 */
async function downloadWithRetry(msg, tries = 3) {
  for (let k = 1; k <= tries; k++) {
    try {
      const media = await msg.downloadMedia();
      if (media && media.data) return media;
    } catch (e) {
      // yut ve tekrar dene
    }
    if (k < tries) await sleep(1500 * k);
  }
  return null;
}

/** readline sorusu -> Promise<cevap> */
function ask(rl, question) {
  return new Promise((resolve) => rl.question(question, (a) => resolve(a)));
}

/** Dosyayı işletim sisteminin varsayılan görüntüleyicisinde açar (sessiz başarısız). */
function openInViewer(p) {
  const plt = process.platform;
  const cmd = plt === 'win32' ? `start "" "${p}"` : plt === 'darwin' ? `open "${p}"` : `xdg-open "${p}"`;
  try { exec(cmd, () => {}); } catch (e) { /* önemsiz */ }
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
    let existed = 0;
    let skipped = 0;
    const rows = [];   // CSV özeti için
    const failed = []; // medyasına erişilemeyenler
    const noName = []; // baca aralığı adı olmayanlar (sonda elle sorulur)
    for (let i = 0; i < images.length; i++) {
      const msg = images[i];
      const globalIndex = all.indexOf(msg);
      const caption = resolveCaption(msg, globalIndex, all);

      if (!caption) {
        noName.push(msg); // adı yok -> en sonda tek tek soracağız
        continue;
      }

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

      // Tekrar çalıştırmada zaten kaydedilmiş dosyayı yeniden indirme (idempotent).
      // Böylece botu tekrar çalıştırınca yalnızca eksikler denenir.
      if (fs.existsSync(outPath)) {
        existed++;
        rows.push([stamp(msg.timestamp), who, ad, fname]);
        console.log(`   ⏭️  [${i + 1}/${images.length}] ${fname} zaten var, atlandı.`);
        continue;
      }

      try {
        const media = await downloadWithRetry(msg, 3);
        if (!media || !media.data) {
          failed.push({ ts: msg.timestamp, ad, reason: 'medya indirilemedi (çok eski / erişilemiyor)' });
          console.log(`   ⚠️  [${i + 1}/${images.length}] ${stamp(msg.timestamp)} «${ad}» — medya indirilemedi (3 deneme).`);
          continue;
        }
        const buffer = Buffer.from(media.data, 'base64');

        // Baca aralığı adını resmin üzerine yaz
        await annotateImage(buffer, ad, outPath);
        saved++;

        rows.push([stamp(msg.timestamp), who, ad, fname]);
        console.log(`   ✅ [${i + 1}/${images.length}] ${fname}  («${ad}»)`);
      } catch (e) {
        failed.push({ ts: msg.timestamp, ad, reason: e.message });
        console.log(`   ❌ [${i + 1}/${images.length}] ${stamp(msg.timestamp)} «${ad}» — hata: ${e.message}`);
      }
    }

    // --- Adı olmayan fotoğrafları en sonda tek tek elle isimlendir ---
    if (noName.length) {
      if (!process.stdin.isTTY) {
        console.log(`\n📝 Baca aralığı adı olmayan ${noName.length} fotoğraf var; elle isim vermek`);
        console.log('   için botu normal (etkileşimli) bir komut satırında çalıştırın.');
        skipped += noName.length;
      } else {
        console.log(`\n📝 Baca aralığı adı OLMAYAN ${noName.length} fotoğraf var. Şimdi sırayla soracağım.`);
        console.log('   Her biri için: adı yaz + Enter  |  boş + Enter = atla  |  q + Enter = kalanları bırak');
        const isimsizDir = path.join(opt.out, 'isimsiz');
        fs.mkdirSync(isimsizDir, { recursive: true });
        const existingFiles = new Set(fs.readdirSync(opt.out));
        const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
        let quit = false;
        for (let k = 0; k < noName.length; k++) {
          if (quit) { skipped++; continue; }
          const msg = noName[k];
          const who = safeName((msg.author || '').split('@')[0]);
          const st = stamp(msg.timestamp);

          // Daha önce elle isimlendirilmişse tekrar sorma (idempotent)
          const zaten = [...existingFiles].some(
            (f) => f.includes(st) && (!who || f.includes(who)) && f.endsWith('.jpg')
          );
          if (zaten) {
            existed++;
            console.log(`   ⏭️  [${k + 1}/${noName.length}] ${st} zaten kayıtlı, atlandı.`);
            continue;
          }

          const media = await downloadWithRetry(msg, 3);
          if (!media || !media.data) {
            failed.push({ ts: msg.timestamp, ad: '(adı yok)', reason: 'medya indirilemedi' });
            console.log(`   ⚠️  [${k + 1}/${noName.length}] ${st} — medya indirilemedi, atlandı.`);
            continue;
          }
          const buffer = Buffer.from(media.data, 'base64');
          const previewPath = path.join(isimsizDir, `${st}${who ? '_' + who : ''}.jpg`);
          fs.writeFileSync(previewPath, buffer);
          openInViewer(previewPath); // fotoğrafı görüp adına karar verebilmen için açar

          console.log(`\n   [${k + 1}/${noName.length}] Tarih: ${st}   Gönderen: ${who || '-'}`);
          console.log(`   Önizleme açıldı: ${previewPath}`);
          const ans = (await ask(rl, '   Baca aralığı adı: ')).trim();

          if (ans.toLowerCase() === 'q') {
            quit = true; skipped++;
            console.log('   → Kalanlar atlanıyor.');
            continue;
          }
          if (!ans) {
            skipped++;
            console.log('   → Boş girildi, atlandı (önizleme "isimsiz" klasöründe kaldı).');
            continue;
          }

          const ad = ans.replace(/\s+/g, ' ').trim();
          const nameParts = [];
          const adSafe = safeName(ad);
          if (adSafe) nameParts.push(adSafe);
          nameParts.push(st);
          if (who) nameParts.push(who);
          const fname = nameParts.join('_') + '.jpg';
          const outPath = path.join(opt.out, fname);
          await annotateImage(buffer, ad, outPath);
          saved++;
          rows.push([st, who, ad, fname]);
          existingFiles.add(fname);
          fs.rmSync(previewPath, { force: true }); // isimli kaydedildi, önizlemeyi sil
          console.log(`   ✅ Kaydedildi: ${fname}  («${ad}»)`);
        }
        rl.close();
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

    // Erişilemeyen fotoğrafların listesi (tekrar denemek için)
    if (failed.length) {
      const BOM = String.fromCharCode(0xfeff);
      const fh = ['tarih', 'baca_araligi_adi', 'sebep'];
      const fcsv = BOM +
        [fh, ...failed.map((x) => [stamp(x.ts), x.ad, x.reason])]
          .map((r) => r.map(csvField).join(';')).join('\r\n') + '\r\n';
      const fpath = path.join(opt.out, 'erisilemeyen.csv');
      fs.writeFileSync(fpath, fcsv, 'utf8');
      console.log(`\n⚠️  ${failed.length} fotoğrafın medyasına erişilemedi. Liste: ${fpath}`);
      console.log('   İPUCU: Telefonda WhatsApp grubunu açıp o eski fotoğraflara kadar yukarı kaydırın');
      console.log('   (böylece telefon medyayı yeniden indirir), sonra botu TEKRAR çalıştırın —');
      console.log('   zaten kaydedilenler atlanır, yalnızca eksikler yeniden denenir.');
    }

    console.log(
      `\n🏁 Bitti. Kaydedilen: ${saved}, zaten vardı: ${existed}, ` +
      `erişilemeyen: ${failed.length}, atlanan: ${skipped}. Klasör: ${path.resolve(opt.out)}`
    );
  } finally {
    await client.destroy();
  }
}

run().catch((e) => {
  console.error('\n💥 Hata:', e.message);
  process.exit(1);
});
