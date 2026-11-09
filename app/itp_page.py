# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""
ITP / Kalite Planı sekmesi (Plan 4).

Başlık formu + şablon seçimi + kalem tablosu → app.itp.olustur.olustur → önizleme ağacı →
app.itp.excel.excel_yaz. Kayıt kipinde (Plan 5a; app/itp_sekme.py kurar) girdiler `on_kaydet`
ile veritabanına yazılır; kilitli revizyon ve Okuyucu rolü salt okunurdur (Excel'e aktarma
Okuyucu'ya kapalı, K15).
Hatalar (ValueError / SablonHatasi / EslesmeHatasi) mesaj kutusunda gösterilir; mesaj
fonksiyonu testler için enjekte edilebilir. Girdi değişince eski doküman geçersiz olur
(Excel'e eski önizleme yazılmasın diye aktarma düğmesi kapanır).
"""

import copy
import importlib.util
from datetime import date
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem,
    QMessageBox, QFileDialog, QSplitter, QHeaderView, QMenu, QDialog, QDialogButtonBox,
    QCheckBox, QInputDialog, QPlainTextEdit,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor

from . import dil, kimlik
from .firma import Firma
from .widgets import page_header
from .itp import kayit as itp_kayit
from .itp.aralik import EslesmeHatasi
from .itp.dokuman import (AMACLAR, DIS_KAPLAMALAR, IC_KAPLAMALAR, KALINLIK_SINIFLARI,
                          KAPLAMA_SINIFLARI, PSL_DEGERLERI, Baslik, ElleGirilecek, Kalem, KalemTablosu, Metin)
from .itp.excel import excel_yaz
from .itp.olustur import NumaraOnekiHatasi, olustur
from .itp.sartname import _SATIR_ADI
from .itp.siparis_secim import (NOT_ADI, duzeltme_bul, duzeltme_yaz, hucre_metni, isaret,
                                iz_metni, ozel_temizle, satir_hedefi, secim_kontrol,
                                secim_ozeti, secim_satirlari)
from .itp.uygula import CakismaSorusu, CeviriSorusu, UygulamaHatasi, uygula
from .itp.veri.api5l_47 import MALZEME
from .itp.yer_tutucu import SablonHatasi
from .dil import N_, _

# (görünen ad, olustur şablon kodu)
SABLON_SECENEKLERI = (
    (N_("ITP (EN)"), "itp_en"),
    (N_("Kalite Planı – çıplak boru (TR)"), "kp_ciplak"),
    (N_("Kalite Planı – kaplama (TR)"), "kp_kaplama"),
)

# (Baslik alanı, etiket)
BASLIK_ALANLARI = (
    ("dokuman_no", N_("Doküman No")), ("rev", N_("Rev")), ("idc", N_("IDC")), ("tarih", N_("Tarih")),
    ("musteri", N_("Müşteri")), ("proje", N_("Proje")), ("siparis_no", N_("Sipariş No")),
    ("hazirlayan", N_("Hazırlayan")), ("inceleyen", N_("İnceleyen")), ("onaylayan", N_("Onaylayan")),
)

SUTUNLAR = (N_("No"), N_("PSL"), N_("Kalite"), N_("D (mm)"), N_("t (mm)"), N_("Boy (m)"), N_("Miktar (m)"), N_("Amaç"),
            N_("Dış Kaplama"), N_("Kaplama Sınıfı"), N_("Kalınlık Sınıfı"), N_("İç Kaplama"))
(C_NO, C_PSL, C_KALITE, C_D, C_T, C_BOY, C_MIKTAR, C_AMAC, C_KAPLAMA, C_SINIF, C_KALINLIK,
 C_IC_KAPLAMA) = range(len(SUTUNLAR))
SAYI_SUTUNLARI = {C_D: "D", C_T: "t", C_BOY: "boy", C_MIKTAR: "miktar"}
YOK = "—"   # sınıfı olmayan kaplamada kaplama/kalınlık sınıfı

HATALAR = (ValueError, SablonHatasi, EslesmeHatasi, UygulamaHatasi)
SORU_SINIRI = 50              # bir «Oluştur»da en çok soru (V-5c2-6); 50. cevaptan sonra da denenir
GRI = QColor(128, 128, 128)   # uygulanmaz satır (V-5c2-8)
ORNEK_YOL = Path(__file__).resolve().parent.parent / "tools" / "ornek_cikti.py"

# (menü adı, örnek kodu) — kod → (başlık, kalemler, şablon) _ornek_siparis'te (V-4-5)
ORNEK_SECENEKLERI = (
    (N_("Örnek ITP (EN), 4 kalem"), "kurum_c"),
    (N_("Örnek Kalite Planı, çıplak boru"), "kurum_a"),
    (N_("Örnek Kalite Planı, kaplama"), "kurum_a_kaplama"),
)


def kaliteler(psl):
    """PSL için API 5L 47 malzeme listesindeki kaliteler (veri sırasıyla)."""
    return [m["grade"] for m in MALZEME if m["psl"] == psl]


def _varsayilan_mesaj(parent, tur, baslik, metin):
    """tur "soru" ise Evet/Hayır sorar ve True/False döner."""
    if tur == "soru":
        yanit = QMessageBox.question(parent, baslik, metin)
        return yanit == QMessageBox.StandardButton.Yes
    if tur == "hata":
        QMessageBox.warning(parent, baslik, metin)
    else:
        QMessageBox.information(parent, baslik, metin)


def _ornek_siparis(ad="kurum_c"):
    """tools/ornek_cikti.py'deki örnek sipariş (tek kaynak; kopya tanım yok):
    (başlık, kalemler, şablon kodu)."""
    spec = importlib.util.spec_from_file_location("ornek_cikti", ORNEK_YOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {"kurum_c": (mod.KURUM_C_BASLIK, mod.KURUM_C, "itp_en"),
            "kurum_a": (mod.KURUM_A_BASLIK, mod.KURUM_A, "kp_ciplak"),
            "kurum_a_kaplama": (mod.KURUM_A_BASLIK, mod.KURUM_A_KAPLAMA, "kp_kaplama")}[ad]


class SartnameSecDialog(QDialog):
    """Yürürlükteki şartname revizyonları ve isteğe bağlı grupları (V-5c2-1/2). Seçimde olup
    listede olmayan kayıt (silinmiş / yürürlükte değil) işaretli ve uyarılı görünür, kaldırılabilir."""

    def __init__(self, satirlar, secim, parent=None, adlar=None):
        """adlar: listede olmayan seçili kaydın adı (yürürlükte değil); silinmişse yok."""
        super().__init__(parent)
        self.setWindowTitle(_("Şartnameler"))
        self.setMinimumWidth(620)
        L = QVBoxLayout(self)
        L.addWidget(QLabel(_("Siparişe uygulanacak şartnameler (yalnız yürürlükteki revizyonlar). "
                             "İsteğe bağlı grupları ayrıca işaretleyin.")))
        self.agac = QTreeWidget()
        self.agac.setHeaderHidden(True)
        secili = {s["id"]: set(s["gruplar"]) for s in secim}
        bilinen = {s["id"] for s in satirlar}
        for s in satirlar:
            metin = f"{s['etiket']}  ·  {_('özel teknik') if s['tur'] == 'ozel' else _('genel')}"
            if s["yeni_rev"]:
                metin += "  " + _("⚠ daha yeni: {rev}").format(rev=s["yeni_rev"])
            oge = self._oge(self.agac, metin, s["id"], s["id"] in secili)
            for gid, ad in s["gruplar"]:
                ad_metni = ad.get(dil.etkin(), "") or ad.get("tr", "") or gid
                self._oge(oge, _("Grup: {ad}").format(ad=ad_metni), gid,
                          gid in secili.get(s["id"], ()))
            oge.setExpanded(True)
        for s in [s for s in secim if s["id"] not in bilinen]:   # doğrulama D-6
            ad = (adlar or {}).get(s["id"])
            metin = (_("{ad} (yürürlükte değil)").format(ad=ad) if ad else
                     _("(kayıt {id} bulunamadı ya da yürürlükte değil)").format(id=s["id"]))
            oge = self._oge(self.agac, metin, s["id"], True)
            oge.setData(0, Qt.ItemDataRole.UserRole + 1, list(s["gruplar"]))
        L.addWidget(self.agac, 1)
        self.chk_temizle = QCheckBox(_("Sipariş kararlarını (çakışma cevaplarını) temizle"))
        L.addWidget(self.chk_temizle)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        L.addWidget(bb)

    @staticmethod
    def _oge(ust, metin, veri, isaretli):
        oge = QTreeWidgetItem(ust, [metin])
        oge.setData(0, Qt.ItemDataRole.UserRole, veri)
        oge.setCheckState(0, Qt.CheckState.Checked if isaretli else Qt.CheckState.Unchecked)
        return oge

    def sonuc(self):
        secim = []
        for i in range(self.agac.topLevelItemCount()):
            oge = self.agac.topLevelItem(i)
            if oge.checkState(0) == Qt.CheckState.Checked:
                saklanan = oge.data(0, Qt.ItemDataRole.UserRole + 1)   # listede olmayan kayıt
                secim.append({"id": oge.data(0, Qt.ItemDataRole.UserRole),
                              "gruplar": list(saklanan) if saklanan is not None else
                              [oge.child(j).data(0, Qt.ItemDataRole.UserRole)
                               for j in range(oge.childCount())
                               if oge.child(j).checkState(0) == Qt.CheckState.Checked]})
        return secim, self.chk_temizle.isChecked()


# karakteristik düzeltilmez: satır hedefinin anahtarıdır (5c-3 doğrulama YÜKSEK-1, V-5c3-7)
DUZELTME_SUTUNLARI = ("kabul", "frekans", "sorumlu", "kayit", "denetim")


class HucreDuzeltDialog(QDialog):
    """Önizlemedeki satırın bir hücresini düzeltir (Plan 5c-3, V-5c3-1). mevcut: {sütun: bu satırın
    önceki düzeltme metni}. sonuc: (sütun, metin) ya da (sütun, None) = düzeltmeyi kaldır."""

    def __init__(self, satir, mevcut, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Hücreyi düzelt"))
        self.setMinimumWidth(560)
        self._satir, self._mevcut, self.sonuc = satir, mevcut, None
        L = QVBoxLayout(self)
        L.addWidget(QLabel(_("Satır: {k}").format(k=satir.karakteristik or satir.aktivite)))
        self.cmb_sutun = QComboBox()
        for s in DUZELTME_SUTUNLARI:
            self.cmb_sutun.addItem(_(_SATIR_ADI[s]), s)
        L.addWidget(self.cmb_sutun)
        self.ed_metin = QPlainTextEdit()
        L.addWidget(self.ed_metin, 1)
        L.addWidget(QLabel(_("Düzeltme bu siparişe kaydedilir ve yeniden oluşturmada uygulanır. "
                             "Kabul kriterinde atıf korunur; tablolar yazdığınız metinle değişir.")))
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        self.btn_kaldir = bb.addButton(_("Düzeltmeyi kaldır"), QDialogButtonBox.ButtonRole.ResetRole)
        bb.accepted.connect(self._tamam)
        bb.rejected.connect(self.reject)
        self.btn_kaldir.clicked.connect(self._kaldir)
        self.lbl_uyari = QLabel(); self.lbl_uyari.setWordWrap(True)
        L.addWidget(self.lbl_uyari)
        L.addWidget(bb)
        self.cmb_sutun.currentIndexChanged.connect(self._sutun_degisti)
        self._sutun_degisti()

    def _sutun_degisti(self, *__):
        s = self.cmb_sutun.currentData()
        self._ilk = self._mevcut.get(s, hucre_metni(self._satir, s))
        self.ed_metin.setPlainText(self._ilk)
        self.btn_kaldir.setEnabled(s in self._mevcut)
        self.lbl_uyari.setText("")

    def _tamam(self):
        metin = self.ed_metin.toPlainText().strip()
        if metin == self._ilk.strip():        # değişiklik yok: düzeltme yazılmaz (ORTA-3)
            self.reject()
            return
        if not metin:
            self.lbl_uyari.setText(_("Metin boş. Düzeltmeyi silmek için «Düzeltmeyi kaldır»."))
            return
        if _("[tablo]") in metin:
            self.lbl_uyari.setText(_("Metinde «[tablo]» yer tutucusu var: tablo bu metinle "
                                     "değişir. Yer tutucuyu silip yerine yazılacak metni girin."))
            return
        self.sonuc = (self.cmb_sutun.currentData(), metin)
        self.accept()

    def _kaldir(self):
        self.sonuc = (self.cmb_sutun.currentData(), None)
        self.accept()


class ITPPage(QWidget):
    def __init__(self, mesaj=None, rol=None, on_kaydet=None, on_aktarim=None,
                 on_listeye_don=None, firma=None, sartname_kayitlari=None):
        super().__init__()
        # sartname_kayitlari(): {id: şartname kaydı} (5c-2); verilmezse şartname satırı gizli
        self._sartname_kayitlari = sartname_kayitlari
        self.secim, self.siparis_ozel = [], []
        # firma(): ayardaki Firma (ad + logo); verilmezse ad boş → Oluştur "ayarlanmamış" der
        self._firma = firma or (lambda: Firma(""))
        # mesaj(tur, baslik, metin): tur "hata" | "bilgi"
        self._mesaj = mesaj or (lambda tur, b, m: _varsayilan_mesaj(self, tur, b, m))
        self.rol = rol                    # None = kullanıcısız (araç/test): tam yetki
        self.on_kaydet, self.on_aktarim = on_kaydet, on_aktarim
        self.on_listeye_don = on_listeye_don
        self.dokuman = None
        self.onek_duzelt = False          # kullanıcı numara düzeltmesini onayladı mı (kayda geçer)
        self.degisti = False
        self.salt_okunur = False
        self._kilitli_kayit = False
        self._yukleniyor = False
        self._build()
        self.satir_ekle()
        self._gecersiz_kil()
        self.degisti = False
        self._dugmeleri_ayarla()

    def _yazabilir(self):
        return self.rol is None or kimlik.yetkili(self.rol, kimlik.DUZENLEYICI)

    # ── arayüz ───────────────────────────────────────────────────
    def _build(self):
        L = QVBoxLayout(self); L.setContentsMargins(24, 20, 24, 16); L.setSpacing(10)
        L.addWidget(page_header(_("ITP / Kalite Planı"),
                                _("Sipariş kalemlerinden ITP veya Kalite Planı oluşturun, "
                                "önizleyin ve Excel'e aktarın")))

        ust = QHBoxLayout()
        self.btn_liste = QPushButton(_("←  Listeye dön")); self.btn_liste.setObjectName("btn_ghost")
        self.btn_liste.clicked.connect(lambda: self.on_listeye_don and self.on_listeye_don())
        self.lbl_kayit = QLabel("")
        self.btn_kaydet = QPushButton(_("Kaydet")); self.btn_kaydet.setObjectName("btn_primary")
        self.btn_kaydet.clicked.connect(self.kaydet)
        ust.addWidget(self.btn_liste); ust.addWidget(self.lbl_kayit); ust.addStretch()
        ust.addWidget(self.btn_kaydet)
        L.addLayout(ust)

        grid = QGridLayout(); grid.setHorizontalSpacing(10); grid.setVerticalSpacing(6)
        self.alanlar = {}
        for i, (ad, etiket) in enumerate(BASLIK_ALANLARI):
            ed = QLineEdit(); ed.setPlaceholderText(_(etiket))
            if ad == "tarih":
                ed.setText(date.today().strftime("%d.%m.%Y"))
            ed.textChanged.connect(self._gecersiz_kil)
            r, c = divmod(i, 5)
            grid.addWidget(QLabel(_(etiket)), r * 2, c)
            grid.addWidget(ed, r * 2 + 1, c)
            self.alanlar[ad] = ed
        L.addLayout(grid)

        tb = QHBoxLayout()
        tb.addWidget(QLabel(_("Şablon:")))
        self.cmb_sablon = QComboBox()
        for ad, kod in SABLON_SECENEKLERI:
            self.cmb_sablon.addItem(_(ad), kod)
        self.cmb_sablon.currentIndexChanged.connect(self._gecersiz_kil)
        tb.addWidget(self.cmb_sablon)
        self.btn_sartname = QPushButton(_("Şartnameler…")); self.btn_sartname.setObjectName("btn_ghost")
        self.btn_sartname.clicked.connect(self.sartname_sec)
        self.lbl_sartname = QLabel()
        tb.addWidget(self.btn_sartname); tb.addWidget(self.lbl_sartname)
        tb.addStretch()
        self.btn_ekle = QPushButton(_("+  Satır ekle")); self.btn_ekle.setObjectName("btn_ghost")
        self.btn_ekle.clicked.connect(lambda: self.satir_ekle())
        self.btn_sil = QPushButton(_("Satır sil")); self.btn_sil.setObjectName("btn_ghost")
        self.btn_sil.clicked.connect(self.satir_sil)
        self.btn_ornek = QPushButton(_("Örnek sipariş yükle"))
        self.btn_ornek.setObjectName("btn_ghost")
        menu = QMenu(self.btn_ornek)
        for ad, kod in ORNEK_SECENEKLERI:
            menu.addAction(_(ad), lambda kod=kod: self.ornek_yukle(kod))
        self.btn_ornek.setMenu(menu)
        self.btn_olustur = QPushButton(_("Oluştur")); self.btn_olustur.setObjectName("btn_primary")
        self.btn_olustur.clicked.connect(self.olustur)
        self.btn_excel = QPushButton(_("Excel'e aktar")); self.btn_excel.setObjectName("btn_primary")
        self.btn_excel.clicked.connect(self.excel_aktar)
        self.btn_duzelt = QPushButton(_("Hücreyi düzelt…")); self.btn_duzelt.setObjectName("btn_ghost")
        self.btn_duzelt.clicked.connect(self.hucre_duzelt)
        for b in (self.btn_ekle, self.btn_sil, self.btn_ornek, self.btn_olustur, self.btn_duzelt,
                  self.btn_excel):
            tb.addWidget(b)
        L.addLayout(tb)

        self.table = QTableWidget(0, len(SUTUNLAR))
        self.table.setHorizontalHeaderLabels([_(x) for x in SUTUNLAR])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)   # hücre içi combobox'lar için
        # Tema form dolgusu (8px 13px) hücreye sığmıyor; tablo içi combobox'lar sıkı dolgulu
        self.table.setStyleSheet("QComboBox { padding: 2px 8px; border-radius: 6px; }")
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        # son sütun esnemez: tam ekranda İç Kaplama boşluğu doldurup aşırı genişliyordu
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.itemChanged.connect(self._gecersiz_kil)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels([_("No"), _("Bölüm / Karakteristik"), _("Kabul kriteri")])
        self.tree.setColumnWidth(0, 90); self.tree.setColumnWidth(1, 380)
        self.tree.currentItemChanged.connect(self._duzelt_durumu)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._agac_menusu)

        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(self.table); split.addWidget(self.tree)
        split.setSizes([260, 340])
        L.addWidget(split, 1)

        self.lbl_durum = QLabel(); self.lbl_durum.setWordWrap(True)
        L.addWidget(self.lbl_durum)

    # ── kalem tablosu ────────────────────────────────────────────
    def _combo(self, degerler, secili=None):
        """secili listede yoksa ValueError (sessizce ilk öğeye düşülmez)."""
        cb = QComboBox()
        for v in degerler:   # gösterim çevrilir, veri (kayda giden) Türkçe kalır (dil D3)
            cb.addItem(dil.deger(str(v)), str(v))
        if secili is not None:
            if str(secili) not in [str(v) for v in degerler]:
                raise ValueError(_("'{secili}' değeri listede yok: {d}").format(secili=secili, d=list(degerler)))
            cb.setCurrentIndex(cb.findData(str(secili)))
        cb.currentIndexChanged.connect(self._gecersiz_kil)
        return cb

    def satir_ekle(self, kalem=None):
        """Boş (varsayılan) ya da verilen Kalem ile dolu satır ekler."""
        r = self.table.rowCount()
        self._yukleniyor = True
        try:
            self.table.insertRow(r)
            no = kalem.no if kalem else self._sonraki_no()
            self.table.setItem(r, C_NO, QTableWidgetItem(str(no)))
            psl = kalem.psl if kalem else PSL_DEGERLERI[-1]
            cb_psl = self._combo(PSL_DEGERLERI, psl)
            self.table.setCellWidget(r, C_PSL, cb_psl)
            self.table.setCellWidget(r, C_KALITE,
                                     self._combo(kaliteler(psl), kalem.grade if kalem else None))
            cb_psl.currentTextChanged.connect(lambda _t, cb=cb_psl: self._psl_degisti(cb))
            for c, alan in ((C_D, "D"), (C_T, "t"), (C_BOY, "boy_m"), (C_MIKTAR, "miktar_m")):
                v = getattr(kalem, alan) if kalem else ""
                self.table.setItem(r, c, QTableWidgetItem(format(v, ".15g") if kalem else ""))
            self.table.setCellWidget(r, C_AMAC, self._combo(AMACLAR, kalem.amac if kalem else None))
            cb_k = self._combo(DIS_KAPLAMALAR, kalem.dis_kaplama if kalem else None)
            self.table.setCellWidget(r, C_KAPLAMA, cb_k)
            cb_k.currentTextChanged.connect(lambda _t, cb=cb_k: self._kaplama_degisti(cb))
            self._siniflari_doldur(r, kalem)
            cb_ic = self._combo(IC_KAPLAMALAR, kalem.ic_kaplama if kalem else None)
            cb_ic.setEnabled(len(IC_KAPLAMALAR) > 1)   # V1 yalnız "çıplak"; seçenekler Plan 7
            self.table.setCellWidget(r, C_IC_KAPLAMA, cb_ic)
        except Exception:
            self.table.removeRow(r)   # yarım satır kalmasın
            raise
        finally:
            self._yukleniyor = False
        self._sutun_genislikleri()
        self._gecersiz_kil()

    def showEvent(self, e):
        super().showEvent(e)
        self._sutun_genislikleri()   # tema yazı tipi/QSS gösterilince oturur; yeniden ölç

    def _sonraki_no(self):
        """Mevcut kalem numaralarının en büyüğü + 1 (satır silinince çakışma olmasın)."""
        sayilar = []
        for r in range(self.table.rowCount()):
            it = self.table.item(r, C_NO)
            try:
                sayilar.append(int((it.text() if it else "").strip()))
            except ValueError:
                pass
        return max(sayilar, default=0) + 1

    def _sutun_genislikleri(self):
        """Hücre içi combobox'lar tam okunsun: sütun = max(başlık, combobox sizeHint)."""
        h = self.table.horizontalHeader()
        for c in range(self.table.columnCount()):
            w = h.fontMetrics().horizontalAdvance(_(SUTUNLAR[c])) + 28
            for r in range(self.table.rowCount()):
                cw = self.table.cellWidget(r, c)
                if cw is not None:
                    w = max(w, cw.sizeHint().width() + 16)
                    if isinstance(cw, QComboBox):   # tema dolgusu + ok: metin + 80 px
                        fm = cw.fontMetrics()
                        w = max(w, 80 + max((fm.horizontalAdvance(cw.itemText(i))
                                             for i in range(cw.count())), default=0))
            self.table.setColumnWidth(c, max(w, 70))

    def _satir_bul(self, widget, sutun):
        for r in range(self.table.rowCount()):
            if self.table.cellWidget(r, sutun) is widget:
                return r
        return -1

    def _psl_degisti(self, cb_psl):
        r = self._satir_bul(cb_psl, C_PSL)
        if r < 0:
            return
        eski = self.table.cellWidget(r, C_KALITE).currentData()
        liste = kaliteler(cb_psl.currentData())
        # elle PSL değişiminde eski kalite yeni listede yoksa ilk kaliteye düşmek serbest
        self.table.setCellWidget(r, C_KALITE, self._combo(liste, eski if eski in liste else None))
        self._sutun_genislikleri()
        self._gecersiz_kil()

    def _kaplama_degisti(self, cb_k):
        r = self._satir_bul(cb_k, C_KAPLAMA)
        if r >= 0:
            self._siniflari_doldur(r, None)
            self._sutun_genislikleri()
            self._gecersiz_kil()

    def _siniflari_doldur(self, r, kalem):
        """Kaplama/kalınlık sınıfı seçenekleri dış kaplamaya göre (ISO 21809-1)."""
        kaplama = self.table.cellWidget(r, C_KAPLAMA).currentData()
        siniflar = KAPLAMA_SINIFLARI.get(kaplama)
        if siniflar is None:
            cb_s, cb_t = self._combo([YOK]), self._combo([YOK])
            cb_s.setEnabled(False); cb_t.setEnabled(False)
        else:
            cb_s = self._combo(siniflar, kalem.kaplama_sinifi if kalem else None)
            cb_t = self._combo(KALINLIK_SINIFLARI, kalem.kalinlik_sinifi if kalem else None)
        self.table.setCellWidget(r, C_SINIF, cb_s)
        self.table.setCellWidget(r, C_KALINLIK, cb_t)

    def satir_sil(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        if not rows:   # V-4-4: seçim yoksa son satır sessizce silinmez
            self._mesaj("bilgi", _("Satır sil"), _("Silmek için önce tabloda satır seçin."))
            return
        for r in rows:
            self.table.removeRow(r)
        self._gecersiz_kil()

    def ornek_yukle(self, ad="kurum_c"):
        try:
            baslik, kalemler, sablon = _ornek_siparis(ad)
        except Exception as e:  # dosya yok / bozuk: sessiz geçme
            self._mesaj("hata", _("Örnek sipariş"), _("Örnek sipariş yüklenemedi: {e}").format(e=e))
            return
        for alan, ed in self.alanlar.items():
            ed.setText(str(getattr(baslik, alan)))
        self.cmb_sablon.setCurrentIndex(self.cmb_sablon.findData(sablon))
        self.table.setRowCount(0)
        try:
            for k in kalemler:
                self.satir_ekle(k)
        except ValueError as e:   # örnekteki değer combo listesinde yok: sessiz düşme
            self._mesaj("hata", _("Örnek sipariş"), _("Örnek sipariş yüklenemedi: {e}").format(e=e))
        self._gecersiz_kil()

    # ── kayıt kipi (Plan 5a) ─────────────────────────────────────
    def _dugmeleri_ayarla(self):
        kayit_kipi = self.on_kaydet is not None
        yaz = self._yazabilir() and not self._kilitli_kayit
        self.salt_okunur = not yaz
        self.btn_liste.setVisible(self.on_listeye_don is not None)
        self.btn_kaydet.setVisible(kayit_kipi and yaz)
        for b in (self.btn_ekle, self.btn_sil, self.btn_ornek, self.btn_olustur, self.btn_duzelt):
            b.setVisible(yaz)
        self.btn_excel.setVisible(self._yazabilir())          # K15: Okuyucu aktaramaz
        kayitli = self._sartname_kayitlari is not None
        self.btn_sartname.setVisible(kayitli)
        self.lbl_sartname.setVisible(kayitli)
        self.btn_sartname.setEnabled(yaz)                      # kilitli / okuyucu (V-5c2-10)
        for ed in self.alanlar.values():
            ed.setReadOnly(not yaz)
        self.cmb_sablon.setEnabled(yaz)
        self.table.setEditTriggers(QTableWidget.EditTrigger.AllEditTriggers if yaz
                                   else QTableWidget.EditTrigger.NoEditTriggers)
        if not yaz:
            for r in range(self.table.rowCount()):
                for c in range(len(SUTUNLAR)):
                    w = self.table.cellWidget(r, c)
                    if w is not None:
                        w.setEnabled(False)

    def girdi_verisi(self):
        return (self.cmb_sablon.currentData(), self.baslik_oku(), self.kalemleri_oku(),
                self.onek_duzelt)

    def kaydi_yukle(self, veri, olustur=True):
        """veri None: yeni boş form. Taslak güncel kodla oluşturulur; kilitli kayıt görüntüden.
        olustur=False: taslakta oluşturma atlanır (tema geçişinde doküman durumdan gelir; 5c-2
        doğrulama O-2: kaydedilmemiş cevaplar yeniden sorulmasın)."""
        self._yukleniyor = True
        try:
            self._kilitli_kayit = veri is not None and itp_kayit.kilitli(veri)
            self.table.setRowCount(0)
            self.secim = [] if veri is None else list(veri.get("sartnameler", []))
            self.siparis_ozel = [] if veri is None else list(veri["siparis_ozel"])
            self._ozeti_guncelle()
            if veri is None:
                for ad, ed in self.alanlar.items():
                    ed.setText(date.today().strftime("%d.%m.%Y") if ad == "tarih" else "")
                self.cmb_sablon.setCurrentIndex(0)
                self.onek_duzelt = False
                self.satir_ekle()
                self.lbl_kayit.setText(_("Yeni kayıt"))
            else:
                sablon, baslik, kalemler, onek = itp_kayit.girdiler(veri)
                for ad, ed in self.alanlar.items():
                    ed.setText(str(getattr(baslik, ad)))
                self.cmb_sablon.setCurrentIndex(self.cmb_sablon.findData(sablon))
                self.onek_duzelt = onek
                for k in kalemler:
                    self.satir_ekle(k)
                self.lbl_kayit.setText(_("{d}  Rev.{d2}  ·  {d3}").format(d=veri['no'], d2=veri['rev'], d3=itp_kayit.durum_metni(veri)))
        finally:
            self._yukleniyor = False
        self._gecersiz_kil()
        self._dugmeleri_ayarla()
        self.degisti = False
        if veri is not None:
            if self._kilitli_kayit:
                self.dokuman = itp_kayit.dokuman_uret(veri, self._firma().ad)
                self._onizle(self.dokuman)
                self.btn_excel.setEnabled(True)
            elif olustur:
                self.olustur()   # numara düzeltmesi burada onaylanırsa degisti olur

    def kaydet(self):
        if self.on_kaydet is None or self.salt_okunur:
            return False
        try:
            girdi = self.girdi_verisi()
        except HATALAR as e:
            self._mesaj("hata", _("Kaydedilemedi"), str(e))
            return False
        if self.on_kaydet(girdi):
            self.degisti = False
            return True
        return False

    # ── okuma ────────────────────────────────────────────────────
    def _sayi(self, r, c, ad):
        it = self.table.item(r, c)
        metin = (it.text() if it else "").strip().replace(",", ".")
        if not metin:
            raise ValueError(_("Satır {d}: {ad} boş").format(d=r + 1, ad=ad))
        try:
            return float(metin)
        except ValueError:
            raise ValueError(_("Satır {d}: {ad} sayı değil ('{metin}')").format(d=r + 1, ad=ad, metin=metin)) from None

    def kalemleri_oku(self):
        kalemler = []
        for r in range(self.table.rowCount()):
            it = self.table.item(r, C_NO)
            no_metni = (it.text() if it else "").strip()
            try:
                no = int(no_metni)
            except ValueError:
                raise ValueError(_("Satır {d}: kalem no tam sayı olmalı ('{no_metni}')").format(d=r + 1, no_metni=no_metni)) \
                    from None
            sinif = self.table.cellWidget(r, C_SINIF).currentData()
            kalinlik = self.table.cellWidget(r, C_KALINLIK).currentData()
            kalemler.append(Kalem(
                no=no,
                psl=self.table.cellWidget(r, C_PSL).currentData(),
                grade=self.table.cellWidget(r, C_KALITE).currentData(),
                D=self._sayi(r, C_D, "D"), t=self._sayi(r, C_T, "t"),
                boy_m=self._sayi(r, C_BOY, "boy"), miktar_m=self._sayi(r, C_MIKTAR, "miktar"),
                amac=self.table.cellWidget(r, C_AMAC).currentData(),
                dis_kaplama=self.table.cellWidget(r, C_KAPLAMA).currentData(),
                ic_kaplama=self.table.cellWidget(r, C_IC_KAPLAMA).currentData(),
                kaplama_sinifi=None if sinif == YOK else sinif,
                kalinlik_sinifi=None if kalinlik == YOK else int(kalinlik)))
        return kalemler

    def baslik_oku(self):
        return Baslik(**{ad: ed.text().strip() for ad, ed in self.alanlar.items()})

    # ── durum (tema değişiminde yeniden kurulan sayfaya taşıma; BULGU-05 / V-4-3) ──
    def durum(self):
        """Girdilerin ham hali (yarım/hatalı hücreler dahil) + oluşturulmuş doküman."""
        satirlar = []
        for r in range(self.table.rowCount()):
            satir = []
            for c in range(len(SUTUNLAR)):
                w = self.table.cellWidget(r, c)
                it = self.table.item(r, c)
                satir.append(w.currentData() if w is not None else (it.text() if it else ""))
            satirlar.append(satir)
        return {"baslik": {ad: ed.text() for ad, ed in self.alanlar.items()},
                "sablon": self.cmb_sablon.currentData(), "satirlar": satirlar,
                "dokuman": self.dokuman, "onek_duzelt": self.onek_duzelt,
                "secim": list(self.secim), "siparis_ozel": list(self.siparis_ozel)}

    def durumu_yukle(self, d):
        self.secim = list(d.get("secim", []))
        self.siparis_ozel = list(d.get("siparis_ozel", []))
        self._ozeti_guncelle()
        for ad, metin in d["baslik"].items():
            self.alanlar[ad].setText(metin)
        self.cmb_sablon.setCurrentIndex(self.cmb_sablon.findData(d["sablon"]))
        self.table.setRowCount(0)
        for degerler in d["satirlar"]:
            self.satir_ekle()
            r = self.table.rowCount() - 1
            # PSL kalite listesini, dış kaplama sınıf combolarını yeniden kurar: önce onlar
            for c in (C_PSL, C_KALITE, C_AMAC, C_KAPLAMA, C_SINIF, C_KALINLIK, C_IC_KAPLAMA):
                cb = self.table.cellWidget(r, c)
                if (i := cb.findData(degerler[c])) >= 0:
                    cb.setCurrentIndex(i)
            for c in (C_NO, C_D, C_T, C_BOY, C_MIKTAR):
                self.table.item(r, c).setText(degerler[c])
        self._sutun_genislikleri()
        if d["dokuman"] is not None:   # girdiler aynı: oluşturulmuş doküman geçerli kalır
            self._onizle(d["dokuman"])
            self.dokuman = d["dokuman"]
            self.btn_excel.setEnabled(True)
        self.onek_duzelt = d.get("onek_duzelt", False)

    # ── oluştur / önizleme ───────────────────────────────────────
    def _gecersiz_kil(self, *__):
        if self._yukleniyor:
            return
        self.degisti = True
        self.dokuman = None
        self.btn_excel.setEnabled(False)
        self.tree.clear()
        self._duzelt_durumu()
        self.lbl_durum.setText(_("Girdileri doldurup «Oluştur»a basın."))

    def olustur(self):
        # başarısız / vazgeçilen oluşturma hiçbir şeyi değiştirmez (Antigravity 5c-2 BULGU-04)
        yedek = (copy.deepcopy(self.siparis_ozel), self.degisti, self.onek_duzelt)
        try:
            girdi = (self.cmb_sablon.currentData(), self.baslik_oku(), self.kalemleri_oku())
            try:
                dokuman = olustur(*girdi, onek_duzelt=self.onek_duzelt, firma=self._firma().ad)
            except NumaraOnekiHatasi as e:   # V-5: uyar, düzeltmeyi kullanıcı onaylasın
                soru = (_("Şablonda satır numarası bulunduğu bölüme uymuyor:\n\n")
                        + "\n".join(e.sorunlar)
                        + _("\n\nNumaralar bulundukları bölüme göre düzeltilsin mi?"))
                if self.salt_okunur or not self._mesaj("soru", _("Numara uyumsuzluğu"), soru):
                    raise                    # Okuyucuya soru sorulmaz (BULGU-01)
                dokuman = olustur(*girdi, onek_duzelt=True, firma=self._firma().ad)
                self.onek_duzelt = True
                self.degisti = True   # onay kayda geçmeli (kaydedilmemiş değişiklik)
            dokuman = self._sartname_uygula(dokuman)
        except HATALAR as e:
            self.siparis_ozel, self.degisti, self.onek_duzelt = yedek
            self.dokuman = None
            self.btn_excel.setEnabled(False)
            self.tree.clear()
            self._duzelt_durumu()
            self.lbl_durum.setText(_("Hata: {e}").format(e=e))
            self._mesaj("hata", _("Oluşturulamadı"), str(e))
            return None
        self._onizle(dokuman)
        self.dokuman = dokuman
        self.btn_excel.setEnabled(True)
        return dokuman

    # ── şartnameler (Plan 5c-2) ──────────────────────────────────
    def _kayitlar(self):
        return self._sartname_kayitlari() if self._sartname_kayitlari is not None else {}

    def _ozeti_guncelle(self):
        if self._sartname_kayitlari is None:
            return
        self.lbl_sartname.setText(secim_ozeti(self.secim, self._kayitlar())
                                  or _("Şartname seçilmedi"))

    def _sartname_sec(self, satirlar, secim):
        """Seçim penceresi; (seçim, kararları temizle) ya da vazgeçilirse None. Testler değiştirir."""
        kayitlar = self._kayitlar()
        adlar = {s["id"]: f"{kayitlar[s['id']]['ad']} Rev. {kayitlar[s['id']]['rev']}"
                 for s in secim if s["id"] in kayitlar}
        d = SartnameSecDialog(satirlar, secim, self, adlar)
        return d.sonuc() if d.exec() else None

    def sartname_sec(self):
        if self._sartname_kayitlari is None or self.salt_okunur:
            return
        kayitlar = self._kayitlar()
        mevcut = self.secim
        while True:                                   # hatada pencere işaretlerle yeniden (D-7)
            sonuc = self._sartname_sec(secim_satirlari(kayitlar), mevcut)
            if sonuc is None:
                return
            secim, temizle = sonuc
            try:
                secim_kontrol(secim, kayitlar)
                break
            except UygulamaHatasi as e:
                self._mesaj("hata", _("Şartnameler"), str(e))
                mevcut = secim
        ozel = ozel_temizle(self.siparis_ozel, secim, temizle)
        if secim == self.secim and ozel == self.siparis_ozel:   # değişiklik yok (D-8)
            return
        self.secim, self.siparis_ozel = secim, ozel
        self._ozeti_guncelle()
        self._gecersiz_kil()

    def _cakisma_sor(self, soru):
        """Çakışma sorusu (V-5c2-4): seçilen ya da yazılan metin; vazgeçilirse None."""
        kendi = _("Kendi metnim…")
        secenekler = [f"{e} {k}: {x}" for e, k, x in soru.adaylar] + [kendi]
        secim, ok = QInputDialog.getItem(self, _("Şartnameler çelişiyor"), str(soru),
                                         secenekler, 0, False)
        if not ok:
            return None
        if secim != kendi:
            return soru.adaylar[secenekler.index(secim)][2]
        metin, ok = QInputDialog.getMultiLineText(self, _("Şartnameler çelişiyor"),
                                                  _("Bu siparişte yazılacak metin:"))
        return metin.strip() if ok and metin.strip() else None

    def _ceviri_sor(self, soru):
        """Çeviri sorusu (V-5c2-5): doküman dilindeki metin; vazgeçilirse None."""
        metin, ok = QInputDialog.getMultiLineText(
            self, _("Eksik çeviri"), _("{s}\n\nBu dokümanın dilindeki metin:").format(s=soru),
            soru.diger)
        return metin.strip() if ok and metin.strip() else None

    def _sartname_uygula(self, dokuman):
        """5c-1 motoru; soruları sorar, cevapları siparis_ozel'e yazar (V-5c2-4/5/6)."""
        # sipariş kararları / düzeltmeler kayıtsız kipte de uygulanır (V-5c3-5)
        if not ((self._sartname_kayitlari is not None and self.secim) or self.siparis_ozel):
            return dokuman
        kayitlar = self._kayitlar()
        diger = "en" if dokuman.dil == "tr" else "tr"
        if self.salt_okunur:            # Okuyucu yalnız görüntüler; soru sorulmaz (BULGU-01)
            try:
                return uygula(dokuman, self.secim, kayitlar, self.siparis_ozel)
            except (CakismaSorusu, CeviriSorusu) as e:
                raise UygulamaHatasi(_("Cevaplanmamış şartname sorusu var ({s}); kaydı açıp "
                                       "«Oluştur»da cevaplayın.").format(s=e)) from None
        for __ in range(SORU_SINIRI + 1):
            try:
                return uygula(dokuman, self.secim, kayitlar, self.siparis_ozel)
            except CakismaSorusu as e:
                soru, cevap = e, self._cakisma_sor(e)
                if cevap is None:
                    raise UygulamaHatasi(_("Çakışma cevaplanmadı; doküman oluşturulmadı.")) from None
                madde = None
            except CeviriSorusu as e:
                soru, cevap = e, self._ceviri_sor(e)
                if cevap is None:
                    raise UygulamaHatasi(_("Çeviri girilmedi; doküman oluşturulmadı.")) from None
                madde = soru.madde
            self.degisti = True
            if madde == [None, ""]:          # sipariş kararının eksik dili: karara yazılır (O-1)
                hedef = getattr(soru, "hedef", None)          # 5c-3: satır düzeltmesi
                self.siparis_ozel = [
                    dict(o, metin=dict(o["metin"], **{dokuman.dil: cevap}))
                    if (o.get("madde") is None and o["kontrol"] == soru.kontrol
                        and o["sutun"] == soru.sutun
                        and ((o.get("satir"), o.get("sira")) == hedef if hedef
                             else "satir" not in o)) else o for o in self.siparis_ozel]
                continue
            if madde is None:            # aynı hücrenin eski kararı atılır (BULGU-02)
                self.siparis_ozel = [o for o in self.siparis_ozel if not (
                    o.get("madde") is None and "satir" not in o and o["kontrol"] == soru.kontrol
                    and o["sutun"] == soru.sutun)]
            else:                        # aynı maddenin çevirisi varsa ona yazılır (BULGU-03)
                var = next((o for o in self.siparis_ozel
                            if o.get("madde") == madde and o["sutun"] == soru.sutun), None)
                if var is not None:
                    var["metin"] = dict(var["metin"], **{dokuman.dil: cevap})
                    continue
            self.siparis_ozel.append({"kontrol": soru.kontrol, "sutun": soru.sutun,
                                      "metin": {dokuman.dil: cevap, diger: ""},
                                      "kaynak": "siparis", "madde": madde})
        raise UygulamaHatasi(_("Çok fazla soru ({n}); işlem durduruldu.").format(n=SORU_SINIRI))

    def _onizle(self, d):
        self.tree.clear()
        n_satir = 0
        if d.notlar:                                         # V-5c2-9
            ni = QTreeWidgetItem(["", _("Notlar ({n})").format(n=len(d.notlar)), ""])
            for n in d.notlar:
                ni.addChild(QTreeWidgetItem(["", _(NOT_ADI.get(n.tur, n.tur)), n.metin]))
            self.tree.addTopLevelItem(ni)
            ni.setExpanded(True)
        for b_i, b in enumerate(d.bolumler):
            bi = QTreeWidgetItem([b.no, b.baslik, ""])
            f = bi.font(1); f.setBold(True); bi.setFont(0, f); bi.setFont(1, f)
            self.tree.addTopLevelItem(bi)
            for s_i, s in enumerate(b.satirlar):
                n_satir += 1
                isr = isaret(s)
                si = QTreeWidgetItem([f"{isr} {s.no}".strip(), s.karakteristik or s.aktivite,
                                      self._ozet(s.kabul)])
                ipucu = ([_("Uygulanmaz: {g}").format(g=s.uygulanmaz)] if s.uygulanmaz else []) \
                    + [iz_metni(iz) for iz in s.izler]
                if ipucu:
                    for c in range(3):
                        si.setToolTip(c, "\n".join(ipucu))
                if s.uygulanmaz:                             # V-5c2-8: soluk
                    for c in range(3):
                        si.setForeground(c, QBrush(GRI))
                si.setData(0, Qt.ItemDataRole.UserRole, (b_i, s_i))   # 5c-3 düzeltme hedefi
                bi.addChild(si)
                for p in s.kabul:
                    si.addChild(self._parca_ogesi(p))
            bi.setExpanded(True)
        elle = d.elle_girilecekler()
        self.lbl_durum.setText(
            _("{format} / {sablon}: {d} kalem, {d2} bölüm, {n_satir} satır").format(format=d.format, sablon=d.sablon, d=len(d.kalemler), d2=len(d.bolumler), n_satir=n_satir) + (_(", {d} ELLE GİRİLECEK alan").format(d=len(elle)) if elle else "")
            + (_(", {n} not").format(n=len(d.notlar)) if d.notlar else ""))

    @staticmethod
    def _ozet(kabul, uzunluk=80):
        """Kabul kriterinin ilk satırı (kısaltılmış); tam parçalar alt öğelerde."""
        for p in kabul:
            if isinstance(p, Metin):
                metin = p.metin
            elif isinstance(p, ElleGirilecek):
                metin = f"ELLE GİRİLECEK: {p.etiket}"
            elif isinstance(p, KalemTablosu):
                metin = "Kalem tablosu"
            else:
                continue
            ilk = metin.strip().splitlines()[0] if metin.strip() else ""
            if ilk:
                return ilk if len(ilk) <= uzunluk else ilk[:uzunluk - 1] + "…"
        return ""

    @staticmethod
    def _parca_ogesi(p):
        if isinstance(p, Metin):
            return QTreeWidgetItem(["", "", p.metin])
        if isinstance(p, ElleGirilecek):
            return QTreeWidgetItem(["", "", f"ELLE GİRİLECEK: {p.etiket}"])
        if isinstance(p, KalemTablosu):
            it = QTreeWidgetItem(["", "Kalem tablosu", " | ".join(p.basliklar)])
            for row in p.satirlar:
                it.addChild(QTreeWidgetItem(["", "", " | ".join(str(x) for x in row)]))
            return it
        return QTreeWidgetItem(["", "", repr(p)])

    # ── önizlemede düzeltme (Plan 5c-3) ──────────────────────────
    def _secili_satir(self):
        """Seçili önizleme öğesinin satır konumu; kabul parçası alt öğesi seçiliyse üst satırı."""
        oge = self.tree.currentItem()
        while oge is not None:
            yer = oge.data(0, Qt.ItemDataRole.UserRole)
            if yer is not None:
                return tuple(yer) if self.dokuman is not None else None
            oge = oge.parent()
        return None

    def _duzelt_durumu(self, *__):
        yer = self._secili_satir()
        acik = (yer is not None and not self.salt_okunur
                and not self.dokuman.bolumler[yer[0]].satirlar[yer[1]].uygulanmaz)   # D-3
        self.btn_duzelt.setEnabled(acik)

    def _agac_menusu(self, konum):
        if not self.btn_duzelt.isEnabled():          # düğmeyle aynı kural (Antigravity 5c-3 BULGU-01)
            return
        menu = QMenu(self.tree)
        menu.addAction(_("Hücreyi düzelt…"), self.hucre_duzelt)
        menu.exec(self.tree.viewport().mapToGlobal(konum))

    def _duzelt_sor(self, satir, mevcut):
        d = HucreDuzeltDialog(satir, mevcut, self)
        return d.sonuc if d.exec() else None

    def hucre_duzelt(self):
        if self.salt_okunur:
            return
        yer = self._secili_satir()
        if yer is None:
            self._mesaj("bilgi", _("Hücreyi düzelt"), _("Önce önizlemeden bir satır seçin."))
            return
        satir = self.dokuman.bolumler[yer[0]].satirlar[yer[1]]
        if satir.uygulanmaz:                          # Antigravity 5c-3 BULGU-01
            self._mesaj("bilgi", _("Hücreyi düzelt"), _("Uygulanmaz satır düzeltilemez."))
            return
        hedef = satir_hedefi(self.dokuman, *yer)
        dil_kodu = self.dokuman.dil
        mevcut = {s: o["metin"].get(dil_kodu, "") for s in DUZELTME_SUTUNLARI
                  if (o := duzeltme_bul(self.siparis_ozel, hedef, s)) is not None}
        sonuc = self._duzelt_sor(satir, mevcut)
        if sonuc is None:
            return
        sutun, metin = sonuc
        yedek = (copy.deepcopy(self.siparis_ozel), self.degisti)     # doğrulama D-3
        self.siparis_ozel = duzeltme_yaz(self.siparis_ozel, hedef, sutun, dil_kodu, metin)
        self.degisti = True
        if self.olustur() is None:                    # Antigravity 5c-3 BULGU-04
            self.siparis_ozel, self.degisti = yedek

    # ── Excel ────────────────────────────────────────────────────
    def excel_aktar(self):
        if not self._yazabilir():                       # K15: Okuyucu yalnız görüntüler
            return None
        if self.on_kaydet is not None and not self._kilitli_kayit:
            if self.dokuman is None and self.olustur() is None:
                return None
            if self.degisti and not self.kaydet():      # müşteriye giden = kayıtlı hal
                return None
        if self.dokuman is None:
            self._mesaj("hata", _("Excel'e aktar"), _("Önce «Oluştur» ile doküman oluşturun."))
            return None
        ad = (self.dokuman.baslik.dokuman_no or self.dokuman.format).replace("/", "-")
        yol, __ = QFileDialog.getSaveFileName(self, _("Excel'e aktar"), _("{ad}.xlsx").format(ad=ad),
                                             _("Excel Dosyaları (*.xlsx)"))
        if not yol:
            return None
        try:
            sonuc = excel_yaz(self.dokuman, yol, self._firma())
        except (OSError, ValueError) as e:
            self._mesaj("hata", _("Excel'e aktarılamadı"), str(e))
            return None
        if self.on_aktarim is not None and not self._kilitli_kayit:
            self.on_aktarim(self.dokuman)
        self._mesaj("bilgi", _("Excel'e aktarıldı"), _("Dosya kaydedildi:\n{sonuc}").format(sonuc=sonuc))
        return sonuc
