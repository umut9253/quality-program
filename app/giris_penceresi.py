# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Giriş, ilk kurulum (yönetici oluşturma) ve şifre değiştirme pencereleri.
Mantık app/kimlik.py'de; burada yalnız form ve mesaj."""
from PyQt6.QtWidgets import (QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QVBoxLayout)

from . import __app_name__, dil, kimlik as K
from .dil import _


class _Form(QDialog):
    def __init__(self, baslik, aciklama):
        super().__init__()
        self.setWindowTitle(f"{_(__app_name__)} — {baslik}")
        self.setMinimumWidth(420)
        self.L = QVBoxLayout(self); self.L.setContentsMargins(24, 22, 24, 18); self.L.setSpacing(10)
        b = QLabel(baslik); b.setStyleSheet("font-size:20px; font-weight:bold;")
        self.L.addWidget(b)
        if aciklama:
            a = QLabel(aciklama); a.setWordWrap(True); self.L.addWidget(a)
        self.form = QFormLayout(); self.L.addLayout(self.form)
        self.mesaj = QLabel(""); self.mesaj.setWordWrap(True)
        self.mesaj.setStyleSheet("color:#ef4444; font-weight:600;")
        self.L.addWidget(self.mesaj)

    def _alan(self, etiket, sifre=False):
        e = QLineEdit()
        if sifre:
            e.setEchoMode(QLineEdit.EchoMode.Password)
        self.form.addRow(etiket, e)
        return e

    def _dugme(self, metin, fn):
        h = QHBoxLayout(); h.addStretch()
        self.iptal = iptal = QPushButton(_("Vazgeç")); iptal.clicked.connect(self.reject)
        b = QPushButton(metin); b.setObjectName("btn_primary"); b.setDefault(True)
        b.clicked.connect(fn)
        h.addWidget(iptal); h.addWidget(b)
        self.L.addLayout(h)
        return b


class GirisDialog(_Form):
    """Başarılı girişte self.kullanici (kimlik.Kullanici) dolar ve pencere kabul edilir."""

    def __init__(self, c):
        super().__init__(_("Giriş"), _("Kullanıcı adınız ve şifrenizle giriş yapın."))
        self.c, self.kullanici = c, None
        self.ad = self._alan(_("Kullanıcı adı"))
        self.sifre = self._alan(_("Şifre"), sifre=True)
        self.btn = self._dugme(_("Giriş yap"), self.dene)
        self.ad.setFocus()

    def dene(self):
        try:
            self.kullanici = K.giris(self.c, self.ad.text(), self.sifre.text(), ip=K.YEREL)
        except K.GirisHatasi as e:
            self.mesaj.setText(str(e))
            self.sifre.clear(); self.sifre.setFocus()
            return
        self.accept()


class KilitDialog(_Form):
    """Hareketsizlik kilidi: yalnız oturum sahibinin şifresiyle açılır (hatalar kilit
    sayacına işler). Vazgeç = programı kapat."""

    def __init__(self, c, kullanici, parent=None):
        super().__init__(_("Ekran kilitlendi"),
                         _("{d} dakika işlem yapılmadığı için kilitlendi. Devam etmek için şifrenizi girin ({ad}).").format(d=K.BOS_KILIT_SN // 60, ad=kullanici.ad))
        if parent is not None:
            self.setParent(parent, self.windowFlags())
        self.c, self.kullanici, self.sonuc = c, kullanici, None
        self.sifre = self._alan(_("Şifre"), sifre=True)
        self._dugme(_("Kilidi aç"), self.dene)
        self.iptal.setText(_("Programı kapat"))
        self.sifre.setFocus()

    def dene(self):
        try:
            self.sonuc = K.giris(self.c, self.kullanici.ad, self.sifre.text(), ip=K.YEREL)
        except K.GirisHatasi as e:
            self.mesaj.setText(str(e))
            self.sifre.clear(); self.sifre.setFocus()
            return
        self.accept()


class KurulumDialog(_Form):
    """İlk açılış: henüz kullanıcı yokken ilk YÖNETİCİ hesabı."""

    def __init__(self, c):
        super().__init__(_("İlk kurulum"),
                         _("Programda henüz kullanıcı yok. Kullanıcıları ve yetkileri yönetecek yönetici hesabını oluşturun (şifre en az {EN_AZ_SIFRE} karakter).").format(EN_AZ_SIFRE=K.EN_AZ_SIFRE))
        self.c = c
        self.ad = self._alan(_("Kullanıcı adı"))
        self.ad_soyad = self._alan(_("Ad soyad"))
        self.sifre = self._alan(_("Şifre"), sifre=True)
        self.sifre2 = self._alan(_("Şifre (tekrar)"), sifre=True)
        self._dugme(_("Yönetici oluştur"), self.kaydet)

    def kaydet(self):
        if self.sifre.text() != self.sifre2.text():
            self.mesaj.setText(_("Şifreler eşleşmiyor."))
            return
        try:
            K.kullanici_ekle(self.c, self.ad.text(), self.sifre.text(), K.YONETICI,
                             ad_soyad=self.ad_soyad.text(), yapan="ilk kurulum")
        except K.KimlikHatasi as e:
            self.mesaj.setText(str(e))
            return
        self.accept()


class SifreDegistirDialog(_Form):
    def __init__(self, c, ad):
        super().__init__(_("Şifre değiştir"), _("Kullanıcı: {ad}").format(ad=ad))
        self.c, self.kullanici_adi = c, ad
        self.eski = self._alan(_("Mevcut şifre"), sifre=True)
        self.yeni = self._alan(_("Yeni şifre"), sifre=True)
        self.yeni2 = self._alan(_("Yeni şifre (tekrar)"), sifre=True)
        self._dugme(_("Değiştir"), self.kaydet)

    def kaydet(self):
        if self.yeni.text() != self.yeni2.text():
            self.mesaj.setText(_("Yeni şifreler eşleşmiyor."))
            return
        try:
            K.sifre_degistir(self.c, self.kullanici_adi, self.eski.text(), self.yeni.text())
        except K.KimlikHatasi as e:
            self.mesaj.setText(str(e))
            return
        self.accept()


def oturum_ac(db):
    """main.py akışı: gerekirse ilk kurulum, sonra giriş. Döner: Kullanici ya da None (vazgeçti).
    Giriş öncesi pencereler bu bilgisayarda son kullanılan dilde (kullanıcının dili MainWindow'da)."""
    from PyQt6.QtCore import QSettings
    son = QSettings("KaliteYS", "WPS_PQR").value("dil_son", "tr")
    dil.ayarla(son if son in dil.DILLER else "tr")
    if K.kurulum_gerekli(db._c) and KurulumDialog(db._c).exec() != QDialog.DialogCode.Accepted:
        return None
    g = GirisDialog(db._c)
    return g.kullanici if g.exec() == QDialog.DialogCode.Accepted else None

