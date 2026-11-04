# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""
Ana pencere: Özel başlık çubuğu (frameless), gruplu sabit yan menü, Ctrl+1…9
kısayolları, tek tıkla koyu/açık tema geçişi ve otomatik standart kontrol
zamanlayıcıları.

Hız (2026-10-29): saydam (layered) pencere, sayfa geçişindeki opaklık efekti ve
hover ile genişleyen menü animasyonu kaldırıldı — her biri tüm pencerenin yeniden
çizimini tetikliyordu.
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QFrame, QLabel, QButtonGroup, QSizeGrip, QStackedWidget, QMessageBox, QApplication, QDialog
)
from PyQt6.QtCore import QEvent, Qt, QTimer, QPoint, QSettings
from PyQt6.QtGui import QGuiApplication, QKeySequence, QShortcut

from . import __app_name__
from . import dil, kimlik
from .dil import N_, _
from . import theme
from .database import Database
from .pages import HomePage, WPSPage, PQRPage, STDPage, CertPage
from .itp_sekme import ITPSekme
from .sartname_sekme import SartnameSekme
from .giris_penceresi import KilitDialog, SifreDegistirDialog
from .yonetim_sayfalari import DegisiklikPage, FirmaPage, KullanicilarPage


class CustomTitleBar(QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setObjectName("title_bar")
        self.setFixedHeight(38)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 0, 0)
        layout.setSpacing(0)

        # Logo / Title
        title_lbl = QLabel(f" {_(__app_name__)}")
        title_lbl.setStyleSheet(
            f"color: {theme.t('text_secondary')}; font-weight: bold; "
            "font-size: 13px; letter-spacing: 1px;")
        layout.addWidget(title_lbl)

        layout.addStretch()

        # Giriş yapan kullanıcı + şifre değiştir + çıkış (kullanıcısız açılışta gizli)
        k = getattr(parent.db, "kullanici", None)
        self.kullanici_etiketi = QLabel(f"👤  {k.ad_soyad or k.ad}  ·  {_(kimlik.ROL_ADI[k.rol])}"
                                        if k else "")
        self.kullanici_etiketi.setStyleSheet(f"color: {theme.t('text_secondary')}; "
                                             "font-size: 12px; padding-right: 10px;")
        layout.addWidget(self.kullanici_etiketi)
        for metin, ipucu, fn in (("🔑", _("Şifremi değiştir"), self.parent.sifre_degistir),
                                 (_("Çıkış"), _("Oturumu kapat (programı kapatır)"), self.parent.close)):
            b = QPushButton(metin); b.setObjectName("btn_win")
            # metin genişliğine göre (İngilizce "Log out" Türkçe "Çıkış"tan uzun; kesilmesin)
            b.setFixedSize(46 if len(metin) < 3 else max(64, b.fontMetrics().horizontalAdvance(metin) + 64), 38)
            b.setToolTip(ipucu); b.clicked.connect(fn); b.setVisible(k is not None)
            layout.addWidget(b)

        # Tema değiştirme butonu (tek tıkla koyu ↔ açık)
        self.btn_theme = QPushButton("🌙" if theme.current() == "light" else "☀")
        self.btn_theme.setObjectName("btn_win")
        self.btn_theme.setFixedSize(46, 38)
        self.btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme.setToolTip(_("Açık temaya geç") if theme.current() == "dark"
                                  else _("Koyu temaya geç"))
        self.btn_theme.clicked.connect(self.parent.toggle_theme)
        layout.addWidget(self.btn_theme)

        # Dil düğmesi: gösterdiği dil, geçilecek dildir (kullanıcı başına kaydedilir)
        self.btn_dil = QPushButton(_("EN") if dil.etkin() == "tr" else _("TR"))
        self.btn_dil.setObjectName("btn_win")
        self.btn_dil.setFixedSize(max(46, self.btn_dil.fontMetrics().horizontalAdvance("EN") + 40), 38)
        self.btn_dil.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_dil.setToolTip(_("İngilizceye geç") if dil.etkin() == "tr" else _("Türkçeye geç"))
        self.btn_dil.clicked.connect(self.parent.toggle_dil)
        layout.addWidget(self.btn_dil)

        # Window Controls
        btn_min = QPushButton("—")
        btn_min.setObjectName("btn_win")
        btn_min.setFixedSize(46, 38)
        btn_min.clicked.connect(self.parent.showMinimized)

        self.btn_max = QPushButton("◻")
        self.btn_max.setObjectName("btn_win")
        self.btn_max.setFixedSize(46, 38)
        self.btn_max.clicked.connect(self.toggle_maximize)

        btn_close = QPushButton("✕")
        btn_close.setObjectName("btn_win_close")
        btn_close.setFixedSize(46, 38)
        btn_close.clicked.connect(self.parent.close)

        layout.addWidget(btn_min)
        layout.addWidget(self.btn_max)
        layout.addWidget(btn_close)

        self._is_tracking = False
        self._start_pos = QPoint()

    def toggle_maximize(self):
        if self.parent.isMaximized():
            self.parent.showNormal()
            self.btn_max.setText("◻")
        else:
            self.parent.showMaximized()
            self.btn_max.setText("❐")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_tracking = True
            self._start_pos = event.globalPosition().toPoint() - self.parent.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._is_tracking:
            if self.parent.isMaximized():
                self.parent.showNormal()
                self.btn_max.setText("◻")
                self._start_pos = QPoint(self.parent.width() // 2, 10)
            self.parent.move(event.globalPosition().toPoint() - self._start_pos)

    def mouseReleaseEvent(self, event):
        self._is_tracking = False

    def mouseDoubleClickEvent(self, event):
        self.toggle_maximize()


# Menü: (grup başlığı | None, [(ikon, etiket, stacked_index)]). Görsel sıra = Ctrl+1…9
# sırası; PQR görünümde WPS'ten önce gelir ama stacked indeksler sabittir (CLAUDE.md).
MENU = (
    (None, [("🏠", N_("Ana Sayfa"), 0)]),
    (N_("KAYNAK"), [("📋", N_("PQR Kayıtları"), 2), ("📄", N_("WPS Yönetimi"), 1)]),
    (N_("BELGE TAKİBİ"), [("📚", N_("Standartlar"), 3), ("📜", N_("Sertifikalar"), 4)]),
    (N_("ÜRETİM KALİTESİ"), [("📑", N_("ITP / Kalite Planı"), 5),
                            ("📘", N_("Şartnameler"), 6)]),
)
MENU_YONETIM = (N_("YÖNETİM"), [("👥", N_("Kullanıcılar"), 7), ("🧾", N_("Değişiklik Kaydı"), 8),
                            ("🏢", N_("Firma Bilgileri"), 9)])


class Sidebar(QFrame):
    """Sabit genişlikte, gruplu yan menü (ikon + etiket hep görünür).

    Buton `QButtonGroup` id'leri stacked sayfa indeksleridir (görsel sıradan bağımsız).
    Önceki hover ile genişleyen menü her açılışta tüm sayfayı yeniden yerleştiriyordu.
    """

    EXPANDED = 220

    def __init__(self, stacked_widget, yonetici=False):
        super().__init__()
        self.stacked_widget = stacked_widget
        self.setObjectName("sidebar")
        self.setFixedWidth(self.EXPANDED)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 18, 12, 18)
        layout.setSpacing(4)

        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)
        self.gruplar = []
        self.sira = []   # görsel sırayla stacked indeksleri (kısayollar)

        for grup, ogeler in MENU + ((MENU_YONETIM,) if yonetici else ()):
            if grup:
                lbl = QLabel(_(grup))
                lbl.setObjectName("nav_group")
                layout.addSpacing(10)
                layout.addWidget(lbl)
                self.gruplar.append(lbl)
            for icon, label, index in ogeler:
                self.sira.append(index)
                btn = QPushButton(f"{icon}  {_(label)}")
                btn.setObjectName("btn_nav")
                btn.setFixedHeight(40)
                btn.setCheckable(True)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                # Ctrl+1…9: onuncu öğenin kısayolu yok ("Ctrl+10" geçersiz)
                btn.setToolTip(f"{_(label)}  (Ctrl+{len(self.sira)})" if len(self.sira) <= 9
                               else _(label))
                btn.clicked.connect(
                    lambda checked, idx=index: self.stacked_widget.setCurrentIndex(idx))
                self.btn_group.addButton(btn, index)
                layout.addWidget(btn)

        self.btn_group.button(0).setChecked(True)
        layout.addStretch()


class MainWindow(QMainWindow):
    def __init__(self, db=None):
        super().__init__()
        self.db = db or Database()
        self._zorla_kapat = False   # kilit iptali: kaydedilmemiş ITP sorulmaz, kaydedilmez
        k = self.db.kullanici
        self.yonetici = k is not None and k.rol == kimlik.YONETICI
        self.settings = QSettings("KaliteYS", "WPS_PQR")
        theme.set_theme(self.settings.value("theme", "dark") or "dark")
        # arayüz dili kullanıcınındır (kullanıcısız açılış: Türkçe); giriş penceresi sonrakinde
        # bu bilgisayarda son kullanılan dille açılır
        dil.ayarla(kimlik.dil_oku(self.db._c, k.id) if k else "tr")
        if k:
            self.settings.setValue("dil_son", dil.etkin())

        # Çerçevesiz ama opak pencere: saydam (layered) pencere Windows'ta her yeniden
        # çizimde tüm pencereyi CPU ile birleştiriyordu (büyük/ekranı kaplayan pencerede yavaş)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setMinimumSize(1240, 720)
        self.resize(1440, 820)

        # Center Window (çok monitörlü kurulumda da geçerli ekran içinde merkezle)
        screen = QGuiApplication.primaryScreen()
        if screen:
            fg = self.frameGeometry()
            fg.moveCenter(screen.availableGeometry().center())
            self.move(fg.topLeft())

        self._page_index = 0
        self._build_ui()

        # Ctrl+1…9: menünün görsel sırası (pencere ömrü boyunca; tema geçişinde kalır)
        self.kisayollar = []
        for n, idx in enumerate(self.sidebar.sira[:9], start=1):
            k = QShortcut(QKeySequence(f"Ctrl+{n}"), self)
            k.activated.connect(lambda idx=idx: self.stacked.setCurrentIndex(idx))
            self.kisayollar.append(k)

        # Timers (her zaman güncel std_page'i kullanır)
        # Not: auto_check_standards() haftada 1 tarar (hafta başlangıcı:
        # config.STD_OTO_KONTROL_GUNU, varsayılan Pazartesi). Bu hafta zaten
        # taranmışsa sessizce döner; 24 saatlik sayaç bu yüzden zararsızdır.
        # Açılış kontrolü pencereye bağlı, durdurulabilir zamanlayıcı (pencere kapanınca
        # tetiklenmez; testler durdurabilir — aksi halde gerçek Gemini isteği gidiyordu)
        self.oto_kontrol_zamanlayici = QTimer(self)
        self.oto_kontrol_zamanlayici.setSingleShot(True)
        self.oto_kontrol_zamanlayici.timeout.connect(self._oto_kontrol)
        self.oto_kontrol_zamanlayici.start(2000)
        self.daily_timer = QTimer(self)
        self.daily_timer.setInterval(24 * 60 * 60 * 1000)
        self.daily_timer.timeout.connect(self._oto_kontrol)
        self.daily_timer.start()
        # Tablette yapılan değişiklikleri birkaç saniyede bir yansıt (PRAGMA data_version)
        self.dis_degisiklik_zamanlayici = QTimer(self)
        self.dis_degisiklik_zamanlayici.setInterval(3000)
        self.dis_degisiklik_zamanlayici.timeout.connect(self.dis_degisiklik_kontrol)
        self.dis_degisiklik_zamanlayici.start()
        # Hareketsizlik kilidi: fare/klavye olayı sayacı baştan başlatır (uygulama genelinde)
        self.bos_kilit_zamanlayici = QTimer(self)
        self.bos_kilit_zamanlayici.setSingleShot(True)
        self.bos_kilit_zamanlayici.setInterval(kimlik.BOS_KILIT_SN * 1000)
        self.bos_kilit_zamanlayici.timeout.connect(self.kilitle)
        if self.db.kullanici is not None:
            QApplication.instance().installEventFilter(self)
            # pencere kapanmadan çıkılırsa da (QApplication.exit) süzgeç kalmasın
            QApplication.instance().aboutToQuit.connect(self._suzgeci_kaldir)
            self.bos_kilit_zamanlayici.start()

    _HAREKET = (QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress,
                QEvent.Type.Wheel)

    def eventFilter(self, nesne, olay):
        if olay.type() in self._HAREKET and self.bos_kilit_zamanlayici.isActive():
            self.bos_kilit_zamanlayici.start()
        return False

    def _suzgeci_kaldir(self):
        # Uygulama geneli süzgeç pencere yok edilirken de çağrılır (yarı silinmiş Python nesnesi
        # → erişim ihlali); kapanırken / çıkarken kaldırılır.
        QApplication.instance().removeEventFilter(self)

    def closeEvent(self, olay):
        # Kaydedilmemiş ITP / şartname değişikliği sorulur; kilit iptalinde (_zorla_kapat)
        # sorulmaz ve kaydedilmez: kilidi geçemeyen kişi "Kaydet" ile yazma yapamasın.
        if not self._zorla_kapat and not (self.itp_page.kapatilabilir()
                                          and self.sartname_page.kapatilabilir()):
            olay.ignore()
            return
        self.std_page.kontrolu_durdur()
        self._suzgeci_kaldir()
        super().closeEvent(olay)

    def kilitle(self):
        """İçeriği ve açık pencereleri gizler, şifre ister; vazgeçilirse programı kapatır."""
        self.bos_kilit_zamanlayici.stop()
        orta = self.centralWidget()
        orta.hide()
        # Açık düzenleme/ayrıntı pencereleri: hide() exec döngüsünü bitirip girdiyi kaybettirir;
        # opaklık 0 ile görünmez yapılır (kilit penceresi uygulama-modal: etkileşim de yok)
        acik = [p for p in QApplication.topLevelWidgets() if p is not self and p.isVisible()]
        for p in acik:
            p.setWindowOpacity(0.0)
        kilit = KilitDialog(self.db._c, self.db.kullanici, self)
        devam = kilit.exec() == QDialog.DialogCode.Accepted
        if devam and kilit.sonuc.rol != self.db.kullanici.rol:
            QMessageBox.information(self, _("Yetki değişti"),
                                    _("Yetkiniz değiştirildi; program kapanıyor, yeniden giriş yapın."))
            devam = False
        if not devam:
            for p in acik:   # kaydedilmeden iptal: kilit atlatılıp kayıt yapılamasın
                p.reject() if isinstance(p, QDialog) else p.close()
            self._zorla_kapat = True
            self.close()
            return
        for p in acik:
            p.setWindowOpacity(1.0)
        orta.show()
        self.bos_kilit_zamanlayici.start()

    def _oto_kontrol(self):
        """Otomatik standart taraması kayıt yazar: yalnız düzenleyici/yönetici oturumunda."""
        k = self.db.kullanici
        if k is None or kimlik.yetkili(k.rol, kimlik.DUZENLEYICI):
            self.std_page.auto_check_standards()

    def dis_degisiklik_kontrol(self):
        if self.db.disaridan_degisti():
            self.db.yeniden_yukle()
            for sayfa in (self.wps_page, self.pqr_page, self.std_page, self.cert_page,
                          self.home_page, self.itp_page, self.sartname_page):
                sayfa.refresh()
            if self.yonetici:
                self.degisiklik_page.refresh()

    def sifre_degistir(self):
        k = self.db.kullanici
        if k and SifreDegistirDialog(self.db._c, k.ad).exec():
            QMessageBox.information(self, _("Şifre"), _("Şifreniz değiştirildi."))

    def _build_ui(self):
        """Merkezi içeriği aktif temaya göre (yeniden) kurar."""
        central = QWidget()
        central.setObjectName("main_bg")
        central.setStyleSheet(
            f"QWidget#main_bg {{ background-color: {theme.t('window_bg')}; "
            f"border: 1px solid {theme.t('border_dim')}; }}")
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Title Bar
        self.title_bar = CustomTitleBar(self)
        root_layout.addWidget(self.title_bar)

        # Body Layout
        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        root_layout.addLayout(body_layout)

        # Stacked Pages (geçiş anında; opaklık efekti tüm sayfayı ekran dışında çiziyordu)
        self.stacked = QStackedWidget()

        # Sidebar
        self.sidebar = Sidebar(self.stacked, self.yonetici)
        body_layout.addWidget(self.sidebar)
        body_layout.addWidget(self.stacked)

        # Init Pages
        self.home_page = HomePage(self.db, self.stacked)
        self.wps_page = WPSPage(self.db)
        self.pqr_page = PQRPage(self.db, self.wps_page)
        self.std_page = STDPage(self.db, on_data_changed=self.home_page.refresh)
        self.cert_page = CertPage(self.db, on_data_changed=self.home_page.refresh)
        self.itp_page = ITPSekme(self.db)
        self.sartname_page = SartnameSekme(self.db)

        self.stacked.addWidget(self.home_page)
        self.stacked.addWidget(self.wps_page)
        self.stacked.addWidget(self.pqr_page)
        self.stacked.addWidget(self.std_page)
        self.stacked.addWidget(self.cert_page)
        self.stacked.addWidget(self.itp_page)   # indeks 5 (V-4-2)
        self.stacked.addWidget(self.sartname_page)   # indeks 6 (Plan 5b-2a; herkes)
        if self.yonetici:                       # indeks 7, 8, 9: yalnız yönetici
            self.kullanicilar_page = KullanicilarPage(self.db)
            self.degisiklik_page = DegisiklikPage(self.db)
            self.firma_page = FirmaPage(self.db)
            self.stacked.addWidget(self.kullanicilar_page)
            self.stacked.addWidget(self.degisiklik_page)
            self.stacked.addWidget(self.firma_page)
            self.stacked.currentChanged.connect(
                lambda i: self.degisiklik_page.refresh() if i == 8 else
                self.firma_page.refresh() if i == 9 else None)

        # Refresh home on switch
        self.stacked.currentChanged.connect(
            lambda i: self.home_page.refresh() if i == 0 else None)

        # Update sidebar selection when page changes programmatically
        self.stacked.currentChanged.connect(
            lambda i: self.sidebar.btn_group.button(i).setChecked(True) if self.sidebar.btn_group.button(i) else None)

        # Geçerli sayfayı geri yükle (tema geçişinde korunur)
        self.stacked.setCurrentIndex(self._page_index)
        btn = self.sidebar.btn_group.button(self._page_index)
        if btn:
            btn.setChecked(True)

        self.setStyleSheet(theme.build_stylesheet())

        # Boyutlandırma tutamacı — çerçevesiz pencere aksi halde boyutlandırılamaz
        self._grip = QSizeGrip(central)
        self._grip.setFixedSize(18, 18)
        self._grip.setStyleSheet("background: transparent;")
        self._grip.setToolTip(_("Pencereyi boyutlandır"))
        self._position_grip()
        self._grip.raise_()

    def _position_grip(self):
        central = self.centralWidget()
        if central is not None and hasattr(self, "_grip"):
            self._grip.move(central.width() - 20, central.height() - 20)
            self._grip.raise_()

    def toggle_theme(self):
        """Koyu ↔ açık tema arasında geçiş yapar ve seçimi kaydeder."""
        if self.std_page.kontrol_suruyor():   # sayfa yeniden kurulunca işçisi yok edilir: çökme
            QMessageBox.information(self, _("Tema"), _("Standart güncelleme kontrolü sürüyor; "
                                    "bitince tema değiştirilebilir."))
            return
        self._page_index = self.stacked.currentIndex()
        new_theme = "light" if theme.current() == "dark" else "dark"
        theme.set_theme(new_theme)
        self.settings.setValue("theme", new_theme)
        # ITP / şartname: açık kayıt + kaydedilmemiş girdiler taşınır (V-4-3)
        itp_durum, sartname_durum = self.itp_page.durum(), self.sartname_page.durum()
        self._build_ui()
        self.itp_page.durumu_yukle(itp_durum)
        self.sartname_page.durumu_yukle(sartname_durum)

    def toggle_dil(self):
        """Türkçe ↔ İngilizce: kullanıcının dili kaydedilir, pencere tema geçişindeki gibi
        yeniden kurulur (ITP ve şartname girdileri taşınır)."""
        if self.std_page.kontrol_suruyor():   # sayfa yeniden kurulunca işçisi yok edilir: çökme
            QMessageBox.information(self, _("Dil"), _("Standart güncelleme kontrolü sürüyor; bitince "
                                                "dil değiştirilebilir."))
            return
        yeni = "en" if dil.etkin() == "tr" else "tr"
        k = self.db.kullanici
        if k:
            kimlik.dil_ayarla(self.db._c, k.id, yeni)
            self.settings.setValue("dil_son", yeni)
        dil.ayarla(yeni)
        self._page_index = self.stacked.currentIndex()
        itp_durum, sartname_durum = self.itp_page.durum(), self.sartname_page.durum()
        self._build_ui()
        self.itp_page.durumu_yukle(itp_durum)
        self.sartname_page.durumu_yukle(sartname_durum)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_grip()
