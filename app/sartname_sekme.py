# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Şartnameler sekmesi (Plan 5b-2a): şartname kütüphanesinin listesi + düzenleyici.

ITP sekmesi kalıbı (app/itp_sekme.py): Liste → Aç / Yeni → SartnamePage. Kurallar
app/itp/sartname.py'de (Qt'siz); burada yalnız seçim, diyalog ve veritabanı çağrısı vardır.
Diyaloglar (mesaj, girdi, üç seçenekli soru, klasör aç) testler için enjekte edilebilir. Kayıt
kalıcı kimliği (id, sürüm) diyaloglardan önce alınır: liste yenilense de aynı kayda yazılır.
"""
import os

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (QHBoxLayout, QHeaderView, QInputDialog, QLineEdit, QMessageBox,
                             QPushButton, QStackedWidget, QTableWidget, QTableWidgetItem,
                             QVBoxLayout, QWidget)

from . import kimlik
from .database import CakismaHatasi, VeritabaniHatasi, YetkiHatasi
from .itp import sartname as S
from .itp_page import _varsayilan_mesaj
from .sartname_page import SartnamePage
from .search_utils import tr_fold
from .widgets import page_header
from .dil import N_, _

SUTUNLAR = (N_("Kurum"), N_("Şartname adı"), N_("Tür"), N_("No"), N_("Rev"), N_("Durum"))
_YAZMA_HATALARI = (S.SartnameHatasi, CakismaHatasi, YetkiHatasi, VeritabaniHatasi)


class SartnameSekme(QStackedWidget):
    def __init__(self, db, mesaj=None, girdi=None, uc_secenek=None, klasor_ac=None):
        super().__init__()
        self.db = db
        self._mesaj = mesaj or (lambda tur, b, m: _varsayilan_mesaj(self, tur, b, m))
        self.girdi = girdi or self._qt_girdi
        self.uc_secenek = uc_secenek or self._qt_uc_secenek
        self.klasor_ac = klasor_ac or (lambda yol: QDesktopServices.openUrl(QUrl.fromLocalFile(yol)))
        k = db.kullanici
        self.rol = k.rol if k else None
        self.acik = None            # açık kaydın (id, sürüm); None = yeni (kaydedilmemiş)
        self._satir_indeks = []     # tablo satırı → db listesindeki indeks
        self.liste = self._liste_kur()
        self.editor = SartnamePage(mesaj=self._mesaj, rol=self.rol, on_kaydet=self._kaydet,
                                   on_listeye_don=self.listeye_don, on_duzelt=self._duzelt,
                                   girdi=lambda *a: self.girdi(*a))
        self.addWidget(self.liste)
        self.addWidget(self.editor)
        self.refresh()

    # ── varsayılan diyaloglar ──────────────────────────────────────
    def _qt_girdi(self, baslik, etiket, varsayilan=""):
        metin, ok = QInputDialog.getText(self, baslik, etiket, text=varsayilan)
        return metin if ok else None

    def _qt_uc_secenek(self, baslik, metin):
        B = QMessageBox.StandardButton
        y = QMessageBox.question(self, baslik, metin, B.Save | B.Discard | B.Cancel, B.Save)
        return {B.Save: "kaydet", B.Discard: "atla"}.get(y, "vazgec")

    def _yazabilir(self):
        return self.rol is None or kimlik.yetkili(self.rol, kimlik.DUZENLEYICI)

    # ── liste ──────────────────────────────────────────────────────
    def _liste_kur(self):
        w = QWidget()
        L = QVBoxLayout(w); L.setContentsMargins(24, 20, 24, 16); L.setSpacing(10)
        L.addWidget(page_header(_("Şartnameler"),
                                _("Müşteri şartnameleri; taslak hazırlayın, yürürlüğe alın, "
                                  "revizyon açın")))
        ust = QHBoxLayout()
        self.arama = QLineEdit(); self.arama.setPlaceholderText(_("Ara (kurum, ad, no…)"))
        self.arama.textChanged.connect(self._suz)
        ust.addWidget(self.arama, 1)
        self.btn_yeni = QPushButton(_("+  Yeni")); self.btn_yeni.setObjectName("btn_primary")
        self.btn_yeni.clicked.connect(self.yeni)
        self.btn_ac = QPushButton(_("Aç"))
        self.btn_kopyala = QPushButton(_("Kopyala"))
        self.btn_yururluk = QPushButton(_("Yürürlüğe al"))
        self.btn_yeni_rev = QPushButton(_("Yeni rev"))
        self.btn_sil = QPushButton(_("Sil"))
        self.btn_klasor = QPushButton(_("Klasörü aç"))
        for b, fn in ((self.btn_ac, self.ac), (self.btn_kopyala, self.kopyala),
                      (self.btn_yururluk, self.yururluge_al), (self.btn_yeni_rev, self.yeni_rev),
                      (self.btn_sil, self.sil), (self.btn_klasor, self.klasoru_ac)):
            b.setObjectName("btn_ghost" if b is not self.btn_ac else "btn_primary")
            b.clicked.connect(lambda __=False, fn=fn: self._secili_ile(fn))
        for b in (self.btn_yeni, self.btn_ac, self.btn_kopyala, self.btn_yururluk,
                  self.btn_yeni_rev, self.btn_sil, self.btn_klasor):
            ust.addWidget(b)
        L.addLayout(ust)
        self.tablo = QTableWidget(0, len(SUTUNLAR))
        self.tablo.setHorizontalHeaderLabels([_(x) for x in SUTUNLAR])
        self.tablo.verticalHeader().setVisible(False)
        self.tablo.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tablo.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tablo.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tablo.itemSelectionChanged.connect(self._dugmeler)
        self.tablo.cellDoubleClicked.connect(lambda r, _c: self._secili_ile(self.ac))
        L.addWidget(self.tablo, 1)
        return w

    def refresh(self):
        kayitlar = self.db.get_sartname()
        sira = sorted(range(len(kayitlar)),
                      key=lambda i: (tr_fold(kayitlar[i]["kurum"]), tr_fold(kayitlar[i]["ad"]),
                                     -kayitlar[i]["rev_sira"]))
        self._satir_indeks = sira
        self.tablo.setRowCount(0)
        for i in sira:
            v = kayitlar[i]
            r = self.tablo.rowCount()
            self.tablo.insertRow(r)
            for c, metin in enumerate((v["kurum"], v["ad"], S.tur_metni(v), v["no"], v["rev"],
                                       S.durum_metni(v))):
                self.tablo.setItem(r, c, QTableWidgetItem(str(metin)))
        self._suz()
        self._dugmeler()

    def _suz(self, *__):
        q = tr_fold(self.arama.text().strip())
        for r in range(self.tablo.rowCount()):
            metin = " ".join(self.tablo.item(r, c).text() for c in range(len(SUTUNLAR)))
            self.tablo.setRowHidden(r, bool(q) and q not in tr_fold(metin))

    def secili_indeks(self):
        satirlar = self.tablo.selectionModel().selectedRows()
        return self._satir_indeks[satirlar[0].row()] if satirlar else None

    def _secili_ile(self, fn):
        i = self.secili_indeks()
        if i is None:
            self._mesaj("bilgi", _("Seçim yok"), _("Önce listeden bir kayıt seçin."))
            return
        fn(i)

    def _dugmeler(self):
        yaz = self._yazabilir()
        for b in (self.btn_yeni, self.btn_kopyala, self.btn_yururluk, self.btn_yeni_rev):
            b.setVisible(yaz)
        i = self.secili_indeks()
        kayitlar = self.db.get_sartname()
        v = None if i is None else kayitlar[i]
        self.btn_sil.setVisible(yaz and (v is None or v["durum"] == S.TASLAK
                                         or self.rol in (None, kimlik.YONETICI)))
        self.btn_ac.setEnabled(v is not None)
        self.btn_kopyala.setEnabled(v is not None)
        self.btn_yururluk.setEnabled(v is not None and v["durum"] == S.TASLAK)
        self.btn_yeni_rev.setEnabled(v is not None and S.en_yuksek_mi(kayitlar, v))
        self.btn_sil.setEnabled(v is not None)
        self.btn_klasor.setEnabled(v is not None and bool(v["kaynak_klasor"].strip()))

    # ── ekran geçişi ───────────────────────────────────────────────
    def yeni(self):
        self.acik = None
        self.editor.kaydi_yukle(None)
        self.setCurrentWidget(self.editor)

    def ac(self, i):
        anahtar = self.db.anahtar("sartname", i)
        try:
            self.editor.kaydi_yukle(self.db.get_sartname()[i])
        except (KeyError, TypeError, ValueError, S.SartnameHatasi) as e:   # bozuk kayıt
            self._mesaj("hata", _("Açılamadı"), str(e))
            return False
        self.acik = anahtar
        self.setCurrentWidget(self.editor)
        return True

    def _kaydedilmemis_sor(self):
        """Düzenleyicide kaydedilmemiş değişiklik varsa sorar. Devam edilebilir mi?"""
        if self.currentWidget() is not self.editor or not self.editor.degisti \
                or self.editor.salt_okunur:
            return True
        secim = self.uc_secenek(_("Kaydedilmemiş değişiklik"),
                                _("Şartnamede kaydedilmemiş değişiklik var. Kaydedilsin mi?"))
        if secim == "kaydet":
            return self.editor.kaydet()
        return secim == "atla"

    def listeye_don(self):
        if not self._kaydedilmemis_sor():
            return False
        self.acik = None
        self.refresh()
        self.setCurrentWidget(self.liste)
        return True

    def kapatilabilir(self):
        return self._kaydedilmemis_sor()

    # ── yazma ──────────────────────────────────────────────────────
    def _yaz(self, baslik, fn):
        """fn() veritabanına yazar; hata mesajla gösterilir. Başarılıysa True."""
        try:
            fn()
        except _YAZMA_HATALARI as e:
            self._mesaj("hata", baslik, str(e))
            if isinstance(e, CakismaHatasi):
                self.refresh()
            return False
        self.refresh()
        return True

    def _acik_indeks(self):
        i = self.db.indeks("sartname", self.acik[0])
        if i is None:
            raise CakismaHatasi(_("Kayıt başka bir cihazda silinmiş."))
        return i

    def _acigi_yenile(self, kid):
        """Yazmadan sonra: yeni sürümle anahtar; düzenleyici kayıtlı hali gösterir."""
        i = self.db.indeks("sartname", kid)
        self.acik = self.db.anahtar("sartname", i)
        self.editor.kaydi_yukle(self.db.get_sartname()[i])

    def _kaydet(self, veri):
        kayitlar = self.db.get_sartname()
        sonuc = {}

        def yaz():
            if self.acik is None:
                S.kaydet_kontrol(kayitlar, veri)
                sonuc["kid"] = self.db.add_sartname(veri)
            else:
                i = self._acik_indeks()
                S.kaydet_kontrol(kayitlar, veri, haric=i)
                self.db.update_sartname(i, veri, anahtar=self.acik)
                sonuc["kid"] = self.acik[0]
        if not self._yaz(_("Kaydedilemedi"), yaz):
            return False
        self._acigi_yenile(sonuc["kid"])
        return True

    def _duzelt(self, veri, gerekce):
        def yaz():
            self.db.sartname_kilitli_duzelt(self._acik_indeks(), veri, gerekce,
                                            anahtar=self.acik)
        if not self._yaz(_("Düzeltilemedi"), yaz):
            return False
        self._acigi_yenile(self.acik[0])
        return True

    def _guncel_indeks(self, anahtar):
        """Diyalogdan sonra: kayıt hâlâ var mı, şimdiki indeksi (liste 3 sn'de yenilenir)."""
        j = self.db.indeks("sartname", anahtar[0])
        if j is None:
            self._mesaj("hata", _("Kayıt yok"), _("Kayıt başka bir cihazda silinmiş; liste yenilendi."))
            self.refresh()
        return j

    def yururluge_al(self, i):
        anahtar = self.db.anahtar("sartname", i)
        v = self.db.get_sartname()[i]
        if not self._mesaj("soru", _("Yürürlüğe al"),
                           _("{d} yürürlüğe alınsın mı? Kayıt kilitlenir; değişiklik için yeni "
                             "rev açılır.").format(d=S.kayit_adi(v))):
            return
        if (j := self._guncel_indeks(anahtar)) is None:
            return
        self._yaz(_("Yürürlüğe alınamadı"), lambda: self.db.update_sartname(
            j, S.yururluge_al(self.db.get_sartname()[j]), anahtar=anahtar))

    def yeni_rev(self, i):
        anahtar = self.db.anahtar("sartname", i)
        v = self.db.get_sartname()[i]
        rev = None
        if not v["rev"].strip().isdigit():
            rev = self.girdi(_("Yeni rev"), _("Rev '{d}' sayısal değil; yeni rev:").format(d=v['rev']), "")
            if rev is None:
                return
        if (j := self._guncel_indeks(anahtar)) is None:
            return
        sonuc = {}

        def yaz():
            kayitlar = self.db.get_sartname()
            eski, yeni = S.yeni_rev(kayitlar, kayitlar[j], rev)
            sonuc["kid"] = self.db.sartname_yeni_rev(j, eski, yeni, anahtar=anahtar)
        if self._yaz(_("Yeni rev açılamadı"), yaz):
            self.ac(self.db.indeks("sartname", sonuc["kid"]))

    def kopyala(self, i):
        anahtar = self.db.anahtar("sartname", i)
        ad = self.girdi(_("Kopyala"), _("Yeni şartname adı:"), "")
        if ad is None or (j := self._guncel_indeks(anahtar)) is None:
            return
        kayitlar = self.db.get_sartname()
        self._yaz(_("Kopyalanamadı"),
                  lambda: self.db.add_sartname(S.kopyala(kayitlar, kayitlar[j], ad)))

    def sil(self, i):
        anahtar = self.db.anahtar("sartname", i)
        v = self.db.get_sartname()[i]
        gerekce = ""
        if S.kilitli(v):
            gerekce = self.girdi(_("Kilitli revizyonu sil"),
                                 _("{d} kilitli. Silme gerekçesi:").format(d=S.kayit_adi(v)), "")
            if gerekce is None:
                return
        elif not self._mesaj("soru", _("Sil"),
                             _("{d} taslağı silinsin mi?").format(d=S.kayit_adi(v))):
            return
        # anahtar verildiği için delete_sartname kaydı id ile bulur (indeks kaymış olsa da)
        self._yaz(_("Silinemedi"),
                  lambda: self.db.delete_sartname(i, anahtar=anahtar, gerekce=gerekce))

    def klasoru_ac(self, i):
        """B3: program belgeyi açmaz; kaynak klasörü Gezgin'de açar."""
        yol = self.db.get_sartname()[i]["kaynak_klasor"].strip()
        if not yol:
            self._mesaj("bilgi", _("Kaynak klasör"),
                        _("Bu şartnameye kaynak klasör girilmemiş."))
        elif not os.path.isdir(yol):
            self._mesaj("hata", _("Kaynak klasör"), _("Klasör bulunamadı: {yol}").format(yol=yol))
        elif not self.klasor_ac(yol):
            self._mesaj("hata", _("Kaynak klasör"), _("Klasör açılamadı: {yol}").format(yol=yol))

    # ── tema / dil geçişinde durum taşıma ──────────────────────────
    def durum(self):
        return {"ekran": "editor" if self.currentWidget() is self.editor else "liste",
                "acik": self.acik, "degisti": self.editor.degisti,
                "editor": self.editor.durum(), "arama": self.arama.text()}

    def durumu_yukle(self, d):
        self.arama.setText(d["arama"])
        if d["ekran"] != "editor":
            return
        i = None if d["acik"] is None else self.db.indeks("sartname", d["acik"][0])
        if i is not None:
            # değişiklik yoksa açmak yeter; düzeltme kipi açıksa o da taşınır (Antigravity BULGU-03)
            if not self.ac(i) or not (d["degisti"] or d["editor"]["duzeltme"]):
                return
            if self.editor.salt_okunur and not d["editor"]["duzeltme"]:
                # arada başka cihazda kilitlendi: girdiler kaydedilemez, sessizce atılmasın
                self._mesaj("bilgi", _("Kayıt kilitlendi"),
                            _("Açık şartname başka bir cihazda yürürlüğe alındı ya da revize "
                              "edildi; kaydedilmemiş girdileriniz uygulanamadı. Değişiklik için "
                              "yeni rev açın."))
                return
            self.acik = d["acik"]     # açıldığı sürümle yazılır (arada değiştiyse çakışma)
        else:
            self.yeni()
            if d["acik"] is not None:   # sessizce yeni kayıt olarak eklenmesin
                self._mesaj("bilgi", _("Kayıt silinmiş"),
                            _("Açık kayıt başka bir cihazda silinmiş; girdileriniz yeni kayıt "
                              "olarak açıldı. Kaydederseniz yeni kayıt oluşur."))
        self.editor.durumu_yukle(d["editor"])
        self.editor.degisti = d["degisti"]
