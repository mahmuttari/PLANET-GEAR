/*
 * app.js
 * Arayüz mantığı: ölçüleri okur, geometriyi kurar, hesabı çalıştırır,
 * çizimi ve sonuç tablosunu üretir.
 */
(function () {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const num = (id) => parseFloat($(id).value);
  const fmt = (v, n = 2) =>
    (v === Infinity ? '∞' : (Math.round(v * Math.pow(10, n)) / Math.pow(10, n)).toFixed(n));

  // Duvar tipine göre görünür alanlar
  function setWallType(type) {
    document.querySelectorAll('[data-type]').forEach((el) => {
      el.style.display = el.dataset.type === type ? '' : 'none';
    });
    document.querySelectorAll('.type-btn').forEach((b) => {
      b.classList.toggle('active', b.dataset.type === type);
    });
    app.type = type;
  }

  function readCommon() {
    return {
      gammaConcrete: num('gammaConcrete'),
      gammaSoil: num('gammaSoil'),
      phi: num('phi'),
      beta: num('beta'),
      q: num('q'),
      baseFrictionDeg: $('baseFriction').value ? num('baseFriction') : num('phi'),
      sigmaAllow: num('sigmaAllow'),
      fsOtMin: num('fsOtMin'),
      fsSlMin: num('fsSlMin'),
    };
  }

  function readCantilever() {
    return Object.assign(readCommon(), {
      H: num('c_H'), tf: num('c_tf'), Lt: num('c_Lt'),
      Lh: num('c_Lh'), tTop: num('c_tTop'), tBot: num('c_tBot'),
    });
  }

  function readGravity() {
    return Object.assign(readCommon(), {
      H: num('g_H'), a: num('g_a'), b: num('g_b'),
    });
  }

  function validate(d, type) {
    const errs = [];
    const pos = (v, name) => { if (!(v > 0)) errs.push(`${name} pozitif olmalı.`); };
    pos(d.H, 'Yükseklik H');
    pos(d.gammaSoil, 'Dolgu birim ağırlığı');
    pos(d.gammaConcrete, 'Beton birim ağırlığı');
    pos(d.sigmaAllow, 'Zemin emniyet gerilmesi');
    if (!(d.phi > 0 && d.phi < 45)) errs.push('Sürtünme açısı φ 0–45° arası olmalı.');
    if (type === 'cantilever') {
      pos(d.tf, 'Temel kalınlığı'); pos(d.tBot, 'Gövde alt kalınlığı');
      if (d.tf >= d.H) errs.push('Temel kalınlığı toplam yükseklikten küçük olmalı.');
      if (d.tTop > d.tBot) errs.push('Gövde üst kalınlığı, alt kalınlıktan büyük olamaz.');
      if (!(d.Lt >= 0 && d.Lh >= 0)) errs.push('Ökçe/topuk uzunlukları negatif olamaz.');
    } else {
      pos(d.b, 'Alt genişlik b');
      if (d.a > d.b) errs.push('Üst genişlik a, alt genişlik b’den büyük olamaz.');
      if (!(d.a >= 0)) errs.push('Üst genişlik negatif olamaz.');
    }
    return errs;
  }

  let lastSVG = '';

  function run() {
    const type = app.type;
    const d = type === 'cantilever' ? readCantilever() : readGravity();

    const errs = validate(d, type);
    const msg = $('messages');
    if (errs.length) {
      msg.className = 'messages error';
      msg.innerHTML = '<strong>Girdi hatası:</strong><ul>' +
        errs.map((e) => `<li>${e}</li>`).join('') + '</ul>';
      return;
    }
    msg.className = 'messages';
    msg.textContent = '';

    const geo = type === 'cantilever' ? Geometry.cantilever(d) : Geometry.gravity(d);
    const model = Geometry.toAnalysisModel(geo, d);
    const res = Eng.analyze(model);

    lastSVG = Draw.render(geo, { showPressure: true });
    $('drawing').innerHTML = lastSVG;

    renderResults(res, geo);
  }

  function renderResults(res, geo) {
    const c = res.checks;
    const badge = (ok) => ok
      ? '<span class="badge ok">UYGUN ✓</span>'
      : '<span class="badge fail">YETERSİZ ✗</span>';

    const row = (chk, dec = 2) => `
      <tr class="${chk.ok ? 'r-ok' : 'r-fail'}">
        <td>${chk.label}</td>
        <td class="numv">${fmt(chk.value, dec)} ${chk.unit}</td>
        <td class="numv">${chk.required != null ? '≥ ' + fmt(chk.required, dec) + ' ' + chk.unit : ''}</td>
        <td>${badge(chk.ok)}</td>
      </tr>`;

    // Zemin gerilmesi için "≤" gösterimi
    const bearingRow = `
      <tr class="${c.bearing.ok ? 'r-ok' : 'r-fail'}">
        <td>${c.bearing.label}</td>
        <td class="numv">${fmt(c.bearing.value, 1)} kPa</td>
        <td class="numv">≤ ${fmt(c.bearing.required, 1)} kPa</td>
        <td>${badge(c.bearing.ok)}</td>
      </tr>`;

    const eccRow = `
      <tr class="${c.eccentricity.ok ? 'r-ok' : 'r-fail'}">
        <td>${c.eccentricity.label}</td>
        <td class="numv">${fmt(c.eccentricity.value, 3)} m</td>
        <td class="numv">≤ ${fmt(c.eccentricity.required, 3)} m</td>
        <td>${badge(c.eccentricity.ok)}</td>
      </tr>`;

    const comps = res.components.map((k) => `
      <tr>
        <td>${k.label}</td>
        <td class="numv">${k.weight.toFixed(2)}</td>
        <td class="numv">${k.arm.toFixed(3)}</td>
        <td class="numv">${k.moment.toFixed(2)}</td>
      </tr>`).join('');

    $('results').innerHTML = `
      <div class="overall ${res.allOk ? 'ok' : 'fail'}">
        ${res.allOk ? '✓ Tüm kontroller sağlandı — kesit uygun.'
                    : '✗ En az bir kontrol sağlanmadı — kesiti revize edin.'}
      </div>

      <h3>Güvenlik Kontrolleri</h3>
      <table class="res-table">
        <thead><tr><th>Kontrol</th><th>Değer</th><th>Sınır</th><th>Durum</th></tr></thead>
        <tbody>
          ${row(c.overturning)}
          ${row(c.sliding)}
          ${bearingRow}
          ${eccRow}
        </tbody>
      </table>

      <h3>Toprak İtkisi ve Yükler</h3>
      <table class="res-table small">
        <tbody>
          <tr><td>Aktif itki katsayısı Ka</td><td class="numv">${fmt(res.Ka, 3)}</td></tr>
          <tr><td>Aktif itki Pa</td><td class="numv">${fmt(res.Pa, 2)} kN/m</td></tr>
          <tr><td>Sürşarj itkisi Pq</td><td class="numv">${fmt(res.Pq, 2)} kN/m</td></tr>
          <tr><td>Yatay itki ΣPh</td><td class="numv">${fmt(res.Ph, 2)} kN/m</td></tr>
          <tr><td>Toplam düşey yük ΣV</td><td class="numv">${fmt(res.sumV, 2)} kN/m</td></tr>
          <tr><td>Tutucu moment Mr</td><td class="numv">${fmt(res.Mr, 2)} kNm/m</td></tr>
          <tr><td>Devirici moment Mo</td><td class="numv">${fmt(res.Mo, 2)} kNm/m</td></tr>
          <tr><td>Dış merkezlik e</td><td class="numv">${fmt(res.e, 3)} m</td></tr>
          <tr><td>Taban gerilmeleri σ_max / σ_min</td><td class="numv">${fmt(res.qMax, 1)} / ${fmt(res.qMin, 1)} kPa</td></tr>
        </tbody>
      </table>

      <h3>Yük Bileşenleri (taban ön ucuna göre moment)</h3>
      <table class="res-table small">
        <thead><tr><th>Bileşen</th><th>W (kN/m)</th><th>x̄ (m)</th><th>M (kNm/m)</th></tr></thead>
        <tbody>${comps}</tbody>
      </table>
    `;
  }

  function downloadSVG() {
    if (!lastSVG) { run(); }
    if (!lastSVG) return;
    const blob = new Blob([lastSVG], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `istinat_duvari_${app.type}.svg`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const app = { type: 'cantilever' };

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.type-btn').forEach((b) =>
      b.addEventListener('click', () => { setWallType(b.dataset.type); run(); }));
    $('btnCalc').addEventListener('click', run);
    $('btnDownload').addEventListener('click', downloadSVG);
    $('btnPrint').addEventListener('click', () => window.print());
    setWallType('cantilever');
    run(); // varsayılan örnekle başla
  });

  window.IstinatApp = { run };
})();
