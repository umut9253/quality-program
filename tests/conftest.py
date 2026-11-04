# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Tüm testler için güvenlik ağı:
- gerçek data/ ve yedek/ klasörüne SQLite bağlantısı yasak (ayrıntı: tests/_koruma.py);
- Qt ayarları (tema, dil_son) gerçek kayıt defterine yazılmaz (2026-11-02). Program
  QSettings("KaliteYS", "WPS_PQR") kullanır; bu kurucu Qt belgesine göre HER ZAMAN yerel biçimdedir
  (Windows: HKCU), setDefaultFormat onu etkilemez. Bu yüzden testlerin "geçici klasöre yönlendirme"
  satırları işe yaramıyor, MainWindow kuran testler kullanıcının tema tercihini değiştiriyordu.
  Test sürecinde QSettings, (kuruluş, uygulama) kurucusunu INI biçimine çeviren alt sınıfla
  değiştirilir; uygulama modülleri sonradan içe aktarıldığı için bu sınıfı alır."""
import atexit
import shutil
import sqlite3
import tempfile

from PyQt6 import QtCore

_GercekAyarlar = QtCore.QSettings


class _TestAyarlari(_GercekAyarlar):
    def __init__(self, *a, **k):
        if len(a) in (1, 2) and all(isinstance(x, str) for x in a) and not k:
            super().__init__(_GercekAyarlar.Format.IniFormat, _GercekAyarlar.Scope.UserScope, *a)
        else:
            super().__init__(*a, **k)


QtCore.QSettings = _TestAyarlari
_TestAyarlari.setDefaultFormat(_GercekAyarlar.Format.IniFormat)
_AYAR_KLASORU = tempfile.mkdtemp(prefix="kys_qsettings_")
_TestAyarlari.setPath(_GercekAyarlar.Format.IniFormat, _GercekAyarlar.Scope.UserScope, _AYAR_KLASORU)
atexit.register(shutil.rmtree, _AYAR_KLASORU, ignore_errors=True)

from tests import _koruma  # noqa: E402

sqlite3.connect = _koruma.sar(sqlite3.connect)


# --- public depo: standart verisi gerektiren testler (tests/standart_verisi_gerekir.txt) ---
import pathlib as _pl  # noqa: E402

import pytest as _pt  # noqa: E402

_GEREKIR = {s.strip() for s in _pl.Path(__file__).with_name("standart_verisi_gerekir.txt")
            .read_text(encoding="utf-8").splitlines() if s.strip() and not s.startswith("#")}


def pytest_collection_modifyitems(config, items):
    for it in items:
        if it.nodeid.split("[")[0] in _GEREKIR:
            it.add_marker(_pt.mark.skip(reason="standart verisi gerekir (public depoda yok)"))
