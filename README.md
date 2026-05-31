# IST_DRAW — İstinat Duvarı Projelendirme

Ölçüleri girince **ölçekli kesit çizimi** üreten ve **stabilite hesabı** yapan,
tamamen tarayıcıda çalışan (kurulum gerektirmeyen) bir uygulama.

## Özellikler

- **İki duvar tipi:**
  - Konsol (betonarme) istinat duvarı — T/L kesit (taban + şevli gövde)
  - Ağırlık duvarı — trapez kesit
- **Ölçekli SVG kesit çizimi:** kotalar (ölçü çizgileri), beton/dolgu taraması,
  zemin çizgisi ve toprak itkisi (Pa) üçgen dağılımı.
- **Stabilite kontrolleri (1 m duvar uzunluğu için, Rankine yöntemi):**
  - Devrilme güvenliği (M_tutucu / M_devirici)
  - Kayma güvenliği (μ·ΣV / ΣP_yatay)
  - Zemin gerilmesi (σ_max ≤ σ_emniyet) ve dış merkezlik (e ≤ B/6)
- Yatay/eğimli dolgu (β), sürşarj yükü (q) ve ayrı taban sürtünme açısı desteği.
- SVG indirme ve yazdırma.

## Kullanım

Sunucu gerekmez. `index.html` dosyasını bir tarayıcıda açmanız yeterli:

```bash
# veya basit bir yerel sunucu:
python3 -m http.server 8000
# http://localhost:8000 adresini açın
```

Duvar tipini seçin, ölçü ve zemin parametrelerini girin, **Hesapla & Çiz**'e basın.

## Dosya yapısı

```
index.html            Arayüz (girdi formları, çizim ve sonuç panelleri)
css/style.css         Stil
js/engineering.js     Stabilite hesapları (Rankine itki, güvenlik kontrolleri)
js/geometry.js        Ölçülerden kesit geometrisinin üretimi
js/draw.js            Geometriden ölçekli SVG teknik çizim
js/app.js             Arayüz mantığı (girdi → hesap → çizim/sonuç)
```

## Yöntem ve varsayımlar

- Rankine aktif toprak itkisi; yatay dolguda `Ka = tan²(45 − φ/2)`,
  eğimli dolguda Rankine eğimli zemin formülü.
- Pasif direnç **ihmal** edilmiştir (güvenli taraf).
- Tüm kuvvet/moment değerleri 1 metre duvar uzunluğu içindir (kN/m, kNm/m).
- Birimler: uzunluk **m**, birim hacim ağırlığı **kN/m³**, gerilme/sürşarj **kPa**.

> Bu araç **ön tasarım** amaçlıdır. Nihai proje için yürürlükteki yönetmeliklere
> (TS, Eurocode 7 vb.) ve donatı/betonarme kesit hesaplarına göre kontrol gereklidir.
