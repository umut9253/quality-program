# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Masaüstü giriş, rol bazlı arayüz, yönetim sayfaları (offscreen; geçici veri, Gemini kapalı)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from app import database, kimlik as K  # noqa: E402

SIFRE = "Guclu-Sifre-1"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def db(app, tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(database, "DATA_FILE", str(tmp_path / "data" / "data.json"))
    monkeypatch.setattr(database, "BACKUP_DIR", str(tmp_path / "yedek"))
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    from app import pages
    monkeypatch.setattr(pages.STDPage, "auto_check_standards", lambda self: None)
    d = database.Database()
    for ad, rol in (("admin", K.YONETICI), ("ali", K.DUZENLEYICI), ("ayse", K.OKUYUCU)):
        K.kullanici_ekle(d._c, ad, SIFRE, rol, yapan=None)
    return d


_PENCERELER = []


@pytest.fixture(autouse=True)
def _suzgecleri_kaldir():
    # close'u yamalanan testlerde pencere kapanmaz: uygulama geneli süzgeci test sonunda
    # kaldırılmazsa pencere çöp toplanırken süzgeç çağrılır ve süreç çöker
    yield
    while _PENCERELER:
        QApplication.instance().removeEventFilter(_PENCERELER.pop())


def pencere(db, ad):
    from app.main_window import MainWindow
    db.kullanici = K.giris(db._c, ad, SIFRE)
    w = MainWindow(db=db)
    _PENCERELER.append(w)
    w.oto_kontrol_zamanlayici.stop(); w.daily_timer.stop(); w.dis_degisiklik_zamanlayici.stop()
    return w


def test_giris_penceresi_hatali_sonra_dogru(db):
    from app.giris_penceresi import GirisDialog
    g = GirisDialog(db._c)
    g.ad.setText("ali"); g.sifre.setText("yanlis")
    g.dene()
    assert g.kullanici is None and "hatalı" in g.mesaj.text()
    g.sifre.setText(SIFRE)
    g.dene()
    assert g.kullanici.ad == "ali"


def test_kurulum_penceresi_yonetici_olusturur(app, tmp_path):
    import sqlite3
    from app.giris_penceresi import KurulumDialog
    c = sqlite3.connect(":memory:"); K.sema_kur(c)
    d = KurulumDialog(c)
    d.ad.setText("patron"); d.ad_soyad.setText("Umut")
    d.sifre.setText(SIFRE); d.sifre2.setText("farkli-sifre")
    d.kaydet()
    assert K.kurulum_gerekli(c) and "eşleşmiyor" in d.mesaj.text()
    d.sifre2.setText(SIFRE)
    d.kaydet()
    assert K.giris(c, "patron", SIFRE).rol == K.YONETICI


def test_okuyucu_duzenleme_dugmelerini_gormez(db):
    w = pencere(db, "ayse")
    for sayfa in (w.wps_page, w.pqr_page, w.std_page, w.cert_page):
        son = sayfa.table.columnCount() - 1
        assert sayfa.table.isColumnHidden(son), type(sayfa).__name__
        assert not sayfa.btn_yeni.isVisibleTo(sayfa)
    assert not w.std_page.btn_check.isVisibleTo(w.std_page)
    assert w.sidebar.btn_group.button(7) is None              # yönetim sayfaları yok
    assert w.sidebar.btn_group.button(6)                      # Şartnameler herkeste
    w.close()


def test_duzenleyici_duzenler_yonetimi_gormez(db):
    w = pencere(db, "ali")
    assert not w.wps_page.table.isColumnHidden(w.wps_page.table.columnCount() - 1)
    assert w.wps_page.btn_yeni.isVisibleTo(w.wps_page)
    assert w.sidebar.btn_group.button(7) is None and w.stacked.count() == 7
    w.close()


def test_yonetici_yonetim_sayfalarini_gorur(db):
    w = pencere(db, "admin")
    assert w.sidebar.btn_group.button(7) and w.sidebar.btn_group.button(8)
    w.stacked.setCurrentIndex(7)
    assert w.stacked.currentWidget() is w.kullanicilar_page
    assert {s["ad"] for s in w.kullanicilar_page.veriler()} == {"admin", "ali", "ayse"}
    db.add_cert({"no": "YENI-1", "bitis": "2030-01-01"})
    w.degisiklik_page.refresh()
    assert w.degisiklik_page.table.rowCount() >= 1
    assert "admin" in w.title_bar.kullanici_etiketi.text()
    w.close()


def test_tabletten_degisiklik_masaustune_yansir(db):
    w = pencere(db, "ali")
    once = w.cert_page.table.rowCount()
    diger = database._baglan(database.db_yolu())
    database.kayit_ekle(diger, "cert", {"no": "TABLET-1", "bitis": "2030-01-01"}, "veli", "tablet")
    w.dis_degisiklik_kontrol()                                # zamanlayıcı tıkı
    assert w.cert_page.table.rowCount() == once + 1
    w.close()


def test_kilit_penceresi_yalniz_oturum_sahibinin_sifresiyle_acilir(db):
    from app.giris_penceresi import KilitDialog
    k = K.giris(db._c, "ali", SIFRE)
    d = KilitDialog(db._c, k)
    d.sifre.setText("yanlis"); d.dene()
    assert d.result() == 0 and "hatalı" in d.mesaj.text()
    d.sifre.setText(SIFRE); d.dene()
    assert d.result() == 1


def test_bos_kalinca_kilitlenir_ve_icerik_gizlenir(db, monkeypatch):
    from PyQt6.QtWidgets import QDialog
    from app import main_window
    w = pencere(db, "ali")
    assert w.bos_kilit_zamanlayici.interval() == K.BOS_KILIT_SN * 1000
    assert w.bos_kilit_zamanlayici.isActive()
    gorunur = []

    class Sahte:
        def __init__(self, c, k, parent=None): self.sonuc = k
        def exec(self):
            gorunur.append(w.centralWidget().isVisibleTo(w))
            return QDialog.DialogCode.Accepted
    monkeypatch.setattr(main_window, "KilitDialog", Sahte)
    w.kilitle()
    assert gorunur == [False]                                 # kilitliyken veri görünmez
    assert w.centralWidget().isVisibleTo(w) and w.bos_kilit_zamanlayici.isActive()


def test_kilit_ekraninda_vazgecince_program_kapanir(db, monkeypatch):
    from PyQt6.QtWidgets import QDialog
    from app import main_window
    w = pencere(db, "ali")
    kapandi = []
    monkeypatch.setattr(w, "close", lambda: kapandi.append(1))

    class Sahte:
        def __init__(self, c, k, parent=None): pass
        def exec(self): return QDialog.DialogCode.Rejected
    monkeypatch.setattr(main_window, "KilitDialog", Sahte)
    w.kilitle()
    assert kapandi == [1]


def _acik_diyalog(w):
    from PyQt6.QtWidgets import QDialog
    d = QDialog(w); d.setWindowTitle("düzenleme"); d.show()
    return d


def test_kilitte_acik_diyalog_gorunmez_ve_girdi_korunur(db, monkeypatch):
    """Denetim: zaman aşımında açık düzenleme penceresi kilidin üstünde okunabiliyordu.
    hide() exec döngüsünü bitirip girdiyi kaybettireceğinden opaklık 0 yapılır."""
    from PyQt6.QtWidgets import QDialog
    from app import main_window
    w = pencere(db, "ali")
    d = _acik_diyalog(w)
    kilitte = []

    class Sahte:
        def __init__(self, c, k, parent=None): self.sonuc = k
        def exec(self):
            kilitte.append((d.windowOpacity(), d.isVisible()))
            return QDialog.DialogCode.Accepted
    monkeypatch.setattr(main_window, "KilitDialog", Sahte)
    w.kilitle()
    assert kilitte == [(0.0, True)]                           # görünmez ama açık (girdi durur)
    assert d.windowOpacity() == 1.0 and d.isVisible()


def test_kilitte_kapatinca_acik_diyalog_iptal_edilir(db, monkeypatch):
    from PyQt6.QtWidgets import QDialog
    from app import main_window
    w = pencere(db, "ali")
    d = _acik_diyalog(w)
    monkeypatch.setattr(w, "close", lambda: None)

    class Sahte:
        def __init__(self, c, k, parent=None): pass
        def exec(self): return QDialog.DialogCode.Rejected
    monkeypatch.setattr(main_window, "KilitDialog", Sahte)
    w.kilitle()
    assert not d.isVisible() and d.result() == QDialog.DialogCode.Rejected   # kayıt yapılamaz


def test_kilit_sirasinda_rol_degistiyse_program_kapanir(db, monkeypatch):
    from PyQt6.QtWidgets import QDialog, QMessageBox
    from app import main_window
    w = pencere(db, "ali")
    kapandi = []
    monkeypatch.setattr(w, "close", lambda: kapandi.append(1))
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    yeni = K.Kullanici(w.db.kullanici.id, "ali", "", K.OKUYUCU)

    class Sahte:
        def __init__(self, c, k, parent=None): self.sonuc = yeni
        def exec(self): return QDialog.DialogCode.Accepted
    monkeypatch.setattr(main_window, "KilitDialog", Sahte)
    w.kilitle()
    assert kapandi == [1]


# ── Antigravity 2026-10-30 BULGU-01: pencere açıkken 3 sn yenilemesi ────────────────────
def tablet():
    return database._baglan(database.db_yolu())


def test_duzenleme_acikken_tablet_degisikligi_ezilmez(db, monkeypatch):
    from PyQt6.QtWidgets import QDialog
    from app import pages
    w = pencere(db, "ali")
    kid, surum = db._ids["cert"][0], db._surum["cert"][0]

    def exec_(self):                    # kullanıcı formu doldururken tablet kaydı değiştirir
        once = dict(db.get_cert()[0])
        database.kayit_guncelle(tablet(), "cert", kid, dict(once, ad="TABLETTEN"), surum,
                                "veli", "tablet")
        w.dis_degisiklik_kontrol()      # 3 sn tıkı pencere açıkken
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(pages.CertDialog, "exec", exec_)
    with pytest.raises(database.CakismaHatasi):
        w.cert_page.edit(0)
    assert database.tum_veri(database.db_yolu())["cert"][0]["ad"] == "TABLETTEN"
    w.close()


def test_silme_onayi_acikken_ustteki_kayit_silinirse_dogru_kayit_silinir(db, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    for no in ("S-2", "S-3"):
        db.add_std({"no": no, "org": "ISO"})
    w = pencere(db, "ali")
    nolar = [s["no"] for s in db.get_std()]

    def soru(*a, **k):                  # onay kutusu açıkken tablet ilk kaydı siler
        database.kayit_sil(tablet(), "std", db._ids["std"][0], db._surum["std"][0], "veli",
                           "tablet")
        w.dis_degisiklik_kontrol()
        return QMessageBox.StandardButton.Yes
    monkeypatch.setattr(QMessageBox, "question", soru)
    w.std_page.delete(1)                # kullanıcı nolar[1]'i silmek istedi
    assert [s["no"] for s in database.tum_veri(database.db_yolu())["std"]] == nolar[2:]
    w.close()


class SahteIsci:
    def __init__(self, kayitlar):
        self.progress = self.finished = self
    def connect(self, fn):
        pass
    def start(self):
        pass
    def isRunning(self):
        return False


def test_standart_kontrolu_sonucu_kayit_kayinca_dogru_standarda_yazilir(db, monkeypatch):
    from app import pages
    db.add_std({"no": "S-2", "org": "ISO", "myVer": "2020"})
    w = pencere(db, "ali")
    hedef = db.get_std()[1]["no"]
    monkeypatch.setattr(pages, "has_api_key", lambda: True)
    monkeypatch.setattr(pages, "CheckWorker", SahteIsci)   # ağ/iş parçacığı yok
    w.std_page._run_check(list(enumerate(db.get_std())))
    database.kayit_sil(tablet(), "std", db._ids["std"][0], db._surum["std"][0], "veli", "tablet")
    w.dis_degisiklik_kontrol()          # kontrol sürerken liste yenilendi
    w.std_page._on_progress(1, "2099", "", "guncel")       # işçi eski indeksle bildirir
    std = database.tum_veri(database.db_yolu())["std"]
    assert [(s["no"], s.get("lastVer")) for s in std] == [(hedef, "2099")]
    w.close()


def test_degisiklik_sayfasi_her_bolumu_adlandirir():
    """Antigravity 5b-1 BULGU-04: ITP ve Şartname de filtrede seçilebilir, adıyla görünür."""
    from app.yonetim_sayfalari import BOLUM_ADI
    assert set(BOLUM_ADI) == set(database.SECTIONS) | {"ayarlar"}   # ayarlar: firma (şema 6)


# ── Firma Bilgileri (stacked 9, spec 2026-11-02 F1) ─────────────────────
def _png(tmp_path, ad="logo.png"):
    from PyQt6.QtGui import QImage
    img = QImage(120, 30, QImage.Format.Format_RGB32)
    img.fill(0x1B2A4A)
    yol = tmp_path / ad
    assert img.save(str(yol), "PNG")
    return yol


def test_firma_sayfasi_yalniz_yoneticide(db):
    w = pencere(db, "admin")
    assert w.sidebar.btn_group.button(9) and w.stacked.count() == 10
    assert len(w.kisayollar) == 9                       # "Ctrl+10" geçersiz: kısayol yok
    assert "Ctrl" not in w.sidebar.btn_group.button(9).toolTip()
    w.stacked.setCurrentIndex(9)
    assert w.stacked.currentWidget() is w.firma_page
    w.close()
    w = pencere(db, "ali")
    assert w.sidebar.btn_group.button(9) is None and w.stacked.count() == 7
    w.close()


def test_firma_sayfasi_kaydeder(db, tmp_path):
    from app.firma import Firma
    from app.yonetim_sayfalari import FirmaPage
    db.kullanici = K.giris(db._c, "admin", SIFRE)
    mesajlar = []
    yol = _png(tmp_path)
    s = FirmaPage(db, mesaj=lambda b, m: mesajlar.append(m), dosya_sec=lambda: str(yol))
    assert "oluşturulamaz" in s.durum.text()
    s.ad.setText("ÖRNEK FİRMA")
    s.logo_sec()
    assert s.kaydet() and mesajlar == []
    assert db.firma() == Firma("ÖRNEK FİRMA", yol.read_bytes())
    assert not s.onizleme.pixmap().isNull() and s.durum.text() == ""
    s.logo_kaldir()
    assert s.kaydet() and db.firma().logo is None


def test_firma_sayfasi_gecersiz_logo_ve_cakisma(db, tmp_path):
    from app.yonetim_sayfalari import FirmaPage
    db.kullanici = K.giris(db._c, "admin", SIFRE)
    mesajlar = []
    gif = tmp_path / "x.gif"
    gif.write_bytes(b"GIF89a" + b"\x00" * 10)
    s = FirmaPage(db, mesaj=lambda b, m: mesajlar.append(m), dosya_sec=lambda: str(gif))
    s.logo_sec()
    assert "PNG ya da JPEG" in mesajlar[-1] and s.logo is None
    bozuk = tmp_path / "bozuk.png"                                # imza doğru, gövde bozuk
    bozuk.write_bytes(b"\x89PNG\r\n\x1a\n" + b"bozuk-govde")
    s._dosya_sec = lambda: str(bozuk)
    s.logo_sec()
    assert "okunamadı" in mesajlar[-1] and s.logo is None
    db.firma_kaydet("BAŞKA OTURUM", None, beklenen=db.firma())   # sayfa açıkken değişti
    s.ad.setText("BENİM")
    assert not s.kaydet()
    assert "başka bir oturumda" in mesajlar[-1] and s.ad.text() == "BAŞKA OTURUM"


# ── Arayüz dili (spec 2026-11-02 D2) ─────────────────────────────────────
def test_dil_dugmesi_kaydeder_ve_pencereyi_yeniden_kurar(db):
    from app import dil
    w = pencere(db, "ali")
    try:
        assert dil.etkin() == "tr" and w.title_bar.btn_dil.text() == "EN"
        w.itp_page.yeni()
        w.itp_page.editor.alanlar["proje"].setText("Korunur")
        w.title_bar.btn_dil.click()
        assert dil.etkin() == "en" and K.dil_oku(db._c, db.kullanici.id) == "en"
        assert w.title_bar.btn_dil.text() == "TR"                 # pencere yeniden kuruldu
        assert w.itp_page.editor.alanlar["proje"].text() == "Korunur"
        assert QSettings("KaliteYS", "WPS_PQR").value("dil_son") == "en"
        w._zorla_kapat = True          # kaydedilmemiş ITP girdisi: soru penceresi açılmasın
        w.close()
        w = pencere(db, "ali")                                     # kullanıcının dili kalıcı
        assert dil.etkin() == "en" and w.title_bar.btn_dil.text() == "TR"
        w.close()
        w = pencere(db, "ayse")                                    # başka kullanıcı: kendi dili
        assert dil.etkin() == "tr"
        w.close()
    finally:
        dil.ayarla("tr")

