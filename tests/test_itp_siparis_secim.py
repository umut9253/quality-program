# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""app/itp/siparis_secim.py: sipariş ekranı şartname seçimi yardımcıları (Plan 5c-2, Qt'siz)."""
import pytest

from app.itp import sartname as S
from app.itp import siparis_secim as SS
from app.itp.uygula import UygulamaHatasi

GRUP = [{"id": "g1", "ad": {"tr": "İlk gün testleri", "en": "First day tests"}}]


def kayit(kurum, ad, rev="1", rev_sira=0, durum=S.YURURLUKTE, tur="genel", gruplar=(), no=""):
    return dict(S.kayit_kur(kurum, ad, tur), rev=rev, rev_sira=rev_sira, durum=durum, no=no,
                gruplar=list(gruplar))


KAYITLAR = {
    # kurgusal kurumlar (public kopya gerçek firma adlarını değiştirir; sıra testi bozulmasın)
    1: kayit("DOĞU", "Doğu Genel Şartname", gruplar=GRUP),
    2: kayit("BATI", "Batı Boru Şartnamesi", rev="6", no="B-100"),
    3: kayit("BATI", "Batı Boru Şartnamesi", rev="7", rev_sira=1, no="B-100"),
    4: kayit("KUZEY", "Kuzey İsteği", durum=S.TASLAK),
    5: kayit("ÇARŞI", "Çarşı Şartnamesi", rev="0", tur="ozel"),
}


def test_satirlar_yalniz_yururlukte_ve_sirali():
    satirlar = SS.secim_satirlari(KAYITLAR)
    assert [s["id"] for s in satirlar] == [2, 3, 5, 1]       # BATI, ÇARŞI, DOĞU (Türkçe sıra: ç, c ile d arası)
    assert satirlar[0]["yeni_rev"] == "Rev. 7" and satirlar[1]["yeni_rev"] == ""
    assert satirlar[3]["gruplar"] == [("g1", {"tr": "İlk gün testleri", "en": "First day tests"})]
    assert "B-100" in satirlar[1]["etiket"] and "Rev. 7" in satirlar[1]["etiket"]


def test_ayni_aileden_iki_revizyon_hata():
    with pytest.raises(UygulamaHatasi, match="iki revizyonu"):
        SS.secim_kontrol([{"id": 2, "gruplar": []}, {"id": 3, "gruplar": []}], KAYITLAR)
    SS.secim_kontrol([{"id": 3, "gruplar": []}, {"id": 1, "gruplar": ["g1"]}], KAYITLAR)


OZEL = [
    {"kontrol": "et_kalinligi", "sutun": "kabul", "metin": {"tr": "x", "en": ""},
     "kaynak": "siparis", "madde": None},
    {"kontrol": "et_kalinligi", "sutun": "kabul", "metin": {"tr": "", "en": "y"},
     "kaynak": "siparis", "madde": [1, "m1"]},
    {"kontrol": "hidrostatik", "sutun": "kabul", "metin": {"tr": "", "en": "z"},
     "kaynak": "siparis", "madde": [3, "m2"]},
]


def test_ozel_temizle_cikarilan_sartnamenin_cevirisi_gider():
    kalan = SS.ozel_temizle(OZEL, [{"id": 3, "gruplar": []}])
    assert kalan == [OZEL[0], OZEL[2]]
    assert SS.ozel_temizle(OZEL, [{"id": 3, "gruplar": []}], kararlar_da=True) == [OZEL[2]]


def test_ozet():
    assert SS.secim_ozeti([], KAYITLAR) == ""
    oz = SS.secim_ozeti([{"id": 3, "gruplar": []}, {"id": 1, "gruplar": ["g1"]},
                         {"id": 9, "gruplar": []}], KAYITLAR)
    assert "Batı Boru Şartnamesi Rev. 7" in oz
    assert "Doğu Genel Şartname Rev. 1 (+1 grup)" in oz
    assert "9" in oz and "bulunamadı" in oz


# ── önizleme yardımcıları (V-5c2-8) ──
from app.itp.dokuman import Denetim, Iz, Satir  # noqa: E402


def _satir(izler=(), uygulanmaz=""):
    return Satir("1", "", "", "", "Kar", "", "", Denetim("H"), (), kontrol="ebat",
                 uygulanmaz=uygulanmaz, izler=tuple(izler))


def test_isaret_onceligi():
    assert SS.isaret(_satir()) == ""
    assert SS.isaret(_satir([Iz("Ş.4", "5", "kabul", "ek")])) == "+"
    assert SS.isaret(_satir([Iz("Ş.4", "5", "kabul", "ek"), Iz("Ş.5", "6", "kabul", "yerine")])) == "⇄"
    assert SS.isaret(_satir([Iz("Ş.4", "5", "", "yeni_satir")])) == "★"
    assert SS.isaret(_satir([Iz("Ş.4", "5", "kabul", "ek")], uygulanmaz="g")) == "⊘"


def test_iz_metni():
    m = SS.iz_metni(Iz("Ş.4", "Md. 5.2", "kabul", "yerine", "eski metin"))
    assert m == "Ş.4 Md. 5.2 — kabul kriteri: yerine geçer · standart: eski metin"
    assert SS.iz_metni(Iz("", "", "frekans", "siparis")).startswith("Sipariş kararı — frekans")
    assert SS.iz_metni(Iz("Ş.4", "9", "", "uygulanmaz")) == "Ş.4 9 — uygulanmaz"
    assert SS.iz_metni(Iz("Ş.4", "9", "kabul", "yerine", "x" * 300)).endswith("…")


# ── Plan 5c-3: düzeltme hedefi ──
from app.itp.dokuman import Bolum, Dokuman, KalemTablosu, Metin  # noqa: E402


def _dok(satirlar):
    return Dokuman("KP", "tr", "kp_ciplak", None, (), (), (), (Bolum("1", "B", tuple(satirlar)),))


def _s(kar, kontrol="kimyasal", kabul=(), no=""):
    return Satir(no, "", "", "Kalite", kar, "Her döküm", "", Denetim("H"), tuple(kabul), kontrol=kontrol)


def test_satir_hedefi_kok_ve_sira():
    d = _dok([_s("Kimyasal (Kalem 1)", no="5"), _s("Kimyasal (Kalem 2)"), _s("Lot", "lot")])
    assert SS.satir_hedefi(d, 0, 0) == ("kimyasal", "Kimyasal (Kalem 1)", 0)
    assert SS.satir_hedefi(d, 0, 1) == ("kimyasal", "Kimyasal (Kalem 2)", 0)
    assert SS.satir_hedefi(d, 0, 2) == ("lot", "Lot", 0)


def test_hucre_metni_kabulde_atif_ayri():
    s = _s("Kimyasal", kabul=[Metin("C ≤ 0,18"), KalemTablosu(("a",), ()), Metin("Ş.1 Tablo 5")])
    assert SS.hucre_metni(s, "kabul") == "C ≤ 0,18\n[tablo]"
    assert SS.hucre_metni(s, "frekans") == "Her döküm"
    assert SS.hucre_metni(s, "denetim") == "H"


def test_duzeltme_yaz_bul_kaldir():
    h = ("kimyasal", "Kimyasal", 1)
    oz = SS.duzeltme_yaz([], h, "kabul", "tr", "Yeni")
    assert oz == [{"kontrol": "kimyasal", "sutun": "kabul", "metin": {"tr": "Yeni", "en": ""},
                   "kaynak": "siparis", "madde": None, "satir": "Kimyasal", "sira": 1}]
    assert SS.duzeltme_bul(oz, h, "kabul") is oz[0] and SS.duzeltme_bul(oz, h, "frekans") is None
    oz2 = SS.duzeltme_yaz(oz, h, "kabul", "tr", "Daha yeni")
    assert len(oz2) == 1 and oz2[0]["metin"]["tr"] == "Daha yeni"
    assert SS.duzeltme_yaz(oz2, h, "kabul", "tr", None) == []
