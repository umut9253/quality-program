# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Kabul kriteri parçaları → Excel ızgara satırları (2026-11-03, Word ITP iç tabloları).

Kabul alanı ALT_SUTUN alt sütundur. Art arda gelen Metin / ElleGirilecek tek satırda (alanın
tamamı birleşik, satırlar "\\n" ile); KalemTablosu'nun başlığı ve her satırı ayrı satırda, n
sütunu alt sütunlara paylaştırılır. openpyxl import edilmez: düzen burada, yazım excel.py'de.
"""
from dataclasses import dataclass

from app.itp.dokuman import ElleGirilecek, KalemTablosu, Metin
from app.dil import _

ALT_SUTUN = 8
METIN, BASLIK, VERI = "metin", "baslik", "veri"
# Excel satır yüksekliği 409 pt ile sınırlı (≈ 33 satır 9 pt): uzun metin bu kadar satırlık
# parçalara bölünür, kesilmez (doğrulama ORTA-4)
METIN_SATIR = 20


@dataclass(frozen=True)
class IzgaraSatiri:
    tur: str           # METIN | BASLIK | VERI
    hucreler: tuple    # ((ilk alt sütun, son alt sütun, metin), ...) 0 tabanlı, uçlar dahil
    elle: bool = False


def dagit(n, alt=ALT_SUTUN):
    """n mantıksal sütun → alt sütun aralıkları; ilk (alt mod n) sütun bir alt sütun fazla."""
    if not 1 <= n <= alt:
        raise TypeError(_("kalem tablosu {n} sütun; kabul alanı {alt} alt sütun").format(
            n=n, alt=alt))
    taban, artik = divmod(alt, n)
    out, bas = [], 0
    for i in range(n):
        g = taban + (1 if i < artik else 0)
        out.append((bas, bas + g - 1))
        bas += g
    return tuple(out)


def izgara(parcalar, alt=ALT_SUTUN):
    satirlar, metin, elle = [], [], False

    def bosalt():
        nonlocal metin, elle
        parca, n = [], 0
        for m in metin:
            k = m.count("\n") + 1
            if parca and n + k > METIN_SATIR:
                satirlar.append(IzgaraSatiri(METIN, ((0, alt - 1, "\n".join(parca)),), elle))
                parca, n = [], 0
            parca.append(m)
            n += k
        if parca:
            satirlar.append(IzgaraSatiri(METIN, ((0, alt - 1, "\n".join(parca)),), elle))
        metin, elle = [], False

    for p in parcalar:
        if isinstance(p, Metin):
            metin.append(p.metin)
        elif isinstance(p, ElleGirilecek):
            metin.append(f"ELLE GİRİLECEK: {p.etiket}")
            elle = True
        elif isinstance(p, KalemTablosu) and len(p.basliklar) > alt:
            # kilitli eski görüntü (ör. 2026-11-03 öncesi 19-20 sütunlu kimya): eski düz biçim
            metin += [" | ".join(p.basliklar)] + [" | ".join(x) for x in p.satirlar]
        elif isinstance(p, KalemTablosu):
            bosalt()
            araliklar = dagit(len(p.basliklar), alt)
            for tur, satir in [(BASLIK, p.basliklar)] + [(VERI, x) for x in p.satirlar]:
                satirlar.append(IzgaraSatiri(tur, tuple(
                    (a, b, str(m)) for (a, b), m in zip(araliklar, satir, strict=True))))
        else:
            raise TypeError(_("tanımsız kabul parçası {p!r}").format(p=p))
    bosalt()
    return tuple(satirlar) or (IzgaraSatiri(METIN, ((0, alt - 1, ""),)),)
