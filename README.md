# PLANET-GEAR — QDD Aktüatör

Tek kademeli planet redüktörlü (6:1), dış rotorlu BLDC motorlu **Quasi-Direct Drive (QDD)**
aktüatör tasarımı. Bacaklı robot / robot kol eklemleri için: geri sürülebilir, tork-şeffaf,
düşük yansıyan atalet.

**Öne çıkanlar:** 24 N·m tepe / 8 N·m sürekli tork · 40 rad/s · 48 V · ~530 g · Ø96×58 mm

## İçerik

- [`docs/tasarim_raporu.md`](docs/tasarim_raporu.md) — tam tasarım raporu
  (spesifikasyonlar, motor seçimi, dişli geometrisi ve mukavemeti, yataklama,
  elektronik, termal analiz, kütle bütçesi, sonraki adımlar)
- [`calc/qdd_hesap.py`](calc/qdd_hesap.py) — boyutlandırma ve doğrulama hesapları

## Hesapları çalıştırma

```bash
python3 calc/qdd_hesap.py
```

Script; dişli montaj koşullarını, kavrama oranını, Lewis eğilme emniyetini,
gerilim marjını ve termal limitleri `assert` ile doğrular ve özet tablo basar.
Bağımlılık yoktur (yalnızca Python standart kütüphanesi).
