# Örnek dosyalar

Bu klasördeki dosyalar, aracın desteklediği alan tanımı biçimlerini ve
yerel sayısal yükseklik modeli (SYM) kullanımını denemek içindir. Hepsi
Kocaeli / İzmit çevresinde aynı örnek proje sahasını tanımlar.

| Dosya | Biçim | Açıklama |
|---|---|---|
| `izmit-ornek-saha.kml` | KML | Google Earth'te çizilip kaydedilmiş bir poligonu temsil eder |
| `izmit-ornek-saha.geojson` | GeoJSON | QGIS / ArcGIS dışa aktarımı |
| `izmit-ornek-saha.wkt` | WKT | Veritabanı sorgusundan kopyalanmış geometri |
| `izmit-ornek-saha.csv` | Düz metin | Her satırda `enlem, boylam` |
| `izmit-ornek-saha.ncn` | Netcad NCN | ITRF96 3° dilim TM30 koordinatlarında sınır noktaları |
| `ornek-sym.asc` | ESRI ASCII Grid | 20 m çözünürlüklü örnek SYM (ITRF96-TM30) |

Beş alan dosyası da aynı poligonu tanımlar; 50 m aralıkla hepsinden
**868 nokta** üretilir.

## Denemeler

```bash
# 1) Google Earth KML'inden, çevrimiçi kaynakla 25 m karelaj
python karelaj.py uret --alan ornekler/izmit-ornek-saha.kml --aralik 25

# 2) Kot okumadan, yalnızca nokta konumlarını üret (internet gerekmez)
python karelaj.py uret --alan ornekler/izmit-ornek-saha.kml --aralik 50 --kot-yok

# 3) Örnek yerel SYM ile: eş yükselti eğrileri ve hacim hesabı dahil
python karelaj.py uret --alan ornekler/izmit-ornek-saha.kml --aralik 25 \
    --kaynak yerel --sym ornekler/ornek-sym.asc --dem-sistemi ITRF96-TM30 \
    --kontur 2 --hacim-kotu 60 --bicim hepsi

# 4) NCN sınır dosyasından (izdüşümlü olduğu için sistem belirtilir)
python karelaj.py uret --alan ornekler/izmit-ornek-saha.ncn \
    --sinir-sistemi ITRF96-TM30 --aralik 50 --kot-yok
```

> `ornek-sym.asc` gerçek arazi değildir; matematiksel olarak üretilmiş
> yapay bir yüzeydir. Yalnızca yerel SYM akışını denemek içindir.
