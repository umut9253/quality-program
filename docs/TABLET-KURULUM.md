# Tablet Kurulumu (Huawei 12" — sürüm 0.2)

Tablet, bu bilgisayardaki ana veritabanına (`data/kalite.db`, SQLite) **şifreli (HTTPS)**
bağlantıyla erişir. Herkes **kendi kullanıcı adı ve şifresiyle** giriş yapar; rolüne göre
kayıtları görür ya da düzenler. Her değişiklik "kim, ne zaman, ne değiştirdi" olarak kaydedilir.

## Roller

| Rol | Görür | Ekler / düzenler / siler | Kullanıcı yönetimi, değişiklik kaydı |
|---|---|---|---|
| Okuyucu | ✓ | — | — |
| Düzenleyici | ✓ | ✓ | — |
| Yönetici | ✓ | ✓ | ✓ (yalnız masaüstü) |

**Hatalı giriş:** ilk 3 hata serbest; 4. hatada 1 dk, sonra 5, 15, 60 dk kilit; bir sonraki
hatada hesap kalıcı kilitlenir ve yalnız yönetici açar (Kullanıcılar > Kilidi aç). İstisna:
kilidi açabilecek başka yönetici yoksa yönetici kalıcı kilitlenmez, her hatada 60 dk bekler.
Yönetici yine de giremiyorsa (şifre unutuldu vb.) bu bilgisayarda **`Yonetici Kurtarma.bat`**
çalıştırılır: kilidi açar, istenirse şifreyi sıfırlar (ağdan kullanılamaz). Tabletten
gelen girişlerde aynı kural cihaza (IP) da uygulanır (en fazla 60 dk), böylece farklı
kullanıcı adları denenerek kilit atlatılamaz.

## 1. Bilgisayar (bir kez)

1. Masaüstü programı açın. İlk açılışta **yönetici hesabı** oluşturulur (şifre en az 8
   karakter). Veritabanı yeni sürüme yükseltilir; önce `yedek/kalite_SEMA1_YEDEK_*.db` alınır.
2. Yönetim > **Kullanıcılar** sayfasından tableti kullanacak kişileri ekleyin (rol seçerek).
3. Wi-Fi ağını **Özel** yapın: Ayarlar > Ağ ve İnternet > Wi-Fi > *ağ adı* > Ağ profili türü: Özel.
4. PowerShell'i **Yönetici olarak çalıştır** ile açıp:
   `powershell -ExecutionPolicy Bypass -File "D:\PROGRAMLARIM\QUALITY PROGRAM\tools\tablet_guvenlik_duvari.ps1"`

## 2. Sunucuyu başlatma (her kullanımda)

`QUALITY PROGRAM\Tablet Sunucusu.bat` dosyasına çift tıklayın:

```
Tablette sunucu adresi : https://192.168.1.23:8765
Sertifika parmak izi   : ca111efb2932e64e…e862c1053bec9e26
```

İlk çalıştırmada sunucu sertifikası `data/tls/` altında üretilir (Git ile gelen OpenSSL).
Pencere açık kaldığı sürece tablet bağlanabilir.

## 3. Tablete kurulum (bir kez; sertifika değişirse tekrar)

1. APK'yı tablete aktarın: `tablet\android\cikti\KaliteYS.apk` dosyasını USB kablosuyla kopyalayın
   (sunucu artık HTTPS olduğundan tarayıcıdan indirme sertifika uyarısı verir; kablo önerilir).
2. Dosyaya dokunup kurun ("bilinmeyen kaynaklar" iznini verin). Eski 0.1 sürümü varsa üzerine kurulur.
3. **Kalite YS**'yi açın > sunucu adresini `https://…` olarak girin > **Kaydet ve bağlan**.
4. Giriş ekranında kendi kullanıcı adınız ve şifrenizle girin.

**Sertifika sabitleme:** APK yalnızca bu bilgisayarın sertifikasına güvenir (parmak izi APK'ya
derlemede gömülür). `data/tls/` silinir ya da sertifika yenilenirse `python tools/apk_derle.py`
ile APK yeniden derlenip tablete kurulmalıdır; aksi halde tablet "sertifika doğrulanamadı" der.
Bu, ağdaki birinin araya girip kendini sunucu gibi göstermesini engeller.

## HarmonyOS sürümü

APK yalnızca Android uyumlu HarmonyOS'ta kurulur (2/3/4.x). **HarmonyOS NEXT (5.x)** APK
çalıştırmaz; o durumda tabletin tarayıcısından `https://192.168.1.23:8765` açılır (tarayıcı
kendinden imzalı sertifika için bir kez uyarı gösterir; parmak izini yukarıdakiyle karşılaştırın).

## Sorun giderme

| Belirti | Neden / çözüm |
|---|---|
| "Sunucuya bağlanılamıyor" | Sunucu penceresi kapalı, tablet başka ağda ya da 1. bölüm yapılmadı |
| "Sertifika doğrulanamadı" | Sertifika yenilendi → APK'yı yeniden derleyip kurun |
| "Kullanıcı adı ya da şifre hatalı" | Yazımı kontrol edin; 3 hatadan sonra kilit başlar |
| "Hesap kilitlendi; yalnız yönetici açabilir" | Yönetici: Kullanıcılar > Kilidi aç; yönetici giremiyorsa bu bilgisayarda `Yonetici Kurtarma.bat` |
| "Kayıt siz düzenlerken başka cihazda değiştirildi" | Liste yenilenir; değişikliği güncel kayıt üzerinde tekrar yapın |
| "Oturum süresi doldu" | Oturum 12 saat geçerli; yeniden giriş yapın |
| Masaüstünde "Ekran kilitlendi" | 5 dk işlem yapılmadı; kendi şifrenizi girin (açık düzenleme penceresi yerinde durur). "Programı kapat" açık pencereleri kaydetmeden kapatır |

**Bilgisayardan ayrılırken Windows oturumunu da kilitleyin (Win+L):** program kendi ekranını
kilitlese de, açık Windows oturumunda veritabanı dosyasına ve kurtarma aracına erişilebilir.

## Geliştirici notları

- Kimlik: `app/kimlik.py` (scrypt şifre özeti, kilit, oturum jetonu — yalnız özeti saklanır).
- Sunucu: `app/sunucu.py` — `POST /api/giris` → jeton; diğer istekler `Authorization: Bearer`.
  Yazma: `POST /api/{bölüm}`, `PUT/DELETE /api/{bölüm}/{id}` (Düzenleyici+; `surum` ile
  iyimser kilit, eskiyse 409). Güvenlik başlıkları (CSP, nosniff, frame-ancestors), gövde ≤ 1 MB.
- Değişiklik kaydı: `degisiklikler` tablosu (masaüstü ve tablet), giriş/güvenlik olayları
  `guvenlik` tablosu; ikisi de yöneticinin **Değişiklik Kaydı** sayfasında.
- APK: `python tools/apk_derle.py` (Gradle'sız). İmza anahtarı `%USERPROFILE%\.android\kalite-tablet.jks`
  — **yedekleyin**. Sertifika ve özel anahtar `data/tls/` (git dışı) — yedekleyin; kaybolursa
  yeni sertifika üretilir ve APK yeniden kurulur.
- Eski `data/tablet_anahtar.txt` artık kullanılmaz (0.1 ortak anahtarı); silinebilir.
