# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""app/itp/kontrol.py: şartname maddelerinin hedefi olan ortak kontrol listesi (Plan 5b)."""
import dataclasses

import pytest

from app.itp import kontrol as KO
from app.itp.hesap import BoruSonucu
from app.itp.olustur import SABLONLAR, sablon_modulu
from app.itp.veri.iso21809 import KRITERLER
from app.itp.yer_tutucu import KAPLAMA_ASAMALARI

_ALANLAR = {f.name for f in dataclasses.fields(BoruSonucu)}


def _el_satirlari(ad):
    return [s["karakteristik"] for b in sablon_modulu(ad).BOLUMLER for s in b.get("satirlar", ())]


def _uretilen_kriterler():
    return [(r[2], r[3]) for r in KRITERLER if r[2] in KAPLAMA_ASAMALARI and r[6] != "tablo"]


def test_kontrol_kayitlari_bicimi():
    for anahtar, k in KO.KONTROLLER.items():
        assert anahtar == anahtar.strip().lower() and " " not in anahtar
        assert k["tr"].strip() and k["en"].strip(), anahtar
        assert isinstance(k["gelecek"], bool)
        assert set(k["kriterler"]) <= _ALANLAR, anahtar


@pytest.mark.parametrize("ad", SABLONLAR)
def test_her_sablon_satiri_bir_kontrole_eslenir(ad):
    for karakteristik in _el_satirlari(ad):
        assert KO.satir_kontrolu(ad, karakteristik) in KO.KONTROLLER


@pytest.mark.parametrize("ad", SABLONLAR)
def test_eslemede_bayat_metin_yok(ad):
    assert set(KO.SATIRLAR[ad]) == set(_el_satirlari(ad))


def test_uretilen_kaplama_kriterleri_eslenir():
    for asama, kriter in _uretilen_kriterler():
        anahtar = KO.kaplama_kontrolu(asama, kriter)
        assert anahtar.startswith("kaplama_") and anahtar in KO.KONTROLLER, (asama, kriter)


def test_bilinmeyen_satir_ve_kriter_hata():
    with pytest.raises(KeyError):
        KO.satir_kontrolu("kp_ciplak", "Böyle bir satır yok")
    with pytest.raises(KeyError):
        KO.kaplama_kontrolu("uygulanmış kaplama", "Böyle bir kriter yok")


def test_gelecek_isaretli_olanlar_disinda_her_kontrol_bir_sablonda():
    for anahtar, k in KO.KONTROLLER.items():
        assert bool(KO.sablonlari(anahtar)) != k["gelecek"], anahtar


def test_sablonlari():
    assert KO.sablonlari("hidrostatik") == ("itp_en", "kp_ciplak")
    assert KO.sablonlari("kaplama_soyulma") == ("itp_en", "kp_kaplama")
    assert KO.sablonlari("kaplama_kalinlik_toplam") == ("itp_en", "kp_kaplama")
    assert KO.sablonlari("ebat") == ("kp_ciplak", "kp_kaplama")
    assert KO.sablonlari("ic_kaplama_epoksi") == ()
    # V-5b-11 (2026-11-03): fabrikanın yaptığı, şablonu henüz olmayan kaplamalar ve muflu boru
    for k in ("dis_kaplama_epoksi", "ic_kaplama_beton", "dis_kaplama_beton", "muflu_boru"):
        assert KO.KONTROLLER[k]["gelecek"] and KO.sablonlari(k) == (), k


@pytest.mark.parametrize("ad,karakteristik,anahtar", [
    # Doğrulama ORTA-3: bir madde yalnız kendi satırına uygulanmalı (test basıncı maddesi gösterge
    # kalibrasyonu satırına, Charpy tekrar deneyi maddesi çekme tekrar deneyine yazılmamalı).
    ("itp_en", "Calibration of gauges", "hidrostatik_gosterge"),
    ("itp_en", "Checking of working gauge", "hidrostatik_gosterge"),
    ("itp_en", "Test pressure and holding time", "hidrostatik"),
    ("kp_ciplak", "Test basıncı ve tutma süresi", "hidrostatik"),
    ("itp_en", "Calibration", "ut_kalibrasyon"),
    ("itp_en", "Control of calibration", "ut_kalibrasyon"),
    ("kp_ciplak", "Kalibrasyon kontrolü", "ut_kalibrasyon"),
    ("itp_en", "Inspection", "ut_kaynak"),
    ("kp_ciplak", "Kaynak dikişinin otomatik UT kontrolü", "ut_kaynak"),
    ("itp_en", "Tensile retest", "tekrar_cekme"),
    ("itp_en", "Charpy retest", "tekrar_charpy"),
    ("itp_en", "Hardness retest", "tekrar_sertlik"),
    ("kp_ciplak", "Çekme tekrar deneyi", "tekrar_cekme"),
    ("kp_ciplak", "CVN tekrar deneyi", "tekrar_charpy"),
    ("kp_ciplak", "Sertlik tekrar deneyi", "tekrar_sertlik"),
])
def test_ayri_satirlar_ayri_kontrol(ad, karakteristik, anahtar):
    assert KO.satir_kontrolu(ad, karakteristik) == anahtar


@pytest.mark.parametrize("kriter,anahtar", [
    ("Yeni aşındırıcının boyut / şekil / özellikleri", "kaplama_asindirici"),
    ("Aşındırıcının boyut / şekil / özellikleri", "kaplama_asindirici"),
    ("Kumlama hat hızı", "kaplama_kumlama_hizi"),
    ("Kaplama hat hızı", "kaplama_uygulama"),
    ("Kumlanmış yüzeyin görsel muayenesi", "kaplama_yuzey_temizlik"),
    ("Kaplama hattına girmeden önce boru muayenesi", "kaplama_hat_girisi"),   # flash rust
    ("Kumlama öncesi yüzey durumu", "kaplama_yuzey_on"),
])
def test_kaplama_ayri_kriterler(kriter, anahtar):
    assert KO.kaplama_kontrolu("yüzey hazırlığı", kriter) == anahtar


def test_sayisal_kriterler():
    assert KO.KONTROLLER["et_kalinligi"]["kriterler"] == ("et",)
    assert KO.KONTROLLER["hidrostatik"]["kriterler"] == ("p_test",)
    assert KO.KONTROLLER["ut_kaynak"]["kriterler"] == ()
