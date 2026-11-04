# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Oluşturulmuş dokümanın JSON anlık görüntüsü (Plan 5a).

Kilitli revizyon bu görüntüden Excel'e aktarılır: sonradan standart verisi ya da kod
değişse de müşteriye gidenin aynısı çıkar. Gidiş-dönüş birebirdir (test): tuple → JSON
dizisi; list ve dict etiketlenir ({"__liste": ...}, {"__sozluk": ...}); dataclass'lar tür
adıyla ({"__tur": "Satir", ...}). Yalnız dokuman/hesap modüllerindeki türler kabul edilir.
"""
import dataclasses

from app.itp import dokuman, hesap
from app.dil import _


# Eski görüntü alan adı → güncel ad: kayıtlı kilitli belgeler okunmaya devam etsin
# (2026-11-02 firma kimliği: Denetim.firma_eski → firma). Eksik Dokuman.firma varsayılanla None olur.
ESKI_ALANLAR = {"Denetim": {"firma_eski": "firma"}}


class GoruntuHatasi(Exception):
    """Görüntüye çevrilemeyen ya da tanınmayan değer."""


_TURLER = {t.__name__: t for m in (dokuman, hesap) for t in vars(m).values()
           if isinstance(t, type) and dataclasses.is_dataclass(t)}


def yaz(x):
    if dataclasses.is_dataclass(x) and not isinstance(x, type):
        ad = type(x).__name__
        if _TURLER.get(ad) is not type(x):
            raise GoruntuHatasi(_("Görüntüye yazılamayan tür: {ad}").format(ad=ad))
        return {"__tur": ad, **{f.name: yaz(getattr(x, f.name)) for f in dataclasses.fields(x)}}
    if isinstance(x, tuple):
        return [yaz(v) for v in x]
    if isinstance(x, list):
        return {"__liste": [yaz(v) for v in x]}
    if isinstance(x, dict):
        if not all(isinstance(k, str) for k in x):
            raise GoruntuHatasi(_("Sözlük anahtarları metin olmalı."))
        return {"__sozluk": {k: yaz(v) for k, v in x.items()}}
    if x is None or isinstance(x, (str, bool, int, float)):
        return x
    raise GoruntuHatasi(_("Görüntüye yazılamayan değer: {name__}").format(name__=type(x).__name__))


def oku(x):
    if isinstance(x, list):
        return tuple(oku(v) for v in x)
    if isinstance(x, dict):
        if "__liste" in x:
            if not isinstance(x["__liste"], list):
                raise GoruntuHatasi(_("Bozuk görüntü: liste bekleniyordu."))
            return [oku(v) for v in x["__liste"]]
        if "__sozluk" in x:
            if not isinstance(x["__sozluk"], dict):
                raise GoruntuHatasi(_("Bozuk görüntü: sözlük bekleniyordu."))
            return {k: oku(v) for k, v in x["__sozluk"].items()}
        tur = _TURLER.get(x.get("__tur"))
        if tur is None:
            raise GoruntuHatasi(_("Tanınmayan görüntü türü: {d!r}").format(d=x.get('__tur')))
        eski = ESKI_ALANLAR.get(tur.__name__, {})
        alanlar = {eski.get(k, k): oku(v) for k, v in x.items() if k != "__tur"}
        try:
            return tur(**alanlar)
        except TypeError as e:   # eksik / fazla alan
            raise GoruntuHatasi(_("Bozuk görüntü verisi ({name__}): {e}").format(name__=tur.__name__, e=e)) from None
    return x
