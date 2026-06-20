# PLANET-GEAR

**QDD (Quasi-Direct Drive) Aktüatör Tasarımı** — yüksek tork yoğunluklu BLDC
outrunner motor + tek kademeli planet redüktör (6:1) + FOC tork kontrolü.

Geri sürülebilir (back-drivable), düşük atalet, yüksek bant genişlikli bir tahrik
birimi. Bacaklı robotlar, robot kolları ve exoskeleton eklemleri için uygundur.

## Öne Çıkan Tasarım Değerleri

| Büyüklük | Değer |
|---|---|
| Çevrim oranı | 6 : 1 (Zs=14, Zp=28×3, Zr=70) |
| Sürekli çıkış torku | ~16.2 Nm |
| Tepe çıkış torku | ~35.1 Nm |
| Maks. çıkış devri | ~400 rpm (41.9 rad/s) |
| Besleme | 24 V |
| Kontrol | FOC + tork/impedans, CAN-FD |

## Depo İçeriği

```
docs/
  QDD-Aktuator-Tasarimi.md   # Ana tasarım dokümanı (mimari, motor, redüktör, kontrol)
  BOM.md                     # Malzeme listesi
tools/
  planetary_gear_calc.py     # Parametrik planet redüktör hesap & doğrulama aracı
```

## Hızlı Başlangıç

```bash
python3 tools/planetary_gear_calc.py
```

Detaylar için: [docs/QDD-Aktuator-Tasarimi.md](docs/QDD-Aktuator-Tasarimi.md)
