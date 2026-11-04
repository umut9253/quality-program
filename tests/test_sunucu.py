# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""app/sunucu.py: HTTPS tablet sunucusu — kullanıcı girişi, rol, yazma + çakışma, güvenlik.
Testler 127.0.0.1'de geçici veritabanıyla; TLS testi geçici sertifikayla (OpenSSL gerekir)."""
import http.client
import json
import os
import shutil
import ssl
import threading
import time
import urllib.request

import pytest

from app import database
from app import kimlik as K
from app import sunucu

SIFRE = "Guclu-Sifre-1"
VERI = {
    "wps": [{"no": "WPS-001", "durum": "Aktif", "pqr": "PQR-001", "proses": "SAW",
             "detay": {"kaynakci": "Ömer"}}],
    "pqr": [{"no": "PQR-001", "test": "Geçti"}],
    "std": [{"no": "API 5L", "title": "Line Pipe", "org": "API", "status": "guncel"},
            {"no": "ISO 21809-1", "title": "External coatings İmalat", "org": "ISO",
             "status": "guncelleme"}],
    "cert": [{"no": "C1", "ad": "ISO 9001", "bitis": "2000-01-01"}],
}


@pytest.fixture
def ortam(tmp_path, monkeypatch):
    """Geçici DB (VERI) + kullanıcılar + 127.0.0.1 düz HTTP sunucu (TLS ayrı testte)."""
    monkeypatch.setattr(database, "DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(database, "DATA_FILE", str(tmp_path / "data" / "data.json"))
    monkeypatch.setattr(database, "BACKUP_DIR", str(tmp_path / "yedek"))
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "data.json").write_text(json.dumps(VERI, ensure_ascii=False),
                                                 encoding="utf-8")
    db = database.Database()
    for ad, rol in (("admin", K.YONETICI), ("ali", K.DUZENLEYICI), ("ayse", K.OKUYUCU)):
        K.kullanici_ekle(db._c, ad, SIFRE, rol, yapan=None)
    srv = sunucu.kur(database.db_yolu(), "127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"127.0.0.1:{srv.server_address[1]}", db
    srv.shutdown(); srv.server_close()


def iste(adres, yontem, yol, govde=None, jeton=None, basliklar=None):
    c = http.client.HTTPConnection(adres, timeout=5)
    h = dict(basliklar or {})
    if jeton:
        h["Authorization"] = f"Bearer {jeton}"
    veri = None
    if govde is not None:
        veri = json.dumps(govde).encode("utf-8")
        h.setdefault("Content-Type", "application/json")
    c.request(yontem, yol, body=veri, headers=h)
    r = c.getresponse()
    b = r.read()
    c.close()
    try:
        icerik = json.loads(b)
    except ValueError:
        icerik = b
    return r.status, dict(r.getheaders()), icerik


def giris(adres, ad="ali"):
    s, _, g = iste(adres, "POST", "/api/giris", {"ad": ad, "sifre": SIFRE})
    assert s == 200, g
    return g["jeton"]


# ── giriş / oturum ──────────────────────────────────────────────────
def test_giris_dogru_jeton_ve_kullanici(ortam):
    adres, _ = ortam
    s, _, g = iste(adres, "POST", "/api/giris", {"ad": "ali", "sifre": SIFRE})
    assert s == 200 and len(g["jeton"]) >= 40
    assert g["kullanici"] == {"ad": "ali", "ad_soyad": "", "rol": K.DUZENLEYICI,
                              "rol_adi": "Düzenleyici", "duzenleyebilir": True}


def test_yanlis_sifre_401_ayni_mesaj(ortam):
    adres, _ = ortam
    s1, _, a = iste(adres, "POST", "/api/giris", {"ad": "ali", "sifre": "yanlis"})
    s2, _, b = iste(adres, "POST", "/api/giris", {"ad": "yok", "sifre": "yanlis"})
    assert (s1, s2) == (401, 401) and a["hata"] == b["hata"]


def test_dorduncu_hatada_429_kilit(ortam):
    adres, _ = ortam
    for _ in range(3):
        assert iste(adres, "POST", "/api/giris", {"ad": "ali", "sifre": "x"})[0] == 401
    s, _, g = iste(adres, "POST", "/api/giris", {"ad": "ali", "sifre": "x"})
    assert s == 429 and 0 < g["kalan_sn"] <= 60
    s, _, g = iste(adres, "POST", "/api/giris", {"ad": "ali", "sifre": SIFRE})
    assert s == 429                                   # kilit sürerken doğru şifre de olmaz


def test_paralel_hatali_girisler_kilitlenir(ortam):
    """Denetim YÜKSEK-1: paralel istekler kademeli kilidi atlatamamalı."""
    adres, db = ortam
    kodlar = []

    def dene():
        kodlar.append(iste(adres, "POST", "/api/giris", {"ad": "ali", "sifre": "x"})[0])

    ts = [threading.Thread(target=dene) for _ in range(12)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert sorted(kodlar) == [401] * 3 + [429] * 9
    assert db._c.execute("SELECT hatali FROM kullanicilar WHERE ad = 'ali'").fetchone()[0] == 4


def test_chunked_govde_411(ortam):
    """Antigravity BULGU-07: Content-Length'siz (chunked) gövde sessizce {} sayılıyordu."""
    adres, _ = ortam
    jeton = giris(adres)
    c = http.client.HTTPConnection(adres, timeout=5)
    c.request("POST", "/api/cert", body=iter([b'{"no": "CHUNK"}']), encode_chunked=True,
              headers={"Content-Type": "application/json", "Authorization": f"Bearer {jeton}"})
    r = c.getresponse()
    assert r.status == 411
    c.close()
    assert all(x["no"] != "CHUNK" for x in database.bolum_kayitlari(database.db_yolu(), "cert"))


def test_negatif_content_length_400(ortam):
    """Denetim ORTA-1: -1 sınırı aşıp EOF'a kadar okutuyordu."""
    adres, _ = ortam
    c = http.client.HTTPConnection(adres, timeout=5)
    c.putrequest("POST", "/api/giris")
    c.putheader("Content-Type", "application/json")
    c.putheader("Content-Length", "-1")
    c.endheaders()
    r = c.getresponse()
    assert r.status == 400
    c.close()


@pytest.mark.parametrize("jeton", [None, "uydurma-jeton"])
def test_oturumsuz_api_401(ortam, jeton):
    adres, _ = ortam
    for yol in ("/api/ozet", "/api/wps", "/api/etiketler", "/api/ben"):
        assert iste(adres, "GET", yol, jeton=jeton)[0] == 401


def test_jeton_adreste_gecmez(ortam):
    adres, _ = ortam
    j = giris(adres)
    assert iste(adres, "GET", f"/api/ozet?jeton={j}")[0] == 401


def test_cikis_oturumu_kapatir(ortam):
    adres, _ = ortam
    j = giris(adres)
    assert iste(adres, "GET", "/api/ben", jeton=j)[0] == 200
    assert iste(adres, "POST", "/api/cikis", {}, jeton=j)[0] == 200
    assert iste(adres, "GET", "/api/ben", jeton=j)[0] == 401


# ── okuma ───────────────────────────────────────────────────────────
def test_ozet(ortam):
    adres, _ = ortam
    s, _, o = iste(adres, "GET", "/api/ozet", jeton=giris(adres, "ayse"))
    assert s == 200 and o["kaynak"]["wps_toplam"] == 1 and o["dikkat"][0]["seviye"] == "kritik"


@pytest.mark.parametrize("bolum", ["wps", "pqr", "std", "cert"])
def test_liste_kimlikli(ortam, bolum):
    adres, _ = ortam
    s, _, g = iste(adres, "GET", f"/api/{bolum}", jeton=giris(adres, "ayse"))
    assert s == 200 and g["duzenleyebilir"] is False
    assert [{a: v for a, v in r.items() if not a.startswith("_")} for r in g["kayitlar"]] \
        == VERI[bolum]
    assert all(isinstance(r["_id"], int) and r["_surum"] == 0 for r in g["kayitlar"])


def test_arama_turkce_katlama(ortam):
    adres, _ = ortam
    _, _, g = iste(adres, "GET", "/api/std?q=imalat", jeton=giris(adres))
    assert [k["no"] for k in g["kayitlar"]] == ["ISO 21809-1"]


def test_etiketler_config_ile_ayni(ortam):
    from app import config as C
    adres, _ = ortam
    e = iste(adres, "GET", "/api/etiketler", jeton=giris(adres))[2]
    assert e["sutunlar"]["wps"][0] == ["WPS No", "no"]
    assert [a for _, a in e["sutunlar"]["std"]] == [k for _, k, _ in C.COLS_STD]
    assert e["secenekler"]["wps.durum"] == [[d, d] for d in C.DURUMLAR]


def test_masaustu_yazinca_tablet_hemen_gorur(ortam):
    adres, db = ortam
    db.add_wps({"no": "WPS-002", "durum": "Aktif"})
    _, _, o = iste(adres, "GET", "/api/ozet", jeton=giris(adres))
    assert o["kaynak"]["wps_toplam"] == 2


# ── yazma ───────────────────────────────────────────────────────────
def _ilk(adres, j, b="cert"):
    return iste(adres, "GET", f"/api/{b}", jeton=j)[2]["kayitlar"][0]


def test_okuyucu_yazamaz_403(ortam):
    adres, _ = ortam
    j = giris(adres, "ayse")
    r = _ilk(adres, j)
    assert iste(adres, "POST", "/api/cert", {"veri": {"no": "X"}}, jeton=j)[0] == 403
    assert iste(adres, "PUT", f"/api/cert/{r['_id']}", {"veri": r, "surum": 0}, jeton=j)[0] == 403
    assert iste(adres, "DELETE", f"/api/cert/{r['_id']}?surum=0", jeton=j)[0] == 403


def test_duzenleyici_ekler_gunceller_siler_ve_kayit_tutulur(ortam):
    adres, db = ortam
    j = giris(adres, "ali")
    s, _, g = iste(adres, "POST", "/api/cert", {"veri": {"no": "C2", "bitis": "2030-01-01"}},
                   jeton=j)
    assert s == 201
    r = _ilk(adres, j)
    s, _, g = iste(adres, "PUT", f"/api/cert/{r['_id']}",
                   {"veri": dict(r, ad="ISO 9001:2015"), "surum": r["_surum"]}, jeton=j)
    assert (s, g) == (200, {"surum": 1})
    assert iste(adres, "DELETE", f"/api/cert/{r['_id']}?surum=1", jeton=j)[0] == 200
    kayit = database.degisiklik_kayitlari(db._c)
    assert [(d["islem"], d["kullanici"], d["kaynak"]) for d in kayit] == [
        ("sil", "ali", "tablet"), ("guncelle", "ali", "tablet"), ("ekle", "ali", "tablet")]
    assert "_id" not in kayit[1]["sonra"] and kayit[1]["sonra"]["ad"] == "ISO 9001:2015"


def test_eski_surumle_yazma_409(ortam):
    adres, db = ortam
    j = giris(adres)
    r = _ilk(adres, j)
    db.update_cert(0, dict(VERI["cert"][0], ad="masaüstünde değişti"))   # araya masaüstü girer
    s, _, g = iste(adres, "PUT", f"/api/cert/{r['_id']}", {"veri": r, "surum": r["_surum"]},
                   jeton=j)
    assert s == 409 and "değiştirildi" in g["hata"]


@pytest.mark.parametrize("govde", [{"veri": "metin"}, {"veri": {"no": ""}}, {},
                                   {"veri": {"no": "X", "a": float("nan")}},
                                   # denetim ORTA-4: masaüstü alanları metin bekler
                                   {"veri": {"no": {"a": 1}}}, {"veri": {"no": "X", "tarih": 5}},
                                   {"veri": {"no": "X", "durum": ["a"]}},
                                   {"veri": {"no": "X", "detay": "metin"}}])
def test_gecersiz_govde_400(ortam, govde):
    adres, _ = ortam
    c = http.client.HTTPConnection(adres, timeout=5)
    c.request("POST", "/api/wps", body=json.dumps(govde, allow_nan=True).encode(),
              headers={"Authorization": f"Bearer {giris(adres)}",
                       "Content-Type": "application/json"})
    assert c.getresponse().status == 400


def test_json_olmayan_ve_buyuk_govde(ortam):
    adres, _ = ortam
    j = giris(adres)
    c = http.client.HTTPConnection(adres, timeout=5)
    c.request("POST", "/api/wps", body=b"no", headers={"Authorization": f"Bearer {j}",
                                                       "Content-Type": "text/plain"})
    assert c.getresponse().status == 415
    c = http.client.HTTPConnection(adres, timeout=5)
    c.putrequest("POST", "/api/wps")
    c.putheader("Authorization", f"Bearer {j}"); c.putheader("Content-Type", "application/json")
    c.putheader("Content-Length", str(sunucu.EN_FAZLA_GOVDE + 1)); c.endheaders()
    assert c.getresponse().status == 413


def test_bilinmeyen_bolum_ve_tablo_adi_enjeksiyonu_404(ortam):
    adres, _ = ortam
    j = giris(adres)
    assert iste(adres, "GET", "/api/sifre", jeton=j)[0] == 404
    assert iste(adres, "POST", "/api/wps%3B%20DROP%20TABLE%20wps", {"veri": {"no": "x"}},
                jeton=j)[0] == 404


# ── güvenlik başlıkları / statik dosyalar ───────────────────────────
def test_guvenlik_basliklari_ve_surum_gizli(ortam):
    adres, _ = ortam
    _, h, _ = iste(adres, "GET", "/")
    assert h["X-Content-Type-Options"] == "nosniff" and h["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in h["Content-Security-Policy"]
    assert "Python" not in h["Server"] and "Access-Control-Allow-Origin" not in h


def test_arayuz_girissiz_sunulur(ortam):
    adres, _ = ortam
    s, h, g = iste(adres, "GET", "/")
    assert s == 200 and "text/html" in h["Content-Type"] and b"<html" in g.lower()
    assert iste(adres, "GET", "/app.js")[0] == 200


@pytest.mark.parametrize("yol", ["/..%2f..%2fdata.json", "/%5c%5chost%5cpaylasim%5cx",
                                 "/C:/Windows/win.ini", "/..%5c..%5cdata.json",
                                 "//host/paylasim/x", "/a%3ab", "/kalite.db"])
def test_arayuz_yol_kacisi_dosya_sistemine_dokunmadan_404(ortam, monkeypatch, yol):
    adres, _ = ortam
    cagri = []
    monkeypatch.setattr(sunucu.os.path, "realpath", lambda p, *a, **k: cagri.append(p) or p)
    assert iste(adres, "GET", yol)[0] == 404 and cagri == []


def test_apk_indirme(ortam, tmp_path, monkeypatch):
    adres, _ = ortam
    apk = tmp_path / "KaliteYS.apk"
    monkeypatch.setattr(sunucu, "APK_YOLU", str(apk))
    assert iste(adres, "GET", "/indir/KaliteYS.apk")[0] == 404
    apk.write_bytes(b"PK-apk")
    s, h, g = iste(adres, "GET", "/indir/KaliteYS.apk")
    assert s == 200 and h["Content-Type"] == "application/vnd.android.package-archive"


def test_veritabani_yoksa_anlamli_500(tmp_path):
    srv = sunucu.kur(str(tmp_path / "yok.db"), "127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        s, _, g = iste(f"127.0.0.1:{srv.server_address[1]}", "POST", "/api/giris",
                       {"ad": "a", "sifre": "b"})
        assert s == 500 and "masaüstü programı" in g["hata"]
        assert "yok.db" not in g["hata"]       # denetim DÜŞÜK-1: dosya yolu dışarı sızmaz
    finally:
        srv.shutdown(); srv.server_close()


def test_istemci_baglantiyi_kesince_traceback_basilmaz(ortam, capsys):
    import socket
    import struct
    adres, _ = ortam
    host, port = adres.split(":")
    for _ in range(3):
        s = socket.create_connection((host, int(port)))
        s.sendall(b"GET /app.js HTTP/1.1\r\nHost: x\r\n\r\n")
        s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        s.close()                                           # RST: yanıt yazılırken kopar
    time.sleep(0.5)
    assert "Traceback" not in capsys.readouterr().err


# ── HTTPS ───────────────────────────────────────────────────────────
@pytest.mark.skipif(not (shutil.which("openssl") or os.path.exists(
    r"C:\Program Files\Git\usr\bin\openssl.exe")), reason="OpenSSL yok")
@pytest.mark.filterwarnings("ignore::DeprecationWarning")   # TLS 1.0/1.1 bilerek deneniyor
def test_https_sertifika_ve_parmak_izi(ortam, tmp_path, capsys):
    crt, key = sunucu.sertifika_hazirla(str(tmp_path / "tls"))
    assert sunucu.sertifika_hazirla(str(tmp_path / "tls")) == (crt, key)   # ikinci kez üretmez
    assert len(sunucu.parmak_izi(crt)) == 64
    srv = sunucu.kur(database.db_yolu(), "127.0.0.1", 0, tls=(crt, key))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    try:
        ctx = ssl.create_default_context(cafile=crt)          # yalnız bu sertifikaya güven
        c = http.client.HTTPSConnection("127.0.0.1", port, context=ctx, timeout=5)
        c.connect()
        assert c.sock.version() in ("TLSv1.2", "TLSv1.3")
        c.request("POST", "/api/giris", body=json.dumps({"ad": "ali", "sifre": SIFRE}),
                  headers={"Content-Type": "application/json"})
        r = c.getresponse()
        assert r.status == 200
        with pytest.raises(Exception):                        # düz HTTP konuşulamaz
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=3)
        eski = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        eski.check_hostname = False
        eski.verify_mode = ssl.CERT_NONE
        eski.minimum_version = ssl.TLSVersion.TLSv1
        eski.maximum_version = ssl.TLSVersion.TLSv1_1
        with pytest.raises((ssl.SSLError, OSError)):          # TLS 1.1 reddedilir
            http.client.HTTPSConnection("127.0.0.1", port, context=eski,
                                        timeout=3).request("GET", "/")
        time.sleep(0.3)
        assert "Traceback" not in capsys.readouterr().err
    finally:
        srv.shutdown(); srv.server_close()
