# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""İngilizce dil desteği doğrulaması (spec 2026-11-02, §5):
- katalog bütünlüğü: koddaki her _()/N_() sabiti katalogda; çeviride Türkçe karakter yok; yer
  tutucular kaynakla aynı; seçmeli veri değerlerinin (D3) karşılığı var;
- İngilizce kip duman testi: program İngilizce açılır, tüm sayfalar ve başlıca pencereler dolaşılır;
  görünen metinlerde Türkçe karakter ya da çevrilmemiş katalog metni kalmaz (kurgusal veri ASCII)."""
import ast
import os
import re
import string
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import (QAbstractButton, QApplication, QComboBox, QGroupBox,  # noqa: E402
                             QLabel, QLineEdit, QTableWidget, QTabWidget, QWidget)

from app import config as C, database, dil, kimlik as K  # noqa: E402
from app.dil_en import EN  # noqa: E402
from app.itp import dokuman  # noqa: E402

KOK = Path(__file__).resolve().parent.parent
TR = re.compile(r"[çğıöşüÇĞİÖŞÜ]")
# yalnız Türkçeye özgü harfler: "TÜV SÜD" gibi özel adlar (Almanca ö/ü) yanlış alarm vermesin
TR_OZEL = re.compile(r"[çğışÇĞİŞ]")
SIFRE = "Guclu-Sifre-1"
_APP = None


def _sabitler():
    for p in sorted((KOK / "app").rglob("*.py")):
        if p.name in ("dil.py", "dil_en.py"):
            continue
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                    and n.func.id in ("_", "N_") and n.args):
                a = n.args[0]
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    yield p.name, n.lineno, a.value


def _alanlar(metin):
    return sorted(f for _, f, _, _ in string.Formatter().parse(metin) if f is not None)


def test_her_sarili_metin_katalogda():
    eksik = [f"{d}:{s} {m!r}" for d, s, m in _sabitler() if m not in EN]
    assert eksik == []


def test_secmeli_veri_degerleri_katalogda():
    degerler = (C.DURUMLAR + C.PWHT_SEC + C.TEST_SEC + list(dokuman.AMACLAR)
                + list(dokuman.DIS_KAPLAMALAR) + list(dokuman.IC_KAPLAMALAR))
    assert [v for v in degerler if v not in EN] == []


def test_ceviriler_turkce_karaktersiz_ve_yer_tutucular_es():
    assert [k for k, v in EN.items() if TR_OZEL.search(v)] == []
    # çevrilmeden kopyalanmış girdi (ö/ü yalnız ise TR_OZEL kaçırır): "Gözle Muayene (VT)" gibi
    assert [k for k, v in EN.items() if k == v and TR.search(re.sub(r"TÜV( SÜD| NORD| AUSTRIA)?", "", k))] == []
    assert [k for k, v in EN.items() if _alanlar(k) != _alanlar(v)] == []


# ── İngilizce kip duman testi ─────────────────────────────────────────
@pytest.fixture
def pencere(tmp_path, monkeypatch):
    global _APP
    _APP = QApplication.instance() or QApplication([])   # başvuru tutulmazsa Qt çöker
    for ad, deger in (("DATA_DIR", tmp_path / "data"), ("DATA_FILE", tmp_path / "data" / "x.json"),
                      ("BACKUP_DIR", tmp_path / "yedek")):
        monkeypatch.setattr(database, ad, str(deger))
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    from app import pages
    monkeypatch.setattr(pages.STDPage, "auto_check_standards", lambda self: None)
    db = database.Database()
    for b in ("wps", "pqr", "std", "cert"):   # yeni kurulum örnek kayıtları (Türkçe kullanıcı verisi)
        while getattr(db, f"get_{b}")():
            getattr(db, f"delete_{b}")(0)
    K.kullanici_ekle(db._c, "admin", SIFRE, K.YONETICI, ad_soyad="QA Admin", yapan=None)
    db.kullanici = K.giris(db._c, "admin", SIFRE)
    K.dil_ayarla(db._c, db.kullanici.id, "en")
    db.firma_kaydet("ORNEK FIRMA", None, beklenen=db.firma())
    # kurgusal, ASCII veri; seçmeli değerler Türkçe (veritabanındaki gibi): ekranda çevrilmeli
    db.add_pqr({"no": "PQR-1", "rev": "00", "tarih": "2025-01-10", "proses": "SAW",
                "metal": "P-1", "dolgu": "EM12K", "onisitma": "Yok", "pwht": "Yok", "test": "Geçti", "lab": "LAB"})
    db.add_wps({"no": "WPS-1", "rev": "00", "tarih": "2025-02-01", "pqr": "PQR-1",
                "proses": "SAW", "metal": "P-1", "dolgu": "EM12K", "pozisyon": "1G",
                "pwht": "Yok", "durum": "Revizyon Bekliyor"})
    db.add_wps({"no": "WPS-2", "rev": "00", "tarih": "2025-02-01", "pqr": "",
                "proses": "SAW", "durum": "Aktif"})
    db.add_std({"no": "API 5L", "org": "API", "title": "Line Pipe", "myVer": "46",
                "lastVer": "47", "status": "guncelleme", "lastCheck": "2026-10-01"})
    db.add_std({"no": "ISO 9001", "org": "ISO", "title": "QMS", "myVer": "2015",
                "lastVer": "", "status": "manuel", "lastCheck": ""})
    db.add_cert({"no": "C-1", "ad": "ISO 9001", "org": "BODY", "bitis": "2020-01-01"})
    db.add_cert({"no": "C-2", "ad": "ISO 14001", "org": "BODY", "bitis": ""})
    from app.main_window import MainWindow
    w = MainWindow(db=db)
    w.oto_kontrol_zamanlayici.stop(); w.daily_timer.stop(); w.dis_degisiklik_zamanlayici.stop()
    yield w
    w._zorla_kapat = True
    w.close()
    QApplication.instance().removeEventFilter(w)
    dil.ayarla("tr")


def _metinler(kok):
    """Görünen metinler (etiket, düğme, ipucu, yer tutucu, açılır liste, tablo, sekme)."""
    out = []
    for w in [kok] + kok.findChildren(QWidget):
        if isinstance(w, QLabel):
            out.append(w.text())
        if isinstance(w, QAbstractButton):
            out.append(w.text())
        if isinstance(w, QLineEdit):
            out.append(w.placeholderText())
        if isinstance(w, QComboBox):
            out += [w.itemText(i) for i in range(w.count())]
        if isinstance(w, QGroupBox):
            out.append(w.title())
        if isinstance(w, QTabWidget):
            out += [w.tabText(i) for i in range(w.count())]
        if isinstance(w, QTableWidget):
            for c in range(w.columnCount()):
                h = w.horizontalHeaderItem(c)
                out.append(h.text() if h else "")
            for r in range(w.rowCount()):
                for c in range(w.columnCount()):
                    it = w.item(r, c)
                    out.append(it.text() if it else "")
        out.append(w.toolTip())
    return [re.sub(r"<[^>]+>", "", m) for m in out if m]


def _sorunlu(metinler):
    """Türkçe karakter ya da İngilizce karşılığı farklı olan (çevrilmemiş) katalog metni.
    Özel adlar (TÜV) dışarıda: kuruluş önerileri listesinde geçer."""
    return sorted({m for m in metinler
                   if TR.search(re.sub(r"TÜV( SÜD| NORD| AUSTRIA)?", "", m)) or (m.strip() in EN and EN[m.strip()] != m.strip())})


def test_ingilizce_kipte_turkce_metin_kalmaz(pencere):
    from app.dialogs import CertDialog, DetailDialog, PQRDialog, STDDialog, WPSDialog
    w = pencere
    assert dil.etkin() == "en"
    sorunlar = {}
    for i in range(w.stacked.count()):
        w.stacked.setCurrentIndex(i)
        QApplication.processEvents()
        sorunlar[f"sayfa {i}"] = _sorunlu(_metinler(w.stacked.widget(i)))
    sorunlar["kenar/başlık"] = _sorunlu(_metinler(w.sidebar) + _metinler(w.title_bar)
                                        + [w.windowTitle()])
    w.itp_page.yeni()
    w.itp_page.editor.ornek_yukle("kurum_c")
    QApplication.processEvents()
    editor = [m for m in _metinler(w.itp_page.editor)]
    sorunlar["itp düzenleyici"] = _sorunlu(editor)
    from app.sartname_page import GrupDialog, MaddeDialog
    s = w.sartname_page
    s.yeni()
    madde = {"id": "m1", "kontrol": "dis_cap", "grup": "g1", "kaynak": "5.1",
             "tur": "sayisal", "kriter": "cap_govde", "alt": -1.6, "ust": 2.4,
             "birim": "mm", "cap_aralik": None, "et_aralik": None}
    gruplar = [{"id": "g1", "ad": {"tr": "Ilk gun", "en": "First day"}}]
    s.editor.durumu_yukle({"alanlar": dict.fromkeys(s.editor.alanlar, "X"), "tur": "ozel",
                           "gruplar": gruplar, "maddeler": [madde], "duzeltme": False})
    sorunlar["şartname düzenleyici"] = _sorunlu(_metinler(s.editor))
    for ad, d in (("madde", MaddeDialog(madde, gruplar, w)), ("grup", GrupDialog(gruplar, [], w))):
        for i in range(d.paneller.count()) if ad == "madde" else (0,):
            if ad == "madde":
                d.paneller.setCurrentIndex(i)
            sorunlar[f"{ad} {i}"] = _sorunlu(_metinler(d) + [d.windowTitle()])
        d.deleteLater()
    s.listeye_don()
    db = w.db
    for ad, d in (("wps", WPSDialog(db, w, db.get_wps()[0])), ("pqr", PQRDialog(w, db.get_pqr()[0])),
                  ("std", STDDialog(w, db.get_std()[0])), ("cert", CertDialog(w, db.get_cert()[0])),
                  ("detay", DetailDialog(db.get_wps()[0], "WPS", w))):
        sorunlar[ad] = _sorunlu(_metinler(d) + [d.windowTitle()])
        d.deleteLater()
    assert {k: v for k, v in sorunlar.items() if v} == {}


def test_secmeli_deger_ekranda_cevrilir_kayitta_turkce(pencere):
    from app.dialogs import WPSDialog
    w = pencere
    d = WPSDialog(w.db, w, w.db.get_wps()[0])
    assert d.f_durum.currentText() == "Awaiting Revision"
    assert d.get_record()["durum"] == "Revizyon Bekliyor" and d.get_record()["pwht"] == "Yok"
    d.deleteLater()


def test_filtre_acilir_listeleri_suzer(pencere):
    """Proses/pozisyon/test sonucu/kuruluş filtreleri addItems ile verisiz eklendiğinden
    currentData() None dönüyor, hiç süzmüyordu (2026-11-02, dil işi sırasında bulundu)."""
    w = pencere
    wps, pqr, std = w.wps_page, w.pqr_page, w.std_page
    wps.cmb_poz.setCurrentIndex(wps.cmb_poz.findData("2G")); wps.refresh()
    assert wps.table.rowCount() == 0
    wps.cmb_poz.setCurrentIndex(wps.cmb_poz.findData("1G")); wps.refresh()
    assert wps.table.rowCount() == 1
    pqr.cmb_test.setCurrentIndex(pqr.cmb_test.findData("Başarısız")); pqr.refresh()
    assert pqr.table.rowCount() == 0
    assert pqr.cmb_test.currentText() == "Failed"                  # gösterim çevrilir
    std.cmb_org.setCurrentIndex(std.cmb_org.findData("ISO")); std.refresh()
    assert std.table.rowCount() == 1


def test_itp_dogrulama_mesajlari_ingilizce():
    """Doğrulama ajanı bulgusu: ITP kalem / hesap mesajları da çevrilir (dokuman, hesap)."""
    from app.itp.dokuman import Kalem
    dil.ayarla("en")
    try:
        with pytest.raises(ValueError, match="must be positive"):
            Kalem(no=1, psl="PSL 2", grade="X52M", D=0, t=7.9, boy_m=12, miktar_m=100,
                  amac="doğalgaz")
    finally:
        dil.ayarla("tr")
