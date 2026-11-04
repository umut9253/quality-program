# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Kaplama kabul kriterleri — ISO 21809-1/-2 (app/itp/veri/iso21809.py)."""
from app.itp.aralik import aralikta, tek_satir
from app.itp.hesap import Deger
from app.itp.veri import iso21809 as KAP

ATIF_KALINLIK = "ISO 21809-1 Table 2"


def min_kalinlik(sinif, kalinlik_sinifi, pm):
    """Pm (kg/m, yuvarlanmamış) aralığına göre min toplam kaplama kalınlığı (mm)."""
    s = tek_satir(KAP.KALINLIK,
                  lambda r: r[1] == sinif and r[2] == kalinlik_sinifi
                  and aralikta(pm, r[3], r[4] == "E", r[5], r[6] == "E"),
                  f"{ATIF_KALINLIK} {sinif}{kalinlik_sinifi} Pm={pm:.3f}")
    return Deger(s[7], s[8], ATIF_KALINLIK)


def kriterler(standart, sinif):
    """Standart + sınıfa uyan kriter satırları, kaynak sırasıyla ('tümü' her sınıfa dahil)."""
    return [r for r in KAP.KRITERLER if r[0] == standart and r[1] in (sinif, "tümü")]
