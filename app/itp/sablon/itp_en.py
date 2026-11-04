# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""ITP (EN) şablonu: BOŞ İSKELET (public depo).

Satır içerikleri (kabul kriterleri, frekanslar, madde atıfları) standart metninden
türediği için bu depoda yoktur; yalnızca bölüm düzeni ve satır yapısı vardır.
Her bölümde görünür bir yer tutucu satır bulunur.
"""

AD = "itp_en"
FORMAT = "ITP"
DIL = "en"

SARTNAMELER = [
    "API 5L 47th Edition - Specification for Line Pipe",
    "Purchase order / ITP request",
    "ISO 21809-1 - External coatings: three-layer polyolefin coatings (3-layer PE and 3-layer PP)",
    "ISO 21809-2 - External coatings: single-layer fusion-bonded epoxy coatings",
]

QD = "Quality dept."
YOK = "Acceptance criteria not included in the public repository (copyrighted standard content)."


def _s(no, aktivite, spec, sorumlu, karakteristik, frekans, kabul, kayit="", firma="H",
       kosul=None, kalite_basina=False):
    satir = {"no": no, "aktivite": aktivite, "spec": spec, "sorumlu": sorumlu,
             "karakteristik": karakteristik, "frekans": frekans, "kabul": kabul,
             "kayit": kayit, "firma": firma}
    if kosul:
        satir["kosul"] = kosul
    if kalite_basina:
        satir["kalite_basina"] = True
    return satir


def _bolum(no, baslik, kosul=None):
    b = {"no": no, "baslik": baslik,
         "satirlar": [_s(f"{no}.1", baslik, "", QD, "", "", [YOK])]}
    if kosul:
        b["kosul"] = kosul
    return b


BOLUMLER = [
    _bolum("1", "Incoming HRC, welding consumables"),
    _bolum("2", "Forming, welding & NDT"),
    _bolum("3", "Visual & dimensional inspection"),
    _bolum("4", "Destructive testing"),
    _bolum("5", "Coating: three-layer PE/PP acc. to ISO 21809-1", kosul="dis_kaplama=3LPE|3LPP"),
    _bolum("6", "Coating: fusion-bonded epoxy acc. to ISO 21809-2", kosul="dis_kaplama=FBE"),
    _bolum("7", "Marking"),
    _bolum("8", "Final documentation"),
]
