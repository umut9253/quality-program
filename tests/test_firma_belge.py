# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Firma adı belgeye (spec 2026-11-02 §3): olustur(firma=), {firma} yer tutucusu, eski görüntü."""
import dataclasses
from pathlib import Path

import pytest

from app.itp import goruntu
from app.itp.dokuman import Denetim, Dokuman, Metin
from app.itp.olustur import olustur
from tools import ornek_cikti as O

FIRMA = "ÖRNEK FİRMA"
KOK = Path(__file__).resolve().parent.parent


def metinler(d):
    return [p.metin for b in d.bolumler for s in b.satirlar for p in s.kabul
            if isinstance(p, Metin)]


@pytest.mark.parametrize("ad", ["", "   "])
def test_firma_adi_bossa_olusturulmaz(ad):
    with pytest.raises(ValueError, match="Firma adı ayarlanmamış"):
        olustur("itp_en", O.KURUM_C_BASLIK, O.KURUM_C, firma=ad)


def test_itp_markalama_firma_adiyla():
    d = olustur("itp_en", O.KURUM_C_BASLIK, O.KURUM_C, firma=f"  {FIRMA} ")
    assert d.firma == FIRMA
    m = metinler(d)
    assert any(f"from the pipe end: {FIRMA}, API Spec 5L" in x for x in m)
    assert any(f"at the other end; {FIRMA} stenciled" in x for x in m)
    assert not any("{firma}" in x for x in m)


def test_kp_markalama_firma_adiyla():
    d = olustur("kp_ciplak", O.KURUM_A_BASLIK, O.KURUM_A, firma=FIRMA)
    assert any(f"(Ş.1 Madde 11.2.1): {FIRMA}, API Spec 5L" in x for x in metinler(d))


def test_eski_goruntu_okunur():
    """Şema 6 öncesi kilitli belge: Denetim'de "firma_eski", Dokuman'da firma yok."""
    d = olustur("kp_ciplak", O.KURUM_A_BASLIK, O.KURUM_A, firma=FIRMA)
    g = goruntu.yaz(d)
    del g["firma"]
    for b in g["bolumler"]:
        for s in b["satirlar"]:
            s["denetim"]["firma_eski"] = s["denetim"].pop("firma")
    eski = goruntu.oku(g)
    assert isinstance(eski, Dokuman) and eski.firma is None
    assert eski == dataclasses.replace(d, firma=None)
    assert isinstance(eski.bolumler[0].satirlar[0].denetim, Denetim)


def test_kodda_firmaya_ozgu_ad_kalmadi():
    bulunan = [str(p.relative_to(KOK)) for kok in ("app", "tools") for p in (KOK / kok).rglob("*.py")
               if "ice_aktarim" not in p.parts
               and any(x in p.read_text(encoding="utf-8") for x in ("FIRMA_ESKI", "NOBIS"))]   # goruntu.py eski alan adı: küçük harf
    assert bulunan == []
