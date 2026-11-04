# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Tablet sunucusu: bu bilgisayardaki ana veritabanını (data/kalite.db, SQLite) yerel ağa
HTTPS üzerinden açar ve tablet arayüzünü (tablet/web/) sunar.

Çalıştırma (QUALITY PROGRAM kökünden): `python -m app.sunucu`
- HTTPS (TLS ≥ 1.2): sertifika ilk çalıştırmada data/tls/ altında üretilir (Git ile gelen
  OpenSSL); APK yalnız bu sertifikaya güvenir (parmak izi derlemede gömülür).
- Kimlik: POST /api/giris (kullanıcı adı + şifre, app/kimlik.py; kademeli kilit cihaz+hesap)
  → oturum jetonu; diğer tüm /api istekleri `Authorization: Bearer <jeton>` ister.
- Yazma: POST /api/{bölüm}, PUT/DELETE /api/{bölüm}/{id} — en az Düzenleyici rolü; her
  yazma değişiklik kaydıyla tek işlemde; eski sürümle yazma 409 (iyimser kilit).
- Arayüz dosyaları (HTML/JS/CSS) veri içermez, girişsiz sunulur (beyaz liste).
"""
import hashlib
import json
import mimetypes
import os
import re
import shutil
import socket
import ssl
import subprocess
import sys
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from . import config as C
from . import database
from . import kimlik
from .ozet import ozet
from .search_utils import matches_query

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARAYUZ = os.path.join(KOK, "tablet", "web")
APK_YOLU = os.path.join(KOK, "tablet", "android", "cikti", "KaliteYS.apk")   # tools/apk_derle.py
TLS_KLASOR = os.path.join(KOK, "data", "tls")                     # git dışı
PORT = 8765
EN_FAZLA_GOVDE = 1_000_000          # bayt; daha büyük istek 413
ISTEK_ZAMAN_ASIMI = 20              # sn; el sıkışma + istek okuma
BOLUMLER = ("wps", "pqr", "std", "cert")
DOSYA_ADI = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*")   # tablet/web/ içindeki dosya adları
# bölüm → aramada bakılan alanlar
ARAMA_ALANLARI = {
    "wps": ("no", "proses", "metal", "dolgu", "pqr", "durum"),
    "pqr": ("no", "proses", "metal", "dolgu", "lab", "test"),
    "std": ("no", "title", "org"),
    "cert": ("no", "ad", "org", "kapsam", "folder_no"),
}
STD_DURUMLARI = [["guncel", "Güncel"], ["guncelleme", "Güncelleme var"],
                 ["manuel", "Manuel kontrol"], ["hata", "Kontrol hatası"],
                 ["kontrol", "Kontrol edilmedi"]]
# "_" ile başlayan sütunlar masaüstünde hesaplanır (Bağlı WPS, Kalan, Durum); tablet kendi
# hesaplar ya da göstermez
ETIKETLER = {
    "sutunlar": {b: [[baslik, a] for baslik, a, _ in sutunlar]
                 for b, sutunlar in (("wps", C.COLS_WPS), ("pqr", C.COLS_PQR),
                                     ("std", C.COLS_STD), ("cert", C.COLS_CERT))},
    "detay": dict(C.DETAIL_LABELS, title="Başlık", org="Kuruluş", myVer="Elimdeki Sürüm",
                  lastVer="Son Sürüm", manualLastVer="Son Sürüm (elle)",
                  lastCheck="Son Kontrol", status="Durum", ad="Sertifika / Standart",
                  kapsam="Kapsam", bitis="Bitiş", folder_no="Klasör No", notlar="Notlar"),
    "uyari_gun": C.CERT_UYARI_GUN,
    # düzenleme formunda seçim listeleri: "bölüm.alan" → [[değer, etiket]...] (masaüstüyle aynı)
    "secenekler": {
        "wps.durum": [[d, d] for d in C.DURUMLAR],
        "wps.proses": [[p, p] for p in C.PROSESLER],
        "wps.pozisyon": [[p, p] for p in C.POZISYONLAR],
        "pqr.test": [[t, t] for t in C.TEST_SEC],
        "pqr.proses": [[p, p] for p in C.PROSESLER],
        "std.status": STD_DURUMLARI,
    },
    "tarih_alanlari": ["tarih", "bitis", "lastCheck"],
}
OKUNAMADI = "Veritabanı okunamadı; ayrıntı sunucu penceresinde."
# Girişler sırayla işlenir: her deneme scrypt ile ~16 MB bellek ister; paralel giriş seli
# sunucuyu tüketemez (kilit doğruluğu ayrıca kimlik.giris içinde işlemle sağlanır).
_GIRIS_SIRASI = threading.Lock()
# Masaüstü alanları metin bekler; iç içe nesne yalnız bu anahtarlarda (WPS/PQR ayrıntı, şema).
IC_ICE = ("detay", "diagram")
GUVENLIK_BASLIKLARI = (
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    ("Referrer-Policy", "no-referrer"),
    ("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; "
                                "img-src 'self' data:; frame-ancestors 'none'; form-action 'none'"),
    ("Cache-Control", "no-store"),
)


class _IstekHatasi(Exception):
    def __init__(self, kod, mesaj):
        super().__init__(mesaj)
        self.kod = kod


def _isleyici():
    class Isleyici(BaseHTTPRequestHandler):
        server_version = "KaliteYS"   # sürüm bilgisi sızdırma
        sys_version = ""
        timeout = ISTEK_ZAMAN_ASIMI

        def log_message(self, *a):   # konsolu her istekte doldurma
            pass

        # ── yanıt ───────────────────────────────────────────────────
        def _gonder(self, kod, govde, tur):
            try:
                self.send_response(kod)
                self.send_header("Content-Type", tur)
                self.send_header("Content-Length", str(len(govde)))
                for ad, deger in GUVENLIK_BASLIKLARI:
                    self.send_header(ad, deger)
                self.end_headers()
                self.wfile.write(govde)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass   # tablet bağlantıyı erken kapattı (sayfa yenileme vb.): sessiz geç

        def _json(self, kod, nesne):
            self._gonder(kod, json.dumps(nesne, ensure_ascii=False).encode("utf-8"),
                         "application/json; charset=utf-8")

        # ── istek ───────────────────────────────────────────────────
        def _govde(self):
            if self.headers.get("Transfer-Encoding"):   # chunked gövde okunmaz: {} sayılmasın
                raise _IstekHatasi(411, "Content-Length gerekli.")
            try:
                uzunluk = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise _IstekHatasi(400, "Geçersiz Content-Length.")
            if uzunluk < 0:
                raise _IstekHatasi(400, "Geçersiz Content-Length.")
            if uzunluk > EN_FAZLA_GOVDE:
                raise _IstekHatasi(413, "İstek çok büyük.")
            if not (self.headers.get("Content-Type") or "").startswith("application/json"):
                raise _IstekHatasi(415, "İstek JSON olmalı (Content-Type: application/json).")
            try:
                g = json.loads(self.rfile.read(uzunluk) or b"{}")
            except (ValueError, UnicodeDecodeError):
                raise _IstekHatasi(400, "Geçersiz JSON.")
            if not isinstance(g, dict):
                raise _IstekHatasi(400, "İstek gövdesi bir nesne olmalı.")
            return g

        def _jeton(self):
            a = self.headers.get("Authorization", "")
            return a[7:].strip() if a.startswith("Bearer ") else ""

        def do_GET(self):
            u = urlparse(self.path)
            if u.path.startswith("/api/"):
                return self._api("GET", u)
            if u.path == "/indir/KaliteYS.apk":   # tablete kurulum: tarayıcıdan indirilir
                return self._apk()
            self._dosya(unquote(u.path))

        def do_POST(self):
            self._api("POST", urlparse(self.path))

        def do_PUT(self):
            self._api("PUT", urlparse(self.path))

        def do_DELETE(self):
            self._api("DELETE", urlparse(self.path))

        # ── API ─────────────────────────────────────────────────────
        def _api(self, yontem, u):
            yol = self.server.veri_yolu
            if not u.path.startswith("/api/"):
                return self._json(404, {"hata": "bilinmeyen adres"})
            if not os.path.exists(yol):
                return self._json(500, {"hata": "Veritabanı bulunamadı — önce masaüstü "
                                                "programı açın."})
            try:
                c = database._baglan(yol)
            except Exception as e:
                print(f"Veritabanı açılamadı: {e}", file=sys.stderr)
                return self._json(500, {"hata": OKUNAMADI})
            try:
                kod, nesne = self._yonlendir(c, yontem, u)
            except _IstekHatasi as e:
                kod, nesne = e.kod, {"hata": str(e)}
            except database.CakismaHatasi as e:
                kod, nesne = 409, {"hata": str(e)}
            except database.YetkiHatasi as e:
                kod, nesne = 403, {"hata": str(e)}
            except database.VeritabaniHatasi as e:
                kod, nesne = 400, {"hata": str(e)}
            except Exception as e:   # DB kilitli/bozuk vb.: ayrıntı konsolda, tablete genel mesaj
                print(f"Veritabanı hatası: {e!r}", file=sys.stderr)
                kod, nesne = 500, {"hata": OKUNAMADI}
            finally:
                c.close()
            self._json(kod, nesne)

        def _yonlendir(self, c, yontem, u):
            parca = [p for p in u.path[len("/api/"):].split("/") if p]
            ip = self.client_address[0]
            if parca == ["giris"]:
                if yontem != "POST":
                    raise _IstekHatasi(405, "Giriş için POST kullanın.")
                g = self._govde()
                try:
                    with _GIRIS_SIRASI:
                        k = kimlik.giris(c, str(g.get("ad", "")), str(g.get("sifre", "")), ip=ip)
                except kimlik.GirisHatasi as e:
                    kilitli = e.kalan_sn is None or e.kalan_sn > 0
                    return (429 if kilitli else 401), {"hata": str(e), "kalan_sn": e.kalan_sn}
                jeton = kimlik.oturum_ac(c, k, cihaz=f"tablet {ip}")
                return 200, {"jeton": jeton, "kullanici": _kullanici_json(k)}

            k = kimlik.oturum_dogrula(c, self._jeton())
            if k is None:
                return 401, {"hata": "Oturum yok ya da süresi doldu; yeniden giriş yapın."}
            if parca == ["cikis"] and yontem == "POST":
                kimlik.oturum_kapat(c, self._jeton())
                return 200, {"tamam": True}
            if yontem == "GET" and parca == ["ben"]:
                return 200, _kullanici_json(k)
            if yontem == "GET" and parca == ["etiketler"]:
                return 200, ETIKETLER
            if yontem == "GET" and parca == ["ozet"]:
                veri = database.tum_veri(self.server.veri_yolu)
                return 200, ozet(*(veri.get(b, []) for b in BOLUMLER), bugun=date.today(),
                                 uyari_gun=C.CERT_UYARI_GUN)
            if not parca or parca[0] not in BOLUMLER:
                raise _IstekHatasi(404, "bilinmeyen adres")
            b = parca[0]
            if len(parca) == 1 and yontem == "GET":
                q = parse_qs(u.query).get("q", [""])[0]
                kayitlar = [r for r in database.bolum_kayitlari(self.server.veri_yolu, b)
                            if matches_query(q, *(str(r.get(a) or "")
                                                  for a in ARAMA_ALANLARI[b]))]
                return 200, {"kayitlar": kayitlar,
                             "duzenleyebilir": kimlik.yetkili(k.rol, kimlik.DUZENLEYICI)}
            if not kimlik.yetkili(k.rol, kimlik.DUZENLEYICI):
                raise database.YetkiHatasi(f"'{k.ad}' kullanıcısının rolü "
                                           f"({kimlik.ROL_ADI[k.rol]}) kayıt değiştirmeye yetmiyor.")
            if len(parca) == 1 and yontem == "POST":
                veri = _veri(self._govde())
                return 201, {"id": database.kayit_ekle(c, b, veri, k.ad, "tablet")}
            if len(parca) == 2 and parca[1].isdigit():
                kid = int(parca[1])
                if yontem == "PUT":
                    g = self._govde()
                    surum = _surum(g.get("surum"))
                    return 200, {"surum": database.kayit_guncelle(c, b, kid, _veri(g), surum,
                                                                  k.ad, "tablet")}
                if yontem == "DELETE":
                    surum = _surum(parse_qs(u.query).get("surum", [None])[0])
                    database.kayit_sil(c, b, kid, surum, k.ad, "tablet")
                    return 200, {"tamam": True}
            raise _IstekHatasi(404, "bilinmeyen adres")

        # ── dosyalar ────────────────────────────────────────────────
        def _apk(self):
            if not os.path.isfile(APK_YOLU):
                return self._gonder(404, "APK henüz derlenmedi: python tools/apk_derle.py"
                                    .encode("utf-8"), "text/plain; charset=utf-8")
            with open(APK_YOLU, "rb") as f:
                self._gonder(200, f.read(), "application/vnd.android.package-archive")

        def _dosya(self, yol):
            ad = "index.html" if yol in ("", "/") else yol[1:]
            # Beyaz liste: tablet/web/ düz klasör; ad yalnız [A-Za-z0-9_.-], noktayla başlamaz.
            # Böylece "\\host\pay" (UNC → SMB/NTLM), "C:/..", "..\" dosya sistemine hiç sorulmaz
            tam = os.path.join(ARAYUZ, ad)
            if not DOSYA_ADI.fullmatch(ad) or not os.path.isfile(tam):
                return self._gonder(404, b"bulunamadi", "text/plain; charset=utf-8")
            tur = mimetypes.guess_type(tam)[0] or "application/octet-stream"
            if tur.startswith("text/") or tur.endswith("javascript"):
                tur += "; charset=utf-8"
            with open(tam, "rb") as f:
                self._gonder(200, f.read(), tur)

    return Isleyici


def _kullanici_json(k):
    return {"ad": k.ad, "ad_soyad": k.ad_soyad, "rol": k.rol, "rol_adi": kimlik.ROL_ADI[k.rol],
            "duzenleyebilir": kimlik.yetkili(k.rol, kimlik.DUZENLEYICI)}


def _veri(g):
    v = g.get("veri")
    if not isinstance(v, dict):
        raise _IstekHatasi(400, "'veri' alanı bir nesne olmalı.")
    v = {a: d for a, d in v.items() if not str(a).startswith("_")}   # _id/_surum meta değil
    for a, d in v.items():
        if not (isinstance(d, dict) if a in IC_ICE else (d is None or isinstance(d, str))):
            raise _IstekHatasi(400, f"'{a}' alanı geçersiz türde.")
    if not (v.get("no") or "").strip():
        raise _IstekHatasi(400, "Kayıt numarası (No) boş olamaz.")
    return v


def _surum(s):
    try:
        return int(s)
    except (TypeError, ValueError):
        raise _IstekHatasi(400, "Kayıt sürümü (surum) eksik ya da geçersiz.")


class _Sunucu(ThreadingHTTPServer):
    daemon_threads = True
    tls = None          # ssl.SSLContext; None = düz HTTP (yalnız testler)
    veri_yolu = None

    def finish_request(self, request, client_address):
        # TLS el sıkışması bağlantının kendi iş parçacığında ve süre sınırıyla: yavaş/kötü
        # niyetli tek bağlantı kabul döngüsünü (diğer tabletleri) bekletemez
        request.settimeout(ISTEK_ZAMAN_ASIMI)
        if self.tls is not None:
            request = self.tls.wrap_socket(request, server_side=True)
        super().finish_request(request, client_address)

    def handle_error(self, request, client_address):
        # Tablet bağlantıyı erken kapattı (yenileme, uyku), TLS'siz/bozuk el sıkışma, zaman
        # aşımı: konsola traceback basma (Antigravity BULGU-05); diğer hatalar raporlanır
        if isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError,
                                          ConnectionAbortedError, ssl.SSLError,
                                          socket.timeout)):
            return
        super().handle_error(request, client_address)


def tls_baglami(crt, key):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(crt, key)
    return ctx


def kur(veri_yolu=None, ev="0.0.0.0", port=PORT, tls=None):
    """Başlatılmamış sunucu (serve_forever çağıran başlatır). tls: (crt, key) yolları."""
    srv = _Sunucu((ev, port), _isleyici())
    srv.veri_yolu = veri_yolu or database.db_yolu()
    if tls:
        srv.tls = tls_baglami(*tls)
    return srv


# ── sertifika ───────────────────────────────────────────────────────
def _openssl():
    adaylar = [shutil.which("openssl")] + [
        os.path.join(os.environ.get(k, ""), "Git", alt, "openssl.exe")
        for k in ("ProgramFiles", "ProgramW6432", "LOCALAPPDATA")
        for alt in (r"usr\bin", r"mingw64\bin", r"ucrt64\bin")]
    for a in adaylar:
        if a and os.path.isfile(a):
            return a
    raise SystemExit("HATA: OpenSSL bulunamadı (Git for Windows ile gelir). Sertifika "
                     "üretilemedi; HTTPS olmadan sunucu başlatılmaz.")


def sertifika_hazirla(klasor=TLS_KLASOR):
    """data/tls/sunucu.crt + sunucu.key (yoksa üretir: EC P-256, 10 yıl). Döner: (crt, key)."""
    crt, key = os.path.join(klasor, "sunucu.crt"), os.path.join(klasor, "sunucu.key")
    if os.path.isfile(crt) and os.path.isfile(key):
        return crt, key
    os.makedirs(klasor, exist_ok=True)
    subprocess.run([_openssl(), "req", "-x509", "-newkey", "ec", "-pkeyopt",
                    "ec_paramgen_curve:prime256v1", "-nodes", "-days", "3650",
                    "-subj", "/CN=Kalite YS tablet sunucusu",
                    "-addext", f"subjectAltName=IP:{yerel_ip()},IP:127.0.0.1,DNS:localhost",
                    "-keyout", key, "-out", crt],
                   check=True, capture_output=True)
    return crt, key


def parmak_izi(crt):
    """Sertifikanın SHA-256 parmak izi (DER; küçük harf onaltılı) — APK buna sabitlenir."""
    with open(crt, encoding="ascii") as f:
        return hashlib.sha256(ssl.PEM_cert_to_DER_cert(f.read())).hexdigest()


def yerel_ip():
    """Tabletin bağlanacağı yerel ağ adresi (internete paket gitmez; UDP connect yalnız
    yönlendirme tablosundan arayüz seçer)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def main():
    # Şema yükseltmesi (1/2 → 3, önce yedek) ve kullanıcı kontrolü: masaüstü hiç açılmadan
    # sunucu başlatılırsa kimlik tabloları olmazdı
    try:
        db = database.Database()
    except database.VeritabaniHatasi as e:
        raise SystemExit(f"HATA: {e}")
    kurulum = kimlik.kurulum_gerekli(db._c)
    db._c.close()
    if kurulum:
        raise SystemExit("HATA: Henüz kullanıcı yok. Önce masaüstü programını açıp yönetici "
                         "hesabını oluşturun, tablet kullanıcılarını Kullanıcılar sayfasından ekleyin.")
    crt, key = sertifika_hazirla()
    srv = kur(tls=(crt, key))
    iz = parmak_izi(crt)
    print("Kalite Yönetim Sistemi — tablet sunucusu (HTTPS)")
    print(f"  Tablette sunucu adresi : https://{yerel_ip()}:{PORT}")
    print(f"  Sertifika parmak izi   : {iz[:16]}…{iz[-16:]}")
    print(f"  Veri                   : {database.db_yolu()}")
    print("  Tablette kendi kullanıcı adınız ve şifrenizle giriş yapın.")
    print("Durdurmak için Ctrl+C")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
