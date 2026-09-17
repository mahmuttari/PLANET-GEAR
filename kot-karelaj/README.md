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
- [Windows uygulaması (exe)](#windows-uygulaması-exe)
- [Hızlı başlangıç](#hızlı-başlangıç)
- [Harita arayüzü](#harita-arayüzü)
- [Google Earth ile birlikte çalışma](#google-earth-ile-birlikte-çalışma)
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

Üç kullanım yolu var. Kurum bilgisayarında en kolayı birincisidir.

**1. Hazır Windows uygulaması (Python gerekmez).** Tek dosyalık
`KotKarelaji.exe`. Bakınız: [Windows uygulaması (exe)](#windows-uygulaması-exe).

**2. Çift tıklanan başlatıcı (Python gerekir).** Depoyu indirin,
`kot-karelaj` klasöründeki **`Baslat.vbs`** dosyasına çift tıklayın. Komut
penceresi açılmadan arayüz tarayıcıda gelir. Komut penceresini görmek
isterseniz `baslat.bat` dosyasını kullanın.

**3. Komut satırı (Python gerekir).**

```bash
git clone <bu-depo>
cd PLANET-GEAR/kot-karelaj
python karelaj.py --help
```

Python yolunu kullanacaksanız gereksinim **Python 3.8 veya üzeridir**; başka
hiçbir şey kurulmaz. Windows'ta `python` komutu tanınmıyorsa `py` deneyin.
Python kurulu değilse python.org'dan kurun ve kurulum ekranındaki
**"Add Python to PATH"** kutusunu işaretleyin.

İsteğe bağlı olarak sisteme kurulabilir (`karelaj` komutu her yerden çalışır):

```bash
pip install .
karelaj --help
```

## Windows uygulaması (exe)

Kurulum, Python ve yönetici yetkisi gerektirmeyen tek dosyalık bir uygulama
üretilebilir. Dosyayı USB belleğe kopyalayıp başka bir bilgisayarda da
çalıştırabilirsiniz.

### Hazır dosyayı indirmek

En kolay yol **Sürümler** sayfasıdır; giriş yapmak gerekmez ve bağlantı
hiç değişmez:

- Sürüm sayfası: <https://github.com/mahmuttari/PLANET-GEAR/releases/tag/son-surum>
- Doğrudan indirme: <https://github.com/mahmuttari/PLANET-GEAR/releases/download/son-surum/KotKarelaji.exe>

Depoya her gönderimde GitHub Actions uygulamayı yeniden derler ve bu sürümü
günceller; dosya daima en son derlemeyi yansıtır.

Aynı dosyalar çalışmanın **Artifacts** bölümünde de bulunur (**Actions**
sekmesi > "Windows uygulaması (.exe) oluştur" > en üstteki yeşil tikli
çalışma > sayfanın altı). Artefaktları indirmek için GitHub'a giriş yapmış
olmanız gerekir; giriş yapmadan açılan artefakt bağlantısı 404 verir.

Sürüm sayfasında (ya da artefakt ZIP'inin içinde) üç dosya vardır:

| Dosya | Ne zaman? |
|---|---|
| **`KotKarelaji.exe`** | Günlük kullanım. Çift tıklayın, **komut penceresi açılmaz**, doğrudan tarayıcıda harita arayüzü gelir |
| `KotKarelaji-konsol.exe` | Komut satırı kullanımı. Aynı programdır, çıktıyı komut penceresine yazar |

Penceresiz sürümü kapatmak için arayüzdeki sağ üstteki **Uygulamayı kapat**
düğmesini kullanın. Konsolu olmadığı için ekran çıktısı
`Belgeler\Kot Karelaji\kot-karelaji-gunluk.txt` dosyasına yazılır; bir
sorun çıkarsa oraya bakın. Ölümcül hatalar ayrıca uyarı kutusuyla bildirilir.

### Kendiniz üretmek

İnternet kısıtlıysa ya da dosyayı kendiniz derlemek isterseniz, `kot-karelaj`
klasöründeki **`paketle\exe-olustur.bat`** dosyasına çift tıklayın. Betik
PyInstaller'ı kurar, uygulamayı paketler ve `kot-karelaj\dist\KotKarelaji.exe`
dosyasını üretir. Elle yapmak isterseniz:

```bash
pip install pyinstaller
pyinstaller paketle/kot-karelaj.spec --noconfirm --clean
```

### Uygulamanın davranışı

| Durum | Ne olur |
|---|---|
| Çift tıklama | Harita arayüzü açılır (`arayuz` komutu varsayılır) |
| Çıktı klasörü | `Belgeler\Kot Karelaji` (Python sürümünde bulunulan klasördeki `cikti`) |
| Komut satırı | `KotKarelaji-konsol.exe uret --alan saha.kml --aralik 25` gibi tüm komutlar çalışır |
| Kapatma | Arayüzdeki **Uygulamayı kapat** düğmesi. Tarayıcı sekmesi kapatılıp unutulursa uygulama yarım saat sonra kendiliğinden kapanır |
| Kapı meşgulse | Sıradaki boş kapı kendiliğinden seçilir; arayüz yine açılır |
| Hata (penceresiz) | Uyarı kutusu çıkar, ayrıntı günlük dosyasına yazılır |
| Hata (konsollu) | İleti yazılır ve pencere "Enter'a basın" diyerek açık kalır |

> Uygulama imzalı değildir. Windows SmartScreen "Bilinmeyen yayımcı" uyarısı
> verirse **Daha fazla bilgi > Yine de çalıştır** deyin. Kurum
> bilgisayarlarında uygulama beyaz listesi varsa BT biriminden izin gerekebilir.

## Hızlı başlangıç

**Yol 1 — Harita arayüzü (en kolay).** Tarayıcıda uydu görüntüsü üzerinde alan
çizip indirirsiniz. `KotKarelaji.exe` dosyasına çift tıklayın, ya da:

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

## Google Earth ile birlikte çalışma

Google Earth Pro'nun eklenti (plugin) desteği yoktur; içine düğme eklenemez.
Bunun yerine iki program arasında **KML dosyasıyla gidip gelinir**. Pratikte
tek tıklık bir akıştır ve gündelik kullanımda fazlasıyla yeterlidir.

### 1. Alanı Google Earth'te çizip araca vermek

1. Google Earth Pro'da sahayı ekrana getirin.
2. Üstteki araç çubuğundan **Poligon Ekle** düğmesine basın (sarı beşgen
   simge). Açılan pencereye bir ad yazın, sonra haritada köşeleri tıklayarak
   alanı çizin ve **Tamam** deyin.
3. Sol taraftaki **Yerlerim** listesinde oluşan öğeye sağ tıklayın,
   **Yeri Farklı Kaydet** deyin ve **`.kml`** olarak kaydedin.
4. Kot Karelajı'nın harita arayüzünde bu dosyayı **haritanın üzerine
   sürükleyip bırakın**. Alan yüklenir, harita kendiliğinden oraya gider.

Komut satırını kullanıyorsanız aynı dosyayı doğrudan verin:

```bash
python karelaj.py uret --alan "C:\Users\adiniz\Desktop\saha.kml" --aralik 25
```

> Google Earth bir dosyada birden çok yer işareti tutabilir. Tek bir tanesini
> kullanmak isterseniz `--alan-katman "Saha adı"` ile adını verin.

### 2. Sonucu Google Earth'te denetlemek

Çıktı biçimleri arasında **KML** işaretliyse (varsayılan olarak işaretlidir),
üretilen `.kml` dosyasına çift tıklayın. Google Earth açılır ve şunları
gösterir:

- Çalışma alanı sınırı (kırmızı poligon),
- Karelaj noktaları (her birine tıklayınca nokta numarası, Y, X, Z ve
  koordinat sistemi görünür),
- Varsa eş yükselti eğrileri, arazi yüzeyine giydirilmiş olarak.

Bu, **noktaların doğru yere oturduğunu gözle denetlemenin en hızlı yoludur**.
Netcad'e aktarmadan önce bu adımı atlamayın; yanlış dilim ya da yanlış datum
seçimi burada hemen görülür.

Dosyayı kalıcı tutmak isterseniz Google Earth'te **Yerlerim** altına
sürükleyin; program her açıldığında yüklü gelir.

### 3. Kot değerleri hakkında

Google Earth'ün ekranın altında gösterdiği yükseklik ile bu aracın yazdığı kot
aynı kaynaktan gelmez; araç varsayılan olarak OpenTopoData'yı kullanır.
Birebir Google Earth arazi verisini istiyorsanız kaynak olarak **Google
Elevation API**'yi seçin ve kendi API anahtarınızı girin. Bu, Google verisine
erişmenin resmî ve lisanslı yoludur.

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

**Aralığı kaynağa göre seçin.** Karelaj aralığının, kot kaynağının
çözünürlüğünden çok daha sık olması yeni bilgi üretmez; aynı hücrenin ara
değeri tekrar tekrar okunur. Çevrimiçi kaynaklarda bu, istek sayısını ve
kota tüketimini boşa katlar. Araç, aralık kaynağın çözünürlüğünün yarısından
küçükse uyarır.

| Kaynak | Çözünürlük | Anlamlı en sık aralık | 1 km² için istek |
|---|---|---|---|
| SRTM / ASTER (OpenTopoData, Google) | ~30 m | 15-30 m | 10-40 |
| EU-DEM | ~25 m | 12-25 m | 16-64 |
| Kurumun 1/1000 hâlihazırdan üretilmiş SYM | 1-5 m | 1-5 m | istek yok |

Örnek: 82 ha'lık bir alanda 3 m aralık 91.563 nokta ve OpenTopoData'da 916
istek demektir; açık sunucunun günlük 1.000 istek sınırına dayanır, tamamı
30 m'lik verinin ara değeridir. Aynı alan 25 m aralıkla 1.300 nokta ve 13
istektir. Daha sık karelaj gerekiyorsa doğru yol kurumun kendi SYM verisini
kullanmaktır.

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

Önce bir yanlış anlaşılmayı gidermek gerekir: **"Google Earth API" diye
kullanılabilir bir servis yoktur.** Eskiden var olan Google Earth API
(tarayıcı eklentisi) 2015'te kapatıldı. Google'ın arazi yüksekliği verisine
bugün erişmenin yolu, Google Maps Platform bünyesindeki **Elevation API**'dir.
Google Earth'ün gösterdiği yüzey ile aynı kaynaktan beslenir.

#### Anahtar nasıl alınır

> Menü adları aşağıda **İngilizce** verilmiştir; Google Cloud konsolu
> çoğu kurulumda İngilizce açılır. Konsolunuz Türkçe ise karşılıkları
> parantez içindedir.

1. [console.cloud.google.com](https://console.cloud.google.com) adresine
   Google hesabınızla girin.
2. Üstteki proje seçicisinden **New Project** (*Yeni Proje*) ile bir proje
   oluşturun (örn. "ISU Kot Karelaji") ve bu projeyi seçin.
3. Sol menüden **Billing** (*Faturalandırma*) bölümüne girip projeye bir
   faturalandırma hesabı bağlayın. Elevation API, kullanım ücretsiz
   aralıkta kalsa bile faturalandırma hesabı olmadan çalışmaz.
4. Sol menüden **APIs & Services > Library** (*API'ler ve Hizmetler >
   Kitaplık*) yolunu izleyin, arama kutusuna **Elevation API** yazın, çıkan
   **Maps Elevation API** kaydına girip **Enable** (*Etkinleştir*) deyin.

   > **Daha kısa yol:** Konsolun hamburger menüsünden (☰) doğrudan
   > **Google Maps Platform** bölümüne girebilirsiniz. Bu bölümün kendi sol
   > menüsünde **APIs & Services**, **Quotas** ve **Keys & Credentials**
   > başlıkları yan yana durur; harita işleri için gereken her şey oradadır.
   > **APIs & Services** sayfasında **PRODUCTS** süzgecinden **Maps**'i
   > seçince **Elevation API** listede çıkar; sağındaki **Enable**
   > bağlantısına basmanız yeter. **STATUS** süzgecinden **Enabled**'ı
   > seçerek hangi API'lerin zaten açık olduğunu görebilirsiniz.
5. **APIs & Services > Credentials** (*Kimlik Bilgileri*) sayfasına gidin.
   Google Maps Platform bölümündeyseniz aynı sayfanın adı
   **Keys & Credentials**'tır. **Create credentials > API key** deyin. Oluşan anahtarı kopyalayın
   (`AIza...` ile başlar).
> **En sık yapılan hata:** API anahtarı ile etkinleştirilen API'nin **aynı
> projede** olması gerekir. Anahtarı bir projede oluşturup Elevation API'yi
> başka bir projede etkinleştirirseniz istekler `REQUEST_DENIED` döner.
> Konsolun üst çubuğundaki proje adının her iki adımda da aynı olduğundan
> emin olun.
>
> Elevation API'nin gerçekten etkin olup olmadığını **API'ler ve Hizmetler >
> Etkin API'ler ve hizmetler** listesinden denetleyebilirsiniz. Bütçe
> oluştururken çıkan "Services" (Servisler) filtresinde de yalnızca o
> kapsamda kullanılan servisler listelenir; Elevation API orada
> görünmüyorsa büyük olasılıkla henüz etkinleştirilmemiştir.

6. Anahtarın yanındaki kalem simgesine basıp **kısıtlayın**:
   - **API restrictions** (*API kısıtlamaları*): **Restrict key** seçip
     yalnızca **Maps Elevation API**'yi işaretleyin.
   - **Application restrictions** (*Uygulama kısıtlamaları*): bilgisayarın
     bağlantı türüne göre seçin, aşağıdaki tabloya bakın.
7. **Save** deyin. Kısıtlamaların etkin olması birkaç dakika sürebilir.

**Uygulama kısıtlaması nasıl seçilir?**

| Kurulum yeri | Seçim | Neden |
|---|---|---|
| Kurum ağı, sabit IP | **IP addresses** + dış IP adresi | En güçlü koruma; anahtar sızsa bile başka yerden kullanılamaz |
| Ev bağlantısı, değişken IP | **None** (kısıtlamasız bırakın) | Ev IP'si modem yeniden başlayınca değişir; kısıtlama koyarsanız anahtar habersizce çalışmaz olur |

**HTTP referrers** seçeneğini hiçbir durumda seçmeyin. Araç istekleri
sunucu tarafından attığı için bu kısıtlama daima `REQUEST_DENIED` verir.

Uygulama kısıtlamasını **None** bırakmak zorunda kaldıysanız korumasız
kalmazsınız. Gerçek güvenlik ağınız şu ikisidir ve ikisi de zaten
kurulacak:

- **API kısıtlaması:** Anahtar yalnızca Elevation API'yi çağırabilir.
  Sızsa bile başka Google servisiyle kullanılamaz.
- **Günlük kota sınırı:** Aşağıdaki kota adımıyla günlük istek sayısına
  tavan koyarsınız. Anahtar tamamen ele geçse bile günlük zarar bu tavanla
  sınırlıdır ve küçük bir tutardır.

Dış IP adresinizi öğrenmek isterseniz tarayıcıda "ip adresim" aratmanız
yeterlidir. Sabit IP'niz olup olmadığını internet sağlayıcınıza
sorabilirsiniz; Türkiye'de ev aboneliklerinde IP çoğunlukla değişkendir.

#### Anahtarı araca verme

Üç yol vardır:

**Harita arayüzünde:** Kot kaynağı olarak "Google Elevation API"yi seçin,
açılan **Google API anahtarı** kutusuna yapıştırın.

**Komut satırında:**

```bash
python karelaj.py uret --alan saha.kml --kaynak google --google-anahtar AIza...
```

**Ortam değişkeniyle** (anahtarı her seferinde yazmamak için):

```bash
# Windows (PowerShell, yalnızca o pencere için)
$env:GOOGLE_ELEVATION_ANAHTARI = "AIza..."

# Windows (kalıcı)
setx GOOGLE_ELEVATION_ANAHTARI "AIza..."

# Linux / macOS
export GOOGLE_ELEVATION_ANAHTARI="AIza..."
```

#### Maliyet ve kota

Ücretlendirme **istek başınadır**, nokta başına değil. Bu araç varsayılan
olarak **istek başına 300 nokta** gönderir (`--toplu` ile en çok 480'e
çıkarılabilir). Buna göre:

| Karelaj | Nokta sayısı | Gereken istek |
|---|---|---|
| 1 km² alan, 50 m aralık | ~400 | 2 |
| 1 km² alan, 25 m aralık | ~1.600 | 6 |
| 1 km² alan, 10 m aralık | ~10.000 | 34 |
| 10 km² alan, 25 m aralık | ~16.000 | 54 |

Google Maps Platform'un aylık ücretsiz kullanım hakkı ve birim fiyatları
zaman zaman değişir; güncel değerleri
[Google Maps Platform fiyatlandırma sayfasından](https://developers.google.com/maps/billing-and-pricing/pricing)
denetleyin.

Araç, okuduğu her kotu yerel önbelleğe yazar; aynı alanı yeniden
çalıştırdığınızda o noktalar için tekrar istek atılmaz.

#### Harcamayı sınırlama: iki ayrı şey

Bu ikisi karıştırılır ama farklı işler yapar. **İkisini birden kurun.**

**1. Bütçe uyarısı — yalnızca haber verir, harcamayı durdurmaz.**

Google Cloud konsolunda **Billing > Budgets & alerts**
(*Faturalandırma > Bütçeler ve uyarılar*) yolunu izleyin:

1. **Create budget** düğmesine basın.
2. **Name** kutusuna anlamlı bir ad yazın (örn. "Elevation API aylik sinir").
3. **Scope** (*Kapsam*) bölümünde **Time range** değerini **Monthly**
   bırakın ve Elevation API'yi etkinleştirdiğiniz projeyi seçin.
4. Aynı bölümdeki **Services** filtresine `elevat` yazıp çıkan
   **Maps Elevation API** kaydını işaretleyin, **OK** deyin. Böylece bütçe
   yalnızca bu servisin harcamasını izler; aynı projede başka işler varsa
   onlar bütçeye karışmaz. Liste boş çıkıyorsa API henüz etkinleştirilmemiş
   demektir; filtreyi boş bırakıp önce API'yi etkinleştirin.
5. **Amount** (*Tutar*) bölümünde **Budget type** olarak
   **Specified amount** seçin, **Target amount** kutusuna aylık üst
   sınırınızı yazın (örn. 200).
6. **Actions** (*Eylemler*) bölümünde eşikleri %50, %90 ve %100 olarak
   ayarlayın, **Trigger on** değerini **Actual** bırakın.
   **Manage notifications** altında **Email alerts to billing admins and
   users** işaretli olsun.
7. **Save** (*Kaydet*) deyin.

Önemli: bütçe dolduğunda Google **hizmeti kapatmaz**, yalnızca e-posta
gönderir. Gerçek tavan için ikinci adım gerekir.

**2. Kota sınırı — harcamayı fiilen durdurur.**

En kısa yol: sol menüden **Google Maps Platform > Quotas**. Açılan sayfada
üstteki **API** listesinden **Maps Elevation API**'yi seçin.

Bu menü yoksa ikinci yol: **APIs & Services > Enabled APIs & services**
listesinden **Maps Elevation API**'ye tıklayıp **Quotas & System Limits**
sekmesine girin. Sınırı değiştirmek için satırın solundaki kutuyu
işaretleyip kalem simgesine (**Edit**) basın, yeni değeri yazıp
**Submit request** deyin.

Düşürülecek iki değer:

| Sınır | Öneri | Karşılığı |
|---|---|---|
| Günlük istek (*Requests per day*) | 300 | Günde ~90.000 nokta; olağan kullanımın çok üstünde |
| Dakikalık istek (*Requests per minute*) | 60 | Aracın varsayılan hızının üstünde, darboğaz yapmaz |

Sınır dolduğunda API `OVER_QUERY_LIMIT` ya da `OVER_DAILY_LIMIT` döner;
araç bunu Türkçe bir iletiyle bildirir ve o noktaları kotsuz bırakır.
Fatura büyümez.

**Günlük sınır neden tam olarak 300?** Google Maps Platform'un Essentials
katmanındaki her servis için aylık belirli sayıda ücretsiz çağrı hakkı
vardır (bu yazının hazırlandığı sırada SKU başına aylık 10.000 çağrı).
Günlük sınırı, **aylık azami toplam bu hakkın altında kalacak** şekilde
seçerseniz en kötü durumda bile fatura sıfır olur:

```
300 istek/gün x 31 gün = 9.300 istek/ay  <  10.000 ücretsiz çağrı
```

Yani kota her gün sonuna kadar dolsa, anahtarınız sızsa, biri kötüye
kullansa bile aylık ödemeniz **0** olur. Günlük sınırı 500 yaparsanız aylık
azami 15.000 çağrıya çıkar; 5.000 çağrı ücretli olur ve Essentials
katmanının 1.000 çağrı başına ücretiyle çarpılır.

Ücretsiz çağrı hakkı ve birim fiyat zaman zaman değişir. Kendi hesabınıza
uygulanan gerçek değerleri konsolda **Billing > Pricing** sayfasından
görebilirsiniz; genel bilgi için
[Google Maps Platform fiyatlandırma sayfasına](https://mapsplatform.google.com/pricing/)
bakın. Ücretsiz hak değişirse günlük sınırı buna göre yeniden hesaplayın:

```
günlük sınır = aylık ücretsiz çağrı hakkı / 31  (aşağı yuvarlayın)
```

Bu iki ayarla, anahtarınız sızsa bile azami zarar önceden bellidir.

#### Güvenlik

- Anahtar bir paroladır. Depoya, ortak klasöre veya e-postaya koymayın.
- Araç anahtarı **hiçbir çıktı dosyasına yazmaz**. Teknik rapordaki
  "çalıştırılan komut" bölümünde bile `--google-anahtar ***` olarak
  maskelenir.
- Anahtar yalnızca sizin bilgisayarınızdan Google'a gider; arada başka bir
  sunucu yoktur.
- Sabit IP'li bir kurum ağındaysanız anahtarı IP ile kısıtlayın. Ev
  bağlantısı gibi değişken IP'li yerlerde bu kısıtlama anahtarı habersizce
  çalışmaz hale getirir; onun yerine API kısıtlamasına ve günlük kota
  sınırına güvenin.

#### Buna gerçekten gerek var mı?

Çoğu durumda hayır. Google verisi de küresel bir modeldir ve Türkiye'de
büyük ölçüde SRTM tabanlıdır; doğruluğu varsayılan OpenTopoData seçeneğinden
belirgin biçimde daha iyi olmayabilir. Kesin kot gerektiren işlerde doğru
yol, kurumun kendi hâlihazır SYM verisini kullanmaktır
(`--kaynak yerel --sym ...`). Google seçeneği, özellikle "Google Earth'te
gördüğüm kot ile aynısını istiyorum" denildiğinde anlamlıdır.

### Önbellek

Çevrimiçi servislerden okunan her kot, SQLite tabanlı bir önbelleğe yazılır
(`~/.karelaj/kot-onbellek.sqlite`). Aynı alanda aralığı değiştirip yeniden
çalıştırdığınızda daha önce sorgulanmış noktalar tekrar indirilmez; yarıda
kesilen iş kaldığı yerden sürer.

Yalnızca **başarıyla okunmuş** kotlar saklanır. Kota dolması, hız sınırı ya
da ağ kesintisi yüzünden okunamayan noktalar önbelleğe yazılmaz; sorun
giderilince aynı komut yeniden çalıştırıldığında yalnızca o noktalar
sorulur. Kaynak art arda üç istekte hata verirse okuma durdurulur ve kalan
noktalar kotsuz bırakılır; kalan her dilim için yeniden deneyip saatlerce
beklenmez.

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

**Varsayılan çıktı** (`--ncn-profil netcad`) Netcad'in kendi yazdığı nokta
dosyalarıyla birebir aynı düzendedir:

```
1/4 429903.20 4064858.18 636.44 0 "YPA1" "" ""
2/5 429894.98 4064863.90 632.89 0 "KDA" "" ""
```

Sekiz alan, tek boşlukla ayrılır:

| Sıra | Alan | Açıklama |
|---|---|---|
| 1 | NoktaNo | Nokta numarası |
| 2 | Y | Sağa değer (easting), 2 ondalık |
| 3 | X | Yukarı değer (northing), 2 ondalık |
| 4 | Z | Kot, 2 ondalık |
| 5 | KodNo | Netcad'in sayısal kod alanı; varsayılan `0` |
| 6 | "Kod" | Nokta kodu, çift tırnak içinde |
| 7 | "" | Boş açıklama alanı |
| 8 | "" | Boş açıklama alanı |

Satır sonu **CRLF**, kodlama **cp1254** (Windows Türkçe).

**Nokta numarasındaki bölü işareti.** Netcad'in kesit dosyalarında numaralar
`kesit/nokta` biçimindedir. Karelajda aynı görünümü satır/sütun numarasıyla
elde edersiniz:

```bash
--no-profil satir-sutun --no-ayirac /
```

Bu, `1/13`, `2/9` gibi numaralar üretir. Varsayılan numaralandırma ise düz
sıra numarasıdır (`1`, `2`, `3` ...).

### Hazır profiller

| `--ncn-profil` | Düzen | Ayırıcı | Ondalık | Tırnak |
|---|---|---|---|---|
| `netcad` (varsayılan) | `no y x z kodno kod bos bos` | boşluk | 2 | var |
| `netcad-virgul` | `no y x z kod` | virgül | 3 | yok |
| `netcad-bosluk` | `no y x z kod` | boşluk, sabit genişlik | 3 | yok |
| `no-y-x-z` | `no y x z` | virgül | 3 | yok |
| `no-x-y-z-kod` | `no x y z kod` | virgül | 3 | yok |
| `y-x-z` | `y x z` | virgül | 3 | yok |
| `x-y-z` | `x y z` | virgül | 3 | yok |
| `ayrintili` | `no y x z kod enlem boylam` + başlık | virgül | 3 | yok |

### Elle ayarlama

```bash
--ncn-sutun no,x,y,z,kod        # sütun sırası
--ncn-ayirac bosluk             # virgul | bosluk | sekme | noktali-virgul
--ncn-ondalik 3                 # koordinat ondalık basamağı
--ncn-ondalik-z 2               # kot ondalık basamağı
--ncn-baslik                    # başlık satırı ekle
--ncn-tirnak yok                # metin alanlarındaki tırnakları kaldır
--ncn-kod-no 0                  # sayısal kod alanına yazılacak değer
--ncn-kodlama utf-8             # varsayılan cp1254
--ncn-satir-sonu lf             # varsayılan crlf
```

Kullanılabilir sütunlar: `no`, `y`, `x`, `z`, `kod`, `kodno`, `bos`,
`enlem`, `boylam`, `satir`, `sutun`, `aciklama`. Bunlardan `kodno` sayısal
kod alanını, `bos` ise boş bir alanı yazar; `kod`, `aciklama` ve `bos`
sütunları tırnak açıkken çift tırnağa alınır.

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
| Google `REQUEST_DENIED` | Elevation API etkin mi, anahtar kısıtları uygun mu, faturalandırma açık mı denetleyin. En sık iki neden: anahtar ile etkinleştirilen API'nin farklı projelerde olması, ya da değişken IP'li bir bağlantıda anahtara IP kısıtlaması konmuş olması |
| Bütçe ekranındaki servis listesinde Elevation API yok | O projede henüz etkinleştirilmemiştir. **API'ler ve Hizmetler > Kitaplık** yolundan etkinleştirin |
| `nokta sayısı güvenlik sınırını aşıyor` | Aralığı büyütün veya `--azami-nokta` değerini yükseltin. 1 km²'lik alanda 5 m aralık 40 000 nokta demektir |
| NCN dosyası boş | Noktaların kotu okunamamış. `--ncn-kotsuz sifir` kullanın ya da kaynağın kapsama alanını denetleyin |
| Çok sayıda nokta kotsuz, "0 istek, hepsi önbellekten" | Önceki çalıştırmada kota dolmuş ya da ağ kesilmiş. Aynı komutu yeniden çalıştırın; eksik noktalar yeniden sorulur. Aralık kaynağın çözünürlüğünden çok sıksa (örn. 30 m veride 3 m) aralığı büyütün |
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
├── Baslat.vbs              Çift tıklayınca komut penceresiz açar
├── baslat.bat              Komut penceresiyle açar (hata ayıklama için)
├── paketle/                Windows uygulaması (.exe) üretme dosyaları
│   ├── kot-karelaj.spec    PyInstaller tanımı
│   ├── exe-olustur.bat     Çift tıklayarak exe üretir
│   └── kot-karelaj.ico     Uygulama simgesi
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
