# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""ITP sekmesi: kayıtlı sipariş listesi + düzenleyici (Plan 5a, K12/K13/K15).
Geçici klasörde Database; gerçek data/ ve yedek/ klasörlerine dokunulmaz."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from app import database, kimlik as K  # noqa: E402
from app import itp_page  # noqa: E402
from app.itp import kayit as R  # noqa: E402
from app.itp_sekme import ITPSekme  # noqa: E402

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
    d.firma_kaydet("ÖRNEK FİRMA", None, beklenen=d.firma())   # kurgusal firma (şema 6)
    yield d
    d._c.close()


def oturum(db, rol):
    ad = f"k{rol}"
    K.kullanici_ekle(db._c, ad, SIFRE, rol, yapan=None)
    db.kullanici = K.giris(db._c, ad, SIFRE)


class Cevaplar:
    """Enjekte edilen diyalog cevapları (sırayla tüketilir)."""
    def __init__(self, *girdiler, uc="kaydet"):
        self.girdiler, self.uc, self.mesajlar = list(girdiler), uc, []

    def girdi(self, baslik, etiket, varsayilan=""):
        return self.girdiler.pop(0) if self.girdiler else None

    def uc_secenek(self, baslik, metin):
        return self.uc

    def mesaj(self, tur, baslik, metin):
        self.mesajlar.append((tur, baslik, metin))
        return True


def sekme(db, c=None):
    c = c or Cevaplar()
    return ITPSekme(db, mesaj=c.mesaj, girdi=c.girdi, uc_secenek=c.uc_secenek), c


def ornek_kaydet(s, no="QP-1"):
    s.yeni()
    s.editor.ornek_yukle("kurum_a")
    s.editor.alanlar["dokuman_no"].setText(no)
    assert s.editor.kaydet()


def test_baslangicta_liste_ekrani(app, db):
    s, _ = sekme(db)
    assert s.currentWidget() is s.liste and s.tablo.rowCount() == 0


def test_yeni_kaydet_listede_gorunur_ve_kalici(app, db):
    s, _ = sekme(db)
    ornek_kaydet(s)
    assert len(db.get_itp()) == 1 and db.get_itp()[0]["no"] == "QP-1"
    assert s.listeye_don() and s.currentWidget() is s.liste
    assert s.tablo.item(0, 0).text() == "QP-1" and s.tablo.item(0, 6).text() == "Taslak"


def test_ayni_kaydi_tekrar_kaydetmek_gunceller(app, db):
    s, _ = sekme(db)
    ornek_kaydet(s)
    s.editor.alanlar["proje"].setText("Değişti")
    assert s.editor.kaydet()
    assert len(db.get_itp()) == 1 and db.get_itp()[0]["baslik"]["proje"] == "Değişti"


def test_bos_dokuman_no_kaydedilmez(app, db):
    s, c = sekme(db)
    s.yeni()
    s.editor.ornek_yukle("kurum_a")
    s.editor.alanlar["dokuman_no"].setText("")
    assert not s.editor.kaydet() and db.get_itp() == []
    assert c.mesajlar[-1][0] == "hata" and "Doküman No" in c.mesajlar[-1][2]


def test_arama_turkce_harf_katlamali(app, db):
    s, _ = sekme(db)
    ornek_kaydet(s, "KP-ÖRNEK-İ1")
    s.listeye_don()
    s.arama.setText("örnek-i1")
    assert not s.tablo.isRowHidden(0)
    s.arama.setText("yok-boyle")
    assert s.tablo.isRowHidden(0)


def test_onay_kilitler_ve_salt_okunur_acilir(app, db):
    s, _ = sekme(db, Cevaplar("05.11.2026", "yazı 1"))
    ornek_kaydet(s)
    s.listeye_don()
    s.onayla(0)
    assert db.get_itp()[0]["durum"] == R.ONAYLI
    assert s.tablo.item(0, 6).text() == "🔒 Onaylı (05.11.2026)"
    s.ac(0)
    assert s.editor.salt_okunur and s.editor.btn_kaydet.isHidden()


def test_yeni_rev_eskiyi_revize_yapar_yeni_taslak_acar(app, db):
    s, _ = sekme(db)
    ornek_kaydet(s)
    s.listeye_don()
    s.yeni_rev(0)
    revler = sorted((r["rev"], r["durum"]) for r in db.get_itp())
    assert revler == [("0", R.REVIZE), ("1", R.TASLAK)]
    assert s.currentWidget() is s.editor and s.editor.alanlar["rev"].text() == "1"


def test_kopyala_yeni_no_ister(app, db):
    s, _ = sekme(db, Cevaplar("QP-9"))
    ornek_kaydet(s)
    s.listeye_don()
    s.kopyala(0)
    assert sorted(r["no"] for r in db.get_itp()) == ["QP-1", "QP-9"]


def test_kaydedilmemis_degisiklikte_soru(app, db):
    c = Cevaplar(uc="vazgec")
    s, _ = sekme(db, c)
    ornek_kaydet(s)
    s.editor.alanlar["proje"].setText("kaydedilmedi")
    assert not s.listeye_don() and s.currentWidget() is s.editor
    c.uc = "atla"
    assert s.listeye_don() and db.get_itp()[0]["baslik"]["proje"] != "kaydedilmedi"


def test_kapatilabilir_kaydet_secenegi_kaydeder(app, db):
    s, _ = sekme(db, Cevaplar(uc="kaydet"))
    ornek_kaydet(s)
    s.editor.alanlar["proje"].setText("son hal")
    assert s.kapatilabilir() and db.get_itp()[0]["baslik"]["proje"] == "son hal"


def test_taslak_sil(app, db):
    s, _ = sekme(db)
    ornek_kaydet(s)
    s.listeye_don()
    s.sil(0)
    assert db.get_itp() == [] and s.tablo.rowCount() == 0


def test_okuyucu_yalniz_goruntuler(app, db):
    s0, _ = sekme(db)
    ornek_kaydet(s0)
    oturum(db, K.OKUYUCU)
    s, _ = sekme(db)
    s.tablo.selectRow(0)
    for b in (s.btn_yeni, s.btn_kopyala, s.btn_onay, s.btn_yeni_rev, s.btn_sil):
        assert b.isHidden()
    s.ac(0)
    assert s.editor.salt_okunur and s.editor.btn_excel.isHidden()
    assert s.editor.dokuman is not None


def test_aktarim_son_aktarimi_kaydeder(app, db, tmp_path, monkeypatch):
    monkeypatch.setattr(itp_page.QFileDialog, "getSaveFileName",
                        lambda *a, **k: (str(tmp_path / "x.xlsx"), ""))
    s, _ = sekme(db)
    ornek_kaydet(s)
    assert s.editor.excel_aktar()
    assert db.get_itp()[0]["son_aktarim"] is not None and db.get_itp()[0]["durum"] == R.TASLAK


def test_baska_yerde_degisen_kayit_cakisma_mesaji(app, db):
    s, c = sekme(db)
    ornek_kaydet(s)
    kid, surum = db.anahtar("itp", 0)
    database.kayit_guncelle(db._c, "itp", kid, dict(db.get_itp()[0], rev="0"), surum,
                            "tablet", "tablet")
    s.editor.alanlar["proje"].setText("çakışan")
    assert not s.editor.kaydet()
    assert c.mesajlar[-1][0] == "hata" and "değiştirildi" in c.mesajlar[-1][2]


def test_tema_durumu_acik_kaydi_korur(app, db):
    s, _ = sekme(db)
    ornek_kaydet(s)
    s.editor.alanlar["proje"].setText("yarım")
    d = s.durum()
    yeni, _ = sekme(db)
    yeni.durumu_yukle(d)
    assert yeni.currentWidget() is yeni.editor and yeni.editor.alanlar["proje"].text() == "yarım"
    assert yeni.editor.degisti
    yeni.editor.kaydet()
    assert len(db.get_itp()) == 1                    # aynı kayda yazıldı (yeni kayıt değil)


# ── ana pencere ──────────────────────────────────────────────────────
from app.main_window import MainWindow  # noqa: E402


@pytest.fixture
def pencere(app, db):
    # tests/test_giris_arayuz.py deseni: zamanlayıcılar durur; uygulama geneli olay süzgeci
    # test sonunda kaldırılır (kaldırılmazsa çöp toplamada süreç çöker)
    p = MainWindow(db)
    for z in (p.oto_kontrol_zamanlayici, p.daily_timer, p.dis_degisiklik_zamanlayici,
              p.bos_kilit_zamanlayici):
        z.stop()
    yield p
    p._zorla_kapat = True
    p.close()
    QApplication.instance().removeEventFilter(p)


def test_ana_pencerede_itp_sekmesi_indeks_5(pencere):
    assert isinstance(pencere.itp_page, ITPSekme)
    assert pencere.stacked.widget(5) is pencere.itp_page


def test_kilit_iptalinde_sorulmaz_kaydedilmez(pencere):
    s = pencere.itp_page
    sorulan = []
    s.uc_secenek = lambda *a: sorulan.append(a) or "kaydet"
    ornek_kaydet(s)
    s.editor.alanlar["proje"].setText("kilitte kaybolmalı")
    pencere._zorla_kapat = True
    pencere.close()
    assert sorulan == [] and pencere.db.get_itp()[0]["baslik"]["proje"] != "kilitte kaybolmalı"


def test_tema_degisiminde_acik_kayit_korunur(pencere):
    s = pencere.itp_page
    ornek_kaydet(s)
    s.editor.alanlar["proje"].setText("tema öncesi")
    pencere.toggle_theme()
    yeni = pencere.itp_page
    assert yeni is not s and yeni.currentWidget() is yeni.editor
    assert yeni.editor.alanlar["proje"].text() == "tema öncesi"


def test_kapanis_olayi_reddedilir(pencere):
    from PyQt6.QtGui import QCloseEvent
    s = pencere.itp_page
    s.uc_secenek = lambda *a: "vazgec"
    ornek_kaydet(s)
    s.editor.alanlar["proje"].setText("yarım")
    olay = QCloseEvent()
    pencere.closeEvent(olay)
    assert not olay.isAccepted()
    assert s.currentWidget() is s.editor and s.editor.degisti


# ── doğrulama ajanı bulguları (2026-11-01) ───────────────────────────
def uc_kayit(db):
    b, kalemler, _ = itp_page._ornek_siparis("kurum_a")
    import dataclasses
    for no in ("QP-A", "QP-B", "QP-C"):
        db.add_itp(R.kayit_kur("kp_ciplak", dataclasses.replace(b, dokuman_no=no), kalemler))


def tablet_siler(db, no):
    """Diyalog açıkken başka bağlantı (tablet) kaydı siler, 3 sn yenilemesi listeyi tazeler."""
    i = [r["no"] for r in db.get_itp()].index(no)
    kid, surum = db.anahtar("itp", i)
    database.kayit_sil(db._c, "itp", kid, surum, "tablet", "tablet")
    db.yeniden_yukle()


def test_onay_diyalogu_sirasinda_liste_kayarsa_dogru_kayit_onaylanir(app, db):
    uc_kayit(db)
    s, c = sekme(db)
    cevaplar = iter(["05.11.2026", ""])

    def girdi(*a):
        if db.get_itp()[0]["no"] == "QP-A":
            tablet_siler(db, "QP-A")
        return next(cevaplar)
    s.girdi = girdi
    s.onayla(1)                                              # QP-B
    durum = {r["no"]: r["durum"] for r in db.get_itp()}
    assert durum == {"QP-B": R.ONAYLI, "QP-C": R.TASLAK}


def test_silme_sorusu_sirasinda_liste_kayarsa_dogru_kayit_silinir(app, db):
    uc_kayit(db)
    s, c = sekme(db)

    def mesaj(tur, baslik, metin):
        if tur == "soru":
            tablet_siler(db, "QP-A")
            return True
    s._mesaj = mesaj
    s.sil(1)                                                 # QP-B
    assert [r["no"] for r in db.get_itp()] == ["QP-C"]


def test_kopya_diyalogu_sirasinda_liste_kayarsa_dogru_kaynak(app, db):
    uc_kayit(db)
    db.update_itp(1, dict(db.get_itp()[1], baslik=dict(db.get_itp()[1]["baslik"], proje="B-proje")),
                  anahtar=db.anahtar("itp", 1))
    s, c = sekme(db)

    def girdi(*a):
        tablet_siler(db, "QP-A")
        return "QP-Y"
    s.girdi = girdi
    s.kopyala(1)                                             # QP-B
    kopya = [r for r in db.get_itp() if r["no"] == "QP-Y"][0]
    assert kopya["baslik"]["proje"] == "B-proje"


def test_acilamayan_kayit_acik_birakmaz(app, db, monkeypatch):
    uc_kayit(db)
    s, c = sekme(db)

    def bozuk(veri):
        raise R.KayitHatasi("bozuk kayıt")
    monkeypatch.setattr(s.editor, "kaydi_yukle", bozuk)
    s.ac(0)
    assert s.acik is None and s.currentWidget() is s.liste


def test_tema_sirasinda_silinen_kayit_bildirilir(app, db):
    s, c = sekme(db)
    ornek_kaydet(s)
    s.editor.alanlar["proje"].setText("yarım")
    d = s.durum()
    db.delete_itp(0, anahtar=db.anahtar("itp", 0))
    yeni, c2 = sekme(db)
    yeni.durumu_yukle(d)
    assert yeni.acik is None and any("silinmiş" in m[2] for m in c2.mesajlar)


def test_revize_en_yuksekse_yeni_rev_dugmesi_acik(app, db):
    s, _ = sekme(db)
    ornek_kaydet(s)
    s.listeye_don()
    s.yeni_rev(0)
    s.listeye_don()
    rev1 = [i for i, r in enumerate(db.get_itp()) if r["rev"] == "1"][0]
    s.sil(rev1)
    s.tablo.selectRow(0)
    assert s.btn_yeni_rev.isEnabled()
