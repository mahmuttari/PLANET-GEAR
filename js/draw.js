/*
 * draw.js
 * Geometriyi ölçekli bir SVG teknik kesit çizimine dönüştürür.
 * Kotalar (ölçü çizgileri), tarama desenleri, dolgu ve toprak itkisi
 * dağılımı çizilir.
 */

const Draw = (function () {
  'use strict';

  const NS = 'http://www.w3.org/2000/svg';
  const fmt = (v) => (Math.round(v * 100) / 100).toFixed(2);

  // Çizim alanı ve kenar boşlukları (piksel)
  const CANVAS = { w: 720, h: 560 };
  const MARGIN = { top: 70, right: 120, bottom: 90, left: 110 };

  function render(geo, opts) {
    opts = opts || {};
    // --- Model sınırları ---
    let maxY = geo.H;
    let maxX = geo.B;
    const all = [];
    Object.values(geo.outline).forEach((poly) => {
      if (Array.isArray(poly)) poly.forEach((p) => all.push(p));
    });
    all.forEach((p) => { if (p.y > maxY) maxY = p.y; if (p.x > maxX) maxX = p.x; });

    const availW = CANVAS.w - MARGIN.left - MARGIN.right;
    const availH = CANVAS.h - MARGIN.top - MARGIN.bottom;
    const scale = Math.min(availW / maxX, availH / maxY);

    // Model (m, y-yukarı) -> SVG (px, y-aşağı)
    const X = (x) => MARGIN.left + x * scale;
    const Y = (y) => CANVAS.h - MARGIN.bottom - y * scale;

    const out = [];
    out.push(`<svg xmlns="${NS}" viewBox="0 0 ${CANVAS.w} ${CANVAS.h}" ` +
      `class="wall-svg" font-family="Arial, sans-serif">`);

    // Desenler
    out.push(`<defs>
      <pattern id="concreteHatch" width="9" height="9" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <rect width="9" height="9" fill="#d9dde3"/>
        <line x1="0" y1="0" x2="0" y2="9" stroke="#9aa3b0" stroke-width="0.7"/>
      </pattern>
      <pattern id="soilHatch" width="14" height="14" patternUnits="userSpaceOnUse">
        <rect width="14" height="14" fill="#efe7d6"/>
        <circle cx="3" cy="3" r="0.9" fill="#b8a072"/>
        <circle cx="10" cy="9" r="0.9" fill="#b8a072"/>
      </pattern>
      <marker id="arrow" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">
        <path d="M0,0 L7,3 L0,6 Z" fill="#1f6feb"/>
      </marker>
      <marker id="dimArrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
        <path d="M0,0 L6,3 L0,6 Z" fill="#333"/>
      </marker>
    </defs>`);

    const poly = (pts, fill, stroke) =>
      `<polygon points="${pts.map((p) => `${X(p.x)},${Y(p.y)}`).join(' ')}" ` +
      `fill="${fill}" stroke="${stroke}" stroke-width="1.6"/>`;

    // --- Dolgu (önce, betonun arkasında) ---
    geo.soil.forEach((s) => {
      if (s.points.length >= 3) out.push(poly(s.points, 'url(#soilHatch)', '#b9a877'));
    });

    // --- Beton bileşenleri ---
    geo.concrete.forEach((c) => out.push(poly(c.points, 'url(#concreteHatch)', '#3a4150')));

    // --- Zemin (temel altı) tarama çizgileri ---
    const gx0 = X(0) - 18, gx1 = X(maxX) + 18, gy = Y(0);
    out.push(`<line x1="${gx0}" y1="${gy}" x2="${gx1}" y2="${gy}" stroke="#555" stroke-width="1.4"/>`);
    for (let x = gx0; x < gx1; x += 11) {
      out.push(`<line x1="${x}" y1="${gy}" x2="${x - 7}" y2="${gy + 9}" stroke="#888" stroke-width="0.8"/>`);
    }

    // --- Dolgu üst yüzeyi çizgisi ---
    if (geo.soil.length && geo.soil[0].points.length >= 3) {
      const sp = geo.soil[0].points;
      const topPts = sp.filter((p) => Math.abs(p.y - geo.H) < 1e-6 || p.y >= geo.H - 1e-6);
      if (topPts.length >= 2) {
        const a = topPts[0], b = topPts[topPts.length - 1];
        out.push(`<line x1="${X(a.x)}" y1="${Y(a.y)}" x2="${X(b.x) + 16}" y2="${Y(b.y)}" stroke="#7a6a3a" stroke-width="1.2" stroke-dasharray="2,3"/>`);
      }
    }

    // --- Toprak itkisi üçgen dağılımı (sanal arka düzlem) ---
    if (opts.showPressure) {
      const xp = X(geo.B) + 6;
      const yTop = Y(geo.H), yBot = Y(0);
      const pmax = 34; // ok uzunluğu (px) tabanda
      const nArr = 5;
      for (let i = 1; i <= nArr; i++) {
        const yy = yTop + ((yBot - yTop) * i) / nArr;
        const frac = (yy - yTop) / (yBot - yTop); // 0 üstte, 1 tabanda
        const len = pmax * frac;
        out.push(`<line x1="${xp + len}" y1="${yy}" x2="${xp}" y2="${yy}" stroke="#1f6feb" stroke-width="1.4" marker-end="url(#arrow)"/>`);
      }
      out.push(`<line x1="${xp + pmax}" y1="${yTop}" x2="${xp}" y2="${yBot}" stroke="#1f6feb" stroke-width="1" stroke-dasharray="3,2"/>`);
      out.push(text(xp + pmax + 6, (yTop + yBot) / 2, 'Pa', { fill: '#1f6feb', size: 12, weight: 'bold', anchor: 'start' }));
    }

    // --- Ölçülendirme (kotalar) ---
    geo.dimLines = [];
    drawDims(out, geo, X, Y, scale);

    // --- Başlık / ölçek ---
    const title = geo.type === 'cantilever' ? 'KONSOL İSTİNAT DUVARI' : 'AĞIRLIK İSTİNAT DUVARI';
    out.push(text(CANVAS.w / 2, 30, title, { size: 15, weight: 'bold', anchor: 'middle' }));
    out.push(text(CANVAS.w / 2, 48, 'Kesit — ölçüler metre (m)', { size: 11, anchor: 'middle', fill: '#666' }));
    out.push(text(MARGIN.left, CANVAS.h - 18, `Ölçek ≈ 1 : ${Math.round(100 / scale)}  (1 m ≈ ${fmt(scale)} px)`, { size: 10, fill: '#888', anchor: 'start' }));

    out.push('</svg>');
    return out.join('\n');
  }

  function text(x, y, s, o) {
    o = o || {};
    return `<text x="${x}" y="${y}" font-size="${o.size || 11}" ` +
      `fill="${o.fill || '#222'}" text-anchor="${o.anchor || 'middle'}" ` +
      `font-weight="${o.weight || 'normal'}">${s}</text>`;
  }

  // Yatay kota çizgisi (x1->x2), model y=yLvl, ekran offseti px (aşağı +)
  function hDim(out, X, Y, x1, x2, yLvl, off, label) {
    const sy = Y(yLvl) + off;
    const a = X(x1), b = X(x2);
    out.push(`<line x1="${a}" y1="${Y(yLvl)}" x2="${a}" y2="${sy + 4}" stroke="#999" stroke-width="0.6"/>`);
    out.push(`<line x1="${b}" y1="${Y(yLvl)}" x2="${b}" y2="${sy + 4}" stroke="#999" stroke-width="0.6"/>`);
    out.push(`<line x1="${a}" y1="${sy}" x2="${b}" y2="${sy}" stroke="#333" stroke-width="0.9" marker-start="url(#dimArrow)" marker-end="url(#dimArrow)"/>`);
    out.push(text((a + b) / 2, sy - 4, label, { size: 10 }));
  }

  // Düşey kota çizgisi (y1->y2), model x=xLvl, ekran offseti px (sola +)
  function vDim(out, X, Y, y1, y2, xLvl, off, label) {
    const sx = X(xLvl) - off;
    const a = Y(y1), b = Y(y2);
    out.push(`<line x1="${X(xLvl)}" y1="${a}" x2="${sx - 4}" y2="${a}" stroke="#999" stroke-width="0.6"/>`);
    out.push(`<line x1="${X(xLvl)}" y1="${b}" x2="${sx - 4}" y2="${b}" stroke="#999" stroke-width="0.6"/>`);
    out.push(`<line x1="${sx}" y1="${a}" x2="${sx}" y2="${b}" stroke="#333" stroke-width="0.9" marker-start="url(#dimArrow)" marker-end="url(#dimArrow)"/>`);
    out.push(`<text x="${sx - 4}" y="${(a + b) / 2}" font-size="10" fill="#222" text-anchor="middle" transform="rotate(-90 ${sx - 4} ${(a + b) / 2})">${label}</text>`);
  }

  function drawDims(out, geo, X, Y, scale) {
    const d = geo.dims;
    if (geo.type === 'cantilever') {
      // Toplam genişlik B (en altta)
      hDim(out, X, Y, 0, d.B, 0, 56, `B = ${fmt(d.B)}`);
      // Ayrıntı: Lt | tBot | Lh (taban üstü hizasında)
      hDim(out, X, Y, 0, d.Lt, 0, 32, `Lt=${fmt(d.Lt)}`);
      hDim(out, X, Y, d.Lt, d.xStemBackBot, 0, 32, `${fmt(d.tBot)}`);
      hDim(out, X, Y, d.xStemBackBot, d.B, 0, 32, `Lh=${fmt(d.Lh)}`);
      // Toplam yükseklik H (solda)
      vDim(out, X, Y, 0, d.H, 0, 60, `H = ${fmt(d.H)}`);
      // Temel kalınlığı tf (solda alt)
      vDim(out, X, Y, 0, d.tf, 0, 30, `tf=${fmt(d.tf)}`);
      // Gövde üst kalınlığı (üstte)
      hDim(out, X, Y, d.xStemFront, d.xStemBackTop, d.H, -16, `${fmt(d.tTop)}`);
    } else {
      hDim(out, X, Y, 0, d.b, 0, 50, `b = ${fmt(d.b)}`);
      vDim(out, X, Y, 0, d.H, 0, 50, `H = ${fmt(d.H)}`);
      hDim(out, X, Y, 0, d.a, d.H, -16, `a = ${fmt(d.a)}`);
    }
  }

  return { render };
})();

if (typeof module !== 'undefined' && module.exports) {
  module.exports = Draw;
}
