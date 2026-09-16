# Kot Karelajı

Seçilen bir alandan **belirli aralıklarla kot (yükseklik) karelajı** üretir ve
noktaları **Netcad NCN** biçiminde dışa aktarır.

Google Earth'te gördüğünüz arazi yüzeyi, deniz seviyesine göre yükseklikleri
bilinen sayısal bir modeldir. Bu araç, haritada seçtiğiniz alanı istediğiniz
metrik aralıkta (10 m, 25 m, 50 m …) düzenli bir nokta ağına böler, her nokta
için o yüzeyden kot okur ve sonucu doğrudan Netcad'e aktarılabilecek bir nokta
dosyası olarak verir.

```
Alan seç  →  Aralık ver  →  Kot oku  →  NCN / DXF / KML / CSV + teknik rapor
```

## İçindekiler

- [Öne çıkanlar](#öne-çıkanlar)
- [Kurulum](#kurulum)
- [Hızlı başlangıç](#hızlı-başlangıç)
- [Harita arayüzü](#harita-arayüzü)
- [Çalışma alanının tanımlanması](#çalışma-alanının-tanımlanması)
- [Karelaj parametreleri](#karelaj-parametreleri)
- [Koordinat sistemleri](#koordinat-sistemleri)
- [Kot kaynakları](#kot-kaynakları)
- [Düşey datum: dikkat edilmesi gereken en kritik konu](#düşey-datum-dikkat-edilmesi-gereken-en-kritik-konu)
- [Netcad NCN biçimi](#netcad-ncn-biçimi)
- [Diğer çıktı biçimleri](#diğer-çıktı-biçimleri)
- [Eş yükselti eğrileri ve hacim hesabı](#eş-yükselti-eğrileri-ve-hacim-hesabı)
- [Komut başvurusu](#komut-başvurusu)
- [Doğruluk ve doğrulama](#doğruluk-ve-doğrulama)
- [Mevzuat ve kullanım koşulları](#mevzuat-ve-kullanım-koşulları)
- [Sorun giderme](#sorun-giderme)
- [Testler ve dosya düzeni](#testler-ve-dosya-düzeni)

## Öne çıkanlar

- **Harici bağımlılık yok.** Yalnızca Python standart kütüphanesi kullanılır.
  Kurum bilgisayarlarında `pip install` izni gerekmeden çalışır; GDAL, pyproj,
  numpy kurulumu aranmaz.
- **Metrik ve tam katlara oturan karelaj.** Aralık izdüşüm düzleminde metre
  cinsindendir; kareler arazide gerçekten karedir. Varsayılan olarak ızgara,
  koordinatların aralığın tam katlarına geldiği şekilde oturtulur, böylece
  komşu paftalarda karelaj süreklidir.
- **Türkiye koordinat sistemleri hazır.** ITRF96/TUREF ve ED50 için 3 derecelik
  dilimler (dilim numarası önekli ve öneksiz), UTM 6 derecelik dilimler.
  Dilim, alanın orta boylamından kendiliğinden seçilir.
- **Beş farklı kot kaynağı.** Açık servisler, Google Earth'ün kullandığı
  Google Elevation API ve en önemlisi **kurumun kendi SYM verisi** (GeoTIFF,
  ESRI ASCII Grid, SRTM `.hgt`).
- **Netcad NCN sütun düzeni ayarlanabilir.** Netcad'iniz hangi sırayı bekliyorsa
  ona göre yazılır.
- **Teknik özet raporu.** Koordinat sistemi, datum, ölçek faktörü, meridyen
  yakınsaması, kot istatistikleri ve hacim hesabıyla birlikte, mühendislik
  evrakına eklenebilecek düzende bir metin dosyası üretilir.
- **Doğrulanmış jeodezi.** İzdüşüm sonuçları PROJ (pyproj) ile 0,1 mm,
  GeoTIFF okuyucu GDAL ile birebir karşılaştırılarak sınanmıştır.

## Kurulum

Gereksinim: **Python 3.8 veya üzeri**. Başka hiçbir şey gerekmez.

```bash
git clone <bu-depo>
cd PLANET-GEAR/kot-karelaj
python karelaj.py --help
```

İsteğe bağlı olarak sisteme kurulabilir (`karelaj` komutu her yerden çalışır):

```bash
pip install .
karelaj --help
```

## Hızlı başlangıç

**Yol 1 — Harita arayüzü (en kolay).** Tarayıcıda uydu görüntüsü üzerinde alan
çizip indirirsiniz:

```bash
python karelaj.py arayuz
```

**Yol 2 — Komut satırı, sınır kutusuyla:**

```bash
python karelaj.py uret --sinir 40.7530,29.9301,40.7602,29.9443 --aralik 25
```

**Yol 3 — Google Earth'ten kaydettiğiniz poligonla:**

```bash
python karelaj.py uret --alan saha.kml --aralik 10 --bicim hepsi
```

Üç durumda da dosyalar `cikti/` klasörüne yazılır.

## Harita arayüzü

```bash
python karelaj.py arayuz          # http://127.0.0.1:8777 adresinde açılır
python karelaj.py arayuz --kapi 8800 --tarayici-yok
```

Arayüz, bilgisayarınızda yalnızca `127.0.0.1` adresini dinleyen küçük bir
sunucu açar; kurum ağındaki başka bilgisayarlar erişemez ve dışarıya hiçbir
veri gönderilmez.

Kullanımı:

1. **Dikdörtgen** ya da **Poligon** düğmesiyle alanı haritada çizin. Poligonda
   köşeler tıklayarak eklenir, çift tıklama (ya da Enter) bitirir, sağ tıklama
   son köşeyi siler.
2. Elinizde hazır bir **KML/GeoJSON** varsa dosyayı doğrudan haritanın üzerine
   sürükleyip bırakın.
3. Aralığı, koordinat sistemini ve kot kaynağını seçin.
4. **Önizle** ile nokta ağını harita üzerinde görün, **Üret ve indir** ile
   dosyaları alın.

Harita için hiçbir dış JavaScript kütüphanesi kullanılmaz (Leaflet, Google
Maps API vb. yoktur); yalnızca uydu görüntüsü döşemeleri internetten çekilir.
İnternet erişimi yoksa arayüz yine açılır, harita boş görünür ama koordinat
girerek ve yerel SYM kullanarak çalışmayı sürdürebilirsiniz.

## Çalışma alanının tanımlanması

### Sınır kutusu

```bash
--sinir enlem1,boylam1,enlem2,boylam2
```

Güneybatı ve kuzeydoğu köşeleridir. Sıra **enlem, boylam** şeklindedir; Google
Earth'ün koordinatı gösterdiği ve panoya kopyaladığı sıra budur.

### Poligon dosyası

```bash
--alan saha.kml
```

Desteklenen biçimler:

| Uzantı | Biçim | Not |
|---|---|---|
| `.kml`, `.kmz` | Google Earth | `--alan-katman` ile belirli bir yer işareti seçilebilir |
| `.geojson`, `.json` | GeoJSON | QGIS / ArcGIS dışa aktarımı |
| `.wkt` | WKT | `POLYGON`, `MULTIPOLYGON`, `LINESTRING` |
| `.csv`, `.txt` | Düz metin | Her satırda bir köşe |
| `.ncn` | Netcad nokta dosyası | İzdüşümlü olduğu için `--sinir-sistemi` gerekir |

**Düz metin dosyalarında sütun sırası.** Türkiye'de enlem (36°–42°) ve boylam
(26°–45°) aralıkları çakıştığı için sıra sezgiyle saptanamaz. Varsayılan
`enlem-boylam`'dır; GeoJSON/WKT sırasındaki dosyalar için `--metin-sirasi
boylam-enlem` verin.

**NCN sınır dosyalarında sütun düzeni.** Varsayılan `no,y,x,z,kod`'dur.
Dosyanız farklı sıradaysa `--sinir-ncn-duzen no,x,y,z,kod` gibi belirtin.

### İç boşluklar (adalar)

GeoJSON ve KML'deki iç halkalar otomatik olarak boşluk kabul edilir; bu
alanlara nokta üretilmez. Örneğin bir gölet ya da yapı adası karelaj dışında
bırakılabilir.

## Karelaj parametreleri

| Seçenek | Varsayılan | Açıklama |
|---|---|---|
| `--aralik` | `25` | Karelaj aralığı (m) |
| `--aralik-yukari` | (aralık) | Kuzey-güney yönünde farklı aralık; dikdörtgen ızgara |
| `--hizalama` | `tam-kat` | `tam-kat`: koordinatlar aralığın tam katı; `alan`: alanın güneybatı köşesinden başla |
| `--donme` | `0` | Karelajı alan merkezi etrafında döndür (derece, saat yönünün tersi pozitif) |
| `--kirpma-yok` | — | Alan sınırının dışındaki noktaları da tut |
| `--tampon` | `0` | Kırpmada sınıra eklenecek tampon (m); negatif değer içeri daraltır |
| `--kose-noktalari` | — | Poligon köşelerini de `SINIR` koduyla ekle |
| `--siralama` | `kuzey-guney` | İlk satır en kuzeyde mi, en güneyde mi |
| `--azami-nokta` | `500000` | Güvenlik sınırı |

**Tam kat hizalaması neden önemli?** 25 m aralık seçtiğinizde noktalar
`…, 494 475, 494 500, 494 525, …` gibi yuvarlak sağa değerlere gelir. Aynı
bölgede farklı zamanlarda üretilen karelajlar birbirine oturur, komşu
paftalarla süreklilik bozulmaz.

**Döndürme.** Bir kollektör hattı ya da yol ekseni boyunca karelaj gerektiğinde
`--donme` ile ızgara eksene paralel hale getirilebilir. Aralık, döndürülmüş
çerçevede ölçülür; kareler bozulmaz.

### Nokta numaralandırma

| Seçenek | Örnek çıktı |
|---|---|
| `--no-profil sira` (varsayılan) | `1`, `2`, `3` … |
| `--no-profil satir-sutun` | `001-001`, `001-002` … |
| `--no-profil sutun-satir` | `001-001`, `002-001` … |
| `--no-onek K --no-basamak 4` | `K0001`, `K0002` … |
| `--no-baslangic 1000` | `1000`, `1001` … |

## Koordinat sistemleri

Tanımlı sistemlerin tamamı için:

```bash
python karelaj.py sistemler
```

| Aile | Kod örneği | EPSG | Açıklama |
|---|---|---|---|
| TUREF/ITRF96 3° TM | `ITRF96-TM30` | 5253–5259 | Sağa değer 500 000 tabanlı |
| TUREF/ITRF96 3° dilim önekli | `ITRF96-GK10` | 5269–5275 | Sağa değer `10 500 000` gibi dilim numarası önekli |
| ED50 3° TM | `ED50-TM30` | 2319–2325 | Eski projelerdeki uyum için |
| ED50 3° dilim önekli | `ED50-GK10` | 2206–2212 | |
| ED50 UTM 6° | `ED50-UTM35N` | 23035–23038 | |
| WGS84 UTM 6° | `WGS84-UTM35N` | 32635–32638 | |

Kullanım:

```bash
--sistem ITRF96-TM30      # doğrudan kod
--sistem EPSG:5254        # EPSG numarası
--sistem ITRF96           # yalnızca aile: dilim alanın boylamından seçilir
--dilim 10                # dilimi elle sabitle (9–15 → 27°–45°)
```

`--sistem` verilmezse alanın orta boylamına göre **ITRF96 3 derecelik dilim**
seçilir. Kocaeli için bu, 30° orta meridyenli `ITRF96-TM30`'dur.

**Eksen adlandırması.** Çıktılarda `Y` sağa değer (easting), `X` yukarı değer
(northing) anlamındadır. Bu, ülkemizdeki ölçme geleneğine ve EPSG'nin Türkiye
TM sistemleri için tanımladığı eksen sırasına uygundur.

**ED50 dönüşümü.** EPSG'nin Türkiye için tanımladığı `ED50 to WGS 84 (30)`
dönüşümü kullanılır (konum vektörü yöntemi, `dX=-84,1 dY=-101,8 dZ=-129,7
rZ=0,468" ölçek=1,05 ppm`, beyan edilen doğruluk **~2 m**). Kurumunuzun kendi
yerel dönüşüm parametreleri varsa ED50 çıktısını bunlarla üretmek daha
doğrudur; bu durumda ITRF96'da üretip dönüşümü kendi yazılımınızda yapın.

Tek nokta dönüşümü için:

```bash
python karelaj.py donustur "40.7654,29.9408" --hedef-sistem ITRF96-TM30
python karelaj.py donustur "495001.578,4514522.262" \
    --kaynak-sistem ITRF96-TM30 --hedef-sistem ED50-TM30
```

Ölçek faktörü ve meridyen yakınsaması da yazdırılır.

## Kot kaynakları

```bash
python karelaj.py kaynaklar     # tümünü ve veri kümelerini listeler
```

| Kaynak | Anahtar | Çözünürlük | Kota | Ne zaman? |
|---|---|---|---|---|
| `yerel` | — | verinizin çözünürlüğü | yok | **En doğrusu.** Kurumun hâlihazır/fotogrametrik SYM verisi |
| `opentopodata` | gerekmez | 25–90 m | 100 nokta/istek, 1 istek/sn, 1000 istek/gün | Varsayılan; ön etüt ve fizibilite |
| `google` | gerekir | değişken | faturalandırmaya bağlı | Google Earth'ün arazi verisinin aynısı |
| `open-elevation` | gerekmez | 30 m | belirsiz | Yedek seçenek; kararlılığı düşüktür |

### Yerel SYM (önerilen)

```bash
--kaynak yerel --sym /veri/sym/kocaeli.tif
--kaynak yerel --sym /veri/sym/karolar/          # klasördeki karolardan seçer
```

Desteklenen biçimler:

- **GeoTIFF** (`.tif`): şeritli ve karolu düzen; sıkıştırmasız, LZW, Deflate/ZIP
  ve PackBits; 1, 2 ve 3 numaralı öngörücüler; `int16`, `uint16`, `int32`,
  `uint32`, `float32`, `float64`; BigTIFF.
- **ESRI ASCII Grid** (`.asc`)
- **SRTM ham karo** (`.hgt`)

Koordinat sistemi dosyanın kendi etiketlerinden okunur; yoksa
`--dem-sistemi ITRF96-TM30` ile verilir. Ara değer yöntemi `--ornekleme` ile
seçilir: `en-yakin`, `bilineer` (varsayılan), `bikubik`.

### OpenTopoData

```bash
--kaynak opentopodata --veri-kumesi srtm30m
```

Veri kümeleri: `srtm30m`, `srtm90m`, `aster30m`, `eudem25m`, `mapzen`,
`gebco2020`, `etopo1`.

Açık sunucunun **günlük 1000 istek** sınırı vardır; bu, istek başına 100 nokta
ile günde en çok 100 000 noktaya karşılık gelir. Kurum içine kendi
OpenTopoData sunucunuzu kurduysanız `--sunucu http://sunucu:5000` ile sınırlar
kalkar.

### Google Elevation API

```bash
--kaynak google --google-anahtar ANAHTARINIZ
# ya da ortam değişkeniyle:
export GOOGLE_ELEVATION_ANAHTARI=...
```

Google Cloud'da Elevation API'nin etkinleştirilmiş ve faturalandırmasının açık
olması gerekir. Bu, Google Earth'te gördüğünüz arazi yüzeyinin **resmî ve
lisanslı** erişim yoludur; araç Google Earth ekranını veya döşemelerini
kazımaz.

### Önbellek

Çevrimiçi servislerden okunan her kot, SQLite tabanlı bir önbelleğe yazılır
(`~/.karelaj/kot-onbellek.sqlite`). Aynı alanda aralığı değiştirip yeniden
çalıştırdığınızda daha önce sorgulanmış noktalar tekrar indirilmez; yarıda
kesilen iş kaldığı yerden sürer.

```bash
python karelaj.py onbellek              # durumu göster
python karelaj.py onbellek --temizle    # tümünü sil
python karelaj.py uret ... --onbellek-yok
```

## Düşey datum: dikkat edilmesi gereken en kritik konu

Bu aracın verdiği kotların doğruluğu, seçtiğiniz kaynağın doğruluğuyla
sınırlıdır ve **yatay konum doğruluğuyla karıştırılmamalıdır**.

**1. Küresel modeller farklı jeoide dayanır.** SRTM ve ASTER EGM96, Copernicus
EGM2008, EU-DEM ise EVRS2000 jeoidine göre ortometrik kot verir. Türkiye Ulusal
Düşey Kontrol Ağı (**TUDKA-99**) kotlarıyla aralarında bölgesel olarak
desimetre mertebesinde **sistematik** fark bulunabilir.

**2. Yükseklik hatası yataydan çok daha büyüktür.** 30 m çözünürlüklü küresel
modellerde düşey karesel ortalama hata literatürde çoğunlukla **metre
mertebesinde** bildirilir ve arazi eğimiyle, bitki örtüsüyle, yerleşim
yoğunluğuyla değişir. Bu değerler:

- vaziyet planı, güzergâh ön etüdü, havza/akış yönü çalışması, ön keşif ve
  fizibilite için **yeterlidir**;
- kesin proje kotu, kanal taban kotu, eğim hesabı, kesin metraj ve keşif için
  **yeterli değildir**.

**3. Ne yapmalı?**

- Mümkünse **kurumun kendi hâlihazır/fotogrametrik SYM verisini** kullanın
  (`--kaynak yerel`). Bu veri zaten TUDKA-99 ortometrik kotlarındadır.
- Küresel model kullanmak zorundaysanız, sahadaki birkaç nivelman veya sabit
  GNSS noktasında farkı ölçün ve ortalama farkı uygulayın:

```bash
--kot-kaydirma -0.35      # okunan her kota -0,35 m eklenir
```

- Üretilen teknik raporda bu uyarı ve uygulanan kaydırma miktarı zaten yazılıdır;
  raporu proje dosyasında saklayın.

> Kısacası: bu araç **ölçme yerine geçmez**. Arazi ölçüsünün yerini almadan,
> etüt ve planlama aşamasını hızlandırmak için tasarlanmıştır.

## Netcad NCN biçimi

Netcad'in nokta dosyası (`.ncn`), her satırı bir nokta olan düz metin bir
dosyadır. Netcad'in **Nokta > Dosyadan Nokta Oku** penceresi sütun düzenini
kullanıcıya seçtirdiği için, bu araç düzeni ayarlanabilir kılar.

**Varsayılan çıktı** (`--ncn-profil netcad`):

```
1,494200.000,4513900.000,181.399,KARELAJ
2,494225.000,4513900.000,185.245,KARELAJ
```

Sütunlar: `NoktaNo , Y (sağa değer) , X (yukarı değer) , Z (kot) , Kod`

- Ayırıcı **virgül**, ondalık ayırıcı **nokta**, satır sonu **CRLF**,
  kodlama **cp1254** (Windows Türkçe). Netcad'in beklediği düzen budur.
- Koordinatlar ve kot varsayılan olarak **3 ondalık** (milimetre) yazılır.

### Hazır profiller

| `--ncn-profil` | Düzen | Ayırıcı |
|---|---|---|
| `netcad` (varsayılan) | `no y x z kod` | virgül |
| `netcad-bosluk` | `no y x z kod` | boşluk, sabit genişlik |
| `no-y-x-z` | `no y x z` | virgül |
| `no-x-y-z-kod` | `no x y z kod` | virgül |
| `y-x-z` | `y x z` | virgül |
| `x-y-z` | `x y z` | virgül |
| `ayrintili` | `no y x z kod enlem boylam` + başlık | virgül |

### Elle ayarlama

```bash
--ncn-sutun no,x,y,z,kod        # sütun sırası
--ncn-ayirac bosluk             # virgul | bosluk | sekme | noktali-virgul
--ncn-ondalik 3                 # koordinat ondalık basamağı
--ncn-ondalik-z 2               # kot ondalık basamağı
--ncn-baslik                    # başlık satırı ekle
--ncn-kodlama utf-8             # varsayılan cp1254
--ncn-satir-sonu lf             # varsayılan crlf
```

Kullanılabilir sütunlar: `no`, `y`, `x`, `z`, `kod`, `enlem`, `boylam`,
`satir`, `sutun`, `aciklama`.

### Kotu okunamayan noktalar

Kaynağın kapsamı dışında kalan ya da veri boşluğuna denk gelen noktaların kotu
okunamaz. Davranış seçilebilir:

```bash
--ncn-kotsuz atla     # varsayılan: bu noktaları dosyaya yazma
--ncn-kotsuz sifir    # kot sütununa 0.000 yaz
--ncn-kotsuz bos      # kot sütununu boş bırak
```

`--kot-yok` ile kot hiç okunmadıysa dosyanın tamamen boş kalmaması için
`sifir` davranışına kendiliğinden geçilir.

## Diğer çıktı biçimleri

`--bicim` ile virgülle ayrılmış olarak seçilir; `hepsi` tümünü üretir.
Varsayılan: `ncn,kml,rapor`.

| Biçim | Dosya | Ne için? |
|---|---|---|
| `ncn` | `.ncn` | Netcad nokta dosyası |
| `csv` | `.csv` | Excel çizelgesi. Türkçe Excel için noktalı virgül ayırıcı ve virgül ondalık; `--csv-ingilizce` ile uluslararası biçim |
| `xyz` | `.xyz` | Boşlukla ayrılmış `Y X Z`; yüzey modelleme araçları |
| `dxf` | `.dxf` | AutoCAD R12 DXF; noktalar, kot yazıları, karelaj çizgileri, sınır ve eş yükselti eğrileri ayrı katmanlarda |
| `kml` | `.kml` | **Google Earth'te açıp gözle denetlemek için**; en hızlı doğrulama yolu |
| `geojson` | `.geojson` | QGIS / ArcGIS |
| `rapor` | `-rapor.txt` | Teknik özet raporu |

DXF katmanları: `KARELAJ_NOKTA`, `KARELAJ_KOT`, `KARELAJ_NO`, `KARELAJ_IZGARA`,
`KARELAJ_SINIR`, `KARELAJ_KONTUR`.

## Eş yükselti eğrileri ve hacim hesabı

### Eş yükselti (kontur)

```bash
--kontur 1            # 1 m aralıkla eş yükselti eğrileri
--kontur-temel 0      # eğrilerin hizalanacağı taban kot
```

Eğriler karelaj matrisinden "yürüyen kareler" yöntemiyle üretilir ve DXF, KML
ile GeoJSON çıktılarına eklenir. Eğri sıklığı karelaj aralığıyla sınırlıdır:
25 m karelajdan 0,5 m eş yükselti üretmek anlamlı değildir.

### Karelaj yöntemiyle kazı/dolgu hacmi

```bash
--hacim-kotu 42.5            # proje (plan) kotu
--hacim-alt-bolme 8          # kare başına alt bölme (varsayılan 8)
```

İki sonuç birlikte raporlanır:

- **Alt bölmeli (prizmatik) yöntem:** Her kare `n x n` alt kareye bölünür, köşe
  kotlarından çift doğrusal ara değerle yükseklik üretilir, kazı ve dolgu
  **ayrı ayrı** toplanır. Keşif ve metraj için kullanılması gereken değerler
  bunlardır.
- **Klasik karelaj (ortalama yükseklik) yöntemi:** `V = a² · (h₁+h₂+h₃+h₄)/4`.
  Yalnızca **net** hacmi doğru verir; bir kısmı kazı bir kısmı dolgu olan
  karışık karelerde ikisini ayırmaz. Karşılaştırma için yazılır.

Dört köşesinden birinin kotu okunamayan ya da alan dışında kalan kareler hesaba
katılmaz; atlanan kare sayısı raporda belirtilir.

## Komut başvurusu

```
python karelaj.py <komut> [seçenekler]

  uret        Karelaj üret ve dosyaları yaz (komut yazılmazsa varsayılan)
  arayuz      Tarayıcıda harita arayüzünü başlat
  sistemler   Tanımlı koordinat sistemlerini listele
  kaynaklar   Kot kaynaklarını ve veri kümelerini listele
  donustur    Tek nokta koordinat dönüşümü
  onbellek    Kot önbelleğini görüntüle / temizle
```

Tam seçenek listesi için `python karelaj.py uret --help`.

### Sık kullanılan örnekler

```bash
# Ön etüt: 50 m karelaj, açık servis, Google Earth'te denetlemek için KML
python karelaj.py uret --alan saha.kml --aralik 50

# Kesin proje: kurum SYM'sinden 5 m karelaj, eş yükselti ve hacim ile
python karelaj.py uret --alan saha.kml --aralik 5 \
    --kaynak yerel --sym /veri/sym/kocaeli.tif \
    --kontur 1 --hacim-kotu 42.5 --bicim hepsi

# Kollektör ekseni boyunca döndürülmüş 10 m karelaj
python karelaj.py uret --alan guzergah.kml --aralik 10 --donme 37.5 --tampon 15

# ED50 dilim numarası önekli koordinatlarda, boşluk ayırıcılı NCN
python karelaj.py uret --alan saha.kml --sistem ED50-GK10 \
    --ncn-profil netcad-bosluk

# Düşey datum farkı düzeltilmiş, satır-sütun numaralı çıktı
python karelaj.py uret --alan saha.kml --aralik 20 \
    --kot-kaydirma -0.35 --no-profil satir-sutun --no-onek K --kod KARELAJ
```

## Doğruluk ve doğrulama

Araç, bağımsız gerçeklemelere karşı sınanmıştır:

| Bileşen | Karşılaştırıldığı yazılım | Sonuç |
|---|---|---|
| Transverse Mercator izdüşümü | PROJ (pyproj), 13 sistem x 300 nokta | en büyük fark **0,10 mm** |
| Meridyen yakınsaması | PROJ `get_factors` | en büyük fark **0,003 yay saniyesi** |
| Nokta ölçek faktörü | PROJ `get_factors` | en büyük fark **3,2 × 10⁻⁸** |
| GeoTIFF okuyucu | GDAL / rasterio, 62 yapılandırma | **birebir** (5 veri türü × 4 sıkıştırma × 3 öngörücü × şerit/karo × BigTIFF) |
| Hacim hesabı | Analitik çözüm (eğik düzlem) | fark **< %0,01** |
| Eş yükselti eğrileri | Analitik çözüm (eğik düzlem) | konum farkı **< 0,1 mm** |

İzdüşüm, Karney'in (2011) Krüger serisi yaklaşımıyla 6. dereceye kadar
hesaplanır; orta meridyenden ±4° içinde nanometre mertebesinde doğruluk verir.

Testler PROJ, GDAL ya da numpy kurulu olmadan çalışır:

```bash
python -m unittest discover -s testler -v
```

## Mevzuat ve kullanım koşulları

- **BÖHHBÜY uyumu.** Büyük Ölçekli Harita ve Harita Bilgileri Üretim
  Yönetmeliği, ülke temel jeodezik referans sistemini **TUREF (ITRF96)** ve
  izdüşümü **3 derecelik dilimli TM** olarak tanımlar; yükseklikler **TUDKA-99
  ortometrik** kotlardır. Aracın varsayılan ayarları bu tanıma uygundur.
  Ancak yönetmelik kapsamındaki **kesin harita üretiminde**, kot değerlerinin
  yönetmeliğin öngördüğü doğruluk sınıfını sağlaması gerekir; küresel modeller
  bu sınıfı karşılamaz. Bu araç, yönetmelik kapsamındaki ölçme işinin yerine
  geçecek bir kaynak değil, etüt ve planlama aşamasında kullanılacak bir
  yardımcıdır.
- **Veri kaynağı lisansları.** Google Earth'ün kendisi ya da döşemeleri
  kazınmaz. Google verisi yalnızca resmî **Elevation API** üzerinden, kullanıcının
  kendi anahtarı ve Google ile yaptığı sözleşme kapsamında okunur. Açık
  servislerin (OpenTopoData, Open-Elevation) ve uydu görüntüsü döşemelerinin
  kendi kullanım koşulları geçerlidir; kurumsal ve ticari kullanımda ilgili
  sağlayıcının koşulları denetlenmelidir.
- **İhale ve keşif dosyaları.** 4734 sayılı Kamu İhale Kanunu kapsamında
  hazırlanan yaklaşık maliyet, keşif ve metraj cetvellerinde kullanılacak
  kotların ölçüye dayanması esastır. Bu araçtan alınan kotlar bu belgelerde
  doğrudan kullanılacaksa, kaynağın ve doğruluğunun teknik raporda açıkça
  belirtilmesi ve sahada doğrulanması gerekir. Üretilen `-rapor.txt` dosyası
  bu beyanı hazır olarak içerir.
- **Veri güvenliği.** Arayüz yalnızca yerel adresi dinler ve dışarıya veri
  göndermez. Çevrimiçi kot kaynağı seçildiğinde, sorgulanan **nokta
  koordinatları** ilgili servise gider. Gizlilik dereceli proje alanlarında
  yerel SYM kaynağını kullanın.

## Sorun giderme

| Belirti | Çözüm |
|---|---|
| `sunucuya erişilemedi` | Kurum vekil sunucusu (proxy) ayarlarını denetleyin. `HTTPS_PROXY` ortam değişkeni ayarlıysa araç bunu kendiliğinden kullanır. Erişim yoksa `--kaynak yerel` ile kendi SYM verinizi kullanın |
| `HTTP 429` / işlem çok yavaş | OpenTopoData açık sunucusu saniyede 1 istek kabul eder. Aralığı büyütün, alanı küçültün ya da kurum içi sunucu kurun |
| Google `REQUEST_DENIED` | Elevation API etkin mi, anahtar kısıtları uygun mu, faturalandırma açık mı denetleyin |
| `nokta sayısı güvenlik sınırını aşıyor` | Aralığı büyütün veya `--azami-nokta` değerini yükseltin. 1 km²'lik alanda 5 m aralık 40 000 nokta demektir |
| NCN dosyası boş | Noktaların kotu okunamamış. `--ncn-kotsuz sifir` kullanın ya da kaynağın kapsama alanını denetleyin |
| Netcad noktaları yanlış yere koyuyor | Netcad'deki "Nokta Oku" sütun eşlemesiyle `--ncn-sutun` düzeni aynı mı? Y sağa, X yukarı değerdir. Proje koordinat sistemi ile `--sistem` aynı mı? |
| Kotlar sistematik olarak kaymış | Düşey datum farkıdır. Sahadaki nivelman noktalarından farkı ölçüp `--kot-kaydirma` ile uygulayın |
| `SYM dosyasında koordinat sistemi bilgisi yok` | `--dem-sistemi ITRF96-TM30` gibi açıkça belirtin |
| `karoların koordinat sistemleri farklı` | Klasördeki karoları tek sisteme getirin ya da tek dosya verin |
| Haritada görüntü gelmiyor | Uydu döşemeleri internetten çekilir; kurum güvenlik duvarı engelliyor olabilir. Koordinat girerek ve yerel SYM ile çalışmayı sürdürebilirsiniz |

## Testler ve dosya düzeni

```bash
cd kot-karelaj
python -m unittest discover -s testler -v     # 92 test
```

```
kot-karelaj/
├── karelaj.py              Hızlı başlatıcı
├── pyproject.toml          Paket tanımı (kurulum isteğe bağlı)
├── karelaj/
│   ├── cli.py              Komut satırı arayüzü
│   ├── sunucu.py           Yerel harita arayüzü sunucusu
│   ├── web/index.html      Harita arayüzü (bağımsız, kütüphanesiz)
│   ├── geodezi.py          TM izdüşümü, datum dönüşümü, Türkiye dilim kataloğu
│   ├── geometri.py         Alan tanımı ve poligon dosyası okuma
│   ├── izgara.py           Karelaj üretimi
│   ├── raster.py           GeoTIFF / ASCII Grid / SRTM okuyucu
│   ├── kontur.py           Eş yükselti eğrileri
│   ├── hacim.py            Karelaj yöntemiyle hacim hesabı
│   ├── onbellek.py         SQLite kot önbelleği
│   ├── bicim.py            Türkçe sayı biçimlendirme
│   ├── kaynaklar/          Kot kaynakları (çevrimiçi servisler + yerel SYM)
│   └── yazicilar/          NCN, CSV, XYZ, DXF, KML, GeoJSON, rapor
├── ornekler/               Örnek alan dosyaları ve örnek SYM
└── testler/                Test paketi
```

## Lisans

MIT.
