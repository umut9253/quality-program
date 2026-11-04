# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Şartname kütüphanesi kuralları (Plan 5b). Qt'siz: masaüstü ve (5d) tablet aynı kodu kullanır.

Kayıt (veritabanı `sartname` bölümü, JSON; bir kayıt = bir revizyon): kurum, ad, tur (genel /
ozel = özel teknik), no, rev, rev_sira, yayim_tarihi, kaynak_klasor, not, durum, gruplar, maddeler.
- Durum: taslak → yururlukte ("Yürürlüğe al") | revize ("Yeni rev"). Kilitli kayıt düzenlenmez;
  yanlış maddeyi yalnız Yönetici gerekçeyle düzeltir (kilitli_duzelt_kontrol, B6).
- Aile = aynı kurum + ad; revizyon zinciri rev_sira ile yalnız "Yeni rev"den büyür.
- Madde türleri: sayisal / metin / ek_satir / uygulanmaz; hedef `kontrol` ortak kontrol
  listesinden (app/itp/kontrol.py). grup "" = zorunlu, dolu = isteğe bağlı grubun id'si (B1, B2).
"""
import math

from app import kimlik
from app.itp.kontrol import KONTROLLER
from app.search_utils import tr_fold
from app.dil import N_, _

TASLAK, YURURLUKTE, REVIZE = "taslak", "yururlukte", "revize"
KILITLI = (YURURLUKTE, REVIZE)
TURLER = ("genel", "ozel")
MADDE_TURLERI = ("sayisal", "metin", "ek_satir", "uygulanmaz")
SUTUNLAR = ("karakteristik", "kabul", "frekans", "kayit", "denetim")
SATIR_ALANLARI = ("aktivite", "karakteristik", "kabul", "frekans", "sorumlu", "kayit", "denetim")
_SATIR_ADI = {"aktivite": N_("aktivite"), "karakteristik": N_("karakteristik"),
              "kabul": N_("kabul kriteri"), "frekans": N_("frekans"), "sorumlu": N_("sorumlu"),
              "kayit": N_("kayıt"), "denetim": N_("denetim")}
ALANLAR = ("kurum", "ad", "tur", "no", "rev", "rev_sira", "yayim_tarihi", "kaynak_klasor", "not",
           "durum", "gruplar", "maddeler")
_METIN_ALANLARI = ("kurum", "ad", "no", "rev", "yayim_tarihi", "kaynak_klasor", "not")


class SartnameHatasi(Exception):
    """Kural ihlali; mesaj kullanıcıya gösterilir."""


def kayit_kur(kurum, ad, tur="genel"):
    return {"kurum": kurum.strip(), "ad": ad.strip(), "tur": tur, "no": "", "rev": "0",
            "rev_sira": 0, "yayim_tarihi": "", "kaynak_klasor": "", "not": "", "durum": TASLAK,
            "gruplar": [], "maddeler": []}


def kilitli(veri):
    return veri["durum"] in KILITLI


def kayit_adi(veri):
    return f"{veri['kurum']} / {veri['ad']} Rev.{veri['rev']}"


def _aile(veri):
    return tr_fold(veri["kurum"].strip()), tr_fold(veri["ad"].strip())


def kaydet_kontrol(kayitlar, veri, haric=None, aile=True):
    """aile: aynı kurum + ad'lı başka kayıt varken yeni kayıt / ad değişikliği reddedilir
    (yeni revizyon yalnız «Yeni rev»le; yeni_rev aile=False verir)."""
    if not veri["kurum"].strip():
        raise SartnameHatasi(_("Kurum boş olamaz."))
    if not veri["ad"].strip():
        raise SartnameHatasi(_("Şartname adı boş olamaz."))
    if kilitli(veri):
        raise SartnameHatasi(_("Kayıt kilitli; kaydedilemez."))
    tekillik_kontrol(kayitlar, veri, haric, aile)


def tekillik_kontrol(kayitlar, veri, haric=None, aile=True):
    """Kurum + ad + rev tekil; aile=True ise başka kayıt aynı aileye giremez."""
    hedef = _aile(veri) + (tr_fold(veri["rev"].strip()),)
    for i, r in enumerate(kayitlar):
        if i != haric and _aile(r) + (tr_fold(r["rev"].strip()),) == hedef:
            raise SartnameHatasi(_("{d} zaten var.").format(d=kayit_adi(veri)))
    if not aile:
        return
    ayni_aile = haric is not None and _aile(kayitlar[haric]) == _aile(veri)
    if not ayni_aile and any(i != haric and _aile(r) == _aile(veri)
                             for i, r in enumerate(kayitlar)):
        raise SartnameHatasi(_("{d} / {d2} zaten var; yeni revizyon için «Yeni rev»i kullanın.").format(d=veri['kurum'], d2=veri['ad']))


def _metin(x, yer, tam):
    if not (isinstance(x, dict) and isinstance(x.get("tr"), str)
            and isinstance(x.get("en"), str)):
        raise SartnameHatasi(_("{yer}: TR/EN metin alanı geçersiz.").format(yer=yer))
    if tam and not x["tr"].strip():
        raise SartnameHatasi(_("{yer}: TR metin boş.").format(yer=yer))


def _sayi_ya_da_bos(x):
    return x is None or (isinstance(x, (int, float)) and not isinstance(x, bool)
                         and not (isinstance(x, float) and not math.isfinite(x)))


def _aralik(x, yer):
    """Çap / et aralığı; kullanıcı kararı 2026-11-02: alt sınır kesin pozitif."""
    if x is None:
        return
    if not (isinstance(x, list) and len(x) == 2 and all(v is not None and _sayi_ya_da_bos(v)
                                                        for v in x) and 0 < x[0] <= x[1]):
        raise SartnameHatasi(_("{yer}: aralık [en az, en çok] olmalı.").format(yer=yer))


def madde_dogrula(m, grup_idleri, tam=False):
    """Yapı her yazmada denetlenir; tam=True (yürürlüğe alma / kilitli kayıt) içerik de dolu."""
    if not isinstance(m, dict):
        raise SartnameHatasi(_("Madde biçimi geçersiz."))
    yer = _("Madde {d}").format(d=m.get('kaynak') or m.get('id') or '?')
    for a in ("id", "kontrol", "grup", "kaynak", "tur"):
        if not isinstance(m.get(a), str):
            raise SartnameHatasi(_("{yer}: '{a}' alanı eksik.").format(yer=yer, a=a))
    if not m["id"]:
        raise SartnameHatasi(_("{yer}: id boş.").format(yer=yer))
    if m["kontrol"] not in KONTROLLER:
        raise SartnameHatasi(_("{yer}: bilinmeyen kontrol '{d}'.").format(yer=yer, d=m['kontrol']))
    if m["grup"] and m["grup"] not in grup_idleri:
        raise SartnameHatasi(_("{yer}: tanımsız grup '{d}'.").format(yer=yer, d=m['grup']))
    tur = m["tur"]
    if tur == "sayisal":
        if m.get("kriter") not in KONTROLLER[m["kontrol"]]["kriterler"]:
            raise SartnameHatasi(_("{yer}: '{d}' kontrolünde '{d2}' sayısal kriteri yok.").format(yer=yer, d=m['kontrol'], d2=m.get('kriter')))
        alt, ust = m.get("alt"), m.get("ust")
        if not (_sayi_ya_da_bos(alt) and _sayi_ya_da_bos(ust)
                and isinstance(m.get("birim"), str)):
            raise SartnameHatasi(_("{yer}: alt/üst sayı ya da boş, birim metin olmalı.").format(yer=yer))
        if alt is not None and ust is not None and alt > ust:
            raise SartnameHatasi(_("{yer}: alt sınır üst sınırdan büyük.").format(yer=yer))
        if tam and alt is None and ust is None:
            raise SartnameHatasi(_("{yer}: alt ya da üst sınırdan en az biri girilmeli.").format(yer=yer))
        _aralik(m.get("cap_aralik"), _("{yer} çap").format(yer=yer))
        _aralik(m.get("et_aralik"), _("{yer} et").format(yer=yer))
    elif tur == "metin":
        if m.get("sutun") not in SUTUNLAR:
            raise SartnameHatasi(_("{yer}: değişen sütun {SUTUNLAR} olmalı.").format(yer=yer, SUTUNLAR=SUTUNLAR))
        _metin(m.get("metin"), yer, tam)
    elif tur == "ek_satir":
        satir = m.get("satir")
        if not isinstance(satir, dict):
            raise SartnameHatasi(_("{yer}: ek satır TR/EN metin alanı geçersiz.").format(yer=yer))
        for a in SATIR_ALANLARI:
            _metin(satir.get(a), _("{yer} {alan}").format(yer=yer, alan=_(_SATIR_ADI[a])),
                   tam and a in ("karakteristik", "kabul"))   # Antigravity BULGU-02
        if m.get("yeni_bolum") is not None:
            _metin(m["yeni_bolum"], _("{yer} yeni bölüm").format(yer=yer), tam)
    elif tur == "uygulanmaz":
        _metin(m.get("gerekce"), _("{yer} gerekçe").format(yer=yer), tam)
    else:
        raise SartnameHatasi(_("{yer}: bilinmeyen madde türü '{tur}'.").format(yer=yer, tur=tur))


def tutarlilik_kontrol(veri):
    """Veritabanına yazılan her şartname kaydı (5a denetim BULGU-01 dersi): biçim, durum,
    gruplar, madde yapısı; kilitli kayıtta içerik de tam (yürürlüğe alma koşulu korunur)."""
    if not isinstance(veri, dict):
        raise SartnameHatasi(_("Kayıt biçimi geçersiz."))
    eksik = [a for a in ALANLAR if a not in veri]
    if eksik:
        raise SartnameHatasi(_("Kayıtta eksik alan: {d}").format(d=', '.join(eksik)))
    if veri["durum"] not in (TASLAK,) + KILITLI:
        raise SartnameHatasi(_("Bilinmeyen kayıt durumu: {d!r}").format(d=veri['durum']))
    if veri["tur"] not in TURLER:
        raise SartnameHatasi(_("Bilinmeyen şartname türü: {d!r}").format(d=veri['tur']))
    for a in _METIN_ALANLARI:
        if not isinstance(veri[a], str):
            raise SartnameHatasi(_("'{a}' alanı metin olmalı.").format(a=a))
    if not isinstance(veri["rev_sira"], int) or isinstance(veri["rev_sira"], bool):
        raise SartnameHatasi(_("rev_sira tam sayı olmalı."))
    if not (isinstance(veri["gruplar"], list) and isinstance(veri["maddeler"], list)):
        raise SartnameHatasi(_("Gruplar ve maddeler liste olmalı."))
    tam = kilitli(veri)
    if tam and not (veri["ad"].strip() and veri["rev"].strip()):
        raise SartnameHatasi(_("Kilitli şartnamede ad ve rev boş olamaz."))
    if tam and not veri["maddeler"]:
        raise SartnameHatasi(_("Kilitli şartnamede en az bir madde olmalı."))
    idler = []
    for g in veri["gruplar"]:
        if not (isinstance(g, dict) and isinstance(g.get("id"), str) and g["id"]):
            raise SartnameHatasi(_("Grup biçimi geçersiz."))
        _metin(g.get("ad"), _("Grup {d}").format(d=g['id']), tam)
        idler.append(g["id"])
    if len(set(idler)) != len(idler):
        raise SartnameHatasi(_("Grup id'leri tekrar ediyor."))
    midler = []
    for m in veri["maddeler"]:
        madde_dogrula(m, idler, tam=tam)
        midler.append(m["id"])
    if len(set(midler)) != len(midler):
        raise SartnameHatasi(_("Madde id'leri tekrar ediyor."))


def yururluge_al(veri):
    if veri["durum"] != TASLAK:
        raise SartnameHatasi(_("Yalnız taslak revizyon yürürlüğe alınabilir."))
    if not veri["ad"].strip() or not veri["rev"].strip():
        raise SartnameHatasi(_("Şartname adı ve rev boş olamaz."))
    if not veri["maddeler"]:
        raise SartnameHatasi(_("Yürürlüğe almak için en az bir madde olmalı."))
    yeni = dict(veri, durum=YURURLUKTE)
    tutarlilik_kontrol(yeni)
    return yeni


def en_yuksek_mi(kayitlar, veri):
    siralar = [r["rev_sira"] for r in kayitlar if _aile(r) == _aile(veri)]
    if not siralar:
        raise SartnameHatasi(_("{d} / {d2} kayıtlarda yok; liste yenilenmiş olabilir.").format(d=veri['kurum'], d2=veri['ad']))
    return veri["rev_sira"] == max(siralar)


def _sonraki_rev(rev):
    r = rev.strip()
    if not r.isdigit():
        raise SartnameHatasi(_("Rev '{rev}' sayısal değil; yeni rev'i girin.").format(rev=rev))
    return str(int(r) + 1).zfill(len(r))


def yeni_rev(kayitlar, veri, yeni_rev=None):
    """Kaynak taslaksa revize olur (kilitlenir); zaten kilitliyse dokunulmaz (eski None)."""
    if not en_yuksek_mi(kayitlar, veri):
        raise SartnameHatasi(_("Yeni rev yalnız en son revizyondan açılır."))
    rev = (yeni_rev or "").strip() or _sonraki_rev(veri["rev"])
    yeni = dict(veri, rev=rev, rev_sira=veri["rev_sira"] + 1, durum=TASLAK)
    kaydet_kontrol(kayitlar, yeni, aile=False)
    eski = None if kilitli(veri) else dict(veri, durum=REVIZE)
    return eski, yeni


def ekle_kontrol(kayitlar, veri):
    """Veritabanı katmanı (5d: tablet de bu yoldan yazacak): yeni kayıt yalnız taslak."""
    if veri["durum"] != TASLAK:
        raise SartnameHatasi(_("Yeni şartname yalnız taslak olarak eklenir."))
    if veri["rev_sira"] != 0:
        raise SartnameHatasi(_("Yeni şartname rev_sira=0 ile başlar; sıra yalnız «Yeni rev»le artar."))
    tekillik_kontrol(kayitlar, veri)


def guncelle_kontrol(kayitlar, j, veri):
    """Taslak → taslak ya da yürürlükte; revize yalnız «Yeni rev»le."""
    if kilitli(kayitlar[j]):
        raise SartnameHatasi(_("Şartname kilitli; düzenlenemez. Değişiklik için yeni rev açın."))
    if veri["durum"] == REVIZE:
        raise SartnameHatasi(_("Revize durumu yalnız «Yeni rev»le verilir."))
    if veri["rev_sira"] != kayitlar[j]["rev_sira"]:
        raise SartnameHatasi(_("Revizyon sırası değiştirilemez."))
    if _aile(veri) != _aile(kayitlar[j]) and sum(_aile(r) == _aile(kayitlar[j])
                                                 for r in kayitlar) > 1:
        raise SartnameHatasi(_("Başka revizyonu olan şartnamenin kurum/adı değiştirilemez "
                             "(revizyon zinciri bölünür)."))
    if veri["tur"] != kayitlar[j]["tur"] and sum(_aile(r) == _aile(kayitlar[j])
                                                  for r in kayitlar) > 1:
        raise SartnameHatasi(_("Başka revizyonu olan şartnamenin türü değiştirilemez."))
    tekillik_kontrol(kayitlar, veri, haric=j)


def yeni_rev_kontrol(kayitlar, j, eski, yeni):
    """Kaynak taslaksa eski = kaynağın revize hali; kaynak kilitliyse eski None (dokunulmaz).
    Yeni kayıt aynı ailede taslak."""
    kaynak = kayitlar[j]
    if eski is not None and kilitli(kaynak):
        raise SartnameHatasi(_("Şartname kilitli; düzenlenemez. Değişiklik için yeni rev açın."))
    if eski is None and not kilitli(kaynak):
        raise SartnameHatasi(_("Taslak kaynak yeni rev'de revize olarak kilitlenmeli."))
    if eski is not None and eski["durum"] != REVIZE:
        raise SartnameHatasi(_("Kaynak yeni rev'de revize olur."))
    if eski is not None and eski != dict(kaynak, durum=REVIZE):    # Antigravity 5b-1 BULGU-01
        raise SartnameHatasi(_("Yeni rev'de kaynak olduğu gibi kilitlenir; kimliği ve içeriği "
                             "değişmez."))
    if not en_yuksek_mi(kayitlar, kaynak):
        raise SartnameHatasi(_("Yeni rev yalnız en son revizyondan açılır."))
    if (yeni["durum"] != TASLAK or _aile(yeni) != _aile(kaynak)
            or yeni["rev_sira"] != kaynak["rev_sira"] + 1):
        raise SartnameHatasi(_("Yeni rev aynı şartnamenin bir sonraki taslağı olmalı."))
    if yeni["tur"] != kaynak["tur"]:
        raise SartnameHatasi(_("Yeni rev kaynağın türünü taşır; tür değiştirilemez."))
    tekillik_kontrol(kayitlar, yeni, aile=False)


def kopyala(kayitlar, veri, yeni_ad):
    ad = yeni_ad.strip()
    if not ad:
        raise SartnameHatasi(_("Şartname adı boş olamaz."))
    yeni = dict(veri, ad=ad, rev="0", rev_sira=0, durum=TASLAK)
    if any(_aile(r) == _aile(yeni) for r in kayitlar):
        raise SartnameHatasi(_("{d} / {ad} zaten var; yeni revizyon için «Yeni rev»i kullanın.").format(d=veri['kurum'], ad=ad))
    return yeni


def sil_kontrol(veri, rol, gerekce):
    if veri["durum"] == TASLAK:
        if rol is not None and not kimlik.yetkili(rol, kimlik.DUZENLEYICI):
            raise SartnameHatasi(_("Taslağı silmeye yetkiniz yok."))
        return
    if rol is not None and rol != kimlik.YONETICI:
        raise SartnameHatasi(_("Kilitli şartnameyi yalnız yönetici silebilir."))
    if not gerekce.strip():
        raise SartnameHatasi(_("Kilitli şartname silinirken gerekçe zorunludur."))


def kilitli_duzelt_kontrol(eski, yeni, rol, gerekce):
    """B6: kilitli revizyondaki yanlış maddeyi yalnız Yönetici gerekçeyle düzeltir. Kimlik alanları
    ve durum değişmez (değişiklik gerekiyorsa yeni rev); içerik tam olmalı."""
    if not kilitli(eski):
        raise SartnameHatasi(_("Taslak kayıt normal kaydedilir; düzeltme yalnız kilitli kayıtta."))
    if rol is not None and rol != kimlik.YONETICI:
        raise SartnameHatasi(_("Kilitli şartnameyi yalnız yönetici düzeltebilir."))
    if not gerekce.strip():
        raise SartnameHatasi(_("Düzeltme gerekçesi zorunludur."))
    for a in ("kurum", "ad", "tur", "rev", "rev_sira", "durum"):
        if yeni.get(a) != eski[a]:
            raise SartnameHatasi(_("Kilitli kayıtta '{a}' değiştirilemez; yeni rev açın.").format(a=a))
    tutarlilik_kontrol(yeni)


def durum_metni(veri):
    if veri["durum"] == YURURLUKTE:
        return _("🔒 Yürürlükte")
    if veri["durum"] == REVIZE:
        return _("🔒 Revize edildi")
    return _("Taslak")


def tur_metni(veri):
    return _("Özel teknik") if veri["tur"] == "ozel" else _("Genel")
