# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""
Excel (.xlsx) dışa aktarma yardımcısı.

Tablo verilerini biçimlendirilmiş bir Excel sayfasına yazar: renkli kalın
başlık satırı, otomatik sütun genişliği, dondurulmuş başlık ve filtre okları.
openpyxl kurulu değilse kullanıcıya kurulum yönergesi gösterilir.
"""

import re

from PyQt6.QtWidgets import QFileDialog, QMessageBox
from .dil import _

HEADER_BG = "2563EB"   # başlık dolgusu (mavi)
STRIPE_BG = "F1F5FB"   # zebra satır dolgusu


def export_xlsx(parent, default_name, sheet_title, headers, rows):
    """Verileri .xlsx dosyasına aktarır; başarılıysa dosya yolunu döndürür.

    headers: sütun başlıkları listesi
    rows:    her biri headers ile aynı uzunlukta hücre listeleri
    """
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        QMessageBox.warning(
            parent, _("Excel Aktarımı"),
            _("Excel aktarımı için 'openpyxl' paketi gerekli.\n\n"
            "Kurulum için komut satırında şunu çalıştırın:\n"
            "    pip install openpyxl"))
        return None

    path, __ = QFileDialog.getSaveFileName(parent, _("Excel'e Aktar"), default_name,
                                          _("Excel Dosyaları (*.xlsx)"))
    if not path:
        return None

    wb = openpyxl.Workbook()
    ws = wb.active
    # Sayfa adı: Excel'de yasak karakterleri temizle, 31 karakterle sınırla
    ws.title = re.sub(r"[\[\]:*?/\\]", " ", str(sheet_title))[:31] or _("Veri")

    thin = Side(style="thin", color="D8DEE9")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill("solid", fgColor=HEADER_BG)
    stripe_fill = PatternFill("solid", fgColor=STRIPE_BG)

    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=c, value=str(h))
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border
    ws.row_dimensions[1].height = 22

    for r, row in enumerate(rows, 2):
        for c, val in enumerate(row, 1):
            cell = ws.cell(row=r, column=c, value="" if val is None else str(val))
            if cell.value.startswith("="):
                cell.data_type = "s"   # kullanıcı metni formül olarak çalışmaz (Antigravity BULGU-03)
            cell.alignment = Alignment(vertical="center", wrap_text=False)
            cell.border = border
            if r % 2 == 0:
                cell.fill = stripe_fill

    # Otomatik sütun genişliği (içeriğe göre, 10–60 arası)
    for c in range(1, len(headers) + 1):
        lengths = [len(str(headers[c - 1]))]
        lengths += [len(str(row[c - 1])) for row in rows
                    if len(row) >= c and row[c - 1] is not None]
        width = min(max(max(lengths) + 3, 10), 60)
        ws.column_dimensions[get_column_letter(c)].width = width

    ws.freeze_panes = "A2"
    if rows:
        ws.auto_filter.ref = ws.dimensions

    try:
        wb.save(path)
    except PermissionError:
        QMessageBox.warning(
            parent, _("Excel Aktarımı"),
            _("Dosya yazılamadı. Aynı isimli dosya Excel'de açık olabilir;\n"
            "kapatıp tekrar deneyin veya farklı bir isim seçin."))
        return None
    except Exception as e:
        QMessageBox.warning(parent, _("Excel Aktarımı"), _("Dosya kaydedilemedi:\n{e}").format(e=e))
        return None
    return path
