# WhatsApp Hat/Baca Aralığı Botu

Bir WhatsApp grubundaki **fotoğrafları geçmişe dönük tarar**, her fotoğrafın
altına yazılan **hat/baca aralığı bilgisini (caption) resmin üzerine okunaklı
bir şekilde basar** ve bir klasöre kaydeder.

Belirttiğin tarihten **bugüne** kadar olan mesajlar taranır.

> Örnek çıktı: fotoğrafın altına yarı saydam bir bant üzerine, kalın beyaz
> (siyah kenarlıklı) ve Türkçe karakter destekli olarak bilgi metni basılır.

---

## Nasıl Çalışır?

- Geçmiş grup mesajlarını okumak için telefonunu **WhatsApp Web** üzerinden
  bağlar (`whatsapp-web.js`). İlk çalıştırmada bir **QR kod** okutulur; oturum
  `.wwebjs_auth/` altında saklandığından sonraki çalıştırmalarda tekrar
  istenmez.
- Her fotoğraf için bilgi metni önceliği:
  1. Fotoğrafın kendi açıklaması (caption),
  2. Yoksa, aynı kişiden **90 saniye** içinde gönderilmiş en yakın metin mesajı.
- Metni, resmin alt kısmına yarı saydam bant üzerine kalın beyaz yazıyla
  (siyah kenarlıklı, Türkçe karakter destekli) basar; uzun metinler otomatik
  satırlara bölünür.

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
# 1 Haziran 2026'dan bugüne, "Saha Ekibi" grubunu tara
node src/index.js --group "Saha Ekibi" --since 2026-06-01
```

Sonuçlar varsayılan olarak `./output/` klasörüne
`YYYY-MM-DD_HH-MM-SS_gonderen.jpg` biçiminde kaydedilir.

### Argümanlar

| Argüman | Zorunlu | Açıklama |
|---|---|---|
| `--group` | ✅ | Grup adı (kısmi eşleşme yeterli, büyük/küçük harf duyarsız) |
| `--since` | ✅ | Başlangıç tarihi, `YYYY-MM-DD`. Bu tarihten bugüne taranır |
| `--out` | ➖ | Çıktı klasörü (varsayılan `./output`) |
| `--limit` | ➖ | Taranacak en fazla mesaj sayısı (varsayılan `5000`) |
| `--list-groups` | ➖ | Sadece grupları listeler |
| `--help`, `-h` | ➖ | Yardım |

> Çok eski tarihli mesajları tarıyorsan `--limit` değerini artır (örn.
> `--limit 15000`). WhatsApp Web eski mesajları kademeli yüklediği için ilk
> çalıştırma biraz uzun sürebilir.

---

## Dosya Yapısı

```
whatsapp-bot/
├── package.json
├── src/
│   ├── index.js       # CLI + ana akış (tara → bilgi bul → bas → kaydet)
│   ├── whatsapp.js    # WhatsApp Web bağlantısı, grup bulma, mesaj çekme
│   └── annotate.js    # sharp ile görüntü üzerine yazı basma
└── output/            # üretilen görseller (git'e dahil edilmez)
```

## Güvenlik

- `.wwebjs_auth/` klasörü WhatsApp oturumunu içerir — **kimseyle paylaşma,
  git'e ekleme** (`.gitignore` ile hariç tutulmuştur).
- Bot yalnızca **okur** ve yerel diske kaydeder; gruba hiçbir şey göndermez.
