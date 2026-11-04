# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""app/itp/dokuman.py testleri."""
import pytest

from app.itp.dokuman import (KAPLAMA_SINIFLARI, Bolum, Denetim, Dokuman, ElleGirilecek,
                             Kalem, KalemTablosu, Metin, Satir)
from app.itp.veri import iso21809 as KAP


def kalem(**kw):
    v = dict(no=1, psl="PSL 2", grade="X52M", D=323.9, t=7.9, boy_m=12, miktar_m=1000,
             amac="doğalgaz")
    v.update(kw)
    return Kalem(**v)


def test_kalem_ciplak_varsayilan():
    k = kalem()
    assert (k.dis_kaplama, k.ic_kaplama, k.kaplama_sinifi, k.kalinlik_sinifi) == \
        ("çıplak", "çıplak", None, None)


def test_kalem_3lpe_sinif_gerekli():
    with pytest.raises(ValueError, match="kaplama sınıfı"):
        kalem(dis_kaplama="3LPE")
    assert kalem(dis_kaplama="3LPE", kaplama_sinifi="B", kalinlik_sinifi=2).kaplama_sinifi == "B"


def test_kalem_3lpp_yalniz_c():
    with pytest.raises(ValueError, match="kaplama sınıfı"):
        kalem(dis_kaplama="3LPP", kaplama_sinifi="B", kalinlik_sinifi=1)
    assert kalem(dis_kaplama="3LPP", kaplama_sinifi="C", kalinlik_sinifi=1).kaplama_sinifi == "C"


def test_kalem_fbe_sinif_verilmez():
    with pytest.raises(ValueError, match="verilmez"):
        kalem(dis_kaplama="FBE", kaplama_sinifi="B", kalinlik_sinifi=2)


@pytest.mark.parametrize("alan, deger", [("dis_kaplama", "PE"), ("ic_kaplama", "FBE")])
def test_kalem_desteklenmeyen_kaplama(alan, deger):
    with pytest.raises(ValueError, match="desteklenmiyor"):
        kalem(**{alan: deger})


@pytest.mark.parametrize("alan, deger", [("psl", "PSL 3"), ("psl", "psl 2"),
                                         ("amac", "gaz"), ("amac", "dogalgaz")])
def test_kalem_psl_amac_dogrulama(alan, deger):
    with pytest.raises(ValueError, match="Kalem 7"):
        kalem(no=7, **{alan: deger})


@pytest.mark.parametrize("alan, etiket", [("D", "D"), ("t", "t"), ("boy_m", "boy"),
                                          ("miktar_m", "miktar")])
@pytest.mark.parametrize("deger", [0, -5])
def test_kalem_sayilar_pozitif(alan, etiket, deger):
    # Antigravity BULGU-06: sıfır/negatif ölçü sessizce doküman üretmesin
    with pytest.raises(ValueError, match=f"Kalem 7: {etiket} pozitif"):
        kalem(no=7, **{alan: deger})


def test_kalem_kalinlik_sinifi_gecersiz():
    with pytest.raises(ValueError, match="kalınlık sınıfı"):
        kalem(dis_kaplama="3LPE", kaplama_sinifi="B", kalinlik_sinifi=4)


def test_kaplama_siniflari_veriyle_ayni():
    veri = {r[1] for r in KAP.SINIFLAR if r[0] == KAP.P1}
    assert {s for ss in KAPLAMA_SINIFLARI.values() for s in ss} == veri


def test_denetim_varsayilan_bos():
    assert Denetim("H") == Denetim("H", "", "")


def test_elle_girilecekler_sirali():
    def satir(kabul):
        return Satir("1", "a", "", "", "", "", "", Denetim("H"), tuple(kabul))
    d = Dokuman(format="ITP", dil="en", sablon="t", baslik=None, kalemler=(), sonuclar=(),
                sartnameler=(), bolumler=(Bolum("1", "b", (
                    satir([Metin("x"), ElleGirilecek("Lot size")]),
                    satir([KalemTablosu(("a",), (("1",),)), ElleGirilecek("Mass tolerance")]),
                )),))
    assert d.elle_girilecekler() == ("Lot size", "Mass tolerance")


def test_elle_girilecekler_tekrarsiz_ilk_gorunme_sirasi():
    def satir(kabul):
        return Satir("1", "a", "", "", "", "", "", Denetim("H"), tuple(kabul))
    d = Dokuman(format="ITP", dil="en", sablon="t", baslik=None, kalemler=(), sonuclar=(),
                sartnameler=(), bolumler=(Bolum("1", "b", (
                    satir([ElleGirilecek("Lot size"), ElleGirilecek("Mass tolerance")]),
                    satir([ElleGirilecek("Lot size"), ElleGirilecek("Charpy")]),
                    satir([ElleGirilecek("Mass tolerance")]),
                )),))
    assert d.elle_girilecekler() == ("Lot size", "Mass tolerance", "Charpy")
