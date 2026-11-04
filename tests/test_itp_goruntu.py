# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""app/itp/goruntu.py: oluşturulmuş dokümanın JSON anlık görüntüsü (Plan 5a)."""
import importlib.util
import json
from pathlib import Path

import openpyxl
import pytest

from app.firma import Firma
from app.itp import goruntu
from app.itp.excel import excel_yaz
from app.itp.olustur import olustur

FIRMA = "ÖRNEK FİRMA"   # kurgusal firma adı (2026-11-02)

_YOL = Path(__file__).resolve().parent.parent / "tools" / "ornek_cikti.py"
_spec = importlib.util.spec_from_file_location("ornek_cikti", _YOL)
O = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(O)

ORNEKLER = {"kurum_c": ("itp_en", O.KURUM_C_BASLIK, O.KURUM_C),
            "kurum_a": ("kp_ciplak", O.KURUM_A_BASLIK, O.KURUM_A),
            "kurum_a_kaplama": ("kp_kaplama", O.KURUM_A_BASLIK, O.KURUM_A_KAPLAMA)}


@pytest.mark.parametrize("ad", ORNEKLER)
def test_gidis_donus_birebir(ad):
    d = olustur(*ORNEKLER[ad], firma=FIRMA)
    metin = json.dumps(goruntu.yaz(d), ensure_ascii=False, allow_nan=False)
    assert goruntu.oku(json.loads(metin)) == d


@pytest.mark.parametrize("ad", ORNEKLER)
def test_goruntuden_excel_hucre_hucre_ayni(ad, tmp_path):
    d = olustur(*ORNEKLER[ad], firma=FIRMA)
    a = excel_yaz(d, tmp_path / "dogrudan.xlsx", Firma(FIRMA))
    b = excel_yaz(goruntu.oku(json.loads(json.dumps(goruntu.yaz(d)))), tmp_path / "goruntu.xlsx", Firma(FIRMA))
    wa, wb = openpyxl.load_workbook(a), openpyxl.load_workbook(b)
    assert wa.sheetnames == wb.sheetnames
    for sa, sb in zip(wa.worksheets, wb.worksheets):
        assert [[c.value for c in r] for r in sa.iter_rows()] == \
               [[c.value for c in r] for r in sb.iter_rows()]
        assert sorted(map(str, sa.merged_cells.ranges)) == sorted(map(str, sb.merged_cells.ranges))


def test_bilinmeyen_tur_hata():
    class Yabanci:
        pass
    with pytest.raises(goruntu.GoruntuHatasi):
        goruntu.yaz(Yabanci())
    with pytest.raises(goruntu.GoruntuHatasi):
        goruntu.oku({"__tur": "YokBoyleTur"})


@pytest.mark.parametrize("bozuk", [
    {"__tur": "Satir", "no": "1"},                 # eksik alan (denetim BULGU-02)
    {"__tur": "Satir", "yok_boyle_alan": 1},       # bilinmeyen alan
    {"__liste": 5},                                # liste olmayan liste
    {"__sozluk": [1]},                             # sözlük olmayan sözlük
])
def test_bozuk_goruntu_anlasilir_hata(bozuk):
    with pytest.raises(goruntu.GoruntuHatasi):
        goruntu.oku(bozuk)
