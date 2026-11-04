# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Şartname düzenleyici + madde / grup pencereleri (Plan 5b-2a Task 2-3). Veritabanı yok."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from app import dil, kimlik as K  # noqa: E402
from app.itp import sartname as S  # noqa: E402
from app.sartname_page import GrupDialog, MaddeDialog, SartnamePage  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def ingilizce():
    dil.ayarla("en")
    yield
    dil.ayarla("tr")


def sayisal(id_="m1", grup=""):
    return {"id": id_, "kontrol": "et_kalinligi", "grup": grup, "kaynak": "5.1", "tur": "sayisal",
            "kriter": "et", "alt": -0.5, "ust": 1.0, "birim": "mm", "cap_aralik": None,
            "et_aralik": [5.0, 12.0]}


def metin(id_="m2"):
    return {"id": id_, "kontrol": "hidrostatik", "grup": "g1", "kaynak": "7.2.4", "tur": "metin",
            "sutun": "frekans", "metin": {"tr": "Her boru", "en": "Every pipe"}}


def ek_satir(id_="m3"):
    satir = {a: {"tr": f"{a} tr", "en": f"{a} en"} for a in S.SATIR_ALANLARI}
    return {"id": id_, "kontrol": "ut_kaynak", "grup": "", "kaynak": "8", "tur": "ek_satir",
            "satir": satir, "yeni_bolum": {"tr": "Ek kontroller", "en": "Additional checks"}}


def uygulanmaz(id_="m4"):
    return {"id": id_, "kontrol": "rt_boru_ucu", "grup": "", "kaynak": "9", "tur": "uygulanmaz",
            "gerekce": {"tr": "Şartnamede yok", "en": ""}}


GRUPLAR = [{"id": "g1", "ad": {"tr": "İlk gün testleri", "en": "First day tests"}}]


def kayit(durum=S.TASLAK):
    v = dict(S.kayit_kur("KURUM_B", "KURUM_B Genel Şartname", "ozel"), no="N-1", yayim_tarihi="2024",
             kaynak_klasor="C:/x", **{"not": "not"})
    v.update(gruplar=GRUPLAR, maddeler=[sayisal(), metin(), ek_satir(), uygulanmaz()],
             durum=durum)
    return v


class Kayitci:
    def __init__(self, sonuc=True):
        self.sonuc, self.kayitlar, self.duzeltmeler, self.mesajlar = sonuc, [], [], []

    def kaydet(self, veri):
        self.kayitlar.append(veri)
        return self.sonuc

    def duzelt(self, veri, gerekce):
        self.duzeltmeler.append((veri, gerekce))
        return self.sonuc

    def mesaj(self, tur, baslik, metin):
        self.mesajlar.append((tur, baslik, metin))
        return True


def sayfa(rol=None, girdi=None):
    k = Kayitci()
    p = SartnamePage(mesaj=k.mesaj, rol=rol, on_kaydet=k.kaydet, on_listeye_don=lambda: True,
                     on_duzelt=k.duzelt, girdi=girdi or (lambda *a: "gerekçe"))
    return p, k


# ── düzenleyici ──────────────────────────────────────────────────────
def test_yukle_oku_gidis_donus(app):
    p, _ = sayfa()
    v = kayit()
    p.kaydi_yukle(v)
    assert p.veri_oku() == v and not p.degisti
    assert p.alanlar["kurum"].text() == "KURUM_B" and p.cmb_tur.currentData() == "ozel"
    assert p.tablo.rowCount() == 4


def test_yeni_bos_form(app):
    p, _ = sayfa()
    p.kaydi_yukle(None)
    v = p.veri_oku()
    assert v == S.kayit_kur("", "") and p.tablo.rowCount() == 0 and not p.degisti


def test_alan_degisince_degisti(app):
    p, k = sayfa()
    p.kaydi_yukle(kayit())
    p.alanlar["no"].setText("N-2")
    assert p.degisti
    assert p.kaydet() and k.kayitlar[-1]["no"] == "N-2" and not p.degisti
    p.cmb_tur.setCurrentIndex(p.cmb_tur.findData("genel"))
    assert p.degisti


def test_kaydet_basarisizsa_degisti_kalir(app):
    p, k = sayfa()
    k.sonuc = False
    p.kaydi_yukle(kayit())
    p.alanlar["no"].setText("N-2")
    assert not p.kaydet() and p.degisti


def test_madde_tablosu_turkce(app):
    p, _ = sayfa()
    p.kaydi_yukle(kayit())
    satir = [[p.tablo.item(r, c).text() for c in range(6)] for r in range(4)]
    assert satir[0] == ["Sayısal", "Et kalınlığı", "Et kalınlığı (t)", "-0.5 – 1 mm", "Zorunlu", "5.1"]
    assert satir[1] == ["Metin", "Hidrostatik test", "Frekans", "Her boru", "İlk gün testleri",
                        "7.2.4"]
    assert satir[2][:4] == ["Ek satır", "Ultrasonik kontrol, kaynak dikişi", "karakteristik tr",
                            "kabul tr"]
    assert satir[3][:4] == ["Uygulanmaz", "Radyografik kontrol, boru ucu kaynağı", "",
                            "Şartnamede yok"]


def test_madde_tablosu_deger_ipucu_tam_metin(app):
    """Kesilen değer hücresinin üstüne gelince tam metin; ek satırda dolu tüm alanlar."""
    p, _ = sayfa()
    p.kaydi_yukle(kayit())
    assert p.tablo.item(1, 3).toolTip() == "Her boru"
    ipucu = p.tablo.item(2, 3).toolTip()
    for a in ("Aktivite: aktivite tr", "Karakteristik: karakteristik tr",
              "Kabul kriteri: kabul tr", "Frekans: frekans tr", "Denetim: denetim tr"):
        assert a in ipucu


def test_madde_tablosu_ingilizce_bos_en_turkceye_duser(app, ingilizce):
    p, _ = sayfa()
    p.kaydi_yukle(kayit())
    assert [p.tablo.item(1, c).text() for c in range(5)] == [
        "Text", "Hydrostatic test", "Frequency", "Every pipe", "First day tests"]
    assert p.tablo.item(3, 3).text() == "Şartnamede yok"            # EN boş: TR gösterilir


def test_tek_sinirli_sayisal_gosterim(app):
    p, _ = sayfa()
    p.kaydi_yukle(dict(kayit(), maddeler=[dict(sayisal(), alt=None, ust=12.5, birim="bar")]))
    assert p.tablo.item(0, 3).text() == "≤ 12.5 bar"
    p.kaydi_yukle(dict(kayit(), maddeler=[dict(sayisal(), alt=3, ust=None, birim="")]))
    assert p.tablo.item(0, 3).text() == "≥ 3"


def test_madde_sirasi_yukari_asagi(app):
    p, _ = sayfa()
    p.kaydi_yukle(kayit())
    p.tablo.selectRow(0)
    p.tasi(1)
    assert [m["id"] for m in p.veri_oku()["maddeler"]] == ["m2", "m1", "m3", "m4"]
    assert p.degisti and p.tablo.currentRow() == 1
    p.tasi(-1)
    p.tasi(-1)                                                       # ilk satırdan yukarı: değişmez
    assert [m["id"] for m in p.veri_oku()["maddeler"]] == ["m1", "m2", "m3", "m4"]


def test_madde_ekle_duzenle_sil_enjekte_pencere(app):
    p, k = sayfa()
    p.kaydi_yukle(kayit())
    gelen = []

    def pencere(madde, gruplar, yeni_id):
        gelen.append((madde, yeni_id))
        return dict(metin(yeni_id or madde["id"]), grup="")
    p.madde_penceresi = pencere
    p.madde_ekle()
    assert gelen[-1] == (None, "m5") and p.tablo.rowCount() == 5 and p.degisti
    p.madde_duzenle(0)
    assert gelen[-1][0]["id"] == "m1" and p.veri_oku()["maddeler"][0]["tur"] == "metin"
    p.madde_sil(4)
    assert [m["id"] for m in p.veri_oku()["maddeler"]] == ["m1", "m2", "m3", "m4"]


def test_madde_penceresi_vazgecilirse_degismez(app):
    p, _ = sayfa()
    p.kaydi_yukle(kayit())
    p.madde_penceresi = lambda *a: None
    p.madde_ekle()
    assert p.tablo.rowCount() == 4 and not p.degisti


def test_gruplar_enjekte_pencere(app):
    p, _ = sayfa()
    p.kaydi_yukle(kayit())
    p.grup_penceresi = lambda g, m: g + [{"id": "g2", "ad": {"tr": "Ek", "en": "Extra"}}]
    p.gruplari_duzenle()
    assert [g["id"] for g in p.veri_oku()["gruplar"]] == ["g1", "g2"] and p.degisti


def test_kilitli_salt_okunur(app):
    p, _ = sayfa(rol=K.DUZENLEYICI)
    p.kaydi_yukle(kayit(S.YURURLUKTE))
    assert p.salt_okunur and p.btn_kaydet.isHidden() and p.btn_madde_ekle.isHidden()
    assert p.alanlar["no"].isReadOnly() and p.btn_duzelt.isHidden()  # düzeltme yalnız Yönetici
    assert not p.kaydet()


def test_okuyucu_salt_okunur(app):
    p, _ = sayfa(rol=K.OKUYUCU)
    p.kaydi_yukle(kayit())
    assert p.salt_okunur and p.btn_kaydet.isHidden() and p.btn_gruplar.isHidden()
    assert p.btn_duzelt.isHidden() and not p.cmb_tur.isEnabled()


def test_gerekceyle_duzelt_yalniz_yonetici_kilitlide(app):
    p, k = sayfa(rol=K.YONETICI, girdi=lambda *a: "yanlış değer")
    p.kaydi_yukle(kayit())
    assert p.btn_duzelt.isHidden()                                   # taslakta normal kaydet
    p.kaydi_yukle(kayit(S.YURURLUKTE))
    assert not p.btn_duzelt.isHidden()
    p.duzelt_ac()
    assert not p.salt_okunur and p.btn_duzelt.isHidden()
    for a in ("kurum", "ad", "rev"):                                 # kimlik alanları değişmez
        assert p.alanlar[a].isReadOnly()
    assert not p.cmb_tur.isEnabled() and not p.alanlar["no"].isReadOnly()
    p.alanlar["no"].setText("N-9")
    assert p.kaydet() and k.kayitlar == []
    veri, gerekce = k.duzeltmeler[-1]
    assert veri["no"] == "N-9" and veri["durum"] == S.YURURLUKTE and gerekce == "yanlış değer"


def test_duzeltme_gerekcesi_vazgecilirse_kaydedilmez(app):
    p, k = sayfa(rol=K.YONETICI, girdi=lambda *a: None)
    p.kaydi_yukle(kayit(S.YURURLUKTE))
    p.duzelt_ac()
    p.alanlar["no"].setText("N-9")
    assert not p.kaydet() and k.duzeltmeler == [] and p.degisti


def test_durum_tasima(app):
    p, _ = sayfa(rol=K.YONETICI)
    p.kaydi_yukle(kayit(S.YURURLUKTE))
    p.duzelt_ac()
    p.alanlar["not"].setText("yarım")
    p.madde_sil(3)
    d = p.durum()
    yeni, _ = sayfa(rol=K.YONETICI)
    yeni.kaydi_yukle(kayit(S.YURURLUKTE))
    yeni.durumu_yukle(d)
    assert yeni.alanlar["not"].text() == "yarım" and yeni.tablo.rowCount() == 3
    assert not yeni.salt_okunur                                       # düzeltme kipi taşındı


# ── madde penceresi ──────────────────────────────────────────────────
@pytest.mark.parametrize("m", [sayisal(), metin(), ek_satir(), uygulanmaz()],
                         ids=["sayisal", "metin", "ek_satir", "uygulanmaz"])
def test_madde_penceresi_duzenle_ayni_maddeyi_doner(app, m):
    d = MaddeDialog(m, GRUPLAR)
    assert d.madde() == m


def test_madde_penceresi_yeni_metin_maddesi(app):
    d = MaddeDialog(None, GRUPLAR, yeni_id="m7")
    d.cmb_tur.setCurrentIndex(d.cmb_tur.findData("metin"))
    d.cmb_kontrol.setCurrentIndex(d.cmb_kontrol.findData("markalama"))
    d.cmb_sutun.setCurrentIndex(d.cmb_sutun.findData("kabul"))
    d.ed_metin_tr.setText("Şablon ile boyama")
    d.ed_kaynak.setText("ÖTŞ 4")
    d.cmb_grup.setCurrentIndex(d.cmb_grup.findData("g1"))
    m = d.madde()
    assert m == {"id": "m7", "kontrol": "markalama", "grup": "g1", "kaynak": "ÖTŞ 4",
                 "tur": "metin", "sutun": "kabul", "metin": {"tr": "Şablon ile boyama", "en": ""}}
    S.madde_dogrula(m, ["g1"], tam=True)


def test_madde_penceresi_yeni_sayisal_virgullu(app):
    d = MaddeDialog(None, [], yeni_id="m1")
    d.cmb_tur.setCurrentIndex(d.cmb_tur.findData("sayisal"))
    d.cmb_kontrol.setCurrentIndex(d.cmb_kontrol.findData("dis_cap"))
    assert [d.cmb_kriter.itemData(i) for i in range(d.cmb_kriter.count())] == ["cap_govde", "cap_uc"]
    d.cmb_kriter.setCurrentIndex(1)
    d.ed_alt.setText("-1,6"); d.ed_ust.setText("2,4"); d.ed_birim.setText("mm")
    d.ed_cap_min.setText("508"); d.ed_cap_max.setText("1422")
    m = d.madde()
    assert (m["kriter"], m["alt"], m["ust"], m["cap_aralik"], m["et_aralik"]) == (
        "cap_uc", -1.6, 2.4, [508.0, 1422.0], None)


@pytest.mark.parametrize("hazirla, eslesme", [
    (lambda d: (d.ed_alt.setText("3"), d.ed_ust.setText("1")), "alt sınır"),
    (lambda d: (d.ed_alt.setText("abc"),), "sayı değil"),
    (lambda d: (d.ed_alt.setText(""), d.ed_ust.setText("")), "en az biri"),
    (lambda d: (d.ed_cap_min.setText("100"),), "birlikte"),
])
def test_madde_penceresi_gecersiz_sayisal(app, hazirla, eslesme):
    d = MaddeDialog(sayisal(), [])
    hazirla(d)
    with pytest.raises(S.SartnameHatasi, match=eslesme):
        d.madde()
    d._tamam()
    assert eslesme in d.lbl_hata.text() and d.sonuc is None and d.result() == 0


def test_madde_penceresi_sayilari_yuvarlamaz(app):
    """Doğrulama O-1: format 'g' 6 basamağa yuvarlıyordu."""
    m = dict(sayisal(), alt=-1.234567, ust=1234567.0, et_aralik=[5.123456789, 12.0])
    assert MaddeDialog(m, []).madde() == m
    p, _ = sayfa()
    p.kaydi_yukle(dict(kayit(), maddeler=[m]))
    assert p.tablo.item(0, 3).text() == "-1.234567 – 1234567 mm"


def test_listede_olmayan_kontrol_cokertmez(app):
    """Doğrulama D-2."""
    d = MaddeDialog(dict(metin(), kontrol="kaldirilmis", grup=""), [])
    assert "listede yok" in d.lbl_sablon.text()
    with pytest.raises(S.SartnameHatasi, match="kontrol"):
        d.madde()
    p, _ = sayfa()
    eksik = {k: v for k, v in sayisal().items() if k not in ("alt", "ust")}
    p.kaydi_yukle(dict(kayit(), maddeler=[eksik]))       # D-1: eksik alt/üst çökertmez
    assert p.tablo.item(0, 3).text() == "mm"


def test_secim_yokken_mesaj(app):
    """Doğrulama D-3: Yukarı / Aşağı ve Grubu sil sessiz kalmaz."""
    p, k = sayfa()
    p.kaydi_yukle(kayit())
    p.tablo.setCurrentCell(-1, -1)
    p.tasi(1)
    assert k.mesajlar[-1][0] == "bilgi" and not p.degisti
    d = GrupDialog(GRUPLAR, [])
    d.tablo.setCurrentCell(-1, -1)
    assert not d.sil() and "seçin" in d.lbl_hata.text()


def test_madde_penceresi_metin_tr_bos_hata(app):
    d = MaddeDialog(dict(metin(), grup=""), [])
    d.ed_metin_tr.setText(" ")
    d._tamam()
    assert "TR" in d.lbl_hata.text() and d.sonuc is None


def test_madde_penceresi_gecerli_tamam_kabul_eder(app):
    d = MaddeDialog(uygulanmaz(), [])
    d._tamam()
    assert d.sonuc == uygulanmaz() and d.result() == 1


def test_kriteri_olmayan_kontrolde_sayisal_girilemez(app):
    d = MaddeDialog(None, [], yeni_id="m1")
    d.cmb_tur.setCurrentIndex(d.cmb_tur.findData("sayisal"))
    d.cmb_kontrol.setCurrentIndex(d.cmb_kontrol.findData("markalama"))
    assert d.cmb_kriter.count() == 0 and not d.lbl_kriter_yok.isHidden()
    with pytest.raises(S.SartnameHatasi, match="sayısal kriteri"):
        d.madde()


def test_kontrol_degisince_sablon_bilgisi(app):
    d = MaddeDialog(None, [], yeni_id="m1")
    d.cmb_kontrol.setCurrentIndex(d.cmb_kontrol.findData("hidrostatik"))
    assert "ITP (EN)" in d.lbl_sablon.text() and "çıplak" in d.lbl_sablon.text()
    d.cmb_kontrol.setCurrentIndex(d.cmb_kontrol.findData("ic_kaplama_epoksi"))
    assert "henüz şablonu yok" in d.lbl_sablon.text()


def test_ek_satir_yeni_bolum_bossa_none(app):
    m = dict(ek_satir(), yeni_bolum=None)
    d = MaddeDialog(m, [])
    assert d.madde()["yeni_bolum"] is None


# ── grup penceresi ───────────────────────────────────────────────────
def test_grup_ekle_adlandir(app):
    d = GrupDialog(GRUPLAR, [metin()])
    d.ekle("Kaplama testleri", "Coating tests")
    assert d.gruplar() == GRUPLAR + [{"id": "g2", "ad": {"tr": "Kaplama testleri",
                                                          "en": "Coating tests"}}]
    d.tablo.item(0, 0).setText("İlk üretim testleri")
    assert d.gruplar()[0] == {"id": "g1", "ad": {"tr": "İlk üretim testleri",
                                                 "en": "First day tests"}}


def test_kullanilan_grup_silinmez(app):
    d = GrupDialog(GRUPLAR, [metin()])                               # metin() g1'de
    assert not d.sil(0) and "kullanılıyor" in d.lbl_hata.text()
    assert len(d.gruplar()) == 1
    d2 = GrupDialog(GRUPLAR, [sayisal()])
    assert d2.sil(0) and d2.gruplar() == []


def test_grup_tr_adi_bos_olamaz(app):
    d = GrupDialog([], [])
    d.ekle("", "x")
    with pytest.raises(S.SartnameHatasi, match="boş"):
        d.gruplar()
    d._tamam()
    assert "boş" in d.lbl_hata.text() and d.sonuc is None
