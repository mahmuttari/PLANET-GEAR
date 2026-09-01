# WhatsApp Masraf Fiş/Dekont İndirici

**"Dsi TBMM Termal Masraf"** WhatsApp grubunda, grubun kurulduğu ilk günden bu yana
paylaşılmış **tüm PDF ve resim (fotoğraf) formatındaki masraf fişi ve
dekontları** bulup bilgisayarınıza indiren araç.

## Özellikler

- QR kod ile WhatsApp Web oturumu açar; oturum kaydedilir, sonraki
  çalıştırmalarda yeniden QR okutmak gerekmez.
- Grubun **tüm mesaj geçmişini** (en eskiden en yeniye) tarar.
- Yalnızca **resim** ve **PDF** dosyalarını indirir; diğer türleri
  (video, ses, Word/Excel vb.) kapsam dışı bırakır.
- Dosyaları `Yıl-Ay` klasörlerine, `Tarih_Gönderen_OrijinalAd.uzantı`
  biçiminde anlamlı adlarla kaydeder.
- **Kaldığı yerden devam eder:** Betik yarıda kesilse veya tekrar
  çalıştırılsa bile daha önce indirilenleri yeniden indirmez; yalnızca
  eksikleri ve yeni gelenleri alır.
- Excel ile açılabilen `rapor.csv` dosyası üretir (tarih, gönderen, dosya,
  sonuç).
- Sunucuda süresi dolduğu için indirilemeyen eski medyaları raporlar ve
  bunlar için yedekten ayıklama betiği (`export-ayikla.js`) sunar.

## Kurulum

Gereksinim: [Node.js](https://nodejs.org) 18 veya üzeri.

```bash
git clone <bu-depo>
cd PLANET-GEAR
npm install
```

## Kullanım

```bash
npm start
# veya
node index.js
```

1. İlk çalıştırmada terminalde bir **QR kod** görüntülenir.
2. Telefonunuzda **WhatsApp > Ayarlar > Bağlı Cihazlar > Cihaz Bağla**
   menüsünden bu QR kodu okutun.
3. Betik grubu bulur, tüm geçmişi yükler ve indirmeye başlar. İlerleme
   terminalde adım adım gösterilir.

İndirilen dosyalar varsayılan olarak `indirilenler/` klasörüne kaydedilir:

```
indirilenler/
├── 2023-04/
│   ├── 2023-04-15_10-22-31_Ahmet Yılmaz_fis-market.jpg
│   └── 2023-04-18_16-05-02_Ayşe Demir_dekont.pdf
├── 2023-05/
│   └── ...
├── rapor.csv        ← tüm işlemlerin dökümü (Excel ile açılır)
└── .durum.json      ← kaldığı yerden devam bilgisi (silmeyin)
```

## Ayarlar

Ayarlar `config.js` dosyasından veya ortam değişkenleriyle değiştirilebilir:

| Ayar | Varsayılan | Açıklama |
|------|-----------|----------|
| `GRUP_ADI` | `Dsi TBMM Termal Masraf` | Taranacak grubun tam adı |
| `INDIRME_KLASORU` | `./indirilenler` | Dosyaların kaydedileceği yer |
| `AZAMI_MESAJ_SAYISI` | `1000000` | Yüklenecek azami mesaj sayısı (grubun toplamından büyük olduğu sürece tüm geçmiş taranır) |
| `YENIDEN_DENEME_SAYISI` | `3` | Başarısız indirme için tekrar sayısı |
| `CHROME_YOLU` | (boş) | Sistemde kurulu Chrome/Chromium yolu (isteğe bağlı) |

Örnek (farklı grup adı ile çalıştırma):

```bash
GRUP_ADI="Başka Grup" node index.js        # Linux/macOS
set GRUP_ADI=Başka Grup && node index.js   # Windows (cmd)
```

## Önemli: Çok eski medyalar hakkında

WhatsApp, medya dosyalarını sunucularında **sınırlı bir süre** tutar
(genellikle birkaç ay). Grubun ilk günlerine ait bazı dosyaların sunucu
kopyası silinmiş olabilir; bu durumda `index.js` o dosyayı indiremez ve
raporda **"BAŞARISIZ"** olarak işaretler.

Bu dosyalar telefonunuzda hâlâ duruyorsa **eksiksiz** almanın garantili
yolu, telefonun kendi yedeğini kullanmaktır:

1. Telefonda grubu açın: **Grup adı > Sohbeti Dışa Aktar > "Medya Dahil"**
   (iPhone'da: **Sohbeti Dışa Aktar > Medya Ekle**).
2. Oluşan ZIP dosyasını bilgisayara aktarın ve bir klasöre **çıkartın**.
3. Şu komutu çalıştırın:

```bash
node export-ayikla.js "ÇIKARTILAN_KLASÖRÜN_YOLU"
```

Betik, yedekteki **tüm PDF ve resimleri** bulur; sohbet dökümünden
(`_chat.txt`) tarih ve gönderen bilgisini eşleştirerek aynı klasör
düzeniyle `indirilenler/yedekten/` altına kopyalar ve ayrı bir
`rapor.csv` üretir.

> Not: WhatsApp'ın dışa aktarma özelliği bazı telefonlarda son ~40.000
> mesajla sınırlıdır; medya dahil dışa aktarmada bu sınır daha düşük
> olabilir. Çok büyük gruplarda iki yöntemi (index.js + yedek) birlikte
> kullanmak en eksiksiz sonucu verir.

## Bilinmesi gerekenler / Sorumluluk

- Bu araç, **kendi WhatsApp hesabınızla ve üyesi olduğunuz** bir gruptaki
  içerikleri kişisel arşivleme amacıyla indirmeniz içindir.
- Resmî WhatsApp API'si yerine WhatsApp Web otomasyonu
  ([whatsapp-web.js](https://wwebjs.dev)) kullanır; WhatsApp'ın hizmet
  şartları gereği otomasyon kullanımı hesap kısıtlaması riski taşıyabilir.
  Betik, istekler arasına bekleme koyarak bu riski azaltır.
- Grup içeriğinde kişisel veriler (KVKK kapsamında) bulunabileceğinden,
  indirilen dosyaları kurum içi veri güvenliği kurallarına uygun şekilde
  saklayınız.

## Sorun giderme

| Sorun | Çözüm |
|-------|-------|
| QR kod görünmüyor | Terminal penceresini büyütün veya yeniden çalıştırın |
| "Grup bulunamadı" | Betik, üyesi olduğunuz grupları listeler; grup adını oradan birebir kopyalayıp `GRUP_ADI` ayarına yazın |
| Chromium indirme hatası | Sistemdeki Chrome yolunu `CHROME_YOLU` ile verin |
| Oturum bozuldu / sürekli QR istiyor | `.wwebjs_auth` klasörünü silip yeniden QR okutun |
| Çok sayıda "BAŞARISIZ" | Normaldir (süresi dolmuş eski medya). Yukarıdaki "Çok eski medyalar" bölümündeki yedek yöntemini kullanın |
