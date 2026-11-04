# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Kimlik ve yetki (2026-10-30): kullanıcılar, şifre özeti, kademeli kilit, oturumlar,
güvenlik kaydı. Qt'siz; masaüstü ve tablet sunucusu aynı kodu kullanır (tablolar kalite.db'de).

- Şifre: scrypt (n=2^14, r=8, p=1) + 16 bayt tuz; düz metin hiçbir yerde saklanmaz.
- Kilit (kullanıcı ve — yalnız ağdan girişte — cihaz/IP ayrı ayrı): ardışık ilk 3 hata serbest; 4. hata 1 dk,
  sonraki hatalar 5, 15, 60 dk; kullanıcıda bir sonraki hata KALICI kilit (yalnız yönetici
  açar). Cihazda en fazla 60 dk (kalıcı değil). Kilit sürerken denemeler kademeyi artırmaz.
- Cihaz sayacı (V-7-15): hatalar hesap adına göre tutulur; başarılı giriş yalnız O HESABIN
  hatalarını düşer (başka hesaplara deneyip kendi hesabıyla girerek sıfırlama yok). Son
  hatadan 60 dk sonra cihaz sayacı kendiliğinden sıfırlanır (ortak tablette hatalar birikmesin).
- Bilinmeyen kullanıcı ile yanlış şifre aynı mesajı ve aynı süreyi alır (ad tahmini yok).
- Oturum: rastgele jeton (yalnız SHA-256 özeti saklanır), 12 saat.
"""
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass

from .dil import N_, DILLER, _
from .search_utils import tr_fold

YONETICI, DUZENLEYICI, OKUYUCU = "yonetici", "duzenleyici", "okuyucu"
ROLLER = (YONETICI, DUZENLEYICI, OKUYUCU)
YEREL = "yerel"   # masaüstü girişi: cihaz kilidi uygulanmaz (aynı bilgisayarı herkes paylaşır)
ROL_ADI = {YONETICI: N_("Yönetici"), DUZENLEYICI: N_("Düzenleyici"), OKUYUCU: N_("Okuyucu")}
_ROL_SIRA = {OKUYUCU: 0, DUZENLEYICI: 1, YONETICI: 2}

ILK_SERBEST_HATA = 3
KILIT_SURELERI = (60, 300, 900, 3600)          # sn: 1, 5, 15, 60 dk
CIHAZ_SAYAC_OMRU = 3600                        # sn: son hatadan sonra cihaz sayacı sıfırlanır
OTURUM_SURESI = 12 * 3600
BOS_KILIT_SN = 5 * 60                          # masaüstü: hareketsizlikte ekran kilidi
EN_AZ_SIFRE = 8
_SCRYPT = dict(n=2 ** 14, r=8, p=1, dklen=32)


class KimlikHatasi(Exception):
    """Kullanıcı yönetimi hatası (zayıf şifre, var olan ad, son yönetici...)."""


class GirisHatasi(KimlikHatasi):
    """Giriş reddedildi. kalan_sn: kilit varsa kalan süre (kalıcı kilitte None)."""

    def __init__(self, mesaj, kalan_sn=0):
        super().__init__(mesaj)
        self.kalan_sn = kalan_sn


@dataclass(frozen=True)
class Kullanici:
    id: int
    ad: str
    ad_soyad: str
    rol: str


def sema_kur(c):
    """Tabloları kurar (CREATE IF NOT EXISTS). Commit etmez: şema yükseltmesi tek işlem kalsın
    (executescript açık işlemi kendiliğinden commit ederdi)."""
    for sql in (
        "CREATE TABLE IF NOT EXISTS kullanicilar (id INTEGER PRIMARY KEY, ad TEXT NOT NULL UNIQUE, "
        "ad_soyad TEXT NOT NULL DEFAULT '', rol TEXT NOT NULL, sifre_ozet TEXT NOT NULL, "
        "aktif INTEGER NOT NULL DEFAULT 1, hatali INTEGER NOT NULL DEFAULT 0, kilit_bitis REAL, "
        "kalici_kilit INTEGER NOT NULL DEFAULT 0, olusturma REAL NOT NULL, "
        "dil TEXT NOT NULL DEFAULT 'tr')",
        "CREATE TABLE IF NOT EXISTS cihaz_kilit (ip TEXT PRIMARY KEY, hatali INTEGER NOT NULL "
        "DEFAULT 0, kilit_bitis REAL, son_ad TEXT NOT NULL DEFAULT '')",
        "CREATE TABLE IF NOT EXISTS cihaz_hata (ip TEXT NOT NULL, ad TEXT NOT NULL, "
        "adet INTEGER NOT NULL, son REAL NOT NULL, PRIMARY KEY (ip, ad))",
        "CREATE TABLE IF NOT EXISTS oturumlar (jeton_ozet TEXT PRIMARY KEY, kullanici_id INTEGER "
        "NOT NULL, cihaz TEXT NOT NULL, olusturma REAL NOT NULL, bitis REAL NOT NULL)",
        "CREATE TABLE IF NOT EXISTS guvenlik (id INTEGER PRIMARY KEY, zaman REAL NOT NULL, "
        "olay TEXT NOT NULL, kullanici TEXT NOT NULL DEFAULT '', ip TEXT NOT NULL DEFAULT '', "
        "yapan TEXT NOT NULL DEFAULT '', ayrinti TEXT NOT NULL DEFAULT '')",
    ):
        c.execute(sql)
    # şema 7: kullanıcı başına arayüz dili (eski tabloya sütun eklenir)
    if "dil" not in [r[1] for r in c.execute("PRAGMA table_info(kullanicilar)")]:
        c.execute("ALTER TABLE kullanicilar ADD COLUMN dil TEXT NOT NULL DEFAULT 'tr'")


def dil_oku(c, kid):
    r = c.execute("SELECT dil FROM kullanicilar WHERE id = ?", (kid,)).fetchone()
    return r[0] if r and r[0] in DILLER else "tr"


def dil_ayarla(c, kid, dil):
    """Kullanıcının arayüz dili (her rol kendi dilini seçer)."""
    if dil not in DILLER:
        raise KimlikHatasi(_("Bilinmeyen dil: {dil!r}").format(dil=dil))
    with c:
        c.execute("UPDATE kullanicilar SET dil = ? WHERE id = ?", (dil, kid))


# ── yardımcılar ─────────────────────────────────────────────────────
def _ad(ad):
    return tr_fold((ad or "").strip())


def _ozet(sifre, tuz=None):
    tuz = tuz or secrets.token_bytes(16)
    o = hashlib.scrypt(sifre.encode("utf-8"), salt=tuz, **_SCRYPT)
    return f"scrypt${tuz.hex()}${o.hex()}"


def _dogru_mu(sifre, kayitli):
    __, tuz, o = kayitli.split("$")
    yeni = _ozet(sifre, bytes.fromhex(tuz)).split("$")[2]
    return hmac.compare_digest(yeni, o)


_SAHTE_OZET = _ozet("zaman-esitleme-icin")    # bilinmeyen kullanıcıda aynı scrypt süresi


def _sifre_kontrol(sifre):
    if len((sifre or "").strip()) < EN_AZ_SIFRE:
        raise KimlikHatasi(_("Şifre en az {EN_AZ_SIFRE} karakter olmalı.").format(EN_AZ_SIFRE=EN_AZ_SIFRE))


def _olay(c, olay, kullanici="", ip="", yapan="", ayrinti="", simdi=None):
    c.execute("INSERT INTO guvenlik (zaman, olay, kullanici, ip, yapan, ayrinti) "
              "VALUES (?, ?, ?, ?, ?, ?)",
              (simdi or time.time(), olay, kullanici, ip, yapan or "", ayrinti))


def _satir(c, ad):
    return c.execute("SELECT id, ad, ad_soyad, rol, sifre_ozet, aktif, hatali, kilit_bitis, "
                     "kalici_kilit FROM kullanicilar WHERE ad = ?", (_ad(ad),)).fetchone()


def _son_yonetici(c, s):
    """s yönetici ve kilidini açabilecek başka etkin, kalıcı kilitsiz yönetici yok mu?"""
    return s[3] == YONETICI and c.execute(
        "SELECT COUNT(*) FROM kullanicilar WHERE rol = ? AND aktif = 1 AND kalici_kilit = 0 "
        "AND id != ?", (YONETICI, s[0])).fetchone()[0] == 0


def _sure_metni(sn):
    sn = int(sn + 0.999)
    return _("{d} dk {d2} sn").format(d=sn // 60, d2=sn % 60) if sn >= 60 else _("{sn} sn").format(sn=sn)


def yetkili(rol, gereken):
    """rol, gereken seviyeye eşit ya da üstünde mi?"""
    return _ROL_SIRA.get(rol, -1) >= _ROL_SIRA[gereken]


def kurulum_gerekli(c):
    return c.execute("SELECT COUNT(*) FROM kullanicilar").fetchone()[0] == 0


# ── giriş ───────────────────────────────────────────────────────────
def _cihaz_sayaci(c, ip, simdi):
    """Cihazın geçerli hata sayısı; son hatadan CIHAZ_SAYAC_OMRU geçtiyse 0."""
    adet, son = c.execute("SELECT COALESCE(SUM(adet), 0), MAX(son) FROM cihaz_hata WHERE ip = ?",
                          (ip,)).fetchone()
    return adet if son is not None and simdi - son < CIHAZ_SAYAC_OMRU else 0


def _kilit_durumu(c, ad_n, ip, cihaz_kilidi, simdi):
    """(cihaz satırı, kullanıcı satırı); cihaz ya da hesap kilitliyse GirisHatasi.
    Kilitliyken yapılan denemeler sayılmaz (çağıran işlem geri alınır)."""
    cihaz = c.execute("SELECT hatali, kilit_bitis FROM cihaz_kilit WHERE ip = ?",
                      (ip,)).fetchone() if cihaz_kilidi else None
    if cihaz and cihaz[1] and cihaz[1] > simdi:
        raise GirisHatasi(_("Bu cihazdan çok fazla hatalı deneme yapıldı; giriş kilitli. {d} sonra tekrar deneyin.").format(d=_sure_metni(cihaz[1] - simdi)),
                          cihaz[1] - simdi)
    s = _satir(c, ad_n)
    if s and s[8]:
        raise GirisHatasi(_("Hesap çok fazla hatalı deneme nedeniyle kilitlendi; yalnızca "
                          "yönetici açabilir."), None)
    if s and s[7] and s[7] > simdi:
        raise GirisHatasi(_("Hesap çok fazla hatalı deneme nedeniyle kilitli. {d} sonra tekrar deneyin.").format(d=_sure_metni(s[7] - simdi)), s[7] - simdi)
    return cihaz, s


def giris(c, ad, sifre, ip="yerel", simdi=None):
    """Başarılıysa Kullanici; değilse GirisHatasi (kilit varsa kalan süreyle)."""
    simdi = time.time() if simdi is None else simdi
    ad_n = _ad(ad)
    # Cihaz kilidi yalnız ağdan gelen girişlerde (tablet): masaüstünde herkes "yerel"; bir
    # kişinin hataları bilgisayarı yöneticiye de kilitlemesin. Kullanıcı kilidi her yerde geçerli.
    cihaz_kilidi = ip != YEREL
    cihaz, s = _kilit_durumu(c, ad_n, ip, cihaz_kilidi, simdi)
    dogru = _dogru_mu(sifre or "", s[4] if s else _SAHTE_OZET) and bool(s) and s[5] == 1
    with c:
        # Sayaçlar yazma kilidi altında TAZE okunur ve kilit yeniden denetlenir: aksi halde
        # paralel denemeler (scrypt süresince) aynı eski sayacı görüp kilidi atlatır.
        c.execute("BEGIN IMMEDIATE")
        onceki = s
        cihaz, s = _kilit_durumu(c, ad_n, ip, cihaz_kilidi, simdi)
        # scrypt sürerken devre dışı bırakıldı ya da şifresi değişti: eski doğrulama geçmez
        dogru = dogru and bool(s) and s[5] == 1 and s[4] == onceki[4]
        if dogru:
            c.execute("UPDATE kullanicilar SET hatali = 0, kilit_bitis = NULL WHERE id = ?",
                      (s[0],))
            if cihaz_kilidi:   # yalnız bu hesabın hataları düşer (V-7-15)
                c.execute("DELETE FROM cihaz_hata WHERE ip = ? AND ad = ?", (ip, ad_n))
                kalan_ip = _cihaz_sayaci(c, ip, simdi)
                if kalan_ip:
                    c.execute("UPDATE cihaz_kilit SET hatali = ? WHERE ip = ?", (kalan_ip, ip))
                else:
                    c.execute("DELETE FROM cihaz_hata WHERE ip = ?", (ip,))
                    c.execute("DELETE FROM cihaz_kilit WHERE ip = ?", (ip,))
            _olay(c, "giris", ad_n, ip, simdi=simdi)
            return Kullanici(s[0], s[1], s[2], s[3])

        # ── hatalı deneme: cihaz ve (varsa) kullanıcı sayaçları ──
        n_ip = (_cihaz_sayaci(c, ip, simdi) if cihaz_kilidi else 0) + 1
        ip_bitis = None
        if cihaz_kilidi and n_ip > ILK_SERBEST_HATA:
            ip_bitis = simdi + KILIT_SURELERI[min(n_ip - ILK_SERBEST_HATA - 1,
                                                  len(KILIT_SURELERI) - 1)]
        if cihaz_kilidi:
            if n_ip == 1:   # süresi dolmuş eski hatalar sayılmasın
                c.execute("DELETE FROM cihaz_hata WHERE ip = ?", (ip,))
            c.execute("INSERT INTO cihaz_hata (ip, ad, adet, son) VALUES (?, ?, 1, ?) "
                      "ON CONFLICT(ip, ad) DO UPDATE SET adet = adet + 1, son = excluded.son",
                      (ip, ad_n, simdi))
            c.execute("INSERT INTO cihaz_kilit (ip, hatali, kilit_bitis, son_ad) VALUES (?, ?, ?, ?) "
                      "ON CONFLICT(ip) DO UPDATE SET hatali = excluded.hatali, "
                      "kilit_bitis = excluded.kilit_bitis, son_ad = excluded.son_ad",
                      (ip, n_ip, ip_bitis, ad_n))
        mesaj, kalan = _("Kullanıcı adı ya da şifre hatalı."), 0
        ayrinti = f"ardışık hata (cihaz): {n_ip}" if cihaz_kilidi else ""
        if s and s[5] == 1:
            n = s[6] + 1
            ayrinti = f"ardışık hata (hesap): {n}" + (f", (cihaz): {n_ip}" if cihaz_kilidi else "")
            bitis, kalici = None, 0
            if n > ILK_SERBEST_HATA:
                kademe = n - ILK_SERBEST_HATA - 1
                if kademe >= len(KILIT_SURELERI) and _son_yonetici(c, s):
                    bitis = simdi + KILIT_SURELERI[-1]   # kilidi açacak kimse kalmasın diye
                    ayrinti += " (son yönetici: kalıcı yerine 60 dk)"
                elif kademe >= len(KILIT_SURELERI):
                    kalici = 1
                else:
                    bitis = simdi + KILIT_SURELERI[kademe]
            c.execute("UPDATE kullanicilar SET hatali = ?, kilit_bitis = ?, kalici_kilit = ? "
                      "WHERE id = ?", (n, bitis, kalici, s[0]))
            if kalici:
                _olay(c, "hesap_kalici_kilit", ad_n, ip, simdi=simdi)
                mesaj, kalan = (_("Kullanıcı adı ya da şifre hatalı. Hesap kilitlendi; yalnızca "
                                "yönetici açabilir."), None)
            elif bitis:
                mesaj, kalan = (_("Kullanıcı adı ya da şifre hatalı. Giriş {d} kilitlendi.").format(d=_sure_metni(bitis - simdi)), bitis - simdi)
        if ip_bitis and kalan == 0:
            mesaj, kalan = (_("Kullanıcı adı ya da şifre hatalı. Giriş {d} kilitlendi.").format(d=_sure_metni(ip_bitis - simdi)), ip_bitis - simdi)
        _olay(c, "giris_basarisiz", ad_n, ip, ayrinti=ayrinti, simdi=simdi)
    raise GirisHatasi(mesaj, kalan)


# ── kullanıcı yönetimi (yetki kontrolü çağıranda: yalnız yönetici) ───
def kullanici_ekle(c, ad, sifre, rol, ad_soyad="", yapan=None):
    ad_n = _ad(ad)
    if not ad_n or any(ch.isspace() for ch in ad_n):
        raise KimlikHatasi(_("Kullanıcı adı boş olamaz ve boşluk içeremez."))
    if rol not in ROLLER:
        raise KimlikHatasi(_("Geçersiz rol: {rol}").format(rol=rol))
    _sifre_kontrol(sifre)
    if _satir(c, ad_n):
        raise KimlikHatasi(_("'{ad_n}' kullanıcısı zaten var.").format(ad_n=ad_n))
    with c:
        c.execute("INSERT INTO kullanicilar (ad, ad_soyad, rol, sifre_ozet, olusturma) "
                  "VALUES (?, ?, ?, ?, ?)", (ad_n, ad_soyad.strip(), rol, _ozet(sifre), time.time()))
        _olay(c, "kullanici_ekle", ad_n, yapan=yapan, ayrinti=f"rol: {rol}")


def _var(c, ad):
    s = _satir(c, ad)
    if not s:
        raise KimlikHatasi(_("'{d}' kullanıcısı yok.").format(d=_ad(ad)))
    return s


def _oturumlari_kapat(c, kullanici_id):
    c.execute("DELETE FROM oturumlar WHERE kullanici_id = ?", (kullanici_id,))


def rol_degistir(c, ad, rol, yapan):
    s = _var(c, ad)
    if rol not in ROLLER:
        raise KimlikHatasi(_("Geçersiz rol: {rol}").format(rol=rol))
    if rol != YONETICI and _son_yonetici(c, s):
        raise KimlikHatasi(_("Bu son yönetici; rolü değiştirilemez (önce başka bir yönetici ekleyin)."))
    with c:
        c.execute("UPDATE kullanicilar SET rol = ? WHERE id = ?", (rol, s[0]))
        _oturumlari_kapat(c, s[0])
        _olay(c, "rol_degistir", s[1], yapan=yapan, ayrinti=f"{s[3]} -> {rol}")


def pasif_yap(c, ad, yapan):
    s = _var(c, ad)
    if _son_yonetici(c, s):
        raise KimlikHatasi(_("Bu son yönetici; devre dışı bırakılamaz."))
    with c:
        c.execute("UPDATE kullanicilar SET aktif = 0 WHERE id = ?", (s[0],))
        _oturumlari_kapat(c, s[0])
        _olay(c, "kullanici_pasif", s[1], yapan=yapan)


def aktif_yap(c, ad, yapan):
    s = _var(c, ad)
    with c:
        c.execute("UPDATE kullanicilar SET aktif = 1 WHERE id = ?", (s[0],))
        _olay(c, "kullanici_aktif", s[1], yapan=yapan)


def kilit_ac(c, ad, yapan):
    s = _var(c, ad)
    with c:
        c.execute("UPDATE kullanicilar SET hatali = 0, kilit_bitis = NULL, kalici_kilit = 0 "
                  "WHERE id = ?", (s[0],))
        c.execute("DELETE FROM cihaz_hata WHERE ip IN (SELECT ip FROM cihaz_kilit WHERE son_ad = ?)",
                  (s[1],))
        c.execute("DELETE FROM cihaz_kilit WHERE son_ad = ?", (s[1],))
        _olay(c, "kilit_ac", s[1], yapan=yapan)


def sifre_degistir(c, ad, eski, yeni):
    """Mevcut şifre girişle aynı kuralla doğrulanır: hatalar kilit sayacına ve güvenlik
    kaydına işler (açık bırakılmış oturumda sınırsız tahmin olmasın)."""
    _sifre_kontrol(yeni)
    if _var(c, ad)[5] != 1:   # giris() bunu "şifre hatalı" diye reddederdi: yanıltıcı
        raise GirisHatasi(_("Hesap devre dışı bırakılmış; şifre değiştirilemez."))
    try:
        giris(c, ad, eski, ip=YEREL)
    except GirisHatasi as e:
        if e.kalan_sn == 0:
            raise GirisHatasi(_("Mevcut şifre hatalı.")) from None
        raise
    s = _var(c, ad)
    with c:
        c.execute("UPDATE kullanicilar SET sifre_ozet = ? WHERE id = ?", (_ozet(yeni), s[0]))
        _oturumlari_kapat(c, s[0])
        _olay(c, "sifre_degistir", s[1], yapan=s[1])


def sifre_sifirla(c, ad, yeni, yapan):
    s = _var(c, ad)
    _sifre_kontrol(yeni)
    with c:
        c.execute("UPDATE kullanicilar SET sifre_ozet = ?, hatali = 0, kilit_bitis = NULL, "
                  "kalici_kilit = 0 WHERE id = ?", (_ozet(yeni), s[0]))
        _oturumlari_kapat(c, s[0])
        _olay(c, "sifre_sifirla", s[1], yapan=yapan)


def kullanicilar(c):
    simdi = time.time()
    return [{"ad": r[0], "ad_soyad": r[1], "rol": r[2], "aktif": bool(r[3]),
             "kilit": _("kalıcı") if r[5] else (_sure_metni(r[4] - simdi) if r[4] and r[4] > simdi
                                             else "")}
            for r in c.execute("SELECT ad, ad_soyad, rol, aktif, kilit_bitis, kalici_kilit "
                               "FROM kullanicilar ORDER BY ad")]


def guvenlik_kayitlari(c, sinir=500):
    return [{"zaman": r[0], "olay": r[1], "kullanici": r[2], "ip": r[3], "yapan": r[4],
             "ayrinti": r[5]}
            for r in c.execute("SELECT zaman, olay, kullanici, ip, yapan, ayrinti FROM guvenlik "
                               "ORDER BY id DESC LIMIT ?", (sinir,))]


# ── oturumlar (tablet) ──────────────────────────────────────────────
def _jeton_ozet(jeton):
    return hashlib.sha256(jeton.encode("utf-8")).hexdigest()


def oturum_ac(c, kullanici, cihaz, simdi=None):
    simdi = time.time() if simdi is None else simdi
    jeton = secrets.token_urlsafe(32)
    with c:
        c.execute("DELETE FROM oturumlar WHERE bitis < ?", (simdi,))
        c.execute("INSERT INTO oturumlar (jeton_ozet, kullanici_id, cihaz, olusturma, bitis) "
                  "VALUES (?, ?, ?, ?, ?)",
                  (_jeton_ozet(jeton), kullanici.id, cihaz, simdi, simdi + OTURUM_SURESI))
    return jeton


def oturum_dogrula(c, jeton, simdi=None):
    """Geçerli oturumun kullanıcısı (rol her seferinde güncel okunur) ya da None."""
    if not jeton:
        return None
    simdi = time.time() if simdi is None else simdi
    r = c.execute("SELECT k.id, k.ad, k.ad_soyad, k.rol FROM oturumlar o JOIN kullanicilar k "
                  "ON k.id = o.kullanici_id WHERE o.jeton_ozet = ? AND o.bitis > ? "
                  "AND k.aktif = 1 AND k.kalici_kilit = 0",
                  (_jeton_ozet(jeton), simdi)).fetchone()
    return Kullanici(*r) if r else None


def oturum_kapat(c, jeton):
    with c:
        c.execute("DELETE FROM oturumlar WHERE jeton_ozet = ?", (_jeton_ozet(jeton or ""),))
