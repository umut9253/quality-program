# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""app/database.py SQLite katmanı (2026-10-30): taşıma, kalıcılık, sıra, yedek, bozuk dosya.
Tüm testler geçici klasörde; gerçek data/ ve yedek/ klasörlerine dokunulmaz."""
import json
import sqlite3
from datetime import date

import pytest

from app import database

ORNEK = {
    "wps": [{"no": "WPS-001", "durum": "Aktif", "pqr": "PQR-001", "proses": "SAW",
             "detay": {"pasolar": [{"paso": "1", "akim": "500"}], "kaynakci": "Ömer Işık"}},
            {"no": "WPS-002", "durum": "İptal", "pqr": ""}],
    "pqr": [{"no": "PQR-001", "test": "Geçti", "diagram": {"tip": "V", "aci": 60}}],
    "std": [{"no": "API 5L", "status": "guncel", "lastCheck": "2026-10-27"},
            {"no": "ISO 21809-1", "status": "guncelleme", "lastCheck": ""}],
    "cert": [{"no": "C1", "ad": "ISO 9001", "bitis": "2027-05-01"},
             {"no": "C2", "ad": "EN 1090", "bitis": "2025-01-01"}],
    "itp": [],
    "sartname": [],
}


@pytest.fixture
def klasor(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(database, "DATA_FILE", str(tmp_path / "data" / "data.json"))
    monkeypatch.setattr(database, "BACKUP_DIR", str(tmp_path / "yedek"))
    return tmp_path


def json_yaz(klasor, veri=ORNEK):
    (klasor / "data").mkdir(exist_ok=True)
    yol = klasor / "data" / "data.json"
    yol.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")
    return yol


def hepsi(db):
    return {b: db_get(db, b) for b in database.SECTIONS}


def db_get(db, b):
    return getattr(db, f"get_{b}")()


def test_ilk_kurulum_ornek_veri(klasor):
    db = database.Database()
    assert (klasor / "data" / "kalite.db").exists()
    assert hepsi(db) == database.SAMPLE_DATA
    assert not (klasor / "data" / "data.json").exists()   # artık JSON yazılmaz


def test_json_tasima_kayipsiz_ve_json_dokunulmaz(klasor):
    yol = json_yaz(klasor)
    once = yol.read_bytes()
    db = database.Database()
    assert hepsi(db) == ORNEK                              # sıra, iç içe alan, Türkçe aynı
    assert yol.read_bytes() == once
    assert hepsi(database.Database()) == ORNEK             # ikinci açılış DB'den


def test_db_varken_json_yeniden_tasinmaz(klasor):
    json_yaz(klasor)
    database.Database()
    json_yaz(klasor, dict(ORNEK, wps=[]))                  # JSON sonradan değişse de
    assert database.Database().get_wps() == ORNEK["wps"]


def test_yazma_islemleri_kalici_ve_sirali(klasor):
    json_yaz(klasor)
    db = database.Database()
    db.add_wps({"no": "WPS-003", "durum": "Aktif"})
    db.update_wps(0, dict(ORNEK["wps"][0], durum="Revizyon Bekliyor"))
    db.delete_wps(1)
    db.add_cert({"no": "C3", "bitis": "2028-01-01"})
    db.delete_cert(0)
    db.mark_std_checked(1, "2026", "guncel", title="Coatings")
    yeni = database.Database()
    assert [w["no"] for w in yeni.get_wps()] == ["WPS-001", "WPS-003"]
    assert yeni.get_wps()[0]["durum"] == "Revizyon Bekliyor"
    assert [c["no"] for c in yeni.get_cert()] == ["C2", "C3"]
    s = yeni.get_std()[1]
    assert (s["lastVer"], s["status"], s["title"], s["lastCheck"]) == \
        ("2026", "guncel", "Coatings", date.today().isoformat())
    assert yeni.wps_count_for_pqr("PQR-001") == 1


def test_turetilmis_sutunlar_sorgulanabilir(klasor):
    json_yaz(klasor)
    database.Database()
    with sqlite3.connect(klasor / "data" / "kalite.db") as c:
        assert c.execute("SELECT no FROM cert WHERE bitis < '2026-01-01'").fetchall() == [("C2",)]
        assert c.execute("SELECT no FROM wps WHERE durum = 'İptal'").fetchall() == [("WPS-002",)]
        assert c.execute("SELECT no FROM std WHERE status = 'guncelleme'").fetchall() == \
            [("ISO 21809-1",)]
        assert c.execute("PRAGMA user_version").fetchone()[0] == database.SEMA_SURUMU


def test_tum_veri_salt_okunur(klasor):
    json_yaz(klasor)
    database.Database()
    yol = str(klasor / "data" / "kalite.db")
    assert database.tum_veri(yol) == ORNEK
    with pytest.raises(sqlite3.OperationalError):          # sunucu yazamaz
        database._baglan(yol, salt_okunur=True).execute("DELETE FROM wps")


def test_gunluk_yedek_gecerli_ve_14_gun(klasor):
    json_yaz(klasor)
    database.Database()._c.close()                         # ilk açılış: bugünün yedeği
    yedek = klasor / "yedek"
    for g in range(1, 20):                                 # eski günlerin yedekleri
        (yedek / f"auto_kalite_2026-01-{g:02d}.db").write_bytes(b"")
    database.Database()
    bugun = yedek / f"auto_kalite_{date.today().isoformat()}.db"
    assert database.tum_veri(str(bugun)) == ORNEK
    assert len(list(yedek.glob("auto_kalite_*.db"))) == database.AUTO_BACKUP_KEEP


def test_bozuk_db_sessizce_ezilmez(klasor):
    (klasor / "data").mkdir()
    db_yolu = klasor / "data" / "kalite.db"
    db_yolu.write_bytes(b"bu bir veritabani degil" * 100)
    with pytest.raises(database.VeritabaniHatasi, match="bozuk"):
        database.Database()
    assert db_yolu.read_bytes() == b"bu bir veritabani degil" * 100
    assert list((klasor / "yedek").glob("kalite_BOZUK_*.db"))


def test_bozuk_json_tasinmaz(klasor):
    (klasor / "data").mkdir()
    (klasor / "data" / "data.json").write_text("{yarim", encoding="utf-8")
    with pytest.raises(database.VeritabaniHatasi, match="data.json"):
        database.Database()
    assert not (klasor / "data" / "kalite.db").exists()


# ── Doğrulama ajanı bulguları (2026-10-30) ───────────────────────────
def test_db_silinince_eski_jsondan_sessizce_kurulmaz(klasor):
    json_yaz(klasor)
    db = database.Database()
    db.add_wps({"no": "WPS-YENI"})                          # taşımadan sonraki değişiklik
    db._c.close()
    (klasor / "data" / "kalite.db").unlink()
    with pytest.raises(database.VeritabaniHatasi, match="yedek"):
        database.Database()                                # donmuş data.json'dan kurmaz
    assert not (klasor / "data" / "kalite.db").exists()


def test_yetim_wal_yeni_db_ye_karismaz(klasor):
    json_yaz(klasor)
    db = database.Database()
    for i in range(50):
        db.add_wps({"no": f"W{i}"})
    data = klasor / "data"
    wal = (data / "kalite.db-wal").read_bytes()
    shm = (data / "kalite.db-shm").read_bytes()
    db._c.close()                                          # "çökme" benzetimi
    for f in ("kalite.db", database.TASINDI_ISARETI):     # hiç kullanılmamış kurulum gibi
        (data / f).unlink()
    for f in (klasor / "yedek").glob("auto_kalite_*.db"):
        f.unlink()
    (data / "kalite.db-wal").write_bytes(wal)
    (data / "kalite.db-shm").write_bytes(shm)
    assert database.Database().get_wps() == ORNEK["wps"]   # 55 değil
    assert list((klasor / "yedek").glob("kalite_YETIM_*-wal"))


def test_kilitli_db_bozuk_sayilmaz(klasor, monkeypatch):
    json_yaz(klasor)
    database.Database()._c.close()
    monkeypatch.setattr(database, "KILIT_BEKLEME", 0.1)
    kilit = sqlite3.connect(klasor / "data" / "kalite.db")
    kilit.execute("PRAGMA locking_mode=EXCLUSIVE")   # WAL'da okuyucuyu da engeller
    kilit.execute("BEGIN EXCLUSIVE")
    kilit.execute("UPDATE wps SET sira = sira")
    try:
        with pytest.raises(database.VeritabaniHatasi, match="kilitli"):
            database.Database()
    finally:
        kilit.rollback(); kilit.close()
    assert not list((klasor / "yedek").glob("kalite_BOZUK_*"))


def test_acilamayan_db_anlamli_hata(klasor):
    (klasor / "data" / "kalite.db").mkdir(parents=True)    # dosya yerine klasör
    with pytest.raises(database.VeritabaniHatasi):
        database.Database()


@pytest.mark.parametrize("icerik", ['[1, 2]', '{"wps": null}', '{"wps": [{"a": NaN}]}',
                                    '{"wps": [1]}'])
def test_yapisal_bozuk_json_anlamli_hata(klasor, icerik):
    (klasor / "data").mkdir()
    (klasor / "data" / "data.json").write_text(icerik, encoding="utf-8")
    with pytest.raises(database.VeritabaniHatasi, match="data.json"):
        database.Database()
    assert not list((klasor / "data").glob("kalite.db*"))


def test_yazma_hatasinda_bellek_degismez(klasor):
    json_yaz(klasor)
    db = database.Database()
    once = json.loads(json.dumps(db.get_std()))
    db._c.close()                                          # yazma başarısız olsun
    with pytest.raises(database.VeritabaniHatasi):
        db.mark_std_checked(0, "2099", "guncelleme")
    with pytest.raises(database.VeritabaniHatasi):
        db.add_cert({"no": "X"})
    assert db.get_std() == once and len(db.get_cert()) == len(ORNEK["cert"])


def test_yeni_sema_surumu_reddedilir(klasor):
    json_yaz(klasor)
    database.Database()._c.close()
    with sqlite3.connect(klasor / "data" / "kalite.db") as c:
        c.execute("PRAGMA user_version = 99")
    with pytest.raises(database.VeritabaniHatasi, match="sürüm"):
        database.Database()


def test_ornek_veriyle_kurulum_isaret_birakmaz(klasor):
    database.Database()._c.close()                         # data.json yok → örnek veri
    assert not (klasor / "data" / database.TASINDI_ISARETI).exists()


def test_tasima_disk_hatasi_anlamli_ve_isaretsiz(klasor, monkeypatch):
    json_yaz(klasor)
    def bozuk(*a, **k):
        raise OSError("disk dolu")
    monkeypatch.setattr(database.os, "replace", bozuk)
    with pytest.raises(database.VeritabaniHatasi, match="disk dolu"):
        database.Database()
    data = klasor / "data"
    assert not (data / database.TASINDI_ISARETI).exists()
    assert not (data / "kalite.db").exists() and not list(data.glob("*.tasima"))


# ── Antigravity denetimi (DENETIM-RAPORU-ARAYUZ-TABLET-SQLITE-2026-10-30) ──
def test_isaret_eksikse_acilista_tamamlanir(klasor):
    # BULGU-01: replace ile işaret arasında çökme → DB var, işaret yok; koruma kendini onarır
    json_yaz(klasor)
    database.Database()._c.close()
    isaret = klasor / "data" / database.TASINDI_ISARETI
    isaret.unlink()
    database.Database()._c.close()
    assert isaret.exists()


def test_isaret_ve_db_silinse_de_yedek_varken_jsondan_kurulmaz(klasor):
    # BULGU-02: kalite.db* birlikte silinirse yedekler eski SQLite kullanımını ele verir
    json_yaz(klasor)
    database.Database()._c.close()
    for f in (klasor / "data").glob("kalite.db*"):
        f.unlink()
    with pytest.raises(database.VeritabaniHatasi, match="yedek"):
        database.Database()
    assert not (klasor / "data" / "kalite.db").exists()


# ── Kimlik/yetki/değişiklik kaydı (şema 2, 2026-10-30) ───────────────
from app import kimlik as KM  # noqa: E402

SIFRE = "Guclu-Sifre-1"


def oturumlu(klasor, rol=KM.DUZENLEYICI):
    json_yaz(klasor)
    db = database.Database()
    KM.kullanici_ekle(db._c, "ali", SIFRE, rol, yapan=None)
    db.kullanici = KM.giris(db._c, "ali", SIFRE)
    return db


def test_sema1_veritabani_yedeklenip_yukseltilir(klasor):
    json_yaz(klasor)
    database.Database()._c.close()
    yol = klasor / "data" / "kalite.db"
    with sqlite3.connect(yol) as c:                         # şema 1'e geri indir (benzetim)
        for b in database.SECTIONS:
            c.execute(f"ALTER TABLE {b} DROP COLUMN surum")
        for t in ("kullanicilar", "cihaz_kilit", "cihaz_hata", "oturumlar", "guvenlik",
                  "degisiklikler"):
            c.execute(f"DROP TABLE {t}")
        c.execute("PRAGMA user_version = 1")
    db = database.Database()
    assert {b: db_get(db, b) for b in database.SECTIONS} == ORNEK
    assert db._c.execute("PRAGMA user_version").fetchone()[0] == database.SEMA_SURUMU == 7
    yedek = list((klasor / "yedek").glob("kalite_SEMA1_YEDEK_*.db"))
    assert len(yedek) == 1 and database.tum_veri(str(yedek[0])) == ORNEK


def test_sema2_veritabani_sema3e_yukseltilir(klasor):
    """Şema 3 (V-7-15): cihaz_hata tablosu; şema 2 dosyası yedeklenip yükseltilir."""
    json_yaz(klasor)
    database.Database()._c.close()
    yol = klasor / "data" / "kalite.db"
    with sqlite3.connect(yol) as c:
        c.execute("DROP TABLE cihaz_hata")
        c.execute("PRAGMA user_version = 2")
    db = database.Database()
    assert {b: db_get(db, b) for b in database.SECTIONS} == ORNEK
    assert db._c.execute("PRAGMA user_version").fetchone()[0] == database.SEMA_SURUMU
    db._c.execute("SELECT ip, ad, adet, son FROM cihaz_hata").fetchall()
    assert len(list((klasor / "yedek").glob("kalite_SEMA2_YEDEK_*.db"))) == 1


def test_degisiklik_kaydi_kim_ne_zaman_once_sonra(klasor):
    db = oturumlu(klasor)
    db.add_cert({"no": "C9", "bitis": "2030-01-01"})
    db.update_cert(0, dict(ORNEK["cert"][0], bitis="2031-01-01"))
    db.delete_wps(1)
    k = db.degisiklik_kayitlari()
    assert [(x["islem"], x["bolum"], x["kullanici"], x["kaynak"]) for x in k] == [
        ("sil", "wps", "ali", "masaustu"), ("guncelle", "cert", "ali", "masaustu"),
        ("ekle", "cert", "ali", "masaustu")]
    assert k[1]["once"]["bitis"] == "2027-05-01" and k[1]["sonra"]["bitis"] == "2031-01-01"
    assert k[0]["kayit_no"] == "WPS-002" and k[0]["sonra"] is None


def test_okuyucu_yazamaz(klasor):
    db = oturumlu(klasor, KM.OKUYUCU)
    with pytest.raises(database.YetkiHatasi):
        db.add_wps({"no": "X"})
    with pytest.raises(database.YetkiHatasi):
        db.update_std(0, {"no": "Y"})
    assert db.get_wps() == ORNEK["wps"] and db.degisiklik_kayitlari() == []


def test_baska_cihaz_degistirince_cakisma_ve_yenileme(klasor):
    db = oturumlu(klasor)
    diger = database._baglan(database.db_yolu())             # tablet sunucusunun yazması
    kid, surum = db._ids["cert"][0], db._surum["cert"][0]
    database.kayit_guncelle(diger, "cert", kid, dict(ORNEK["cert"][0], ad="TABLETTEN"), surum,
                            "veli", "tablet")
    assert db.disaridan_degisti()
    with pytest.raises(database.CakismaHatasi):
        db.update_cert(0, dict(ORNEK["cert"][0], ad="MASAUSTU"))   # eski görünümden yazamaz
    assert db.get_cert()[0]["ad"] == "TABLETTEN"                  # liste yenilendi
    db.update_cert(0, dict(db.get_cert()[0], ad="MASAUSTU"))       # yeniden deneyince olur
    assert database.tum_veri(database.db_yolu())["cert"][0]["ad"] == "MASAUSTU"


def test_kayit_surumu_eskiyse_reddedilir(klasor):
    json_yaz(klasor)
    database.Database()._c.close()
    c = database._baglan(database.db_yolu())
    kid = c.execute("SELECT id FROM wps ORDER BY sira").fetchone()[0]
    yeni = database.kayit_guncelle(c, "wps", kid, {"no": "W1"}, 0, "a", "tablet")
    assert yeni == 1
    with pytest.raises(database.CakismaHatasi):
        database.kayit_guncelle(c, "wps", kid, {"no": "W2"}, 0, "b", "tablet")   # eski sürüm
    with pytest.raises(database.CakismaHatasi):
        database.kayit_sil(c, "wps", 99999, 0, "b", "tablet")


def test_gecersiz_bolum_adi_reddedilir(klasor):
    json_yaz(klasor)
    database.Database()._c.close()
    c = database._baglan(database.db_yolu())
    with pytest.raises(database.VeritabaniHatasi):
        database.kayit_ekle(c, "wps; DROP TABLE wps", {"no": "x"}, "a", "tablet")


def test_tablet_girisi_masaustu_yazmasini_engellemez(klasor):
    # data_version her yazmada artar (giriş/oturum kaydı dahil): yalnız KAYIT değişikliği sayılır
    db = oturumlu(klasor)
    diger = database._baglan(database.db_yolu())
    KM.kullanici_ekle(diger, "veli", SIFRE, KM.OKUYUCU, yapan=None)
    KM.oturum_ac(diger, KM.giris(diger, "veli", SIFRE, ip="10.0.0.5"), cihaz="tablet")
    assert not db.disaridan_degisti()
    db.update_cert(0, dict(ORNEK["cert"][0], ad="masaüstü"))         # çakışma hatası yok


# ── Antigravity 2026-10-30 BULGU-01: açık pencere sırasında 3 sn yenilemesi ─────────────
def tablet():
    return database._baglan(database.db_yolu())


def tablet_guncelle(kid, **alan):
    c = tablet()
    veri, surum = c.execute("SELECT veri, surum FROM cert WHERE id = ?", (kid,)).fetchone()
    database.kayit_guncelle(c, "cert", kid, dict(json.loads(veri), **alan), surum, "veli",
                            "tablet")


def test_pencere_acikken_yenileme_tablet_degisikligini_ezdirmez(klasor):
    db = oturumlu(klasor)
    a = db.anahtar("cert", 0)                       # düzenleme penceresi açıldı
    tablet_guncelle(a[0], ad="TABLETTEN")
    db.yeniden_yukle()                              # pencere açıkken 3 sn tıkı
    with pytest.raises(database.CakismaHatasi):
        db.update_cert(0, dict(ORNEK["cert"][0], ad="MASAUSTU"), anahtar=a)
    assert database.tum_veri(database.db_yolu())["cert"][0]["ad"] == "TABLETTEN"


def test_pencere_acikken_ustteki_kayit_silinirse_dogru_kayit_yazilir(klasor):
    db = oturumlu(klasor)
    a = db.anahtar("cert", 1)                       # C2 düzenleniyor
    c = tablet()
    database.kayit_sil(c, "cert", db._ids["cert"][0], 0, "veli", "tablet")   # C1 silindi
    db.yeniden_yukle()                              # indeksler kaydı: C2 artık 0
    db.update_cert(1, dict(ORNEK["cert"][1], ad="MASAUSTU"), anahtar=a)
    assert database.tum_veri(database.db_yolu())["cert"] == [dict(ORNEK["cert"][1], ad="MASAUSTU")]
    assert db.get_cert() == [dict(ORNEK["cert"][1], ad="MASAUSTU")]


def test_pencere_acikken_ustteki_kayit_silinirse_dogru_kayit_silinir(klasor):
    db = oturumlu(klasor)
    db.add_wps({"no": "WPS-003"})
    a = db.anahtar("wps", 1)                        # WPS-002 için silme onayı açık
    database.kayit_sil(tablet(), "wps", db._ids["wps"][0], 0, "veli", "tablet")
    db.yeniden_yukle()
    db.delete_wps(1, anahtar=a)                     # eski indeks artık WPS-003'ü gösteriyor
    assert [w["no"] for w in database.tum_veri(database.db_yolu())["wps"]] == ["WPS-003"]


def test_pencere_acikken_kayit_silindiyse_cakisma(klasor):
    db = oturumlu(klasor)
    a = db.anahtar("cert", 0)
    database.kayit_sil(tablet(), "cert", a[0], 0, "veli", "tablet")
    db.yeniden_yukle()
    with pytest.raises(database.CakismaHatasi):
        db.update_cert(0, {"no": "C1", "ad": "MASAUSTU"}, anahtar=a)
    assert [c["no"] for c in database.tum_veri(database.db_yolu())["cert"]] == ["C2"]


def test_silinen_kaydin_id_si_yeni_kayda_verilmez(klasor):
    # id yeniden kullanılırsa eski anahtar (id, sürüm 0) başka bir kaydı ezer (tablet formu dahil)
    db = oturumlu(klasor)
    a = db.anahtar("cert", 1)                       # en büyük id
    database.kayit_sil(tablet(), "cert", a[0], 0, "veli", "tablet")
    kid = database.kayit_ekle(tablet(), "cert", {"no": "C3"}, "veli", "tablet")
    assert kid != a[0]
    db.yeniden_yukle()
    with pytest.raises(database.CakismaHatasi):
        database.kayit_guncelle(tablet(), "cert", a[0], {"no": "eski form"}, a[1], "x", "tablet")


# ── Antigravity 2026-10-30 BULGU-02: salt okunur URI yüzde-kodlanmalı ──────────────────
@pytest.mark.parametrize("ad", ["Proje #1", "test%20dir", "QUALITY PROGRAM", "Güncel İş ı"])
def test_salt_okunur_baglanti_ozel_karakterli_klasorde(tmp_path, monkeypatch, ad):
    kok = tmp_path / ad
    kok.mkdir()
    monkeypatch.setattr(database, "DATA_DIR", str(kok / "data"))
    monkeypatch.setattr(database, "DATA_FILE", str(kok / "data" / "data.json"))
    monkeypatch.setattr(database, "BACKUP_DIR", str(kok / "yedek"))
    json_yaz(kok)
    database.Database()._c.close()
    assert database.tum_veri(database.db_yolu()) == ORNEK


# ── Antigravity 2026-10-30 NOT-01: günlük yedek tek dosya (WAL bayrağı yok) ────────────
def test_gunluk_yedek_tek_dosya_wal_kipinde_degil(klasor):
    json_yaz(klasor)
    db = database.Database()
    yedek = next((klasor / "yedek").glob("auto_kalite_*.db"))
    with sqlite3.connect(yedek) as c:
        assert c.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    c.close()
    db._c.close()
    assert not list((klasor / "yedek").glob("auto_kalite_*.db-*"))
    assert database.tum_veri(str(yedek)) == ORNEK


def test_eszamanli_eklemeler_ayni_id_ye_carpmaz(klasor):
    # Doğrulama ajanı: id artık programda hesaplanıyor; MAX okuma ile INSERT arası atomik olmalı
    import threading
    json_yaz(klasor)
    database.Database()._c.close()
    hatalar, idler = [], []

    def ekle(n):
        c = database._baglan(database.db_yolu())
        for k in range(25):
            try:
                idler.append(database.kayit_ekle(c, "wps", {"no": f"T{n}-{k}"}, "x", "tablet"))
            except Exception as e:
                hatalar.append(e)
        c.close()
    isler = [threading.Thread(target=ekle, args=(n,)) for n in range(4)]
    for t in isler:
        t.start()
    for t in isler:
        t.join()
    assert hatalar == [] and len(set(idler)) == 100


# ── Plan 5a: itp bölümü ─────────────────────────────────────────────
def itp_kaydi(no="QP-1", rev="0", durum="taslak"):
    # kilitli kayıt tutarlı olmalı (denetim BULGU-01): görüntü dolu, onaylıda onay bilgisi
    kilitli = durum != "taslak"
    return {"no": no, "rev": rev, "rev_sira": 0, "durum": durum, "baslik": {}, "sablon": "x",
            "kalemler": [], "onek_duzelt": False, "siparis_ozel": [], "son_aktarim": None,
            "goruntu": {"__tur": "Dokuman"} if kilitli else None,
            "onay": {"tarih": "01.11.2026", "not": "", "kaydeden": "x"}
            if durum == "onayli" else None}


def kilitli_itp(db, durum="onayli"):
    """Kilitli kayıt yalnız onay ya da «Yeni rev»le oluşur (Antigravity tam program BULGU-06):
    onaylıda tek kayıt, revizede kaynak (indeks 0) + yeni taslak."""
    db.add_itp(itp_kaydi())
    if durum == "onayli":
        db.update_itp(0, itp_kaydi(durum="onayli"), anahtar=db.anahtar("itp", 0))
    else:
        db.itp_yeni_rev(0, itp_kaydi(durum="revize"), dict(itp_kaydi(rev="1"), rev_sira=1),
                        anahtar=db.anahtar("itp", 0))


def test_sema3_veritabani_sema4e_yukseltilir_ve_eski_yedek_okunur(klasor):
    json_yaz(klasor)
    database.Database()._c.close()
    yol = klasor / "data" / "kalite.db"
    with sqlite3.connect(yol) as c:
        c.execute("DROP TABLE itp")
        c.execute("PRAGMA user_version = 3")
    db = database.Database()
    assert db._c.execute("PRAGMA user_version").fetchone()[0] == database.SEMA_SURUMU
    assert {b: db_get(db, b) for b in database.SECTIONS} == ORNEK
    yedek = list((klasor / "yedek").glob("kalite_SEMA3_YEDEK_*.db"))
    assert len(yedek) == 1 and database.tum_veri(str(yedek[0])) == ORNEK   # itp tablosu yok: boş


def test_data_json_itp_anahtarsiz_tasinir(klasor):
    eski = {b: k for b, k in ORNEK.items() if b != "itp"}
    json_yaz(klasor, eski)
    assert database.Database().get_itp() == []


def test_itp_ekle_id_doner_guncelle_sil(klasor):
    db = oturumlu(klasor)
    kid = db.add_itp(itp_kaydi())
    assert db.anahtar("itp", 0) == (kid, 0)
    db.update_itp(0, dict(itp_kaydi(), rev="0"), anahtar=(kid, 0))
    db.delete_itp(0, anahtar=(kid, 1))
    assert db.get_itp() == []
    assert database.Database().get_itp() == []


def test_okuyucu_itp_yazamaz(klasor):
    db = oturumlu(klasor, rol=KM.OKUYUCU)
    with pytest.raises(database.YetkiHatasi):
        db.add_itp(itp_kaydi())


def test_kilitli_itp_yalniz_yonetici_gerekceyle_siler_ve_kaydeder(klasor):
    db = oturumlu(klasor, rol=KM.DUZENLEYICI)
    kilitli_itp(db)
    from app.itp.kayit import KayitHatasi
    with pytest.raises(KayitHatasi, match="yönetici"):
        db.delete_itp(0, gerekce="x")
    KM.kullanici_ekle(db._c, "yon", SIFRE, KM.YONETICI, yapan=None)
    db.kullanici = KM.giris(db._c, "yon", SIFRE)
    with pytest.raises(KayitHatasi, match="gerekçe"):
        db.delete_itp(0, gerekce=" ")
    db.delete_itp(0, gerekce="yanlış sipariş")
    olay = db._c.execute("SELECT olay, kullanici, yapan, ayrinti FROM guvenlik "
                         "WHERE olay = 'itp_kilitli_sil'").fetchone()
    assert olay == ("itp_kilitli_sil", "QP-1 Rev.0", "yon", "yanlış sipariş")


def test_itp_yeni_rev_tek_islemde_yarim_kalmaz(klasor, monkeypatch):
    """Eskiyi kilitleme + yeniyi ekleme tek işlem: ikinci adım düşerse ikisi de geri alınır."""
    db = oturumlu(klasor)
    db.add_itp(itp_kaydi())
    gercek = database._kaydet_degisiklik

    def bozuk(c, b, kid, islem, *a):
        if islem == "ekle":
            raise sqlite3.OperationalError("disk dolu")
        return gercek(c, b, kid, islem, *a)
    monkeypatch.setattr(database, "_kaydet_degisiklik", bozuk)
    with pytest.raises(database.VeritabaniHatasi):
        db.itp_yeni_rev(0, itp_kaydi(durum="revize"), dict(itp_kaydi(rev="1"), rev_sira=1),
                        anahtar=db.anahtar("itp", 0))
    monkeypatch.setattr(database, "_kaydet_degisiklik", gercek)
    assert [(r["rev"], r["durum"]) for r in database.Database().get_itp()] == [("0", "taslak")]
    assert [(r["rev"], r["durum"]) for r in db.get_itp()] == [("0", "taslak")]


def test_itp_yeni_rev_iki_kayit_yazar(klasor):
    db = oturumlu(klasor)
    db.add_itp(itp_kaydi())
    kid = db.itp_yeni_rev(0, itp_kaydi(durum="revize"), dict(itp_kaydi(rev="1"), rev_sira=1),
                          anahtar=db.anahtar("itp", 0))
    assert [(r["rev"], r["durum"]) for r in db.get_itp()] == [("0", "revize"), ("1", "taslak")]
    assert db.indeks("itp", kid) == 1


def test_kilitli_itp_veritabani_katmaninda_da_guncellenemez(klasor):
    db = oturumlu(klasor)
    kilitli_itp(db)
    from app.itp.kayit import KayitHatasi
    with pytest.raises(KayitHatasi, match="kilitli"):
        db.update_itp(0, itp_kaydi(), anahtar=db.anahtar("itp", 0))
    with pytest.raises(KayitHatasi, match="kilitli"):
        db.itp_yeni_rev(0, itp_kaydi(durum="revize"), itp_kaydi(rev="1"))
    assert db.get_itp()[0]["durum"] == "onayli"


@pytest.mark.parametrize("bozuk", [
    dict(itp_kaydi(), durum="onayli"),                      # görüntüsüz, onaysız onaylı
    dict(itp_kaydi(durum="onayli"), goruntu=None),          # görüntüsüz kilit
    dict(itp_kaydi(durum="onayli"), onay=None),             # onay bilgisi yok
    dict(itp_kaydi(), durum="revize"),                      # görüntüsüz revize
    dict(itp_kaydi(), durum="kilitsiz"),                    # bilinmeyen durum
])
def test_tutarsiz_itp_veritabanina_yazilamaz(klasor, bozuk):
    """Denetim BULGU-01: onay akışı atlanarak görüntüsüz kilit yazılırsa kayıt açılınca çöker."""
    db = oturumlu(klasor)
    db.add_itp(itp_kaydi())
    from app.itp.kayit import KayitHatasi
    with pytest.raises(KayitHatasi):
        db.update_itp(0, bozuk, anahtar=db.anahtar("itp", 0))
    with pytest.raises(KayitHatasi):
        db.add_itp(bozuk)
    with pytest.raises(KayitHatasi):
        db.itp_yeni_rev(0, bozuk, itp_kaydi(rev="1"), anahtar=db.anahtar("itp", 0))
    with pytest.raises(KayitHatasi):
        db.itp_yeni_rev(0, None, bozuk, anahtar=db.anahtar("itp", 0))
    assert [(r["rev"], r["durum"]) for r in database.Database().get_itp()] == [("0", "taslak")]


def test_kilitli_silme_ve_gerekce_kaydi_tek_islem(klasor, monkeypatch):
    db = oturumlu(klasor, rol=KM.YONETICI)
    kilitli_itp(db, "revize")

    def bozuk(*a, **k):
        raise sqlite3.OperationalError("disk dolu")
    monkeypatch.setattr(database.kimlik, "_olay", bozuk)
    with pytest.raises(database.VeritabaniHatasi):
        db.delete_itp(0, gerekce="yanlış")
    assert len(database.Database().get_itp()) == 2 and len(db.get_itp()) == 2


# ── Plan 5b: sartname bölümü ─────────────────────────────────────────
def sartname_kaydi(ad="KURUM_B Genel Şartname", rev="0", durum="taslak"):
    from app.itp import sartname as S
    v = dict(S.kayit_kur("KURUM_B", ad), rev=rev, durum=durum)
    v["maddeler"] = [{"id": "m1", "kontrol": "hidrostatik", "grup": "", "kaynak": "7.2.4",
                      "tur": "metin", "sutun": "frekans",
                      "metin": {"tr": "Her boru", "en": "Every pipe"}}]
    return v


def yururlukte_ekle(db, **k):
    """Kilitli kayıt yalnız taslak → yürürlükte geçişiyle oluşur (doğrulama ORTA-2)."""
    kid = db.add_sartname(sartname_kaydi(**k))
    i = db.indeks("sartname", kid)
    db.update_sartname(i, sartname_kaydi(durum="yururlukte", **k), anahtar=db.anahtar("sartname", i))
    return kid


def test_sema4_veritabani_sema5e_yukseltilir_ve_eski_yedek_okunur(klasor):
    json_yaz(klasor)
    database.Database()._c.close()
    yol = klasor / "data" / "kalite.db"
    with sqlite3.connect(yol) as c:
        c.execute("DROP TABLE sartname")
        c.execute("PRAGMA user_version = 4")
    db = database.Database()
    assert db._c.execute("PRAGMA user_version").fetchone()[0] == database.SEMA_SURUMU
    assert {b: db_get(db, b) for b in database.SECTIONS} == ORNEK
    yedek = list((klasor / "yedek").glob("kalite_SEMA4_YEDEK_*.db"))
    assert len(yedek) == 1 and database.tum_veri(str(yedek[0])) == ORNEK   # tablosuz: boş


def test_sartname_ekle_guncelle_sil_ve_degisiklik_kaydi(klasor):
    db = oturumlu(klasor)
    kid = db.add_sartname(sartname_kaydi())
    assert db.anahtar("sartname", 0) == (kid, 0)
    db.update_sartname(0, dict(sartname_kaydi(), no="ÇBŞ-1"), anahtar=(kid, 0))
    assert database.Database().get_sartname()[0]["no"] == "ÇBŞ-1"
    kayit_no = db._c.execute("SELECT kayit_no FROM degisiklikler WHERE bolum = 'sartname' "
                             "ORDER BY id").fetchall()
    assert kayit_no == [("KURUM_B Genel Şartname",), ("ÇBŞ-1",)]   # no boşsa ad
    db.delete_sartname(0, anahtar=(kid, 1))
    assert db.get_sartname() == [] and database.Database().get_sartname() == []


def test_okuyucu_sartname_yazamaz(klasor):
    db = oturumlu(klasor, rol=KM.OKUYUCU)
    with pytest.raises(database.YetkiHatasi):
        db.add_sartname(sartname_kaydi())


def test_kilitli_sartname_guncellenemez(klasor):
    from app.itp.sartname import SartnameHatasi
    db = oturumlu(klasor)
    yururlukte_ekle(db)
    with pytest.raises(SartnameHatasi, match="kilitli"):
        db.update_sartname(0, sartname_kaydi(), anahtar=db.anahtar("sartname", 0))
    with pytest.raises(SartnameHatasi, match="kilitli"):
        db.sartname_yeni_rev(0, sartname_kaydi(durum="revize"), sartname_kaydi(rev="1"))
    assert db.get_sartname()[0]["durum"] == "yururlukte"


def test_sartname_yeni_rev_iki_kayit_tek_islem(klasor, monkeypatch):
    db = oturumlu(klasor)
    db.add_sartname(sartname_kaydi())
    gercek = database._kaydet_degisiklik

    def bozuk(c, b, kid, islem, *a):
        if islem == "ekle":
            raise sqlite3.OperationalError("disk dolu")
        return gercek(c, b, kid, islem, *a)
    monkeypatch.setattr(database, "_kaydet_degisiklik", bozuk)
    with pytest.raises(database.VeritabaniHatasi):
        db.sartname_yeni_rev(0, sartname_kaydi(durum="revize"), dict(sartname_kaydi(rev="1"), rev_sira=1),
                             anahtar=db.anahtar("sartname", 0))
    monkeypatch.setattr(database, "_kaydet_degisiklik", gercek)
    assert [(r["rev"], r["durum"]) for r in database.Database().get_sartname()] == [("0", "taslak")]
    kid = db.sartname_yeni_rev(0, sartname_kaydi(durum="revize"), dict(sartname_kaydi(rev="1"), rev_sira=1),
                               anahtar=db.anahtar("sartname", 0))
    assert [(r["rev"], r["durum"]) for r in db.get_sartname()] == [("0", "revize"), ("1", "taslak")]
    assert db.indeks("sartname", kid) == 1


def test_kilitli_sartname_yonetici_gerekceyle_siler(klasor, monkeypatch):
    from app.itp.sartname import SartnameHatasi
    db = oturumlu(klasor, rol=KM.DUZENLEYICI)
    yururlukte_ekle(db)
    with pytest.raises(SartnameHatasi, match="yönetici"):
        db.delete_sartname(0, gerekce="x")
    KM.kullanici_ekle(db._c, "yon", SIFRE, KM.YONETICI, yapan=None)
    db.kullanici = KM.giris(db._c, "yon", SIFRE)

    def bozuk(*a, **k):
        raise sqlite3.OperationalError("disk dolu")
    gercek = database.kimlik._olay
    monkeypatch.setattr(database.kimlik, "_olay", bozuk)
    with pytest.raises(database.VeritabaniHatasi):
        db.delete_sartname(0, gerekce="yanlış")
    # undo() DEĞİL: klasor fikstürünün yollarını da geri alır, gerçek data/ açılır
    monkeypatch.setattr(database.kimlik, "_olay", gercek)
    assert len(database.Database().get_sartname()) == 1       # tek işlem: silme geri alındı
    db.delete_sartname(0, gerekce="yanlış kurum")
    olay = db._c.execute("SELECT olay, kullanici, yapan, ayrinti FROM guvenlik "
                         "WHERE olay = 'sartname_kilitli_sil'").fetchone()
    assert olay == ("sartname_kilitli_sil", "KURUM_B / KURUM_B Genel Şartname Rev.0", "yon",
                    "yanlış kurum")


def test_kilitli_sartname_yonetici_gerekceyle_duzeltir(klasor, monkeypatch):
    from app.itp.sartname import SartnameHatasi
    db = oturumlu(klasor, rol=KM.YONETICI)
    yururlukte_ekle(db)
    duz = sartname_kaydi(durum="yururlukte")
    duz["maddeler"][0]["metin"] = {"tr": "Her 10 boru", "en": "Every 10 pipes"}
    with pytest.raises(SartnameHatasi, match="'rev'"):
        db.sartname_kilitli_duzelt(0, dict(duz, rev="1"), "x")

    def bozuk(*a, **k):
        raise sqlite3.OperationalError("disk dolu")
    gercek = database.kimlik._olay
    monkeypatch.setattr(database.kimlik, "_olay", bozuk)
    with pytest.raises(database.VeritabaniHatasi):
        db.sartname_kilitli_duzelt(0, duz, "yazım hatası")
    monkeypatch.setattr(database.kimlik, "_olay", gercek)   # undo() değil (yolları geri alır)
    assert database.Database().get_sartname()[0]["maddeler"][0]["metin"]["tr"] == "Her boru"
    db.sartname_kilitli_duzelt(0, duz, "yazım hatası", anahtar=db.anahtar("sartname", 0))
    assert db.get_sartname()[0]["maddeler"][0]["metin"]["tr"] == "Her 10 boru"
    assert db.get_sartname()[0]["durum"] == "yururlukte"
    olay = db._c.execute("SELECT olay, kullanici, ayrinti FROM guvenlik "
                         "WHERE olay = 'sartname_kilitli_duzelt'").fetchone()
    assert olay == ("sartname_kilitli_duzelt", "KURUM_B / KURUM_B Genel Şartname Rev.0", "yazım hatası")


def test_duzenleyici_kilitli_sartnameyi_duzeltemez(klasor):
    from app.itp.sartname import SartnameHatasi
    db = oturumlu(klasor, rol=KM.DUZENLEYICI)
    yururlukte_ekle(db)
    with pytest.raises(SartnameHatasi, match="yönetici"):
        db.sartname_kilitli_duzelt(0, sartname_kaydi(durum="yururlukte"), "x")


@pytest.mark.parametrize("bozuk", [
    dict(sartname_kaydi(), durum="kilitsiz"),
    dict(sartname_kaydi(), tur="baska"),
    {k: v for k, v in sartname_kaydi().items() if k != "maddeler"},
    dict(sartname_kaydi(), maddeler=[{"id": "m1", "kontrol": "yok", "grup": "", "kaynak": "",
                                       "tur": "metin", "sutun": "kabul",
                                       "metin": {"tr": "x", "en": ""}}]),
    dict(sartname_kaydi(durum="yururlukte"), maddeler=[]) | {"maddeler": [
        {"id": "m1", "kontrol": "hidrostatik", "grup": "", "kaynak": "", "tur": "metin",
         "sutun": "kabul", "metin": {"tr": "", "en": ""}}]},          # kilitli + boş TR
])
def test_tutarsiz_sartname_yazilamaz(klasor, bozuk):
    from app.itp.sartname import SartnameHatasi
    db = oturumlu(klasor)
    db.add_sartname(sartname_kaydi())
    with pytest.raises(SartnameHatasi):
        db.update_sartname(0, bozuk, anahtar=db.anahtar("sartname", 0))
    with pytest.raises(SartnameHatasi):
        db.add_sartname(bozuk)
    with pytest.raises(SartnameHatasi):
        db.sartname_yeni_rev(0, None, bozuk, anahtar=db.anahtar("sartname", 0))
    assert [(r["rev"], r["durum"]) for r in database.Database().get_sartname()] == [("0", "taslak")]


# ── Doğrulama ORTA-2 / DÜŞÜK-5: veritabanı katmanı durum geçişlerini ve tekilliği korur ──
def _bos_maddeli(**k):
    return dict(sartname_kaydi(**k), maddeler=[])


@pytest.mark.parametrize("bozuk", [
    sartname_kaydi(durum="yururlukte"),             # kilitli kayıt doğrudan eklenemez
    sartname_kaydi(durum="revize"),
])
def test_sartname_yalniz_taslak_eklenir(klasor, bozuk):
    from app.itp.sartname import SartnameHatasi
    db = oturumlu(klasor)
    with pytest.raises(SartnameHatasi):
        db.add_sartname(bozuk)
    assert database.Database().get_sartname() == []


@pytest.mark.parametrize("bozuk", [
    _bos_maddeli(durum="yururlukte"),                # maddesiz kilit
    sartname_kaydi(rev="", durum="yururlukte"),      # rev'siz kilit
    sartname_kaydi(durum="revize"),                  # taslak → revize yalnız «Yeni rev»le
])
def test_sartname_guncellemede_gecersiz_gecis_reddedilir(klasor, bozuk):
    from app.itp.sartname import SartnameHatasi
    db = oturumlu(klasor)
    db.add_sartname(sartname_kaydi(rev=bozuk["rev"]))
    with pytest.raises(SartnameHatasi):
        db.update_sartname(0, bozuk, anahtar=db.anahtar("sartname", 0))
    assert database.Database().get_sartname()[0]["durum"] == "taslak"


def test_kilitli_duzeltme_maddeleri_bosaltamaz(klasor):
    from app.itp.sartname import SartnameHatasi
    db = oturumlu(klasor, rol=KM.YONETICI)
    yururlukte_ekle(db)
    with pytest.raises(SartnameHatasi, match="madde"):
        db.sartname_kilitli_duzelt(0, _bos_maddeli(durum="yururlukte"), "temizlik",
                                   anahtar=db.anahtar("sartname", 0))
    assert len(database.Database().get_sartname()[0]["maddeler"]) == 1


def test_sartname_yeni_rev_durumlari_korunur(klasor):
    from app.itp.sartname import SartnameHatasi
    db = oturumlu(klasor)
    db.add_sartname(sartname_kaydi())
    a = db.anahtar("sartname", 0)
    with pytest.raises(SartnameHatasi):              # yeni kayıt taslak olmalı
        db.sartname_yeni_rev(0, sartname_kaydi(durum="revize"),
                             sartname_kaydi(rev="1", durum="yururlukte"), anahtar=a)
    with pytest.raises(SartnameHatasi):              # kaynak "revize" olarak kilitlenir
        db.sartname_yeni_rev(0, sartname_kaydi(durum="yururlukte"), sartname_kaydi(rev="1"),
                             anahtar=a)
    with pytest.raises(SartnameHatasi):              # taslak kaynak kilitlenmeden bırakılamaz
        db.sartname_yeni_rev(0, None, sartname_kaydi(rev="1"), anahtar=a)
    assert [(r["rev"], r["durum"]) for r in database.Database().get_sartname()] == [("0", "taslak")]


def test_sartname_tekilligi_veritabaninda(klasor):
    from app.itp.sartname import SartnameHatasi
    db = oturumlu(klasor)
    db.add_sartname(sartname_kaydi())
    with pytest.raises(SartnameHatasi, match="zaten var"):        # aynı kurum + ad + rev
        db.add_sartname(sartname_kaydi())
    with pytest.raises(SartnameHatasi, match="zaten var"):        # aynı aileye yeni kayıt
        db.add_sartname(sartname_kaydi(rev="1"))
    db.add_sartname(sartname_kaydi(ad="KURUM_B Özel Teknik Şartname"))
    with pytest.raises(SartnameHatasi, match="zaten var"):        # başka aileye ad değişikliği
        db.update_sartname(1, sartname_kaydi(), anahtar=db.anahtar("sartname", 1))
    with pytest.raises(SartnameHatasi, match="zaten var"):        # yeni rev'de çakışan rev
        db.sartname_yeni_rev(0, sartname_kaydi(durum="revize"), dict(sartname_kaydi(), rev_sira=1),
                             anahtar=db.anahtar("sartname", 0))
    assert [r["ad"] for r in database.Database().get_sartname()] == [
        "KURUM_B Genel Şartname", "KURUM_B Özel Teknik Şartname"]


def test_degisiklik_kaydinda_ad_yedegi_yalniz_sartnamede(klasor):
    """Doğrulama DÜŞÜK-6: no'su boş sertifikada kayıt no'su eskisi gibi boş kalır."""
    db = oturumlu(klasor)
    db.add_cert({"no": "", "ad": "Ali Kaynakçı"})
    assert db._c.execute("SELECT kayit_no FROM degisiklikler WHERE bolum = 'cert'").fetchone() \
        == ("",)


# ── İkinci doğrulama BULGU-A / A2: yeni rev'de kaynağın kimliği ve revizyon sırası ──
@pytest.mark.parametrize("eski", [
    sartname_kaydi(ad="Başka Şartname", durum="revize"),   # kaynak başka aileye taşınamaz
    sartname_kaydi(rev="1", durum="revize"),                # geçmiş rev değiştirilemez
    dict(sartname_kaydi(durum="revize"), rev_sira=5),
])
def test_yeni_rev_kaynak_kimligi_degismez(klasor, eski):
    from app.itp.sartname import SartnameHatasi
    db = oturumlu(klasor)
    db.add_sartname(sartname_kaydi())
    with pytest.raises(SartnameHatasi):
        db.sartname_yeni_rev(0, eski, dict(sartname_kaydi(rev="2"), rev_sira=1),
                             anahtar=db.anahtar("sartname", 0))
    assert [(r["ad"], r["rev"], r["durum"]) for r in database.Database().get_sartname()] == [
        ("KURUM_B Genel Şartname", "0", "taslak")]


def test_yeni_rev_sirasi_ve_en_son_revizyon(klasor):
    from app.itp.sartname import SartnameHatasi
    db = oturumlu(klasor)
    yururlukte_ekle(db)
    with pytest.raises(SartnameHatasi):                       # rev_sira kaynak + 1 olmalı
        db.sartname_yeni_rev(0, None, sartname_kaydi(rev="1"), anahtar=db.anahtar("sartname", 0))
    db.sartname_yeni_rev(0, None, dict(sartname_kaydi(rev="1"), rev_sira=1),
                         anahtar=db.anahtar("sartname", 0))
    with pytest.raises(SartnameHatasi):                       # yalnız en son revizyondan
        db.sartname_yeni_rev(0, None, dict(sartname_kaydi(rev="2"), rev_sira=1),
                             anahtar=db.anahtar("sartname", 0))
    with pytest.raises(SartnameHatasi):                       # taslakta rev_sira değişmez
        db.update_sartname(1, dict(sartname_kaydi(rev="1"), rev_sira=7),
                           anahtar=db.anahtar("sartname", 1))
    assert [(r["rev"], r["rev_sira"]) for r in database.Database().get_sartname()] == [
        ("0", 0), ("1", 1)]


def test_cok_revizyonlu_ailede_taslak_adi_degismez(klasor):
    """Kullanıcı kararı 2026-11-01: ad değişince aile bölünmesin (tek revizyonlu taslakta serbest)."""
    from app.itp.sartname import SartnameHatasi
    db = oturumlu(klasor)
    db.add_sartname(sartname_kaydi())
    db.update_sartname(0, sartname_kaydi(ad="KURUM_B Genel Şartnamesi"), anahtar=db.anahtar("sartname", 0))
    db.sartname_yeni_rev(0, sartname_kaydi(ad="KURUM_B Genel Şartnamesi", durum="revize"),
                         dict(sartname_kaydi(ad="KURUM_B Genel Şartnamesi", rev="1"), rev_sira=1),
                         anahtar=db.anahtar("sartname", 0))
    for yeni in (dict(sartname_kaydi(ad="Yeni Ad", rev="1"), rev_sira=1),
                 dict(sartname_kaydi(ad="KURUM_B Genel Şartnamesi", rev="1"), rev_sira=1, kurum="KURUM_A")):
        with pytest.raises(SartnameHatasi, match="revizyon"):
            db.update_sartname(1, yeni, anahtar=db.anahtar("sartname", 1))
    assert [r["ad"] for r in database.Database().get_sartname()] == ["KURUM_B Genel Şartnamesi"] * 2


def test_ailede_tur_degismez(klasor):
    """Kullanıcı kararı 2026-11-01: genel / özel teknik türü revizyonlar arasında değişmez."""
    from app.itp.sartname import SartnameHatasi
    db = oturumlu(klasor)
    yururlukte_ekle(db)
    with pytest.raises(SartnameHatasi, match="tür"):              # yeni rev başka türde açılamaz
        db.sartname_yeni_rev(0, None, dict(sartname_kaydi(rev="1"), rev_sira=1, tur="ozel"),
                             anahtar=db.anahtar("sartname", 0))
    db.sartname_yeni_rev(0, None, dict(sartname_kaydi(rev="1"), rev_sira=1),
                         anahtar=db.anahtar("sartname", 0))
    with pytest.raises(SartnameHatasi, match="tür"):              # çok revizyonlu ailede taslak
        db.update_sartname(1, dict(sartname_kaydi(rev="1"), rev_sira=1, tur="ozel"),
                           anahtar=db.anahtar("sartname", 1))
    db.add_sartname(sartname_kaydi(ad="Tek Revizyonlu"))           # tek revizyonlu taslakta serbest
    db.update_sartname(2, dict(sartname_kaydi(ad="Tek Revizyonlu"), tur="ozel"),
                       anahtar=db.anahtar("sartname", 2))
    assert [r["tur"] for r in database.Database().get_sartname()] == ["genel", "genel", "ozel"]


# ── Antigravity 5b-1 denetimi (2026-11-02) ──
def test_sartname_yeni_rev_kaynak_icerigi_degismez(klasor):
    """BULGU-01: taslak kaynak olduğu gibi revize olur; maddesi değiştirilerek kilitlenemez."""
    from app.itp.sartname import SartnameHatasi
    db = oturumlu(klasor)
    db.add_sartname(sartname_kaydi())
    eski = sartname_kaydi(durum="revize")
    eski["maddeler"][0]["metin"] = {"tr": "Değiştirilmiş", "en": "Changed"}
    with pytest.raises(SartnameHatasi, match="olduğu gibi"):
        db.sartname_yeni_rev(0, eski, dict(sartname_kaydi(rev="1"), rev_sira=1),
                             anahtar=db.anahtar("sartname", 0))
    assert database.Database().get_sartname()[0]["maddeler"][0]["metin"]["tr"] == "Her boru"


def test_itp_yeni_rev_kaynak_icerigi_degismez(klasor):
    """BULGU-01 (kullanıcı kararı: ITP'ye de): kaynak yalnız durum + görüntüyle kilitlenir;
    son aktarım varsa görüntü odur."""
    from app.itp.kayit import KayitHatasi
    db = oturumlu(klasor)
    son = {"__tur": "Dokuman", "x": 1}
    db.add_itp(dict(itp_kaydi(), son_aktarim=son))
    yeni = dict(itp_kaydi(rev="1"), rev_sira=1)
    for eski in (dict(itp_kaydi(durum="revize"), kalemler=["sızdırılmış"], son_aktarim=son,
                      goruntu=son),
                 dict(itp_kaydi(durum="revize"), son_aktarim=son,
                      goruntu={"__tur": "Dokuman", "x": 2})):
        with pytest.raises(KayitHatasi, match="olduğu gibi"):
            db.itp_yeni_rev(0, eski, yeni, anahtar=db.anahtar("itp", 0))
    assert [r["durum"] for r in database.Database().get_itp()] == ["taslak"]
    db.itp_yeni_rev(0, dict(itp_kaydi(durum="revize"), son_aktarim=son, goruntu=son), yeni,
                    anahtar=db.anahtar("itp", 0))
    assert [r["durum"] for r in database.Database().get_itp()] == ["revize", "taslak"]


def test_kilitli_kaynaktan_yeni_rev_surumu_islemde_denetlenir(klasor):
    """BULGU-05: kaynak zaten kilitliyken (eski None) de başka cihazdaki değişiklik yakalanır."""
    db = oturumlu(klasor)
    yururlukte_ekle(db)
    a = db.anahtar("sartname", 0)
    db._c.execute("UPDATE sartname SET surum = surum + 1 WHERE id = ?", (a[0],))
    db._c.commit()                                          # başka cihaz kaynağı değiştirdi
    with pytest.raises(database.CakismaHatasi):
        db.sartname_yeni_rev(0, None, dict(sartname_kaydi(rev="1"), rev_sira=1), anahtar=a)
    assert len(database.Database().get_sartname()) == 1


def test_5c1_sartname_sozlugu_kimlikle(klasor):
    db = oturumlu(klasor)
    kid = db.add_sartname(sartname_kaydi())
    assert db.sartname_sozlugu() == {kid: db.get_sartname()[0]}
