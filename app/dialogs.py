# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""
Kayıt diyalogları (ekle/düzenle) ve salt-okunur detay penceresi.

WPS ve PQR diyalogları sekmelidir (Genel / Detay / Paso-Paso / Testler);
paso parametreleri ve test sonuçları artık tamamen UI üzerinden girilebilir.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QGridLayout, QTabWidget,
    QWidget, QScrollArea, QFrame, QLabel, QLineEdit, QComboBox, QTextEdit,
    QDateEdit, QDialogButtonBox, QMessageBox,
)
from PyQt6.QtCore import Qt, QDate

from . import config as C
from . import dil
from . import theme
from .widgets import EditableTable, ro_table, parse_range
from .diagram import DiagramPane, diagram_view
from .search_utils import tr_fold
from .standards_check import compare_std_status
from .dil import _


# ── Ortak küçük yapı taşları ────────────────────────────────────────
def _scroll_form():
    """Kaydırılabilir bir QFormLayout döndürür: (tab_widget, form_layout)."""
    tab = QScrollArea(); tab.setWidgetResizable(True)
    tab.setFrameShape(QFrame.Shape.NoFrame)
    inner = QWidget(); F = QFormLayout(inner)
    F.setLabelAlignment(Qt.AlignmentFlag.AlignRight); F.setSpacing(9)
    F.setContentsMargins(6, 10, 14, 10)
    tab.setWidget(inner)
    return tab, F


def _section(text):
    """QFormLayout içinde tam satır kaplayan bölüm başlığı etiketi."""
    lb = QLabel(text)
    lb.setStyleSheet(f"font-size:12px; font-weight:bold; color:{theme.t('accent_section')}; "
                     "padding:12px 0 2px 0; letter-spacing:0.4px;")
    return lb


def _style_buttonbox(b):
    """Kaydet butonunu ikon + birincil gradient ile vurgular, İptal'i sadeleştirir."""
    save = b.button(QDialogButtonBox.StandardButton.Save)
    if save:
        save.setText(_("💾  Kaydet"))
        save.setObjectName("btn_primary")
    cancel = b.button(QDialogButtonBox.StandardButton.Cancel)
    if cancel:
        cancel.setText(_("Vazgeç"))


def _secenekler(cmb, degerler):
    """Seçmeli veri: gösterim çevrilir, kayda giden veri Türkçe kalır (dil spec D3)."""
    for v in degerler:
        cmb.addItem(dil.deger(v), v)


def _secili_yap(cmb, deger):
    i = cmb.findData(deger)
    if i >= 0:
        cmb.setCurrentIndex(i)


def _detay_tab():
    """Detay skalar alanları sekmesi: (widget, {anahtar: QLineEdit})."""
    tab, F = _scroll_form()
    fields = {}
    for key, label, ph in C.DETAY_ALANLARI:
        e = QLineEdit(); e.setPlaceholderText(_(ph) if ph else ph)
        fields[key] = e
        F.addRow(_(label), e)
    return tab, fields


def _pasolar_tab():
    w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(6, 10, 6, 10)
    hint = QLabel(_("Her kaynak pasosu için parametreleri girin. "
                  "Boş satırlar kaydedilmez."))
    hint.setStyleSheet(f"color:{theme.t('hint_text')}; font-size:11px;")
    v.addWidget(hint)
    table = EditableTable(C.PASS_COLS, height=240)
    v.addWidget(table)
    return w, table


# ── WPS Diyaloğu ────────────────────────────────────────────────────
class WPSDialog(QDialog):
    def __init__(self, db, parent=None, record=None):
        super().__init__(parent)
        self.db = db
        self.record = record
        self.setWindowTitle(_("WPS Düzenle") if record else _("Yeni WPS Ekle"))
        self.setMinimumSize(640, 620)
        self._build()
        if record:
            self._fill(record)

    def _build(self):
        L = QVBoxLayout(self)
        tabs = QTabWidget(); tabs.setObjectName("dlg_tabs")

        # — Genel —
        gtab, F = _scroll_form()
        self.f_no = QLineEdit(); self.f_no.setPlaceholderText(_("Ör: WPS-001"))
        self.f_rev = QLineEdit(); self.f_rev.setPlaceholderText("00")
        self.f_tarih = QDateEdit(QDate.currentDate()); self.f_tarih.setCalendarPopup(True)
        self.f_tarih.setDisplayFormat("dd.MM.yyyy")
        self.f_pqr = QComboBox()
        self.f_proses = QComboBox(); self.f_proses.addItems(C.PROSESLER)
        self.f_metal = QLineEdit(); self.f_metal.setPlaceholderText(_("Ör: P-1, S355J2"))
        self.f_dolgu = QLineEdit(); self.f_dolgu.setPlaceholderText(_("Ör: ER70S-6"))
        self.f_pozisyon = QComboBox(); self.f_pozisyon.addItems(C.POZISYONLAR)
        self.f_onisitma = QLineEdit(); self.f_onisitma.setPlaceholderText(_("Ör: 150 veya Yok"))
        self.f_pwht = QComboBox(); _secenekler(self.f_pwht, C.PWHT_SEC)
        self.f_akim = QLineEdit(); self.f_akim.setPlaceholderText(_("Ör: 80-120"))
        self.f_voltaj = QLineEdit(); self.f_voltaj.setPlaceholderText(_("Ör: 22-26"))
        self.f_hiz = QLineEdit(); self.f_hiz.setPlaceholderText(_("Ör: 150-200"))
        self.f_polarite = QComboBox(); self.f_polarite.addItems(C.POLARITELER)
        self.f_durum = QComboBox(); _secenekler(self.f_durum, C.DURUMLAR)
        self.f_notlar = QTextEdit(); self.f_notlar.setFixedHeight(64)

        self.f_pqr.addItem(_("— PQR Seçiniz —"), None)
        for p in self.db.get_pqr():
            self.f_pqr.addItem(f"{p['no']} ({p.get('proses','')})", p["no"])

        def addrows(rows):
            for lbl, w in rows:
                F.addRow(lbl, w)
        F.addRow(_section(_("Tanımlama")))
        addrows([(_("WPS No *"), self.f_no), (_("Revizyon"), self.f_rev),
                 (_("Tarih"), self.f_tarih), (_("Bağlı PQR *"), self.f_pqr),
                 (_("Durum"), self.f_durum)])
        F.addRow(_section(_("Kaynak Bilgileri")))
        addrows([(_("Proses"), self.f_proses), (_("Metal Grubu"), self.f_metal),
                 (_("Dolgu Malzemesi"), self.f_dolgu), (_("Pozisyon"), self.f_pozisyon),
                 (_("Polarite"), self.f_polarite)])
        F.addRow(_section(_("Kaynak Parametreleri")))
        addrows([(_("Ön Isıtma (°C)"), self.f_onisitma), (_("PWHT"), self.f_pwht),
                 (_("Akım (A)"), self.f_akim), (_("Voltaj (V)"), self.f_voltaj),
                 (_("Hız (mm/dk)"), self.f_hiz)])
        F.addRow(_section(_("Notlar")))
        addrows([(_("Notlar"), self.f_notlar)])
        tabs.addTab(gtab, _("Genel"))

        # — Detay —
        dtab, self.detay_fields = _detay_tab()
        tabs.addTab(dtab, _("Detay"))

        # — Paso-Paso —
        ptab, self.pasolar_table = _pasolar_tab()
        tabs.addTab(ptab, _("Paso-Paso Parametreler"))

        # — Kaynak Şematik —
        self.diagram_pane = DiagramPane()
        tabs.addTab(self.diagram_pane, _("Kaynak Şematik"))

        L.addWidget(tabs)
        b = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                             QDialogButtonBox.StandardButton.Cancel)
        b.accepted.connect(self._ok); b.rejected.connect(self.reject)
        _style_buttonbox(b)
        L.addWidget(b)

    def _fill(self, r):
        self.f_no.setText(r.get("no", "")); self.f_rev.setText(r.get("rev", "00"))
        if r.get("tarih"):
            self.f_tarih.setDate(QDate.fromString(r["tarih"], "yyyy-MM-dd"))
        self.diagram_pane.set_diagram(r.get("diagram"))
        idx = self.f_pqr.findData(r.get("pqr", ""))
        if idx >= 0:
            self.f_pqr.setCurrentIndex(idx)
        self.f_proses.setCurrentText(r.get("proses", "GTAW"))
        self.f_metal.setText(r.get("metal", "")); self.f_dolgu.setText(r.get("dolgu", ""))
        self.f_pozisyon.setCurrentText(r.get("pozisyon", "1G"))
        self.f_onisitma.setText(r.get("onisitma", ""))
        _secili_yap(self.f_pwht, r.get("pwht", "Yok"))
        self.f_akim.setText(r.get("akim", "")); self.f_voltaj.setText(r.get("voltaj", ""))
        self.f_hiz.setText(r.get("hiz", ""))
        self.f_polarite.setCurrentText(r.get("polarite", "DCEP"))
        _secili_yap(self.f_durum, r.get("durum", "Aktif"))
        self.f_notlar.setPlainText(r.get("notlar", ""))

        detay = r.get("detay", {}) or {}
        for key, e in self.detay_fields.items():
            e.setText(str(detay.get(key, "") or ""))
        self.pasolar_table.set_rows(detay.get("pasolar", []))

    def _tolerance_issues(self, pqr):
        issues = []
        for key, wval, lbl in [
            ("proses", self.f_proses.currentText(), _("Proses")),
            ("metal", self.f_metal.text().strip(), _("Metal grubu")),
            ("dolgu", self.f_dolgu.text().strip(), _("Dolgu malzemesi")),
            ("polarite", self.f_polarite.currentText(), _("Polarite")),
            ("pwht", self.f_pwht.currentData(), "PWHT"),
        ]:
            pval = (pqr.get(key, "") or "").strip()
            if pval and wval and tr_fold(wval) != tr_fold(pval):
                issues.append(_("{lbl}: WPS '{wval}' ≠ PQR '{pval}'").format(lbl=lbl, wval=wval, pval=pval))
        for key, wtext, lbl, unit in [
            ("akim", self.f_akim.text().strip(), _("Akım"), "A"),
            ("voltaj", self.f_voltaj.text().strip(), _("Voltaj"), "V"),
            ("hiz", self.f_hiz.text().strip(), _("Hız"), _("mm/dk")),
        ]:
            pr = parse_range(pqr.get(key, "")); wr = parse_range(wtext)
            if not pr or not wr:
                continue
            (plo, phi), (wlo, whi) = pr, wr
            if wlo < plo or whi > phi:
                issues.append(_("{lbl}: WPS {wtext} {unit} → PQR onaylı aralık {plo:g}–{phi:g} {unit} dışında").format(lbl=lbl, wtext=wtext, unit=unit, plo=plo, phi=phi))
        return issues

    def _ok(self):
        if not self.f_no.text().strip():
            QMessageBox.warning(self, _("Uyarı"), _("WPS No zorunludur.")); return
        pqr_no = self.f_pqr.currentData()
        if not pqr_no:
            QMessageBox.warning(self, _("Uyarı"),
                _("WPS bir PQR'ye bağlanmadan oluşturulamaz.\n"
                "Lütfen 'Bağlı PQR' alanından bir PQR seçin "
                "(yoksa önce PQR sekmesinden ekleyin)."))
            return
        pqr = next((p for p in self.db.get_pqr() if p.get("no") == pqr_no), None)
        if pqr:
            issues = self._tolerance_issues(pqr)
            if issues:
                txt = (_("Bu WPS, bağlı <b>{pqr_no}</b> PQR'sinin onaylı kapsamı dışında değerler içeriyor:<br><br>").format(pqr_no=pqr_no)
                       + "<br>".join("•  " + i for i in issues)
                       + _("<br><br>Değerleri PQR kapsamına göre düzeltmeniz önerilir."
                         "<br>Yine de kaydetmek istiyor musunuz?"))
                r = QMessageBox.warning(self, _("Tolerans Uyarısı"), txt,
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No)
                if r != QMessageBox.StandardButton.Yes:
                    return
        self.accept()

    def get_record(self):
        detay = {key: e.text().strip() for key, e in self.detay_fields.items()
                 if e.text().strip()}
        pasolar = self.pasolar_table.get_rows()
        if pasolar:
            detay["pasolar"] = pasolar
        rec = {
            "no": self.f_no.text().strip(), "rev": self.f_rev.text().strip() or "00",
            "tarih": self.f_tarih.date().toString("yyyy-MM-dd"),
            "pqr": self.f_pqr.currentData(),
            "proses": self.f_proses.currentText(), "metal": self.f_metal.text().strip(),
            "dolgu": self.f_dolgu.text().strip(), "pozisyon": self.f_pozisyon.currentText(),
            "onisitma": self.f_onisitma.text().strip() or "Yok",
            "pwht": self.f_pwht.currentData(), "akim": self.f_akim.text().strip(),
            "voltaj": self.f_voltaj.text().strip(), "hiz": self.f_hiz.text().strip(),
            "polarite": self.f_polarite.currentText(), "durum": self.f_durum.currentData(),
            "notlar": self.f_notlar.toPlainText().strip(),
        }
        if detay:
            rec["detay"] = detay
        diagram = self.diagram_pane.get_diagram()
        if diagram:
            rec["diagram"] = diagram
        return rec


# ── PQR Diyaloğu ────────────────────────────────────────────────────
class PQRDialog(QDialog):
    def __init__(self, parent=None, record=None):
        super().__init__(parent)
        self.record = record
        self.setWindowTitle(_("PQR Düzenle") if record else _("Yeni PQR Ekle"))
        self.setMinimumSize(660, 640)
        self._build()
        if record:
            self._fill(record)

    def _build(self):
        L = QVBoxLayout(self)
        tabs = QTabWidget(); tabs.setObjectName("dlg_tabs")

        # — Genel —
        gtab, F = _scroll_form()
        self.f_no = QLineEdit(); self.f_no.setPlaceholderText(_("Ör: PQR-001"))
        self.f_rev = QLineEdit(); self.f_rev.setPlaceholderText("00")
        self.f_tarih = QDateEdit(QDate.currentDate()); self.f_tarih.setCalendarPopup(True)
        self.f_tarih.setDisplayFormat("dd.MM.yyyy")
        self.f_proses = QComboBox(); self.f_proses.addItems(C.PROSESLER)
        self.f_metal = QLineEdit(); self.f_metal.setPlaceholderText(_("Ör: P-1, S355J2"))
        self.f_dolgu = QLineEdit(); self.f_dolgu.setPlaceholderText(_("Ör: ER70S-6"))
        self.f_onisitma = QLineEdit(); self.f_onisitma.setPlaceholderText(_("Ör: 150 veya Yok"))
        self.f_pwht = QComboBox(); _secenekler(self.f_pwht, C.PWHT_SEC)
        self.f_akim = QLineEdit(); self.f_akim.setPlaceholderText(_("Ör: 90-110"))
        self.f_voltaj = QLineEdit(); self.f_voltaj.setPlaceholderText(_("Ör: 22-24"))
        self.f_hiz = QLineEdit(); self.f_hiz.setPlaceholderText(_("Ör: 120-160"))
        self.f_polarite = QComboBox(); self.f_polarite.addItems(C.POLARITELER)
        self.f_test = QComboBox(); _secenekler(self.f_test, C.TEST_SEC)
        self.f_lab = QLineEdit(); self.f_lab.setPlaceholderText(_("Ör: TÜV SÜD, SGS"))
        self.f_notlar = QTextEdit(); self.f_notlar.setFixedHeight(64)

        def addrows(rows):
            for lbl, w in rows:
                F.addRow(lbl, w)
        F.addRow(_section(_("Tanımlama")))
        addrows([(_("PQR No *"), self.f_no), (_("Revizyon"), self.f_rev),
                 (_("Tarih"), self.f_tarih)])
        F.addRow(_section(_("Kaynak Bilgileri")))
        addrows([(_("Proses"), self.f_proses), (_("Metal Grubu"), self.f_metal),
                 (_("Dolgu Malzemesi"), self.f_dolgu), (_("Polarite"), self.f_polarite)])
        F.addRow(_section(_("Kaynak Parametreleri")))
        addrows([(_("Ön Isıtma (°C)"), self.f_onisitma), (_("PWHT"), self.f_pwht),
                 (_("Akım (A)"), self.f_akim), (_("Voltaj (V)"), self.f_voltaj),
                 (_("Hız (mm/dk)"), self.f_hiz)])
        F.addRow(_section(_("Onay & Test")))
        addrows([(_("Test Sonucu"), self.f_test), (_("Test Kuruluşu"), self.f_lab)])
        F.addRow(_section(_("Notlar")))
        addrows([(_("Notlar"), self.f_notlar)])
        tabs.addTab(gtab, _("Genel"))

        # — Detay —
        dtab, self.detay_fields = _detay_tab()
        tabs.addTab(dtab, _("Detay"))

        # — Paso-Paso —
        ptab, self.pasolar_table = _pasolar_tab()
        tabs.addTab(ptab, _("Paso-Paso Parametreler"))

        # — Testler —
        ttab = self._build_test_tab()
        tabs.addTab(ttab, _("Test Sonuçları"))

        # — Kaynak Şematik —
        self.diagram_pane = DiagramPane()
        tabs.addTab(self.diagram_pane, _("Kaynak Şematik"))

        L.addWidget(tabs)
        b = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                             QDialogButtonBox.StandardButton.Cancel)
        b.accepted.connect(self._ok); b.rejected.connect(self.reject)
        _style_buttonbox(b)
        L.addWidget(b)

    def _build_test_tab(self):
        tab = QScrollArea(); tab.setWidgetResizable(True)
        tab.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget(); v = QVBoxLayout(inner); v.setContentsMargins(8, 10, 14, 10); v.setSpacing(8)

        def section(text):
            lb = QLabel(text)
            lb.setStyleSheet(f"font-size:13px; font-weight:bold; color:{theme.t('accent_section')}; "
                             "padding:6px 0 2px 0;")
            return lb

        # Skalar test alanları
        v.addWidget(section(_("Tahribatsız / Genel Muayene")))
        F = QFormLayout(); F.setSpacing(8); F.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.test_fields = {}
        for key, lbl in C.SCALAR_TESTS.items():
            e = QLineEdit(); e.setPlaceholderText(_("Ör: EN ISO 5817 – Kabul"))
            self.test_fields[key] = e
            F.addRow(_(lbl), e)
        v.addLayout(F)

        v.addWidget(section(_("Çekme Testi (EN ISO 4136)")))
        self.cekme_table = EditableTable(C.CEKME_COLS, height=130)
        v.addWidget(self.cekme_table)

        v.addWidget(section(_("Eğme Testi (EN ISO 5173)")))
        self.egme_table = EditableTable(C.EGME_COLS, height=130)
        v.addWidget(self.egme_table)

        v.addWidget(section(_("Çentik Darbe Testi (EN ISO 9016)")))
        self.centik_table = EditableTable(C.CENTIK_COLS, height=130)
        v.addWidget(self.centik_table)

        v.addStretch()
        tab.setWidget(inner)
        return tab

    def _fill(self, r):
        self.f_no.setText(r.get("no", "")); self.f_rev.setText(r.get("rev", "00"))
        if r.get("tarih"):
            self.f_tarih.setDate(QDate.fromString(r["tarih"], "yyyy-MM-dd"))
        self.diagram_pane.set_diagram(r.get("diagram"))
        self.f_proses.setCurrentText(r.get("proses", "GTAW"))
        self.f_metal.setText(r.get("metal", "")); self.f_dolgu.setText(r.get("dolgu", ""))
        self.f_onisitma.setText(r.get("onisitma", ""))
        _secili_yap(self.f_pwht, r.get("pwht", "Yok"))
        self.f_akim.setText(r.get("akim", "")); self.f_voltaj.setText(r.get("voltaj", ""))
        self.f_hiz.setText(r.get("hiz", ""))
        self.f_polarite.setCurrentText(r.get("polarite", "DCEP"))
        _secili_yap(self.f_test, r.get("test", "Geçti"))
        self.f_lab.setText(r.get("lab", ""))
        self.f_notlar.setPlainText(r.get("notlar", ""))

        detay = r.get("detay", {}) or {}
        for key, e in self.detay_fields.items():
            e.setText(str(detay.get(key, "") or ""))
        self.pasolar_table.set_rows(detay.get("pasolar", []))

        testler = detay.get("testler", {}) or {}
        for key, e in self.test_fields.items():
            e.setText(str(testler.get(key, "") or ""))
        self.cekme_table.set_rows(testler.get("cekme", []))
        self.egme_table.set_rows(testler.get("egme", []))
        self.centik_table.set_rows(testler.get("centik", []))

    def _ok(self):
        if not self.f_no.text().strip():
            QMessageBox.warning(self, _("Uyarı"), _("PQR No zorunludur.")); return
        self.accept()

    def get_record(self):
        detay = {key: e.text().strip() for key, e in self.detay_fields.items()
                 if e.text().strip()}
        pasolar = self.pasolar_table.get_rows()
        if pasolar:
            detay["pasolar"] = pasolar

        testler = {key: e.text().strip() for key, e in self.test_fields.items()
                   if e.text().strip()}
        for tname, table in [("cekme", self.cekme_table), ("egme", self.egme_table),
                             ("centik", self.centik_table)]:
            rows = table.get_rows()
            if rows:
                testler[tname] = rows
        if testler:
            detay["testler"] = testler

        rec = {
            "no": self.f_no.text().strip(), "rev": self.f_rev.text().strip() or "00",
            "tarih": self.f_tarih.date().toString("yyyy-MM-dd"),
            "proses": self.f_proses.currentText(), "metal": self.f_metal.text().strip(),
            "dolgu": self.f_dolgu.text().strip(),
            "onisitma": self.f_onisitma.text().strip() or "Yok",
            "pwht": self.f_pwht.currentData(), "akim": self.f_akim.text().strip(),
            "voltaj": self.f_voltaj.text().strip(), "hiz": self.f_hiz.text().strip(),
            "polarite": self.f_polarite.currentText(), "test": self.f_test.currentData(),
            "lab": self.f_lab.text().strip(), "notlar": self.f_notlar.toPlainText().strip(),
        }
        if detay:
            rec["detay"] = detay
        diagram = self.diagram_pane.get_diagram()
        if diagram:
            rec["diagram"] = diagram
        return rec


# ── Standart Diyaloğu ───────────────────────────────────────────────
class STDDialog(QDialog):
    def __init__(self, parent=None, record=None):
        super().__init__(parent)
        self.record = record
        self.setWindowTitle(_("Standart Düzenle") if record else _("Standart Ekle"))
        self.setMinimumWidth(520)
        self._build()
        if record:
            self._fill(record)

    def _build(self):
        L = QVBoxLayout(self); F = QFormLayout()
        F.setLabelAlignment(Qt.AlignmentFlag.AlignRight); F.setSpacing(10)

        self.f_no = QLineEdit(); self.f_no.setPlaceholderText(_("Ör: ASME IX, AWS D1.1, EN ISO 15614-1"))
        self.f_org = QComboBox(); self.f_org.addItems(C.ORGANIZASYONLAR)
        self.f_title = QLineEdit(); self.f_title.setPlaceholderText(_("Standart tam adı"))
        self.f_myver = QLineEdit()
        self.f_myver.setPlaceholderText(_("Yıl (Ör: 2021)  |  API: '23rd Edition (Errata 1, Addendum 2)'"))
        self.f_lastver = QLineEdit(); self.f_lastver.setPlaceholderText(_("Manuel giriş (opsiyonel)"))
        self.f_year = QLineEdit(); self.f_year.setPlaceholderText(_("Ör: 2019"))
        self.f_notlar = QTextEdit(); self.f_notlar.setFixedHeight(70)

        for lbl, w in [
            (_("Standart No *"), self.f_no), (_("Kuruluş"), self.f_org), (_("Başlık"), self.f_title),
            (_("Elimdeki Sürüm"), self.f_myver), (_("Son Sürüm (Manuel)"), self.f_lastver),
            (_("Yayın Yılı"), self.f_year), (_("Notlar"), self.f_notlar),
        ]:
            F.addRow(lbl, w)

        hint = QLabel(_("💡 'Son Sürüm (Manuel)' alanı otomatik kontrolün\n"
                      "    sonuç döndüremediği durumlar için kullanılır."))
        hint.setStyleSheet(f"color:{theme.t('hint_text')}; font-size:11px;")
        F.addRow("", hint)

        L.addLayout(F)
        b = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                             QDialogButtonBox.StandardButton.Cancel)
        b.accepted.connect(self._ok); b.rejected.connect(self.reject)
        _style_buttonbox(b)
        L.addWidget(b)

    def _fill(self, r):
        self.f_no.setText(r.get("no", "")); self.f_org.setCurrentText(r.get("org", "ASME"))
        self.f_title.setText(r.get("title", "")); self.f_myver.setText(r.get("myVer", ""))
        self.f_lastver.setText(r.get("manualLastVer", "")); self.f_year.setText(r.get("year", ""))
        self.f_notlar.setPlainText(r.get("notlar", ""))

    def _ok(self):
        if not self.f_no.text().strip():
            QMessageBox.warning(self, _("Uyarı"), _("Standart No zorunludur.")); return
        self.accept()

    def get_record(self, existing=None):
        r = {
            "no": self.f_no.text().strip(), "org": self.f_org.currentText(),
            "title": self.f_title.text().strip(), "myVer": self.f_myver.text().strip(),
            "manualLastVer": self.f_lastver.text().strip(), "year": self.f_year.text().strip(),
            "notlar": self.f_notlar.toPlainText().strip(),
            "lastVer": existing.get("lastVer", "") if existing else "",
            "lastCheck": existing.get("lastCheck", "") if existing else "",
            "status": existing.get("status", "kontrol") if existing else "kontrol",
        }
        # Sürüm elle değişince durum haftalık kontrolü beklemez (Antigravity BULGU-10); kural
        # kontrol sonucunun yazımıyla aynı (pages.STDPage._sonucu_yaz)
        if r["manualLastVer"]:
            r["status"] = compare_std_status(r["myVer"], r["manualLastVer"])
        elif r["lastVer"] and r["status"] in ("guncel", "guncelleme"):
            r["status"] = compare_std_status(r["myVer"], r["lastVer"])
        return r


# ── Sertifika Diyaloğu ──────────────────────────────────────────────
class CertDialog(QDialog):
    def __init__(self, parent=None, record=None):
        super().__init__(parent)
        self.record = record
        self.setWindowTitle(_("Sertifika Düzenle") if record else _("Sertifika Ekle"))
        self.setMinimumWidth(540)
        self._build()
        if record:
            self._fill(record)

    def _build(self):
        L = QVBoxLayout(self); F = QFormLayout()
        F.setLabelAlignment(Qt.AlignmentFlag.AlignRight); F.setSpacing(10)

        self.f_no = QLineEdit(); self.f_no.setPlaceholderText(_("Belge / Sertifika numarası"))
        self.f_ad = QComboBox(); self.f_ad.setEditable(True)
        self.f_ad.addItems(C.CERT_TIPLERI)
        self.f_ad.setCurrentText("")
        self.f_org = QComboBox(); self.f_org.setEditable(True)
        self.f_org.addItems(C.CERT_KURULUSLAR)
        self.f_org.setCurrentText("")
        self.f_kapsam = QLineEdit(); self.f_kapsam.setPlaceholderText(_("Belgelendirme kapsamı"))
        self.f_tarih = QDateEdit(QDate.currentDate()); self.f_tarih.setCalendarPopup(True)
        self.f_tarih.setDisplayFormat("dd.MM.yyyy")
        self.f_bitis = QDateEdit(QDate.currentDate().addYears(3)); self.f_bitis.setCalendarPopup(True)
        self.f_bitis.setDisplayFormat("dd.MM.yyyy")
        self.f_notlar = QTextEdit(); self.f_notlar.setFixedHeight(70)

        for lbl, w in [
            (_("Belge No *"), self.f_no), (_("Sertifika / Standart *"), self.f_ad),
            (_("Belgelendirme Kuruluşu"), self.f_org), (_("Kapsam"), self.f_kapsam),
            (_("Düzenleme Tarihi"), self.f_tarih), (_("Bitiş Tarihi"), self.f_bitis),
            (_("Notlar"), self.f_notlar),
        ]:
            F.addRow(lbl, w)

        hint = QLabel(_("💡 Durum (Geçerli / Yakında Dolacak / Süresi Doldu) "
                      "bitiş tarihine göre otomatik hesaplanır."))
        hint.setStyleSheet(f"color:{theme.t('hint_text')}; font-size:11px;")
        F.addRow("", hint)

        L.addLayout(F)
        b = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                             QDialogButtonBox.StandardButton.Cancel)
        b.accepted.connect(self._ok); b.rejected.connect(self.reject)
        _style_buttonbox(b)
        L.addWidget(b)

    def _fill(self, r):
        self.f_no.setText(r.get("no", ""))
        self.f_ad.setCurrentText(r.get("ad", ""))
        self.f_org.setCurrentText(r.get("org", ""))
        self.f_kapsam.setText(r.get("kapsam", ""))
        if r.get("tarih"):
            self.f_tarih.setDate(QDate.fromString(r["tarih"], "yyyy-MM-dd"))
        if r.get("bitis"):
            self.f_bitis.setDate(QDate.fromString(r["bitis"], "yyyy-MM-dd"))
        self.f_notlar.setPlainText(r.get("notlar", ""))

    def _ok(self):
        if not self.f_no.text().strip():
            QMessageBox.warning(self, _("Uyarı"), _("Belge No zorunludur.")); return
        if not self.f_ad.currentText().strip():
            QMessageBox.warning(self, _("Uyarı"), _("Sertifika / Standart adı zorunludur.")); return
        self.accept()

    def get_record(self):
        return {
            "no": self.f_no.text().strip(),
            "ad": self.f_ad.currentText().strip(),
            "org": self.f_org.currentText().strip(),
            "kapsam": self.f_kapsam.text().strip(),
            "tarih": self.f_tarih.date().toString("yyyy-MM-dd"),
            "bitis": self.f_bitis.date().toString("yyyy-MM-dd"),
            "notlar": self.f_notlar.toPlainText().strip(),
        }


# ── Salt-okunur detay penceresi (WPS / PQR) ─────────────────────────
class DetailDialog(QDialog):
    def __init__(self, record, kind, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("{kind} Detay — {d}").format(kind=kind, d=record.get('no','')))
        self.setMinimumSize(700, 580)
        self._build(record, kind)

    def _section(self, title):
        lb = QLabel(title)
        lb.setStyleSheet(f"font-size:14px; font-weight:bold; color:{theme.t('accent_section')}; "
                         f"padding:10px 0 4px 0; border-bottom:1px solid {theme.t('divider')};")
        return lb

    def _mini_label(self, text):
        lb = QLabel(text)
        lb.setStyleSheet(f"color:{theme.t('mini_label')}; font-size:12px; font-weight:600; padding-top:6px;")
        return lb

    def _info_grid(self, record):
        detay = record.get("detay", {}) or {}
        order = ["no", "rev", "tarih", "pqr", "test", "lab", "proses",
                 "kaynak_tipi", "standart", "yeterlilik", "metal", "malzeme",
                 "malzeme_grubu", "dolgu", "kalinlik", "pozisyon", "polarite",
                 "akim", "voltaj", "hiz", "onisitma", "pasolar_arasi", "pwht",
                 "gaz", "gaz_debisi", "tungsten", "joint_design", "paso_tipi",
                 "durum", "kaynakci", "muayene_kurulusu", "rapor_no",
                 "hazirlayan", "onaylayan", "belge_no"]
        merged = {**record, **detay}
        grid = QGridLayout(); grid.setHorizontalSpacing(18); grid.setVerticalSpacing(6)
        col = 0; row = 0
        for key in order:
            if key in ("detay", "testler", "pasolar", "notlar"):
                continue
            val = merged.get(key)
            if val in (None, "", "-"):
                continue
            lk = QLabel(_(C.DETAIL_LABELS.get(key, key)) + ":")
            lk.setStyleSheet(f"color:{theme.t('val_slate')}; font-size:12px;")
            lv = QLabel(dil.deger(str(val)) if key in ("durum", "test", "pwht", "onisitma") else str(val))
            lv.setStyleSheet(f"color:{theme.t('detail_value')}; font-size:12px; font-weight:600;")
            lv.setWordWrap(True)
            grid.addWidget(lk, row, col * 2)
            grid.addWidget(lv, row, col * 2 + 1)
            col += 1
            if col == 2:
                col = 0; row += 1
        w = QWidget(); w.setLayout(grid)
        return w

    def _build(self, record, kind):
        outer = QVBoxLayout(self)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget(); V = QVBoxLayout(body); V.setSpacing(8)
        V.setContentsMargins(4, 4, 14, 4)

        detay = record.get("detay", {}) or {}

        head = QLabel(f"{_(kind)} {record.get('no','')}")
        head.setStyleSheet(f"font-size:18px; font-weight:bold; color:{theme.t('text_bright')};")
        V.addWidget(head)

        V.addWidget(self._section(_("📋  Genel Bilgiler")))
        V.addWidget(self._info_grid(record))

        pasolar = detay.get("pasolar") or []
        if pasolar:
            V.addWidget(self._section(_("🔧  Kaynak Parametreleri (Paso Paso)")))
            V.addWidget(ro_table(pasolar, C.PASS_COLS))

        testler = detay.get("testler") or {}
        if testler:
            V.addWidget(self._section(_("🧪  Tahribatlı / Tahribatsız Muayene Sonuçları")))
            for k, lbl in C.SCALAR_TESTS.items():
                if testler.get(k):
                    line = QLabel(f"• {_(lbl)}: {testler[k]}")
                    line.setStyleSheet(f"color:{theme.t('text_soft')}; font-size:12px;")
                    V.addWidget(line)
            if testler.get("cekme"):
                V.addWidget(self._mini_label(_("Çekme Testi (EN ISO 4136)")))
                V.addWidget(ro_table(testler["cekme"], C.CEKME_COLS))
            if testler.get("egme"):
                V.addWidget(self._mini_label(_("Eğme Testi (EN ISO 5173)")))
                V.addWidget(ro_table(testler["egme"], C.EGME_COLS))
            if testler.get("centik"):
                V.addWidget(self._mini_label(_("Çentik Darbe Testi (EN ISO 9016)")))
                V.addWidget(ro_table(testler["centik"], C.CENTIK_COLS))

        view = diagram_view(record.get("diagram"))
        if view is not None:
            V.addWidget(self._section(_("🖼  Kaynak Şematik")))
            V.addWidget(view, alignment=Qt.AlignmentFlag.AlignLeft)

        if record.get("notlar"):
            V.addWidget(self._section(_("📝  Notlar")))
            nb = QLabel(record["notlar"]); nb.setWordWrap(True)
            nb.setStyleSheet(f"color:{theme.t('text_soft')}; font-size:12px;")
            V.addWidget(nb)

        V.addStretch()
        scroll.setWidget(body)
        outer.addWidget(scroll)

        btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn.rejected.connect(self.reject); btn.accepted.connect(self.accept)
        btn.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.accept)
        outer.addWidget(btn)
