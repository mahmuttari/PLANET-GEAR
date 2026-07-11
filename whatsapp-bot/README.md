# WhatsApp Baca Aralığı Botu

Bir WhatsApp grubundaki **fotoğrafları geçmişe dönük tarar**, her fotoğrafın
altına yazılan **baca aralığı adını (örn. `A20-A19`) resmin üzerine yazar** ve
bir klasöre kaydeder.

Belirttiğin tarihten **bugüne** kadar olan mesajlar taranır.

> Örnek: fotoğrafın altına yazılan `A20-A19`, resmin alt kısmına yarı saydam bir
> bant üzerine kalın beyaz (siyah kenarlıklı) olarak işlenir.

---

## Nasıl Çalışır?

- Geçmiş grup mesajlarını okumak için telefonunu **WhatsApp Web** üzerinden
  bağlar (`whatsapp-web.js`). İlk çalıştırmada bir **QR kod** okutulur; oturum
  `.wwebjs_auth/` altında saklandığından sonraki çalıştırmalarda tekrar
  istenmez.
- Her fotoğraf için baca aralığı adı önceliği:
  1. Fotoğrafın kendi açıklaması (caption) — örn. `A20-A19`,
  2. Yoksa, aynı kişiden **90 saniye** içinde gönderilmiş en yakın metin mesajı.
  3. Hiçbiri yoksa fotoğraf **en sonda elle isimlendirme** için biriktirilir
     (aşağıya bakın).
- Bu adı, resmin alt kısmına yarı saydam bant üzerine kalın beyaz yazıyla
  (siyah kenarlıklı, Türkçe karakter destekli) basar.
- Görseli, adı dosya adına da ekleyerek kaydeder ve bir CSV özeti üretir.

> ⚠️ **Not:** Resmi WhatsApp Cloud API geçmiş mesajları okuyamaz (yalnızca
> kurulumdan sonra geleni görür). Geriye dönük tarama için WhatsApp Web
> otomasyonu şarttır ve telefonunun çevrimiçi olması gerekir.

---

## Kurulum

Gereksinim: **Node.js ≥ 18** (Chromium'u whatsapp-web.js indirir).

```bash
cd whatsapp-bot
npm install
```

---

## Kullanım

Önce grubun tam adını görmek istersen:

```bash
npm run list-groups
```

Ardından taramayı başlat:

```bash
# 27 Haziran 2026'dan bugüne, "Saha Ekibi" grubunu tara
node src/index.js --group "Saha Ekibi" --since 2026-06-27
```

### Çıktılar

Sonuçlar varsayılan olarak `./output/` klasörüne kaydedilir:

- **Görseller:** dosya adı baca aralığı adını içerir, örn.
  `A20-A19_2026-06-27_12-00-00_905xx.jpg`.
- **Özet tablosu:** `output/ozet.csv` — Excel uyumlu (UTF-8 BOM, `;` ayraç).
  Sütunlar: `tarih; gonderen; baca_araligi_adi; dosya`.
- **Erişilemeyenler:** medyası indirilemeyen fotoğraflar varsa
  `output/erisilemeyen.csv` oluşturulur (`tarih; baca_araligi_adi; sebep`).

### Argümanlar

| Argüman | Zorunlu | Açıklama |
|---|---|---|
| `--group` | ✅ | Grup adı (kısmi eşleşme yeterli, büyük/küçük harf duyarsız) |
| `--since` | ✅ | Başlangıç tarihi, `YYYY-MM-DD`. Bu tarihten bugüne taranır |
| `--out` | ➖ | Çıktı klasörü (varsayılan `./output`) |
| `--limit` | ➖ | Taranacak en fazla mesaj sayısı (varsayılan `20000`) |
| `--list-groups` | ➖ | Sadece grupları listeler |
| `--help`, `-h` | ➖ | Yardım |

> Çok eski tarihli mesajları tarıyorsan `--limit` değerini artır (örn.
> `--limit 40000`). WhatsApp Web eski mesajları kademeli yüklediği için ilk
> çalıştırma biraz uzun sürebilir.

---

## Bazı fotoğraflara erişilemezse

Geçmişe gidildikçe bazı fotoğrafların medyası indirilemeyebilir. Bunun iki
nedeni vardır ve bot ikisini de ele alır:

1. **Yeterince eski mesaj yüklenmemiş olması** → `--limit` değerini artır
   (varsayılan artık `20000`).
2. **Çok eski medyanın telefonda/sunucuda önbellekte olmaması** → bot her
   indirmeyi **3 kez** dener; yine de olmazsa `erisilemeyen.csv`'ye yazar.

**En etkili çözüm:** Telefonunda WhatsApp grubunu açıp erişilemeyen eski
fotoğraflara kadar **yukarı kaydır** (telefon o medyayı yeniden indirir), sonra
botu **tekrar çalıştır**. Bot zaten kaydedilmiş görselleri atlar (idempotent),
yalnızca eksik olanları yeniden dener — baştan taramaz.

---

## Adı olmayan fotoğraflara elle isim verme

Bazı fotoğrafların altında baca aralığı adı yazmamış olabilir. Bot bunları
otomatik atlamaz; **en sonda tek tek** karşına getirir:

1. Fotoğrafın bir önizlemesini `output/isimsiz/` klasörüne kaydeder ve
   bilgisayarının **varsayılan görüntüleyicisinde açar** (sen ne olduğunu gör).
2. Komut satırında **baca aralığı adını yazmanı** ister:
   - Adı yaz + Enter → fotoğraf o adla işlenip normal görsellerle birlikte kaydedilir.
   - Boş bırak + Enter → o fotoğrafı atlar (önizleme `isimsiz` klasöründe kalır).
   - `q` + Enter → kalan hepsini bırakır.
3. Daha önce elle isim verdiğin fotoğraflar tekrar sorulmaz (idempotent).

> Bu adım için botu **normal bir komut satırında** (etkileşimli) çalıştırmalısın;
> girdi verilemeyen bir ortamda bot sormayı atlar ve sadece kaç tane olduğunu bildirir.

---

## Dosya Yapısı

```
whatsapp-bot/
├── package.json
├── src/
│   ├── index.js       # CLI + ana akış (tara → adı bul → resme yaz → kaydet)
│   ├── whatsapp.js    # WhatsApp Web bağlantısı, grup bulma, mesaj çekme
│   └── annotate.js    # sharp ile görüntü üzerine yazı basma
└── output/            # üretilen görseller + ozet.csv (git'e dahil edilmez)
```

## Güvenlik

- `.wwebjs_auth/` klasörü WhatsApp oturumunu içerir — **kimseyle paylaşma,
  git'e ekleme** (`.gitignore` ile hariç tutulmuştur).
- Bot yalnızca **okur** ve yerel diske kaydeder; gruba hiçbir şey göndermez.
