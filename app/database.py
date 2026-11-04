# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""
SQLite veritabanı katmanı (2026-10-30; öncesi tek dosya data/data.json).

Ana veritabanı: data/kalite.db (bu bilgisayar). Her bölüm (wps, pqr, std, cert) bir
tablo; her satır kaydın EKSİKSİZ JSON'unu (`veri`) ve sırasını (`sira`) taşır. Sık
sorgulanan alanlar (no, durum, bitis...) `veri`'den türetilmiş sütunlardır — bilgi
tek yerde tutulur, sütunlar sapamaz. Program kayıtlara sıra indeksiyle erişir
(update_wps(i, r)); bellek içi listeler + yazınca anında DB'ye işlenir. Pencere açıkken
liste yenilenebildiği için düzenleme/silme kaydın kimliğini önceden alır:
update_wps(i, r, anahtar=db.anahtar("wps", i)).

İlk açılışta data/data.json varsa taşınır: geçici dosyaya yazılır, kayıt kayıt
doğrulanır, sonra tek adımda yerine konur. data.json'a dokunulmaz (artık okunmaz).
WAL kipi: tablet sunucusu (salt okunur bağlantı) masaüstü yazarken okuyabilir.
"""

import os
import glob
import pathlib
import json
import shutil
import sqlite3
from datetime import date, datetime

from . import firma as firma_ayar, kimlik
from .dil import _

# Proje kökü: app/ klasörünün bir üstü
ROOT_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR   = os.path.join(ROOT_DIR, "data")
DATA_FILE  = os.path.join(DATA_DIR, "data.json")   # yalnız taşıma kaynağı
BACKUP_DIR = os.path.join(ROOT_DIR, "yedek")
AUTO_BACKUP_KEEP = 14   # tutulacak günlük otomatik yedek sayısı
DB_ADI = "kalite.db"
TASINDI_ISARETI = "kalite.db.tasindi"   # taşıma yapıldı işareti (data/ içinde)
KILIT_BEKLEME = 5   # sn; başka bağlantı yazarken bekleme süresi
SEMA_SURUMU = 7   # 1: veri tabloları; 2: + surum, kimlik, değişiklik kaydı; 3: + cihaz_hata; 4: + itp; 5: + sartname; 6: + ayarlar (firma); 7: + kullanicilar.dil

SECTIONS = ("pqr", "wps", "std", "cert", "itp", "sartname")
# bölüm → veri'den türetilen sorgu sütunları (JSON anahtarı = sütun adı)
TURETILMIS = {
    "wps": ("no", "rev", "pqr", "durum"),
    "pqr": ("no", "rev", "test"),
    "std": ("no", "org", "status"),
    "cert": ("no", "ad", "org", "bitis"),
    "itp": ("no", "rev", "durum"),
    "sartname": ("kurum", "ad", "tur", "no", "rev", "durum"),
}


class VeritabaniHatasi(Exception):
    """Veritabanı açılamadı/taşınamadı; kullanıcıya gösterilecek anlamlı mesaj taşır."""


class YetkiHatasi(VeritabaniHatasi):
    """Giriş yapan kullanıcının rolü bu işlem için yetmiyor."""


class CakismaHatasi(VeritabaniHatasi):
    """Kayıt başka bir cihazda değiştirilmiş/silinmiş; güncel hali yüklenip tekrar denenmeli."""


def db_yolu():
    """DATA_DIR'den hesaplanır (testler DATA_DIR'i yamalayınca DB de geçici klasöre gider)."""
    return os.path.join(DATA_DIR, DB_ADI)


def _baglan(yol, salt_okunur=False):
    if salt_okunur:
        # as_uri yüzde-kodlar: yolda '#' ya da '%' varsa yol kesilip başka dosya açılmasın
        uri = pathlib.Path(os.path.abspath(yol)).as_uri() + "?mode=ro"
        return sqlite3.connect(uri, uri=True, timeout=KILIT_BEKLEME)
    c = sqlite3.connect(yol, timeout=KILIT_BEKLEME)
    c.execute("PRAGMA journal_mode=WAL")
    return c


def _veri_tablolari(c):
    for b in SECTIONS:
        turet = "".join(f", {s} TEXT GENERATED ALWAYS AS (json_extract(veri, '$.{s}')) VIRTUAL"
                        for s in TURETILMIS[b])
        # surum: çakışma sayacı (her güncellemede +1). "rev" adı WPS/PQR'nin kendi revizyonu.
        c.execute(f"CREATE TABLE IF NOT EXISTS {b} (id INTEGER PRIMARY KEY, "
                  f"sira INTEGER NOT NULL, veri TEXT NOT NULL CHECK (json_valid(veri)), "
                  f"surum INTEGER NOT NULL DEFAULT 0{turet})")
        c.execute(f"CREATE INDEX IF NOT EXISTS {b}_no ON {b}(no)")


def _sema_kur(c):
    _veri_tablolari(c)
    _ek_sema(c)
    c.execute(f"PRAGMA user_version = {SEMA_SURUMU}")


def _ek_sema(c):
    """Şema 2-3 ekleri: kimlik tabloları + değişiklik kaydı (CREATE IF NOT EXISTS)."""
    kimlik.sema_kur(c)
    c.execute("CREATE TABLE IF NOT EXISTS degisiklikler (id INTEGER PRIMARY KEY, "
              "zaman TEXT NOT NULL, kullanici TEXT NOT NULL, kaynak TEXT NOT NULL, "
              "bolum TEXT NOT NULL, kayit_id INTEGER NOT NULL, kayit_no TEXT NOT NULL DEFAULT '', "
              "islem TEXT NOT NULL, once TEXT, sonra TEXT)")
    firma_ayar.sema_kur(c)   # şema 6


def _oku(c):
    """{bölüm: ([kayıt...], [id...], [surum...])} sira düzeninde."""
    sonuc = {}
    for b in SECTIONS:
        sutunlar = [r[1] for r in c.execute(f"PRAGMA table_xinfo({b})")]
        if not sutunlar:   # eski şema dosyası (ör. şema 3 yedeği): bölüm tablosu yok = boş
            sonuc[b] = ([], [], [])
            continue
        # şema 1 dosyaları (eski yedekler) surum sütununu taşımaz: 0 sayılır
        surum = "surum" if "surum" in sutunlar else "0"
        satirlar = c.execute(f"SELECT id, veri, {surum} FROM {b} ORDER BY sira, id").fetchall()
        sonuc[b] = ([json.loads(v) for __, v, __ in satirlar], [i for i, __, __ in satirlar],
                    [u for __, __, u in satirlar])
    return sonuc


def bolum_kayitlari(yol, b):
    """Salt okunur: [{"_id", "_surum", ...kayıt}] (tablet düzenleme için kimlikli liste)."""
    _bolum(b)
    c = _baglan(yol, salt_okunur=True)
    try:
        return [dict(json.loads(v), _id=i, _surum=u)
                for i, v, u in c.execute(f"SELECT id, veri, surum FROM {b} ORDER BY sira, id")]
    finally:
        c.close()


# ── yazma (masaüstü ve tablet sunucusu ortak; her biri tek işlem + değişiklik kaydı) ──
def _bolum(b):
    if b not in SECTIONS:   # tablo adı SQL'e girer: yalnız sabit listeden
        raise VeritabaniHatasi(_("Bilinmeyen bölüm: {b!r}").format(b=b))


def _kaydet_degisiklik(c, b, kid, islem, once, sonra, kim, kaynak):
    d = sonra or once or {}
    no = d.get("no", "")
    if b == "sartname" and not no:   # şartnamede no boş olabilir: kayıt adıyla görünsün
        no = d.get("ad", "")
    c.execute("INSERT INTO degisiklikler (zaman, kullanici, kaynak, bolum, kayit_id, kayit_no, "
              "islem, once, sonra) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
              (datetime.now().isoformat(timespec="seconds"), kim, kaynak, b, kid, str(no), islem,
               None if once is None else _jdump(once), None if sonra is None else _jdump(sonra)))


def _veri_kontrol(veri):
    if not isinstance(veri, dict):
        raise VeritabaniHatasi(_("Kayıt bir sözlük (alan: değer) olmalı."))
    try:
        return json.dumps(veri, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as e:
        raise VeritabaniHatasi(_("Kayıt JSON'a çevrilemedi: {e}").format(e=e)) from e


def _sql(fn):
    """sqlite hatasını anlamlı hataya çevirir (değişiklik uygulanmamıştır)."""
    def sar(*a, **k):
        try:
            return fn(*a, **k)
        except sqlite3.Error as e:
            raise VeritabaniHatasi(_("Kayıt veritabanına yazılamadı, değişiklik uygulanmadı: {e}").format(e=e)) from e
    return sar


def _ekle_ic(c, b, veri, metin, kim, kaynak):
    """İşlem içinde (BEGIN IMMEDIATE sonrası) ekleme. Döner: id."""
    sira = c.execute(f"SELECT COALESCE(MAX(sira), -1) FROM {b}").fetchone()[0] + 1
    # Silinmiş kaydın id'si yeniden verilmez (INTEGER PRIMARY KEY en büyük id silinince onu
    # yeniden kullanır): yoksa o kaydın açık formu (id, sürüm 0) yeni kaydı ezerdi.
    kid = 1 + c.execute(f"SELECT MAX(COALESCE((SELECT MAX(id) FROM {b}), 0), COALESCE("
                        "(SELECT MAX(kayit_id) FROM degisiklikler WHERE bolum = ?), 0))",
                        (b,)).fetchone()[0]
    c.execute(f"INSERT INTO {b} (id, sira, veri) VALUES (?, ?, ?)", (kid, sira, metin))
    _kaydet_degisiklik(c, b, kid, "ekle", None, veri, kim, kaynak)
    return kid


firma_yaz = _sql(firma_ayar.yaz)


@_sql
def kayit_ekle(c, b, veri, kim, kaynak):
    """Yeni kayıt (sona). Döner: id."""
    _bolum(b)
    metin = _veri_kontrol(veri)
    with c:
        c.execute("BEGIN IMMEDIATE")   # MAX okuma ile INSERT arası başka bağlantı yazamasın
        return _ekle_ic(c, b, veri, metin, kim, kaynak)


def _mevcut(c, b, kid, surum):
    r = c.execute(f"SELECT veri, surum FROM {b} WHERE id = ?", (kid,)).fetchone()
    if r is None:
        raise CakismaHatasi(_("Kayıt başka bir cihazda silinmiş; liste yenilendi."))
    if r[1] != surum:
        raise CakismaHatasi(_("Kayıt siz düzenlerken başka bir cihazda değiştirildi; güncel hali "
                            "yüklendi, değişikliğinizi tekrar yapın."))
    return json.loads(r[0])


def _guncelle_ic(c, b, kid, veri, metin, surum, kim, kaynak):
    once = _mevcut(c, b, kid, surum)
    if c.execute(f"UPDATE {b} SET veri = ?, surum = surum + 1 WHERE id = ? AND surum = ?",
                 (metin, kid, surum)).rowcount != 1:
        raise CakismaHatasi(_("Kayıt aynı anda başka bir cihazda değiştirildi; tekrar deneyin."))
    _kaydet_degisiklik(c, b, kid, "guncelle", once, veri, kim, kaynak)


@_sql
def kayit_guncelle(c, b, kid, veri, surum, kim, kaynak):
    """surum eşleşirse günceller (iyimser kilit). Döner: yeni surum."""
    _bolum(b)
    metin = _veri_kontrol(veri)
    with c:
        _guncelle_ic(c, b, kid, veri, metin, surum, kim, kaynak)
    return surum + 1


def _sil_ic(c, b, kid, surum, kim, kaynak):
    once = _mevcut(c, b, kid, surum)
    if c.execute(f"DELETE FROM {b} WHERE id = ? AND surum = ?", (kid, surum)).rowcount != 1:
        raise CakismaHatasi(_("Kayıt aynı anda başka bir cihazda değiştirildi; tekrar deneyin."))
    _kaydet_degisiklik(c, b, kid, "sil", once, None, kim, kaynak)


@_sql
def kayit_sil(c, b, kid, surum, kim, kaynak):
    _bolum(b)
    with c:
        _sil_ic(c, b, kid, surum, kim, kaynak)


@_sql
def rev_yaz(c, b, kid, eski, surum, yeni, kim, kaynak):
    """"Yeni rev" (ITP, şartname): kaynağı kilitleme (eski None ise yok) + yeni taslak TEK işlemde
    (ikinci adım düşerse kaynak kilitli, yeni rev'siz kalmasın). Döner: yeni id."""
    _bolum(b)
    yeni_metin = _veri_kontrol(yeni)
    eski_metin = None if eski is None else _veri_kontrol(eski)
    with c:
        c.execute("BEGIN IMMEDIATE")
        if eski is not None:
            _guncelle_ic(c, b, kid, eski, eski_metin, surum, kim, kaynak)
        else:
            _mevcut(c, b, kid, surum)   # kilitli kaynak: başka cihazda silinmiş/düzeltilmiş mi
        return _ekle_ic(c, b, yeni, yeni_metin, kim, kaynak)


@_sql
def kilitli_sil(c, b, kid, surum, kim, kaynak, olay, kayit_adi, gerekce):
    """Kilitli kayıt silme + gerekçeli güvenlik kaydı TEK işlemde."""
    _bolum(b)
    with c:
        c.execute("BEGIN IMMEDIATE")
        _sil_ic(c, b, kid, surum, kim, kaynak)
        kimlik._olay(c, olay, kayit_adi, yapan=kim, ayrinti=gerekce)


@_sql
def kilitli_duzelt_yaz(c, b, kid, veri, surum, kim, kaynak, olay, kayit_adi, gerekce):
    """Kilitli kayıt düzeltmesi (yalnız Yönetici) + gerekçeli güvenlik kaydı TEK işlemde."""
    _bolum(b)
    metin = _veri_kontrol(veri)
    with c:
        c.execute("BEGIN IMMEDIATE")
        _guncelle_ic(c, b, kid, veri, metin, surum, kim, kaynak)
        kimlik._olay(c, olay, kayit_adi, yapan=kim, ayrinti=gerekce)


def degisiklik_kayitlari(c, sinir=1000, bolum=None):
    sql, args = ("SELECT zaman, kullanici, kaynak, bolum, kayit_id, kayit_no, islem, once, sonra "
                 "FROM degisiklikler"), []
    if bolum:
        sql += " WHERE bolum = ?"; args.append(bolum)
    sql += " ORDER BY id DESC LIMIT ?"; args.append(sinir)
    return [{"zaman": z, "kullanici": k, "kaynak": ky, "bolum": b, "kayit_id": i, "kayit_no": n,
             "islem": isl, "once": json.loads(o) if o else None,
             "sonra": json.loads(so) if so else None}
            for z, k, ky, b, i, n, isl, o, so in c.execute(sql, args)]


def tum_veri(yol):
    """Salt okunur bağlantıyla tüm bölümler (tablet sunucusu, yedek doğrulama)."""
    c = _baglan(yol, salt_okunur=True)
    try:
        return {b: kayitlar for b, (kayitlar, __, __) in _oku(c).items()}
    finally:
        c.close()


def _isaret_yaz(yol):
    with open(yol, "w", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')} data.json -> {DB_ADI}\n")


def _jdump(r):
    return json.dumps(r, ensure_ascii=False)


SAMPLE_DATA = {
    "pqr": [
        {"no": "PQR-001", "rev": "00", "tarih": "2022-03-15", "proses": "GTAW",
         "metal": "P-1", "dolgu": "ER70S-6", "onisitma": "Yok", "pwht": "Yok",
         "akim": "90-110", "voltaj": "22-24", "hiz": "120-160", "polarite": "DCEP",
         "test": "Geçti", "lab": "TÜV SÜD", "notlar": "ASME IX kapsamında"},
    ],
    "wps": [
        {"no": "WPS-001", "rev": "00", "tarih": "2022-04-01", "pqr": "PQR-001",
         "proses": "GTAW", "metal": "P-1", "dolgu": "ER70S-6", "pozisyon": "1G",
         "onisitma": "Yok", "pwht": "Yok", "akim": "90-110", "voltaj": "22-24",
         "hiz": "120-160", "polarite": "DCEP", "durum": "Aktif", "notlar": ""},
    ],
    "std": [
        {"no": "ASME IX", "org": "ASME",
         "title": "Qualification Standard for Welding, Brazing and Fusing Procedures",
         "myVer": "2021", "year": "2021", "lastVer": "", "manualLastVer": "",
         "lastCheck": "", "status": "kontrol", "notlar": ""},
    ],
    "cert": [
        {"no": "TR-001", "ad": "ISO 9001", "org": "TÜV NORD",
         "kapsam": "Çelik boru üretimi ve kaplama",
         "tarih": "2023-05-01", "bitis": "2026-05-01", "notlar": ""},
    ],
    "itp": [],
    "sartname": [],
}


def parse_iso(d):
    """'YYYY-MM-DD' → date | None."""
    if not d:
        return None
    try:
        return date.fromisoformat(str(d)[:10])
    except (ValueError, TypeError):
        return None


def cert_status(rec, warn_days=60):
    """Bitiş tarihine göre sertifika durumunu hesaplar.

    Döner: ('gecerli'|'yakinda'|'dolmus'|'belirsiz', kalan_gun | None)
    kalan_gun negatifse süre dolmuştur.
    """
    bitis = parse_iso(rec.get("bitis"))
    if bitis is None:
        return "belirsiz", None
    kalan = (bitis - date.today()).days
    if kalan < 0:
        return "dolmus", kalan
    if kalan <= warn_days:
        return "yakinda", kalan
    return "gecerli", kalan


class Database:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        yol = db_yolu()
        if not os.path.exists(yol):
            self._olustur(yol)
        self._c = self._ac(yol)
        isaret = os.path.join(DATA_DIR, TASINDI_ISARETI)
        if os.path.exists(DATA_FILE) and not os.path.exists(isaret):
            try:
                _isaret_yaz(isaret)   # data.json'dan sessiz yeniden kurulum koruması hep yerinde
            except OSError as e:
                self._c.close()
                raise VeritabaniHatasi(_("Taşıma işareti yazılamadı: {e}\nDosya: {isaret} (klasör yazma izni / virüs tarayıcı kilidi?)").format(e=e, isaret=isaret)) from e
        self.kullanici = None      # kimlik.Kullanici; None = sistem (testler, araçlar)
        self.kaynak = "masaustu"
        self._data = {b: [] for b in SECTIONS}
        self._ids, self._surum = {}, {}
        self.yeniden_yukle()
        self._auto_backup()

    # ── başka bağlantıların (tablet sunucusu) yazmaları ──────────────
    def _veri_surumu(self):
        """Kayıt verisinin sürümü = son değişiklik kaydı id'si. PRAGMA data_version değil:
        o, tablette giriş/oturum/güvenlik kaydı yazılınca da artar ve masaüstü düzenlemelerini
        boş yere "başka cihazda değişti" diye reddettirirdi."""
        try:
            return self._c.execute("SELECT COALESCE(MAX(id), 0) FROM degisiklikler").fetchone()[0]
        except sqlite3.Error as e:
            raise VeritabaniHatasi(_("Veritabanı okunamadı, değişiklik uygulanmadı: {e}").format(e=e)) from e

    def disaridan_degisti(self):
        """Son yüklemeden sonra başka bir bağlantı (tablet) kayıt değiştirdi mi?"""
        return self._veri_surumu() != self._dv

    def yeniden_yukle(self):
        """Listeleri DB'den tazeler; liste nesneleri korunur (sayfalar referans tutabilir).
        Veri ve sürüm aynı okuma işleminde (WAL anlık görüntüsü): arada gelen yazma kaçmaz."""
        self._c.execute("BEGIN")
        try:
            okunan = _oku(self._c)
            dv = self._veri_surumu()
        finally:
            self._c.execute("COMMIT")
        for b in SECTIONS:
            self._data[b][:] = okunan[b][0]
            self._ids[b], self._surum[b] = okunan[b][1], okunan[b][2]
        self._dv = dv

    def _yazma_sonrasi(self, onceki):
        """Kendi yazmamızdan sonra: arada başka yazma yoksa (sürüm tam +1) güncel sayılırız;
        varsa sürüm eski kalır ve sonraki yoklama listeleri tazeler (tablet değişikliği kaçmaz)."""
        yeni = self._veri_surumu()
        if yeni == onceki + 1:
            self._dv = yeni

    def _yazma_oncesi(self):
        if self.kullanici is not None and not kimlik.yetkili(self.kullanici.rol,
                                                             kimlik.DUZENLEYICI):
            raise YetkiHatasi(_("'{ad}' kullanıcısının rolü ({d}) kayıt değiştirmeye yetmiyor.").format(ad=self.kullanici.ad, d=_(kimlik.ROL_ADI[self.kullanici.rol])))
        if self.disaridan_degisti():   # liste indeksleri kaymış olabilir: eski görünümle yazma
            self.yeniden_yukle()
            raise CakismaHatasi(_("Kayıtlar başka bir cihazda (tablet) değiştirildi; liste "
                                "yenilendi. İşlemi tekrar yapın."))

    def anahtar(self, b, i):
        """Kaydın kalıcı kimliği (id, sürüm). Düzenleme/silme penceresi açılırken alınır ve
        yazmaya verilir: pencere açıkken liste yenilense de (3 sn) aynı kayda ve açıldığı
        sürümle yazılır; indeks kaymaz, tablette yapılan değişiklik sessizce ezilmez."""
        return self._ids[b][i], self._surum[b][i]

    def indeks(self, b, kid):
        """id'nin şimdiki liste indeksi; kayıt yoksa None."""
        try:
            return self._ids[b].index(kid)
        except ValueError:
            return None

    def _hedef(self, b, i, anahtar):
        """(indeks, beklenen sürüm). anahtar yoksa eski davranış: indeks + bellekteki sürüm."""
        if anahtar is None:
            return i, self._surum[b][i]
        i = self.indeks(b, anahtar[0])
        if i is None:
            raise CakismaHatasi(_("Kayıt başka bir cihazda silinmiş; liste yenilendi."))
        return i, anahtar[1]

    def _kim(self):
        return self.kullanici.ad if self.kullanici else "sistem"

    # ── firma kimliği (şema 6): yalnız Yönetici yazar ────────────────
    def firma(self):
        return firma_ayar.oku(self._c)

    def firma_kaydet(self, ad, logo, beklenen):
        if self.kullanici is not None and self.kullanici.rol != kimlik.YONETICI:
            raise YetkiHatasi(_("Firma bilgilerini yalnız Yönetici değiştirebilir."))
        onceki = self._dv
        firma_yaz(self._c, ad, logo, beklenen, self._kim(), self.kaynak)
        self._yazma_sonrasi(onceki)

    def degisiklik_kayitlari(self, sinir=1000, bolum=None):
        return degisiklik_kayitlari(self._c, sinir, bolum)

    # ── açılış / taşıma ──────────────────────────────────────────────
    def _olustur(self, yol):
        """data.json varsa onu, yoksa örnek veriyi yeni DB'ye yazar. Önce geçici dosya,
        kayıt kayıt doğrulama, sonra os.replace (yarım DB hiç oluşmaz). Başarılı taşıma
        işaret dosyası bırakır: DB sonradan kaybolursa donmuş data.json'dan sessizce
        yeniden kurulmaz (taşımadan sonraki tüm değişiklikler kaybolurdu)."""
        isaret = os.path.join(DATA_DIR, TASINDI_ISARETI)
        # İşaret ya da SQLite yedeği varsa veritabanı daha önce kullanılmıştır (Antigravity
        # BULGU-02: kalite.db* birlikte silinse de yedekler bunu ele verir)
        if os.path.exists(isaret) or glob.glob(os.path.join(glob.escape(BACKUP_DIR),
                                                            "auto_kalite_*.db")):
            raise VeritabaniHatasi(
                _("Veritabanı bulunamadı: {yol}\nDaha önce SQLite veritabanı kullanılmış (taşıma işareti ya da yedek bulundu); eski data.json güncel değil, ondan yeniden kurulmadı.\nGeri yükleme: {BACKUP_DIR} içindeki en yeni auto_kalite_*.db dosyasını {yol} olarak kopyalayın (yanında kalite.db-wal / -shm varsa önce silin).").format(yol=yol, BACKUP_DIR=BACKUP_DIR))
        json_var = os.path.exists(DATA_FILE)
        kaynak = self._kaynak_oku()
        gecici = yol + ".tasima"
        try:
            self._tasi(yol, gecici, kaynak, isaret if json_var else None)
        except (OSError, sqlite3.Error) as e:   # disk dolu, izin vb.: anlamlı hata, artık yok
            for f in (gecici, gecici + "-journal"):
                try:
                    os.remove(f)
                except OSError:
                    pass
            raise VeritabaniHatasi(_("Veritabanı oluşturulamadı: {e}\nDosya: {yol}; data.json'a dokunulmadı.").format(e=e, yol=yol)) from e

    def _tasi(self, yol, gecici, kaynak, isaret):
        for eski in (gecici, gecici + "-journal"):
            if os.path.exists(eski):
                os.remove(eski)
        self._yetimleri_kaldir(yol)   # eski DB'nin WAL'ı yeni dosyaya uygulanmasın
        try:
            satirlar = {b: [(i, json.dumps(r, ensure_ascii=False, allow_nan=False))
                            for i, r in enumerate(kaynak[b])] for b in SECTIONS}
        except ValueError as e:   # NaN/Infinity: JSON standardı dışı
            raise VeritabaniHatasi(_("data.json taşınamadı: geçersiz sayı değeri ({e}).\nDosya: {DATA_FILE} (dokunulmadı)").format(e=e, DATA_FILE=DATA_FILE)) from e
        c = sqlite3.connect(gecici)
        try:
            with c:
                _sema_kur(c)
                for b in SECTIONS:
                    c.executemany(f"INSERT INTO {b} (sira, veri) VALUES (?, ?)", satirlar[b])
            okunan = {b: k for b, (k, __, __) in _oku(c).items()}
        finally:
            c.close()
        if okunan != kaynak:
            os.remove(gecici)
            fark = [b for b in SECTIONS if okunan[b] != kaynak[b]]
            raise VeritabaniHatasi(_("Taşıma doğrulanamadı (fark: {fark}); veritabanı oluşturulmadı, data.json'a dokunulmadı.").format(fark=fark))
        os.replace(gecici, yol)
        # İşaret DB yerine konduktan SONRA (Antigravity BULGU-01: önce yazılırsa arada çökmede
        # DB'siz işaret açılışı kilitlerdi). Arada çökme olursa __init__ eksik işareti tamamlar.
        # Yalnız data.json'dan taşımada (örnek veriyle ilk kurulum "taşındı" sayılmaz).
        if isaret:
            try:
                _isaret_yaz(isaret)
            except OSError as e:   # DB oluştu; işareti __init__ bir sonraki açılışta yazar
                print(f"[DB] Taşıma işareti yazılamadı: {e}")

    @staticmethod
    def _kaynak_oku():
        """data.json (yoksa örnek veri) → {bölüm: [dict...]}; yapı bozuksa anlamlı hata."""
        if not os.path.exists(DATA_FILE):
            return json.loads(json.dumps(SAMPLE_DATA))
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                kaynak = json.load(f)
        except Exception as e:
            raise VeritabaniHatasi(_("data.json okunamadı, veritabanına taşınamadı: {e}\nDosya: {DATA_FILE} (dokunulmadı)").format(e=e, DATA_FILE=DATA_FILE)) from e
        if not isinstance(kaynak, dict):
            raise VeritabaniHatasi(_("data.json taşınamadı: en üst düzey sözlük değil.\nDosya: {DATA_FILE} (dokunulmadı)").format(DATA_FILE=DATA_FILE))
        sonuc = {}
        for b in SECTIONS:
            kayitlar = kaynak.get(b, [])
            if not isinstance(kayitlar, list) or not all(isinstance(r, dict) for r in kayitlar):
                raise VeritabaniHatasi(_("data.json taşınamadı: '{b}' bölümü kayıt listesi değil.\nDosya: {DATA_FILE} (dokunulmadı)").format(b=b, DATA_FILE=DATA_FILE))
            sonuc[b] = kayitlar
        return sonuc

    @staticmethod
    def _yetimleri_kaldir(yol):
        """DB'siz kalmış -wal/-shm/-journal dosyalarını silmeden yedek/ altına taşır."""
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        for ek in ("-wal", "-shm", "-journal"):
            if os.path.exists(yol + ek):
                os.makedirs(BACKUP_DIR, exist_ok=True)
                shutil.move(yol + ek, os.path.join(BACKUP_DIR, f"kalite_YETIM_{stamp}{ek}"))

    def _ac(self, yol):
        c = None
        try:
            c = _baglan(yol)
            sonuc = c.execute("PRAGMA quick_check").fetchone()[0]
            if sonuc != "ok":
                raise sqlite3.DatabaseError(sonuc)
            surum = c.execute("PRAGMA user_version").fetchone()[0]
            if surum < SEMA_SURUMU:
                self._yukselt(c, surum)
            if surum > SEMA_SURUMU:
                c.close()
                raise VeritabaniHatasi(
                    _("Veritabanı daha yeni bir program sürümüyle oluşturulmuş (şema sürümü {surum}, bu program {SEMA_SURUMU}). Programı güncelleyin; dosyaya dokunulmadı.").format(surum=surum, SEMA_SURUMU=SEMA_SURUMU))
            return c
        except sqlite3.OperationalError as e:   # kilit / açılamama: bozukluk değil
            if c is not None:
                c.close()
            m = str(e).lower()
            neden = (_("kilitli (başka bir program ya da açık bir kopya kullanıyor olabilir; "
                     "onu kapatıp tekrar deneyin)") if "locked" in m or "busy" in m
                     else _("açılamadı ({e})").format(e=e))
            raise VeritabaniHatasi(_("Veritabanı {neden}.\nDosya: {yol}").format(neden=neden, yol=yol)) from e
        except sqlite3.DatabaseError as e:
            if c is not None:
                c.close()
            kopya = self._preserve_corrupt_file(yol)
            raise VeritabaniHatasi(
                _("Veritabanı bozuk: {e}\nDosya: {yol} (silinmedi; kopyası: {kopya}).\nSon sağlam yedek: {BACKUP_DIR} içindeki auto_kalite_*.db").format(e=e, yol=yol, kopya=kopya, BACKUP_DIR=BACKUP_DIR)) from e
        except VeritabaniHatasi:
            raise
        except Exception as e:   # yükseltme yedeği yazılamadı (disk dolu vb.): dosya kilitli kalmasın
            if c is not None:
                c.close()
            raise VeritabaniHatasi(
                _("Veritabanı yükseltilemedi: {e}\nDosya: {yol} (değiştirilmedi; yükseltme tek işlemde yapılır, yarım kalmaz).").format(e=e, yol=yol)) from e

    def _yukselt(self, c, surum):
        """Eski şema → SEMA_SURUMU: önce tutarlı yedek, sonra tek işlemde (hepsi ya da hiçbiri)."""
        os.makedirs(BACKUP_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        hedef = sqlite3.connect(os.path.join(BACKUP_DIR, f"kalite_SEMA{surum}_YEDEK_{stamp}.db"))
        try:
            c.backup(hedef)
            hedef.execute("PRAGMA journal_mode=DELETE")   # yedek tek dosya kalsın (BULGU-08)
        finally:
            hedef.close()
        c.execute("BEGIN")
        try:
            _veri_tablolari(c)   # şema 4-5: itp / sartname tablosu (yoksa)
            for b in SECTIONS:
                sutunlar = [r[1] for r in c.execute(f"PRAGMA table_xinfo({b})")]
                if "surum" not in sutunlar:
                    c.execute(f"ALTER TABLE {b} ADD COLUMN surum INTEGER NOT NULL DEFAULT 0")
            _ek_sema(c)
            c.execute(f"PRAGMA user_version = {SEMA_SURUMU}")
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise

    def _preserve_corrupt_file(self, yol):
        """Bozuk DB'yi (ve WAL'ını) yedek/ altına kopyalar; kopyalanamazsa nedenini döndürür."""
        try:
            os.makedirs(BACKUP_DIR, exist_ok=True)
            stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            dest = os.path.join(BACKUP_DIR, f"kalite_BOZUK_{stamp}.db")
            shutil.copyfile(yol, dest)
            if os.path.exists(yol + "-wal"):
                shutil.copyfile(yol + "-wal", dest + "-wal")
            return dest
        except OSError as e:
            return _("kopyalanamadı: {e}").format(e=e)

    def _auto_backup(self):
        """Günde bir kez tutarlı DB kopyası (sqlite backup API) yedek/ altına; son N gün."""
        try:
            os.makedirs(BACKUP_DIR, exist_ok=True)
            target = os.path.join(BACKUP_DIR, f"auto_kalite_{date.today().isoformat()}.db")
            if not os.path.exists(target):
                # önce geçici dosyaya: yarıda kalan yedek o günün yedeğini engellemesin ve
                # saklama sırasında sağlam bir yedeğin yerini almasın (Antigravity BULGU-08)
                gecici = target + ".tmp"
                try:
                    if os.path.exists(gecici):
                        os.remove(gecici)
                    hedef = sqlite3.connect(gecici)
                    try:
                        self._c.backup(hedef)
                        # backup WAL bayrağını da kopyalar: yedek tek dosya kalsın (-wal/-shm yok)
                        hedef.execute("PRAGMA journal_mode=DELETE")
                    finally:
                        hedef.close()
                    os.replace(gecici, target)
                finally:
                    if os.path.exists(gecici):
                        os.remove(gecici)
            autos = sorted(f for f in os.listdir(BACKUP_DIR)
                           if f.startswith("auto_kalite_") and f.endswith(".db"))
            for old in autos[:-AUTO_BACKUP_KEEP]:
                os.remove(os.path.join(BACKUP_DIR, old))
        except Exception as e:
            print(f"[DB] Otomatik yedek hatası: {e}")

    # ── ortak yazma: yetki + dış değişiklik kontrolü, önce DB (kayıtla), sonra bellek ──
    def _ekle(self, b, r):
        self._yazma_oncesi()
        onceki = self._dv
        kid = kayit_ekle(self._c, b, r, self._kim(), self.kaynak)
        self._data[b].append(r)
        self._ids[b].append(kid)
        self._surum[b].append(0)
        self._yazma_sonrasi(onceki)
        return kid

    def _guncelle(self, b, i, r, anahtar=None):
        self._yazma_oncesi()
        i, surum = self._hedef(b, i, anahtar)
        onceki = self._dv
        try:
            self._surum[b][i] = kayit_guncelle(self._c, b, self._ids[b][i], r,
                                               surum, self._kim(), self.kaynak)
        except CakismaHatasi:
            self.yeniden_yukle()
            raise
        self._data[b][i] = r
        self._yazma_sonrasi(onceki)

    def _sil(self, b, i, anahtar=None):
        self._yazma_oncesi()
        i, surum = self._hedef(b, i, anahtar)
        onceki = self._dv
        try:
            kayit_sil(self._c, b, self._ids[b][i], surum, self._kim(), self.kaynak)
        except CakismaHatasi:
            self.yeniden_yukle()
            raise
        self._data[b].pop(i)
        self._ids[b].pop(i)
        self._surum[b].pop(i)
        self._yazma_sonrasi(onceki)

    # ── WPS ──────────────────────────────────────────────────────────
    def get_wps(self):              return self._data["wps"]
    def add_wps(self, r):           self._ekle("wps", r)
    def update_wps(self, i, r, anahtar=None): self._guncelle("wps", i, r, anahtar)
    def delete_wps(self, i, anahtar=None):    self._sil("wps", i, anahtar)

    # ── PQR ──────────────────────────────────────────────────────────
    def get_pqr(self):              return self._data["pqr"]
    def add_pqr(self, r):           self._ekle("pqr", r)
    def update_pqr(self, i, r, anahtar=None): self._guncelle("pqr", i, r, anahtar)
    def delete_pqr(self, i, anahtar=None):    self._sil("pqr", i, anahtar)
    def wps_count_for_pqr(self, no):
        return sum(1 for w in self._data["wps"] if w.get("pqr") == no)

    # ── STD ──────────────────────────────────────────────────────────
    def get_std(self):              return self._data["std"]
    def add_std(self, r):           self._ekle("std", r)
    def update_std(self, i, r, anahtar=None): self._guncelle("std", i, r, anahtar)
    def delete_std(self, i, anahtar=None):    self._sil("std", i, anahtar)
    def mark_std_checked(self, i, last_ver, status, title=""):
        s = self._data["std"][i]
        yeni = dict(s, lastVer=last_ver, lastCheck=date.today().isoformat(), status=status)
        if title and not s.get("title"):
            yeni["title"] = title
        self._guncelle("std", i, yeni)   # önce DB; hata olursa bellek değişmez
        s.update(yeni)                   # yerinde: kaydı tutan sayfa da günceli görür
        self._data["std"][i] = s

    # ── CERT (sertifika) ─────────────────────────────────────────────
    def get_cert(self):             return self._data["cert"]
    def add_cert(self, r):          self._ekle("cert", r)
    def update_cert(self, i, r, anahtar=None): self._guncelle("cert", i, r, anahtar)
    def delete_cert(self, i, anahtar=None):    self._sil("cert", i, anahtar)

    # ── ITP / Kalite Planı siparişleri (Plan 5a) ─────────────────────
    def get_itp(self):              return self._data["itp"]
    def add_itp(self, r):
        """Yalnız taslak, rev_sira 0; no + rev tekil (Antigravity BULGU-06: arayüz kuralları
        veritabanı katmanında da; 5d: tablet bu yoldan yazacak)."""
        from .itp import kayit
        self._itp_tutarli(r)
        kayit.ekle_kontrol(self._data["itp"], r)
        return self._ekle("itp", r)

    @staticmethod
    def _itp_tutarli(*kayitlar):
        """Yazılan ITP kaydı tutarlı mı (görüntüsüz kilit vb.; denetim BULGU-01)."""
        from .itp import kayit
        for r in kayitlar:
            if r is not None:
                kayit.tutarlilik_kontrol(r)

    def update_itp(self, i, r, anahtar=None):
        """Kilitli kayıt düzenlenmez; taslak → taslak / onaylı (revize yalnız yeni rev'le)."""
        from .itp import kayit   # geç: ITP motoru yalnız gerektiğinde yüklensin
        self._itp_tutarli(r)
        kayit.guncelle_kontrol(self._data["itp"], self._hedef("itp", i, anahtar)[0], r)
        self._guncelle("itp", i, r, anahtar)

    def itp_yeni_rev(self, i, eski, yeni, anahtar=None):
        """Kaynağı kilitleme (eski; None = zaten kilitli, dokunulmaz) + yeni taslak, tek işlem.
        Döner: yeni kaydın id'si."""
        self._itp_tutarli(eski, yeni)
        self._yazma_oncesi()
        j, surum = self._hedef("itp", i, anahtar)
        from .itp import kayit
        kayit.yeni_rev_kontrol(self._data["itp"], j, eski, yeni)
        try:
            kid = rev_yaz(self._c, "itp", self._ids["itp"][j], eski, surum, yeni, self._kim(),
                          self.kaynak)
        finally:
            self.yeniden_yukle()   # başarıda iki kayıt; hatada (geri alındı) güncel hal
        return kid

    def delete_itp(self, i, anahtar=None, gerekce=""):
        """Taslak: Düzenleyici+. Kilitli: yalnız Yönetici, gerekçe zorunlu; silme ve gerekçeli
        güvenlik kaydı tek işlemde."""
        from .itp import kayit
        j, __ = self._hedef("itp", i, anahtar)
        veri = self._data["itp"][j]
        kayit.sil_kontrol(veri, self.kullanici.rol if self.kullanici else None, gerekce)
        if veri["durum"] == kayit.TASLAK:
            self._sil("itp", i, anahtar)
            return
        self._yazma_oncesi()
        j, surum = self._hedef("itp", i, anahtar)
        try:
            kilitli_sil(self._c, "itp", self._ids["itp"][j], surum, self._kim(), self.kaynak,
                        "itp_kilitli_sil", f"{veri['no']} Rev.{veri['rev']}", gerekce.strip())
        finally:
            self.yeniden_yukle()

    # ── Şartname kütüphanesi (Plan 5b) ───────────────────────────────
    def get_sartname(self):         return self._data["sartname"]

    @staticmethod
    def _sartname_tutarli(*kayitlar):
        """Yazılan şartname kaydı tutarlı mı (5d: tablet de bu yoldan yazacak)."""
        from .itp import sartname   # geç: ITP motoru yalnız gerektiğinde yüklensin
        for r in kayitlar:
            if r is not None:
                sartname.tutarlilik_kontrol(r)

    def add_sartname(self, r):
        """Yalnız taslak; kurum + ad + rev tekil (doğrulama ORTA-2, DÜŞÜK-5)."""
        from .itp import sartname
        self._sartname_tutarli(r)
        sartname.ekle_kontrol(self._data["sartname"], r)
        return self._ekle("sartname", r)

    def update_sartname(self, i, r, anahtar=None):
        """Kilitli kayıt düzenlenmez; taslak → taslak / yürürlükte (revize yalnız yeni rev'le)."""
        from .itp import sartname
        self._sartname_tutarli(r)
        sartname.guncelle_kontrol(self._data["sartname"], self._hedef("sartname", i, anahtar)[0], r)
        self._guncelle("sartname", i, r, anahtar)

    def sartname_yeni_rev(self, i, eski, yeni, anahtar=None):
        """Kaynağı kilitleme (eski; None = zaten kilitli, dokunulmaz) + yeni taslak, tek işlem.
        Döner: yeni kaydın id'si."""
        from .itp import sartname
        self._sartname_tutarli(eski, yeni)
        self._yazma_oncesi()
        j, surum = self._hedef("sartname", i, anahtar)
        sartname.yeni_rev_kontrol(self._data["sartname"], j, eski, yeni)
        try:
            kid = rev_yaz(self._c, "sartname", self._ids["sartname"][j], eski, surum, yeni,
                          self._kim(), self.kaynak)
        finally:
            self.yeniden_yukle()
        return kid

    def delete_sartname(self, i, anahtar=None, gerekce=""):
        """Taslak: Düzenleyici+. Kilitli: yalnız Yönetici, gerekçe zorunlu; silme ve gerekçeli
        güvenlik kaydı tek işlemde."""
        from .itp import sartname
        j, __ = self._hedef("sartname", i, anahtar)
        veri = self._data["sartname"][j]
        sartname.sil_kontrol(veri, self.kullanici.rol if self.kullanici else None, gerekce)
        if veri["durum"] == sartname.TASLAK:
            self._sil("sartname", i, anahtar)
            return
        self._yazma_oncesi()
        j, surum = self._hedef("sartname", i, anahtar)
        try:
            kilitli_sil(self._c, "sartname", self._ids["sartname"][j], surum, self._kim(),
                        self.kaynak, "sartname_kilitli_sil", sartname.kayit_adi(veri),
                        gerekce.strip())
        finally:
            self.yeniden_yukle()

    def sartname_kilitli_duzelt(self, i, r, gerekce, anahtar=None):
        """B6: kilitli revizyonun maddesini yalnız Yönetici gerekçeyle düzeltir; güncelleme ve
        güvenlik kaydı tek işlemde."""
        from .itp import sartname
        self._yazma_oncesi()
        j, surum = self._hedef("sartname", i, anahtar)
        eski = self._data["sartname"][j]
        sartname.kilitli_duzelt_kontrol(eski, r, self.kullanici.rol if self.kullanici else None,
                                        gerekce)
        try:
            kilitli_duzelt_yaz(self._c, "sartname", self._ids["sartname"][j], r, surum,
                               self._kim(), self.kaynak, "sartname_kilitli_duzelt",
                               sartname.kayit_adi(eski), gerekce.strip())
        finally:
            self.yeniden_yukle()
