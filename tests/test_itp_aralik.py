# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""app/itp/aralik.py testleri — Database.xlsx 'alt dahil / üst dahil' kodlaması
ve SUMPRODUCT(...)=1 tek-satır kuralının Python karşılığı."""
import pytest

from app.itp.aralik import EslesmeHatasi, aralikta, tek_satir


def test_alt_dahil_sinirda_true():
    # API 5L: 60,3 ≤ D ≤ 168,3 → 60,3 bu satıra düşer
    assert aralikta(60.3, 60.3, True, 168.3, True)


def test_ust_haric_sinirda_false():
    # D < 60,3 satırı 60,3'ü almaz
    assert not aralikta(60.3, 0, True, 60.3, False)


def test_alt_haric_sinirda_false():
    # 168,3 < D ≤ 610 satırı 168,3'ü almaz
    assert not aralikta(168.3, 168.3, False, 610, True)


def test_ic_deger():
    assert aralikta(100, 60.3, True, 168.3, True)


def test_tek_satir_bir_eslesme():
    assert tek_satir([1, 2, 3], lambda s: s == 2, "deneme") == 2


def test_tek_satir_sifir_eslesme_hata():
    with pytest.raises(EslesmeHatasi, match="0 satır"):
        tek_satir([1, 2, 3], lambda s: s == 9, "deneme")


def test_tek_satir_cift_eslesme_hata():
    with pytest.raises(EslesmeHatasi, match="2 satır"):
        tek_satir([1, 2, 2], lambda s: s == 2, "deneme")
