# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""
═══════════════════════════════════════════════════════════════════════
  Kalite Yönetim Sistemi  —  WPS / PQR / Standart / Sertifika Takibi
  Modüler PyQt6 uygulaması (Python 3.13)
═══════════════════════════════════════════════════════════════════════

KURULUM:
  pip install PyQt6 requests openpyxl

API ANAHTARI (standart güncelleme kontrolü için):
  Gemini API anahtarı artık kodda TUTULMAZ. Şu iki yoldan biriyle tanımlanır:
    1) GEMINI_API_KEY ortam değişkeni, veya
    2) data/api_key.txt dosyası (ilk # ile başlamayan satır anahtar kabul edilir)
  Bu dosya gizlidir; kod paylaşılırken PAYLAŞILMAMALIDIR.

ÇALIŞTIRMA:
  python main.py

Proje yapısı:
  main.py              → giriş noktası
  data/kalite.db       → SQLite veritabanı (ilk açılışta data/data.json'dan
                         taşınır; her açılışta yedek/auto_kalite_*.db günlük yedeği)
  app/                 → uygulama modülleri (config, theme, database,
                         standards_check, widgets, dialogs, pages,
                         exporter, main_window)
"""

import sys

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QFont

from app import __app_name__
from app.database import Database, VeritabaniHatasi
from app.giris_penceresi import oturum_ac
from app.main_window import MainWindow


def _hata_kancasi(tur, deger, iz):
    """Çalışırken veritabanı yazma hatası (disk dolu, kilit...): program kapanmaz, kullanıcı
    görür; değişiklik uygulanmamıştır (önce DB, sonra bellek). Diğer hatalar eskisi gibi."""
    if issubclass(tur, VeritabaniHatasi):
        if _hata_kancasi.acik:   # kalıcı hatada (disk dolu) toplu işlem pencere yığmasın
            print(f"[DB] {deger}", file=sys.stderr)
            return
        _hata_kancasi.acik = True
        try:
            QMessageBox.critical(None, "Veritabanı hatası", str(deger))
        finally:
            _hata_kancasi.acik = False
        return
    sys.__excepthook__(tur, deger, iz)
    QApplication.exit(1)


_hata_kancasi.acik = False


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setFont(QFont("Segoe UI", 10))
    try:
        db = Database()
    except VeritabaniHatasi as e:   # bozuk DB / taşınamayan data.json: sessiz örnek veri yok
        QMessageBox.critical(None, "Veritabanı açılamadı", str(e))
        sys.exit(1)
    kullanici = oturum_ac(db)       # ilk açılışta yönetici oluşturma, sonra giriş
    if kullanici is None:
        sys.exit(0)
    db.kullanici = kullanici
    win = MainWindow(db)
    sys.excepthook = _hata_kancasi
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
