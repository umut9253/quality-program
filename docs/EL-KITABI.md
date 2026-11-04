# Geliştirici El Kitabı: Kalite Yönetim Sistemi (QUALITY PROGRAM)

Bu belge programın kodunu ilk kez okuyacak biri içindir. Amaç iki gün içinde şu sorulara
cevap verebilmek: "Program ne yapar, veri nerede durur, bir değişikliği nereye yaparım, neyi
asla yapmam?" Modül modül liste için `docs/MIMARI.md`, değişikliklerin geçmişi için
`docs/DEGISIKLIK-GUNLUGU.md` okunur. Bu belge onların yerine geçmez, okuma sırasını verir.

Kodda adlar Türkçedir (`kayit_ekle`, `yeniden_yukle`, `surum`). Sona eklenen §11 sözlüğü sık
geçen kelimeleri açıklar.

---

## 1. Program ne yapar?

Spiral kaynaklı çelik boru üreten bir fabrikanın kalite birimi için masaüstü uygulaması
(Windows, Python 3.13, PyQt6). Beş iş yapar:

| İş | Ekranda | Kodda |
|---|---|---|
| Kaynak prosedürleri: WPS ve PQR kayıtları, paso parametreleri, kaynak şematiği çizimi | WPS, PQR sekmeleri | `pages.py`, `dialogs.py`, `diagram.py` |
| Dış kaynaklı standartların güncelliği: ASME, API, EN ISO vb. için en son sürüm Gemini + Google aramayla bulunur | Standartlar sekmesi | `standards_check.py` |
| Sertifika takibi: geçerlilik tarihi, "yakında dolacak / doldu" uyarısı | Sertifikalar sekmesi | `pages.py`, `database.cert_status` |
| ITP (Inspection and Test Plan, İngilizce) ve Kalite Planı (KP, Türkçe) üretimi: sipariş kalemlerinden API 5L ve ISO 21809 kabul kriterleri hesaplanır, Excel'e yazılır, siparişler revizyonlu saklanır | ITP sekmesi | `app/itp/`, `itp_page.py`, `itp_sekme.py` |
| Tablet erişimi: aynı veriyi yerel ağda tabletten okuma ve yazma | tarayıcı / APK | `sunucu.py`, `tablet/web/`, `tablet/android/` |

Kullanıcı ve yetki sistemi her şeyin üstündedir: Yönetici, Düzenleyici, Okuyucu. Her kayıt
değişikliği kim, ne zaman, önce ve sonra bilgisiyle kaydedilir.

## 2. Çalıştırma ve test

```bash
pip install PyQt6 requests openpyxl
python main.py                                   # masaüstü (gerçek veriyle çalışır!)
python -m pytest tests -q -p no:cacheprovider    # bütün testler, yaklaşık 2 dakika
```

- Testler her zaman `tests` yolu verilerek çalıştırılır. Kök klasörde `arsiv/` altında eski
  deneme betikleri var, pytest onları toplamamalı.
- Testler gerçek veriye dokunmaz. Her test kendi geçici klasöründe veritabanı kurar.
  `tests/conftest.py` buna bir güvenlik ağı ekler: bir test gerçek `data/` ya da `yedek/`
  klasörüne SQLite bağlantısı açmaya kalkarsa bağlantı kurulmadan `GercekVeriHatasi` verir.
- `python main.py` ve `Tablet Sunucusu.bat` **gerçek veriyi** açar. Deneme için önce
  `data/` klasörünün kopyasını alın ya da aşağıdaki güvenli kalıbı kullanın.

**Güvenli deneme kalıbı** (programı gerçek veri olmadan açmak için):

```python
import os, sys, tempfile
sys.path.insert(0, r"D:\PROGRAMLARIM\QUALITY PROGRAM")
from app import database
g = tempfile.mkdtemp(); os.makedirs(g + r"\data")
database.DATA_DIR, database.DATA_FILE, database.BACKUP_DIR = g + r"\data", g + r"\data\data.json", g + r"\yedek"
db = database.Database()     # geçici klasörde, örnek veriyle kurulur
```

## 3. Klasör haritası

```
QUALITY PROGRAM/
├── main.py                 giriş noktası: veritabanını açar, giriş penceresi, ana pencere
├── app/                    uygulama
│   ├── database.py         veri katmanı (SQLite): HER YAZMA BURADAN GEÇER
│   ├── kimlik.py           kullanıcı, şifre, rol, kilit, oturum, güvenlik kaydı (Qt'siz)
│   ├── firma.py            firma adı + logo (ayarlar tablosu; Qt'siz)
│   ├── dil.py, dil_en.py   arayüz dili (_ / N_ / deger) ve İngilizce katalog (Qt'siz)
│   ├── main_window.py      ana pencere, yan menü, sekme geçişi, 3 sn yenileme
│   ├── pages.py            Ana sayfa, WPS, PQR, Standart, Sertifika sekmeleri
│   ├── dialogs.py          ekle / düzenle / detay pencereleri
│   ├── widgets.py, theme.py, config.py   ortak arayüz parçaları, iki tema, sabitler
│   ├── itp_page.py         ITP düzenleyicisi (başlık, kalemler, önizleme, Excel)
│   ├── itp_sekme.py        ITP sipariş listesi (aç, kopyala, onay, yeni rev, sil)
│   ├── sartname_sekme.py, sartname_page.py   Şartnameler: liste + düzenleyici, madde/grup pencereleri
│   ├── itp/                ITP motoru, Qt'siz (bkz. §6)
│   ├── giris_penceresi.py  giriş, ilk kurulum (yönetici) ve şifre değiştirme pencereleri
│   ├── yonetim_sayfalari.py   yalnız yönetici: Kullanıcılar, Değişiklik kaydı, Firma Bilgileri
│   ├── standards_check.py  standart sürüm kontrolü (Gemini; haftalık otomatik + elle)
│   ├── exporter.py, diagram.py   liste Excel aktarımı, WPS birleşim diyagramı çizimi
│   ├── sunucu.py           tablet sunucusu (HTTPS, port 8765)
│   ├── ozet.py             ana sayfa özeti (masaüstü ve tablet ortak)
│   └── search_utils.py     Türkçe harf katlamalı arama
├── tests/                  pytest (her modülün test_*.py dosyası)
├── tools/                  yardımcı araçlar (APK derleme, yönetici kurtarma, örnek çıktı)
│   └── ice_aktarim/        eski data.json'a Excel içe aktarma betikleri (kalite.db varken çalışmaz)
├── tablet/
│   ├── web/                tablet web arayüzü (HTML/CSS/JS, bağımlılıksız)
│   └── android/            tablet için WebView kabuğu (APK)
├── data/                   GERÇEK VERİ: kalite.db, TLS anahtarı, API anahtarı (git'e girmez)
├── yedek/                  otomatik yedekler (git'e girmez)
├── docs/                   el kitabı, mimari, kurulum, açık sorular, değişiklik günlüğü
│   ├── denetim/            Antigravity denetim talepleri ve raporları
│   ├── kaynak/             kaynak Excel/PDF listeleri (standart, sertifika)
│   ├── ornek-cikti/        örnek ITP/KP çıktıları
│   └── superpowers/        tasarım (specs) ve uygulama planları (plans)
└── arsiv/                  eski deneme betikleri ve .bak kopyalar (programın parçası değil)
```

## 3.1 Arayüz metni eklerken (TR/EN)

Program Türkçe ve İngilizce çalışır (`app/dil.py`). Kullanıcıya görünen her yeni metin:

- Fonksiyon içinde `_("Kaydet")`; değişkenli metin `_("{n} kayıt").format(n=n)` (f-string
  değil: katalog anahtarı sabit olmalı).
- Modül / sınıf sabitinde `N_("Durum")`, kullanıldığı yerde `_(sabit)` (dil program
  çalışırken değişir; içe aktarmada dondurulmaz).
- Veritabanına yazılan seçmeli değerler ("Aktif", "Geçti"…) Türkçe kalır; ekranda
  `dil.deger(v)`; açılır listede `addItem(dil.deger(v), v)` ve okuma `currentData()`.
- İngilizce karşılığı `app/dil_en.py`'ye eklenir. Unutulursa `tests/test_dil_katalog.py`
  kırmızı olur; İngilizce kip duman testi ekranda kalan Türkçe metni de yakalar.
- `_` bir fonksiyon/çağrı adıdır: "kullanılmayan değişken" için `__` kullanın (`_`
  ataması aynı fonksiyondaki `_()` çağrısını bozar).

## 4. Önce okunacak beş dosya

Bu sırayla okumak programın iskeletini verir:

1. `main.py` (80 satır): açılış sırası. `Database()` → `oturum_ac` → `MainWindow`.
   Veritabanı hatası programı kapatmaz, mesaj gösterir.
2. `app/database.py` §5'te anlatılan kavramlarla birlikte. En önemli dosya.
3. `app/kimlik.py` yalnız üst kısmı: roller, `yetkili(rol, gereken)`, `giris`, `_olay`.
4. `app/itp/olustur.py` ve `app/itp/hesap.py`: ITP üretiminin kalbi.
5. `app/itp/kayit.py`: kayıt kuralları "Qt'siz kural dosyası" kalıbıyla yazılır. Yeni
   özellikler (`sartname.py`) aynı kalıbı izler.

## 5. Veri katmanı (`app/database.py`)

### 5.1 Dosya ve tablolar

- Veri `data/kalite.db` dosyasında, SQLite, WAL kipinde. 2026-10-30'dan önce
  `data/data.json` kullanılıyordu. İlk açılışta JSON doğrulanarak veritabanına taşındı;
  `data/kalite.db.tasindi` işareti taşımanın yapıldığını gösterir. `data.json` artık okunmaz.
- **Bölümler** (`SECTIONS`): `pqr`, `wps`, `std`, `cert`, `itp`, `sartname`. Her bölüm bir
  tablodur. Sütunlar: `id`, `sira`, `surum`, `veri` (kaydın tam JSON'u) ve listeleme için
  `veri`'den türetilmiş sütunlar (`TURETILMIS`). Yani **kaydın kendisi JSON'dur**: yeni bir
  alan eklemek şema değişikliği gerektirmez.
- Diğer tablolar: `degisiklikler` (her yazmanın kaydı), `kullanicilar`, `oturumlar`,
  `guvenlik` (giriş ve yetki olayları), `cihaz_kilit`, `cihaz_hata` (tablet giriş kilidi),
  `ayarlar` (firma adı ve logo; `app/firma.py`).
- **Şema sürümü** `PRAGMA user_version` içinde, şu an `SEMA_SURUMU = 7`. Eski sürümlü dosya
  açılınca `_yukselt` önce `yedek/kalite_SEMA<n>_YEDEK_<zaman>.db` yedeğini alır, sonra
  yükseltmeyi tek işlemde yapar: ya hepsi olur ya hiçbiri.
- Her açılışta günlük yedek: `yedek/auto_kalite_<tarih>.db`, son 14 tanesi tutulur. Bozuk
  dosya ezilmez; `kalite_BOZUK_*.db` olarak kopyalanır ve `VeritabaniHatasi` verilir.

### 5.2 `Database` sınıfı: bellekte liste, diskte gerçek

- `Database()` açılınca bütün bölümleri belleğe liste olarak yükler: `db.get_wps()` bir
  `list[dict]` döndürür. Sayfalar bu listeyi gösterir.
- Yazma API'si bölüm başına aynıdır: `add_<b>(r)`, `update_<b>(i, r, anahtar=...)`,
  `delete_<b>(i, anahtar=...)`. Sıra hep aynıdır: **önce veritabanı, sonra bellek.** DB
  yazması başarısız olursa bellekteki liste değişmez.
- Her yazma, kayıt ve değişiklik kaydı satırıyla birlikte **tek SQLite işleminde** yapılır.
  Modül düzeyindeki iç fonksiyonlar `_ekle_ic`, `_guncelle_ic`, `_sil_ic`; birden fazla kaydı
  birlikte yazanlar (`rev_yaz`, `kilitli_sil`, `kilitli_duzelt_yaz`) `BEGIN IMMEDIATE` ile
  hepsini tek işlemde yapar.

### 5.3 Üç kavram: anahtar, sürüm, yenileme

Masaüstü ve tablet aynı dosyaya yazar. Bunun güvenli olması üç kavrama dayanır:

1. **Sürüm (`surum`)**: her kayıt her güncellemede 1 artar. Güncelleme ve silme "bu kaydı
   şu sürümdeyken gördüm" bilgisiyle yapılır. Arada başkası değiştirdiyse yazma reddedilir
   (`CakismaHatasi`) ve liste tazelenir. Buna iyimser kilit denir.
2. **Anahtar**: `db.anahtar(bolum, i)` kaydın kalıcı kimliğini ve sürümünü verir:
   `(id, surum)`. **Kural:** düzenleme ya da silme penceresi açılmadan önce anahtar alınır
   ve yazmaya verilir. Pencere açıkken liste 3 saniyede bir yenilenir, satır numarası (`i`)
   kayabilir; anahtar kaymaz.
3. **Yenileme**: `main_window` 3 saniyede bir `db.disaridan_degisti()` sorar. Tablet yazdıysa
   `yeniden_yukle()` listeleri tazeler. Liste nesneleri korunur, sayfalar aynı listeye
   bakmaya devam eder.

### 5.4 Yetki nerede denetlenir?

- Masaüstünde: `Database._yazma_oncesi()`. Okuyucu yazamaz (`YetkiHatasi`). Kilitli kayıt
  kuralları ilgili kural dosyasında (`itp/kayit.py`, `itp/sartname.py`) ve `Database`
  metotlarında ikinci kez denetlenir.
- Tablette: `app/sunucu.py` her istekte oturum jetonunu ve rolü denetler. Sunucu modül
  düzeyindeki `database.kayit_ekle/guncelle/sil` fonksiyonlarını çağırır. **Bu fonksiyonlar
  rol denetlemez**; denetim sunucu ucundadır. Sunucu yalnız `wps`, `pqr`, `std`, `cert`
  bölümlerine yazar (`BOLUMLER`); ITP ve şartname tabletten görünmez.
- Değişiklik kaydında `kaynak` sütunu yazmanın nereden geldiğini gösterir: `masaustu` ya da
  `tablet`.

## 6. ITP / Kalite Planı motoru (`app/itp/`)

Bütün klasör Qt'siz, saf Python. Bu yüzden tamamı arayüz açmadan test edilir; ileride tablet
de aynı kodu kullanacak.

### 6.1 Hat: girdi → Excel

```
Sipariş başlığı + kalemler (çap, et, kalite, PSL, kaplama...)
   │
   ▼  hesap.boru_hesapla(BoruGirdisi) → BoruSonucu       her kalem için API 5L kabul kriterleri
   │       veri: veri/api5l_47.py (API 5L 47. baskı tabloları)
   │             veri/iso21809.py (kaplama kriterleri; kaplama.py okur)
   ▼  olustur.olustur(sablon, baslik, kalemler) → Dokuman
   │       şablon: sablon/itp_en.py | kp_ciplak.py | kp_kaplama.py
   │       metindeki {yer_tutucu}'lar ve {"blok": ...}'lar yer_tutucu.py ile doldurulur
   ▼  excel.excel_yaz(dokuman, yol)                     ITP (EN, 2 sayfa) ya da KP (TR) .xlsx
```

- **Veri modülleri** (`veri/`) standart tablolarının tek kaynağıdır. Bu dosyalara dokunan
  her değişiklik iki kişi (ya da iki ajan) tarafından standardın PDF metnine karşı
  doğrulanır. Kapsam bugün yalnız SAWH borudur.
- **Şablonlar** Python veri dosyalarıdır: `BOLUMLER` listesi, her bölümde `satirlar`, her
  satırda aktivite, karakteristik, kabul, frekans, kayıt, denetim alanları. Şablon yalnız
  metin ve yer tutucu taşır; **sayı yazmaz**. Sayılar `hesap.py`'den gelir.
- **Yer tutucular**: `"{et_formul}"` gibi metin içi adlar kalem başına doldurulur ve
  kalemler arasında gruplanır ("Items 1-4: <formül>"). `{"blok": "ebat"}` kalem tablosu
  basar; `{"elle": ...}` Excel'de "ELLE GİRİLECEK" olarak çıkar. Tanımsız bir ad sessizce
  geçmez, `SablonHatasi` verir.
- **Kabul kriteri hücresi (2026-11-03):** Excel'de kabul alanı 8 alt sütundur
  (`kabul_izgara.py`). Metin satırları alanın tamamına, kalem tabloları ("Nom. | Min. | Maks.",
  kimya "Element | kalite") gerçek alt hücrelere yazılır; Word ITP'lerdeki iç tabloların karşılığı.
  Çekme satırı şablonda `"kalite_basina": True` ile kalite başına satırlara açılır; uzama (Af)
  `hesap.uzama_af` ile et kalınlığı başına hesaplanır (numune genişliği 40 mm, ayar
  `api5l_47.PARAMETRELER`). Frekans hücresi yalnız kısa sıklık taşır; ek şartlar ve atıf kabul
  hücresinin altındadır.
- `hesap.excel_round` Excel'in ROUND davranışını taklit eder. Eski Excel çıktılarıyla birebir
  aynı sayılar bu yüzden çıkar; Python'un `round`'u kullanılmaz.

### 6.2 Sipariş kaydı (Plan 5a): `kayit.py`, `goruntu.py`

- Her sipariş revizyonu `itp` bölümünde ayrı bir kayıttır. Durumlar: `taslak` → müşteri
  onayıyla `onayli` (kilitli) ya da "Yeni rev"le `revize` (kilitli).
- Kilitli revizyonun Excel'i yeniden hesaplanmaz. Kilitlenirken dokümanın JSON anlık
  görüntüsü (`goruntu.yaz`) kayda yazılır; sonradan hep o görüntüden üretilir. Böylece
  standart verisi düzeltilse bile müşteriye gitmiş doküman değişmez.
- Kilitli kaydı yalnız Yönetici, gerekçe yazarak silebilir; bu bir güvenlik olayıdır.

### 6.3 Şartname kütüphanesi (Plan 5b): `sartname.py`, `kontrol.py`

- Müşteri ya da idare şartnamelerinin (KURUM_A, KURUM_B, KURUM_C) standarttan farklı istediği
  maddeler. Her şartname revizyonu `sartname` bölümünde bir kayıttır: `taslak` →
  "Yürürlüğe al" ile `yururlukte` (kilitli); taslaktan yeni rev açılırsa taslak `revize` olur.
- Her madde bir **kontrol anahtarına** bağlanır (`kontrol.py` içindeki `KONTROLLER`, örn.
  `hidrostatik`, `et_kalinligi`). Şablon satırları bu anahtarlara `SATIRLAR` ile eşlenir.
  Böylece madde bir kez yazılır, hangi doküman (ITP / KP) kullanılırsa onun satırına
  uygulanır. Farklı işler (ör. gösterge kalibrasyonu ile test basıncı) ayrı anahtar alır.
- Arayüz (5b-2a): "Şartnameler" sayfası (`sartname_sekme.py` liste, `sartname_page.py`
  düzenleyici + `MaddeDialog` / `GrupDialog`). Madde penceresi tam doğrular
  (`madde_dogrula(tam=True)`). Kilitli kaydı Yönetici "Gerekçeyle düzelt" ile düzeltir.
- Başlangıç taslakları (5b-2b): `tools/sartname_baslangic.py`, boş kütüphaneye KURUM_A, KURUM_C, KURUM_B
  Genel ve KURUM_B Özel Teknik taslaklarını ekler (içerik `tools/sartname_baslangic/*.json`; kütüphane
  doluysa dokunmaz). Gerçek veride kullanıcı bir kez, program ve tablet sunucusu KAPALIYKEN
  çalıştırır (komut "evet" onayı ister). Belirsiz maddeler
  `docs/ACIK-SORULAR.md` V-5b-*.
- Maddelerin dokümana uygulanması (5c) henüz yok. Tasarım:
  `docs/superpowers/specs/2026-11-01-itp-plan5b-sartname-kutuphanesi-design.md`.

## 7. Arayüz

- `main_window.py` çerçevesiz pencere, yan menü ve `QStackedWidget` kurar. **Sekme
  indeksleri sabittir**: Ana=0, WPS=1, PQR=2, STD=3, CERT=4, ITP=5, Şartnameler=6; yalnız
  yöneticiye Kullanıcılar=7, Değişiklik Kaydı=8, Firma Bilgileri=9. Menüde PQR, WPS'ten önce
  görünür ama indeksler bu sırayla kalır. Ana sayfa kartları bu indekslerle gezinir.
  Kısayollar menünün görsel sırasıyla Ctrl+1…9 (onuncu öğenin kısayolu yok).
- Görünüm: `theme.py` iki palet (koyu / açık) ve QSS üretir. Renk ya da stil hücre
  widget'larına `setStyleSheet` ile verilmez; tema QSS'inde `objectName` ile verilir.
  Yüzlerce satırlı tabloda hücre başına stil ayrıştırmak 100 ms'yi geçiyordu.
- PyQt6'da QSS animasyonu çalışmaz. Animasyon gerekiyorsa `QPropertyAnimation` kullanılır.
  Çerçevesiz pencerede kalıcı `QGraphicsEffect` kullanılmaz (Windows'ta hata yağmuru yapar).
- Arama kutularında `.lower()` kullanılmaz; `search_utils.matches_query` ya da `tr_fold`
  kullanılır. Türkçe "I/ı/İ/i" ancak böyle doğru eşleşir.

## 8. Değişiklik yaparken: tarifler

**Bir kayda yeni alan eklemek (ör. sertifikaya "veren kurum"):**
`dialogs.py` içindeki pencereye alanı ekleyin, `config.py`'de sütun ya da etiket
gerekiyorsa ekleyin. Veri JSON olduğu için veritabanında değişiklik gerekmez. Alana göre
listelemek ya da sorgu yapmak gerekiyorsa `TURETILMIS`'e eklemek şema değişikliğidir;
`SEMA_SURUMU` artırılır ve `_yukselt` güncellenir.

**Yeni bir bölüm (tablo) eklemek:** `SECTIONS`, `TURETILMIS`, `SAMPLE_DATA`'ya ekleyin,
`SEMA_SURUMU`'nu artırın, `Database`'e `get/add/update/delete_<b>` yazın. Örnek olarak
şema 5'te eklenen `sartname`'e bakın (`git show 91c40e8`). Eski yedeklerin okunduğunu
ve yükseltmenin önce yedek aldığını test edin (`tests/test_veritabani.py`).

**Kilit, revizyon ya da onay kuralı eklemek:** kuralı Qt'siz kural dosyasına yazın
(`itp/kayit.py` ya da `itp/sartname.py`). Arayüz yalnız çağırır. `Database` metodu
kuralı yazmadan önce bir kez daha çağırır, çünkü tablet arayüzü atlayabilir.

**Bir şablon satırını değiştirmek:** `itp/sablon/*.py` içinde metni değiştirin. Satırın
karakteristik metni değiştiyse `itp/kontrol.py` içindeki `SATIRLAR` eşlemesini de
güncelleyin; `tests/test_itp_kontrol.py` eksik ya da eskimiş eşlemeyi yakalar. Örnek
Excel çıktıları `python tools/ornek_cikti.py` ile yeniden üretilir.

**Standart verisini değiştirmek (`itp/veri/`):** yalnız standardın kendi metnine dayanarak.
Değişiklik ikinci bir kişiye PDF madde metnine karşı doğrulatılır.

## 9. Değişmez kurallar

1. **Gerçek veri kutsaldır.** `data/` ve `yedek/` altında elle dosya oluşturulmaz,
   değiştirilmez ya da silinmez. `data/tls/sunucu.key`, `data/api_key.txt`,
   `data/tablet_anahtar.txt` gizlidir; okunmaz, paylaşılmaz, git'e girmez.
2. **Önce test.** Her değişiklikte önce hatayı gösteren test yazılır (kırmızı), sonra kod
   (yeşil). Bütün takım geçmeden iş bitmiş sayılmaz.
3. **Testlerde `monkeypatch.undo()` kullanılmaz.** Fikstürün veritabanı yolu yamalarını da
   geri alır ve test gerçek veriyi açar. 2026-11-01'de bu oldu: veri kaybı yok, ama gerçek
   veritabanı test sırasında yükseltildi. Tek bir yamayı geri almak için eski değer saklanır
   ve `monkeypatch.setattr` ile geri konur.
4. **Her davranış değişikliği** `docs/DEGISIKLIK-GUNLUGU.md`'ye yazılır: en üste, tarihli,
   ne yapıldı, etkilenen dosyalar, test sonucu.
5. **Sessiz hata yok.** Başarısızlık ya anlamlı bir mesajla kullanıcıya gösterilir ya da
   görünür biçimde ele alınır. Örnek veriyle sessizce devam etmek yasaktır.
6. **API anahtarları koda yazılmaz.** Gemini anahtarı `GEMINI_API_KEY` ortam değişkeninden
   ya da `data/api_key.txt` dosyasından okunur ve HTTP başlığıyla (`x-goog-api-key`)
   gönderilir, URL'de gönderilmez.
7. **Türkçe arama** her yerde `tr_fold` ya da `matches_query` ile yapılır.

## 10. Süreç: tasarım → plan → uygulama → denetim

Büyük işler dört adımda yürür; belgeleri `docs/` altında:

| Adım | Belge |
|---|---|
| Kararlar ve tasarım (kullanıcıyla) | `docs/superpowers/specs/<tarih>-<konu>-design.md` |
| Uygulama planı (görev görev, test kodlarıyla) | `docs/superpowers/plans/<tarih>-<konu>.md` |
| Uygulama ve iç doğrulama (ayrı bir inceleyici) | commit'ler + `DEGISIKLIK-GUNLUGU.md` |
| Bağımsız denetim | `docs/denetim/DENETIM-TALEBI-*.md` → `docs/denetim/DENETIM-RAPORU-*.md` |

Yol haritası: `docs/superpowers/plans/2026-10-23-itp-generator-yol-haritasi.md`. Kullanıcıdan
cevap bekleyen sorular: `docs/ACIK-SORULAR.md`.

## 11. Sözlük

| Kodda | Anlamı |
|---|---|
| `bolum` (`b`) | veri bölümü / tablo: `wps`, `pqr`, `std`, `cert`, `itp`, `sartname` |
| `kayit`, `veri` | bir satırın JSON içeriği (dict) |
| `surum` | kaydın sürüm sayacı (iyimser kilit) |
| `anahtar` | `(id, surum)`: kaydın kalıcı kimliği |
| `degisiklikler` | değişiklik kaydı tablosu (kim, kaynak, önce, sonra) |
| `guvenlik` | giriş ve yetki olayları tablosu |
| `yeniden_yukle` | listeleri veritabanından tazelemek |
| `tek işlem` | tek SQLite transaction: ya hepsi yazılır ya hiçbiri |
| `kalem` | sipariş satırı (bir boru ebadı) |
| `sablon` | ITP / KP doküman şablonu (`itp_en`, `kp_ciplak`, `kp_kaplama`) |
| `yer_tutucu`, `blok` | şablon metnindeki hesapla doldurulan alanlar |
| `goruntu` | kilitli dokümanın JSON anlık görüntüsü |
| `taslak`, `onayli`, `revize`, `yururlukte` | kayıt durumları; taslak dışındakiler kilitli |
| `rev`, `rev_sira` | gösterilen revizyon adı ("0", "A") ve zincirdeki sıra numarası |
| `aile` | aynı dokümanın / şartnamenin revizyonları (şartnamede kurum + ad) |
| `kontrol` (anahtar) | şartname maddesinin hedefi olan ortak muayene adı |
| `tr_fold` | Türkçe harf katlama (İ/I/ı/i eşdeğer) |
| `Yonetici`, `Duzenleyici`, `Okuyucu` | roller |

## 12. Bilinen eksikler ve eskimiş yerler

- `docs/README.md` kısmen eskimiş: Gemini anahtarının `standards_check.py` içinde olduğunu ve
  sekme sırasında ITP'nin olmadığını söylüyor. Doğrusu bu belgede ve `CLAUDE.md`'de. Yedekler de
  artık `.zip` değil, `.db`.
- Arayüz testleri sınırlıdır; görsel doğrulama büyük ölçüde elle yapılıyor.
- Şartname maddelerinin dokümana uygulanması (5c) ve tablette
  ITP (5d) henüz yazılmadı.
