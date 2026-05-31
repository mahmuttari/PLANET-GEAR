/*
 * engineering.js
 * İstinat duvarı stabilite hesapları.
 *
 * Birim sistemi:
 *   - Uzunluklar: metre (m)
 *   - Birim hacim ağırlığı (gamma): kN/m^3
 *   - Kuvvetler: kN/m (1 m duvar uzunluğu başına)
 *   - Momentler: kNm/m
 *   - Gerilmeler / sürşarj: kPa
 *
 * Yöntem: Rankine aktif toprak itkisi. Pasif direnç ihmal edilmiştir (güvenli taraf).
 * Tüm hesaplar duvarın 1 metrelik uzunluğu içindir.
 */

const Eng = (function () {
  'use strict';

  const rad = (deg) => (deg * Math.PI) / 180;

  /* ---- Geometri yardımcıları (poligon alanı ve ağırlık merkezi) ---- */

  // points: [{x, y}, ...] (saat yönünde veya tersine, sıralı)
  function polygonArea(points) {
    let a = 0;
    for (let i = 0; i < points.length; i++) {
      const p = points[i];
      const q = points[(i + 1) % points.length];
      a += p.x * q.y - q.x * p.y;
    }
    return Math.abs(a) / 2;
  }

  function polygonCentroid(points) {
    let cx = 0, cy = 0, a = 0;
    for (let i = 0; i < points.length; i++) {
      const p = points[i];
      const q = points[(i + 1) % points.length];
      const cross = p.x * q.y - q.x * p.y;
      a += cross;
      cx += (p.x + q.x) * cross;
      cy += (p.y + q.y) * cross;
    }
    a /= 2;
    if (Math.abs(a) < 1e-12) return { x: 0, y: 0 };
    return { x: cx / (6 * a), y: cy / (6 * a) };
  }

  /* ---- Rankine aktif itki katsayısı ---- */
  // Yatay dolgu (beta=0): Ka = tan^2(45 - phi/2)
  // Eğimli dolgu (beta>0): Rankine eğimli zemin formülü
  function activeCoefficient(phiDeg, betaDeg) {
    const phi = rad(phiDeg);
    const beta = rad(betaDeg || 0);
    if (!betaDeg || betaDeg <= 0) {
      return (1 - Math.sin(phi)) / (1 + Math.sin(phi));
    }
    const cb = Math.cos(beta);
    const cp = Math.cos(phi);
    const root = Math.sqrt(Math.max(0, cb * cb - cp * cp));
    return cb * ((cb - root) / (cb + root));
  }

  /*
   * Ana analiz fonksiyonu.
   * model = {
   *   B: taban genişliği (m),
   *   H: itkinin etkidiği toplam yükseklik (m),
   *   concrete: [ {points:[...], gamma:..} ],  // beton bileşenleri
   *   soil:     [ {points:[...], gamma:..} ],  // duvar üzerine oturan dolgu
   *   gammaSoil: dolgu birim ağırlığı (kN/m^3),
   *   phi: dolgu içsel sürtünme açısı (derece),
   *   beta: dolgu yüzeyi eğimi (derece),
   *   q: sürşarj yükü (kPa),
   *   baseFrictionDeg: taban-zemin sürtünme açısı (derece),
   *   sigmaAllow: zemin emniyet gerilmesi (kPa),
   *   fsOtMin, fsSlMin: gerekli güvenlik sayıları
   * }
   */
  function analyze(model) {
    const Ka = activeCoefficient(model.phi, model.beta);
    const beta = rad(model.beta || 0);
    const H = model.H;
    const B = model.B;

    // --- Düşey kuvvetler ve devirici/tutucu momentler (taban ön ucuna göre) ---
    const components = [];
    let sumV = 0;       // toplam düşey kuvvet (kN/m)
    let Mr = 0;         // tutucu moment (kNm/m), taban ön köşesine (x=0) göre

    function addBody(label, body, type) {
      const area = polygonArea(body.points);
      const c = polygonCentroid(body.points);
      const W = area * body.gamma;
      const M = W * c.x;
      sumV += W;
      Mr += M;
      components.push({ label, type, area, weight: W, arm: c.x, moment: M });
    }

    (model.concrete || []).forEach((b, i) =>
      addBody(b.label || `Beton ${i + 1}`, b, 'beton'));
    (model.soil || []).forEach((b, i) =>
      addBody(b.label || `Dolgu ${i + 1}`, b, 'dolgu'));

    // --- Toprak itkisi (Rankine) ---
    const Pa = 0.5 * Ka * model.gammaSoil * H * H;   // aktif itki (kN/m)
    const Pq = Ka * (model.q || 0) * H;              // sürşarj itkisi (kN/m)

    const Ph = (Pa + Pq) * Math.cos(beta);           // yatay bileşen
    const Pv = (Pa + Pq) * Math.sin(beta);           // düşey bileşen (eğimli dolgu)

    // Devirici moment (taban ön ucuna göre)
    const Mo = Pa * Math.cos(beta) * (H / 3) + Pq * Math.cos(beta) * (H / 2);

    // Düşey itki bileşeni taban arka ucunda (x=B) etki eder -> tutucu
    if (Pv > 0) {
      sumV += Pv;
      Mr += Pv * B;
      components.push({
        label: 'İtki düşey bileşeni (Pv)', type: 'itki',
        area: null, weight: Pv, arm: B, moment: Pv * B,
      });
    }

    // --- Güvenlik kontrolleri ---
    // 1) Devrilme
    const fsOt = Mo > 0 ? Mr / Mo : Infinity;

    // 2) Kayma
    const mu = Math.tan(rad(model.baseFrictionDeg));
    const slidingResist = mu * sumV;
    const fsSl = Ph > 0 ? slidingResist / Ph : Infinity;

    // 3) Zemin gerilmesi
    const xbar = (Mr - Mo) / sumV;     // bileşkenin tabandaki yeri (ön uca göre)
    const e = B / 2 - xbar;            // dış merkezlik
    const eLimit = B / 6;
    let qMax, qMin, pressureValid;
    if (Math.abs(e) <= eLimit) {
      qMax = (sumV / B) * (1 + (6 * e) / B);
      qMin = (sumV / B) * (1 - (6 * e) / B);
      pressureValid = true;
    } else {
      // Çekme bölgesi: yeniden dağılım (üçgen gerilme bloğu)
      const aLen = 3 * xbar;           // x=0 ucundan basınç bölgesi uzunluğu
      qMax = (2 * sumV) / Math.max(aLen, 1e-6);
      qMin = 0;
      pressureValid = false;
    }

    const checks = {
      overturning: {
        label: 'Devrilme güvenliği',
        value: fsOt,
        required: model.fsOtMin,
        unit: '',
        ok: fsOt >= model.fsOtMin,
      },
      sliding: {
        label: 'Kayma güvenliği',
        value: fsSl,
        required: model.fsSlMin,
        unit: '',
        ok: fsSl >= model.fsSlMin,
      },
      bearing: {
        label: 'Zemin gerilmesi (σ_max)',
        value: qMax,
        required: model.sigmaAllow,
        unit: 'kPa',
        ok: qMax <= model.sigmaAllow && qMin >= -1e-6,
      },
      eccentricity: {
        label: 'Dış merkezlik (e ≤ B/6)',
        value: Math.abs(e),
        required: eLimit,
        unit: 'm',
        ok: Math.abs(e) <= eLimit,
      },
    };

    const allOk = Object.values(checks).every((c) => c.ok);

    return {
      Ka,
      Pa, Pq, Ph, Pv,
      sumV, Mr, Mo,
      xbar, e, eLimit,
      qMax, qMin, pressureValid,
      mu, slidingResist,
      components,
      checks,
      allOk,
    };
  }

  return { polygonArea, polygonCentroid, activeCoefficient, analyze, rad };
})();

if (typeof module !== 'undefined' && module.exports) {
  module.exports = Eng;
}
