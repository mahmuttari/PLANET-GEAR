// Caption ayrıştırma katmanı.
// Türkçe bilgi metninden "hat" numarasını ve "baca aralığı" değerini çıkarır.
// Türkçe karakter farklılıklarına dayanıklı olmak için metin önce ASCII'ye
// katlanır (ı->i, ğ->g, ş->s, ö->o, ü->u, ç->c) ve öyle eşleştirilir.

/** Türkçe karakterleri ASCII'ye katlar ve küçük harfe çevirir. */
export function foldTr(s) {
  return String(s || '')
    .replace(/İ/g, 'i')
    .replace(/I/g, 'i')
    .replace(/ı/g, 'i')
    .replace(/Ğ/g, 'g').replace(/ğ/g, 'g')
    .replace(/Ş/g, 's').replace(/ş/g, 's')
    .replace(/Ö/g, 'o').replace(/ö/g, 'o')
    .replace(/Ü/g, 'u').replace(/ü/g, 'u')
    .replace(/Ç/g, 'c').replace(/ç/g, 'c')
    .toLowerCase();
}

/**
 * Metinden hat ve baca aralığı bilgisini ayrıştırır.
 * Desteklenen kalıplar (büyük/küçük harf ve Türkçe karakter duyarsız):
 *   "Hat: 3", "hat no 3", "3. hat", "3 nolu hat"
 *   "Baca Aralığı: 45 cm", "baca araligi 45cm", "baca aralik 60"
 *
 * @param {string} caption
 * @returns {{hat: string|null, baca: string|null, unit: string|null}}
 */
export function parseInfo(caption) {
  const f = foldTr(caption);

  // --- Hat numarası ---
  let hat = null;
  let m = f.match(/hat\s*(?:no|numarasi|nu)?\s*[:.\-]?\s*(\d+)/);
  if (m) {
    hat = m[1];
  } else {
    // "3. hat" veya "3 nolu hat" gibi ters sıralı kalıp
    m = f.match(/(\d+)\s*\.?\s*(?:nolu\s*)?hat/);
    if (m) hat = m[1];
  }

  // --- Baca aralığı ---
  let baca = null;
  let unit = null;
  // "baca aralığı/aralik ... 45 cm"
  m = f.match(/baca\s*aral\w*\s*[:.\-]?\s*(\d+(?:[.,]\d+)?)\s*(mm|cm|m)?/);
  if (!m) {
    // yalnızca "baca ... 45" yedeği
    m = f.match(/baca\s*[:.\-]?\s*(\d+(?:[.,]\d+)?)\s*(mm|cm|m)?/);
  }
  if (m) {
    baca = m[1].replace(',', '.');
    unit = m[2] || null;
  }

  return { hat, baca, unit };
}
