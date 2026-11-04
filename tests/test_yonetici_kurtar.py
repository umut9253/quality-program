# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""tools/yonetici_kurtar.py: bu bilgisayarda yönetici kilidini açma / şifre sıfırlama."""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import yonetici_kurtar as Y  # noqa: E402

from app import kimlik as K  # noqa: E402

SIFRE = "Guclu-Sifre-1"


@pytest.fixture
def c():
    c = sqlite3.connect(":memory:")
    K.sema_kur(c)
    K.kullanici_ekle(c, "admin", SIFRE, K.YONETICI, yapan=None)
    K.kullanici_ekle(c, "ali", SIFRE, K.DUZENLEYICI, yapan="admin")
    c.execute("UPDATE kullanicilar SET hatali = 9, kalici_kilit = 1, aktif = 0 WHERE ad = 'admin'")
    c.commit()
    return c


def test_yalniz_yoneticiler_listelenir(c):
    assert [y["ad"] for y in Y.yoneticiler(c)] == ["admin"]


def test_kilit_acar_etkinlestirir_ve_kaydeder(c):
    Y.kurtar(c, "admin")
    assert K.giris(c, "admin", SIFRE).ad == "admin"
    olay = c.execute("SELECT olay, yapan FROM guvenlik WHERE olay = 'kurtarma'").fetchone()
    assert olay == ("kurtarma", Y.YAPAN)


def test_sifre_sifirlar(c):
    Y.kurtar(c, "admin", yeni_sifre="Yeni-Sifre-22")
    with pytest.raises(K.GirisHatasi):
        K.giris(c, "admin", SIFRE)
    assert K.giris(c, "admin", "Yeni-Sifre-22").ad == "admin"


def test_yonetici_olmayan_kurtarilamaz(c):
    with pytest.raises(K.KimlikHatasi):
        Y.kurtar(c, "ali")


def test_eski_semada_hicbir_sey_degistirmeden_cikar(tmp_path, monkeypatch):
    """Şema 2 dosyada cihaz_hata yok: kilit_ac yarıda düşer, önceki adımlar kaydedilmiş
    kalırdı (doğrulama ajanı, 2026-10-31). Araç yükseltilmemiş dosyaya hiç dokunmamalı."""
    yol = tmp_path / "kalite.db"
    c = sqlite3.connect(yol)
    K.sema_kur(c)
    K.kullanici_ekle(c, "admin", SIFRE, K.YONETICI, yapan=None)
    c.execute("DROP TABLE cihaz_hata")
    c.execute("PRAGMA user_version = 2")
    c.commit()
    once = c.execute("SELECT * FROM kullanicilar").fetchall()
    c.close()
    monkeypatch.setattr(Y.database, "db_yolu", lambda: str(yol))
    monkeypatch.setattr("builtins.input", lambda *_: "1")
    with pytest.raises(SystemExit, match="masaüstü programı"):
        Y.main()
    c = sqlite3.connect(yol)
    assert c.execute("SELECT * FROM kullanicilar").fetchall() == once
