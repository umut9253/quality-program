# Mimari — Modül Yapısı

Uygulama tek bir giriş noktası (`main.py`) ve `app/` paketinden oluşur.
Tüm UI metinleri ve sabitler tek kaynaktan (`app/config.py`) beslenir.

## Akış

```
main.py
  └── app.main_window.MainWindow
         ├── app.database.Database        (veri katmanı, SQLite)
         ├── app.theme.STYLESHEET         (görünüm / QSS)
         └── app.pages.*                  (sekme sayfaları)
                ├── app.widgets.*         (paylaşılan UI yapı taşları)
                ├── app.dialogs.*         (ekle/düzenle/detay pencereleri)
                └── app.standards_check.* (Gemini + Google arama, arka plan iş parçacığı)
```

## Modüller

| Dosya | Sorumluluk |
|-------|------------|
| `main.py` | Giriş noktası. QApplication kurar, fontu (Segoe UI 10) ayarlar, `MainWindow`'u açar. |
| `app/__init__.py` | Paket meta verisi (`__app_name__`). |
| `app/config.py` | Sabitler: seçim listeleri, tablo sütunları (`COLS_*`), Türkçe etiketler, detay alanları. (Durum renkleri tema bağımlı olduğundan `theme.py`'dedir.) |
| `app/theme.py` | Çift tema sistemi: `_DARK`/`_LIGHT` paletleri, durum/aksan sözlükleri, `build_stylesheet()` (QSS üretimi), `set_theme/current/t/status/accent/badge_*` API. Tek tıkla koyu↔açık geçiş. |
| `app/database.py` | SQLite (`data/kalite.db`, WAL). `Database` sınıfı: bellek içi listeler + her yazma tek işlemde DB'ye (sıra indeksli API aynı: `update_wps(i, r)`). Tablo başına `id, sira, veri` (kaydın tam JSON'u) + `veri`'den türetilmiş sütunlar (`TURETILMIS`: no, durum, status, bitis…). İlk açılışta `data.json` → DB doğrulamalı taşıma (geçici dosya + os.replace). Günlük yedek `yedek/auto_kalite_*.db` (sqlite backup API, son 14); bozuk DB `kalite_BOZUK_*.db` olarak kopyalanır, `VeritabaniHatasi`. `tum_veri(yol)` salt okunur okuma (tablet sunucusu). `SAMPLE_DATA`, `cert_status()`. |
| `app/standards_check.py` | Gemini + Google Search ile standart sürüm sorgulama. `query_gemini`, `compare_std_status`, `fetch_latest_versions_bulk`, `CheckWorker(QThread)`. API anahtarı kodda tutulmaz: `GEMINI_API_KEY` ortam değişkeni veya `data/api_key.txt` (gizli dosya); istekte `x-goog-api-key` başlığı kullanılır. |
| `app/exporter.py` | Excel (.xlsx) dışa aktarma: `export_xlsx()` — biçimli başlık, zebra satırlar, otomatik sütun genişliği, filtre. openpyxl yoksa kullanıcıya kurulum mesajı. |
| `app/widgets.py` | Paylaşılan UI: `badge_item`, `ro_item`, `page_header`, `make_action_cell`, `stat_card`, `animate_count`, `attach_pulse`, `HoverCard`, `apply_col_widths`, `parse_range`, `ro_table`, `EditableTable`. |
| `app/dialogs.py` | `WPSDialog`, `PQRDialog`, `STDDialog`, `CertDialog`, `DetailDialog`. |
| `app/pages.py` | `HomePage`, `WPSPage`, `PQRPage`, `STDPage`, `CertPage`. |
| `app/main_window.py` | `MainWindow`: sekme düzeni, tema uygulaması, otomatik standart kontrol zamanlayıcıları. |
| `app/itp/aralik.py` | ITP: aralık eşleme (`alt/üst dahil` bayrakları) ve `tek_satir` (0 veya 2+ eşleşmede `EslesmeHatasi`). |
| `app/itp/veri/api5l_47.py` | ITP: API 5L 47 SAWH verisi (Table 2, 4–11, 14, 16, 18 No. 3–5, 22, 23, 26; 9.8.3.1, 9.14.1, Figure 9 + parametreler). Public depoda boş iskelet. |
| `app/itp/veri/iso21809.py` | ITP: ISO 21809-1/-2 kaplama kriterleri, Table 2 kalınlık, sınıflar (public depoda boş iskelet). |
| `app/itp/hesap.py` | ITP: boru kabul kriterleri (`boru_hesapla(BoruGirdisi) -> BoruSonucu`). Excel ROUND uyumlu `excel_round`; Pm yuvarlanmaz. Plan 2b: `charpy`, `mandrel` (Agb + çene açıklığı B), `lot`, `kutle_toleransi`; `BoruSonucu`'nda `charpy/mandrel/lot/kutle`. |
| `app/itp/kaplama.py` | ITP: `min_kalinlik(sinif, kalinlik_sinifi, pm)`, `kriterler(standart, sinif)`. |
| `app/itp/dokuman.py` | ITP: ortak doküman modeli (`Dokuman`, `Bolum`, `Satir`, `Kalem`, `Sartname`, `KalemTablosu`, `ElleGirilecek`); `Kalem` PSL/amaç doğrular, `elle_girilecekler()` tekrarsız listeler. |
| `app/itp/yer_tutucu.py` | ITP: şablon yer tutucuları, blokları ve üreticileri; `sayi` biçimleme, `grupla` (karar C). Sayıları Plan 1'den alır, standart sayısı yazmaz. |
| `app/itp/olustur.py` | ITP: `olustur(sablon, baslik, kalemler, *, firma)` kurulum motoru (`{firma}` belge geneli yer tutucu); satır/bölüm koşulları (`dis_kaplama`, `ic_kaplama`, `psl`); hesap hataları kalem no ile (`EslesmeHatasi`), şablon hataları şablon yeriyle (`SablonHatasi`). |
| `app/itp/sablon/` | ITP: Python veri şablonları — `itp_en.py` (ITP EN), `kp_ciplak.py` (KP çıplak boru TR), `kp_kaplama.py` (KP kaplama TR); yalnız standart değerleri taşır. |
| `app/itp/excel.py` | ITP: `excel_yaz(dokuman, yol, firma)` — ITP (EN, KURUM_C düzeni, 2 sayfa; kabul G:N 8 alt sütun, 18 sütun; logo A1:B1) ve KP (TR, KURUM_A KP düzeni, kabul D:K 8 alt sütun, 14 sütun, 3rd party varsa 15; logo A1:B3) Excel yazıcısı. |
| `app/itp/kabul_izgara.py` | ITP: kabul parçaları → Excel ızgara satırları (`izgara`, `dagit`; 8 alt sütun). Saf düzen, openpyxl'siz (2026-11-03). |
| `app/dil.py` | Arayüz dili (Qt'siz): `_` (çevir), `N_` (modül sabitini işaretle; kullanımda `_`), `deger` (veritabanında Türkçe duran seçmeli değerin gösterimi), `ayarla` / `etkin`. Süreç geneli tek dil; masaüstü kullanıcının dilini (`kullanicilar.dil`, şema 7) etkinleştirir, tablet sunucusu Türkçe kalır. |
| `app/dil_en.py` | İngilizce katalog: Türkçe kaynak metin → İngilizce. Eksik girdi `tests/test_dil_katalog.py`'de yakalanır. |
| `app/firma.py` | Firma kimliği (Qt'siz, şema 6 `ayarlar` tablosu): `Firma(ad, logo)`, `oku`, `yaz` (yalnız Yönetici; çakışma denetimli), `ad_dogrula`, `logo_turu` (PNG/JPEG, ≤1 MB). |
| `tools/ornek_cikti.py` | `docs/ornek-cikti/` altına 4 örnek sipariş xlsx'i üretir. |
| `app/itp_page.py` | ITP / Kalite Planı sekmesi (stacked indeks 5): başlık formu, şablon seçimi, kalem tablosu, önizleme ağacı, Excel'e aktarma; veri kaydetmez. |
| `tools/itp_ekran_goruntusu.py` | Sekmenin offscreen ekran görüntülerini (`docs/ornek-cikti/itp-sekmesi*.png`) üretir. |
| `tools/itp_goc.py` | Tek seferlik Database.xlsx → `api5l_47.py` göçü (çıktı varsa durur). |
| `app/kimlik.py` | Kimlik/yetki (Qt'siz): kullanıcılar (scrypt), roller (`YONETICI/DUZENLEYICI/OKUYUCU`, `yetkili`), kademeli kilit (hesap + ağdan girişte cihaz), oturum jetonu (özet saklanır), `guvenlik` olay kaydı. |
| `app/giris_penceresi.py` | İlk kurulum (yönetici), giriş, şifre değiştirme pencereleri; `oturum_ac(db)` main.py akışı. |
| `app/yonetim_sayfalari.py` | Yönetici sayfaları: Kullanıcılar (stacked 7), Değişiklik Kaydı + giriş/güvenlik olayları (stacked 8), Firma Bilgileri (stacked 9). |
| `app/itp_sekme.py` | ITP sipariş listesi + düzenleyici (stacked 5): aç, kopyala, müşteri onayı, yeni rev, sil; kayıt kuralları `itp/kayit.py`. |
| `app/itp/kayit.py`, `app/itp/goruntu.py` | ITP sipariş kaydı kuralları (Qt'siz; taslak / onaylı / revize) ve kilitli revizyonun JSON anlık görüntüsü. |
| `app/itp/kontrol.py` | Ortak kontrol listesi (`KONTROLLER`), şablon satırı eşlemesi (`SATIRLAR`), `sablonlari(anahtar)`. |
| `app/itp/sartname.py` | Şartname kütüphanesi kuralları (Qt'siz): kayıt, madde doğrulama, yürürlüğe alma, yeni rev, kopyala, sil, kilitli düzeltme (B6). |
| `app/sartname_sekme.py`, `app/sartname_page.py` | Şartnameler sayfası (stacked 6, herkes): liste (yürürlüğe al, yeni rev, klasörü aç) + düzenleyici, madde ve grup pencereleri. |
| `app/ozet.py` | Ana sayfa özeti (Qt'siz): kaynak (WPS/PQR) + belge (standart/sertifika) grupları ve öncelik sıralı "dikkat gerektirenler" (`seviye`, `metin`, `sekme`). Masaüstü ana sayfa ve tablet API'si ortak kullanır. |
| `app/sunucu.py` | Tablet sunucusu (`python -m app.sunucu`, port 8765): HTTPS (sertifika `data/tls/`); `POST /api/giris` → Bearer jeton; okuma (`/api/ozet`, `/api/{wps,pqr,std,cert}`, `/api/etiketler`, `/api/ben`) ve Düzenleyici+ için yazma (`POST /api/{b}`, `PUT/DELETE /api/{b}/{id}`, `surum` ile 409). Yazma `database.kayit_ekle/guncelle/sil` ile (değişiklik kaydı kaynak=tablet); rol kontrolü sunucu ucunda. `tablet/web/` arayüzünü ve `/indir/KaliteYS.apk`'yı sunar. |
| `tablet/web/` | Tablet web arayüzü (HTML/CSS/JS, bağımlılıksız; eski WebView uyumlu). |
| `tools/yonetici_kurtar.py` (+ `Yonetici Kurtarma.bat`) | Yalnız bu bilgisayarda: yöneticiyi etkinleştirir, kilidini açar, istenirse şifresini sıfırlar; güvenlik kaydına "kurtarma". |
| `tablet/android/`, `tools/apk_derle.py` | WebView kabuğu APK (Gradle'sız derleme). Kurulum: `docs/TABLET-KURULUM.md`. |

## Önemli teknik kararlar

- **Sekme indeksleri**: Ana=0, WPS=1, PQR=2, Standartlar=3, Sertifikalar=4, ITP=5,
  Şartnameler=6; yalnız yöneticide Kullanıcılar=7, Değişiklik Kaydı=8, Firma Bilgileri=9
  (görsel sırada PQR, WPS'ten önce gösterilir ama stacked indeksler budur).
  `HomePage` kartları bu indekslerle gezinir (`_card(..., tab_index)`).
- **Tablo aksiyon butonları** (`make_action_cell`): `padding:0` ZORUNLU (global
  QPushButton padding'i ikonu kırpar); sabit 26px boyut, satır yüksekliği 42.
  `QTableWidget::item` padding'i hücre alanını kısalttığından buton bundan büyük olmamalı.
- **Sütun genişliği** (`apply_col_widths`): başlık metnine göre, sabit Segoe UI 11px bold
  referansıyla deterministik hesaplanır → başlık kırpılması olmaz.
- **Hız (2026-10-29)**: pencere opak (saydam/layered pencere yok); sayfa geçişi, menü ve
  kartlarda sürekli çizim yapan efekt/animasyon yok (`QGraphicsEffect` yalnız geçici toast'ta).
  Tablo hücresi widget'larına `setStyleSheet` verilmez — stil tema QSS'inde objectName ile
  (satır başına QSS ayrıştırma yüzlerce satırda 100+ ms). Arama kutuları
  `widgets.gecikmeli_arama` (200 ms) ile bağlanır.
- **Standart sürümleme**: API kuruluşları baskı (Edition) + Errata/Addendum ile; diğerleri
  4 haneli yıl ile. Karşılaştırma `compare_std_status` içinde.
