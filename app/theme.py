# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""
Tema sistemi — Koyu (Premium Dark) ve Açık (Soft Light) iki palet.

Renkler tek bir "token" sözlüğünden (palet) beslenir. QSS, `build_stylesheet()`
ile aktif paletten üretilir; programatik (inline) stiller `theme.t("token")`
ile aynı paletten renk okur. Tek tıkla geçiş için `set_theme("light"/"dark")`.

v4.0 — Çift tema + runtime geçiş.
"""
from .dil import N_, _

# ── Aksan renkleri (tema-bağımsız, geriye dönük uyumluluk) ──────────
ACCENT_BLUE   = "#5b9dff"
ACCENT_PURPLE = "#b08cff"
ACCENT_GREEN  = "#4ade80"
ACCENT_AMBER  = "#fbbf24"
ACCENT_TEAL   = "#34d399"
ACCENT_ROSE   = "#fb7185"


def _rgba(hexc, a):
    """'#rrggbb' + alfa → 'rgba(r,g,b,a)' (QSS için)."""
    hexc = hexc.lstrip("#")
    r, g, b = int(hexc[0:2], 16), int(hexc[2:4], 16), int(hexc[4:6], 16)
    return f"rgba({r},{g},{b},{a})"


# ╔══════════════════════════════════════════════════════════════════╗
# ║                          KOYU PALET                               ║
# ╚══════════════════════════════════════════════════════════════════╝
_DARK = {
    # Zemin / yüzeyler
    "window_bg": "#060910", "base_bg": "#0a0e18", "elevated_bg": "#141c30",
    "card_bg": "#0f1525", "dialog_bg": "#0b1220",
    "table_bg": "#0a0f1c", "table_alt": "#0c1222", "table_border": "#141e34",
    # Metin
    "text_primary": "#eef1f8", "text_bright": "#f4f6fb",
    "text_secondary": "#7b87a5", "text_muted": "#4d5872",
    "text_soft": "#cbd5e1", "placeholder": "#3d4a68",
    # Kenarlık
    "border_dim": "#1a2340", "border_dim_rgb": "26,35,64", "border_mid": "#243054",
    # Aksanlar (+ tint için rgb)
    "accent_blue": "#3b82f6", "accent_blue_rgb": "59,130,246",
    "accent_violet": "#8b5cf6", "accent_violet_rgb": "139,92,246",
    "accent_blue_sel": "#2563eb",
    # Sekme çubuğu
    "tab_inactive": "#5d6a85", "tab_selected": "#8ab8ff",
    "tab_hover": "#b8c5de", "tab_sel_bg": "#0f1628",
    # Butonlar
    "btn_border": "#1f2b45", "btn_border_hover": "#2d3f66",
    "btn_bg1": "#151d32", "btn_bg2": "#0f1525",
    "btn_hover1": "#1c2744", "btn_hover2": "#151d32",
    "btn_pressed": "#0d1222", "btn_text": "#d5dced",
    "btn_disabled_text": "#3d4860", "btn_disabled_bg": "#0a0f1a",
    "btn_disabled_border": "#141c2e",
    # Birincil buton
    "primary1": "#4287f5", "primary2": "#6366f1",
    "primary_hover1": "#5a9bf8", "primary_hover2": "#818cf8",
    "primary_pressed": "#4338ca",
    # Tehlike butonu
    "danger_rgb": "248,113,113", "danger_text": "#f08c8c",
    "danger_border": "#3b1818", "danger_hover_border": "#7f1d1d",
    "danger_hover_text": "#fca5a5",
    # Form elemanları
    "input_border": "#1a2340", "input_border_hover": "#243054",
    "input_bg1": "#0d1322", "input_bg2": "#0a0f1c",
    "input_hover1": "#101828", "input_hover2": "#0c1220",
    "input_focus1": "#111d34", "input_focus2": "#0d1628",
    # Tablo başlığı
    "header_bg1": "#111a30", "header_bg2": "#0d1525", "header_text": "#5d6a85",
    # Kartlar (rgba gradyan)
    "card_grad_top": "rgba(20,28,48,0.9)", "card_grad_bottom": "rgba(13,21,37,0.95)",
    "homecard_top": "rgba(18,26,46,0.92)", "homecard_bottom": "rgba(10,16,30,0.96)",
    "homecard_border_rgb": "30,42,72",
    "tile_bg1": "#0f1826", "tile_bg2": "#0b1220",
    "tile_hover1": "#131f36", "tile_hover2": "#0e1828",
    "recent_top": "rgba(18,26,46,0.85)", "recent_bottom": "rgba(10,16,30,0.92)",
    # Tooltip
    "tooltip_bg1": "#1a2540", "tooltip_bg2": "#131d34",
    # ── Inline (programatik) tokenlar ──
    "val_green": "#86efac", "val_amber": "#fcd34d", "val_red": "#fca5a5",
    "val_blue": "#93c5fd", "val_purple": "#c4b5fd", "val_slate": "#94a3b8",
    "accent_section": "#7db4ff", "mini_label": "#a5b4fc",
    "hint_text": "#64748b", "divider": "#1f2738",
    "detail_value": "#e2e8f0",
    "badge_info_bg": "#16314f", "badge_info_fg": "#93c5fd",
    "badge_neutral_bg": "#1c2336", "badge_neutral_fg": "#9aa6c0",
    "circ_ring": "#1a2340",
}

# ╔══════════════════════════════════════════════════════════════════╗
# ║                          AÇIK PALET                               ║
# ╚══════════════════════════════════════════════════════════════════╝
_LIGHT = {
    # Zemin / yüzeyler
    "window_bg": "#eaedf3", "base_bg": "#f1f4f9", "elevated_bg": "#e3e9f2",
    "card_bg": "#ffffff", "dialog_bg": "#f5f7fb",
    "table_bg": "#ffffff", "table_alt": "#f6f8fc", "table_border": "#e2e8f2",
    # Metin
    "text_primary": "#1e293b", "text_bright": "#0f172a",
    "text_secondary": "#5b6577", "text_muted": "#8a93a6",
    "text_soft": "#334155", "placeholder": "#9aa3b5",
    # Kenarlık
    "border_dim": "#d8dee9", "border_dim_rgb": "210,216,228", "border_mid": "#c4cdde",
    # Aksanlar
    "accent_blue": "#2563eb", "accent_blue_rgb": "37,99,235",
    "accent_violet": "#7c3aed", "accent_violet_rgb": "124,58,237",
    "accent_blue_sel": "#2563eb",
    # Sekme çubuğu
    "tab_inactive": "#7a8499", "tab_selected": "#1d4ed8",
    "tab_hover": "#334155", "tab_sel_bg": "#e4ebf7",
    # Butonlar
    "btn_border": "#d2dae6", "btn_border_hover": "#b9c4d6",
    "btn_bg1": "#ffffff", "btn_bg2": "#f3f6fb",
    "btn_hover1": "#f5f8fd", "btn_hover2": "#eef3fb",
    "btn_pressed": "#e8edf6", "btn_text": "#334155",
    "btn_disabled_text": "#aab2c2", "btn_disabled_bg": "#f1f4f9",
    "btn_disabled_border": "#e2e8f0",
    # Birincil buton
    "primary1": "#3b82f6", "primary2": "#6366f1",
    "primary_hover1": "#2563eb", "primary_hover2": "#4f46e5",
    "primary_pressed": "#4338ca",
    # Tehlike butonu
    "danger_rgb": "220,38,38", "danger_text": "#dc2626",
    "danger_border": "#fecaca", "danger_hover_border": "#f87171",
    "danger_hover_text": "#b91c1c",
    # Form elemanları
    "input_border": "#cdd5e3", "input_border_hover": "#b3bed1",
    "input_bg1": "#ffffff", "input_bg2": "#fbfcfe",
    "input_hover1": "#f7f9fc", "input_hover2": "#f1f4f9",
    "input_focus1": "#eef4ff", "input_focus2": "#e8f0ff",
    # Tablo başlığı
    "header_bg1": "#f0f3f9", "header_bg2": "#e9eef6", "header_text": "#5b6577",
    # Kartlar
    "card_grad_top": "rgba(255,255,255,0.96)", "card_grad_bottom": "rgba(248,250,253,0.98)",
    "homecard_top": "rgba(255,255,255,0.97)", "homecard_bottom": "rgba(247,249,252,0.98)",
    "homecard_border_rgb": "210,216,228",
    "tile_bg1": "#ffffff", "tile_bg2": "#f6f8fc",
    "tile_hover1": "#f0f4fb", "tile_hover2": "#eaf0fa",
    "recent_top": "rgba(255,255,255,0.96)", "recent_bottom": "rgba(247,249,252,0.98)",
    # Tooltip
    "tooltip_bg1": "#ffffff", "tooltip_bg2": "#f1f4f9",
    # ── Inline (programatik) tokenlar ──
    "val_green": "#16a34a", "val_amber": "#d97706", "val_red": "#dc2626",
    "val_blue": "#2563eb", "val_purple": "#7c3aed", "val_slate": "#64748b",
    "accent_section": "#2563eb", "mini_label": "#7c3aed",
    "hint_text": "#8a93a6", "divider": "#e2e8f0",
    "detail_value": "#1e293b",
    "badge_info_bg": "#dbeafe", "badge_info_fg": "#1d4ed8",
    "badge_neutral_bg": "#e2e8f0", "badge_neutral_fg": "#475569",
    "circ_ring": "#d8dee9",
}

# ── Aksan adı → tema bazlı renk (stat kartları, dashboard) ──────────
ACCENTS = {
    "blue":   {"dark": "#5b9dff", "light": "#2563eb"},
    "purple": {"dark": "#b08cff", "light": "#7c3aed"},
    "green":  {"dark": "#4ade80", "light": "#16a34a"},
    "amber":  {"dark": "#fbbf24", "light": "#d97706"},
    "rose":   {"dark": "#fb7185", "light": "#e11d48"},
}

# ── Durum rozetleri (tema bazlı) ────────────────────────────────────
# WPS / PQR: (bg, fg) — STD / CERT: (etiket, bg, fg)
_STATUS = {
    "dark": {
        "wps": {
            "Aktif":             ("#0f3d2e", "#7ee2b8"),
            "Revizyon Bekliyor": ("#5a3d12", "#fcd34d"),
            "İptal":             ("#5c1d1d", "#fca5a5"),
        },
        "pqr": {
            "Geçti":     ("#0f3d2e", "#7ee2b8"),
            "Başarısız": ("#5c1d1d", "#fca5a5"),
            "Beklemede": ("#5a3d12", "#fcd34d"),
        },
        "std": {
            "guncel":     (N_("✓  Güncel"),            "#0f3d2e", "#7ee2b8"),
            "guncelleme": (N_("❗  Güncelleme Var"),    "#5c1d1d", "#fca5a5"),
            "kontrol":    (N_("•  Kontrol Edilmedi"),  "#1c2336", "#9aa6c0"),
            "hata":       (N_("✕  Kontrol Hatası"),    "#3b0f0f", "#fca5a5"),
            "manuel":     (N_("❗  Manuel Kontrol"),    "#5a3d12", "#fcd34d"),
        },
        "cert": {
            "gecerli": (N_("✓  Geçerli"),          "#0f3d2e", "#7ee2b8"),
            "yakinda": (N_("▲  Yakında Dolacak"),  "#5a3d12", "#fcd34d"),
            "dolmus":  (N_("✕  Süresi Doldu"),     "#5c1d1d", "#fca5a5"),
            "belirsiz":(N_("•  Tarih Girilmedi"),  "#1c2336", "#9aa6c0"),
        },
    },
    "light": {
        "wps": {
            "Aktif":             ("#d1fae5", "#047857"),
            "Revizyon Bekliyor": ("#fef3c7", "#b45309"),
            "İptal":             ("#fee2e2", "#b91c1c"),
        },
        "pqr": {
            "Geçti":     ("#d1fae5", "#047857"),
            "Başarısız": ("#fee2e2", "#b91c1c"),
            "Beklemede": ("#fef3c7", "#b45309"),
        },
        "std": {
            "guncel":     (N_("✓  Güncel"),            "#d1fae5", "#047857"),
            "guncelleme": (N_("❗  Güncelleme Var"),    "#fee2e2", "#b91c1c"),
            "kontrol":    (N_("•  Kontrol Edilmedi"),  "#e2e8f0", "#475569"),
            "hata":       (N_("✕  Kontrol Hatası"),    "#fee2e2", "#b91c1c"),
            "manuel":     (N_("❗  Manuel Kontrol"),    "#fef3c7", "#b45309"),
        },
        "cert": {
            "gecerli": (N_("✓  Geçerli"),          "#d1fae5", "#047857"),
            "yakinda": (N_("▲  Yakında Dolacak"),  "#fef3c7", "#b45309"),
            "dolmus":  (N_("✕  Süresi Doldu"),     "#fee2e2", "#b91c1c"),
            "belirsiz":(N_("•  Tarih Girilmedi"),  "#e2e8f0", "#475569"),
        },
    },
}


# ── Aktif tema durumu ───────────────────────────────────────────────
_PALETTES = {"dark": _DARK, "light": _LIGHT}
_active = "dark"
_PAL = _DARK


def set_theme(name):
    """Aktif temayı değiştirir ('dark' / 'light')."""
    global _active, _PAL
    if name not in _PALETTES:
        name = "dark"
    _active = name
    _PAL = _PALETTES[name]


def current():
    """Aktif tema adını döndürür."""
    return _active


def t(key):
    """Aktif paletten renk token'ı."""
    return _PAL[key]


def status(kind):
    """Durum rozeti sözlüğü: kind ∈ {'wps','pqr','std','cert'}."""
    return _STATUS[_active][kind]


def accent(name):
    """Aksan adından aktif tema rengi (blue/purple/green/amber/rose)."""
    return ACCENTS.get(name, ACCENTS["blue"])[_active]


def accent_chip(name, alpha=0.14):
    """Aksan için yumuşak çip arka planı (rgba)."""
    return _rgba(accent(name), alpha)


def badge_info():
    return (_PAL["badge_info_bg"], _PAL["badge_info_fg"])


def badge_neutral():
    return (_PAL["badge_neutral_bg"], _PAL["badge_neutral_fg"])


# ╔══════════════════════════════════════════════════════════════════╗
# ║   QSS ŞABLONU — %(token)s yer tutucuları aktif paletten dolar    ║
# ╚══════════════════════════════════════════════════════════════════╝
_QSS_TEMPLATE = """
/* ── Taban ────────────────────────────────────────────────────────── */
QMainWindow { background: %(window_bg)s; }
QWidget {
    background: %(window_bg)s;
    color: %(text_primary)s;
    font-family: 'Segoe UI', 'Inter', Arial, sans-serif;
    font-size: 13px;
}

/* ── Sekme çubuğu ─────────────────────────────────────────────────── */
QTabWidget::pane { border: none; background: %(window_bg)s; }
QTabBar {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 %(window_bg)s, stop:1 %(base_bg)s);
    qproperty-drawBase: 0;
}
QTabBar::tab {
    background: transparent;
    color: %(tab_inactive)s;
    padding: 14px 30px;
    font-size: 13px;
    font-weight: 600;
    border: none;
    border-bottom: 2px solid transparent;
    margin-right: 2px;
    letter-spacing: 0.3px;
}
QTabBar::tab:selected {
    color: %(tab_selected)s;
    border-bottom: 2px solid qlineargradient(x1:0, y1:0, x2:1, y2:0,
                   stop:0 %(accent_blue)s, stop:1 %(accent_violet)s);
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 %(tab_sel_bg)s, stop:1 %(window_bg)s);
}
QTabBar::tab:hover:!selected {
    color: %(tab_hover)s;
    background: rgba(%(accent_blue_rgb)s,0.06);
    border-bottom: 2px solid rgba(%(accent_blue_rgb)s,0.25);
}

/* ── Butonlar ─────────────────────────────────────────────────────── */
QPushButton {
    border: 1px solid %(btn_border)s;
    border-radius: 10px;
    padding: 9px 18px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 %(btn_bg1)s, stop:1 %(btn_bg2)s);
    color: %(btn_text)s;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.2px;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 %(btn_hover1)s, stop:1 %(btn_hover2)s);
    border-color: %(btn_border_hover)s;
    color: %(text_primary)s;
}
QPushButton:pressed {
    background: %(btn_pressed)s;
    border-color: %(accent_blue)s;
}
QPushButton:disabled {
    color: %(btn_disabled_text)s;
    background: %(btn_disabled_bg)s;
    border-color: %(btn_disabled_border)s;
}

/* Birincil buton */
QPushButton#btn_primary {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 %(primary1)s, stop:1 %(primary2)s);
    color: white;
    border: 1px solid rgba(99,102,241,0.5);
    padding: 9px 22px;
    font-weight: 700;
    border-radius: 10px;
}
QPushButton#btn_primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 %(primary_hover1)s, stop:1 %(primary_hover2)s);
    border-color: rgba(129,140,248,0.6);
}
QPushButton#btn_primary:pressed { background: %(primary_pressed)s; }

/* Tehlike butonu */
QPushButton#btn_danger {
    background: rgba(%(danger_rgb)s,0.08);
    color: %(danger_text)s;
    border-color: %(danger_border)s;
}
QPushButton#btn_danger:hover {
    background: rgba(%(danger_rgb)s,0.18);
    border-color: %(danger_hover_border)s;
    color: %(danger_hover_text)s;
}

/* Ghost (hayalet) buton */
QPushButton#btn_ghost {
    background: transparent;
    border: 1px solid %(btn_border)s;
    color: %(text_secondary)s;
    padding: 5px 16px;
    border-radius: 15px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#btn_ghost:hover {
    color: %(text_primary)s;
    border-color: %(accent_blue)s;
    background: rgba(%(accent_blue_rgb)s,0.10);
}

/* Küçük buton */
QPushButton#btn_small { padding: 4px 12px; font-size: 12px; border-radius: 8px; }

/* ── Form elemanları ──────────────────────────────────────────────── */
QLineEdit, QComboBox, QDateEdit, QTextEdit, QSpinBox {
    border: 1px solid %(input_border)s;
    border-radius: 9px;
    padding: 8px 13px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 %(input_bg1)s, stop:1 %(input_bg2)s);
    font-size: 13px;
    color: %(text_primary)s;
    selection-background-color: %(accent_blue)s;
    selection-color: white;
}
QLineEdit:hover, QComboBox:hover, QDateEdit:hover, QTextEdit:hover {
    border-color: %(input_border_hover)s;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 %(input_hover1)s, stop:1 %(input_hover2)s);
}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QTextEdit:focus {
    border-color: %(accent_blue)s;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 %(input_focus1)s, stop:1 %(input_focus2)s);
}
QLineEdit::placeholder { color: %(placeholder)s; }
QComboBox::drop-down { border: none; width: 28px; }
QComboBox QAbstractItemView {
    background: %(card_bg)s;
    color: %(text_primary)s;
    selection-background-color: %(accent_blue_sel)s;
    selection-color: white;
    border: 1px solid %(btn_border)s;
    border-radius: 9px;
    padding: 5px;
    outline: none;
}

/* ── Tablolar ─────────────────────────────────────────────────────── */
QTableWidget {
    background: %(table_bg)s;
    border: 1px solid %(table_border)s;
    border-radius: 13px;
    gridline-color: transparent;
    font-size: 13px;
    color: %(text_primary)s;
    alternate-background-color: %(table_alt)s;
}
QTableWidget::item {
    padding: 7px 11px;
    color: %(text_primary)s;
    border-bottom: 1px solid rgba(%(border_dim_rgb)s,0.6);
}
QTableWidget::item:selected {
    background: rgba(%(accent_blue_rgb)s,0.15);
    color: %(text_primary)s;
}
QTableWidget::item:hover { background: rgba(%(accent_blue_rgb)s,0.08); }
/* ITP önizleme ağacı: tabloyla aynı zemin/seçim (Antigravity BULGU-04) */
QTreeWidget {
    background: %(table_bg)s;
    border: 1px solid %(table_border)s;
    border-radius: 13px;
    font-size: 13px;
    color: %(text_primary)s;
    alternate-background-color: %(table_alt)s;
}
QTreeWidget::item { padding: 2px 4px; color: %(text_primary)s; }
QTreeWidget::item:selected {
    background: rgba(%(accent_blue_rgb)s,0.15);
    color: %(text_primary)s;
}
QTreeWidget::item:hover { background: rgba(%(accent_blue_rgb)s,0.08); }
QHeaderView::section {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 %(header_bg1)s, stop:1 %(header_bg2)s);
    color: %(header_text)s;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    padding: 11px 7px;
    border: none;
    border-bottom: 2px solid %(border_dim)s;
    letter-spacing: 0.2px;
}
QTableCornerButton::section { background: %(header_bg2)s; border: none; }

/* ── Kaydırma çubukları ───────────────────────────────────────────── */
QScrollBar:vertical { background: transparent; width: 8px; margin: 4px 2px; }
QScrollBar::handle:vertical {
    background: rgba(%(accent_blue_rgb)s,0.25);
    border-radius: 4px;
    min-height: 32px;
}
QScrollBar::handle:vertical:hover { background: rgba(%(accent_blue_rgb)s,0.45); }
QScrollBar:horizontal { background: transparent; height: 8px; margin: 2px 4px; }
QScrollBar::handle:horizontal {
    background: rgba(%(accent_blue_rgb)s,0.25);
    border-radius: 4px;
    min-width: 32px;
}
QScrollBar::handle:horizontal:hover { background: rgba(%(accent_blue_rgb)s,0.45); }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

/* ── Etiket / kart / uyarı ────────────────────────────────────────── */
QLabel { color: %(text_primary)s; background: transparent; }
QLabel#stat_value {
    font-size: 28px; font-weight: bold; color: %(text_bright)s; letter-spacing: -0.5px;
}
QLabel#stat_label {
    font-size: 10px; font-weight: 700; color: %(text_muted)s;
    text-transform: uppercase; letter-spacing: 0.8px;
}

/* İstatistik kartı */
QFrame#stat_card {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 %(card_grad_top)s, stop:1 %(card_grad_bottom)s);
    border: 1px solid rgba(%(accent_blue_rgb)s,0.12);
    border-radius: 14px;
}
QFrame#stat_card:hover {
    border-color: rgba(%(accent_blue_rgb)s,0.30);
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 %(card_grad_top)s, stop:1 %(card_grad_bottom)s);
}

/* Ana sayfa kartı */
QFrame#home_card {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 %(homecard_top)s, stop:1 %(homecard_bottom)s);
    border: 1px solid rgba(%(homecard_border_rgb)s,0.5);
    border-radius: 16px;
}
QFrame#home_card:hover {
    border-color: rgba(%(accent_blue_rgb)s,0.25);
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 %(homecard_top)s, stop:1 %(homecard_bottom)s);
}
QFrame#home_card[accent="blue"]   { border-top: 3px solid qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #60a5fa); }
QFrame#home_card[accent="purple"] { border-top: 3px solid qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #a78bfa); }
QFrame#home_card[accent="green"]  { border-top: 3px solid qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #34d399); }
QFrame#home_card[accent="amber"]  { border-top: 3px solid qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #fbbf24); }

/* Mini tile'lar */
QFrame#home_tile {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 %(tile_bg1)s, stop:1 %(tile_bg2)s);
    border: 1px solid rgba(%(border_dim_rgb)s,0.7);
    border-radius: 11px;
}
QFrame#home_tile:hover {
    border-color: rgba(%(accent_blue_rgb)s,0.22);
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 %(tile_hover1)s, stop:1 %(tile_hover2)s);
}

/* Uyarı barı */
QFrame#alert_bar {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 rgba(245,158,11,0.10), stop:1 rgba(217,119,6,0.06));
    border: 1px solid rgba(245,158,11,0.28);
    border-left: 3px solid #f59e0b;
    border-radius: 11px;
}
QFrame#alert_bar_red {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 rgba(248,113,113,0.10), stop:1 rgba(239,68,68,0.06));
    border: 1px solid rgba(248,113,113,0.28);
    border-left: 3px solid #ef4444;
    border-radius: 11px;
}

/* Ana sayfa: bölüm başlığı, dikkat satırları, grup kartı ölçüleri */
QWidget#olcu_sutun { background: transparent; }
QLabel#home_section { font-size: 12px; font-weight: 700; color: %(text_muted)s; letter-spacing: 0.8px; }
QLabel#home_sub { font-size: 12px; color: %(text_muted)s; }
QLabel#kart_baslik { font-size: 16px; font-weight: bold; color: %(text_bright)s; }
QLabel#olcu_baslik { font-size: 11px; font-weight: 700; color: %(text_muted)s; letter-spacing: 0.6px; }
QLabel#olcu_toplam { font-size: 34px; font-weight: bold; color: %(text_bright)s; }
QLabel#olcu_ad { font-size: 13px; color: %(text_secondary)s; }
QLabel#olcu_deger { font-size: 13px; font-weight: 700; color: %(text_primary)s; }
QLabel#dikkat_yok {
    padding: 14px 16px; border-radius: 11px; font-weight: 600; color: %(val_green)s;
    border: 1px solid %(border_dim)s;
}
QPushButton#dikkat_satir {
    text-align: left; padding: 12px 16px; border-radius: 11px; font-size: 13px;
    color: %(text_primary)s; background: %(card_bg)s;
    border: 1px solid %(border_dim)s; border-left: 5px solid %(val_slate)s;
}
QPushButton#dikkat_satir:hover { border-color: %(accent_blue)s; }
QPushButton#dikkat_satir[seviye="kritik"] { border-left: 5px solid #ef4444; }
QPushButton#dikkat_satir[seviye="uyari"]  { border-left: 5px solid #f59e0b; }

/* Yan menü grup başlığı */
QLabel#nav_group {
    font-size: 11px; font-weight: 700; color: %(text_muted)s; letter-spacing: 0.8px;
    padding: 6px 0px 2px 14px;
}

/* Tablo satırı Düzenle/Sil düğmeleri (widgets.make_action_cell) */
QWidget#act_cell { background: transparent; }
QStackedWidget#madde_paneli, QWidget#madde_paneli { background: transparent; }
QPushButton#act_edit {
    padding: 0px; color: %(val_blue)s; background: rgba(%(accent_blue_rgb)s,0.12);
    border: 1px solid rgba(%(accent_blue_rgb)s,0.18); border-radius: 7px; font-size: 14px;
}
QPushButton#act_edit:hover {
    background: rgba(%(accent_blue_rgb)s,0.26); border-color: %(accent_blue)s; color: %(text_bright)s;
}
QPushButton#act_del {
    padding: 0px; color: %(danger_text)s; background: rgba(%(danger_rgb)s,0.10);
    border: 1px solid rgba(%(danger_rgb)s,0.16); border-radius: 7px; font-size: 14px; font-weight: bold;
}
QPushButton#act_del:hover {
    background: rgba(%(danger_rgb)s,0.26); border-color: %(danger_hover_border)s; color: %(danger_hover_text)s;
}

/* ── Separator ────────────────────────────────────────────────────── */
QFrame#separator {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 transparent, stop:0.5 %(border_dim)s, stop:1 transparent);
    border: none;
}

/* ── Diyalog / tooltip ────────────────────────────────────────────── */
QDialog { background: %(dialog_bg)s; border: 1px solid %(border_dim)s; }
QMessageBox { background: %(dialog_bg)s; }
QMessageBox QLabel { color: %(text_primary)s; }
QToolTip {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 %(tooltip_bg1)s, stop:1 %(tooltip_bg2)s);
    color: %(text_primary)s;
    border: 1px solid rgba(%(accent_blue_rgb)s,0.25);
    padding: 6px 10px;
    border-radius: 8px;
    font-size: 12px;
}
QMenu {
    background: %(card_bg)s;
    color: %(text_primary)s;
    border: 1px solid %(btn_border)s;
    border-radius: 9px;
    padding: 5px;
}
QMenu::item { padding: 7px 20px; border-radius: 6px; }
QMenu::item:selected { background: rgba(%(accent_blue_rgb)s,0.15); color: %(text_primary)s; }
QTabWidget#dlg_tabs::pane {
    border: 1px solid %(border_dim)s;
    border-radius: 11px;
    top: -1px;
    background: %(dialog_bg)s;
}
QTabWidget#dlg_tabs QTabBar::tab { padding: 10px 20px; }

/* ── Form etiketleri ──────────────────────────────────────────────── */
QFormLayout QLabel { color: %(text_secondary)s; font-weight: 600; font-size: 12px; }

/* ── Diyalog buton kutusu ─────────────────────────────────────────── */
QDialogButtonBox QPushButton { min-width: 90px; }

/* ── Progress bar ─────────────────────────────────────────────────── */
QProgressBar {
    background: rgba(%(border_dim_rgb)s,0.5);
    border: none; border-radius: 4px; height: 6px; text-align: center;
}
QProgressBar::chunk {
    border-radius: 4px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 %(accent_blue)s, stop:1 %(accent_violet)s);
}

/* ── Selamlama başlığı ────────────────────────────────────────────── */
QLabel#greeting { font-size: 25px; font-weight: bold; color: %(text_bright)s; letter-spacing: -0.4px; }

/* ── "Son İşlemler" satır kartları ────────────────────────────────── */
QFrame#recent_item {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 %(recent_top)s, stop:1 %(recent_bottom)s);
    border: 1px solid rgba(%(homecard_border_rgb)s,0.55);
    border-radius: 10px;
}
QFrame#recent_item:hover { border-color: rgba(%(accent_blue_rgb)s,0.28); }

/* ── Özel Başlık Çubuğu ───────────────────────────────────────────── */
QFrame#title_bar { background: %(window_bg)s; border-bottom: 1px solid %(border_dim)s; }
QPushButton#btn_win {
    background: transparent; border: none; color: %(text_secondary)s; border-radius: 0px;
}
QPushButton#btn_win:hover { background: %(elevated_bg)s; color: %(text_primary)s; }
QPushButton#btn_win_close {
    background: transparent; border: none; color: %(text_secondary)s; border-radius: 0px;
}
QPushButton#btn_win_close:hover { background: #e11d48; color: white; }

/* ── Sol Yan Menü ─────────────────────────────────────────────────── */
QFrame#sidebar {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 %(base_bg)s, stop:1 %(window_bg)s);
    border-right: 1px solid %(border_dim)s;
}
QPushButton#btn_nav {
    background: transparent; border: none; border-radius: 10px;
    color: %(text_secondary)s; text-align: left; padding-left: 16px;
    font-size: 14px; font-weight: 600;
}
/* Kapalı (dar) modda ikon ortalanır — sola dayalı padding ikonu kırpıyordu */
QPushButton#btn_nav[compact="true"] {
    text-align: center; padding-left: 0px;
}
QPushButton#btn_nav:hover { background: rgba(%(accent_blue_rgb)s,0.06); color: %(tab_hover)s; }
QPushButton#btn_nav:checked {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 rgba(%(accent_blue_rgb)s,0.15), stop:1 transparent);
    color: %(tab_selected)s;
    border-left: 3px solid %(accent_blue)s;
    border-radius: 0px;
    border-top-right-radius: 10px;
    border-bottom-right-radius: 10px;
}
"""


def build_stylesheet():
    """Aktif paletten tam QSS dizesini üretir."""
    return _QSS_TEMPLATE % _PAL


# Geriye dönük uyumluluk: ilk yüklemede koyu tema QSS'i
STYLESHEET = build_stylesheet()
