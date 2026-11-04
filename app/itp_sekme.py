# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""ITP / Kalite Planı sekmesi (Plan 5a): kayıtlı siparişlerin listesi + düzenleyici.

Liste → Aç / Yeni → ITPPage (kayıt kipi). Kurallar app/itp/kayit.py'de (Qt'siz); burada
yalnız seçim, diyalog ve veritabanı çağrısı vardır. Diyaloglar (girdi, üç seçenekli soru,
mesaj) testler için enjekte edilebilir. Kayıt kalıcı kimliği (id, sürüm) açılışta alınır:
liste yenilense de aynı kayda, açıldığı sürümle yazılır (2026-10-31 deseni).
"""
from datetime import date

from PyQt6.QtWidgets import (QHBoxLayout, QHeaderView, QInputDialog, QLineEdit, QMessageBox,
                             QPushButton, QStackedWidget, QTableWidget, QTableWidgetItem,
                             QVBoxLayout, QWidget)

from . import kimlik
from .database import CakismaHatasi, VeritabaniHatasi, YetkiHatasi
from .itp import kayit as R
from .itp.goruntu import GoruntuHatasi
from .itp_page import HATALAR, ITPPage, _varsayilan_mesaj
from .search_utils import tr_fold
from .widgets import page_header
from .dil import N_, _

SUTUNLAR = (N_("Doküman No"), N_("Rev"), N_("Müşteri"), N_("Proje"), N_("Sipariş No"), N_("Tarih"), N_("Durum"))
_YAZMA_HATALARI = (R.KayitHatasi, CakismaHatasi, YetkiHatasi, VeritabaniHatasi,
                   GoruntuHatasi) + HATALAR


class ITPSekme(QStackedWidget):
    def __init__(self, db, mesaj=None, girdi=None, uc_secenek=None):
        super().__init__()
        self.db = db
        self._mesaj = mesaj or (lambda tur, b, m: _varsayilan_mesaj(self, tur, b, m))
        self.girdi = girdi or self._qt_girdi
        self.uc_secenek = uc_secenek or self._qt_uc_secenek
        k = db.kullanici
        self.rol = k.rol if k else None
        self.acik = None            # açık kaydın (id, sürüm); None = yeni (kaydedilmemiş)
        self._satir_indeks = []     # tablo satırı → db listesindeki indeks
        self.liste = self._liste_kur()
        self.editor = ITPPage(mesaj=self._mesaj, rol=self.rol, on_kaydet=self._kaydet,
                              on_aktarim=self._aktarim, on_listeye_don=self.listeye_don,
                              firma=db.firma)
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

    # ── yetki ─────────────────────────────────────────────────────
    def _yazabilir(self):
        return self.rol is None or kimlik.yetkili(self.rol, kimlik.DUZENLEYICI)

    # ── liste ──────────────────────────────────────────────────────
    def _liste_kur(self):
        w = QWidget()
        L = QVBoxLayout(w); L.setContentsMargins(24, 20, 24, 16); L.setSpacing(10)
        L.addWidget(page_header(_("ITP / Kalite Planı"),
                                _("Kayıtlı ITP ve Kalite Planları; açın, yeni oluşturun, "
                                "revizyon açın")))
        ust = QHBoxLayout()
        self.arama = QLineEdit(); self.arama.setPlaceholderText(_("Ara (no, müşteri, proje…)"))
        self.arama.textChanged.connect(self._suz)   # liste kısa: anında süz (test de bekler)
        ust.addWidget(self.arama, 1)
        self.btn_yeni = QPushButton(_("+  Yeni")); self.btn_yeni.setObjectName("btn_primary")
        self.btn_ac = QPushButton(_("Aç"))
        self.btn_kopyala = QPushButton(_("Kopyala"))
        self.btn_onay = QPushButton(_("Müşteri onayı"))
        self.btn_yeni_rev = QPushButton(_("Yeni rev"))
        self.btn_sil = QPushButton(_("Sil"))
        self.btn_yeni.clicked.connect(self.yeni)
        for b, fn in ((self.btn_ac, self.ac), (self.btn_kopyala, self.kopyala),
                      (self.btn_onay, self.onayla), (self.btn_yeni_rev, self.yeni_rev),
                      (self.btn_sil, self.sil)):
            b.setObjectName("btn_ghost" if b is not self.btn_ac else "btn_primary")
            b.clicked.connect(lambda _=False, fn=fn: self._secili_ile(fn))
        for b in (self.btn_yeni, self.btn_ac, self.btn_kopyala, self.btn_onay,
                  self.btn_yeni_rev, self.btn_sil):
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
        kayitlar = self.db.get_itp()
        sira = sorted(range(len(kayitlar)),
                      key=lambda i: (tr_fold(kayitlar[i]["no"]), -kayitlar[i]["rev_sira"]))
        self._satir_indeks = sira
        self.tablo.setRowCount(0)
        for i in sira:
            v = kayitlar[i]
            b = v["baslik"]
            r = self.tablo.rowCount()
            self.tablo.insertRow(r)
            for c, metin in enumerate((v["no"], v["rev"], b.get("musteri", ""),
                                       b.get("proje", ""), b.get("siparis_no", ""),
                                       b.get("tarih", ""), R.durum_metni(v))):
                self.tablo.setItem(r, c, QTableWidgetItem(str(metin)))
        self._suz()
        self._dugmeler()

    def _suz(self, *_):
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
        for b in (self.btn_yeni, self.btn_kopyala, self.btn_onay, self.btn_yeni_rev):
            b.setVisible(yaz)
        i = self.secili_indeks()
        v = None if i is None else self.db.get_itp()[i]
        sil_gorunur = yaz and (v is None or v["durum"] == R.TASLAK
                               or self.rol in (None, kimlik.YONETICI))
        self.btn_sil.setVisible(sil_gorunur)
        self.btn_ac.setEnabled(v is not None)
        self.btn_kopyala.setEnabled(v is not None)
        self.btn_onay.setEnabled(v is not None and v["durum"] == R.TASLAK)
        self.btn_yeni_rev.setEnabled(v is not None and R.en_yuksek_mi(self.db.get_itp(), v))
        self.btn_sil.setEnabled(v is not None)

    # ── ekran geçişi ───────────────────────────────────────────────
    def yeni(self):
        self.acik = None
        self.editor.kaydi_yukle(None)
        self.setCurrentWidget(self.editor)

    def ac(self, i):
        anahtar = self.db.anahtar("itp", i)
        try:
            self.editor.kaydi_yukle(self.db.get_itp()[i])
        except _YAZMA_HATALARI as e:
            self._mesaj("hata", _("Açılamadı"), str(e))
            return
        self.acik = anahtar
        self.setCurrentWidget(self.editor)

    def _kaydedilmemis_sor(self):
        """Düzenleyicide kaydedilmemiş değişiklik varsa sorar. Devam edilebilir mi?"""
        if self.currentWidget() is not self.editor or not self.editor.degisti \
                or self.editor.salt_okunur:
            return True
        secim = self.uc_secenek(_("Kaydedilmemiş değişiklik"),
                                _("ITP / Kalite Planı'nda kaydedilmemiş değişiklik var. "
                                "Kaydedilsin mi?"))
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

    def _kaydet(self, girdi):
        kayitlar = self.db.get_itp()

        def yaz():
            if self.acik is None:
                veri = R.kayit_kur(*girdi)
                R.kaydet_kontrol(kayitlar, veri)
                kid = self.db.add_itp(veri)
                self.acik = (kid, 0)
            else:
                i = self.db.indeks("itp", self.acik[0])
                if i is None:
                    raise CakismaHatasi(_("Kayıt başka bir cihazda silinmiş."))
                veri = R.girdileri_guncelle(kayitlar[i], *girdi)
                R.kaydet_kontrol(kayitlar, veri, haric=i)
                self.db.update_itp(i, veri, anahtar=self.acik)
                self.acik = self.db.anahtar("itp", self.db.indeks("itp", self.acik[0]))
        if not self._yaz(_("Kaydedilemedi"), yaz):
            return False
        i = self.db.indeks("itp", self.acik[0])
        self.editor.lbl_kayit.setText(
            _("{d}  Rev.{d2}  ·  Taslak").format(d=self.db.get_itp()[i]['no'], d2=self.db.get_itp()[i]['rev']))
        return True

    def _aktarim(self, dokuman):
        if self.acik is None:
            return
        def yaz():
            i = self.db.indeks("itp", self.acik[0])
            self.db.update_itp(i, R.aktarim_kaydi(self.db.get_itp()[i], dokuman),
                               anahtar=self.acik)
            self.acik = self.db.anahtar("itp", self.db.indeks("itp", self.acik[0]))
        self._yaz(_("Aktarım kayda geçmedi"), yaz)

    def _guncel_indeks(self, anahtar):
        """Diyalogdan sonra: kayıt hâlâ var mı, şimdiki indeksi (liste 3 sn'de yenilenir)."""
        j = self.db.indeks("itp", anahtar[0])
        if j is None:
            self._mesaj("hata", _("Kayıt yok"), _("Kayıt başka bir cihazda silinmiş; liste yenilendi."))
            self.refresh()
        return j

    def onayla(self, i):
        # Kayıt kimliği diyalogdan ÖNCE (CLAUDE.md: indeks diyalog sırasında kayabilir)
        anahtar = self.db.anahtar("itp", i)
        tarih = self.girdi(_("Müşteri onayı"), _("Onay tarihi (GG.AA.YYYY):"),
                           date.today().strftime("%d.%m.%Y"))
        if tarih is None:
            return
        not_ = self.girdi(_("Müşteri onayı"), _("Not (yazı no vb., isteğe bağlı):"), "")
        if not_ is None or (j := self._guncel_indeks(anahtar)) is None:
            return
        k = self.db.kullanici
        self._yaz(_("Onaylanamadı"), lambda: self.db.update_itp(
            j, R.onayla(self.db.get_itp()[j], tarih, not_, k.ad if k else "sistem",
                     self.db.firma().ad),
            anahtar=anahtar))

    def yeni_rev(self, i):
        anahtar = self.db.anahtar("itp", i)
        v = self.db.get_itp()[i]
        rev = None
        if not v["rev"].strip().isdigit():
            rev = self.girdi(_("Yeni rev"), _("Rev '{d}' sayısal değil; yeni rev:").format(d=v['rev']), "")
            if rev is None:
                return
        if (j := self._guncel_indeks(anahtar)) is None:
            return
        sonuc = {}

        def yaz():
            kayitlar = self.db.get_itp()
            eski, yeni = R.yeni_rev(kayitlar, kayitlar[j], rev, firma=self.db.firma().ad)
            # kilitleme + yeni taslak tek işlemde; sürüm açılıştaki (arada değiştiyse çakışma)
            sonuc["kid"] = self.db.itp_yeni_rev(j, eski, yeni, anahtar=anahtar)
        if self._yaz(_("Yeni rev açılamadı"), yaz):
            self.ac(self.db.indeks("itp", sonuc["kid"]))

    def kopyala(self, i):
        anahtar = self.db.anahtar("itp", i)
        no = self.girdi(_("Kopyala"), _("Yeni doküman no:"), "")
        if no is None or (j := self._guncel_indeks(anahtar)) is None:
            return
        kayitlar = self.db.get_itp()
        self._yaz(_("Kopyalanamadı"), lambda: self.db.add_itp(R.kopyala(kayitlar, kayitlar[j], no)))

    def sil(self, i):
        anahtar = self.db.anahtar("itp", i)
        v = self.db.get_itp()[i]
        gerekce = ""
        if R.kilitli(v):
            gerekce = self.girdi(_("Kilitli revizyonu sil"),
                                 _("{d} Rev.{d2} kilitli. Silme gerekçesi:").format(d=v['no'], d2=v['rev']), "")
            if gerekce is None:
                return
        elif not self._mesaj("soru", _("Sil"), _("{d} Rev.{d2} taslağı silinsin mi?").format(d=v['no'], d2=v['rev'])):
            return
        # anahtar verildiği için delete_itp kaydı id ile bulur (indeks kaymış olsa da)
        self._yaz(_("Silinemedi"), lambda: self.db.delete_itp(i, anahtar=anahtar, gerekce=gerekce))

    # ── tema geçişinde durum taşıma (V-4-3) ────────────────────────
    def durum(self):
        return {"ekran": "editor" if self.currentWidget() is self.editor else "liste",
                "acik": self.acik, "degisti": self.editor.degisti,
                "editor": self.editor.durum(), "arama": self.arama.text()}

    def durumu_yukle(self, d):
        self.arama.setText(d["arama"])
        if d["ekran"] != "editor":
            return
        i = None if d["acik"] is None else self.db.indeks("itp", d["acik"][0])
        if i is not None and not d["degisti"]:
            self.ac(i)
            return
        if i is not None:
            self.ac(i)
        else:
            self.yeni()
            if d["acik"] is not None:   # sessizce yeni kayıt olarak eklenmesin
                self._mesaj("bilgi", _("Kayıt silinmiş"),
                            _("Açık kayıt başka bir cihazda silinmiş; girdileriniz yeni kayıt "
                            "olarak açıldı. Kaydederseniz yeni kayıt oluşur."))
        self.acik = d["acik"] if i is not None else None
        self.editor.durumu_yukle(d["editor"])
        self.editor.degisti = d["degisti"]
