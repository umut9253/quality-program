# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Arama yardımcıları: Türkçe harf katlama ve çok kelimeli eşleştirme.

Saf fonksiyonlar — PyQt6 bağımlılığı yok, headless test edilebilir.
Spec: docs/superpowers/specs/2026-07-17-std-arama-turkce-fold-design.md
"""

# İ/I/ı/i tek harfe katlanır: hem Türkçe ("imalat"→"İMALAT") hem İngilizce
# ("piping"→"PIPING") arama çalışsın diye ı/i eşdeğer sayılır.
_TR_FOLD_MAP = str.maketrans({"İ": "i", "I": "i", "ı": "i"})


def tr_fold(text: str) -> str:
    """Metni arama amaçlı katlar: Türkçe-I sorunu olmadan küçük harfe çevirir."""
    folded = text.translate(_TR_FOLD_MAP).lower()
    # Naif .lower()'dan gelmiş olabilecek birleşik nokta (U+0307) temizlenir
    return folded.replace("̇", "")


def matches_query(query: str, *fields: str) -> bool:
    """Sorgudaki her kelime, alanların katlanmış halinde geçiyorsa True.

    Alanlar " " ayracıyla birleştirilir — alan sınırında sahte eşleşme olmaz.
    Boş sorgu her kaydı geçirir.
    """
    tokens = tr_fold(query).split()
    if not tokens:
        return True
    haystack = " ".join(tr_fold(f or "") for f in fields)
    return all(t in haystack for t in tokens)
