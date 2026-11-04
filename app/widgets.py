# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""
Paylaşılan UI yardımcıları: rozet/salt-okunur hücreler, sayfa başlığı,
işlem (düzenle/sil) hücresi, istatistik kartı, aralık ayrıştırıcı ve
satır ekle/sil destekli düzenlenebilir tablo (EditableTable).

v4.0 — Eklenenler: ToastNotification
2026-10-29 — Kaldırılanlar (hız): CircularProgressBar, FadingStackedWidget, HoverCard,
attach_pulse, animate_count, _add_glow (gölge/opaklık efektleri sürekli yeniden çizim yapıyordu)
"""

import re

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressBar, QGraphicsOpacityEffect, QApplication, QMenu
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, QPoint
from PyQt6.QtGui import QColor

from . import theme
from .dil import N_, _


# Durum rozetlerinde kullanılan küçük ikonlar
ICON_OK = "✓"
ICON_WARN = "▲"
ICON_BAD = "✕"
ICON_NEUTRAL = "●"


def _rgba(hexc, a):
    """'#rrggbb' + alfa → 'rgba(r,g,b,a)' (QSS için)."""
    hexc = hexc.lstrip("#")
    r, g, b = int(hexc[0:2], 16), int(hexc[2:4], 16), int(hexc[4:6], 16)
    return f"rgba({r},{g},{b},{a})"


# ── Yeni: Toast Bildirimi ───────────────────────────────────────────
class ToastNotification(QFrame):
    """Pencerenin sağ alt köşesinde beliren modern anlık bildirim (Toast).

    Ana pencerenin çocuğu (child widget) olarak konumlanır; böylece
    koordinatlar pencereye göre doğru hesaplanır.
    """

    def __init__(self, parent, message, type_="success", duration_ms=3000):
        super().__init__(parent)
        self.setObjectName("toast")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Tema ayarlaması
        bg_color = "rgba(16, 185, 129, 0.9)" if type_ == "success" else "rgba(239, 68, 68, 0.9)"
        if type_ == "info": bg_color = "rgba(59, 130, 246, 0.9)"
        if type_ == "warning": bg_color = "rgba(245, 158, 11, 0.9)"
        
        icon = {"success": "✅", "error": "❌", "info": "ℹ", "warning": "⚠️"}.get(type_, "ℹ")
        
        self.setStyleSheet(f"""
            QFrame#toast {{
                background-color: {bg_color};
                border-radius: 8px;
            }}
            QLabel {{
                color: white;
                font-size: 13px;
                font-weight: 600;
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        
        icon_lbl = QLabel(icon)
        msg_lbl = QLabel(message)
        
        layout.addWidget(icon_lbl)
        layout.addWidget(msg_lbl)
        
        self.adjustSize()
        
        # Efektler
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0)
        
        self.duration_ms = duration_ms
        self.parent_widget = parent

    def show_toast(self):
        # DİKKAT: Qt'nin QWidget.show() metodu gölgelenmemeli — statik
        # yardımcının adı bu yüzden `notify` (eskiden `show` idi ve toast'ın
        # hiç görünmemesine yol açıyordu).
        self.show()
        self.raise_()

        # Konumlandırma (Sağ alt köşe, margin: 24px)
        parent_rect = self.parent_widget.rect()
        target_x = parent_rect.width() - self.width() - 24
        target_y = parent_rect.height() - self.height() - 24
        start_y = target_y + 30

        self.move(target_x, start_y)
        
        # Görünme animasyonu
        self.anim_group = QPropertyAnimation(self, b"pos")
        self.anim_group.setDuration(400)
        self.anim_group.setStartValue(QPoint(target_x, start_y))
        self.anim_group.setEndValue(QPoint(target_x, target_y))
        self.anim_group.setEasingCurve(QEasingCurve.Type.OutBack)
        
        self.fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in.setDuration(400)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        
        self.anim_group.start()
        self.fade_in.start()
        
        # Kapanma Timer'ı
        QTimer.singleShot(self.duration_ms, self.hide_toast)

    def hide_toast(self):
        self.fade_out = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_out.setDuration(500)
        self.fade_out.setStartValue(1.0)
        self.fade_out.setEndValue(0.0)
        self.fade_out.finished.connect(self.deleteLater)
        self.fade_out.start()
        
    @staticmethod
    def notify(parent, message, type_="success", duration=3000):
        if parent is None:
            return
        toast = ToastNotification(parent, message, type_, duration)
        toast.show_toast()


# ── Yeni: Geçiş Efektli StackedWidget ───────────────────────────────
# ── Mevcut Tablo ve Badge Yardımcıları ──────────────────────────────
def badge_item(text, bg, fg, icon=None):
    label = f"{icon}  {text}" if icon else text
    item = QTableWidgetItem(label)
    item.setBackground(QColor(bg))
    item.setForeground(QColor(fg))
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item

def ro_item(text, align=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft):
    item = QTableWidgetItem(str(text) if text not in (None, "") else "-")
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    item.setTextAlignment(align)
    return item

def page_header(title, subtitle):
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(0, 0, 0, 8)
    v.setSpacing(4)
    t = QLabel(title)
    t.setStyleSheet(
        f"font-size:22px; font-weight:bold; color:{theme.t('text_bright')}; "
        "letter-spacing:-0.3px;"
    )
    s = QLabel(subtitle)
    s.setStyleSheet(f"font-size:12px; color:{theme.t('text_muted')}; letter-spacing:0.2px;")

    line = QFrame()
    line.setFixedHeight(2)
    line.setStyleSheet(
        "background: qlineargradient(x1:0,y1:0,x2:1,y2:0, "
        f"stop:0 {theme.t('accent_blue')}, stop:0.5 {theme.t('accent_violet')}, stop:1 transparent); "
        "border:none; border-radius:1px;"
    )

    v.addWidget(t)
    v.addWidget(s)
    v.addWidget(line)
    return w

def gecikmeli_arama(line_edit, fn, ms=200):
    """Arama kutusu: her harfte değil, yazma `ms` kadar durunca fn çağrılır (tablo kurulumu
    yüzlerce satırda 100+ ms sürer; her tuşta kurulunca yazma takılıyordu)."""
    t = QTimer(line_edit)
    t.setSingleShot(True)
    t.setInterval(ms)
    t.timeout.connect(fn)
    line_edit.textChanged.connect(lambda _metin: t.start())
    line_edit._arama_zamanlayici = t
    return t


def export_button(on_excel, on_json):
    """Excel/JSON seçenekli 'Dışa Aktar' menü butonu."""
    b = QPushButton(_("⬇  Dışa Aktar"))
    menu = QMenu(b)
    menu.addAction(_("📊  Excel (.xlsx)"), on_excel)
    menu.addAction(_("🗂  JSON (.json)"), on_json)
    b.setMenu(menu)
    return b


def make_action_cell(on_edit, on_delete):
    # Stil tema QSS'inde (#act_cell/#act_edit/#act_del): satır başına setStyleSheet her
    # tabloda yüzlerce kez QSS ayrıştırıyordu (262 standartta ~320 ms yenileme)
    cell = QWidget()
    cell.setObjectName("act_cell")
    hl = QHBoxLayout(cell)
    hl.setContentsMargins(0, 0, 0, 0)
    hl.setSpacing(6)
    hl.setAlignment(Qt.AlignmentFlag.AlignCenter)

    be = QPushButton("✎")
    be.setObjectName("act_edit")
    be.setFixedSize(26, 26)
    be.setCursor(Qt.CursorShape.PointingHandCursor)
    be.setToolTip(_("Düzenle"))

    bd = QPushButton("✕")
    bd.setObjectName("act_del")
    bd.setFixedSize(26, 26)
    bd.setCursor(Qt.CursorShape.PointingHandCursor)
    bd.setToolTip(_("Sil"))

    be.clicked.connect(on_edit)
    bd.clicked.connect(on_delete)
    hl.addWidget(be)
    hl.addWidget(bd)
    return cell

def stat_card(label, parent, size=(212, 88), icon=None, accent="blue"):
    # accent bir aksan adı ('blue','green'...) veya doğrudan hex olabilir
    accent = theme.accent(accent) if accent in theme.ACCENTS else accent
    f = QFrame()
    f.setObjectName("stat_card")
    # Sabit genişlik dar pencerede kartların üst üste binmesine yol açıyordu;
    # kartlar gerektiğinde daralabilir, yükseklik sabit kalır
    f.setMinimumWidth(150)
    f.setMaximumWidth(size[0])
    f.setFixedHeight(size[1])

    v = QVBoxLayout(f)
    v.setContentsMargins(16, 12, 16, 12)
    v.setSpacing(4)

    top = QHBoxLayout(); top.setSpacing(8)
    lb = QLabel(label)
    lb.setObjectName("stat_label")
    top.addWidget(lb); top.addStretch()
    if icon:
        ic = QLabel(icon)
        ic.setFixedSize(26, 26)
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet(
            f"font-size:13px; background:{_rgba(accent, 0.14)}; "
            f"color:{accent}; border-radius:8px;"
        )
        top.addWidget(ic)

    vl = QLabel("0")
    vl.setObjectName("stat_value")

    v.addLayout(top)
    v.addWidget(vl)
    parent.addWidget(f)


    return vl

def parse_range(s):
    if not s:
        return None
    nums = re.findall(r"\d+(?:[.,]\d+)?", str(s))
    if not nums:
        return None
    vals = [float(n.replace(",", ".")) for n in nums]
    return (min(vals), max(vals))

def apply_col_widths(table, cols):
    for i, (__, __, w) in enumerate(cols):
        table.setColumnWidth(i, w)


def ro_table(rows, cols, max_rows=12):
    t = QTableWidget()
    t.setColumnCount(len(cols))
    t.setHorizontalHeaderLabels([_(c[1]) for c in cols])
    t.setRowCount(len(rows))
    t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    t.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
    t.verticalHeader().setVisible(False)
    t.setAlternatingRowColors(True)
    for r, row in enumerate(rows):
        for c, (key, __) in enumerate(cols):
            it = QTableWidgetItem(str(row.get(key, "") or "-"))
            it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            t.setItem(r, c, it)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setFixedHeight(min(len(rows), max_rows) * 30 + 32)
    return t

class EditableTable(QWidget):
    def __init__(self, cols, height=170, add_label=N_("＋ Satır Ekle")):
        super().__init__()
        self.cols = cols
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(6)

        self.table = QTableWidget()
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels([_(c[1]) for c in cols])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setFixedHeight(height)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        v.addWidget(self.table)

        bar = QHBoxLayout(); bar.setSpacing(6)
        add = QPushButton(_(add_label)); add.setObjectName("btn_small"); add.clicked.connect(self.add_row)
        rem = QPushButton(_("－ Seçili Satırı Sil")); rem.setObjectName("btn_small")
        rem.clicked.connect(self.remove_selected)
        bar.addWidget(add); bar.addWidget(rem); bar.addStretch()
        v.addLayout(bar)

    def add_row(self, values=None):
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setRowHeight(r, 30)
        for c, (key, __) in enumerate(self.cols):
            val = (values or {}).get(key, "") if values else ""
            self.table.setItem(r, c, QTableWidgetItem(str(val) if val else ""))

    def remove_selected(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        if not rows:
            r = self.table.rowCount()
            if r:
                self.table.removeRow(r - 1)
            return
        for r in rows:
            self.table.removeRow(r)

    def set_rows(self, rows):
        self.table.setRowCount(0)
        for row in (rows or []):
            self.add_row(row)

    def get_rows(self):
        out = []
        for r in range(self.table.rowCount()):
            rec = {}
            has_value = False
            for c, (key, __) in enumerate(self.cols):
                it = self.table.item(r, c)
                txt = it.text().strip() if it else ""
                rec[key] = txt
                if txt:
                    has_value = True
            if has_value:
                out.append(rec)
        return out
