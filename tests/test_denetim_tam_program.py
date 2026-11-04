# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Antigravity tam program denetimi (2026-11-02) bulguları: her test önce kırmızıydı.
Offscreen; veri ve QSettings geçici klasörde, Gemini'ye istek gitmez."""
import dataclasses
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sqlite3  # noqa: E402
from datetime import date  # noqa: E402

import openpyxl  # noqa: E402
import pytest  # noqa: E402
from PyQt6.QtCore import QRectF, QSettings, QThread  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from app import database  # noqa: E402
from app import kimlik as KM  # noqa: E402
from app.firma import Firma  # noqa: E402
from app.itp import kayit as R  # noqa: E402

FIRMA = "ÖRNEK FİRMA"   # kurgusal firma adı (2026-11-02)
SIFRE = "Guclu-Sifre-1"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def klasor(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(database, "DATA_FILE", str(tmp_path / "data" / "data.json"))
    monkeypatch.setattr(database, "BACKUP_DIR", str(tmp_path / "yedek"))
    return tmp_path


def oturumlu():
    db = database.Database()
    KM.kullanici_ekle(db._c, "ali", SIFRE, KM.DUZENLEYICI, yapan=None)
    db.kullanici = KM.giris(db._c, "ali", SIFRE)
    return db


@pytest.fixture
def pencere(app, klasor, monkeypatch):
    """tests/test_arayuz_hizi.py deseni: QSettings geçici, otomatik kontrol kapalı."""
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(klasor))
    from app import pages
    monkeypatch.setattr(pages.STDPage, "auto_check_standards", lambda self: None)
    from app.main_window import MainWindow
    w = MainWindow()
    w.daily_timer.stop()
    w.oto_kontrol_zamanlayici.stop()
    yield w
    w._zorla_kapat = True
    w.close()
    QApplication.instance().removeEventFilter(w)


# ── BULGU-03: Excel'e yazılan kullanıcı metni formül olarak çalışmaz ────────────
def test_liste_aktariminda_formul_calismaz(app, tmp_path, monkeypatch):
    from app import exporter
    yol = str(tmp_path / "l.xlsx")
    monkeypatch.setattr(exporter.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (yol, "")))
    exporter.export_xlsx(None, "l.xlsx", "WPS", ["No", "Not"],
                         [["W1", '=HYPERLINK("http://x","tikla")'], ["W2", "-5 mm"]])
    ws = openpyxl.load_workbook(yol).active
    assert ws["B2"].data_type == "s" and ws["B2"].value.startswith("=HYPERLINK")
    assert ws["B3"].value == "-5 mm"


def test_itp_excelinde_baslik_metni_formul_olmaz(tmp_path):
    from app.itp.excel import excel_yaz
    from app.itp.olustur import olustur
    from tests.test_itp_excel import BASLIK, KURUM_C
    b = dataclasses.replace(BASLIK, proje="=1+1")
    wb = openpyxl.load_workbook(excel_yaz(olustur("itp_en", b, KURUM_C, firma=FIRMA), tmp_path / "i.xlsx", Firma(FIRMA)))
    hucreler = [h for ws in wb for satir in ws.iter_rows() for h in satir if h.value == "=1+1"]
    assert hucreler and all(h.data_type == "s" for h in hucreler)


# ── BULGU-17: lejant tablosu başlık genişliğinde (kullanıcı kararı) ─────────────
def test_lejant_tablosu_tam_genislik(tmp_path):
    from app.itp.excel import excel_yaz
    from app.itp.olustur import olustur
    from tests.test_itp_excel import BASLIK, KURUM_C
    ws = openpyxl.load_workbook(excel_yaz(olustur("itp_en", BASLIK, KURUM_C, firma=FIRMA),
                                          tmp_path / "i.xlsx", Firma(FIRMA)))["General Information"]
    r = next(h.row for h in ws["A"] if h.value == "LEGEND") + 1
    birlesik = {str(m) for m in ws.merged_cells.ranges}
    for satir in range(r, r + 5):                        # başlık + 4 satır
        assert {f"B{satir}:C{satir}", f"E{satir}:G{satir}"} <= birlesik


# ── BULGU-04: standart kontrolü sürerken tema / kapanış çökmesin ────────────────
class _Bekleyen(QThread):
    def run(self):
        while not self.isInterruptionRequested():
            self.msleep(10)


def test_kontrol_surerken_tema_degismez(pencere, monkeypatch):
    mesaj = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a: mesaj.append(a[1])))
    isci = _Bekleyen()
    sayfa = pencere.std_page
    sayfa._worker = isci
    isci.start()
    try:
        pencere.toggle_theme()
        assert pencere.std_page is sayfa and mesaj      # sayfa (ve işçisi) silinmedi, söylendi
    finally:
        isci.requestInterruption()
        isci.wait()


def test_kapanista_kontrol_iscisi_durur(pencere):
    isci = _Bekleyen()
    pencere.std_page._worker = isci
    isci.start()
    try:
        pencere.close()
        assert isci.isFinished()
    finally:
        isci.requestInterruption()
        isci.wait()


def test_isci_beklemede_kesilebilir(app, monkeypatch):
    from app import standards_check as S
    monkeypatch.setattr(S, "fetch_latest_versions_bulk", lambda parca: S.API_ERROR)
    w = S.CheckWorker([(i, {"no": f"S{i}", "org": "ASME"}) for i in range(40)])
    w.chunk_pause = 5
    w.start()
    QThread.msleep(200)
    w.requestInterruption()
    try:
        assert w.wait(2000)
    finally:
        w.wait()


# ── BULGU-12: otomatik kontrolde pencere yalnız bulgu varsa (kullanıcı kararı) ──
def test_otomatik_kontrol_yalniz_bulgu_varsa_pencere_acar(pencere, monkeypatch):
    from app import pages
    acilan = []
    monkeypatch.setattr(pages.QMessageBox, "information",
                        staticmethod(lambda *a: acilan.append(a[2])))
    monkeypatch.setattr(pages, "has_api_key", lambda: True)

    class Sinyal:
        def connect(self, *_):
            pass

    class SahteIsci:
        def __init__(self, kayitlar):
            self.progress = self.finished = Sinyal()

        def start(self):
            pass

        def isRunning(self):
            return False

    monkeypatch.setattr(pages, "CheckWorker", SahteIsci)
    sayfa = pencere.std_page
    kayitlar = list(enumerate(pencere.db.get_std()))
    sayfa._run_check(kayitlar, silent=True)
    sayfa._on_finished(len(kayitlar), 0, 0)
    assert acilan == []                                  # her şey güncel: sessiz
    sayfa._run_check(kayitlar, silent=True)
    sayfa._on_finished(len(kayitlar), 1, 0)              # güncelleme var
    sayfa._run_check(kayitlar, silent=True)
    sayfa._on_finished(len(kayitlar), 0, 2)              # manuel bekleyen var
    sayfa._run_check(kayitlar)
    sayfa._on_finished(len(kayitlar), 0, 0)              # elle başlatılan: her zaman
    assert len(acilan) == 3


# ── BULGU-05: WPS/PQR uyum kontrolünde Türkçe harf katlama ──────────────────────
def test_wps_pqr_uyumu_turkce_harfte_sahte_uyari_vermez(app, klasor):
    from app.dialogs import WPSDialog
    d = WPSDialog(oturumlu())
    d.f_metal.setText("İNOKS")
    d.f_dolgu.setText("ER 70S-6")
    assert d._tolerance_issues({"metal": "inoks", "dolgu": "er 70s-6"}) == []
    assert d._tolerance_issues({"metal": "karbon"})          # gerçek fark hâlâ uyarılır


# ── BULGU-10: standart düzenlenince durum yeniden hesaplanır ────────────────────
@pytest.mark.parametrize("kayit, benim, beklenen", [
    ({"myVer": "2021", "lastVer": "2025", "status": "guncelleme"}, "2025", "guncel"),
    ({"myVer": "2025", "lastVer": "2025", "status": "guncel"}, "2021", "guncelleme"),
    ({"myVer": "2021", "manualLastVer": "2025", "status": "guncelleme"}, "2025", "guncel"),
    ({"myVer": "2021", "lastVer": "", "status": "hata"}, "2025", "hata"),   # son sürüm bilinmiyor
    ({"myVer": "2021", "lastVer": "2025", "status": "hata"}, "2025", "hata"),  # son kontrol hatalı
])
def test_standart_duzenlenince_durum_guncellenir(app, kayit, benim, beklenen):
    from app.dialogs import STDDialog
    kayit = dict(kayit, no="ASME IX", org="ASME")
    d = STDDialog(record=kayit)
    d.f_myver.setText(benim)
    assert d.get_record(existing=kayit)["status"] == beklenen


# ── BULGU-11: düz çizgi boyutlandırılır ─────────────────────────────────────────
def test_duz_cizgi_boyutlandirilir(app):
    from app.diagram import DiagramCanvas as D
    s = {"type": "line", "x1": 0, "y1": 10, "x2": 100, "y2": 10}
    D._refit(s, QRectF(0, 10, 100, 0), QRectF(0, 10, 200, 0))
    assert (s["x1"], s["y1"], s["x2"], s["y2"]) == (0, 10, 200, 10)
    s = {"type": "line", "x1": 5, "y1": 0, "x2": 5, "y2": 50}
    D._refit(s, QRectF(5, 0, 0, 50), QRectF(15, 0, 0, 100))
    assert (s["x1"], s["y1"], s["x2"], s["y2"]) == (15, 0, 15, 100)


# ── BULGU-08: yedekleme ve açılış hata yolları ──────────────────────────────────
def test_yarim_gunluk_yedek_kalmaz(klasor, monkeypatch):
    db = database.Database()
    hedef = klasor / "yedek" / f"auto_kalite_{date.today().isoformat()}.db"
    hedef.unlink()
    gercek = sqlite3.connect

    class Yarim:   # backup() bunu bağlantı saymaz → yarıda kesilen yedek benzetimi
        def __init__(self, yol):
            self.c = gercek(yol)

        def execute(self, *a):
            return self.c.execute(*a)

        def close(self):
            self.c.close()

    monkeypatch.setattr(database.sqlite3, "connect", lambda yol, *a, **k: Yarim(yol))
    db._auto_backup()
    monkeypatch.setattr(database.sqlite3, "connect", gercek)
    assert not hedef.exists()                             # yarım dosya bugünün yedeğini engellemez
    assert not list((klasor / "yedek").glob("*.tmp"))
    db._auto_backup()
    c = gercek(hedef)
    try:
        assert c.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    finally:
        c.close()


def test_sema_yukseltme_yedegi_tek_dosya(klasor):
    database.Database()._c.close()
    yol = klasor / "data" / "kalite.db"
    c = sqlite3.connect(yol)
    c.execute("DROP TABLE sartname")
    c.execute("PRAGMA user_version = 4")
    c.commit()
    c.close()
    database.Database()._c.close()
    yedek = next((klasor / "yedek").glob("kalite_SEMA4_YEDEK_*.db"))
    c = sqlite3.connect(yedek)
    try:
        assert c.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    finally:
        c.close()


def test_yukseltme_hatasinda_anlasilir_hata_ve_baglanti_kapanir(klasor, monkeypatch):
    database.Database()._c.close()
    yol = klasor / "data" / "kalite.db"
    c = sqlite3.connect(yol)
    c.execute("PRAGMA user_version = 4")
    c.commit()
    c.close()

    def disk_dolu(self, c, surum):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(database.Database, "_yukselt", disk_dolu)
    with pytest.raises(database.VeritabaniHatasi, match="yükseltilemedi"):
        database.Database()
    os.replace(yol, yol.with_name("tasindi.db"))         # Windows: açık bağlantı dosyayı kilitlerdi


# ── BULGU-06: ITP kuralları veritabanı katmanında da (5d: tablet aynı yoldan yazacak) ──
def itp_kaydi(no="QP-1", rev="0", durum="taslak", rev_sira=0):
    kilitli = durum != "taslak"
    return {"no": no, "rev": rev, "rev_sira": rev_sira, "durum": durum, "baslik": {},
            "sablon": "x", "kalemler": [], "onek_duzelt": False, "siparis_ozel": [],
            "son_aktarim": None, "goruntu": {"__tur": "Dokuman"} if kilitli else None,
            "onay": {"tarih": "01.11.2026", "not": "", "kaydeden": "x"}
            if durum == "onayli" else None}


@pytest.mark.parametrize("veri, mesaj", [
    (itp_kaydi(durum="onayli"), "taslak"),
    (itp_kaydi(rev_sira=3), "rev_sira"),
])
def test_itp_eklemede_yalniz_taslak_ve_sira_sifir(klasor, veri, mesaj):
    db = oturumlu()
    with pytest.raises(R.KayitHatasi, match=mesaj):
        db.add_itp(veri)
    assert db.get_itp() == []


def test_itp_no_rev_tekilligi_veritabaninda(klasor):
    db = oturumlu()
    db.add_itp(itp_kaydi())
    with pytest.raises(R.KayitHatasi, match="zaten var"):
        db.add_itp(itp_kaydi(no="qp-1 "))
    with pytest.raises(R.KayitHatasi, match="Yeni rev"):
        db.add_itp(itp_kaydi(rev="1"))                   # aynı aile: yalnız «Yeni rev»le
    assert len(db.get_itp()) == 1


def test_itp_guncellemede_durum_ve_sira_korunur(klasor):
    db = oturumlu()
    db.add_itp(itp_kaydi())
    a = db.anahtar("itp", 0)
    with pytest.raises(R.KayitHatasi, match="Revize"):
        db.update_itp(0, itp_kaydi(durum="revize"), anahtar=a)
    with pytest.raises(R.KayitHatasi, match="sıra"):
        db.update_itp(0, itp_kaydi(rev_sira=1), anahtar=a)
    with pytest.raises(R.KayitHatasi, match="Onay"):
        db.update_itp(0, dict(itp_kaydi(durum="onayli"), kalemler=["sızdırılmış"]), anahtar=a)
    db.update_itp(0, itp_kaydi(durum="onayli"), anahtar=a)
    assert db.get_itp()[0]["durum"] == "onayli"


def test_itp_yeni_rev_veritabaninda_denetlenir(klasor):
    db = oturumlu()
    db.add_itp(itp_kaydi())
    a = db.anahtar("itp", 0)
    eski = itp_kaydi(durum="revize")
    with pytest.raises(R.KayitHatasi, match="kilitlenmeli"):     # iki etkin taslak olurdu
        db.itp_yeni_rev(0, None, itp_kaydi(rev="1", rev_sira=1), anahtar=a)
    for yeni in (itp_kaydi(rev="1", rev_sira=5), itp_kaydi(no="BASKA", rev="1", rev_sira=1),
                 itp_kaydi(rev="1", rev_sira=1, durum="onayli")):
        with pytest.raises(R.KayitHatasi, match="sonraki"):
            db.itp_yeni_rev(0, eski, yeni, anahtar=a)
    assert [r["durum"] for r in database.Database().get_itp()] == ["taslak"]
    db.itp_yeni_rev(0, eski, itp_kaydi(rev="1", rev_sira=1), anahtar=a)
    assert [(r["rev"], r["durum"]) for r in db.get_itp()] == [("0", "revize"), ("1", "taslak")]

def test_itp_revizyon_zinciri_bolunemez(klasor):
    """Başka revizyonu olan taslağın no'su değişmez (şartnameyle aynı; doğrulama ajanı bulgu 1).
    Tek revizyonlu taslakta no değiştirilebilir."""
    db = oturumlu()
    db.add_itp(itp_kaydi())
    db.itp_yeni_rev(0, itp_kaydi(durum="revize"), itp_kaydi(rev="1", rev_sira=1),
                    anahtar=db.anahtar("itp", 0))
    with pytest.raises(R.KayitHatasi, match="zinciri"):
        db.update_itp(1, itp_kaydi(no="QP-X", rev="1", rev_sira=1), anahtar=db.anahtar("itp", 1))
    db.add_itp(itp_kaydi(no="QP-2"))
    db.update_itp(2, itp_kaydi(no="QP-3"), anahtar=db.anahtar("itp", 2))
    assert [r["no"] for r in db.get_itp()] == ["QP-1", "QP-1", "QP-3"]


def test_itp_onayinda_kilit_goruntusu_son_aktarimdir(klasor):
    """Müşteriye giden Excel neyse kilit odur (doğrulama ajanı bulgu 2; yeni rev'deki kuralla aynı)."""
    db = oturumlu()
    son = {"__tur": "Dokuman", "x": 1}
    db.add_itp(dict(itp_kaydi(), son_aktarim=son))
    a = db.anahtar("itp", 0)
    with pytest.raises(R.KayitHatasi, match="görüntü"):
        db.update_itp(0, dict(itp_kaydi(durum="onayli"), son_aktarim=son,
                              goruntu={"__tur": "Dokuman", "x": 2}), anahtar=a)
    db.update_itp(0, dict(itp_kaydi(durum="onayli"), son_aktarim=son, goruntu=son), anahtar=a)
    assert db.get_itp()[0]["durum"] == "onayli"
