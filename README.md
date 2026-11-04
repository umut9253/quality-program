# QUALITY PROGRAM — Kalite Yönetim Sistemi

Kaynak / kaplama / boru üretiminde kalite birimleri için masaüstü uygulaması.
*A desktop quality-management app for welding, coating and line-pipe QC teams (Turkish UI, English option).*

**Python 3.13 · PyQt6 · SQLite (WAL) · çift tema · TR/EN arayüz · HTTPS tablet istemcisi**

## Ne yapar

- **WPS / PQR takibi:** kaynak prosedürleri ve nitelendirme kayıtları, ilişkili kayıt kontrolü, kaynak şematiği.
- **Standart takibi:** standart listesi, sürüm karşılaştırması (API: Edition+Errata, diğerleri: yıl),
  isteğe bağlı Gemini + Google Search ile haftalık otomatik sürüm taraması.
- **Sertifika takibi:** bitiş tarihine göre geçerli / yakında / dolmuş durumu.
- **ITP / Kalite Planı oluşturucu:** sipariş kalemlerinden (PSL, grade, çap, et kalınlığı, kaplama)
  Excel ITP (EN) ve KP (TR) üretir; şartname kütüphanesiyle müşteri şartnamesi farklarını uygular;
  taslak / onaylı / revize akışı.
- **Kullanıcılar ve yetki:** roller, hesap kilidi, oturum; her değişiklik kim/önce/sonra ile kaydedilir.
- **Tablet:** yerel ağda HTTPS sunucu + web arayüzü + Android APK derleyici.
- **Türkçe arama:** İ/I/ı/i katlamalı arama (`app/search_utils.py`).

## Standart verisi bu depoda YOK

API 5L, ISO 21809 gibi standartların tablo değerleri ve madde metinleri telif kapsamındadır ve
**bu depoya konmamıştır**. Aşağıdaki dosyalar aynı ad ve yapıda **boş iskelettir**:

| Dosya | İçerik |
| --- | --- |
| `app/itp/veri/api5l_47.py` | API 5L tablo/parametre yapısı, değerler boş |
| `app/itp/veri/iso21809.py` | ISO 21809 kriter/kalınlık yapısı, değerler boş |
| `app/itp/sablon/*.py` | ITP / KP bölüm düzeni, her bölümde görünür yer tutucu satır |

Bu yüzden program açılır ve tüm modüller çalışır, ancak ITP/KP hesapları kabul kriteri üretmez
("eşleşen satır yok" hatası verir). Kendi lisanslı standardınızdan doldurduğunuz veriyi aynı
değişken adlarıyla bu dosyalara koyabilirsiniz. Standart değerlerini doğrulayan testler de bu
nedenle depoda yoktur; ITP akış testlerinden veri gerektirenler
([tests/standart_verisi_gerekir.txt](tests/standart_verisi_gerekir.txt)) `SKIPPED` olarak görünür.

## Çalıştırma

```bash
pip install PyQt6 requests openpyxl
python main.py
```

İlk açılışta `data/kalite.db` örnek (kurgusal) kayıtlarla oluşturulur.
Otomatik standart taraması için isteğe bağlı: `GEMINI_API_KEY` ortam değişkeni veya
`data/api_key.txt` (depoya girmez).

```bash
pip install pytest Pillow
QT_QPA_PLATFORM=offscreen python -m pytest tests -q
```

Ayrıntılar: [docs/MIMARI.md](docs/MIMARI.md) · [docs/EL-KITABI.md](docs/EL-KITABI.md) ·
[docs/TABLET-KURULUM.md](docs/TABLET-KURULUM.md)

## Lisans

**Tüm hakları saklıdır** (© 2026 Umut Can Hocaoğlu) — [LICENSE](LICENSE). Kod yalnızca
incelemek için görünür durumdadır; kopyalama, değiştirme, dağıtma veya ticari kullanım için
yazılı izin gerekir. *All rights reserved; viewing only, no license granted.*
