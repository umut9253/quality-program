# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Arayüz dili (2026-11-02; spec docs/superpowers/specs/2026-11-02-ingilizce-dil-destegi-design.md).

Kaynak dil Türkçe: kodda metinler `_("Kaydet")` ile sarılır; etkin dil İngilizceyse katalogdan
(`app/dil_en.py`) karşılığı döner. Süreç geneli tek dil: masaüstü kullanıcının dilini `ayarla` ile
etkinleştirir; tablet sunucusu ayarlamaz, Türkçe kalır. Qt'siz (database, kimlik, itp kuralları
da kullanır).

- `N_("…")`: modül yüklenirken değerlendirilen sabitleri işaretler (çevirmez); kullanıldığı yerde
  `_()` ile çevrilir (dil program çalışırken değişebilir).
- `deger("Aktif")`: veritabanında Türkçe duran seçmeli değerin gösterimi (D3); kayda Türkçe yazılır.
Katalogda karşılığı olmayan metin Türkçe kalır; `tests/test_dil_katalog.py` bunu yakalar.
"""
from .dil_en import EN

DILLER = ("tr", "en")
DIL_ADI = {"tr": "Türkçe", "en": "English"}
_etkin = "tr"


def ayarla(dil):
    global _etkin
    if dil not in DILLER:
        raise ValueError(f"Bilinmeyen dil: {dil!r} {DILLER}")
    _etkin = dil


def etkin():
    return _etkin


def _(metin):
    return EN.get(metin, metin) if _etkin == "en" else metin


def deger(metin):
    """Seçmeli veri değerinin gösterimi; boş/None olduğu gibi döner."""
    return _(metin) if isinstance(metin, str) and metin else metin


def N_(metin):
    return metin
