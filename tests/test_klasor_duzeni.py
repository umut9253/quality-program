# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Klasör düzeni (2026-11-02): tablet istemcisi tablet/ altında (web/ + android/); sunucu ve
APK derleyici aynı yerleri görür. Taşımadan sonra kırılan yol sessizce 404/boş APK verirdi."""
import os
import sys
from pathlib import Path

from app import sunucu

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / "tools"))
import apk_derle  # noqa: E402


def test_tablet_web_arayuzu_yerinde():
    assert Path(sunucu.ARAYUZ) == KOK / "tablet" / "web"
    assert (Path(sunucu.ARAYUZ) / "index.html").is_file()


def test_apk_derleyici_ve_sunucu_ayni_apk_yolunu_gorur():
    assert apk_derle.PROJE == KOK / "tablet" / "android"
    assert (apk_derle.PROJE / "AndroidManifest.xml").is_file()
    assert Path(sunucu.APK_YOLU) == apk_derle.CIKTI


def test_kok_dizinde_daginik_betik_kalmaz():
    kok_py = sorted(p.name for p in KOK.glob("*.py"))
    assert kok_py == ["main.py"]
    assert not list(KOK.glob("app/*.bak"))
    assert os.path.isfile(KOK / "tools" / "ice_aktarim" / "raw_certs.txt")
