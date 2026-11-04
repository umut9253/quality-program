# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""ITP / Kalite Planı sekmesinin ekran görüntüsünü üretir (QUALITY PROGRAM kökünden:
`python tools/itp_ekran_goruntusu.py`). Offscreen çalışır; MainWindow kurulmaz (veritabanı
yazılmaz, QSettings'e dokunulmaz): sayfa, uygulamanın temalı QSS'i ve kenar çubuğu görünümüyle
gerçek Sidebar sınıfıyla (genişlemiş, ITP düğmesi seçili) bir ana makete yerleştirilir. Çıktı: docs/ornek-cikti/itp-sekmesi.png ve itp-sekmesi-kp.png."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")   # 1400x900 piksel, ölçeksiz

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from PyQt6.QtGui import QFontDatabase  # noqa: E402
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QWidget  # noqa: E402

from app import theme  # noqa: E402
from app.firma import Firma  # noqa: E402
from app.itp_page import ITPPage  # noqa: E402

VARSAYILAN_DIZIN = KOK / "docs" / "ornek-cikti"
GENISLIK, YUKSEKLIK = 1400, 900
SECILI = 5


def _yazi_tipleri():
    """Offscreen platformda sistem yazı tipi yok (kutucuk çıkar): Windows yazı tiplerini yükler."""
    kok = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    for ad in ("segoeui.ttf", "segoeuib.ttf", "seguiemj.ttf", "seguisym.ttf"):
        if (kok / ad).exists():
            QFontDatabase.addApplicationFont(str(kok / ad))


def _pencere(sayfa):
    """Gerçek Sidebar sınıfı (app/main_window.py): 0-4 yer tutucu, 5 = ITP sayfası; genişlemiş
    durumda, 5. düğme seçili. MainWindow kurulmaz."""
    from PyQt6.QtWidgets import QStackedWidget
    from app.main_window import Sidebar
    host = QWidget()
    host.resize(GENISLIK, YUKSEKLIK)
    yigin = QStackedWidget()
    for _ in range(SECILI):
        yigin.addWidget(QWidget())
    yigin.addWidget(sayfa)
    yigin.setCurrentIndex(SECILI)
    yan = Sidebar(yigin)   # sabit genişlikte, gruplu menü (animasyon yok)
    yan.btn_group.button(SECILI).setChecked(True)
    yatay = QHBoxLayout(host); yatay.setContentsMargins(0, 0, 0, 0); yatay.setSpacing(0)
    yatay.addWidget(yan)
    yatay.addWidget(yigin, 1)
    host._yan = yan
    return host


def goruntu_al(sablon_adi, yol):
    """Sayfayı KURUM_C örnek siparişiyle doldurup verilen şablonla Oluştur'a basar, PNG yazar."""
    app = QApplication.instance() or QApplication(sys.argv)
    _yazi_tipleri()
    theme.set_theme("dark")
    app.setStyleSheet(theme.build_stylesheet())
    sayfa = ITPPage(mesaj=lambda tur, b, m: print(f"{tur}: {b}: {m}"),
                    firma=lambda: Firma("ÖRNEK FİRMA"))   # kurgusal
    host = _pencere(sayfa)
    sayfa.ornek_yukle()
    sayfa.cmb_sablon.setCurrentIndex(sayfa.cmb_sablon.findText(sablon_adi))
    host.show()
    app.processEvents()
    if sayfa.olustur() is None:
        raise RuntimeError(f"Oluştur başarısız: {sablon_adi}")
    app.processEvents()
    yol = Path(yol); yol.parent.mkdir(parents=True, exist_ok=True)
    if not host.grab().save(str(yol)):
        raise OSError(f"PNG yazılamadı: {yol}")
    host.close()
    return yol


def main(dizin=None):
    dizin = Path(dizin) if dizin else VARSAYILAN_DIZIN
    yollar = [goruntu_al("ITP (EN)", dizin / "itp-sekmesi.png"),
              goruntu_al("Kalite Planı – çıplak boru (TR)", dizin / "itp-sekmesi-kp.png")]
    for y in yollar:
        print(y)
    return yollar


if __name__ == "__main__":
    main()
