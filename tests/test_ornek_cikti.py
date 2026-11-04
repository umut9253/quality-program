# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""tools/ornek_cikti.py smoke testi: 4 örnek dosya yazılır ve openpyxl ile açılır."""
import importlib.util
from pathlib import Path

import openpyxl

YOL = Path(__file__).resolve().parent.parent / "tools" / "ornek_cikti.py"


def test_ornek_cikti_dort_dosya(tmp_path):
    spec = importlib.util.spec_from_file_location("ornek_cikti", YOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    yollar = mod.main(tmp_path)
    assert len(yollar) == 4
    assert len({p.name for p in yollar}) == 4
    for p in yollar:
        assert p.exists()
        wb = openpyxl.load_workbook(p)
        # ITP'de ilk sayfa kapak (2026-11-03): tablo "ITP" sayfasında denetlenir
        assert (wb["ITP"] if "ITP" in wb.sheetnames else wb.worksheets[0]).max_row > 5
