# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Firma kimliği (ad + logo): `ayarlar` tablosu, şema 6 (spec 2026-11-02 F1, F4)."""
import hashlib
import json
import sqlite3

import pytest

from app import database, firma
from app import kimlik as KM

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
SIFRE = "Guclu-Sifre-1"


@pytest.fixture
def klasor(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(database, "DATA_FILE", str(tmp_path / "data" / "data.json"))
    monkeypatch.setattr(database, "BACKUP_DIR", str(tmp_path / "yedek"))
    return tmp_path


def oturumlu(rol):
    db = database.Database()
    KM.kullanici_ekle(db._c, "ali", SIFRE, rol, yapan=None)
    db.kullanici = KM.giris(db._c, "ali", SIFRE)
    return db


def test_bos_veritabaninda_firma_yok(klasor):
    assert database.Database().firma() == firma.Firma("", None)


def test_kaydet_ve_oku(klasor):
    db = oturumlu(KM.YONETICI)
    db.firma_kaydet("  ÖRNEK FİRMA ", PNG, beklenen=db.firma())
    assert db.firma() == firma.Firma("ÖRNEK FİRMA", PNG)
    db.firma_kaydet("ÖRNEK FİRMA", None, beklenen=db.firma())      # logoyu kaldır
    assert database.Database().firma() == firma.Firma("ÖRNEK FİRMA", None)


def test_degisiklik_kaydi_logo_baytini_yazmaz(klasor):
    db = oturumlu(KM.YONETICI)
    db.firma_kaydet("A", JPEG, beklenen=db.firma())
    bolum, no, once, sonra = db._c.execute(
        "SELECT bolum, kayit_no, once, sonra FROM degisiklikler WHERE bolum = 'ayarlar'"
    ).fetchone()
    assert (bolum, no) == ("ayarlar", "Firma bilgileri")
    assert json.loads(once) == {"firma_adi": "", "firma_logo": None}
    assert json.loads(sonra) == {"firma_adi": "A", "firma_logo": {
        "bayt": len(JPEG), "sha256": hashlib.sha256(JPEG).hexdigest()}}


def test_degismeyen_kayit_kayda_gecmez(klasor):
    db = oturumlu(KM.YONETICI)
    db.firma_kaydet("A", None, beklenen=db.firma())
    db.firma_kaydet("A", None, beklenen=db.firma())
    assert db._c.execute("SELECT COUNT(*) FROM degisiklikler WHERE bolum = 'ayarlar'"
                         ).fetchone()[0] == 1


@pytest.mark.parametrize("rol", [KM.DUZENLEYICI, KM.OKUYUCU])
def test_yalniz_yonetici_yazar(klasor, rol):
    db = oturumlu(rol)
    with pytest.raises(database.YetkiHatasi):
        db.firma_kaydet("A", None, beklenen=db.firma())
    assert db.firma() == firma.Firma("", None)


def test_eszamanli_degisiklik_cakisma(klasor):
    db = oturumlu(KM.YONETICI)
    eski = db.firma()
    db.firma_kaydet("A", None, beklenen=eski)
    with pytest.raises(database.CakismaHatasi):
        db.firma_kaydet("B", None, beklenen=eski)
    assert db.firma().ad == "A"


@pytest.mark.parametrize("veri, mesaj", [(b"GIF89a" + b"\x00" * 10, "PNG ya da JPEG"),
                                         (PNG + b"\x00" * firma.LOGO_EN_BUYUK, "en çok")],
                         ids=["gif", "buyuk"])
def test_gecersiz_logo(klasor, veri, mesaj):
    db = oturumlu(KM.YONETICI)
    with pytest.raises(ValueError, match=mesaj):
        db.firma_kaydet("A", veri, beklenen=db.firma())
    assert db.firma() == firma.Firma("", None)


def test_logo_turu():
    assert firma.logo_turu(PNG) == "png" and firma.logo_turu(JPEG) == "jpeg"


@pytest.mark.parametrize("ad", ["", "   ", None])
def test_ad_dogrula_bos(ad):
    with pytest.raises(ValueError, match="Firma adı ayarlanmamış"):
        firma.ad_dogrula(ad)


def test_sema5_dosyasi_yukseltilir(klasor):
    database.Database()._c.close()
    yol = klasor / "data" / "kalite.db"
    with sqlite3.connect(yol) as c:
        c.execute("DROP TABLE ayarlar")
        c.execute("PRAGMA user_version = 5")
    db = database.Database()
    assert db._c.execute("PRAGMA user_version").fetchone()[0] == database.SEMA_SURUMU
    assert db.firma() == firma.Firma("", None)
    assert len(list((klasor / "yedek").glob("kalite_SEMA5_YEDEK_*.db"))) == 1
