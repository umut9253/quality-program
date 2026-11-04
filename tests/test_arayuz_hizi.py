# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Arayüz hızı/sadelik kuralları (2026-10-29): offscreen; gerçek data.json'a dokunulmaz."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication, QGraphicsEffect, QLineEdit, QWidget  # noqa: E402

from app import database  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def pencere(app, tmp_path, monkeypatch):
    """MainWindow geçici veriyle (data.json ve QSettings gerçek kullanıcıya yazılmaz)."""
    veri = tmp_path / "data"
    monkeypatch.setattr(database, "DATA_DIR", str(veri))
    monkeypatch.setattr(database, "DATA_FILE", str(veri / "data.json"))
    monkeypatch.setattr(database, "BACKUP_DIR", str(tmp_path / "yedek"))
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    # MainWindow 2 sn sonra otomatik standart kontrolü başlatır: testte gerçek Gemini API'sine
    # istek gitmesin (kota harcıyordu)
    from app import pages
    monkeypatch.setattr(pages.STDPage, "auto_check_standards", lambda self: None)
    from app.main_window import MainWindow
    w = MainWindow()
    w.daily_timer.stop()
    w.oto_kontrol_zamanlayici.stop()   # yama geri alındıktan sonra da tetiklenmesin
    yield w
    w.close()


def test_aksiyon_hucresi_kendi_stilini_ayristirmaz(app):
    from app.widgets import make_action_cell
    h = make_action_cell(lambda *_: None, lambda *_: None)
    dugmeler = h.findChildren(QWidget)
    assert h.objectName() == "act_cell" and h.styleSheet() == ""
    assert {d.objectName() for d in dugmeler} >= {"act_edit", "act_del"}
    assert all(d.styleSheet() == "" for d in dugmeler)


def test_arama_gecikmeli(pencere, app):
    sayfa = pencere.std_page
    once = sayfa.table.rowCount()
    assert once > 0                            # örnek veride en az bir standart
    for metin in ("z", "zz", "zzq"):           # hiçbir kayıtla eşleşmez
        sayfa.search.setText(metin)
    assert sayfa.table.rowCount() == once      # her harfte tablo kurulmaz
    assert sayfa.search._arama_zamanlayici.isActive()
    sayfa.search._arama_zamanlayici.timeout.emit()
    assert sayfa.table.rowCount() == 0         # yazma durunca bir kez süzülür


def test_grafik_efekti_ve_saydam_pencere_yok(pencere):
    from PyQt6.QtCore import Qt
    assert not pencere.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    efektli = [w.objectName() or type(w).__name__ for w in pencere.findChildren(QWidget)
               if isinstance(w.graphicsEffect(), QGraphicsEffect)]
    assert efektli == []


def test_menu_gruplu_ve_sabit(pencere):
    sb = pencere.sidebar
    assert [sb.btn_group.id(b) for b in sb.btn_group.buttons()] == [0, 2, 1, 3, 4, 5, 6]
    assert all("  " in b.text() for b in sb.btn_group.buttons())   # ikon + etiket hep görünür
    assert sb.minimumWidth() == sb.maximumWidth()                   # hover ile genişleme yok
    assert [g.text() for g in sb.gruplar] == ["KAYNAK", "BELGE TAKİBİ", "ÜRETİM KALİTESİ"]


# kısayollar menünün görsel sırasıyla: PQR (stacked 2) WPS'ten (1) önce gelir
@pytest.mark.parametrize("tus, indeks", [("Ctrl+1", 0), ("Ctrl+2", 2), ("Ctrl+3", 1),
                                         ("Ctrl+4", 3), ("Ctrl+5", 4), ("Ctrl+6", 5),
                                         ("Ctrl+7", 6)])
def test_kisayollar(pencere, tus, indeks):
    k = {s.key().toString(): s for s in pencere.kisayollar}
    k[tus].activated.emit()
    assert pencere.stacked.currentIndex() == indeks


def test_ana_sayfa_dikkat_listesi_sekmeye_gider(pencere, app):
    pencere.db.get_cert()[:] = [{"no": "C1", "bitis": "2000-01-01"}]
    ana = pencere.home_page
    ana.refresh()
    assert ana.dikkat_satirlari, "süresi dolmuş sertifika dikkat listesinde olmalı"
    ana.dikkat_satirlari[0].click()
    assert pencere.stacked.currentIndex() == 4
