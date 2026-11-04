# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Test güvenlik ağı (tests/_koruma.py): gerçek data/ ve yedek/ yolları yasak.

Yalnız yol metinleri sınanır; gerçek dosyaya hiçbir bağlantı açılmaz.
"""
import os
import pathlib
import sqlite3

import pytest

from tests import _koruma as KR

KOK = KR.KOK


@pytest.mark.parametrize("yol", [
    os.path.join(KOK, "data", "kalite.db"),
    os.path.join(KOK, "data", "alt", "x.db"),
    os.path.join(KOK, "yedek", "kalite_SEMA4_YEDEK_x.db"),
    os.path.join(KOK, "DATA", "kalite.db"),                               # Windows: büyük/küçük harf
    pathlib.Path(KOK, "data", "kalite.db").as_uri() + "?mode=ro",          # _baglan salt okunur
    "file:" + os.path.join(KOK, "data", "kalite.db") + "?mode=ro",
    pathlib.Path(KOK, "data", "kalite.db"),
    # doğrulama DÜŞÜK-7: aynı klasöre çözülen başka yazımlar
    "\\\\?\\" + os.path.join(KOK, "data", "kalite.db"),
    "\\\\.\\" + os.path.join(KOK, "data", "kalite.db"),
    "\\\\localhost\\" + KOK[0] + "$" + os.path.join(KOK[2:], "data", "kalite.db"),
    "\\\\?\\UNC\\localhost\\" + KOK[0] + "$" + os.path.join(KOK[2:], "yedek", "x.db"),
    "file://localhost/" + pathlib.Path(KOK, "data", "kalite.db").as_posix() + "?mode=ro",
])
def test_gercek_klasorler_yasak(yol):
    assert KR.yasak_yol(yol)


@pytest.mark.parametrize("yol", [
    "\\\\?\\" + os.path.join(KOK, "data", "kalite.db"),
    "\\\\.\\" + os.path.join(KOK, "data", "kalite.db"),
    "\\\\localhost\\" + KOK[0] + "$" + os.path.join(KOK[2:], "data", "kalite.db"),
    "\\\\127.0.0.1\\" + KOK[0] + "$" + os.path.join(KOK[2:], "data", "kalite.db"),
    "\\\\?\\UNC\\localhost\\" + KOK[0] + "$" + os.path.join(KOK[2:], "yedek", "x.db"),
    "//localhost/" + KOK[0] + "$" + pathlib.PurePath(KOK[2:], "data", "kalite.db").as_posix(),
    "file://127.0.0.1/" + KOK[0] + "$" + pathlib.PurePath(KOK[2:], "data", "kalite.db").as_posix(),
])
def test_yerel_paylasim_yollari_agsiz_yasak(yol, monkeypatch):
    """Antigravity 5b-1 BULGU-02: yönetici paylaşımı (D$) kapalı ya da kısıtlı makinede de
    yakalanır; os.stat/SMB'ye gerek kalmadan metinle çözülür."""
    monkeypatch.setattr(KR, "_ayni_klasorde", lambda yol: False)
    assert KR.yasak_yol(yol)


@pytest.mark.parametrize("yol", [
    ":memory:", "",
    os.path.join(KOK, "tests", "x.db"),
    os.path.join(KOK, "database.db"),
    os.path.join(KOK, "dataset", "x.db"),                                 # "data" önekli başka klasör
    r"C:\Temp\pytest-1\data\kalite.db",
])
def test_diger_yollar_serbest(yol):
    assert not KR.yasak_yol(yol)


def test_koruma_etkin():
    """conftest sqlite3.connect'i sarar: yasak yolda bağlantı açılmadan hata."""
    with pytest.raises(KR.GercekVeriHatasi):
        sqlite3.connect(pathlib.Path(KOK, "data", "olmayan_dosya_koruma_testi.db").as_uri()
                        + "?mode=ro", uri=True)
    assert not os.path.exists(os.path.join(KOK, "data", "olmayan_dosya_koruma_testi.db"))
