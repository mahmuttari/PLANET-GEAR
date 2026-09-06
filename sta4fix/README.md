# sta4fix — Sta4CAD Çizim Yazısı Düzeltici

Sta4CAD'in DWG/DXF olarak dışa aktardığı kiriş, kolon ve döşeme detaylarında
**iç içe giren, okunamayan yazıları** otomatik olarak boş alana taşır.

- TEXT/MTEXT yazılarının sınır kutularını çıkarır, çizgi/polyline/blok
  geometrisiyle ve birbirleriyle çakışanları bulur.
- Her çakışan yazıyı, orijinal konumunun çevresinde halka taramasıyla bulunan
  **en yakın boş konuma** taşır.
- Yazı yüksekliğinden fazla kayan yazılara, orijinal noktayı gösteren
  **kılavuz çizgisi** ekler (ayrı `STA4FIX_LEADER` katmanında, kırmızı —
  istenmezse katman kapatılır veya `--no-leader` kullanılır).
- İsteğe bağlı olarak tüm yazıları küçültür (`--scale 0.8` gibi).

## Kurulum

```bash
pip install ezdxf
```

## Kullanım

```bash
python -m sta4fix kiris_detay.dxf                 # kiris_detay_fixed.dxf üretir
python -m sta4fix kiris_detay.dxf --dry-run       # dosya yazmadan çakışma raporu
python -m sta4fix K101.dxf K102.dxf K103.dxf      # toplu işlem
python -m sta4fix plan.dxf --scale 0.8 --margin 2 # yazıları %20 küçült, 2 birim pay
python -m sta4fix plan.dxf --layers YAZI DONATI   # yalnızca bu katmanlardaki yazılar
```

### DWG dosyaları

DWG kapalı bir formattır; araç DXF üzerinde çalışır. Üç seçenek:

1. **Sta4CAD'den DXF dışa aktarın** (en temizi),
2. Ücretsiz [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter)
   kurun — kuruluysa `python -m sta4fix cizim.dwg` DWG'yi otomatik çevirir,
3. LibreDWG (`dwg2dxf`) kuruluysa o da otomatik kullanılır.

Düzeltilen `_fixed.dxf` dosyası AutoCAD/BricsCAD/DraftSight ile açılıp
yeniden DWG olarak kaydedilebilir.

## Parametreler

| Parametre | Varsayılan | Açıklama |
|---|---|---|
| `--margin` | 1.0 | Yazı çevresinde bırakılan pay (çizim birimi) |
| `--scale` | 1.0 | Yazı yüksekliği çarpanı (0.8 → %20 küçült) |
| `--max-shift` | 12 | En büyük kaydırma = değer × yazı yüksekliği |
| `--layers` | hepsi | Yalnızca verilen katmanlardaki yazıları düzeltir |
| `--no-leader` | — | Kılavuz çizgisi ekleme |
| `--dry-run` | — | Dosya yazmadan rapor |

## Test

```bash
python -m sta4fix.tests.test_fixer
```

Sentetik bir kiriş detayı üretir (çizgilerin üstüne bindirilmiş donatı
yazıları), düzeltir ve sonuçta sıfır çakışma kaldığını doğrular.

## Bilinen sınırlar (v0.1)

- Yalnızca modelspace'teki TEXT/MTEXT yazıları taşınır; blok **içindeki**
  yazılar ve DIMENSION ölçü yazıları engel olarak dikkate alınır ama taşınmaz.
- Yer bulunamayan yazılar raporda "çözümsüz" olarak listelenir ve dokunulmaz.
