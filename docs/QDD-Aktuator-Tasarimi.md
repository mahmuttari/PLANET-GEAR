# QDD Aktüatör Tasarımı — PLANET-GEAR

**QDD (Quasi-Direct Drive)** aktüatör; yüksek tork yoğunluklu bir BLDC dış rotor
(outrunner) motorun, **düşük oranlı tek kademeli planet redüktör** (≈6:1) ile
birleştirilmesinden oluşan, geri sürülebilir (back-drivable), düşük atalet ve
yüksek bant genişlikli bir tahrik birimidir. Bacaklı robotlarda (MIT Mini Cheetah,
Unitree), robot kollarında ve exoskeleton eklemlerinde tercih edilir.

> Neden "Quasi-Direct"? Doğrudan tahrikin (redüktörsüz) düşük sürtünme ve yüksek
> şeffaflığını korurken, küçük bir redüksiyonla tork yoğunluğunu birkaç kat artırır.
> Yüksek oranlı redüktörlerin (harmonik, çok kademeli planet) aksine geri
> sürülebilirliği bozmaz; bu da kuvvet kontrolünü (impedance/torque control)
> mümkün kılar.

---

## 1. Hedef Performans Gereksinimleri

| Parametre | Hedef Değer | Açıklama |
|---|---|---|
| Sürekli çıkış torku | **≥ 15 Nm** | Termal sınırda sürekli |
| Tepe çıkış torku | **≥ 33 Nm** | Kısa süreli (sıçrama/darbe) |
| Maks. çıkış devri | **≥ 380 rpm** | ≈ 40 rad/s |
| Çevrim oranı | **6 : 1** | Geri sürülebilirliği korur |
| Besleme gerilimi | **24 V** (18–30 V) | 6S LiPo uyumlu |
| Kütle (hedef) | **≤ 600 g** | Tork yoğunluğu ≈ 27 Nm/kg |
| Kontrol | **FOC + tork kontrolü** | CAN-FD / CAN 2.0B |
| Geri besleme | **14-bit mutlak enkoder** | Çıkış + rotor pozisyonu |

---

## 2. Sistem Mimarisi

```
        +------------------------------------------------+
        |                  QDD AKTÜATÖR                  |
        |                                                |
 24V →  | [FOC Sürücü PCB] ── 3 faz ──> [BLDC Outrunner] |
 CAN ↔  |        |                            |          |
        |   [MA702 Enkoder]            (Dış rotor)       |
        |   (rotor açısı)                    |           |
        |                              [Güneş dişli]      |
        |                                    |           |
        |                          [3x Planet] (taşıyıcı) |
        |                                    |           |
        |                          [Halka dişli - sabit]  |
        |                                    |           |
        |   [Çıkış enkoderi] <──────── [Çıkış mili]  → Yük|
        +------------------------------------------------+
```

- **Motor:** Dış rotorlu (outrunner) BLDC. Düşük KV, yüksek kutup sayısı (yüksek tork).
- **Redüktör:** Tek kademeli planet; halka (ring) gövdeye sabit, güneş (sun) motora
  bağlı giriş, taşıyıcı (carrier) çıkış mili.
- **Sürücü:** FOC tabanlı (örn. moteus, ODrive S1, VESC veya özel STM32G4 PCB).

---

## 3. Motor Seçimi (BLDC Outrunner)

| Parametre | Değer | Not |
|---|---|---|
| Tip | Dış rotor BLDC | Yüksek tork yoğunluğu |
| Kutup çifti | 21 (42 kutup) | Düşük cogging, yüksek tork |
| Oluk (slot) | 36 | 36N42P sargı düzeni |
| KV | ~100 rpm/V | Düşük KV = yüksek tork sabiti |
| Stator dış çapı | ~80–90 mm | Redüktörle uyumlu |
| Stator yüksekliği | ~25 mm | |
| Sürekli tork | **~3.0 Nm** | Termal sınır |
| Tepe tork | **~6.5 Nm** | Akım sınırı |
| Sürekli devir (24V) | ~2400 rpm | KV × V |
| Tork sabiti Kt | ~0.10 Nm/A | 8.27/KV ≈ 0.083; sargıya göre |

> **Not:** Mini Cheetah tipi mimaride özel sarılmış stator kullanılır. Hazır
> alternatif olarak T-Motor U10/U12, Eaglepower 8108/9108 veya benzeri büyük
> outrunner gövdeler uygundur.

---

## 4. Planet Redüktör Tasarımı (Çekirdek)

`tools/planetary_gear_calc.py` ile hesaplanan ve **tüm kinematik koşulları
sağlayan** tek kademeli planet redüktör:

| Parametre | Değer |
|---|---|
| Modül (m) | 1.0 mm |
| Basınç açısı | 20° |
| **Güneş dişli (Zs)** | **14 diş** |
| **Planet dişli (Zp)** | **28 diş** (×3 adet) |
| **Halka dişli (Zr)** | **70 diş** |
| Planet sayısı | 3 |
| **Çevrim oranı** | **6.000 : 1** |

**Geometri (bölüm daireleri):**

| Eleman | Çap |
|---|---|
| Güneş | 14.00 mm |
| Planet | 28.00 mm |
| Halka (iç) | 70.00 mm |
| Eksenler arası mesafe (a) | 21.00 mm |

### 4.1 Doğrulanan Tasarım Koşulları

| Koşul | Formül | Sonuç |
|---|---|---|
| Diş sayısı uyumu | Zr = Zs + 2·Zp = 70 | ✅ |
| Montaj koşulu | (Zs + Zr)/p = 84/3 = 28 (tam sayı) | ✅ |
| Komşuluk koşulu | (Zs+Zp)·sin(π/p) = 36.37 > Zp+2 = 30 | ✅ |
| Eş eksenlilik | Ortak modül | ✅ |

> **Çevrim oranı formülü** (halka sabit, güneş giriş, taşıyıcı çıkış):
> `i = 1 + Zr/Zs = 1 + 70/14 = 6.0`

### 4.2 Malzeme ve Üretim

- **Güneş & planet dişliler:** Sertleştirilmiş çelik (16MnCr5 / 20MnCr5,
  sementasyon + taşlama) veya yüksek yük için. Hafiflik istenirse planet taşıyıcı
  7075 alüminyum.
- **Halka dişli:** İç dişli; çelikten talaşlı imalat veya tel erozyon (WEDM).
- **Diş genişliği (yüzü):** ~10 mm (tork kapasitesi için).
- **Diş profili:** Standart involüt, addendum profil kaydırması güneşte negatif
  alt kesmeyi (undercut) önlemek için +x kaydırma önerilir (Zs=14 < 17 olduğundan).

---

## 5. Tork ve Devir Bütçesi

Redüktör verimi η ≈ 0.90 (tek kademe planet) varsayımıyla:

| Büyüklük | Motor | × i × η | **Çıkış** |
|---|---|---|---|
| Sürekli tork | 3.0 Nm | × 6 × 0.9 | **16.2 Nm** ✅ |
| Tepe tork | 6.5 Nm | × 6 × 0.9 | **35.1 Nm** ✅ |
| Devir | 2400 rpm | ÷ 6 | **400 rpm (41.9 rad/s)** ✅ |

Üç hedef de (≥15 Nm sürekli, ≥33 Nm tepe, ≥380 rpm) sağlanıyor.

---

## 6. Mekanik Yerleşim

- **Yapı:** Dış rotor "kapak" olarak döner; stator ortadaki sabit mile cıvatalanır.
- **Rulmanlar:**
  - Çıkış mili için çapraz makaralı (crossed-roller) **veya** çift açısal temaslı
    rulman (eksenel + radyal yükü taşır).
  - Her planet for iğneli rulman (needle bearing) veya bronz burç.
  - Rotor için derin oluklu bilyalı rulman (örn. 6700/6800 serisi).
- **Çıkış arayüzü:** Standart cıvata deliği deseni (örn. ISO flanş), tork mili
  veya doğrudan bağlantı.
- **Önerilen gövde çapı:** ~90 mm, toplam yükseklik ~45 mm.

---

## 7. Elektronik & Kontrol (FOC)

| Bileşen | Öneri |
|---|---|
| MCU | STM32G431/G474 (FOC için donanım hızlandırma) |
| Kapı sürücü | DRV8353 / DRV8323 |
| MOSFET | Düşük RDS(on), ≥ 60 V, ≥ 100 A tepe |
| Akım algılama | 3× düşük yan shunt + dahili amfi |
| Rotor enkoderi | MA702 / AS5047P (manyetik, 14-bit) |
| Çıkış enkoderi | AS5048A (mutlak, çıkış açısı) |
| Haberleşme | CAN-FD (5 Mbit) / CAN 2.0B |
| Kontrol modu | Tork (akım) kontrolü + opsiyonel impedans (Kp, Kd, τff) |

**Kontrol döngüsü:** Saha yönlendirmeli kontrol (FOC) ile `id=0`, `iq ∝ tork`.
Çıkış enkoderi yük tarafı pozisyonunu doğrudan ölçer → dişli boşluğu (backlash) ve
sapmalar kapatılır. Tipik komut çerçevesi: `(pozisyon, hız, Kp, Kd, ileri-besleme torku)`.

---

## 8. Sonraki Adımlar / Yapılacaklar

- [ ] CAD: Planet taşıyıcı ve gövde 3D modeli (FreeCAD/Fusion).
- [ ] Dişli mukavemet hesabı (Lewis eğilme + Hertz temas / ISO 6336).
- [ ] Termal model (sürekli akımda stator sıcaklığı).
- [ ] FOC firmware portu (moteus/ODrive/SimpleFOC) ve kalibrasyon.
- [ ] Prototip & dinamometre testi (tork-hız eğrisi, verim).

---

## Hesap Aracını Çalıştırma

```bash
# Varsayılan tasarım (6:1)
python3 tools/planetary_gear_calc.py

# Farklı bir oran denemek için (örn. 9:1 -> Zs=10, Zp=30, Zr=70)
python3 tools/planetary_gear_calc.py --zsun 10 --zplanet 30 --planets 3 --module 1.0
```

Betik tüm kinematik koşulları otomatik doğrular; bir koşul sağlanmazsa
sıfırdan farklı çıkış kodu döner.
