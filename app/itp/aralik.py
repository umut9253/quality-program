# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Aralık eşleme ve tek-satır seçimi.

Database.xlsx'teki SUMPRODUCT(...)=1 kuralının Python karşılığı: bir tablo
sorgusu ya TAM BİR satır döndürür ya da EslesmeHatasi fırlatır. Yanlış veri
sessizce sonuç üretmez.
"""
from app.dil import _


class EslesmeHatasi(LookupError):
    """Tabloda 0 veya birden fazla satır eşleşti."""


def aralikta(x, alt, alt_dahil, ust, ust_dahil):
    """x aralıkta mı? Sınırların dahil olup olmadığı bayrakla verilir.

    API 5L sınırları düzensizdir (alt sınır bazen dahil, bazen hariç), bu yüzden
    basit "alt < x ≤ üst" yetmez.
    """
    alt_ok = x > alt or (alt_dahil and x == alt)
    ust_ok = x < ust or (ust_dahil and x == ust)
    return alt_ok and ust_ok


def tek_satir(satirlar, kosul, aciklama):
    """kosul(satir) True olan TEK satırı döndürür; değilse EslesmeHatasi."""
    eslesen = [s for s in satirlar if kosul(s)]
    if len(eslesen) != 1:
        raise EslesmeHatasi(
            _("{aciklama}: {d} satır eşleşti (1 bekleniyordu)").format(aciklama=aciklama, d=len(eslesen)))
    return eslesen[0]
