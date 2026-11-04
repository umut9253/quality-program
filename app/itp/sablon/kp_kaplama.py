# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Kalite Planı — dış kaplama (TR): BOŞ İSKELET (public depo).

Kaplama bölümleri ISO 21809 verisinden (app/itp/veri/iso21809.py) satır satır üretilir;
o veri public depoda boş olduğu için bölümler de boş gelir.
Bölüm no "2" = şartname listesi (SARTNAMELER); kaplama bölümleri 3 ve 4'tür.
"""
from app.itp.veri.iso21809 import P1, P2

AD = "kp_kaplama"
FORMAT = "KP"
DIL = "tr"
AYRILMIS_BOLUMLER = ("2",)

SARTNAMELER = [
    "Üretim standardı: API 5L, 47. baskı (PSL kalem listesinde)",
    "Dış kaplama standardı: ISO 21809-1 (3 katlı PE/PP)",
    "Dış kaplama standardı: ISO 21809-2 (tek katlı FBE)",
    "Kalite planı talebi / sipariş",
    "Fabrika uygulaması",
]

_URET = {"uret": "kaplama_kriterleri", "sorumlu": "Kaplama üretim / Kalite",
         "kayit": "Vardiya raporu", "firma": "H"}

BOLUMLER = [
    {"no": "1", "baslik": "Ebat", "satirlar": [
        {"no": "1", "aktivite": "Ebat", "spec": "Ş.4", "sorumlu": "Kalite",
         "karakteristik": "Kalem listesi", "frekans": "", "kabul": [{"blok": "ebat"}],
         "kayit": "", "firma": "H"},
    ]},
    {"no": "3", "baslik": "Dış kaplama — ISO 21809-1", "kosul": "dis_kaplama=3LPE|3LPP",
     "standart": P1, "spec": "Ş.2", **_URET},
    {"no": "4", "baslik": "Dış kaplama — ISO 21809-2", "kosul": "dis_kaplama=FBE",
     "standart": P2, "spec": "Ş.3", **_URET},
]
