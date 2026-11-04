# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""
Program içi basit kaynak şematik çizim modülü.

`DiagramCanvas` vektör tabanlı bir tuvaldir; şekiller (serbest kalem, çizgi,
dikdörtgen, elips, metin) JSON'a serileştirilip `data.json` içindeki WPS/PQR
kaydına gömülür ve yeniden düzenlenebilir. `DiagramPane` tuvali bir araç
çubuğu ile sarmalar (diyaloglarda kullanılır).

Özellikler:
- Çizim araçları + hazır kaynak şablonları (alın / köşe kaynağı).
- "Seç" aracıyla şekilleri fareyle tutup taşıma ve köşe tutamaklarından
  yeniden boyutlandırma.

Koordinatlar sabit bir mantıksal tuval boyutunda (CANVAS_W × CANVAS_H)
saklanır; böylece düzenleme ve salt-okunur görünüm birebir aynı görünür.
"""

import copy

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QButtonGroup,
    QColorDialog, QInputDialog, QSpinBox, QLabel, QScrollArea, QFrame,
)
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QPen, QColor, QPainterPath, QFont
from .dil import N_, _

CANVAS_W = 720
CANVAS_H = 440
PAPER = "#ffffff"      # tema bağımsız beyaz zemin (şematik okunaklı kalsın)
PAPER_BORDER = "#cbd5e1"
DEFAULT_COLOR = "#111827"
WELD_COLOR = "#dc2626"     # kaynak dikişi vurgusu
HANDLE = 7                 # köşe tutamak yarı-boyutu
_OPPOSITE = {"tl": "br", "tr": "bl", "bl": "tr", "br": "tl"}


# ── Hazır kaynak şablonları ─────────────────────────────────────────
def butt_weld_template(ox=200, oy=150):
    """Alın kaynağı (tek-V) kesit şablonu — şekil listesi döndürür."""
    c, w = DEFAULT_COLOR, 2
    return [
        # İki levha (sol / sağ)
        {"type": "rect", "x": ox, "y": oy + 60, "w": 130, "h": 45, "color": c, "width": w},
        {"type": "rect", "x": ox + 190, "y": oy + 60, "w": 130, "h": 45, "color": c, "width": w},
        # V ağzı (kök noktasında birleşir)
        {"type": "line", "x1": ox + 130, "y1": oy + 60, "x2": ox + 160, "y2": oy + 105,
         "color": c, "width": w},
        {"type": "line", "x1": ox + 190, "y1": oy + 60, "x2": ox + 160, "y2": oy + 105,
         "color": c, "width": w},
        # Kaynak dikişi (taç) — kırmızı vurgu
        {"type": "ellipse", "x": ox + 125, "y": oy + 42, "w": 70, "h": 26,
         "color": WELD_COLOR, "width": 2},
        {"type": "text", "x": ox + 95, "y": oy + 135, "text": _("Alın Kaynağı (V)"),
         "color": c, "size": 14},
    ]


def fillet_weld_template(ox=240, oy=120):
    """Köşe (fillet) kaynağı T-birleşim şablonu — şekil listesi döndürür."""
    c, w = DEFAULT_COLOR, 2
    return [
        # Yatay taban levhası
        {"type": "rect", "x": ox - 40, "y": oy + 130, "w": 300, "h": 40, "color": c, "width": w},
        # Dikey levha (tabana oturur)
        {"type": "rect", "x": ox + 80, "y": oy, "w": 40, "h": 130, "color": c, "width": w},
        # Sağ köşe fillet dikişi (üçgen)
        {"type": "path",
         "points": [[ox + 120, oy + 130], [ox + 120, oy + 70], [ox + 180, oy + 130], [ox + 120, oy + 130]],
         "color": WELD_COLOR, "width": 2},
        # Sol köşe fillet dikişi (üçgen)
        {"type": "path",
         "points": [[ox + 80, oy + 130], [ox + 80, oy + 70], [ox + 20, oy + 130], [ox + 80, oy + 130]],
         "color": WELD_COLOR, "width": 2},
        {"type": "text", "x": ox - 10, "y": oy + 200, "text": _("Köşe Kaynağı (Fillet)"),
         "color": c, "size": 14},
    ]


class DiagramCanvas(QWidget):
    """Vektör şekilleri tutan, fare ile çizilebilen/düzenlenebilen tuval."""

    def __init__(self, read_only=False, parent=None):
        super().__init__(parent)
        self.read_only = read_only
        self.shapes = []           # kalıcı şekiller
        self._preview = None       # sürüklerken geçici şekil
        self._start = None
        self.tool = "select" if not read_only else None
        self.color = DEFAULT_COLOR
        self.pen_width = 2
        self.text_size = 14
        # Seç/taşı/boyutlandır durumu
        self.selected = None       # seçili şekil indeksi
        self._mode = None          # "move" | "resize" | None
        self._handle = None        # "tl"/"tr"/"bl"/"br"
        self._last = None          # son fare konumu (taşıma)
        self._resize_orig = None   # boyutlandırma başlangıç kopyası
        self._resize_obbox = None
        self._resize_fixed = None
        self.setFixedSize(CANVAS_W, CANVAS_H)
        self._apply_cursor()

    def _apply_cursor(self):
        if self.read_only:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        elif self.tool == "select":
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.setCursor(Qt.CursorShape.CrossCursor)

    def set_tool(self, tool):
        self.tool = tool
        if tool != "select":
            self.selected = None
        self._apply_cursor()
        self.update()

    # ── Serileştirme ────────────────────────────────────────────────
    def to_json(self):
        return {"size": [CANVAS_W, CANVAS_H], "shapes": self.shapes}

    def from_json(self, data):
        if isinstance(data, dict):
            self.shapes = list(data.get("shapes", []) or [])
        else:
            self.shapes = []
        self._preview = None
        self.selected = None
        self.update()

    def is_empty(self):
        return not self.shapes

    def clear(self):
        self.shapes = []
        self._preview = None
        self.selected = None
        self.update()

    def undo(self):
        if self.shapes:
            self.shapes.pop()
            self.selected = None
            self.update()

    def add_shapes(self, shapes):
        """Hazır şablon vb. şekil grubunu ekler ve seç moduna geçer."""
        self.shapes.extend(copy.deepcopy(shapes))
        self.update()

    # ── Çizim ────────────────────────────────────────────────────────
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(PAPER))
        p.setPen(QPen(QColor(PAPER_BORDER), 1))
        p.drawRect(0, 0, self.width() - 1, self.height() - 1)
        for s in self.shapes:
            self._draw_shape(p, s)
        if self._preview:
            self._draw_shape(p, self._preview)
        if (not self.read_only and self.selected is not None
                and 0 <= self.selected < len(self.shapes)):
            self._draw_selection(p, self._bbox(self.shapes[self.selected]))
        p.end()

    def _draw_shape(self, p, s):
        t = s.get("type")
        pen = QPen(QColor(s.get("color", DEFAULT_COLOR)), s.get("width", 2))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        if t == "path":
            pts = s.get("points", [])
            if len(pts) >= 2:
                path = QPainterPath(QPointF(*pts[0]))
                for pt in pts[1:]:
                    path.lineTo(QPointF(*pt))
                p.drawPath(path)
            elif len(pts) == 1:
                p.drawPoint(QPointF(*pts[0]))
        elif t == "line":
            p.drawLine(QPointF(s["x1"], s["y1"]), QPointF(s["x2"], s["y2"]))
        elif t == "rect":
            p.drawRect(self._rectf(s))
        elif t == "ellipse":
            p.drawEllipse(self._rectf(s))
        elif t == "text":
            f = QFont("Segoe UI", int(s.get("size", 14)))
            p.setFont(f)
            p.drawText(QPointF(s["x"], s["y"]), s.get("text", ""))

    def _draw_selection(self, p, b):
        pen = QPen(QColor("#2563eb"), 1, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(b)
        p.setPen(QPen(QColor("#2563eb"), 1))
        p.setBrush(QColor("#ffffff"))
        for pt in self._corners(b).values():
            p.drawRect(QRectF(pt.x() - HANDLE, pt.y() - HANDLE, HANDLE * 2, HANDLE * 2))

    @staticmethod
    def _rectf(s):
        return QRectF(s["x"], s["y"], s["w"], s["h"]).normalized()

    @staticmethod
    def _corners(b):
        return {"tl": b.topLeft(), "tr": b.topRight(),
                "bl": b.bottomLeft(), "br": b.bottomRight()}

    # ── Fare etkileşimi ──────────────────────────────────────────────
    def mousePressEvent(self, e):
        if self.read_only or e.button() != Qt.MouseButton.LeftButton:
            return
        pos = e.position()
        pt = [pos.x(), pos.y()]

        if self.tool == "select":
            # Önce seçili şeklin tutamağına basıldı mı?
            if self.selected is not None and 0 <= self.selected < len(self.shapes):
                h = self._handle_at(pos, self._bbox(self.shapes[self.selected]))
                if h:
                    self._begin_resize(h)
                    return
            idx = self._shape_at(pt)
            self.selected = idx
            if idx is not None:
                self._mode = "move"
                self._last = pos
            self.update()
            return

        if self.tool == "erase":
            self._erase_at(pt)
            self.update()
            return
        if self.tool == "text":
            txt, ok = QInputDialog.getText(self, _("Metin"), _("Eklenecek metin:"))
            if ok and txt.strip():
                self.shapes.append({"type": "text", "x": pt[0], "y": pt[1],
                                    "text": txt.strip(), "color": self.color,
                                    "size": self.text_size})
                self.update()
            return
        self._start = pt
        if self.tool == "pen":
            self._preview = {"type": "path", "points": [pt],
                             "color": self.color, "width": self.pen_width}
        else:
            self._preview = self._shape_from(pt, pt)

    def mouseMoveEvent(self, e):
        if self.read_only:
            return
        pos = e.position()

        if self.tool == "select":
            if self._mode == "move" and self.selected is not None:
                dx = pos.x() - self._last.x()
                dy = pos.y() - self._last.y()
                self._translate(self.shapes[self.selected], dx, dy)
                self._last = pos
                self.update()
            elif self._mode == "resize" and self.selected is not None:
                nb = QRectF(self._resize_fixed, pos).normalized()
                if nb.width() < 5:
                    nb.setWidth(5)
                if nb.height() < 5:
                    nb.setHeight(5)
                self.shapes[self.selected] = self._refit(
                    copy.deepcopy(self._resize_orig), self._resize_obbox, nb)
                self.update()
            return

        if self._preview is None:
            return
        pt = [pos.x(), pos.y()]
        if self.tool == "pen":
            self._preview["points"].append(pt)
        else:
            self._preview = self._shape_from(self._start, pt)
        self.update()

    def mouseReleaseEvent(self, e):
        if self.read_only:
            return
        if self.tool == "select":
            self._mode = None
            self._handle = None
            return
        if self._preview is None:
            return
        s = self._preview
        self._preview = None
        if self._is_meaningful(s):
            self.shapes.append(s)
        self.update()

    # ── Seç / taşı / boyutlandır yardımcıları ───────────────────────
    def _begin_resize(self, handle):
        self._mode = "resize"
        self._handle = handle
        shape = self.shapes[self.selected]
        self._resize_orig = copy.deepcopy(shape)
        self._resize_obbox = self._bbox(shape)
        self._resize_fixed = self._corners(self._resize_obbox)[_OPPOSITE[handle]]

    def _handle_at(self, pos, b):
        for name, pt in self._corners(b).items():
            if abs(pos.x() - pt.x()) <= HANDLE + 2 and abs(pos.y() - pt.y()) <= HANDLE + 2:
                return name
        return None

    def _shape_at(self, pt):
        x, y = pt
        for i in range(len(self.shapes) - 1, -1, -1):
            if self._bbox(self.shapes[i]).adjusted(-6, -6, 6, 6).contains(QPointF(x, y)):
                return i
        return None

    @staticmethod
    def _translate(s, dx, dy):
        t = s.get("type")
        if t == "line":
            s["x1"] += dx; s["y1"] += dy; s["x2"] += dx; s["y2"] += dy
        elif t in ("rect", "ellipse", "text"):
            s["x"] += dx; s["y"] += dy
        elif t == "path":
            s["points"] = [[px + dx, py + dy] for px, py in s["points"]]

    @staticmethod
    def _refit(s, old, new):
        # düz çizgide genişlik ya da yükseklik 0: o eksen ölçeklenmez, kaydırılır (Antigravity BULGU-11)
        sx = new.width() / old.width() if old.width() >= 1 else None
        sy = new.height() / old.height() if old.height() >= 1 else None
        if sx is None and sy is None:
            return s

        def mx(x):
            return new.x() + (x - old.x()) * sx if sx is not None else x + new.x() - old.x()

        def my(y):
            return new.y() + (y - old.y()) * sy if sy is not None else y + new.y() - old.y()

        t = s.get("type")
        if t == "line":
            s["x1"], s["y1"] = mx(s["x1"]), my(s["y1"])
            s["x2"], s["y2"] = mx(s["x2"]), my(s["y2"])
        elif t in ("rect", "ellipse"):
            s["x"], s["y"] = new.x(), new.y()
            s["w"], s["h"] = new.width(), new.height()
        elif t == "path":
            s["points"] = [[mx(px), my(py)] for px, py in s["points"]]
        elif t == "text":
            s["x"], s["y"] = mx(s["x"]), my(s["y"])
            s["size"] = max(6, s.get("size", 14) * sy)
        return s

    # ── Serbest çizim yardımcıları ──────────────────────────────────
    def _shape_from(self, a, b):
        if self.tool == "line":
            return {"type": "line", "x1": a[0], "y1": a[1], "x2": b[0], "y2": b[1],
                    "color": self.color, "width": self.pen_width}
        return {"type": self.tool, "x": a[0], "y": a[1],
                "w": b[0] - a[0], "h": b[1] - a[1],
                "color": self.color, "width": self.pen_width}

    @staticmethod
    def _is_meaningful(s):
        t = s.get("type")
        if t == "path":
            return len(s.get("points", [])) >= 2
        if t == "line":
            return abs(s["x2"] - s["x1"]) + abs(s["y2"] - s["y1"]) > 3
        if t in ("rect", "ellipse"):
            return abs(s["w"]) > 3 and abs(s["h"]) > 3
        return True

    def _erase_at(self, pt):
        idx = self._shape_at(pt)
        if idx is not None:
            del self.shapes[idx]
            if self.selected == idx:
                self.selected = None

    @staticmethod
    def _bbox(s):
        t = s.get("type")
        if t == "path":
            pts = s.get("points", [[0, 0]])
            xs = [q[0] for q in pts]
            ys = [q[1] for q in pts]
            return QRectF(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        if t == "line":
            return QRectF(QPointF(s["x1"], s["y1"]), QPointF(s["x2"], s["y2"])).normalized()
        if t in ("rect", "ellipse"):
            return QRectF(s["x"], s["y"], s["w"], s["h"]).normalized()
        if t == "text":
            w = max(20, len(s.get("text", "")) * s.get("size", 14) * 0.6)
            return QRectF(s["x"], s["y"] - s.get("size", 14), w, s.get("size", 14) + 4)
        return QRectF()


class DiagramPane(QWidget):
    """Araç çubuğu + tuval; WPS/PQR diyaloglarına gömülür."""

    TOOLS = [
        ("⤢", "select", N_("Seç / Taşı / Boyutlandır")),
        ("✏️", "pen", N_("Serbest kalem")),
        ("／", "line", N_("Çizgi")),
        ("▭", "rect", N_("Dikdörtgen")),
        ("◯", "ellipse", N_("Elips")),
        ("T", "text", N_("Metin")),
        ("⌫", "erase", N_("Sil (şekle tıkla)")),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.canvas = DiagramCanvas()

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 8, 6, 8)
        root.setSpacing(8)

        hint = QLabel(_("Araç seçip tuvale çizin veya hazır şablon ekleyin. "
                      "“Seç” aracıyla şekilleri taşıyıp köşelerinden boyutlandırabilirsiniz. "
                      "Şematik kayıtla birlikte saklanır."))
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size:11px; color:#94a3b8;")
        root.addWidget(hint)

        # Araçlar satırı
        bar = QHBoxLayout()
        bar.setSpacing(6)
        self._tool_group = QButtonGroup(self)
        self._tool_group.setExclusive(True)
        for icon, tool, tip in self.TOOLS:
            b = QPushButton(icon)
            b.setObjectName("btn_small")
            b.setCheckable(True)
            b.setFixedSize(34, 30)
            b.setToolTip(_(tip)); b.setProperty("arac", tool)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c, t=tool: self.canvas.set_tool(t))
            self._tool_group.addButton(b)
            bar.addWidget(b)
            if tool == "select":
                b.setChecked(True)

        bar.addSpacing(10)
        self._color_btn = QPushButton(_("Renk"))
        self._color_btn.setObjectName("btn_small")
        self._color_btn.setFixedHeight(30)
        self._color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._color_btn.clicked.connect(self._pick_color)
        self._sync_color_btn()
        bar.addWidget(self._color_btn)

        bar.addWidget(QLabel(_("Kalınlık")))
        self._width_spin = QSpinBox()
        self._width_spin.setRange(1, 20)
        self._width_spin.setValue(self.canvas.pen_width)
        self._width_spin.setFixedWidth(54)
        self._width_spin.valueChanged.connect(self._set_width)
        bar.addWidget(self._width_spin)

        bar.addStretch()
        self._undo_btn = self._mk_btn(_("Geri Al"), self.canvas.undo)
        bar.addWidget(self._undo_btn)
        self._clear_btn = self._mk_btn(_("Temizle"), self.canvas.clear)
        bar.addWidget(self._clear_btn)
        root.addLayout(bar)

        # Hazır şablonlar satırı
        tpl = QHBoxLayout()
        tpl.setSpacing(6)
        tpl.addWidget(QLabel(_("Hazır şablon:")))
        tpl.addWidget(self._mk_btn(_("⧉  Alın Kaynağı"),
                                   lambda: self._add_template(butt_weld_template())))
        tpl.addWidget(self._mk_btn(_("⧉  Köşe Kaynağı"),
                                   lambda: self._add_template(fillet_weld_template())))
        tpl.addStretch()
        root.addLayout(tpl)

        # Tuval, kaydırılabilir bir alanda ortalanır
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        holder = QWidget()
        hl = QHBoxLayout(holder)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addStretch()
        hl.addWidget(self.canvas)
        hl.addStretch()
        scroll.setWidget(holder)
        root.addWidget(scroll, 1)

    # ── API ──────────────────────────────────────────────────────────
    def get_diagram(self):
        return None if self.canvas.is_empty() else self.canvas.to_json()

    def set_diagram(self, data):
        if data:
            self.canvas.from_json(data)

    # ── İç yardımcılar ───────────────────────────────────────────────
    def _mk_btn(self, text, slot):
        b = QPushButton(text)
        b.setObjectName("btn_small")
        b.setFixedHeight(30)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(slot)
        return b

    def _add_template(self, shapes):
        self.canvas.add_shapes(shapes)
        # Şablon eklendikten sonra Seç aracına geç ki hemen taşınabilsin
        self.canvas.set_tool("select")
        for b in self._tool_group.buttons():
            b.setChecked(b.property("arac") == "select")

    def _set_width(self, v):
        self.canvas.pen_width = v

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self.canvas.color), self, _("Renk seç"))
        if c.isValid():
            self.canvas.color = c.name()
            self._sync_color_btn()

    def _sync_color_btn(self):
        self._color_btn.setStyleSheet(
            f"QPushButton#btn_small {{ border:2px solid {self.canvas.color}; }}")


def diagram_view(data, parent=None):
    """Salt-okunur tuval döndürür (detay penceresi için). Boşsa None."""
    if not data or not (isinstance(data, dict) and data.get("shapes")):
        return None
    c = DiagramCanvas(read_only=True, parent=parent)
    c.from_json(data)
    return c
