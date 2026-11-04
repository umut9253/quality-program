# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""tools/itp_ekran_goruntusu.py smoke testi: iki PNG tmp_path'e yazılır (offscreen)."""
import importlib.util
from pathlib import Path

YOL = Path(__file__).resolve().parent.parent / "tools" / "itp_ekran_goruntusu.py"


def test_ekran_goruntusu_iki_png(tmp_path):
    spec = importlib.util.spec_from_file_location("itp_ekran_goruntusu", YOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    yollar = mod.main(tmp_path)
    assert [p.name for p in yollar] == ["itp-sekmesi.png", "itp-sekmesi-kp.png"]
    for p in yollar:
        assert p.exists() and p.stat().st_size > 0
