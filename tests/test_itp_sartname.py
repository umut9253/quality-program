# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""app/itp/sartname.py: şartname kütüphanesi kuralları (Plan 5b, B1-B9)."""
import pytest

from app import kimlik as K
from app.itp import sartname as S


def metin_maddesi(id_="m1", kontrol="hidrostatik", grup=""):
    return {"id": id_, "kontrol": kontrol, "grup": grup, "kaynak": "7.2.4", "tur": "metin",
            "sutun": "frekans", "metin": {"tr": "Her boru", "en": "Every pipe"}}


def taslak(kurum="KURUM_B", ad="KURUM_B Genel Şartname", rev="0", maddeler=None):
    v = dict(S.kayit_kur(kurum, ad), rev=rev)
    v["maddeler"] = [metin_maddesi()] if maddeler is None else maddeler
    return v


def test_kayit_kur_alanlar():
    v = S.kayit_kur(" KURUM_B ", " KURUM_B Özel Teknik Şartname ", "ozel")
    assert v["kurum"] == "KURUM_B" and v["ad"] == "KURUM_B Özel Teknik Şartname" and v["tur"] == "ozel"
    assert v["durum"] == S.TASLAK and v["rev"] == "0" and v["rev_sira"] == 0
    assert v["gruplar"] == [] and v["maddeler"] == []
    assert tuple(v) == S.ALANLAR
    S.tutarlilik_kontrol(v)


def test_kaydet_kontrol_bos_ve_tekrar():
    with pytest.raises(S.SartnameHatasi, match="Kurum"):
        S.kaydet_kontrol([], dict(taslak(), kurum=" "))
    with pytest.raises(S.SartnameHatasi, match="adı"):
        S.kaydet_kontrol([], dict(taslak(), ad=""))
    with pytest.raises(S.SartnameHatasi, match="zaten var"):
        S.kaydet_kontrol([taslak()], dict(taslak(), kurum="kurum_b"))     # Türkçe katlama: kurum_b = KURUM_B
    with pytest.raises(S.SartnameHatasi, match="Yeni rev"):
        S.kaydet_kontrol([taslak()], taslak(rev="1"))                 # aynı aile yeni kayıtla
    S.kaydet_kontrol([taslak()], taslak(rev="1"), aile=False)
    S.kaydet_kontrol([taslak()], dict(taslak(), not_="x"), haric=0)    # kendi kaydı


def test_kilitli_kaydedilemez():
    with pytest.raises(S.SartnameHatasi, match="kilitli"):
        S.kaydet_kontrol([], dict(taslak(), durum=S.YURURLUKTE))


def test_yururluge_al():
    y = S.yururluge_al(taslak())
    assert y["durum"] == S.YURURLUKTE and S.kilitli(y)
    with pytest.raises(S.SartnameHatasi, match="taslak"):
        S.yururluge_al(y)
    with pytest.raises(S.SartnameHatasi, match="madde"):
        S.yururluge_al(taslak(maddeler=[]))
    with pytest.raises(S.SartnameHatasi, match="TR"):
        S.yururluge_al(taslak(maddeler=[dict(metin_maddesi(), metin={"tr": " ", "en": "x"})]))
    with pytest.raises(S.SartnameHatasi, match="rev"):
        S.yururluge_al(taslak(rev=" "))


@pytest.mark.parametrize("madde, eslesme", [
    (dict(metin_maddesi(), kontrol="yok_boyle"), "bilinmeyen kontrol"),
    (dict(metin_maddesi(), grup="g9"), "tanımsız grup"),
    (dict(metin_maddesi(), tur="baska"), "madde türü"),
    (dict(metin_maddesi(), sutun="aktivite"), "sütun"),
    ({k: v for k, v in metin_maddesi().items() if k != "kaynak"}, "kaynak"),
    ({"id": "m1", "kontrol": "et_kalinligi", "grup": "", "kaynak": "", "tur": "sayisal",
      "kriter": "cap_govde", "alt": None, "ust": 1.0, "birim": "mm"}, "sayısal kriteri"),
    ({"id": "m1", "kontrol": "et_kalinligi", "grup": "", "kaynak": "", "tur": "sayisal",
      "kriter": "et", "alt": 2.0, "ust": 1.0, "birim": "mm"}, "alt sınır"),
    ({"id": "m1", "kontrol": "et_kalinligi", "grup": "", "kaynak": "", "tur": "sayisal",
      "kriter": "et", "alt": None, "ust": 1.0, "birim": "mm", "cap_aralik": [500, 100]},
     "aralık"),
    ({"id": "m1", "kontrol": "ut_kaynak", "grup": "", "kaynak": "", "tur": "uygulanmaz",
      "gerekce": "düz metin"}, "TR/EN"),
    ({"id": "m1", "kontrol": "ut_kaynak", "grup": "", "kaynak": "", "tur": "ek_satir",
      "satir": {}, "yeni_bolum": None}, "TR/EN"),
    ("madde değil", "biçimi"),
])
def test_madde_dogrula_yapi_hatalari(madde, eslesme):
    with pytest.raises(S.SartnameHatasi, match=eslesme):
        S.madde_dogrula(madde, ["g1"])


def _ek_satir(tr="Makro + sertlik"):
    alan = {"tr": "", "en": ""}
    satir = {a: dict(alan) for a in S.SATIR_ALANLARI}
    satir["karakteristik"] = {"tr": tr, "en": "Macro + hardness"}
    satir["kabul"] = {"tr": "Şartname 7.1", "en": "Specification 7.1"}
    return {"id": "m2", "kontrol": "hidrostatik", "grup": "g1", "kaynak": "ÖTŞ 7.1",
            "tur": "ek_satir", "satir": satir,
            "yeni_bolum": {"tr": "İlk gün testleri", "en": "First day tests"}}


def test_gecerli_maddeler_ve_tam_kontrol():
    sayisal = {"id": "m3", "kontrol": "et_kalinligi", "grup": "", "kaynak": "KURUM_C 4.2",
               "tur": "sayisal", "kriter": "et", "alt": -12.5, "ust": 15.0, "birim": "%t",
               "cap_aralik": [100, 500], "et_aralik": None}
    uyg = {"id": "m4", "kontrol": "kaplama_katodik", "grup": "", "kaynak": "ÖTŞ 6.2",
           "tur": "uygulanmaz", "gerekce": {"tr": "İç yüzeyde uygulanmaz", "en": ""}}
    for m in (metin_maddesi(), _ek_satir(), sayisal, uyg):
        S.madde_dogrula(m, ["g1"], tam=True)
    S.madde_dogrula(_ek_satir(tr=""), ["g1"])                    # taslakta boş olabilir
    with pytest.raises(S.SartnameHatasi, match="TR"):
        S.madde_dogrula(_ek_satir(tr=""), ["g1"], tam=True)
    with pytest.raises(S.SartnameHatasi, match="en az biri"):
        S.madde_dogrula(dict(sayisal, alt=None, ust=None), [], tam=True)


def test_tutarlilik_kontrol_kayit():
    v = taslak(maddeler=[metin_maddesi(), _ek_satir()])
    v["gruplar"] = [{"id": "g1", "ad": {"tr": "İlk gün testleri", "en": "First day tests"}}]
    S.tutarlilik_kontrol(v)
    S.tutarlilik_kontrol(S.yururluge_al(v))
    for bozuk in (None, [], {"durum": "taslak"}, dict(v, durum="x"), dict(v, tur="ozel_degil"),
                  dict(v, maddeler=[metin_maddesi(), metin_maddesi()]),         # tekrar id
                  dict(v, gruplar=v["gruplar"] * 2),                            # tekrar grup
                  dict(v, gruplar=[{"id": "g1", "ad": "düz"}]),
                  dict(v, rev_sira="0"), dict(v, kurum=None),
                  dict(S.yururluge_al(v), maddeler=[dict(metin_maddesi(),
                                                         metin={"tr": "", "en": ""})])):
        with pytest.raises(S.SartnameHatasi):
            S.tutarlilik_kontrol(bozuk)


def test_yeni_rev_taslaktan_ve_kilitliden():
    v = taslak()
    eski, yeni = S.yeni_rev([v], v)
    assert eski["durum"] == S.REVIZE and yeni["durum"] == S.TASLAK
    assert yeni["rev"] == "1" and yeni["rev_sira"] == 1 and yeni["maddeler"] == v["maddeler"]
    y = S.yururluge_al(taslak(rev="03"))
    eski, yeni = S.yeni_rev([y], y)
    assert eski is None and yeni["rev"] == "04"
    with pytest.raises(S.SartnameHatasi, match="en son"):
        S.yeni_rev([v, dict(yeni, rev_sira=1)], v)
    with pytest.raises(S.SartnameHatasi, match="sayısal"):
        S.yeni_rev([taslak(rev="A")], taslak(rev="A"))
    _, yeni = S.yeni_rev([taslak(rev="A")], taslak(rev="A"), "B")
    assert yeni["rev"] == "B"


def test_kopyala():
    y = S.yururluge_al(taslak())
    k = S.kopyala([y], y, "KURUM_A Boru Şartnamesi")
    assert k["ad"] == "KURUM_A Boru Şartnamesi" and k["kurum"] == "KURUM_B"
    assert k["durum"] == S.TASLAK and k["rev"] == "0" and k["rev_sira"] == 0
    assert k["maddeler"] == y["maddeler"]
    with pytest.raises(S.SartnameHatasi, match="zaten var"):
        S.kopyala([y], y, "kurum_b genel şartname")
    with pytest.raises(S.SartnameHatasi, match="boş"):
        S.kopyala([y], y, " ")


def test_sil_kontrol_yetki():
    S.sil_kontrol(taslak(), K.DUZENLEYICI, "")
    with pytest.raises(S.SartnameHatasi, match="yetkiniz"):
        S.sil_kontrol(taslak(), K.OKUYUCU, "")
    y = S.yururluge_al(taslak())
    with pytest.raises(S.SartnameHatasi, match="yönetici"):
        S.sil_kontrol(y, K.DUZENLEYICI, "x")
    with pytest.raises(S.SartnameHatasi, match="gerekçe"):
        S.sil_kontrol(y, K.YONETICI, " ")
    S.sil_kontrol(y, K.YONETICI, "yanlış kayıt")


def test_kilitli_duzelt_kontrol():
    y = S.yururluge_al(taslak())
    duz = dict(y, maddeler=[dict(metin_maddesi(), metin={"tr": "Her 10 boru", "en": "Every 10"})])
    S.kilitli_duzelt_kontrol(y, duz, K.YONETICI, "yazım hatası")
    with pytest.raises(S.SartnameHatasi, match="yönetici"):
        S.kilitli_duzelt_kontrol(y, duz, K.DUZENLEYICI, "x")
    with pytest.raises(S.SartnameHatasi, match="gerekçe"):
        S.kilitli_duzelt_kontrol(y, duz, K.YONETICI, "")
    with pytest.raises(S.SartnameHatasi, match="'rev'"):
        S.kilitli_duzelt_kontrol(y, dict(duz, rev="1"), K.YONETICI, "x")
    with pytest.raises(S.SartnameHatasi, match="'durum'"):
        S.kilitli_duzelt_kontrol(y, dict(duz, durum=S.TASLAK), K.YONETICI, "x")
    with pytest.raises(S.SartnameHatasi, match="Taslak"):
        S.kilitli_duzelt_kontrol(taslak(), taslak(), K.YONETICI, "x")


def test_metinler():
    assert S.durum_metni(taslak()) == "Taslak"
    assert S.durum_metni(S.yururluge_al(taslak())) == "🔒 Yürürlükte"
    assert S.durum_metni(dict(taslak(), durum=S.REVIZE)) == "🔒 Revize edildi"
    assert S.tur_metni(taslak()) == "Genel"
    assert S.tur_metni(dict(taslak(), tur="ozel")) == "Özel teknik"
    assert S.kayit_adi(taslak()) == "KURUM_B / KURUM_B Genel Şartname Rev.0"


def test_listede_olmayan_aileden_yeni_rev_anlasilir_hata():
    """Doğrulama 3 bulgu 4: form kurum/adı listede yoksa ValueError değil SartnameHatasi."""
    kayitlar = [S.kayit_kur("KURUM_B", "KURUM_B Genel Şartname")]
    with pytest.raises(S.SartnameHatasi):
        S.yeni_rev(kayitlar, S.kayit_kur("KURUM_B", "Başka Ad"))


# ── Antigravity 5b-1 denetimi (2026-11-02) ──
def test_yeni_sartname_rev_sira_sifirla_baslar():
    """BULGU-03: rev_sira yalnız «Yeni rev»le büyür; ilk kayıt 0'dan başlar."""
    for sira in (99, -1):
        with pytest.raises(S.SartnameHatasi, match="rev_sira"):
            S.ekle_kontrol([], dict(taslak(), rev_sira=sira))
    S.ekle_kontrol([], taslak())


def _sayisal(**k):
    return dict({"id": "m1", "kontrol": "et_kalinligi", "grup": "", "kaynak": "", "tur": "sayisal",
                 "kriter": "et", "alt": None, "ust": 1.0, "birim": "mm"}, **k)


@pytest.mark.parametrize("madde", [
    _sayisal(ust=float("nan")),
    _sayisal(alt=float("-inf")),
    _sayisal(cap_aralik=[100, float("inf")]),
    _sayisal(cap_aralik=[-10, 0]),                 # BULGU-06: çap/et fiziksel olarak > 0
    _sayisal(et_aralik=[0, 12.7]),                 # kullanıcı kararı: alt sınır kesin pozitif
])
def test_sayisal_madde_sonlu_ve_pozitif_aralik(madde):
    """BULGU-06: nan/inf kural katmanında anlaşılır hatayla reddedilir (veritabanına kadar inmez)."""
    with pytest.raises(S.SartnameHatasi):
        S.madde_dogrula(madde, [])


def test_cok_buyuk_tam_sayi_cokertmez():
    """Doğrulama YENİ-1: math.isfinite(10**400) OverflowError atar; tam sayı her zaman sonludur."""
    S.madde_dogrula(_sayisal(ust=10**400), [])

def test_ek_satir_alan_adi_ingilizce():
    """Antigravity BULGU-02: ek satır hatasında alan adı ham anahtar kalmaz."""
    from app import dil
    satir = {a: {"tr": "x", "en": ""} for a in S.SATIR_ALANLARI}
    satir["karakteristik"] = {"tr": " ", "en": ""}
    m = {"id": "m1", "kontrol": "ut_kaynak", "grup": "", "kaynak": "8", "tur": "ek_satir",
         "satir": satir, "yeni_bolum": None}
    dil.ayarla("en")
    try:
        with pytest.raises(S.SartnameHatasi, match="characteristic"):
            S.madde_dogrula(m, [], tam=True)
    finally:
        dil.ayarla("tr")

