/*
 * geometry.js
 * Girilen ölçülerden duvar kesit geometrisini üretir.
 *
 * Koordinat sistemi (model uzayı, metre):
 *   - x: tabanın ön (ayak/parmak) ucundan arkaya (dolgu tarafına) doğru
 *   - y: taban altından yukarı doğru
 *   - Orijin (0,0): taban ön alt köşesi
 *
 * Çıktı, hem çizim (draw.js) hem de hesap (engineering.js) tarafından kullanılır.
 */

const Geometry = (function () {
  'use strict';

  /* ---------- KONSOL (BETONARME) İSTİNAT DUVARI ---------- */
  function cantilever(d) {
    const H = d.H;            // toplam yükseklik
    const tf = d.tf;          // temel kalınlığı
    const Lt = d.Lt;          // ön ökçe (parmak) uzunluğu
    const Lh = d.Lh;          // arka topuk uzunluğu
    const tTop = d.tTop;      // gövde üst kalınlığı
    const tBot = d.tBot;      // gövde alt kalınlığı
    const B = Lt + tBot + Lh; // toplam taban genişliği
    const Hs = H - tf;        // gövde yüksekliği

    const xStemFront = Lt;            // gövde ön yüzü (düşey)
    const xStemBackBot = Lt + tBot;   // gövde arka yüzü taban kotunda
    const xStemBackTop = Lt + tTop;   // gövde arka yüzü üst kotunda

    // Taban plağı (saat yönü tersi)
    const base = [
      { x: 0, y: 0 }, { x: B, y: 0 }, { x: B, y: tf }, { x: 0, y: tf },
    ];

    // Gövde (ön yüz düşey, arka yüz şevli)
    const stem = [
      { x: xStemFront, y: tf },
      { x: xStemBackBot, y: tf },
      { x: xStemBackTop, y: H },
      { x: xStemFront, y: H },
    ];

    // Topuk üzerindeki dolgu (gövde arka yüzünden taban arka ucuna kadar)
    const soil = [
      { x: xStemBackBot, y: tf },
      { x: B, y: tf },
      { x: B, y: H },
      { x: xStemBackTop, y: H },
    ];

    // Ölçülendirme için anahtar noktalar
    const dims = {
      B, H, Hs, tf, Lt, Lh, tTop, tBot,
      xStemFront, xStemBackBot, xStemBackTop,
    };

    return {
      type: 'cantilever',
      B, H,
      concrete: [
        { label: 'Taban plağı', gamma: d.gammaConcrete, points: base },
        { label: 'Gövde', gamma: d.gammaConcrete, points: stem },
      ],
      soil: [
        { label: 'Topuk üstü dolgu', gamma: d.gammaSoil, points: soil },
      ],
      outline: { base, stem, soil },
      dims,
    };
  }

  /* ---------- AĞIRLIK DUVARI ---------- */
  function gravity(d) {
    const H = d.H;        // yükseklik
    const a = d.a;        // üst genişlik
    const b = d.b;        // alt (taban) genişlik
    const B = b;

    // Ön yüz düşey (x=0), arka yüz şevli
    const body = [
      { x: 0, y: 0 },
      { x: b, y: 0 },
      { x: a, y: H },
      { x: 0, y: H },
    ];

    // Arka yüze yaslanan dolgu kaması (x=b düşey düzlemine kadar)
    const soil = (b > a)
      ? [
          { x: b, y: 0 },
          { x: b, y: H },
          { x: a, y: H },
        ]
      : [];

    const dims = { B, H, a, b };

    const soilBodies = soil.length
      ? [{ label: 'Arka dolgu kaması', gamma: d.gammaSoil, points: soil }]
      : [];

    return {
      type: 'gravity',
      B, H,
      concrete: [
        { label: 'Duvar gövdesi', gamma: d.gammaConcrete, points: body },
      ],
      soil: soilBodies,
      outline: { body, soil },
      dims,
    };
  }

  // Hesap motoruna verilecek modeli derler.
  function toAnalysisModel(geo, d) {
    return {
      B: geo.B,
      H: geo.H,
      concrete: geo.concrete,
      soil: geo.soil,
      gammaSoil: d.gammaSoil,
      phi: d.phi,
      beta: d.beta || 0,
      q: d.q || 0,
      baseFrictionDeg: d.baseFrictionDeg || d.phi,
      sigmaAllow: d.sigmaAllow,
      fsOtMin: d.fsOtMin || 1.5,
      fsSlMin: d.fsSlMin || 1.5,
    };
  }

  return { cantilever, gravity, toAnalysisModel };
})();

if (typeof module !== 'undefined' && module.exports) {
  module.exports = Geometry;
}
