# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""app/itp/kayit.py: ITP/KP sipariş kaydı kuralları (Plan 5a, K12/K15)."""
import dataclasses
import importlib.util
import json
from pathlib import Path

import pytest

from app import kimlik as K
from app.itp import goruntu
from app.itp import kayit as R

FIRMA = "ÖRNEK FİRMA"   # kurgusal firma adı (2026-11-02)

_YOL = Path(__file__).resolve().parent.parent / "tools" / "ornek_cikti.py"
_spec = importlib.util.spec_from_file_location("ornek_cikti", _YOL)
O = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(O)


def taslak(no="QP-1", rev="0"):
    b = dataclasses.replace(O.KURUM_A_BASLIK, dokuman_no=no, rev=rev)
    return R.kayit_kur("kp_ciplak", b, O.KURUM_A)


def test_kayit_kur_taslak_ve_alanlar():
    v = taslak()
    assert (v["no"], v["rev"], v["durum"], v["rev_sira"]) == ("QP-1", "0", R.TASLAK, 0)
    assert v["siparis_ozel"] == [] and v["son_aktarim"] is None and v["goruntu"] is None
    assert v["onay"] is None and v["onek_duzelt"] is False
    json.dumps(v, allow_nan=False)                       # veritabanına yazılabilir
    sablon, baslik, kalemler, onek = R.girdiler(v)
    assert (sablon, baslik, kalemler, onek) == ("kp_ciplak", dataclasses.replace(
        O.KURUM_A_BASLIK, dokuman_no="QP-1", rev="0"), tuple(O.KURUM_A), False)


def test_dokuman_no_zorunlu():
    with pytest.raises(R.KayitHatasi, match="Doküman No"):
        R.kaydet_kontrol([], taslak(no="  "))


def test_no_rev_benzersiz_turkce_harf_katlamali():
    var = taslak(no="KP-ÖRNEK-1")
    with pytest.raises(R.KayitHatasi, match="zaten var"):
        R.kaydet_kontrol([var], taslak(no="kp-örnek-1"))
    R.kaydet_kontrol([var], taslak(no="KP-ÖRNEK-2"))            # farklı no serbest
    R.kaydet_kontrol([var], var, haric=0)                        # kendisi sayılmaz


def test_kilitli_kayit_kaydedilemez_ve_girdisi_degismez():
    v = R.onayla(taslak(), "05.11.2026", "", "ali", firma=FIRMA)
    with pytest.raises(R.KayitHatasi, match="kilitli"):
        R.kaydet_kontrol([], v)
    with pytest.raises(R.KayitHatasi, match="kilitli"):
        R.girdileri_guncelle(v, *R.girdiler(v))


def test_kaydetme_ve_aktarim_kilitlemez():
    v = taslak()
    d = R.dokuman_uret(v, firma=FIRMA)
    v2 = R.aktarim_kaydi(v, d)
    assert v2["durum"] == R.TASLAK and goruntu.oku(v2["son_aktarim"]) == d
    v3 = R.girdileri_guncelle(v2, "kp_kaplama", R.girdiler(v2)[1], O.KURUM_A_KAPLAMA, False)
    assert v3["durum"] == R.TASLAK and v3["son_aktarim"] == v2["son_aktarim"]


def test_onay_kilitler_goruntu_son_aktarim():
    v = taslak()
    d_gonderilen = R.dokuman_uret(v, firma=FIRMA)
    v = R.aktarim_kaydi(v, d_gonderilen)
    # aktarımdan sonra düzeltme: kilitli görüntü yine müşteriye giden (son aktarım)
    v = R.girdileri_guncelle(v, "kp_kaplama", R.girdiler(v)[1], O.KURUM_A_KAPLAMA, False)
    o = R.onayla(v, "05.11.2026", "yazı 123", "ali", firma=FIRMA)
    assert o["durum"] == R.ONAYLI and R.kilitli(o)
    assert o["onay"] == {"tarih": "05.11.2026", "not": "yazı 123", "kaydeden": "ali"}
    assert R.dokuman_uret(o, firma=FIRMA) == d_gonderilen


def test_aktarimsiz_onay_goruntuyu_o_an_uretir():
    v = taslak()
    o = R.onayla(v, "05.11.2026", "", "ali", firma=FIRMA)
    assert R.dokuman_uret(o, firma=FIRMA) == R.dokuman_uret(v, firma=FIRMA)


def test_onay_tarihi_gecerli_olmali():
    with pytest.raises(R.KayitHatasi, match="tarih"):
        R.onayla(taslak(), "2026-13-45", "", "ali", firma=FIRMA)
    with pytest.raises(R.KayitHatasi, match="taslak"):
        R.onayla(R.onayla(taslak(), "05.11.2026", "", "ali", firma=FIRMA), "06.11.2026", "", "ali", firma=FIRMA)


def test_yeni_rev_taslaktan_revize_ve_artirim():
    v = taslak(rev="00")
    eski, yeni = R.yeni_rev([v], v, firma=FIRMA)
    assert eski["durum"] == R.REVIZE and eski["goruntu"] is not None
    assert (yeni["rev"], yeni["baslik"]["rev"], yeni["rev_sira"], yeni["durum"]) == \
           ("01", "01", 1, R.TASLAK)
    assert yeni["son_aktarim"] is None and yeni["onay"] is None and yeni["goruntu"] is None


def test_yeni_rev_onayli_kaynak_oldugu_gibi_kalir():
    o = R.onayla(taslak(), "05.11.2026", "", "ali", firma=FIRMA)
    eski, yeni = R.yeni_rev([o], o, firma=FIRMA)
    assert eski is None and yeni["rev"] == "1"


def test_yeni_rev_yalniz_en_yuksek_revizyondan():
    v = taslak()
    eski, yeni = R.yeni_rev([v], v, firma=FIRMA)
    with pytest.raises(R.KayitHatasi, match="en son revizyon"):
        R.yeni_rev([eski, yeni], eski, firma=FIRMA)
    assert R.en_yuksek_mi([eski, yeni], yeni) and not R.en_yuksek_mi([eski, yeni], eski)


def test_sayisal_olmayan_rev_sorulur():
    v = taslak(rev="A")
    with pytest.raises(R.KayitHatasi, match="sayısal değil"):
        R.yeni_rev([v], v, firma=FIRMA)
    _, yeni = R.yeni_rev([v], v, yeni_rev="B", firma=FIRMA)
    assert yeni["rev"] == "B"
    with pytest.raises(R.KayitHatasi, match="zaten var"):
        R.yeni_rev([v], v, yeni_rev="a", firma=FIRMA)                  # aynı no + rev (harf katlamalı)


def test_kopyala_yeni_no_rev0_taslak():
    o = R.onayla(taslak(rev="3"), "05.11.2026", "", "ali", firma=FIRMA)
    k = R.kopyala([o], o, "QP-2")
    assert (k["no"], k["rev"], k["rev_sira"], k["durum"]) == ("QP-2", "0", 0, R.TASLAK)
    assert k["baslik"]["dokuman_no"] == "QP-2" and k["kalemler"] == o["kalemler"]
    assert k["goruntu"] is None and k["son_aktarim"] is None and k["onay"] is None
    with pytest.raises(R.KayitHatasi, match="zaten var"):
        R.kopyala([o], o, "qp-1")              # aynı no (harf katlamalı): ikinci zincir yok
    with pytest.raises(R.KayitHatasi, match="Doküman No"):
        R.kopyala([o], o, " ")


@pytest.mark.parametrize("rol, durum, gerekce, izin", [
    (K.DUZENLEYICI, "taslak", "", True),
    (K.OKUYUCU, "taslak", "", False),
    (K.DUZENLEYICI, "onayli", "x", False),
    (K.YONETICI, "onayli", "", False),          # gerekçe zorunlu
    (K.YONETICI, "revize", "yanlış sipariş", True),
    (None, "onayli", "sistem", True),           # kullanıcısız (araç/test) = yönetici
])
def test_silme_yetkisi(rol, durum, gerekce, izin):
    v = dict(taslak(), durum=durum)
    if izin:
        R.sil_kontrol(v, rol, gerekce)
    else:
        with pytest.raises(R.KayitHatasi):
            R.sil_kontrol(v, rol, gerekce)


def test_durum_metni():
    v = taslak()
    assert R.durum_metni(v) == "Taslak"
    assert R.durum_metni(R.onayla(v, "05.11.2026", "", "a", firma=FIRMA)) == "🔒 Onaylı (05.11.2026)"
    assert R.durum_metni(R.yeni_rev([v], v, firma=FIRMA)[0]) == "🔒 Revize edildi"


# ── doğrulama ajanı bulguları (2026-11-01) ───────────────────────────
def test_en_yuksek_revize_ise_yeni_rev_acilir():
    """Rev.1 taslağı silinince Rev.0 (revize) en yüksek kalır: numara sıkışmamalı."""
    v = taslak()
    eski, _ = R.yeni_rev([v], v, firma=FIRMA)
    tekrar_eski, yeni = R.yeni_rev([eski], eski, firma=FIRMA)
    assert tekrar_eski is None and yeni["rev"] == "1" and yeni["rev_sira"] == 1


def test_var_olan_dokuman_no_yeni_kayitla_kullanilamaz():
    """Aynı no ile ayrı kayıt rev_sira zincirini bozar: yeni revizyon «Yeni rev» ile açılır."""
    var = taslak(no="QP-1", rev="0")
    with pytest.raises(R.KayitHatasi, match="Yeni rev"):
        R.kaydet_kontrol([var], taslak(no="qp-1", rev="5"))
    diger = taslak(no="QP-2")
    with pytest.raises(R.KayitHatasi, match="Yeni rev"):
        R.kaydet_kontrol([var, diger], dict(diger, no="QP-1", rev="7"), haric=1)
    R.kaydet_kontrol([var], dict(var, rev="00"), haric=0)       # kendi rev metnini düzeltebilir


@pytest.mark.parametrize("goruntu_degeri", [None, {"__sozluk": {}}, {"__tur": "Satir", "no": "1"}])
def test_kilitli_kaydin_bozuk_goruntusu_anlasilir_hata(goruntu_degeri):
    """Denetim BULGU-01/02: görüntü yoksa ya da Dokuman değilse Excel'de çökme yerine hata."""
    v = dict(taslak(), durum=R.ONAYLI, goruntu=goruntu_degeri)
    with pytest.raises(goruntu.GoruntuHatasi):
        R.dokuman_uret(v, firma=FIRMA)


def test_tutarlilik_kontrolu():
    v = R.onayla(taslak(), "05.11.2026", "", "ali", firma=FIRMA)
    R.tutarlilik_kontrol(v)                     # akıştan gelen kilitli kayıt geçer
    R.tutarlilik_kontrol(taslak())
    for bozuk in (dict(v, goruntu=None), dict(v, onay=None), dict(taslak(), durum="x"),
                  dict(taslak(), durum=R.REVIZE)):
        with pytest.raises(R.KayitHatasi):
            R.tutarlilik_kontrol(bozuk)


@pytest.mark.parametrize("bozuk", [None, [], "abc", {"durum": "taslak"},
                                   {k: v for k, v in taslak().items() if k != "rev"}])
def test_tutarlilik_eksik_alan_ve_sozluk_olmayan(bozuk):
    """Doğrulama notu: eksik alanlı ya da sözlük olmayan kayıt da KayitHatasi (5d: tablet girdisi)."""
    with pytest.raises(R.KayitHatasi):
        R.tutarlilik_kontrol(bozuk)
