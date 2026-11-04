# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Şartnameler sekmesi: liste + düzenleyici (Plan 5b-2a, spec 2026-11-01 §4).
Geçici klasörde Database; gerçek data/ ve yedek/ klasörlerine dokunulmaz."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from app import database, kimlik as K  # noqa: E402
from app.itp import sartname as S  # noqa: E402
from app.sartname_sekme import SartnameSekme  # noqa: E402

SIFRE = "Guclu-Sifre-1"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(database, "DATA_FILE", str(tmp_path / "data" / "data.json"))
    monkeypatch.setattr(database, "BACKUP_DIR", str(tmp_path / "yedek"))
    d = database.Database()
    yield d
    d._c.close()


def oturum(db, rol):
    ad = f"k{rol}"
    K.kullanici_ekle(db._c, ad, SIFRE, rol, yapan=None)
    db.kullanici = K.giris(db._c, ad, SIFRE)


class Cevaplar:
    """Enjekte edilen diyalog cevapları (sırayla tüketilir)."""
    def __init__(self, *girdiler, uc="kaydet", soru=True):
        self.girdiler, self.uc, self.soru, self.mesajlar = list(girdiler), uc, soru, []
        self.acilan = []

    def girdi(self, baslik, etiket, varsayilan=""):
        return self.girdiler.pop(0) if self.girdiler else None

    def uc_secenek(self, baslik, metin):
        return self.uc

    def mesaj(self, tur, baslik, metin):
        self.mesajlar.append((tur, baslik, metin))
        return self.soru if tur == "soru" else None

    def klasor_ac(self, yol):
        self.acilan.append(yol)
        return True


def sekme(db, c=None):
    c = c or Cevaplar()
    return SartnameSekme(db, mesaj=c.mesaj, girdi=c.girdi, uc_secenek=c.uc_secenek,
                         klasor_ac=c.klasor_ac), c


def madde(id_="m1", kontrol="hidrostatik"):
    return {"id": id_, "kontrol": kontrol, "grup": "", "kaynak": "7.2.4", "tur": "metin",
            "sutun": "frekans", "metin": {"tr": "Her boru", "en": "Every pipe"}}


def ekle(db, kurum="KURUM_B", ad="KURUM_B Genel Şartname", maddeler=True, **alan):
    v = dict(S.kayit_kur(kurum, ad), **alan)
    v["maddeler"] = [madde()] if maddeler else []
    return db.add_sartname(v)


def satirlar(s):
    return [tuple(s.tablo.item(r, c).text() for c in range(s.tablo.columnCount()))
            for r in range(s.tablo.rowCount())]


def sec(s, kurum, ad=None):
    for r in range(s.tablo.rowCount()):
        if s.tablo.item(r, 0).text() == kurum and (ad is None or s.tablo.item(r, 1).text() == ad):
            s.tablo.selectRow(r)
            return s.secili_indeks()
    raise AssertionError(f"{kurum} / {ad} listede yok")


def test_liste_siralama_ve_sutunlar(app, db):
    ekle(db, "KURUM_C", "KURUM_C Genel")
    ekle(db, "KURUM_A", "KURUM_A Şartnamesi", tur="ozel", no="TS-1")
    ekle(db, "KURUM_B", "KURUM_B Genel Şartname")
    s, _ = sekme(db)
    assert satirlar(s) == [("KURUM_A", "KURUM_A Şartnamesi", "Özel teknik", "TS-1", "0", "Taslak"),
                           ("KURUM_B", "KURUM_B Genel Şartname", "Genel", "", "0", "Taslak"),
                           ("KURUM_C", "KURUM_C Genel", "Genel", "", "0", "Taslak")]


def test_revizyonlar_buyukten_kucuge(app, db):
    ekle(db)
    s, _ = sekme(db)
    s.yeni_rev(0)
    s.listeye_don()
    assert [r[4] for r in satirlar(s)] == ["1", "0"]
    assert [r[5] for r in satirlar(s)] == ["Taslak", "🔒 Revize edildi"]


def test_arama_turkce_harf_katlamali(app, db):
    ekle(db)
    ekle(db, "KURUM_C", "KURUM_C Genel")
    s, _ = sekme(db)
    s.arama.setText("kurum_b")
    assert [s.tablo.isRowHidden(r) for r in range(2)] == [False, True]
    s.arama.setText("")
    assert not any(s.tablo.isRowHidden(r) for r in range(2))


def test_dugme_durumlari_taslak_ve_kilitli(app, db):
    ekle(db)
    s, _ = sekme(db)
    assert not s.btn_ac.isEnabled() and not s.btn_yururluk.isEnabled()
    sec(s, "KURUM_B")
    assert s.btn_yururluk.isEnabled() and s.btn_yeni_rev.isEnabled()
    assert not s.btn_klasor.isEnabled()                         # kaynak klasör boş
    s.yururluge_al(0)
    sec(s, "KURUM_B")
    assert not s.btn_yururluk.isEnabled() and s.btn_yeni_rev.isEnabled()


def test_okuyucu_yazma_dugmelerini_gormez(app, db):
    ekle(db)
    oturum(db, K.OKUYUCU)
    s, _ = sekme(db)
    sec(s, "KURUM_B")
    for b in (s.btn_yeni, s.btn_kopyala, s.btn_yururluk, s.btn_yeni_rev, s.btn_sil):
        assert b.isHidden()
    assert not s.btn_ac.isHidden() and not s.btn_klasor.isHidden()
    s.ac(0)
    assert s.editor.salt_okunur and s.editor.btn_kaydet.isHidden()


def test_duzenleyici_kilitli_kaydin_silinmesini_gormez(app, db):
    ekle(db)
    s0, _ = sekme(db)
    s0.yururluge_al(0)
    oturum(db, K.DUZENLEYICI)
    s, _ = sekme(db)
    sec(s, "KURUM_B")
    assert s.btn_sil.isHidden()


def test_yeni_kaydet_listede_gorunur(app, db):
    s, _ = sekme(db)
    s.yeni()
    assert s.currentWidget() is s.editor
    s.editor.alanlar["kurum"].setText("KURUM_B")
    s.editor.alanlar["ad"].setText("KURUM_B Genel Şartname")
    assert s.editor.kaydet()
    assert len(db.get_sartname()) == 1 and db.get_sartname()[0]["kurum"] == "KURUM_B"
    s.editor.alanlar["no"].setText("No-5")                      # aynı kayda yazar
    assert s.editor.kaydet()
    assert len(db.get_sartname()) == 1 and db.get_sartname()[0]["no"] == "No-5"
    assert s.listeye_don() and satirlar(s)[0][:4] == ("KURUM_B", "KURUM_B Genel Şartname", "Genel", "No-5")


def test_bos_kurum_kaydedilmez(app, db):
    s, c = sekme(db)
    s.yeni()
    s.editor.alanlar["ad"].setText("Ad")
    assert not s.editor.kaydet() and db.get_sartname() == []
    assert c.mesajlar[-1][0] == "hata" and "Kurum" in c.mesajlar[-1][2]


def test_kopyala_yeni_ad_ister_ayni_ad_hata(app, db):
    ekle(db)
    s, c = sekme(db, Cevaplar("KURUM_B Kopya", "kurum_b genel şartname"))
    s.kopyala(0)
    assert sorted(r["ad"] for r in db.get_sartname()) == ["KURUM_B Genel Şartname", "KURUM_B Kopya"]
    kopya = [r for r in db.get_sartname() if r["ad"] == "KURUM_B Kopya"][0]
    assert kopya["maddeler"] == [madde()] and kopya["durum"] == S.TASLAK
    s.kopyala(0)
    assert len(db.get_sartname()) == 2 and c.mesajlar[-1][0] == "hata"
    assert "zaten var" in c.mesajlar[-1][2]


def test_yururluge_al_maddesizse_mesaj(app, db):
    ekle(db, maddeler=False)
    s, c = sekme(db)
    s.yururluge_al(0)
    assert db.get_sartname()[0]["durum"] == S.TASLAK
    assert c.mesajlar[-1][0] == "hata" and "madde" in c.mesajlar[-1][2]


def test_yururluge_al_soru_reddedilirse_dokunulmaz(app, db):
    ekle(db)
    s, c = sekme(db, Cevaplar(soru=False))
    s.yururluge_al(0)
    assert db.get_sartname()[0]["durum"] == S.TASLAK


def test_yururluge_al_kilitler_ve_salt_okunur_acilir(app, db):
    ekle(db)
    s, _ = sekme(db)
    s.yururluge_al(0)
    assert db.get_sartname()[0]["durum"] == S.YURURLUKTE
    s.ac(0)
    assert s.editor.salt_okunur and s.editor.btn_kaydet.isHidden()


def test_yeni_rev_kilitli_kaynaga_dokunmaz(app, db):
    ekle(db)
    s, _ = sekme(db)
    s.yururluge_al(0)
    s.yeni_rev(0)
    revler = sorted((r["rev"], r["durum"]) for r in db.get_sartname())
    assert revler == [("0", S.YURURLUKTE), ("1", S.TASLAK)]
    assert s.currentWidget() is s.editor and s.editor.alanlar["rev"].text() == "1"
    assert not s.editor.salt_okunur


def test_yeni_rev_taslak_kaynagi_revize_yapar(app, db):
    ekle(db)
    s, _ = sekme(db)
    s.yeni_rev(0)
    assert sorted((r["rev"], r["durum"]) for r in db.get_sartname()) == [
        ("0", S.REVIZE), ("1", S.TASLAK)]


def test_yeni_rev_sayisal_olmayan_rev_sorar(app, db):
    ekle(db, rev="A")
    s, _ = sekme(db, Cevaplar("B"))
    s.yeni_rev(0)
    assert sorted(r["rev"] for r in db.get_sartname()) == ["A", "B"]


def test_taslak_sil_soru_ile(app, db):
    ekle(db)
    s, c = sekme(db, Cevaplar(soru=False))
    s.sil(0)
    assert len(db.get_sartname()) == 1
    c.soru = True
    s.sil(0)
    assert db.get_sartname() == [] and s.tablo.rowCount() == 0


def test_kilitli_sil_gerekce_ister(app, db):
    ekle(db)
    s, c = sekme(db, Cevaplar(None, "yanlış kayıt"))
    s.yururluge_al(0)
    s.sil(0)                                                     # gerekçe penceresi kapatıldı
    assert len(db.get_sartname()) == 1
    s.sil(0)
    assert db.get_sartname() == []


def test_klasoru_ac(app, db, tmp_path):
    ekle(db)
    ekle(db, "KURUM_C", "KURUM_C Genel", kaynak_klasor=str(tmp_path / "yok"))
    ekle(db, "KURUM_A", "KURUM_A Şartnamesi", kaynak_klasor=str(tmp_path))
    s, c = sekme(db)
    s.klasoru_ac(sec(s, "KURUM_B"))
    assert c.mesajlar[-1][0] == "bilgi" and c.acilan == []
    s.klasoru_ac(sec(s, "KURUM_C"))
    assert c.mesajlar[-1][0] == "hata" and "bulunamadı" in c.mesajlar[-1][2] and c.acilan == []
    s.klasoru_ac(sec(s, "KURUM_A"))
    assert c.acilan == [str(tmp_path)]
    assert s.btn_klasor.isEnabled()


def tablet_siler(db, kurum):
    """Diyalog açıkken başka bağlantı (tablet) kaydı siler, 3 sn yenilemesi listeyi tazeler."""
    i = [r["kurum"] for r in db.get_sartname()].index(kurum)
    kid, surum = db.anahtar("sartname", i)
    database.kayit_sil(db._c, "sartname", kid, surum, "tablet", "tablet")
    db.yeniden_yukle()


def test_kopya_diyalogu_sirasinda_kayit_silinirse_mesaj(app, db):
    ekle(db)
    s, c = sekme(db)

    def girdi(*a):
        tablet_siler(db, "KURUM_B")
        return "Yeni Ad"
    s.girdi = girdi
    s.kopyala(0)
    assert db.get_sartname() == []
    assert c.mesajlar[-1][0] == "hata" and "silinmiş" in c.mesajlar[-1][2]


def test_diyalog_sirasinda_liste_kayarsa_dogru_kayit_silinir(app, db):
    for k in ("A", "B", "C"):
        ekle(db, k, f"{k} Şartnamesi")
    s, c = sekme(db)

    def mesaj(tur, baslik, metin):
        if tur == "soru":
            tablet_siler(db, "A")
            return True
    s._mesaj = mesaj
    s.sil(1)                                                     # B
    assert [r["kurum"] for r in db.get_sartname()] == ["C"]


def test_kaydedilmemis_degisiklikte_soru(app, db):
    ekle(db)
    c = Cevaplar(uc="vazgec")
    s, _ = sekme(db, c)
    s.ac(0)
    s.editor.alanlar["not"].setText("kaydedilmedi")
    assert not s.listeye_don() and s.currentWidget() is s.editor
    c.uc = "atla"
    assert s.listeye_don() and db.get_sartname()[0]["not"] == ""


def test_kapatilabilir_kaydet_secenegi_kaydeder(app, db):
    ekle(db)
    s, _ = sekme(db, Cevaplar(uc="kaydet"))
    s.ac(0)
    s.editor.alanlar["not"].setText("son hal")
    assert s.kapatilabilir() and db.get_sartname()[0]["not"] == "son hal"


def test_baska_yerde_degisen_kayit_cakisma_mesaji(app, db):
    ekle(db)
    s, c = sekme(db)
    s.ac(0)
    kid, surum = db.anahtar("sartname", 0)
    database.kayit_guncelle(db._c, "sartname", kid, dict(db.get_sartname()[0], no="T"), surum,
                            "tablet", "tablet")
    s.editor.alanlar["not"].setText("çakışan")
    assert not s.editor.kaydet()
    assert c.mesajlar[-1][0] == "hata" and "değiştirildi" in c.mesajlar[-1][2]


def test_gerekceyle_duzelt_yonetici(app, db):
    ekle(db)
    oturum(db, K.YONETICI)
    s, c = sekme(db, Cevaplar("yazım hatası"))
    s.yururluge_al(0)
    s.ac(0)
    assert s.editor.salt_okunur and not s.editor.btn_duzelt.isHidden()
    s.editor.duzelt_ac()
    assert not s.editor.salt_okunur and s.editor.alanlar["ad"].isReadOnly()
    s.editor.alanlar["not"].setText("düzeltildi")
    assert s.editor.kaydet()
    v = db.get_sartname()[0]
    assert v["not"] == "düzeltildi" and v["durum"] == S.YURURLUKTE
    assert s.editor.salt_okunur                                  # düzeltme sonrası yine kilitli


def test_tema_durumu_acik_kaydi_korur(app, db):
    ekle(db)
    s, _ = sekme(db)
    s.ac(0)
    s.editor.alanlar["not"].setText("yarım")
    s.arama.setText("ds")
    d = s.durum()
    yeni, _ = sekme(db)
    yeni.durumu_yukle(d)
    assert yeni.currentWidget() is yeni.editor and yeni.editor.alanlar["not"].text() == "yarım"
    assert yeni.editor.degisti and yeni.arama.text() == "ds"
    assert yeni.editor.kaydet() and len(db.get_sartname()) == 1


def test_acilamayan_kayit_acik_birakmaz(app, db, monkeypatch):
    """Doğrulama D-1 (ITP kalıbı)."""
    ekle(db)
    s, c = sekme(db)

    def bozuk(veri):
        raise KeyError("alt")
    monkeypatch.setattr(s.editor, "kaydi_yukle", bozuk)
    assert not s.ac(0)
    assert s.acik is None and s.currentWidget() is s.liste
    assert c.mesajlar[-1][:2] == ("hata", "Açılamadı")


def test_tema_sirasinda_kilitlenen_kayit_bildirilir(app, db):
    """Doğrulama D-4: kaydedilemeyecek girdiler salt okunur ekrana sessizce taşınmaz."""
    ekle(db)
    s, _ = sekme(db)
    s.ac(0)
    s.editor.alanlar["not"].setText("yarım")
    d = s.durum()
    s.yururluge_al(0)                                            # başka cihaz gibi
    yeni, c2 = sekme(db)
    yeni.durumu_yukle(d)
    assert yeni.editor.salt_okunur and not yeni.editor.degisti
    assert yeni.editor.alanlar["not"].text() == ""
    assert c2.mesajlar[-1][1] == "Kayıt kilitlendi"


def test_tema_degisikliksiz_duzeltme_kipini_korur(app, db):
    """Antigravity BULGU-03: düzeltme açık, henüz değişiklik yok."""
    ekle(db)
    oturum(db, K.YONETICI)
    s, _ = sekme(db)
    s.yururluge_al(0)
    s.ac(0)
    s.editor.duzelt_ac()
    d = s.durum()
    yeni, _ = sekme(db)
    yeni.durumu_yukle(d)
    assert not yeni.editor.salt_okunur and yeni.editor.btn_duzelt.isHidden()


def test_tema_sirasinda_silinen_kayit_bildirilir(app, db):
    ekle(db)
    s, _ = sekme(db)
    s.ac(0)
    s.editor.alanlar["not"].setText("yarım")
    d = s.durum()
    db.delete_sartname(0, anahtar=db.anahtar("sartname", 0))
    yeni, c2 = sekme(db)
    yeni.durumu_yukle(d)
    assert yeni.acik is None and any("silinmiş" in m[2] for m in c2.mesajlar)


# ── ana pencere ──────────────────────────────────────────────────────
from app.main_window import MainWindow  # noqa: E402


@pytest.fixture
def pencere(app, db):
    # tests/test_itp_sekme.py deseni: zamanlayıcılar durur; uygulama geneli olay süzgeci kaldırılır
    p = MainWindow(db)
    for z in (p.oto_kontrol_zamanlayici, p.daily_timer, p.dis_degisiklik_zamanlayici,
              p.bos_kilit_zamanlayici):
        z.stop()
    yield p
    p._zorla_kapat = True
    p.close()
    QApplication.instance().removeEventFilter(p)


def test_ana_pencerede_sartname_sekmesi_indeks_6(pencere):
    assert isinstance(pencere.sartname_page, SartnameSekme)
    assert pencere.stacked.widget(6) is pencere.sartname_page
    assert pencere.sidebar.sira.index(6) == pencere.sidebar.sira.index(5) + 1   # ITP'nin altında


def acik_taslak(pencere):
    s = pencere.sartname_page
    ekle(pencere.db)
    s.refresh()
    s.ac(0)
    s.editor.alanlar["not"].setText("yarım")
    return s


def test_tema_ve_dil_degisiminde_acik_sartname_korunur(pencere):
    from app import dil
    s = acik_taslak(pencere)
    pencere.toggle_theme()
    yeni = pencere.sartname_page
    assert yeni is not s and yeni.currentWidget() is yeni.editor
    assert yeni.editor.alanlar["not"].text() == "yarım" and yeni.editor.degisti
    try:
        pencere.toggle_dil()
        assert pencere.sartname_page.editor.alanlar["not"].text() == "yarım"
    finally:
        dil.ayarla("tr")


def test_kapanista_kaydedilmemis_sartname_sorulur(pencere):
    from PyQt6.QtGui import QCloseEvent
    s = acik_taslak(pencere)
    s.uc_secenek = lambda *a: "vazgec"
    olay = QCloseEvent()
    pencere.closeEvent(olay)
    assert not olay.isAccepted() and s.currentWidget() is s.editor


def test_kilit_iptalinde_sartname_sorulmaz_kaydedilmez(pencere):
    s = acik_taslak(pencere)
    sorulan = []
    s.uc_secenek = lambda *a: sorulan.append(a) or "kaydet"
    pencere._zorla_kapat = True
    pencere.close()
    assert sorulan == [] and pencere.db.get_sartname()[0]["not"] == ""


def test_dis_degisiklikte_liste_yenilenir_girdiler_korunur(pencere):
    s = acik_taslak(pencere)
    ekle(pencere.db, "KURUM_C", "KURUM_C Genel")
    pencere.db.disaridan_degisti = lambda: True   # başka bağlantı (tablet) yazmış gibi
    pencere.dis_degisiklik_kontrol()
    assert s.tablo.rowCount() == 2 and s.editor.alanlar["not"].text() == "yarım"
