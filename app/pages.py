# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""
Sekme sayfaları: Ana Sayfa (dashboard), WPS, PQR, Standart ve Sertifika.

Her sayfa kendi tablosunu, filtrelerini ve CRUD işlemlerini yönetir; ortak
yardımcılar widgets.py'den, diyaloglar dialogs.py'den gelir. Standart sayfası
arka plan kontrol işçisini (standards_check) kullanır.
"""

import json
from datetime import date, timedelta

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFrame, QLabel, QLineEdit,
    QComboBox, QPushButton, QTableWidget, QMessageBox, QFileDialog, QDialog,
    QScrollArea,
)
from PyQt6.QtCore import Qt, QTime
from PyQt6.QtGui import QColor

from . import config as C
from . import dil
from . import kimlik
from . import theme
from .database import CakismaHatasi, cert_status, parse_iso
from .ozet import ozet
from .widgets import (
    badge_item, ro_item, page_header, make_action_cell, stat_card,
    ToastNotification, apply_col_widths, export_button, gecikmeli_arama,
    ICON_OK, ICON_WARN, ICON_BAD, ICON_NEUTRAL,
)
from .dialogs import WPSDialog, PQRDialog, STDDialog, CertDialog, DetailDialog
from .exporter import export_xlsx
from .search_utils import matches_query, tr_fold
from .standards_check import CheckWorker, compare_std_status, has_api_key
from .dil import N_, _


def _kisalt(adlar, sinir=5):
    """Uyarı çubuğu için ad listesi: ilk `sinir` ad + kalan sayısı."""
    adlar = list(adlar)
    ek = _(" +{d} diğer").format(d=len(adlar) - sinir) if len(adlar) > sinir else ""
    return ", ".join(adlar[:sinir]) + ek


def _duzenleyebilir(db):
    """Giriş yapan kullanıcı kayıt değiştirebilir mi? (kullanıcısız = sistem/test: evet).
    Arayüz gizler; asıl engel veritabanı katmanındadır (database.YetkiHatasi)."""
    k = getattr(db, "kullanici", None)
    return k is None or kimlik.yetkili(k.rol, kimlik.DUZENLEYICI)


# ── WPS SAYFASI ─────────────────────────────────────────────────────
class WPSPage(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self._row_map = {}
        self._sort_col = -1
        self._sort_asc = True
        self._build()
        self.refresh()

    def _build(self):
        L = QVBoxLayout(self); L.setContentsMargins(24, 20, 24, 16); L.setSpacing(12)
        L.addWidget(page_header(_("Kaynak Prosedür Şartnameleri"),
                                _("WPS kayıtlarını oluşturun, filtreleyin ve yönetin")))
        sr = QHBoxLayout()
        self.s_total = stat_card(_("Toplam WPS"), sr, icon="📄", accent="blue")
        self.s_active = stat_card(_("Aktif"), sr, icon=ICON_OK, accent="green")
        self.s_rev = stat_card(_("Revizyon Bekleyen"), sr, icon=ICON_WARN, accent="amber")
        sr.addStretch(); L.addLayout(sr)

        tb = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText(_("🔍  WPS No, PQR, Proses..."))
        self.search.setFixedWidth(230); gecikmeli_arama(self.search, self.refresh)
        self.cmb_proses = QComboBox(); self.cmb_proses.addItem(_("Tüm Prosesler"), "")
        for x in C.PROSESLER:   # veri = değer: filtre currentData okur
            self.cmb_proses.addItem(x, x)
        self.cmb_proses.currentIndexChanged.connect(self.refresh)
        self.cmb_poz = QComboBox(); self.cmb_poz.addItem(_("Tüm Pozisyonlar"), "")
        for x in C.POZISYONLAR:
            self.cmb_poz.addItem(x, x)
        self.cmb_poz.currentIndexChanged.connect(self.refresh)
        bn = QPushButton(_("＋  Yeni WPS")); bn.setObjectName("btn_primary"); bn.clicked.connect(self.add)
        self.btn_yeni = bn; bn.setVisible(_duzenleyebilir(self.db))
        be = export_button(self.export_excel, self.export_json)
        tb.addWidget(self.search); tb.addWidget(self.cmb_proses); tb.addWidget(self.cmb_poz)
        tb.addStretch(); tb.addWidget(be); tb.addWidget(bn)
        L.addLayout(tb)

        self.table = QTableWidget()
        self.table.setColumnCount(len(C.COLS_WPS) + 1)
        self.table.setColumnHidden(len(C.COLS_WPS), not _duzenleyebilir(self.db))   # Düzenle/Sil
        self.table.setHorizontalHeaderLabels([_(c[0]) for c in C.COLS_WPS] + [_("İşlem")])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True); self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setToolTip(_("Detayları görmek için satıra çift tıklayın"))
        self.table.cellDoubleClicked.connect(self._show_detail)
        hdr = self.table.horizontalHeader()
        hdr.setSortIndicatorShown(True)
        hdr.sectionClicked.connect(self._on_header_clicked)
        apply_col_widths(self.table, C.COLS_WPS)
        L.addWidget(self.table)

    def _show_detail(self, row, _col):
        real_idx = self._row_map.get(row)
        if real_idx is None:
            return
        DetailDialog(self.db.get_wps()[real_idx], "WPS", self).exec()

    def _on_header_clicked(self, col):
        if col == len(C.COLS_WPS):
            return
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        self.table.horizontalHeader().setSortIndicator(
            col, Qt.SortOrder.AscendingOrder if self._sort_asc else Qt.SortOrder.DescendingOrder)
        self.refresh()

    def refresh(self):
        s = self.search.text()
        pf = self.cmb_proses.currentData() or ""
        po = self.cmb_poz.currentData() or ""
        data = [(i, w) for i, w in enumerate(self.db.get_wps())
                if matches_query(s, w.get("no", ""), w.get("pqr") or "", w.get("proses", ""),
                                 w.get("metal", ""), w.get("dolgu", ""))
                and (not pf or w.get("proses") == pf)
                and (not po or w.get("pozisyon") == po)]
        if 0 <= self._sort_col < len(C.COLS_WPS):
            key = C.COLS_WPS[self._sort_col][1]
            rev = not self._sort_asc
            if key == "durum":
                _ord = {"Aktif": 0, "Revizyon Bekliyor": 1, "İptal": 2}
                data.sort(key=lambda x: _ord.get(x[1].get("durum", ""), 99), reverse=rev)
            elif key in ("akim", "voltaj", "hiz"):
                def _n(x, k=key):
                    try: return float(str(x[1].get(k, "") or 0).replace(",", "."))
                    except: return 0.0
                data.sort(key=_n, reverse=rev)
            else:
                data.sort(key=lambda x, k=key: tr_fold(x[1].get(k, "") or ""), reverse=rev)
        self._row_map = {}
        self.table.setRowCount(len(data))
        for row, (real_idx, w) in enumerate(data):
            self._row_map[row] = real_idx
            self.table.setRowHeight(row, 42)
            for col, (__, key, __) in enumerate(C.COLS_WPS):
                val = w.get(key, "") or "-"
                if key == "durum":
                    bg, fg = theme.status("wps").get(val, theme.badge_neutral())
                    icon = {"Aktif": ICON_OK, "Revizyon Bekliyor": ICON_WARN,
                            "İptal": ICON_BAD}.get(val, ICON_NEUTRAL)
                    self.table.setItem(row, col, badge_item(dil.deger(val), bg, fg, icon))
                elif key == "pqr":
                    it = ro_item(val, Qt.AlignmentFlag.AlignCenter)
                    it.setForeground(QColor(theme.t("val_purple")))
                    self.table.setItem(row, col, it)
                else:   # seçmeli değerler (Var/Yok) ekranda çevrilir, veri Türkçe (dil D3)
                    self.table.setItem(row, col, ro_item(dil.deger(val) if key in ("pwht", "onisitma") else val))
            cell = make_action_cell(
                lambda _, i=real_idx: self.edit(i),
                lambda _, i=real_idx: self.delete(i),
            )
            self.table.setCellWidget(row, len(C.COLS_WPS), cell)
        all_wps = self.db.get_wps()
        self.s_total.setText(str(len(all_wps)))
        self.s_active.setText(str(sum(1 for w in all_wps if w.get("durum") == "Aktif")))
        self.s_rev.setText(str(sum(1 for w in all_wps if w.get("durum") == "Revizyon Bekliyor")))

    def add(self):
        d = WPSDialog(self.db, self)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.db.add_wps(d.get_record()); self.refresh()

    def edit(self, idx):
        a = self.db.anahtar("wps", idx)   # pencere açıkken liste yenilenebilir (tablet)
        d = WPSDialog(self.db, self, record=self.db.get_wps()[idx])
        if d.exec() == QDialog.DialogCode.Accepted:
            self.db.update_wps(idx, d.get_record(), anahtar=a); self.refresh()

    def delete(self, idx):
        w = self.db.get_wps()[idx]
        a = self.db.anahtar("wps", idx)
        if QMessageBox.question(self, _("Silme Onayı"),
                _("<b>{d}</b> numaralı WPS kaydı silinecek. Emin misiniz?").format(d=w['no']),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                ) == QMessageBox.StandardButton.Yes:
            self.db.delete_wps(idx, anahtar=a); self.refresh()

    def export_json(self):
        path, __ = QFileDialog.getSaveFileName(self, _("Dışa Aktar"),
                                              _("WPS_export_{d}.json").format(d=date.today()),
                                              _("JSON Dosyaları (*.json)"))
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"tarih": str(date.today()), "wps": self.db.get_wps()},
                              f, ensure_ascii=False, indent=2)
            except OSError as e:
                ToastNotification.notify(self.window(), _("Dışa aktarılamadı: {e}").format(e=e), "error")
                return
            ToastNotification.notify(self.window(), _("WPS verileri JSON'a aktarıldı."), "success")

    def export_excel(self):
        headers = [_(c[0]) for c in C.COLS_WPS] + [_("Notlar")]
        # seçmeli değerler ekrandaki gibi (standart/sertifika durumlarıyla tutarlı; dil D3)
        rows = [[dil.deger(w.get(key, "") or "") if key in ("durum", "pwht", "onisitma", "test") else w.get(key, "") or ""
                 for __, key, __ in C.COLS_WPS] + [w.get("notlar", "")]
                for w in self.db.get_wps()]
        path = export_xlsx(self, f"WPS_Listesi_{date.today()}.xlsx", "WPS", headers, rows)
        if path:
            ToastNotification.notify(self.window(), _("WPS listesi Excel'e aktarıldı."), "success")


# ── PQR SAYFASI ─────────────────────────────────────────────────────
class PQRPage(QWidget):
    def __init__(self, db, wps_page):
        super().__init__()
        self.db = db; self.wps_page = wps_page
        self._row_map = {}
        self._sort_col = -1
        self._sort_asc = True
        self._build(); self.refresh()

    def _build(self):
        L = QVBoxLayout(self); L.setContentsMargins(24, 20, 24, 16); L.setSpacing(12)
        L.addWidget(page_header(_("Prosedür Onay Kayıtları"),
                                _("PQR kayıtları ve test sonuçlarını takip edin")))
        sr = QHBoxLayout()
        self.s_total = stat_card(_("Toplam PQR"), sr, icon="📋", accent="purple")
        self.s_valid = stat_card(_("Geçerli PQR"), sr, icon=ICON_OK, accent="green")
        self.s_wps = stat_card(_("Toplam Bağlı WPS"), sr, icon="📄", accent="blue")
        sr.addStretch(); L.addLayout(sr)

        tb = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText(_("🔍  PQR No, Proses..."))
        self.search.setFixedWidth(230); gecikmeli_arama(self.search, self.refresh)
        self.cmb_proses = QComboBox(); self.cmb_proses.addItem(_("Tüm Prosesler"), "")
        for x in C.PROSESLER:   # veri = değer: filtre currentData okur
            self.cmb_proses.addItem(x, x)
        self.cmb_proses.currentIndexChanged.connect(self.refresh)
        self.cmb_test = QComboBox(); self.cmb_test.addItem(_("Tüm Sonuçlar"), "")
        for x in C.TEST_SEC:   # gösterim çevrilir, filtre Türkçe değerle
            self.cmb_test.addItem(dil.deger(x), x)
        self.cmb_test.currentIndexChanged.connect(self.refresh)
        bn = QPushButton(_("＋  Yeni PQR")); bn.setObjectName("btn_primary"); bn.clicked.connect(self.add)
        self.btn_yeni = bn; bn.setVisible(_duzenleyebilir(self.db))
        be = export_button(self.export_excel, self.export_json)
        tb.addWidget(self.search); tb.addWidget(self.cmb_proses); tb.addWidget(self.cmb_test)
        tb.addStretch(); tb.addWidget(be); tb.addWidget(bn)
        L.addLayout(tb)

        self.table = QTableWidget()
        self.table.setColumnCount(len(C.COLS_PQR) + 1)
        self.table.setColumnHidden(len(C.COLS_PQR), not _duzenleyebilir(self.db))   # Düzenle/Sil
        self.table.setHorizontalHeaderLabels([_(c[0]) for c in C.COLS_PQR] + [_("İşlem")])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True); self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setToolTip(_("Detayları görmek için satıra çift tıklayın"))
        self.table.cellDoubleClicked.connect(self._show_detail)
        hdr = self.table.horizontalHeader()
        hdr.setSortIndicatorShown(True)
        hdr.sectionClicked.connect(self._on_header_clicked)
        apply_col_widths(self.table, C.COLS_PQR)
        L.addWidget(self.table)

    def _show_detail(self, row, _col):
        real_idx = self._row_map.get(row)
        if real_idx is None:
            return
        DetailDialog(self.db.get_pqr()[real_idx], "PQR", self).exec()

    def _on_header_clicked(self, col):
        if col == len(C.COLS_PQR):
            return
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        self.table.horizontalHeader().setSortIndicator(
            col, Qt.SortOrder.AscendingOrder if self._sort_asc else Qt.SortOrder.DescendingOrder)
        self.refresh()

    def refresh(self):
        s = self.search.text()
        pf = self.cmb_proses.currentData() or ""
        tf = self.cmb_test.currentData() or ""
        data = [(i, p) for i, p in enumerate(self.db.get_pqr())
                if matches_query(s, p.get("no", ""), p.get("proses", ""),
                                 p.get("metal", ""), p.get("dolgu", ""))
                and (not pf or p.get("proses") == pf)
                and (not tf or p.get("test") == tf)]
        if 0 <= self._sort_col < len(C.COLS_PQR):
            key = C.COLS_PQR[self._sort_col][1]
            rev = not self._sort_asc
            if key == "test":
                _ord = {"Geçti": 0, "Beklemede": 1, "Başarısız": 2}
                data.sort(key=lambda x: _ord.get(x[1].get("test", ""), 99), reverse=rev)
            elif key == "_wps_count":
                data.sort(key=lambda x: self.db.wps_count_for_pqr(x[1]["no"]), reverse=rev)
            elif key in ("akim", "voltaj"):
                def _n(x, k=key):
                    try: return float(str(x[1].get(k, "") or 0).replace(",", "."))
                    except: return 0.0
                data.sort(key=_n, reverse=rev)
            else:
                data.sort(key=lambda x, k=key: tr_fold(x[1].get(k, "") or ""), reverse=rev)
        self._row_map = {}
        self.table.setRowCount(len(data))
        for row, (real_idx, p) in enumerate(data):
            self._row_map[row] = real_idx
            self.table.setRowHeight(row, 42)
            for col, (__, key, __) in enumerate(C.COLS_PQR):
                if key == "_wps_count":
                    cnt = self.db.wps_count_for_pqr(p["no"])
                    bg, fg = theme.badge_info() if cnt > 0 else theme.badge_neutral()
                    self.table.setItem(row, col, badge_item(f"{cnt} WPS", bg, fg))
                elif key == "test":
                    tval = p.get("test", "")
                    bg, fg = theme.status("pqr").get(tval, theme.badge_neutral())
                    icon = {"Geçti": ICON_OK, "Başarısız": ICON_BAD,
                            "Beklemede": ICON_WARN}.get(tval, ICON_NEUTRAL)
                    self.table.setItem(row, col, badge_item(dil.deger(tval) or "-", bg, fg, icon))
                else:
                    v = p.get(key, "")
                    self.table.setItem(row, col, ro_item(dil.deger(v) if key in ("pwht", "onisitma") else v))
            cell = make_action_cell(
                lambda _, i=real_idx: self.edit(i),
                lambda _, i=real_idx: self.delete(i),
            )
            self.table.setCellWidget(row, len(C.COLS_PQR), cell)
        all_pqr = self.db.get_pqr()
        self.s_total.setText(str(len(all_pqr)))
        self.s_valid.setText(str(sum(1 for p in all_pqr if p.get("test") == "Geçti")))
        self.s_wps.setText(str(len(self.db.get_wps())))

    def add(self):
        d = PQRDialog(self)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.db.add_pqr(d.get_record()); self.refresh(); self.wps_page.refresh()

    def edit(self, idx):
        a = self.db.anahtar("pqr", idx)   # pencere açıkken liste yenilenebilir (tablet)
        d = PQRDialog(self, record=self.db.get_pqr()[idx])
        if d.exec() == QDialog.DialogCode.Accepted:
            self.db.update_pqr(idx, d.get_record(), anahtar=a)
            self.refresh(); self.wps_page.refresh()

    def delete(self, idx):
        p = self.db.get_pqr()[idx]
        a = self.db.anahtar("pqr", idx)
        cnt = self.db.wps_count_for_pqr(p["no"])
        if cnt > 0:
            QMessageBox.warning(self, _("Silinemez"),
                _("<b>{d}</b>'e bağlı <b>{cnt} WPS</b> kaydı bulunmaktadır.<br>Önce bağlı WPS kayıtlarını güncelleyiniz.").format(d=p['no'], cnt=cnt))
            return
        if QMessageBox.question(self, _("Silme Onayı"),
                _("<b>{d}</b> numaralı PQR kaydı silinecek. Emin misiniz?").format(d=p['no']),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                ) == QMessageBox.StandardButton.Yes:
            self.db.delete_pqr(idx, anahtar=a); self.refresh(); self.wps_page.refresh()

    def export_json(self):
        path, __ = QFileDialog.getSaveFileName(self, _("Dışa Aktar"),
                                              _("PQR_export_{d}.json").format(d=date.today()),
                                              _("JSON Dosyaları (*.json)"))
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"tarih": str(date.today()), "pqr": self.db.get_pqr()},
                              f, ensure_ascii=False, indent=2)
            except OSError as e:
                ToastNotification.notify(self.window(), _("Dışa aktarılamadı: {e}").format(e=e), "error")
                return
            ToastNotification.notify(self.window(), _("PQR verileri JSON'a aktarıldı."), "success")

    def export_excel(self):
        headers = [_(c[0]) for c in C.COLS_PQR] + [_("Notlar")]
        rows = []
        for p in self.db.get_pqr():
            row = []
            for __, key, __ in C.COLS_PQR:
                if key == "_wps_count":
                    row.append(self.db.wps_count_for_pqr(p.get("no")))
                else:
                    v = p.get(key, "") or ""
                    row.append(dil.deger(v) if key in ("durum", "pwht", "onisitma", "test") else v)
            row.append(p.get("notlar", ""))
            rows.append(row)
        path = export_xlsx(self, f"PQR_Listesi_{date.today()}.xlsx", "PQR", headers, rows)
        if path:
            ToastNotification.notify(self.window(), _("PQR listesi Excel'e aktarıldı."), "success")


# ── STANDART SAYFASI ────────────────────────────────────────────────
class STDPage(QWidget):
    def __init__(self, db, on_data_changed=None):
        super().__init__()
        self.db = db
        self.on_data_changed = on_data_changed
        self._worker = None
        self._sort_col = -1
        self._sort_asc = True
        self._build()
        self.refresh()

    def _build(self):
        L = QVBoxLayout(self); L.setContentsMargins(24, 20, 24, 16); L.setSpacing(10)
        L.addWidget(page_header(_("Standart Takibi"),
                                _("Takip edilen standartların güncellik kontrolü ve sürüm yönetimi")))

        self.alert_frame = QFrame(); self.alert_frame.setObjectName("alert_bar")
        self.alert_frame.setVisible(False)
        al = QHBoxLayout(self.alert_frame); al.setContentsMargins(14, 10, 14, 10)
        self.alert_label = QLabel(); self.alert_label.setWordWrap(True)
        self.alert_label.setStyleSheet(f"color:{theme.t('val_amber')}; font-size:13px;")
        al.addWidget(QLabel("⚠️")); al.addWidget(self.alert_label, 1)
        L.addWidget(self.alert_frame)

        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet(f"color:{theme.t('val_blue')}; font-size:12px;")
        self.progress_label.setVisible(False)
        L.addWidget(self.progress_label)

        tb = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText(_("🔍  Standart No, Başlık..."))
        self.search.setFixedWidth(230); gecikmeli_arama(self.search, self.refresh)
        self.cmb_org = QComboBox(); self.cmb_org.addItem(_("Tüm Kuruluşlar"), "")
        for x in C.ORGANIZASYONLAR:
            self.cmb_org.addItem(x, x)
        self.cmb_org.currentIndexChanged.connect(self.refresh)
        self.cmb_status = QComboBox()
        for txt, val in [(_("Tüm Durumlar"), ""), (_("Güncel"), "guncel"), (_("Güncelleme Var"), "guncelleme"),
                         (_("Kontrol Edilmedi"), "kontrol"), (_("Manuel Kontrol"), "manuel"),
                         (_("Kontrol Hatası"), "hata")]:
            self.cmb_status.addItem(txt, val)
        self.cmb_status.currentIndexChanged.connect(self.refresh)
        self.btn_check = QPushButton(_("🔄  Güncelleme Kontrol")); self.btn_check.clicked.connect(self.manual_check)
        self.btn_check.setVisible(_duzenleyebilir(self.db))
        bn = QPushButton(_("＋  Standart Ekle")); bn.setObjectName("btn_primary"); bn.clicked.connect(self.add)
        self.btn_yeni = bn; bn.setVisible(_duzenleyebilir(self.db))
        be = export_button(self.export_excel, self.export_json)
        tb.addWidget(self.search); tb.addWidget(self.cmb_org); tb.addWidget(self.cmb_status)
        tb.addStretch(); tb.addWidget(be); tb.addWidget(self.btn_check); tb.addWidget(bn)
        L.addLayout(tb)

        self.table = QTableWidget()
        self.table.setColumnCount(len(C.COLS_STD) + 1)
        self.table.setColumnHidden(len(C.COLS_STD), not _duzenleyebilir(self.db))   # Düzenle/Sil
        self.table.setHorizontalHeaderLabels([_(c[0]) for c in C.COLS_STD] + [_("İşlem")])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True); self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        hdr = self.table.horizontalHeader()
        hdr.setSortIndicatorShown(True)
        hdr.sectionClicked.connect(self._on_header_clicked)
        apply_col_widths(self.table, C.COLS_STD)
        L.addWidget(self.table)

    def _on_header_clicked(self, col):
        if col == len(C.COLS_STD):
            return
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        self.table.horizontalHeader().setSortIndicator(
            col, Qt.SortOrder.AscendingOrder if self._sort_asc else Qt.SortOrder.DescendingOrder)
        self.refresh()

    def refresh(self):
        s = self.search.text()
        of = self.cmb_org.currentData() or ""
        sf = self.cmb_status.currentData() or ""
        data = [(i, d) for i, d in enumerate(self.db.get_std())
                if matches_query(s, d.get("no", ""), d.get("title", ""), d.get("org", ""))
                and (not of or d.get("org") == of)
                and (not sf or d.get("status") == sf)]
        if 0 <= self._sort_col < len(C.COLS_STD):
            key = C.COLS_STD[self._sort_col][1]
            rev = not self._sort_asc
            if key == "status":
                _ord = {"guncel": 0, "guncelleme": 1, "manuel": 2, "kontrol": 3, "hata": 4}
                data.sort(key=lambda x: _ord.get(x[1].get("status", ""), 99), reverse=rev)
            else:
                data.sort(key=lambda x, k=key: tr_fold(x[1].get(k, "") or ""), reverse=rev)
        self.table.setRowCount(len(data))
        for row, (real_idx, d) in enumerate(data):
            self.table.setRowHeight(row, 42)
            for col, (__, key, __) in enumerate(C.COLS_STD):
                if key == "status":
                    skey = d.get("status", "kontrol")
                    std_status = theme.status("std")
                    lbl, bg, fg = std_status.get(skey, std_status["kontrol"])
                    self.table.setItem(row, col, badge_item(_(lbl), bg, fg))   # ikon etikette
                elif key == "org":
                    bg, fg = theme.badge_info()
                    self.table.setItem(row, col, badge_item(d.get("org", "-"), bg, fg))
                elif key == "lastCheck":
                    val = d.get("lastCheck", "") or _("Hiç kontrol edilmedi")
                    it = ro_item(val); it.setForeground(QColor(theme.t("val_slate")))
                    self.table.setItem(row, col, it)
                elif key == "lastVer":
                    val = d.get("manualLastVer", "") or d.get("lastVer", "") or "-"
                    self.table.setItem(row, col, ro_item(val))
                elif key == "title":
                    it = ro_item(d.get("title", "")); it.setToolTip(d.get("title", ""))
                    self.table.setItem(row, col, it)
                else:
                    self.table.setItem(row, col, ro_item(d.get(key, "")))
            cell = make_action_cell(
                lambda _, i=real_idx: self.edit(i),
                lambda _, i=real_idx: self.delete(i),
            )
            self.table.setCellWidget(row, len(C.COLS_STD), cell)
        self._update_alert()
        if self.on_data_changed:
            self.on_data_changed()

    def _update_alert(self):
        updates = [d for d in self.db.get_std() if d.get("status") == "guncelleme"]
        manuels = [d for d in self.db.get_std() if d.get("status") == "manuel"]
        parts = []
        if updates:
            parts.append(_("{d} standartta güncelleme var: {d2}").format(d=len(updates), d2=_kisalt(d['no'] for d in updates)))
        if manuels:
            parts.append(_("{d} standart manuel kontrol bekliyor: {d2}").format(d=len(manuels), d2=_kisalt(d['no'] for d in manuels)))
        if parts:
            self.alert_label.setText("  |  ".join(parts))
            self.alert_frame.setVisible(True)
        else:
            self.alert_frame.setVisible(False)

    def _run_check(self, records, silent=False):
        if not has_api_key():
            if not silent:
                QMessageBox.warning(
                    self, _("API Anahtarı Gerekli"),
                    _("Otomatik standart kontrolü için Gemini API anahtarı bulunamadı.\n\n"
                    "Anahtarı şu iki yoldan biriyle tanımlayın:\n"
                    "  1) GEMINI_API_KEY ortam değişkeni, veya\n"
                    "  2) data/api_key.txt dosyası (tek satır anahtar).\n\n"
                    "Yeni anahtar: https://aistudio.google.com/apikey"))
            return
        if self._worker and self._worker.isRunning():
            if not silent:
                QMessageBox.information(self, _("Bilgi"), _("Kontrol devam ediyor, lütfen bekleyin."))
            return
        self.btn_check.setEnabled(False)
        self.btn_check.setText(_("⏳  Kontrol ediliyor..."))
        self.progress_label.setText(_("0 / {d} standart kontrol edildi...").format(d=len(records)))
        self.progress_label.setVisible(True)
        self._checked = 0; self._total = len(records); self._skipped = 0
        self._silent = silent
        # İşçi indeks bildirir; kontrol dakikalar sürer ve bu arada liste (tablet) değişebilir:
        # sonuç kayda id ile eşlenir
        self._kontrol_idleri = {i: self.db.anahtar("std", i)[0] for i, __ in records}
        self._worker = CheckWorker(records)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, db_idx, last_ver, title, status):
        self._checked += 1
        self.progress_label.setText(_("{checked} / {total} standart kontrol edildi...").format(checked=self._checked, total=self._total))
        if status == "skip":
            self._skipped += 1
            return
        try:
            self._sonucu_yaz(db_idx, last_ver, title, status)
        except CakismaHatasi:   # tablet az önce yazdı: liste yenilendi, id ile tekrar eşlenir
            self._sonucu_yaz(db_idx, last_ver, title, status)
        self.refresh()

    def _sonucu_yaz(self, db_idx, last_ver, title, status):
        i = self.db.indeks("std", self._kontrol_idleri.get(db_idx))
        if i is None:
            return   # kontrol sürerken kayıt silinmiş
        rec = self.db.get_std()[i]
        my_ver = str(rec.get("myVer") or "").strip()
        manual = (rec.get("manualLastVer") or "").strip()
        if manual:
            final_status = compare_std_status(my_ver, manual)
            self.db.mark_std_checked(i, manual, final_status, title)
        elif status in ("hata", "kontrol", "manuel"):
            self.db.mark_std_checked(i, last_ver or rec.get("lastVer", ""), status, title)
        else:
            final_status = compare_std_status(my_ver, last_ver)
            self.db.mark_std_checked(i, last_ver, final_status, title)

    def _on_finished(self, total, updates, manuel):
        self.btn_check.setEnabled(True)
        self.btn_check.setText(_("🔄  Güncelleme Kontrol"))
        self.progress_label.setVisible(False)
        self.refresh()
        skipped = getattr(self, "_skipped", 0)
        checked = total - skipped
        msg = _("{checked} standart kontrol edildi.\n").format(checked=checked)
        msg += (_("\n⚠️  {} standartta güncelleme tespit edildi!").format(updates)
                if updates else _("\n✅  Otomatik kontrol edilen standartlar güncel."))
        if manuel:
            msg += (_("\n\n👤  {manuel} standart için otomatik veri alınamadı.\nBu standartları düzenleyip 'Son Sürüm (Manuel)' alanına\ngüncel sürümü girebilirsiniz.").format(manuel=manuel))
        if skipped:
            msg += (_("\n\n⏳  {skipped} standart API kotası/bağlantı nedeniyle kontrol edilemedi.\nMevcut bilgileri korundu — birkaç dakika sonra tekrar deneyin.").format(skipped=skipped))
        # Otomatik (haftalık) kontrol işi bölmez: pencere yalnız bulgu varsa (kullanıcı kararı,
        # Antigravity BULGU-12); elle başlatılan kontrolde her zaman
        if not getattr(self, "_silent", False) or updates or manuel:
            QMessageBox.information(self, _("Kontrol Tamamlandı"), msg)

    def kontrol_suruyor(self):
        return bool(self._worker and self._worker.isRunning())

    def kontrolu_durdur(self):
        """Kapanışta (Antigravity BULGU-04): QThread çalışırken yok edilirse program çöker. İşçi
        veritabanına yazmaz (yalnız ağ isteği + sinyal); süren istek 3 sn'de bitmezse kesilir."""
        w = self._worker
        if w is None or not w.isRunning():
            return
        w.requestInterruption()
        if not w.wait(3000):
            w.terminate()
            w.wait()

    def auto_check_standards(self):
        """Haftada 1 otomatik tarama — günden bağımsız.

        Hafta, config.STD_OTO_KONTROL_GUNU gününde başlar (varsayılan Pazartesi).
        Bu hafta içinde hiç kontrol edilmemiş kayıtlar, program haftanın hangi
        günü açılırsa açılsın taranır; böylece pazartesi açılmayan bilgisayarda
        tarama kaçmaz, haftanın ilk açılışında yapılır. Aynı hafta içinde
        ikinci kez tarama yapılmaz. Manuel kontrol butonu bundan bağımsızdır.
        """
        today = date.today()
        week_start = today - timedelta(days=(today.weekday() - C.STD_OTO_KONTROL_GUNU) % 7)

        def _bu_hafta_kontrol_edildi(d):
            lc = parse_iso(d.get("lastCheck"))
            return lc is not None and lc >= week_start

        to_check = [(i, d) for i, d in enumerate(self.db.get_std())
                    if not _bu_hafta_kontrol_edildi(d)]
        if to_check:
            self._run_check(to_check, silent=True)

    def manual_check(self):
        all_std = [(i, d) for i, d in enumerate(self.db.get_std())]
        if not all_std:
            QMessageBox.information(self, _("Bilgi"), _("Takip listesinde standart bulunmuyor."))
            return
        self._run_check(all_std)

    def add(self):
        d = STDDialog(self)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.db.add_std(d.get_record()); self.refresh()

    def edit(self, idx):
        rec = self.db.get_std()[idx]
        a = self.db.anahtar("std", idx)   # pencere açıkken liste yenilenebilir (tablet)
        d = STDDialog(self, record=rec)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.db.update_std(idx, d.get_record(existing=rec), anahtar=a); self.refresh()

    def delete(self, idx):
        s = self.db.get_std()[idx]
        a = self.db.anahtar("std", idx)
        if QMessageBox.question(self, _("Silme Onayı"),
                _("<b>{d}</b> standart kaydı silinecek. Emin misiniz?").format(d=s['no']),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                ) == QMessageBox.StandardButton.Yes:
            self.db.delete_std(idx, anahtar=a); self.refresh()

    def export_json(self):
        path, __ = QFileDialog.getSaveFileName(self, _("Dışa Aktar"),
                                              _("Standart_export_{d}.json").format(d=date.today()),
                                              _("JSON Dosyaları (*.json)"))
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"tarih": str(date.today()), "std": self.db.get_std()},
                              f, ensure_ascii=False, indent=2)
            except OSError as e:
                ToastNotification.notify(self.window(), _("Dışa aktarılamadı: {e}").format(e=e), "error")
                return
            ToastNotification.notify(self.window(), _("Standart listesi JSON'a aktarıldı."), "success")

    def export_excel(self):
        _status_lbl = {"guncel": _("Güncel"), "guncelleme": _("Güncelleme Var"),
                       "kontrol": _("Kontrol Edilmedi"), "manuel": _("Manuel Kontrol"),
                       "hata": _("Kontrol Hatası")}
        headers = [_(c[0]) for c in C.COLS_STD] + [_("Notlar")]
        rows = []
        for d in self.db.get_std():
            row = []
            for __, key, __ in C.COLS_STD:
                if key == "lastVer":
                    row.append(d.get("manualLastVer", "") or d.get("lastVer", "") or "")
                elif key == "status":
                    row.append(_status_lbl.get(d.get("status", ""), d.get("status", "")))
                else:
                    row.append(d.get(key, "") or "")
            row.append(d.get("notlar", ""))
            rows.append(row)
        path = export_xlsx(self, f"Standart_Listesi_{date.today()}.xlsx",
                           _("Standartlar"), headers, rows)
        if path:
            ToastNotification.notify(self.window(), _("Standart listesi Excel'e aktarıldı."), "success")


# ── SERTİFİKA SAYFASI ───────────────────────────────────────────────
class CertPage(QWidget):
    def __init__(self, db, on_data_changed=None):
        super().__init__()
        self.db = db
        self.on_data_changed = on_data_changed
        self._row_map = {}
        self._sort_col = -1
        self._sort_asc = True
        self._build()
        self.refresh()

    def _build(self):
        L = QVBoxLayout(self); L.setContentsMargins(24, 20, 24, 16); L.setSpacing(12)
        L.addWidget(page_header(_("Sertifika Takibi"),
                                _("Sistem ve firma belgelerinin geçerlilik durumunu izleyin")))
        sr = QHBoxLayout()
        self.s_total = stat_card(_("Toplam Sertifika"), sr, icon="📜", accent="amber")
        self.s_valid = stat_card(_("Geçerli"), sr, icon=ICON_OK, accent="green")
        self.s_soon = stat_card(_("Yakında Dolacak"), sr, icon=ICON_WARN, accent="amber")
        self.s_exp = stat_card(_("Süresi Dolmuş"), sr, icon=ICON_BAD, accent="rose")
        sr.addStretch(); L.addLayout(sr)

        self.alert_frame = QFrame(); self.alert_frame.setObjectName("alert_bar")
        self.alert_frame.setVisible(False)
        al = QHBoxLayout(self.alert_frame); al.setContentsMargins(14, 10, 14, 10)
        self.alert_label = QLabel(); self.alert_label.setWordWrap(True)
        self.alert_label.setStyleSheet(f"color:{theme.t('val_amber')}; font-size:13px;")
        al.addWidget(QLabel("⚠️")); al.addWidget(self.alert_label, 1)
        L.addWidget(self.alert_frame)

        tb = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText(_("🔍  Belge No, Sertifika, Kuruluş..."))
        self.search.setFixedWidth(250); gecikmeli_arama(self.search, self.refresh)
        self.cmb_status = QComboBox()
        for txt, val in [(_("Tüm Durumlar"), ""), (_("Geçerli"), "gecerli"),
                         (_("Yakında Dolacak"), "yakinda"), (_("Süresi Dolmuş"), "dolmus"),
                         (_("Tarih Girilmedi"), "belirsiz")]:
            self.cmb_status.addItem(txt, val)
        self.cmb_status.currentIndexChanged.connect(self.refresh)
        bn = QPushButton(_("＋  Sertifika Ekle")); bn.setObjectName("btn_primary"); bn.clicked.connect(self.add)
        self.btn_yeni = bn; bn.setVisible(_duzenleyebilir(self.db))
        be = export_button(self.export_excel, self.export_json)
        tb.addWidget(self.search); tb.addWidget(self.cmb_status)
        tb.addStretch(); tb.addWidget(be); tb.addWidget(bn)
        L.addLayout(tb)

        self.table = QTableWidget()
        self.table.setColumnCount(len(C.COLS_CERT) + 1)
        self.table.setColumnHidden(len(C.COLS_CERT), not _duzenleyebilir(self.db))   # Düzenle/Sil
        self.table.setHorizontalHeaderLabels([_(c[0]) for c in C.COLS_CERT] + [_("İşlem")])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True); self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        hdr = self.table.horizontalHeader()
        hdr.setSortIndicatorShown(True)
        hdr.sectionClicked.connect(self._on_header_clicked)
        apply_col_widths(self.table, C.COLS_CERT)
        L.addWidget(self.table)

    @staticmethod
    def _kalan_text(status, kalan):
        if status == "belirsiz" or kalan is None:
            return "-"
        if kalan < 0:
            return _("{d} gün önce doldu").format(d=abs(kalan))
        if kalan == 0:
            return _("Bugün doluyor")
        return _("{kalan} gün kaldı").format(kalan=kalan)

    def _on_header_clicked(self, col):
        if col == len(C.COLS_CERT):
            return
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        self.table.horizontalHeader().setSortIndicator(
            col, Qt.SortOrder.AscendingOrder if self._sort_asc else Qt.SortOrder.DescendingOrder)
        self.refresh()

    def refresh(self):
        s = self.search.text()
        sf = self.cmb_status.currentData() or ""
        data = []
        for i, c in enumerate(self.db.get_cert()):
            status, kalan = cert_status(c, C.CERT_UYARI_GUN)
            if not matches_query(s, c.get("no", ""), c.get("ad", ""), c.get("org", ""),
                                 c.get("kapsam", ""), c.get("folder_no", "")):
                continue
            if sf and status != sf:
                continue
            data.append((i, c, status, kalan))

        if 0 <= self._sort_col < len(C.COLS_CERT):
            key = C.COLS_CERT[self._sort_col][1]
            rev = not self._sort_asc
            if key == "_kalan":
                data.sort(key=lambda x: x[3] if x[3] is not None else (99999 if self._sort_asc else -99999),
                          reverse=rev)
            elif key == "_durum":
                _ord = {"dolmus": 0, "yakinda": 1, "gecerli": 2, "belirsiz": 3}
                data.sort(key=lambda x: _ord.get(x[2], 99), reverse=rev)
            else:
                data.sort(key=lambda x, k=key: tr_fold(x[1].get(k, "") or ""), reverse=rev)

        self._row_map = {}
        self.table.setRowCount(len(data))
        for row, (real_idx, c, status, kalan) in enumerate(data):
            self._row_map[row] = real_idx
            self.table.setRowHeight(row, 42)
            for col, (__, key, __) in enumerate(C.COLS_CERT):
                if key == "_durum":
                    cert_st = theme.status("cert")
                    lbl, bg, fg = cert_st.get(status, cert_st["belirsiz"])
                    self.table.setItem(row, col, badge_item(_(lbl), bg, fg))   # ikon etikette
                elif key == "_kalan":
                    it = ro_item(self._kalan_text(status, kalan), Qt.AlignmentFlag.AlignCenter)
                    if status == "dolmus":
                        it.setForeground(QColor(theme.t("val_red")))
                    elif status == "yakinda":
                        it.setForeground(QColor(theme.t("val_amber")))
                    else:
                        it.setForeground(QColor(theme.t("val_slate")))
                    self.table.setItem(row, col, it)
                elif key == "ad":
                    ad = c.get("ad", "")
                    fn = c.get("folder_no", "")
                    it = ro_item(f"{fn} - {ad}" if fn else ad)
                    it.setForeground(QColor(theme.t("val_purple")))
                    self.table.setItem(row, col, it)
                elif key == "kapsam":
                    it = ro_item(c.get("kapsam", "")); it.setToolTip(c.get("kapsam", ""))
                    self.table.setItem(row, col, it)
                else:
                    self.table.setItem(row, col, ro_item(c.get(key, "")))
            cell = make_action_cell(
                lambda _, i=real_idx: self.edit(i),
                lambda _, i=real_idx: self.delete(i),
            )
            self.table.setCellWidget(row, len(C.COLS_CERT), cell)

        self._update_stats_and_alert()
        if self.on_data_changed:
            self.on_data_changed()

    def _update_stats_and_alert(self):
        certs = self.db.get_cert()
        counts = {"gecerli": 0, "yakinda": 0, "dolmus": 0, "belirsiz": 0}
        soon_names, exp_names = [], []
        for c in certs:
            st, __ = cert_status(c, C.CERT_UYARI_GUN)
            counts[st] += 1
            if st == "yakinda":
                soon_names.append(c.get("no", "") or c.get("ad", ""))
            elif st == "dolmus":
                exp_names.append(c.get("no", "") or c.get("ad", ""))
        self.s_total.setText(str(len(certs)))
        self.s_valid.setText(str(counts["gecerli"]))
        self.s_soon.setText(str(counts["yakinda"]))
        self.s_exp.setText(str(counts["dolmus"]))

        parts = []
        if exp_names:
            parts.append(_("{d} sertifikanın süresi doldu: {d2}").format(d=len(exp_names), d2=_kisalt(exp_names)))
        if soon_names:
            parts.append(_("{d} sertifika yakında dolacak: {d2}").format(d=len(soon_names), d2=_kisalt(soon_names)))
        if parts:
            self.alert_label.setText("  |  ".join(parts))
            self.alert_frame.setVisible(True)
        else:
            self.alert_frame.setVisible(False)

    def add(self):
        d = CertDialog(self)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.db.add_cert(d.get_record()); self.refresh()

    def edit(self, idx):
        orig = self.db.get_cert()[idx]
        a = self.db.anahtar("cert", idx)  # pencere açıkken liste yenilenebilir (tablet)
        d = CertDialog(self, record=orig)
        if d.exec() == QDialog.DialogCode.Accepted:
            rec = d.get_record()
            if orig.get("folder_no"):        # klasör no'yu düzenlemede koru
                rec["folder_no"] = orig["folder_no"]
            self.db.update_cert(idx, rec, anahtar=a); self.refresh()

    def delete(self, idx):
        c = self.db.get_cert()[idx]
        a = self.db.anahtar("cert", idx)
        if QMessageBox.question(self, _("Silme Onayı"),
                _("<b>{d}</b> belgesi silinecek. Emin misiniz?").format(d=c.get('no','')),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                ) == QMessageBox.StandardButton.Yes:
            self.db.delete_cert(idx, anahtar=a); self.refresh()

    def export_json(self):
        path, __ = QFileDialog.getSaveFileName(self, _("Dışa Aktar"),
                                              _("Sertifika_export_{d}.json").format(d=date.today()),
                                              _("JSON Dosyaları (*.json)"))
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"tarih": str(date.today()), "cert": self.db.get_cert()},
                              f, ensure_ascii=False, indent=2)
            except OSError as e:
                ToastNotification.notify(self.window(), _("Dışa aktarılamadı: {e}").format(e=e), "error")
                return
            ToastNotification.notify(self.window(), _("Sertifika verileri JSON'a aktarıldı."), "success")

    def export_excel(self):
        _durum_lbl = {"gecerli": _("Geçerli"), "yakinda": _("Yakında Dolacak"),
                      "dolmus": _("Süresi Doldu"), "belirsiz": _("Tarih Girilmedi")}
        headers = [_(c[0]) for c in C.COLS_CERT] + [_("Notlar")]
        rows = []
        for c in self.db.get_cert():
            status, kalan = cert_status(c, C.CERT_UYARI_GUN)
            row = []
            for __, key, __ in C.COLS_CERT:
                if key == "_kalan":
                    row.append(self._kalan_text(status, kalan))
                elif key == "_durum":
                    row.append(_durum_lbl.get(status, status))
                elif key == "ad":
                    fn = c.get("folder_no", "")
                    ad = c.get("ad", "")
                    row.append(f"{fn} - {ad}" if fn else ad)
                else:
                    row.append(c.get(key, "") or "")
            row.append(c.get("notlar", ""))
            rows.append(row)
        path = export_xlsx(self, f"Sertifika_Listesi_{date.today()}.xlsx",
                           _("Sertifikalar"), headers, rows)
        if path:
            ToastNotification.notify(self.window(), _("Sertifika listesi Excel'e aktarıldı."), "success")


# ── ANA SAYFA (DASHBOARD) ───────────────────────────────────────────
class HomePage(QWidget):
    """Genel bakış: öncelik sıralı "dikkat gerektirenler", iki grup özeti (kaynak
    prosedürleri / belge takibi) ve hızlı işlemler. Hesap app/ozet.py'de (tabletle ortak).

    2026-10-29: aynı bilgiyi 2-3 kez gösteren kartlar, dairesel grafikler ve detay
    kutuları; sürekli dönen gölge animasyonu kaldırıldı.
    """

    # (etiket, stacked indeks, sayfada çağrılacak yöntem | None)
    HIZLI = ((N_("+  Yeni WPS"), 1, "add"), (N_("+  Yeni PQR"), 2, "add"),
             (N_("+  Standart"), 3, "add"), (N_("+  Sertifika"), 4, "add"),
             (N_("📑  ITP / Kalite Planı"), 5, None))

    def __init__(self, db, tabs):
        super().__init__()
        self.db = db
        self.tabs = tabs
        self.v = {}
        self.dikkat_satirlari = []
        self._build()
        self.refresh()

    def _git(self, indeks, yontem=None):
        self.tabs.setCurrentIndex(indeks)
        if yontem:
            getattr(self.tabs.widget(indeks), yontem)()

    def _baslik(self, metin):
        lb = QLabel(metin); lb.setObjectName("home_section")
        return lb

    def _olcu(self, grid, satir, anahtar, ad):
        a = QLabel(ad); a.setObjectName("olcu_ad")
        d = QLabel("0"); d.setObjectName("olcu_deger")
        d.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(a, satir, 0); grid.addWidget(d, satir, 1)
        self.v[anahtar] = d

    def _sutun(self, baslik, toplam_anahtar, olculer):
        w = QWidget(); w.setObjectName("olcu_sutun"); g = QGridLayout(w)
        g.setContentsMargins(0, 0, 0, 0); g.setHorizontalSpacing(12); g.setVerticalSpacing(6)
        b = QLabel(baslik); b.setObjectName("olcu_baslik")
        t = QLabel("0"); t.setObjectName("olcu_toplam")
        g.addWidget(b, 0, 0, 1, 2); g.addWidget(t, 1, 0, 1, 2)
        self.v[toplam_anahtar] = t
        for i, (anahtar, ad) in enumerate(olculer, start=2):
            self._olcu(g, i, anahtar, ad)
        g.setRowStretch(len(olculer) + 2, 1)
        return w

    def _kart(self, baslik, sol, sag, dugmeler):
        k = QFrame(); k.setObjectName("home_card")
        v = QVBoxLayout(k); v.setContentsMargins(22, 18, 22, 18); v.setSpacing(14)
        t = QLabel(baslik); t.setObjectName("kart_baslik")
        v.addWidget(t)
        ic = QHBoxLayout(); ic.setSpacing(28); ic.addWidget(sol, 1); ic.addWidget(sag, 1)
        v.addLayout(ic)
        alt = QHBoxLayout(); alt.setSpacing(8)
        for ad, indeks in dugmeler:
            bt = QPushButton(f"{_(ad)}  →"); bt.setObjectName("btn_ghost")
            bt.setCursor(Qt.CursorShape.PointingHandCursor)
            bt.clicked.connect(lambda _=False, i=indeks: self._git(i))
            alt.addWidget(bt)
        alt.addStretch()
        v.addLayout(alt)
        return k

    def _build(self):
        # Küçük pencerede içerik sıkışmasın diye kaydırılabilir gövde
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        sa = QScrollArea(); sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.Shape.NoFrame)
        sa.setStyleSheet(
            "QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        body = QWidget()
        sa.setWidget(body)
        outer.addWidget(sa)
        root = QVBoxLayout(body); root.setContentsMargins(28, 22, 28, 22); root.setSpacing(10)

        self.head = QLabel(_("Genel Bakış")); self.head.setObjectName("greeting")
        root.addWidget(self.head)
        self.sub_head = QLabel(""); self.sub_head.setObjectName("home_sub")
        root.addWidget(self.sub_head)

        hizli = QHBoxLayout(); hizli.setSpacing(8)
        for ad, indeks, yontem in self.HIZLI:
            bt = QPushButton(_(ad))
            bt.setVisible(yontem is None or _duzenleyebilir(self.db))
            bt.setObjectName("btn_primary" if yontem is None else "btn_ghost")
            bt.setCursor(Qt.CursorShape.PointingHandCursor)
            bt.clicked.connect(lambda _=False, i=indeks, y=yontem: self._git(i, y))
            hizli.addWidget(bt)
        hizli.addStretch()
        root.addSpacing(6)
        root.addLayout(hizli)

        root.addSpacing(8)
        root.addWidget(self._baslik(_("DİKKAT GEREKTİRENLER")))
        self.dikkat_kutu = QVBoxLayout(); self.dikkat_kutu.setSpacing(8)
        root.addLayout(self.dikkat_kutu)

        root.addSpacing(8)
        root.addWidget(self._baslik(_("ÖZET")))
        kartlar = QHBoxLayout(); kartlar.setSpacing(16)
        kartlar.addWidget(self._kart(
            _("Kaynak prosedürleri"),
            self._sutun(_("WPS"), "wps_toplam", [("wps_aktif", _("Aktif")),
                                              ("wps_revizyon", _("Revizyon bekliyor")),
                                              ("wps_iptal", _("İptal")),
                                              ("wps_pqrsiz", _("Bağlı PQR'si yok"))]),
            self._sutun(_("PQR"), "pqr_toplam", [("pqr_gecti", _("Geçti")),
                                              ("pqr_bekliyor", _("Sonuç bekliyor")),
                                              ("pqr_basarisiz", _("Başarısız")),
                                              ("pqr_wpssiz", _("WPS'e bağlı değil"))]),
            [(_("PQR kayıtları"), 2), (_("WPS yönetimi"), 1)]), 1)
        kartlar.addWidget(self._kart(
            _("Belge takibi"),
            self._sutun(_("STANDARTLAR"), "std_toplam", [("std_guncel", _("Güncel")),
                                                      ("std_guncelleme", _("Yeni sürüm var")),
                                                      ("std_kontrol", _("Elle kontrol bekliyor")),
                                                      ("std_son_kontrol", _("Son kontrol"))]),
            self._sutun(_("SERTİFİKALAR"), "cert_toplam", [("cert_gecerli", _("Geçerli")),
                                                        ("cert_yakinda", _("Yakında dolacak")),
                                                        ("cert_dolmus", _("Süresi dolmuş")),
                                                        ("cert_en_yakin", _("En yakın bitiş"))]),
            [(_("Standartlar"), 3), (_("Sertifikalar"), 4)]), 1)
        root.addLayout(kartlar)
        root.addStretch()

    def _dikkat_listesi(self, dikkat):
        while self.dikkat_kutu.count():
            w = self.dikkat_kutu.takeAt(0).widget()
            if w is not None:
                # deleteLater olay döngüsüne kadar bekler; o arada yerleşimsiz satır
                # varsayılan boyutta sol üstte görünüyordu (sayfa başını örtüyordu)
                w.hide()
                w.deleteLater()
        self.dikkat_satirlari = []
        if not dikkat:
            lb = QLabel(_("✓  Bekleyen iş yok, her şey güncel.")); lb.setObjectName("dikkat_yok")
            self.dikkat_kutu.addWidget(lb)
            return
        etiket = {"kritik": _("KRİTİK"), "uyari": _("UYARI"), "bilgi": _("BİLGİ")}
        for d in dikkat:
            bt = QPushButton(f"{etiket[d['seviye']]}    {d['metin']}")
            bt.setObjectName("dikkat_satir")
            bt.setProperty("seviye", d["seviye"])
            bt.setCursor(Qt.CursorShape.PointingHandCursor)
            bt.setToolTip(_("İlgili sayfayı aç"))
            bt.clicked.connect(lambda _=False, i=d["sekme"]: self._git(i))
            self.dikkat_kutu.addWidget(bt)
            self.dikkat_satirlari.append(bt)

    def refresh(self):
        wps, pqr = self.db.get_wps(), self.db.get_pqr()
        std, cert = self.db.get_std(), self.db.get_cert()
        o = ozet(wps, pqr, std, cert, bugun=date.today(), uyari_gun=C.CERT_UYARI_GUN)
        for grup in (o["kaynak"], o["belge"]):
            for anahtar, deger in grup.items():
                if anahtar not in self.v:
                    continue
                if anahtar == "cert_en_yakin":
                    deger = _("{d} ({d2} gün)").format(d=deger[0], d2=deger[1]) if deger else "—"
                self.v[anahtar].setText(str(deger) if deger is not None else "—")
        self._dikkat_listesi(o["dikkat"])
        k, b = o["kaynak"], o["belge"]
        self.head.setText(self._greeting())
        self.sub_head.setText(
            _("{d}   •   {d2} WPS  ·  {d3} PQR  ·  {d4} standart  ·  {d5} sertifika   •   Ctrl+rakam ile sayfalar arasında geçin").format(d=date.today().strftime('%d.%m.%Y'), d2=k['wps_toplam'], d3=k['pqr_toplam'], d4=b['std_toplam'], d5=b['cert_toplam']))

    @staticmethod
    def _greeting():
        h = QTime.currentTime().hour()
        if h < 6:
            return _("İyi geceler 🌙")
        if h < 12:
            return _("Günaydın ☀️")
        if h < 18:
            return _("İyi günler 👋")
        return _("İyi akşamlar 🌆")
