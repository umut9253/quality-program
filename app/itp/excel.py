# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Dokuman → Excel (Plan 3).

ITP formatı KURUM_C-ITP düzenini izler (Word sırası, 2026-11-03): "Document
Information" kapak sayfası (başlık alanları) + "General Information" sayfası (kalem listesi,
şartname listesi, lejant; başlığı her basılı sayfada) + "ITP" sayfası (başlık, sütun
başlıkları, bölüm/aktivite satırları, lejant, imza). KP formatı KURUM_A-KP düzenini izler: tek
"Kalite Planı" sayfası (üst blok, sütun başlıkları, bölüm 2 = Şartname listesi). Metinler yalnızca Dokuman'dan gelir; burada
yalnızca sabit düzen etiketleri vardır (ITP şablonu İngilizce, KP Türkçe). PyQt6 import edilmez.

Firma kimliği (2026-11-02): firma adı belgedendir (Dokuman.firma; eski görüntüde yoksa ayardaki
ad); logo belgeye gömülmez, aktarım anındaki ayardan basılır (ITP A1:B1, KP A1:B3). Logo yoksa
alan boş kalır.
"""
import math
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.firma import ad_dogrula
from app.itp import kaplama as KAPL
from app.itp.kabul_izgara import ALT_SUTUN, BASLIK, METIN, izgara
from app.dil import _

LACIVERT, ACIK_MAVI, MAVI, BOLUM, LEJANT, SARI = (
    "FF1F4E79", "FFDEEBF7", "FF2E75B6", "FFD9E2F3", "FFBDD7EE", "FFFFFF00")
BOLUM_YAZI, BEYAZ = "FF1F3864", "FFFFFFFF"
INCE = Side(style="thin")
KENAR = Border(left=INCE, right=INCE, top=INCE, bottom=INCE)

# ITP: A-F tek sütun, kabul alanı G'den 8 alt sütun (toplam 68), sonra kayıt + 3 denetim
# (2026-11-03; öncesi G tek sütun, H kayıt, I-K denetim)
ITP_KABUL = 7
ITP_KABUL_SON = ITP_KABUL + ALT_SUTUN - 1
ITP_KAYIT = ITP_KABUL_SON + 1
ITP_DENETIM = (ITP_KAYIT + 1, ITP_KAYIT + 2, ITP_KAYIT + 3)
ITP_SON = ITP_DENETIM[-1]
ITP_GENISLIK = {get_column_letter(c): g for c, g in enumerate(
    (7, 24, 16, 17, 22, 20) + (68 / ALT_SUTUN,) * ALT_SUTUN + (22, 9, 9, 9), 1)}
LEJANT_ARALIK = ((1, 3), (4, 6), (ITP_KABUL, ITP_KABUL_SON), (ITP_KAYIT, ITP_SON))
ITP_BASLIKLAR = ("No", "Description of Activity", "Specification /\nControlling document",
                 "Performed by", "Process / Product\ncharacteristic inspected",
                 "Sampling size / type /\nfrequency", "Acceptance Criteria /\nChecking method",
                 "Quality Record", "Inspection, Test and Witnessing Plan")
DIS_DENETIM = ("3rd Party", "Company")   # ilk denetim sütunu firma adıyla başlıklanır
KAPSAM = "Spiral Welded Steel Pipes"
LEJANT_KODLAR = (("C", "Check"), ("H", "Hold point"), ("R", "Review"), ("SW", "Spot Witness"),
                 ("W", "Witness"), ("W x %", "Witness percentage"), ("I", "Inspection"),
                 ("I x %", "Inspection percentage"))
# Kalem.dis_kaplama/ic_kaplama model değeri → İngilizce etiket (V-3-5)
KAPLAMA_EN = {"çıplak": "Bare"}
# KP: A:B aktivite, C karakteristik, kabul D'den 8 alt sütun (toplam 78), sorumlu, frekans;
# [3'RD PARTY] ve REFERANS _kp_genislik'te (2026-11-03; öncesi kabul D:H 5 sütun)
KP_KABUL = 4
KP_KABUL_SON = KP_KABUL + ALT_SUTUN - 1
KP_SORUMLU, KP_FREKANS = KP_KABUL_SON + 1, KP_KABUL_SON + 2
KP_GENISLIK = {get_column_letter(c): g for c, g in enumerate(
    (12, 20, 30) + (78 / ALT_SUTUN,) * ALT_SUTUN + (18, 24), 1)}
GRI, ACIK_GRI = "FFD9D9D9", "FFF2F2F2"
SATIR_PT = 12          # 9 pt yazı için yaklaşık satır yüksekliği
KARAKTER_CARPANI = 1.2  # 9 pt yazıda sütun genişliği birimi başına yaklaşık karakter
KALIN_CARPANI = 0.85    # kalın yazı daha geniş (tablo başlığı)
MAKS_YUKSEKLIK = 409    # Excel satır yüksekliği üst sınırı
PIKSEL_BIRIM = 7        # sütun genişliği birimi başına yaklaşık piksel
LOGO_PAYI = 8           # logo ile hücre kenarı arası (px, toplam)


def excel_yaz(dokuman, yol, firma):
    """firma: ayardaki app.firma.Firma (logo; eski görüntülerde ad)."""
    yol = Path(yol)
    firma_adi = ad_dogrula(dokuman.firma or firma.ad)
    wb = Workbook()
    if (dokuman.format, dokuman.dil) == ("ITP", "en"):
        _kapak_sayfasi(wb.active, dokuman)
        _genel_bilgi_sayfasi(wb.create_sheet("General Information"), dokuman)
        _itp_sayfasi(wb.create_sheet("ITP"), dokuman, firma_adi, firma.logo)
    elif (dokuman.format, dokuman.dil) == ("KP", "tr"):
        _kp_sayfasi(wb.active, dokuman, firma_adi, firma.logo)
    else:
        raise ValueError(_("desteklenmeyen format/dil: {format}/{dil}").format(format=dokuman.format, dil=dokuman.dil))
    wb.save(yol)
    return yol


# --- yardımcılar ---------------------------------------------------------------------

def _dolgu(renk):
    return PatternFill("solid", fgColor=renk)


def _yaz(ws, r, c, deger, *, kalin=False, boyut=9, renk=None, dolgu=None, yatay="left",
         dikey="top", kenar=True, ad="Calibri"):
    h = ws.cell(r, c, deger if deger != "" else None)
    if isinstance(h.value, str) and h.value.startswith("="):
        h.data_type = "s"   # başlık vb. kullanıcı metni formül olarak çalışmaz (Antigravity BULGU-03)
    h.font = Font(name=ad, b=kalin, sz=boyut, color=renk)
    h.alignment = Alignment(horizontal=yatay, vertical=dikey, wrap_text=True)
    if dolgu:
        h.fill = _dolgu(dolgu)
    if kenar:
        h.border = KENAR
    return h


def _birlestir(ws, r1, c1, r2, c2, **stil):
    """Birleşik aralıktaki her hücreye stil (kenarlık/dolgu tüm aralıkta görünsün)."""
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            if (r, c) != (r1, c1):
                _yaz(ws, r, c, None, **stil)
    if (r1, c1) != (r2, c2):
        ws.merge_cells(start_row=r1, start_column=c1, end_row=r2, end_column=c2)


def _logo(ws, logo, hucre, genislik, yukseklik_pt):
    """Logo hücre kutusuna (sütun genişliği toplamı × yükseklik) oranı korunarak sığar."""
    if not logo:
        return
    try:
        img = XLImage(BytesIO(logo))
    except Exception as e:   # bozuk veri: logosuz sessiz devam yok
        raise ValueError(_("Firma logosu okunamadı ({e}); Firma Bilgileri'nden yeniden yükleyin.").format(e=e)) from e
    olcek = min((genislik * PIKSEL_BIRIM - LOGO_PAYI) / img.width,
                (yukseklik_pt * 4 / 3 - LOGO_PAYI) / img.height)
    img.width, img.height = max(1, int(img.width * olcek)), max(1, int(img.height * olcek))
    ws.add_image(img, hucre)


def _sayi(x):
    return str(int(x)) if float(x).is_integer() else str(x)


def _binlik(x):
    """İngilizce binlik ayırıcı: 21216 → "21,216" (kullanıcı kararı 2026-11-03)."""
    return f"{int(x):,}" if float(x).is_integer() else f"{x:,}"


def _izgara_satiri(ws, r, ilk, iz, **stil):
    """Izgara satırı → kabul alanı hücreleri (ilk = alanın ilk sütunu). Tablo başlığı kalın,
    açık gri; tablo hücreleri ortalı; ELLE GİRİLECEK satırı alanın tamamında sarı."""
    st = dict(stil)
    if iz.tur == BASLIK:
        st.update(kalin=True, dolgu=ACIK_GRI)
    if iz.tur != METIN:
        st.update(yatay="center")
    if iz.elle:                 # birleştirmeden önce: alt hücrelerin hepsi sarı (BULGU-03)
        st.update(dolgu=SARI)
    for a, b, metin in iz.hucreler:
        _yaz(ws, r, ilk + a, metin, **st)
        _birlestir(ws, r, ilk + a, r, ilk + b, **st)


def _izgara_yuksekligi(iz, ilk, genislik):
    hucre = {(ilk + a, ilk + b): m for a, b, m in iz.hucreler}
    return _yukseklik([(m, k) for k, m in hucre.items()],
                      {k: _aralik_genisligi(genislik, *k) for k in hucre}, kalin=iz.tur == BASLIK)


def _ek_yukseklik(ws, r, son, gerek):
    """Kabul dışı hücreler (aktivite, frekans …) satırlar boyunca birleşik: toplam yükseklik
    onların metnine yetmiyorsa fark son satıra eklenir."""
    toplam = sum(ws.row_dimensions[x].height for x in range(r, son + 1))
    if gerek > toplam:
        ws.row_dimensions[son].height = min(MAKS_YUKSEKLIK,
                                            ws.row_dimensions[son].height + gerek - toplam)


def _birlesim_araliklari(grup, sutun_metni):
    """grup: [(ilk satır, son satır, Satir)]. sutun_metni None ise ya da devam satırlarında
    metin ilkinden farklıysa her Satir kendi aralığında; değilse grubun tamamı tek aralık
    (birleştirme metin kaybettirmez)."""
    r1, __, ilk = grup[0]
    if (sutun_metni and len(grup) > 1
            and all(sutun_metni(s) in ("", sutun_metni(ilk)) for *__, s in grup[1:])):
        return [(r1, grup[-1][1])]
    return [(a, b) for a, b, __ in grup]


def _satir_sayisi(metin, genislik, kalin=False):
    """Kelime kaydırmalı yaklaşık satır sayısı (Excel kelimeyi bölmez; sığmayan uzun kelime
    karakterle bölünür)."""
    karakter = max(1, int(genislik * KARAKTER_CARPANI * (KALIN_CARPANI if kalin else 1)))
    n = 0
    for paragraf in str(metin).split("\n"):
        satir = 0
        for kelime in paragraf.split():
            if satir and satir + 1 + len(kelime) <= karakter:
                satir += 1 + len(kelime)
                continue
            if satir:
                n += 1
            n += (len(kelime) - 1) // karakter
            satir = (len(kelime) - 1) % karakter + 1
        n += 1
    return n


def _yukseklik(degerler, genislik=ITP_GENISLIK, kalin=False):
    """degerler: (metin, sütun harfi) — en çok satır tutan hücreye göre yaklaşık yükseklik."""
    n = max((_satir_sayisi(m, genislik[h], kalin) for m, h in degerler if m), default=1)
    return min(MAKS_YUKSEKLIK, max(15, n * SATIR_PT + 3))


# --- ITP sayfası -----------------------------------------------------------------------

def _itp_sayfasi(ws, d, firma_adi, logo):
    ws.title = "ITP"
    for h, g in ITP_GENISLIK.items():
        ws.column_dimensions[h].width = g
    b = d.baslik
    ust = dict(kalin=True, boyut=10, dolgu=ACIK_MAVI, yatay="center", dikey="center")
    _yaz(ws, 1, 1, None)                             # logo alanı A1:B1
    _birlestir(ws, 1, 1, 1, 2)
    _yaz(ws, 1, 3, "INSPECTION AND TEST PLAN", kalin=True, boyut=14, renk=BEYAZ,
         dolgu=LACIVERT, yatay="center", dikey="center")
    _birlestir(ws, 1, 3, 1, ITP_SON, kalin=True, boyut=14, dolgu=LACIVERT)
    ws.row_dimensions[1].height = 45 if logo else 24
    _logo(ws, logo, "A1", ITP_GENISLIK["A"] + ITP_GENISLIK["B"], 45)
    for c1, c2, metin in ((1, 3, f"Document No : {b.dokuman_no}"),
                          (4, 6, f"Scope of Plan : {KAPSAM}"),
                          (ITP_KABUL, ITP_KAYIT, f"Rev : {b.rev}   IDC : {b.idc}"),
                          (ITP_DENETIM[0], ITP_SON, f"Date : {b.tarih}")):
        _yaz(ws, 2, c1, metin, **ust)
        _birlestir(ws, 2, c1, 2, c2, **ust)
    ws.row_dimensions[2].height = 20.1
    bas = dict(kalin=True, boyut=10, renk=BEYAZ, dolgu=MAVI, yatay="center", dikey="center")
    araliklar = ((1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6), (ITP_KABUL, ITP_KABUL_SON),
                 (ITP_KAYIT, ITP_KAYIT), (ITP_DENETIM[0], ITP_SON))
    for (c1, c2), metin in zip(araliklar, ITP_BASLIKLAR):
        _yaz(ws, 3, c1, metin, **bas)
        _birlestir(ws, 3, c1, 3 if c1 == ITP_DENETIM[0] else 4, c2, **bas)
    for c, metin in zip(ITP_DENETIM, (firma_adi,) + DIS_DENETIM):
        _yaz(ws, 4, c, metin, **bas)
    ws.row_dimensions[3].height = 30
    # firma adı dar denetim sütununda kaydırılır: satır yüksekliği ada göre (kesik görünmesin)
    ws.row_dimensions[4].height = max(15.95, _satir_sayisi(
        firma_adi, ITP_GENISLIK[get_column_letter(ITP_DENETIM[0])]) * 13.5)

    r = 5
    for bolum in d.bolumler:
        st = dict(kalin=True, boyut=11, renk=BOLUM_YAZI, dolgu=BOLUM)
        _yaz(ws, r, 1, bolum.no, yatay="center", **st)
        _yaz(ws, r, 2, bolum.baslik, **st)
        _birlestir(ws, r, 2, r, ITP_SON, **st)
        ws.row_dimensions[r].height = 20.1
        r += 1
        grup = []                      # (ilk satır, son satır, Satir) — aynı aktivite
        for s in bolum.satirlar:
            if s.no and grup:
                _grubu_birlestir(ws, grup)
                grup = []
            n = _aktivite_satiri(ws, r, s)
            grup.append((r, r + n - 1, s))
            r += n
        if grup:
            _grubu_birlestir(ws, grup)

    r += 1
    _yaz(ws, r, 1, "Legend", kalin=True, boyut=10, dolgu=LEJANT, yatay="center")
    r += 1
    for i in range(2):
        for j, (c1, c2) in enumerate(LEJANT_ARALIK):
            kod, anlam = LEJANT_KODLAR[i * 4 + j]
            ws.cell(r, c1, f"{kod} = {anlam}").font = Font(name="Calibri", sz=9)
            ws.merge_cells(start_row=r, start_column=c1, end_row=r, end_column=c2)
        r += 1
    r += 1
    for c1, c2, metin in ((1, 4, f"Prepared by : {b.hazirlayan}"),
                          (5, ITP_KABUL_SON, f"Checked by : {b.inceleyen}"),
                          (ITP_KAYIT, ITP_SON, f"Approved by : {b.onaylayan}")):
        _yaz(ws, r, c1, metin, kalin=True, boyut=10, yatay="center", dikey="center",
             kenar=False)
        ws.merge_cells(start_row=r, start_column=c1, end_row=r, end_column=c2)
    ws.row_dimensions[r].height = 21.95

    ws.freeze_panes = "A5"
    ws.print_title_rows = "1:4"
    _baski(ws, "landscape")
    ws.page_margins.left = ws.page_margins.right = 0.3
    ws.page_margins.top = ws.page_margins.bottom = 0.4


def _aktivite_satiri(ws, r, s):
    """Satir → kabul ızgarası kadar Excel satırı; dönüş kullanılan satır sayısı."""
    izg = izgara(s.kabul)
    son = r + len(izg) - 1
    tek = ((1, s.no), (2, s.aktivite), (3, s.spec), (4, s.sorumlu), (5, s.karakteristik),
           (6, s.frekans), (ITP_KAYIT, s.kayit))
    for c, deger in tek:
        st = dict(kalin=True, yatay="center") if c == 1 else {}
        _yaz(ws, r, c, deger, **st)
        for x in range(r + 1, son + 1):
            _yaz(ws, x, c, None, **st)
    for c, deger in zip(ITP_DENETIM, (s.denetim.firma, s.denetim.ucuncu_taraf,
                                      s.denetim.musteri)):
        _yaz(ws, r, c, deger, kalin=True, yatay="center")
        for x in range(r + 1, son + 1):
            _yaz(ws, x, c, None, kalin=True, yatay="center")
    for i, iz in enumerate(izg):
        _izgara_satiri(ws, r + i, ITP_KABUL, iz)
        ws.row_dimensions[r + i].height = _izgara_yuksekligi(iz, ITP_KABUL, ITP_GENISLIK)
    _ek_yukseklik(ws, r, son, _yukseklik(
        [(m, get_column_letter(c)) for c, m in tek], ITP_GENISLIK))
    return len(izg)


# ITP: aynı aktivitenin satırlarında grubun tamamında birleşebilecek sütunlar → hücre metni;
# diğer kabul dışı sütunlar yalnızca kendi Satir aralığında birleşir.
ITP_GRUP = {1: lambda s: s.no, 2: lambda s: s.aktivite, 3: lambda s: s.spec,
            4: lambda s: s.sorumlu}
ITP_DIKEY = (1, 2, 3, 4, 5, 6, ITP_KAYIT) + ITP_DENETIM


def _grubu_birlestir(ws, grup):
    """grup: [(ilk satır, son satır, Satir)] — aynı aktivitenin satırları (ilki no'lu)."""
    for c in ITP_DIKEY:
        for a, b in _birlesim_araliklari(grup, ITP_GRUP.get(c)):
            if b > a:
                ws.merge_cells(start_row=a, start_column=c, end_row=b, end_column=c)


def _baski(ws, yon):
    ws.page_setup.orientation = yon
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0


# --- Document Information (kapak) ve General Information sayfaları --------------------

BILGI_GENISLIK = dict(A=22, B=26, C=20, D=18, E=16, F=16, G=22)


def _kapak_sayfasi(ws, d):
    ws.title = "Document Information"
    for h, g in BILGI_GENISLIK.items():
        ws.column_dimensions[h].width = g
    b = d.baslik
    r = _bilgi_basligi(ws, 1, "DOCUMENT INFORMATION")
    for etiket, deger in (("Document Title", "Inspection and Test Plan"),
                          ("Document No", b.dokuman_no), ("Rev.", b.rev), ("IDC", b.idc),
                          ("Date", b.tarih), ("Company", b.musteri), ("Project", b.proje),
                          ("Order No", b.siparis_no), ("Prepared by", b.hazirlayan),
                          ("Checked by", b.inceleyen), ("Approved by", b.onaylayan)):
        _yaz(ws, r, 1, etiket, kalin=True, boyut=10, dolgu=ACIK_MAVI)
        _yaz(ws, r, 2, deger)
        _birlestir(ws, r, 2, r, 7)
        r += 1
    _baski(ws, "portrait")


def _genel_bilgi_sayfasi(ws, d):
    for h, g in BILGI_GENISLIK.items():
        ws.column_dimensions[h].width = g
    r = _bilgi_basligi(ws, 1, "GENERAL INFORMATION")
    r = _tablo_basligi(ws, r, ("Item No", "Diameter (mm)", "Thickness (mm)", "Steel Grade",
                               "Length (m)", "Quantity (m)", "Coating / Lining"))
    for k, s in zip(d.kalemler, d.sonuclar):
        # KURUM_C ITP biçimi "PE(<t>mm)/BARE": büyük harf, kalınlık = ISO 21809-1 min toplam
        dis = KAPLAMA_EN.get(k.dis_kaplama, k.dis_kaplama).upper()
        if k.kaplama_sinifi:
            mm = KAPL.min_kalinlik(k.kaplama_sinifi, k.kalinlik_sinifi, s.pm).deger
            dis += f"({_sayi(mm)}mm)"
        ic = KAPLAMA_EN.get(k.ic_kaplama, k.ic_kaplama).upper()
        for c, deger in enumerate((str(k.no), _sayi(k.D), _sayi(k.t), f"{k.grade} {k.psl}",
                                   _sayi(k.boy_m), _binlik(k.miktar_m), f"{dis}/{ic}"), 1):
            _yaz(ws, r, c, deger, yatay="center")
        r += 1

    r = _bilgi_basligi(ws, r + 1, "SPECIFICATION")
    r = _tablo_basligi(ws, r, ("Spec. No", "Document"))
    _birlestir(ws, r - 1, 2, r - 1, 7, kalin=True, boyut=10, renk=BEYAZ, dolgu=MAVI)
    for sp in d.sartnameler:
        _yaz(ws, r, 1, str(sp.no), yatay="center")
        _yaz(ws, r, 2, sp.metin)
        _birlestir(ws, r, 2, r, 7)
        r += 1

    r = _bilgi_basligi(ws, r + 1, "LEGEND")
    r = _tablo_basligi(ws, r, ("Code", "Meaning", None, "Code", "Meaning"))
    # tablo başlık genişliğinde: anlam hücreleri B:C ve E:G (kullanıcı kararı, Antigravity BULGU-17)
    st = dict(kalin=True, boyut=10, renk=BEYAZ, dolgu=MAVI, yatay="center", dikey="center")
    _birlestir(ws, r - 1, 2, r - 1, 3, **st)
    _birlestir(ws, r - 1, 5, r - 1, 7, **st)
    for i in range(4):
        for c, (kod, anlam), son in ((1, LEJANT_KODLAR[i], 3), (4, LEJANT_KODLAR[i + 4], 7)):
            _yaz(ws, r, c, kod, yatay="center")
            _yaz(ws, r, c + 1, anlam)
            _birlestir(ws, r, c + 1, r, son)
        r += 1
    ws.print_title_rows = "1:2"
    _baski(ws, "portrait")


def _bilgi_basligi(ws, r, metin):
    st = dict(kalin=True, boyut=14, renk=BEYAZ, dolgu=LACIVERT, yatay="center",
              dikey="center")
    _yaz(ws, r, 1, metin, **st)
    _birlestir(ws, r, 1, r, 7, **st)
    ws.row_dimensions[r].height = 21.95
    return r + 1


def _tablo_basligi(ws, r, basliklar):
    for c, metin in enumerate(basliklar, 1):
        if metin is not None:
            _yaz(ws, r, c, metin, kalin=True, boyut=10, renk=BEYAZ, dolgu=MAVI,
                 yatay="center", dikey="center")
    return r + 1


# --- KP sayfası (KURUM_A KP düzeni, 11 sütun) ------------------------------------------

def _kp_aktivite(s):
    """AKTİVİTE/PROSES hücresi: "no) aktivite" (KURUM_A "1) Ebat" biçimi)."""
    if s.no:
        return f"{s.no}) {s.aktivite}" if s.aktivite else f"{s.no})"
    return s.aktivite


def _kp_hucreler(s, son):
    """Kabul dışı (ilk sütun, son sütun, metin) hücreleri: A:B aktivite, C karakteristik,
    sorumlu, frekans, [3'RD PARTY], son sütun referans (spec F3, F5)."""
    return ([(1, 2, _kp_aktivite(s)), (3, 3, s.karakteristik),
             (KP_SORUMLU, KP_SORUMLU, s.sorumlu), (KP_FREKANS, KP_FREKANS, s.frekans)]
            + ([(KP_FREKANS + 1, KP_FREKANS + 1, s.denetim.ucuncu_taraf)]
               if son == KP_FREKANS + 2 else [])
            + [(son, son, s.spec)])


def _kp_son(ucuncu):
    return KP_FREKANS + (2 if ucuncu else 1)


def _kp_genislik(son):
    ek = (11, 18) if son == KP_FREKANS + 2 else (18,)
    return dict(KP_GENISLIK, **{get_column_letter(KP_FREKANS + i): g
                                for i, g in enumerate(ek, 1)})


def _aralik_genisligi(genislik, c1, c2):
    return sum(genislik[get_column_letter(c)] for c in range(c1, c2 + 1))


def _kp_sayfasi(ws, d, firma_adi, logo):
    if any(b.no == "2" for b in d.bolumler):
        raise ValueError(_("KP: bölüm 2 (Şartname) Excel katmanında şartname listesinden "
                         "basılır; şablonda bölüm 2 olmamalı"))
    ws.title = "Kalite Planı"
    # F5: bir satırda bile 3rd party değeri varsa REFERANS'tan önce 3'RD PARTY sütunu
    son = _kp_son(any(s.denetim.ucuncu_taraf for b in d.bolumler for s in b.satirlar))
    genislik = _kp_genislik(son)
    for h, g in genislik.items():
        ws.column_dimensions[h].width = g
    b = d.baslik
    et = dict(ad="Arial", boyut=10, dikey="center")
    deg = dict(et, kalin=True)
    baslik = dict(ad="Arial", kalin=True, boyut=20, yatay="center", dikey="center")
    _yaz(ws, 1, 1, None, **et)                       # logo alanı A1:B3
    _birlestir(ws, 1, 1, 3, 2, **et)
    et_c, deg_c = KP_KABUL_SON, KP_SORUMLU          # "No / Tarih / Rev." etiketi, değeri
    _yaz(ws, 1, 3, "KALİTE PLANI", **baslik)
    _birlestir(ws, 1, 3, 3, et_c - 1, **baslik)
    for r, etiket, deger in ((1, "No", b.dokuman_no), (2, "Tarih", b.tarih)):
        _yaz(ws, r, et_c, etiket, **et)
        _yaz(ws, r, deg_c, deger, **deg)
        _birlestir(ws, r, deg_c, r, son, **deg)
    _yaz(ws, 3, et_c, "Rev.", **et)
    _yaz(ws, 3, deg_c, b.rev, **deg)
    _yaz(ws, 3, deg_c + 1, f"IDC: {b.idc}", **deg)
    _birlestir(ws, 3, deg_c + 1, 3, son, **deg)
    _yaz(ws, 4, et_c, "Sipariş No:", **et)
    _yaz(ws, 4, deg_c, b.siparis_no, **deg)
    _birlestir(ws, 4, deg_c, 4, son, **deg)
    for r, etiket, deger in ((4, "MÜŞTERİ", b.musteri), (5, "FİRMA", firma_adi),
                             (6, "PROJE", b.proje)):
        _yaz(ws, r, 1, etiket, **et)
        _birlestir(ws, r, 1, r, 2, **et)
        _yaz(ws, r, 3, deger, **deg)
        _birlestir(ws, r, 3, r, et_c - 1, **deg)
    _yaz(ws, 5, et_c, None, **et)
    _birlestir(ws, 5, et_c, 6, son, **et)
    imza = dict(ad="Arial", boyut=10)
    for c1, c2, metin in ((1, 2, f"Hazırlayan :\n{b.hazirlayan}"),
                          (3, 5, f"İnceleyen :\n{b.inceleyen}"),
                          (6, et_c - 1, f"Onaylayan :\n{b.onaylayan}")):
        _yaz(ws, 7, c1, metin, **imza)
        _birlestir(ws, 7, c1, 7, c2, **imza)
    muhur = dict(ad="Arial", boyut=9, yatay="center", dikey="bottom")
    _yaz(ws, 7, et_c, "_______________________________\nMühür / İmza / Tarih", **muhur)
    _birlestir(ws, 7, et_c, 7, son, **muhur)
    for r, y in ((1, 20), (2, 20), (3, 20), (4, 18), (5, 18), (6, 18), (7, 45)):
        ws.row_dimensions[r].height = y
    _logo(ws, logo, "A1", genislik["A"] + genislik["B"], 60)
    bas = dict(ad="Arial", kalin=True, boyut=10, dolgu=GRI, yatay="center", dikey="center")
    for c1, c2, metin in ([(1, 2, "AKTİVİTE/PROSES"), (3, KP_KABUL_SON, "YAPILMASI GEREKENLER"),
                           (KP_SORUMLU, KP_SORUMLU, "SÜREÇ SORUMLUSU"),
                           (KP_FREKANS, KP_FREKANS, "TEST FREKANSI")]
                          + ([(KP_FREKANS + 1, KP_FREKANS + 1, "3'RD PARTY")]
                             if son == KP_FREKANS + 2 else [])
                          + [(son, son, "REFERANS")]):
        _yaz(ws, 8, c1, metin, **bas)
        _birlestir(ws, 8, c1, 8, c2, **bas)
    ws.row_dimensions[8].height = 30          # "SÜREÇ SORUMLUSU" iki satır

    r = 9
    for i, bolum in enumerate(d.bolumler):
        if i == 1:
            r = _kp_sartname_bolumu(ws, r, d, son, genislik)
        etiket = f"{bolum.no}) {bolum.baslik}"
        # V-3-9: ilk aktivite satırı aynı etiketi taşıyorsa ayrı bölüm satırı basılmaz
        if not bolum.satirlar or _kp_aktivite(bolum.satirlar[0]) != etiket:
            r = _kp_bolum_satiri(ws, r, etiket, son)
        grup = []                      # (ilk satır, son satır, Satir) — aynı aktivite
        for s in bolum.satirlar:
            if s.no and grup:
                _kp_grubu_birlestir(ws, grup, son)
                grup = []
            n = _kp_satiri(ws, r, s, son, genislik)
            grup.append((r, r + n - 1, s))
            r += n
        if grup:
            _kp_grubu_birlestir(ws, grup, son)
    if len(d.bolumler) < 2:
        _kp_sartname_bolumu(ws, r, d, son, genislik)

    ws.freeze_panes = "A9"
    ws.print_title_rows = "1:8"
    _baski(ws, "landscape")
    ws.page_margins.left = ws.page_margins.right = 0.3
    ws.page_margins.top = ws.page_margins.bottom = 0.4


def _kp_bolum_satiri(ws, r, metin, son):
    st = dict(ad="Arial", kalin=True, boyut=10, dolgu=ACIK_GRI, dikey="center")
    _yaz(ws, r, 1, metin, **st)
    _birlestir(ws, r, 1, r, son, **st)
    ws.row_dimensions[r].height = 18
    return r + 1


def _kp_sartname_bolumu(ws, r, d, son, genislik):
    """Bölüm 2 = Şartname: dokuman.sartnameler "Ş.n) metin" satırları C:son (V-3-2)."""
    r = _kp_bolum_satiri(ws, r, "2) Şartname", son)
    for sp in d.sartnameler:
        metin = f"Ş.{sp.no}) {sp.metin}"
        _yaz(ws, r, 1, None, ad="Arial")
        _birlestir(ws, r, 1, r, 2, ad="Arial")
        _yaz(ws, r, 3, metin, ad="Arial")
        _birlestir(ws, r, 3, r, son, ad="Arial")
        ws.row_dimensions[r].height = _yukseklik(
            [(metin, "C")], {"C": _aralik_genisligi(genislik, 3, son)})
        r += 1
    return r


def _kp_satiri(ws, r, s, son, genislik):
    """Değer + stil, kabul ızgarası kadar satır; dönüş satır sayısı. Kabul dışı hücrelerin
    birleştirmesi _kp_grubu_birlestir'de (aktivite dikey birleşebilir)."""
    izg = izgara(s.kabul)
    bitis = r + len(izg) - 1
    hucreler = _kp_hucreler(s, son)
    for c1, c2, deger in hucreler:
        st = dict(ad="Arial", kalin=c1 == 1, yatay="center" if c1 > KP_FREKANS else "left")
        _yaz(ws, r, c1, deger, **st)
        for x in range(r, bitis + 1):
            for c in range(c1, c2 + 1):
                if (x, c) != (r, c1):
                    _yaz(ws, x, c, None, **st)
    for i, iz in enumerate(izg):
        _izgara_satiri(ws, r + i, KP_KABUL, iz, ad="Arial")
        ws.row_dimensions[r + i].height = _izgara_yuksekligi(iz, KP_KABUL, genislik)
    _ek_yukseklik(ws, r, bitis, _yukseklik(
        [(m, (c1, c2)) for c1, c2, m in hucreler],
        {(c1, c2): _aralik_genisligi(genislik, c1, c2) for c1, c2, __ in hucreler}))
    return len(izg)


def _kp_grubu_birlestir(ws, grup, son):
    """grup: [(ilk satır, son satır, Satir)]. Aktivite (A:B), sorumlu, referans devam
    satırlarında boş ya da aynıysa grubun tamamında; diğer kabul dışı hücreler kendi Satir
    aralığında birleşir. Kabul alanı _izgara_satiri'nde satır satır birleşik."""
    alanlar = {(1, 2): _kp_aktivite, (KP_SORUMLU, KP_SORUMLU): lambda s: s.sorumlu,
               (son, son): lambda s: s.spec}
    for c1, c2, __ in _kp_hucreler(grup[0][2], son):
        for a, b in _birlesim_araliklari(grup, alanlar.get((c1, c2))):
            if (a, c1) != (b, c2):
                ws.merge_cells(start_row=a, start_column=c1, end_row=b, end_column=c2)
