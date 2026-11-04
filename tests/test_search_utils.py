# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""app/search_utils.py testleri — STD arama: Türkçe harf katlama + çok kelimeli filtre.

TDD kaydı (FAZ 1 doğrulaması): bu testler modül yazılmadan ÖNCE yazıldı.
Spec: docs/superpowers/specs/2026-07-17-std-arama-turkce-fold-design.md
"""
import pytest

from app.search_utils import tr_fold, matches_query


# --- tr_fold ---------------------------------------------------------------

def test_tr_fold_buyuk_i_noktali():
    # Python'un naif .lower()'ı "İ" için "i" + U+0307 üretir; tr_fold düz "i" vermeli
    assert tr_fold("İMALAT") == "imalat"


def test_tr_fold_buyuk_i_noktasiz():
    # "ISIL" → dotless I'lar da "i"ye katlanır (ı/i eşdeğerliği)
    assert tr_fold("ISIL") == "isil"


def test_tr_fold_kucuk_dotless():
    assert tr_fold("ısıl") == "isil"


def test_tr_fold_diger_turkce_harfler():
    assert tr_fold("ÇEKME ĞÜŞÖ") == "çekme ğüşö"


def test_tr_fold_bos_metin():
    assert tr_fold("") == ""


# --- matches_query ----------------------------------------------------------

def test_tek_kelime_turkce_duyarsiz():
    # Kullanıcı "imalat" yazınca büyük harfli Türkçe başlık bulunmalı
    assert matches_query("imalat", "TS EN 1090", "ÇELİK İMALAT KURALLARI", "TSE")


def test_cok_kelime_and_mantigi():
    # "asme ix" → her iki kelime de kayıtta geçmeli (farklı konumlarda olabilir)
    assert matches_query("asme ix", "ASME BPVC Section IX", "Welding Qualifications", "ASME")


def test_eslesmeyen_kelime_false():
    # Kelimelerden biri geçmiyorsa kayıt elenmelidir
    assert not matches_query("asme d1.1", "ASME BPVC Section IX", "Welding Qualifications", "ASME")


def test_bos_sorgu_hepsini_gecirir():
    assert matches_query("", "EN 10255", "Borular", "CEN")


def test_alan_siniri_sahte_eslesme_yok():
    # Eski kod no+title bitiştirdiği için "10255", no="EN 10" + title="255 borular"
    # kaydını yanlışlıkla bulurdu; alan ayracıyla bu sahte eşleşme olmamalı
    assert not matches_query("10255", "EN 10", "255 borular", "CEN")


def test_ingilizce_buyuk_i_piping():
    # Klasik Türkçe-I ikilemi: "piping" araması "PIPING" başlığını bulabilmeli
    assert matches_query("piping", "ASME B31.3", "PROCESS PIPING", "ASME")
