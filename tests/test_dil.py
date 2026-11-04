# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Arayüz dili altyapısı (spec 2026-11-02 İngilizce dil desteği, D2): dil.py, kullanıcı dili
(şema 7). Dil düğmesi testi tests/test_giris_arayuz.py'de (pencere süzgeci temizliği)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sqlite3  # noqa: E402

import pytest  # noqa: E402
from PyQt6.QtCore import QSettings  # noqa: E402

from app import database, dil, kimlik as K  # noqa: E402
from app.dil import N_, _  # noqa: E402

SIFRE = "Guclu-Sifre-1"


@pytest.fixture(autouse=True)
def turkce():
    dil.ayarla("tr")
    yield
    dil.ayarla("tr")


@pytest.fixture
def klasor(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(database, "DATA_FILE", str(tmp_path / "data" / "data.json"))
    monkeypatch.setattr(database, "BACKUP_DIR", str(tmp_path / "yedek"))
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    return tmp_path


def test_cevirme_ve_isaret():
    assert _("Türkçeye geç") == "Türkçeye geç" and N_("x") == "x"
    dil.ayarla("en")
    assert _("Türkçeye geç") == "Switch to Turkish"
    assert _("katalogda olmayan") == "katalogda olmayan"        # Türkçe kalır (test yakalar)
    assert dil.deger("") == "" and dil.deger(None) is None
    with pytest.raises(ValueError):
        dil.ayarla("de")


def test_kullanici_dili_varsayilan_tr_ve_ayarlanir(klasor):
    db = database.Database()
    K.kullanici_ekle(db._c, "ali", SIFRE, K.DUZENLEYICI, yapan=None)
    k = K.giris(db._c, "ali", SIFRE)
    assert K.dil_oku(db._c, k.id) == "tr"
    K.dil_ayarla(db._c, k.id, "en")
    assert K.dil_oku(database.Database()._c, k.id) == "en"
    with pytest.raises(K.KimlikHatasi):
        K.dil_ayarla(db._c, k.id, "xx")


def test_sema6_dosyasi_yukseltilir(klasor):
    db = database.Database()
    K.kullanici_ekle(db._c, "ali", SIFRE, K.DUZENLEYICI, yapan=None)
    db._c.close()
    with sqlite3.connect(klasor / "data" / "kalite.db") as c:
        c.execute("ALTER TABLE kullanicilar DROP COLUMN dil")
        c.execute("PRAGMA user_version = 6")
    db = database.Database()
    assert db._c.execute("PRAGMA user_version").fetchone()[0] == database.SEMA_SURUMU == 7
    k = K.giris(db._c, "ali", SIFRE)
    assert K.dil_oku(db._c, k.id) == "tr"
    assert len(list((klasor / "yedek").glob("kalite_SEMA6_YEDEK_*.db"))) == 1


def test_testlerde_qt_ayarlari_kayit_defterine_yazilmaz():
    """tests/conftest.py: tema / dil_son gerçek kayıt defterine (HKCU) yazılmaz."""
    yol = QSettings("KaliteYS", "WPS_PQR").fileName()
    assert yol.lower().endswith(".ini") and "HKEY" not in yol.upper()
