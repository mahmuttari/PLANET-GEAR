# Malzeme Listesi (BOM) — QDD Aktüatör

| # | Bileşen | Adet | Özellik / Öneri | Not |
|---|---|---|---|---|
| 1 | BLDC outrunner motor | 1 | 36N42P, KV~100, OD ~80–90 mm | Özel sargı veya T-Motor/Eaglepower |
| 2 | Güneş dişli | 1 | m=1, Z=14, çelik 20MnCr5 | Motor miline preslenir |
| 3 | Planet dişli | 3 | m=1, Z=28, çelik 20MnCr5 | İğneli rulman üzerinde |
| 4 | Halka (iç) dişli | 1 | m=1, Z=70, çelik | Gövdeye sabit |
| 5 | Planet taşıyıcı | 1 | 7075-T6 alüminyum, CNC | Çıkış mili ile bütünleşik |
| 6 | Çıkış rulmanı | 1 | Çapraz makaralı veya 2× açısal temaslı | Eksenel+radyal yük |
| 7 | Rotor rulmanı | 2 | 6800/6700 serisi bilyalı | |
| 8 | Planet iğne rulmanı | 3 | İğneli rulman / bronz burç | |
| 9 | Rotor enkoder IC | 1 | MA702 / AS5047P (14-bit) | Rotor arkası diametrik mıknatıs |
| 10 | Çıkış enkoder IC | 1 | AS5048A (mutlak) | Çıkış mili açısı |
| 11 | Diametrik mıknatıs | 2 | Ø6×2.5 mm | Enkoderler için |
| 12 | FOC sürücü PCB | 1 | STM32G4 + DRV8353 + 3× MOSFET yarım köprü | moteus/ODrive/özel |
| 13 | Gövde / kapak | 1 set | Alüminyum CNC | Stator montaj + halka tutucu |
| 14 | Bağlantı elemanları | — | M2.5 / M3 cıvata seti | Civata deseni ISO flanş |
| 15 | CAN konnektör | 1 | JST-GH veya XT | CAN-FD haberleşme |

**Tahmini toplam kütle hedefi:** ≤ 600 g
**Tahmini çıkış performansı:** 16.2 Nm sürekli / 35.1 Nm tepe / 400 rpm
