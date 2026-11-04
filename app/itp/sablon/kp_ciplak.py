# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Kalite Planı — çıplak boru (TR): BOŞ İSKELET (public depo).

Satır içerikleri (kabul kriterleri, frekanslar, madde atıfları) standart metninden
türediği için bu depoda yoktur; yalnızca bölüm düzeni ve satır yapısı vardır.
Her bölümde görünür bir yer tutucu satır bulunur.
"""

AD = "kp_ciplak"
FORMAT = "KP"
DIL = "tr"
# Bölüm 2 = şartname listesi; olustur numaralarken bu no'yu atlar.
AYRILMIS_BOLUMLER = ("2",)

SARTNAMELER = [
    "Üretim standardı: API 5L, 47. baskı (PSL kalem listesinde)",
    "Kalite planı talebi / sipariş",
    "Fabrika uygulaması",
]

KU = "Kalite ve Üretim"
YOK = "Kabul kriteri public depoda yok (standart içeriği telif kapsamındadır)."


def _s(no, aktivite, karakteristik, kabul, frekans, sorumlu=KU, spec="Ş.1", kayit="",
       firma="H", kosul=None, kalite_basina=False):
    satir = {"no": no, "aktivite": aktivite, "spec": spec, "sorumlu": sorumlu,
             "karakteristik": karakteristik, "frekans": frekans, "kabul": kabul,
             "kayit": kayit, "firma": firma}
    if kosul:
        satir["kosul"] = kosul
    if kalite_basina:
        satir["kalite_basina"] = True
    return satir


def _bolum(no, baslik):
    return {"no": no, "baslik": baslik, "satirlar": [_s(no, baslik, "", [YOK], "", spec="")]}


BOLUMLER = [
    {"no": "1", "baslik": "Ebat", "satirlar": [
        _s("1", "Ebat", "Kalem listesi", [{"blok": "ebat"}], "", spec="Ş.2")]},
] + [_bolum(no, baslik) for no, baslik in (
    ("3", "Başlangıç malzemesi"), ("4", "Doğrulama"), ("5", "Kimyasal kompozisyon"),
    ("6", "Lot"), ("7", "Mekanik özellikler"), ("8", "Kaynak geometrisi"), ("9", "Boyutlar"),
    ("10", "Boru ucu"), ("11", "Hidrostatik test"), ("12", "Ultrasonik kontrol"),
    ("13", "Radyografik kontrol"), ("14", "Kalıcı manyetizma"), ("15", "Tamir kaynağı"),
    ("16", "Yüzey kusurları"), ("17", "Uygunsuzluk yönetimi"), ("18", "Markalama"),
    ("19", "Kalite dokümantasyonu"))]
