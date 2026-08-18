// Görüntü üzerine yazı basma katmanı.
// Caption (hat/baca aralığı bilgisi) metnini, resmin alt kısmına yarı
// saydam bir bant üzerine okunaklı biçimde yazar. sharp + SVG kullanır;
// Türkçe karakterler (ç, ğ, ı, ö, ş, ü) desteklenir.

import sharp from 'sharp';

/** SVG içine gömülecek metni güvenli hale getirir. */
function escapeXml(s) {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

/**
 * Uzun metni, satır başına yaklaşık maxChars karakter olacak şekilde
 * kelime bazında satırlara böler. Tek kelime çok uzunsa zorla böler.
 */
function wrapText(text, maxChars) {
  const lines = [];
  // Kullanıcının kendi satır sonlarını koru
  for (const rawLine of text.split(/\r?\n/)) {
    const words = rawLine.split(/\s+/).filter(Boolean);
    let cur = '';
    for (const w of words) {
      const candidate = cur ? cur + ' ' + w : w;
      if (candidate.length <= maxChars) {
        cur = candidate;
      } else {
        if (cur) lines.push(cur);
        if (w.length > maxChars) {
          let rest = w;
          while (rest.length > maxChars) {
            lines.push(rest.slice(0, maxChars));
            rest = rest.slice(maxChars);
          }
          cur = rest;
        } else {
          cur = w;
        }
      }
    }
    if (cur) lines.push(cur);
    if (words.length === 0) lines.push(''); // boş satırı koru
  }
  return lines.length ? lines : [''];
}

/**
 * inputBuffer görüntüsüne caption metnini basıp outputPath'e JPEG olarak kaydeder.
 * @param {Buffer} inputBuffer  Orijinal görüntü (JPEG/PNG)
 * @param {string} caption      Resmin üzerine yazılacak metin
 * @param {string} outputPath   Kayıt yolu (.jpg)
 */
export async function annotateImage(inputBuffer, caption, outputPath) {
  const img = sharp(inputBuffer).rotate(); // EXIF yönünü otomatik düzelt
  const meta = await img.metadata();
  const W = meta.width || 1000;
  const H = meta.height || 1000;

  const fontSize = Math.max(20, Math.round(W / 26));
  const padding = Math.round(fontSize * 0.7);
  const lineHeight = Math.round(fontSize * 1.3);
  // Ortalama karakter genişliği ~ fontSize * 0.58 kabul edilir
  const maxChars = Math.max(8, Math.floor((W - 2 * padding) / (fontSize * 0.58)));

  const lines = wrapText(caption.trim(), maxChars);
  const bandHeight = lines.length * lineHeight + 2 * padding;
  const bandY = Math.max(0, H - bandHeight);
  const strokeW = Math.max(1, Math.round(fontSize / 16));

  const textElems = lines
    .map((line, i) => {
      const y = bandY + padding + i * lineHeight + Math.round(fontSize * 0.85);
      return (
        `<text x="${padding}" y="${y}" ` +
        `font-family="DejaVu Sans, Noto Sans, Arial, sans-serif" ` +
        `font-size="${fontSize}" font-weight="bold" ` +
        `fill="#FFFFFF" stroke="#000000" stroke-width="${strokeW}" ` +
        `paint-order="stroke">${escapeXml(line)}</text>`
      );
    })
    .join('\n  ');

  const svg = `<svg width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg">
  <rect x="0" y="${bandY}" width="${W}" height="${bandHeight}" fill="#000000" fill-opacity="0.55"/>
  ${textElems}
</svg>`;

  await img
    .composite([{ input: Buffer.from(svg), top: 0, left: 0 }])
    .jpeg({ quality: 90 })
    .toFile(outputPath);
}
