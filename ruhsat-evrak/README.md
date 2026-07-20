# Ruhsat Evrak Hazırlama Paneli

İnşaat (yapı) ruhsatı projelerinde istenen **taahhütname, sözleşme, davetname ve
dilekçe** belgelerini hızlıca hazırlayan tek dosyalık bir web uygulaması.
Kurulum gerekmez — `index.html` dosyasını çift tıklayıp tarayıcıda açman yeterli.

## Özellikler

- **Kontrol paneli:** Proje/parsel bilgileri ve projede yer alan tüm kişiler
  (mimar, inşaat/statik, elektrik, makine, jeoloji, harita mühendisi, müteahhit,
  şantiye şefi, yapı denetim, kalfa) tek ekrandan girilir.
- **Otomatik belge üretimi:** Girilen bilgilere göre aşağıdaki belgeler doldurulur:
  - Taahhütnameler: mimar, inşaat/statik, elektrik, makine, jeoloji, harita,
    şantiye şefi, müteahhit, kalfa
  - Sözleşmeler: Yapı Sahibi–Müteahhit, Şantiye Şefliği Hizmet Sözleşmesi
  - Davetnameler (her kişi için) ve Yapı Ruhsatı Başvuru Dilekçesi
- **Evrak Takip / Kontrol Listesi:** Excel çizelgesindeki tüm evraklar (Vize,
  Yapı Denetim, Müteahhit, Şantiye Şefi grupları) işaretlenebilir liste olarak
  gelir; grup ve genel **ilerleme çubuğu**, her maddeye **not**, ve uygulamanın
  üretebildiği belgeler için **"✍️ Üret"** kısayolu bulunur. Çizelge PDF olarak
  da yazdırılabilir.
- **PDF / Yazdır:** Her belge tek tek veya "Tümünü Yazdır" ile toplu olarak
  PDF'e aktarılır (tarayıcı yazdır penceresinde "PDF olarak kaydet").
- **Veri güvenliği:** Bilgiler yalnızca tarayıcıda (localStorage) saklanır,
  hiçbir yere gönderilmez. **Yedek Al / Yükle** ile JSON olarak taşınabilir.

## Kullanım

1. `index.html`'i tarayıcıda aç.
2. **Bilgi Girişi** sekmesinde alanları doldur (otomatik kaydedilir).
3. **Belgeler** sekmesinde belgeyi seç → önizle → **PDF / Yazdır**.

## Not

Üretilen belgeler **taslak** niteliğindedir; imzalatmadan önce bağlı bulunduğun
belediye/idarenin güncel form ve gereksinimleriyle karşılaştır. Boş bırakılan
alanlar belgede noktalı satır olarak çıkar (elle doldurulabilir).
