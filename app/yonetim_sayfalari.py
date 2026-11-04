# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Yönetici sayfaları: Kullanıcılar (stacked 7), Değişiklik kaydı (stacked 8), Firma Bilgileri (9).
Yalnız yönetici rolünde kurulur (main_window); işlemler app/kimlik.py üzerinden."""
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout,
                             QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton,
                             QTableWidget, QTabWidget, QVBoxLayout, QWidget)

from . import firma, kimlik as K
from .database import VeritabaniHatasi
from .widgets import page_header, ro_item
from .dil import N_, _

BOLUM_ADI = {"wps": N_("WPS"), "pqr": N_("PQR"), "std": N_("Standart"), "cert": N_("Sertifika"),
             "itp": N_("ITP / KP"), "sartname": N_("Şartname"), "ayarlar": N_("Firma Bilgileri")}
ISLEM_ADI = {"ekle": N_("Eklendi"), "guncelle": N_("Güncellendi"), "sil": N_("Silindi")}
OLAY_ADI = {"giris": N_("Giriş"), "giris_basarisiz": N_("Hatalı giriş"), "hesap_kalici_kilit": N_("Hesap kilitlendi"),
            "kullanici_ekle": N_("Kullanıcı eklendi"), "rol_degistir": N_("Rol değişti"),
            "kullanici_pasif": N_("Devre dışı bırakıldı"), "kullanici_aktif": N_("Etkinleştirildi"),
            "kilit_ac": N_("Kilit açıldı"), "sifre_degistir": N_("Şifre değişti"),
            "sifre_sifirla": N_("Şifre sıfırlandı"), "itp_kilitli_sil": N_("Kilitli ITP/KP silindi"),
            "sartname_kilitli_sil": N_("Kilitli şartname silindi"),
            "sartname_kilitli_duzelt": N_("Kilitli şartname düzeltildi")}


def _tablo(basliklar):
    t = QTableWidget(0, len(basliklar))
    t.setHorizontalHeaderLabels(basliklar)
    t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    t.verticalHeader().setVisible(False)
    t.setAlternatingRowColors(True)
    t.horizontalHeader().setStretchLastSection(True)
    return t


def _doldur(t, satirlar):
    t.setRowCount(len(satirlar))
    for r, satir in enumerate(satirlar):
        for c, v in enumerate(satir):
            t.setItem(r, c, ro_item(v))
    t.resizeColumnsToContents()


class KullaniciEkleDialog(QDialog):
    def __init__(self, c, yapan):
        super().__init__()
        self.c, self.yapan = c, yapan
        self.setWindowTitle(_("Kullanıcı ekle")); self.setMinimumWidth(400)
        L = QVBoxLayout(self); f = QFormLayout(); L.addLayout(f)
        self.ad, self.ad_soyad = QLineEdit(), QLineEdit()
        self.rol = QComboBox()
        for r in K.ROLLER:
            self.rol.addItem(_(K.ROL_ADI[r]), r)
        self.rol.setCurrentIndex(K.ROLLER.index(K.DUZENLEYICI))
        self.sifre = QLineEdit(); self.sifre.setEchoMode(QLineEdit.EchoMode.Password)
        for etiket, w in ((_("Kullanıcı adı"), self.ad), (_("Ad soyad"), self.ad_soyad),
                          (_("Rol"), self.rol), (_("İlk şifre (en az {EN_AZ_SIFRE})").format(EN_AZ_SIFRE=K.EN_AZ_SIFRE), self.sifre)):
            f.addRow(etiket, w)
        self.mesaj = QLabel(""); self.mesaj.setStyleSheet("color:#ef4444;"); L.addWidget(self.mesaj)
        h = QHBoxLayout(); h.addStretch()
        b = QPushButton(_("Ekle")); b.setObjectName("btn_primary"); b.clicked.connect(self.kaydet)
        v = QPushButton(_("Vazgeç")); v.clicked.connect(self.reject)
        h.addWidget(v); h.addWidget(b); L.addLayout(h)

    def kaydet(self):
        try:
            K.kullanici_ekle(self.c, self.ad.text(), self.sifre.text(), self.rol.currentData(),
                             ad_soyad=self.ad_soyad.text(), yapan=self.yapan)
        except K.KimlikHatasi as e:
            self.mesaj.setText(str(e))
            return
        self.accept()


class KullanicilarPage(QWidget):
    SUTUNLAR = (N_("Kullanıcı adı"), N_("Ad soyad"), N_("Rol"), N_("Durum"), N_("Kilit"))

    def __init__(self, db):
        super().__init__()
        self.db = db
        L = QVBoxLayout(self); L.setContentsMargins(24, 20, 24, 16); L.setSpacing(10)
        L.addWidget(page_header(_("Kullanıcılar"), _("Hesaplar, roller, şifre sıfırlama ve kilitler")))
        tb = QHBoxLayout()
        for metin, fn, birincil in ((_("+  Kullanıcı ekle"), self.ekle, True),
                                    (_("Rol değiştir"), self.rol, False),
                                    (_("Şifre sıfırla"), self.sifirla, False),
                                    (_("Kilidi aç"), self.kilit_ac, False),
                                    (_("Devre dışı / etkin"), self.aktiflik, False)):
            b = QPushButton(metin); b.clicked.connect(fn)
            b.setObjectName("btn_primary" if birincil else "btn_ghost")
            tb.addWidget(b)
        tb.addStretch(); L.addLayout(tb)
        self.table = _tablo([_(x) for x in self.SUTUNLAR]); L.addWidget(self.table)
        self.refresh()

    def veriler(self):
        return K.kullanicilar(self.db._c)

    def refresh(self):
        self._v = self.veriler()
        _doldur(self.table, [(k["ad"], k["ad_soyad"], _(K.ROL_ADI.get(k["rol"], k["rol"])),
                              _("Aktif") if k["aktif"] else _("Devre dışı"), k["kilit"] or "—")
                             for k in self._v])

    def _secili(self):
        r = self.table.currentRow()
        if r < 0:
            QMessageBox.information(self, _("Kullanıcılar"), _("Önce tablodan bir kullanıcı seçin."))
            return None
        return self._v[r]

    def _yap(self, fn, *a):
        try:
            fn(self.db._c, *a, yapan=self.db.kullanici.ad if self.db.kullanici else "sistem")
        except K.KimlikHatasi as e:
            QMessageBox.warning(self, _("Kullanıcılar"), str(e))
        self.refresh()

    def ekle(self):
        if KullaniciEkleDialog(self.db._c, self.db.kullanici.ad if self.db.kullanici
                               else "sistem").exec():
            self.refresh()

    def rol(self):
        k = self._secili()
        if not k:
            return
        adlar = [_(K.ROL_ADI[r]) for r in K.ROLLER]
        sec, ok = QInputDialog.getItem(self, _("Rol değiştir"), _("{d} için yeni rol:").format(d=k['ad']), adlar,
                                       adlar.index(_(K.ROL_ADI[k["rol"]])), False)
        if ok:
            self._yap(K.rol_degistir, k["ad"], K.ROLLER[adlar.index(sec)])

    def sifirla(self):
        k = self._secili()
        if not k:
            return
        yeni, ok = QInputDialog.getText(self, _("Şifre sıfırla"), _("{d} için yeni şifre (en az {EN_AZ_SIFRE} karakter):").format(d=k['ad'], EN_AZ_SIFRE=K.EN_AZ_SIFRE),
                                        QLineEdit.EchoMode.Password)
        if ok:
            self._yap(K.sifre_sifirla, k["ad"], yeni)

    def kilit_ac(self):
        k = self._secili()
        if k:
            self._yap(K.kilit_ac, k["ad"])

    def aktiflik(self):
        k = self._secili()
        if k:
            self._yap(K.pasif_yap if k["aktif"] else K.aktif_yap, k["ad"])


def _degisen(once, sonra, sinir=4):
    if once is None or sonra is None:
        return ""
    alanlar = [a for a in sorted(set(once) | set(sonra)) if once.get(a) != sonra.get(a)]
    metin = "; ".join(f"{a}: {str(once.get(a, ''))[:30]} → {str(sonra.get(a, ''))[:30]}"
                      for a in alanlar[:sinir])
    return metin + (f" (+{len(alanlar) - sinir})" if len(alanlar) > sinir else "")


class DegisiklikPage(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        L = QVBoxLayout(self); L.setContentsMargins(24, 20, 24, 16); L.setSpacing(10)
        L.addWidget(page_header(_("Değişiklik kaydı"),
                                _("Kim, ne zaman, hangi kaydı değiştirdi; giriş ve güvenlik olayları")))
        tb = QHBoxLayout()
        self.bolum = QComboBox(); self.bolum.addItem(_("Tüm bölümler"), "")
        for b, ad in BOLUM_ADI.items():
            self.bolum.addItem(_(ad), b)
        self.bolum.currentIndexChanged.connect(self.refresh)
        yen = QPushButton(_("Yenile")); yen.setObjectName("btn_ghost"); yen.clicked.connect(self.refresh)
        tb.addWidget(self.bolum); tb.addStretch(); tb.addWidget(yen); L.addLayout(tb)
        self.sekme = QTabWidget()
        self.table = _tablo((_("Zaman"), _("Kullanıcı"), _("Kaynak"), _("Bölüm"), _("Kayıt No"), _("İşlem"),
                             _("Değişen alanlar")))
        self.guvenlik = _tablo((_("Zaman"), _("Olay"), _("Kullanıcı"), _("Cihaz / IP"), _("Yapan"), _("Ayrıntı")))
        self.sekme.addTab(self.table, _("Kayıt değişiklikleri"))
        self.sekme.addTab(self.guvenlik, _("Giriş ve güvenlik"))
        L.addWidget(self.sekme)
        self.refresh()

    def refresh(self):
        kayit = self.db.degisiklik_kayitlari(bolum=self.bolum.currentData() or None)
        _doldur(self.table, [(d["zaman"].replace("T", " "), d["kullanici"],
                              _("Tablet") if d["kaynak"] == "tablet" else _("Masaüstü"),
                              _(BOLUM_ADI.get(d["bolum"], d["bolum"])), d["kayit_no"],
                              _(ISLEM_ADI.get(d["islem"], d["islem"])), _degisen(d["once"], d["sonra"]))
                             for d in kayit])
        _doldur(self.guvenlik, [(datetime.fromtimestamp(g["zaman"]).strftime("%Y-%m-%d %H:%M:%S"),
                                 _(OLAY_ADI.get(g["olay"], g["olay"])), g["kullanici"],
                                 _("bu bilgisayar") if g["ip"] == "yerel" else g["ip"], g["yapan"],
                                 g["ayrinti"])
                                for g in K.guvenlik_kayitlari(self.db._c)])


class FirmaPage(QWidget):
    """Firma adı ve logo (spec 2026-11-02 F1): ITP/KP çıktılarına girer. Yalnız Yönetici görür;
    kayıt kalite.db `ayarlar` tablosuna (yedeğe girer, değişiklik kaydına işlenir)."""
    LOGO_KUTU = (240, 80)

    def __init__(self, db, mesaj=None, dosya_sec=None):
        super().__init__()
        self.db = db
        self._mesaj = mesaj or (lambda baslik, metin: QMessageBox.warning(self, baslik, metin))
        self._dosya_sec = dosya_sec or (lambda: QFileDialog.getOpenFileName(
            self, _("Logo seç"), "", _("Resim (*.png *.jpg *.jpeg)"))[0])
        L = QVBoxLayout(self); L.setContentsMargins(24, 20, 24, 16); L.setSpacing(10)
        L.addWidget(page_header(_("Firma Bilgileri"),
                                _("ITP ve Kalite Planı çıktılarındaki firma adı ve logo")))
        f = QFormLayout(); L.addLayout(f)
        self.ad = QLineEdit(); self.ad.setPlaceholderText(_("Belgelerde görünecek firma adı"))
        f.addRow(_("Firma adı"), self.ad)
        self.onizleme = QLabel(); self.onizleme.setFixedSize(*self.LOGO_KUTU)
        self.onizleme.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.onizleme.setStyleSheet("border:1px dashed #888;")
        f.addRow(_("Logo (PNG/JPG)"), self.onizleme)
        tb = QHBoxLayout()
        for metin, fn, ad in ((_("Logo seç…"), self.logo_sec, "btn_ghost"),
                              (_("Logoyu kaldır"), self.logo_kaldir, "btn_ghost"),
                              (_("Kaydet"), self.kaydet, "btn_primary")):
            b = QPushButton(metin); b.setObjectName(ad); b.clicked.connect(fn); tb.addWidget(b)
        tb.addStretch(); L.addLayout(tb)
        self.durum = QLabel(""); L.addWidget(self.durum)
        L.addStretch()
        self.refresh()

    def refresh(self):
        self._yuklenen = self.db.firma()
        self.ad.setText(self._yuklenen.ad)
        self._logo_goster(self._yuklenen.logo)
        self.durum.setText("" if self._yuklenen.ad else
                           _("Firma adı girilmeden ITP / Kalite Planı oluşturulamaz."))

    def _logo_goster(self, logo):
        self.logo = logo
        if not logo:
            self.onizleme.setPixmap(QPixmap()); self.onizleme.setText(_("Logo yok"))
            return
        p = QPixmap(); p.loadFromData(logo)
        self.onizleme.setPixmap(p.scaled(*self.LOGO_KUTU, Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation))

    def logo_sec(self):
        yol = self._dosya_sec()
        if not yol:
            return
        try:
            with open(yol, "rb") as f:
                veri = f.read()
            firma.logo_turu(veri)
            if not QPixmap().loadFromData(veri):   # imza doğru, gövde bozuk (Antigravity BULGU-02)
                raise ValueError(_("Logo resmi okunamadı (dosya bozuk ya da eksik)."))
        except (OSError, ValueError) as e:
            self._mesaj(_("Logo"), str(e))
            return
        self._logo_goster(veri)

    def logo_kaldir(self):
        self._logo_goster(None)

    def kaydet(self):
        try:
            self.db.firma_kaydet(self.ad.text(), self.logo, beklenen=self._yuklenen)
        except (VeritabaniHatasi, ValueError) as e:   # Cakisma/Yetki VeritabaniHatasi'dır
            self._mesaj(_("Firma Bilgileri"), str(e))
            self.refresh()                             # çakışmada güncel hal yüklenir
            return False
        self.refresh()
        return True
