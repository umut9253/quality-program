# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""ITP/KP sipariş kaydı kuralları (Plan 5a). Qt'siz: masaüstü ve (5d) tablet aynı kodu kullanır.

Kayıt (veritabanı `itp` bölümü, JSON): no, rev, rev_sira, durum, baslik, sablon, kalemler,
onek_duzelt, siparis_ozel (5c), son_aktarim, goruntu, onay; isteğe bağlı sartnameler (5c-1:
[{"id": şartname kayıt id, "gruplar": [grup id]}], eksik = []).
- siparis_ozel (5c-1): {"kontrol", "sutun", "metin": {tr, en}, "kaynak": "siparis", "madde"}; madde
  None = hücre kararı (çakışma cevabı), [şartname id, madde id] = o maddenin çeviri cevabı.
- Durum: taslak → onayli (müşteri onayı) | revize ("Yeni rev"). Kaydetmek ve Excel'e aktarmak
  kilitlemez (K12). Kilitli kayıt düzenlenmez; Excel'i `goruntu`'dan üretilir.
- Kilitlenen görüntü = son Excel aktarımı (müşteriye giden); hiç aktarılmamışsa o an üretilir.
- rev_sira: aynı doküman no içinde revizyon sırası (rev metni "A"/"01" olabilir; sıra sayısal).
"""
import dataclasses
from datetime import date, datetime

from app import kimlik
from app.itp import goruntu
from app.itp.dokuman import Baslik, Dokuman, Kalem
from app.itp.kontrol import KONTROLLER
from app.itp.olustur import olustur
from app.itp.uygula import UygulamaHatasi, uygula
from app.search_utils import tr_fold
from app.dil import _

TASLAK, ONAYLI, REVIZE = "taslak", "onayli", "revize"
KILITLI = (ONAYLI, REVIZE)
ALANLAR = ("no", "rev", "rev_sira", "durum", "baslik", "sablon", "kalemler", "onek_duzelt",
           "siparis_ozel", "son_aktarim", "goruntu", "onay")


class KayitHatasi(Exception):
    """Kural ihlali; mesaj kullanıcıya gösterilir."""


def kayit_kur(sablon, baslik, kalemler, onek_duzelt=False):
    return {"no": baslik.dokuman_no.strip(), "rev": baslik.rev.strip(), "rev_sira": 0,
            "durum": TASLAK, "baslik": dataclasses.asdict(baslik), "sablon": sablon,
            "kalemler": [dataclasses.asdict(k) for k in kalemler],
            "onek_duzelt": bool(onek_duzelt), "siparis_ozel": [], "sartnameler": [],
            "son_aktarim": None,
            "goruntu": None, "onay": None}


def kilitli(veri):
    return veri["durum"] in KILITLI


def girdileri_guncelle(veri, sablon, baslik, kalemler, onek_duzelt):
    if kilitli(veri):
        raise KayitHatasi(_("Kayıt kilitli; düzenlenemez. Değişiklik için yeni rev açın."))
    yeni = kayit_kur(sablon, baslik, kalemler, onek_duzelt)
    for alan in ("rev_sira", "siparis_ozel", "son_aktarim"):
        yeni[alan] = veri[alan]
    yeni["sartnameler"] = veri.get("sartnameler", [])
    return yeni


def girdiler(veri):
    return (veri["sablon"], Baslik(**veri["baslik"]),
            tuple(Kalem(**k) for k in veri["kalemler"]), veri["onek_duzelt"])


def tutarlilik_kontrol(veri):
    """Veritabanına yazılan her ITP kaydı için (denetim BULGU-01): kilit yalnız onay / yeni rev
    akışından gelir; görüntüsüz kilitli kayıt açılınca çökerdi."""
    if not isinstance(veri, dict):
        raise KayitHatasi(_("Kayıt biçimi geçersiz."))
    eksik = [a for a in ALANLAR if a not in veri]
    if eksik:
        raise KayitHatasi(_("Kayıtta eksik alan: {d}").format(d=', '.join(eksik)))
    durum = veri["durum"]
    if durum not in (TASLAK,) + KILITLI:
        raise KayitHatasi(_("Bilinmeyen kayıt durumu: {durum!r}").format(durum=durum))
    if durum in KILITLI and not veri.get("goruntu"):
        raise KayitHatasi(_("Kilitli revizyonun anlık görüntüsü yok; kilit yalnız müşteri onayı "
                          "ya da «Yeni rev» ile konur."))
    if durum == ONAYLI and not veri.get("onay"):
        raise KayitHatasi(_("Onaylı revizyonda onay bilgisi yok."))
    _secim_kontrol(veri.get("sartnameler", []))
    _siparis_ozel_kontrol(veri["siparis_ozel"])


OZEL_SUTUNLAR = ("karakteristik", "kabul", "frekans", "sorumlu", "kayit", "denetim")
CEVIRI_SUTUNLARI = OZEL_SUTUNLAR + ("aktivite", "gerekce", "yeni_bolum")


def _tam_sayi(x):
    return isinstance(x, int) and not isinstance(x, bool)


def _secim_kontrol(sec):
    """5c-1: [{"id": şartname kayıt id, "gruplar": [grup id]}]."""
    if not (isinstance(sec, list) and all(
            isinstance(s, dict) and _tam_sayi(s.get("id")) and isinstance(s.get("gruplar"), list)
            and all(isinstance(g, str) for g in s["gruplar"]) for s in sec)):
        raise KayitHatasi(_("Şartname seçimi biçimi geçersiz."))


def _siparis_ozel_kontrol(oz):
    """5c-1: hücre kararı ("madde": None; sütun OZEL_SUTUNLAR) ya da çeviri cevabı
    ("madde": [şartname id, madde id]; sütun CEVIRI_SUTUNLARI)."""
    def gecerli(o):
        if not isinstance(o, dict):
            return False
        m = o.get("madde")
        metin = o.get("metin")
        return (o.get("kontrol") in KONTROLLER and o.get("kaynak") == "siparis"
                and isinstance(metin, dict)
                and all(isinstance(metin.get(d), str) for d in ("tr", "en"))
                and (o.get("sutun") in OZEL_SUTUNLAR if m is None else
                     isinstance(m, list) and len(m) == 2 and _tam_sayi(m[0])
                     and isinstance(m[1], str) and o.get("sutun") in CEVIRI_SUTUNLARI))
    if not (isinstance(oz, list) and all(gecerli(o) for o in oz)):
        raise KayitHatasi(_("Siparişe özel değer biçimi geçersiz."))


def dokuman_uret(veri, firma, sartname_kayitlari=None):
    """firma: ayardaki firma adı; yalnız taslak yeniden oluşturulurken kullanılır (kilitli
    belge görüntüsündeki adla kalır). sartname_kayitlari: şartname kayıt id → kayıt (5c-1); seçim
    varken verilmezse UygulamaHatasi (sessiz atlama yok)."""
    if kilitli(veri):
        d = goruntu.oku(veri["goruntu"])
        if not isinstance(d, Dokuman):
            raise goruntu.GoruntuHatasi(_("Kilitli revizyonun anlık görüntüsü yok ya da bozuk; "
                                        "Excel üretilemez."))
        return d
    sablon, baslik, kalemler, onek = girdiler(veri)
    if veri.get("sartnameler") and sartname_kayitlari is None:
        raise UygulamaHatasi(_("Şartname kayıtları verilmedi; şartnameli doküman üretilemez "
                               "(program hatası)."))
    d = olustur(sablon, baslik, kalemler, onek_duzelt=onek, firma=firma)
    return uygula(d, veri.get("sartnameler", []), sartname_kayitlari or {}, veri["siparis_ozel"])


def _anahtar(no, rev):
    return tr_fold(no.strip()), tr_fold(rev.strip())


def kaydet_kontrol(kayitlar, veri, haric=None, aile=True):
    """aile: aynı doküman no'lu başka kayıt varken yeni kayıt / no değişikliği reddedilir
    (revizyon zinciri rev_sira ile yalnız «Yeni rev»den büyür; yeni_rev aile=False verir)."""
    if not veri["no"].strip():
        raise KayitHatasi(_("Doküman No boş olamaz."))
    if kilitli(veri):
        raise KayitHatasi(_("Kayıt kilitli; kaydedilemez."))
    hedef = _anahtar(veri["no"], veri["rev"])
    for i, r in enumerate(kayitlar):
        if i != haric and _anahtar(r["no"], r["rev"]) == hedef:
            raise KayitHatasi(_("{d} Rev.{d2} zaten var.").format(d=veri['no'], d2=veri['rev']))
    if not aile:
        return
    no = hedef[0]
    ayni_aile = haric is not None and tr_fold(kayitlar[haric]["no"].strip()) == no
    if not ayni_aile and any(i != haric and tr_fold(r["no"].strip()) == no
                             for i, r in enumerate(kayitlar)):
        raise KayitHatasi(_("{d} doküman no'su zaten var; yeni revizyon için «Yeni rev»i kullanın.").format(d=veri['no']))


def aktarim_kaydi(veri, dokuman):
    if kilitli(veri):
        raise KayitHatasi(_("Kilitli kaydın aktarımı kayda geçmez."))
    return dict(veri, son_aktarim=goruntu.yaz(dokuman))


def _kilit_goruntusu(veri, firma, sartname_kayitlari=None):
    return veri["son_aktarim"] or goruntu.yaz(dokuman_uret(veri, firma, sartname_kayitlari))


def onayla(veri, tarih, not_, kim, firma, sartname_kayitlari=None):
    if veri["durum"] != TASLAK:
        raise KayitHatasi(_("Yalnız taslak revizyon onaylanabilir."))
    try:
        datetime.strptime(tarih.strip(), "%d.%m.%Y")
    except ValueError:
        raise KayitHatasi(_("Onay tarihi GG.AA.YYYY olmalı ('{tarih}').").format(tarih=tarih)) from None
    return dict(veri, durum=ONAYLI, goruntu=_kilit_goruntusu(veri, firma, sartname_kayitlari),
                onay={"tarih": tarih.strip(), "not": not_.strip(), "kaydeden": kim})


def en_yuksek_mi(kayitlar, veri):
    no = tr_fold(veri["no"].strip())
    return veri["rev_sira"] == max(r["rev_sira"] for r in kayitlar
                                   if tr_fold(r["no"].strip()) == no)


def _sonraki_rev(rev):
    r = rev.strip()
    if not r.isdigit():
        raise KayitHatasi(_("Rev '{rev}' sayısal değil; yeni rev'i girin.").format(rev=rev))
    return str(int(r) + 1).zfill(len(r))


def yeni_rev(kayitlar, veri, yeni_rev=None, *, firma, sartname_kayitlari=None):
    # revize kaynak da olabilir: üstündeki taslak silinmişse en yüksek odur (numara sıkışmasın)
    if not en_yuksek_mi(kayitlar, veri):
        raise KayitHatasi(_("Yeni rev yalnız en son revizyondan açılır."))
    rev = (yeni_rev or "").strip() or _sonraki_rev(veri["rev"])
    yeni = dict(veri, rev=rev, rev_sira=veri["rev_sira"] + 1, durum=TASLAK,
                baslik=dict(veri["baslik"], rev=rev), son_aktarim=None, goruntu=None, onay=None)
    kaydet_kontrol(kayitlar, yeni, aile=False)
    eski = None if kilitli(veri) else dict(
        veri, durum=REVIZE, goruntu=_kilit_goruntusu(veri, firma, sartname_kayitlari))
    return eski, yeni


def kilitlenen_kaynak_kontrol(kaynak, eski):
    """«Yeni rev»de taslak kaynak olduğu gibi revize olur (Antigravity 5b-1 BULGU-01): yalnız durum
    ve kilit görüntüsü eklenir; son aktarım varsa görüntü odur."""
    def icerik(v):
        return {a: x for a, x in v.items() if a not in ("durum", "goruntu")}
    if (icerik(eski) != icerik(kaynak) or eski["durum"] != REVIZE
            or (kaynak["son_aktarim"] and eski["goruntu"] != kaynak["son_aktarim"])):
        raise KayitHatasi(_("Yeni rev'de kaynak olduğu gibi kilitlenir; içeriği değişmez."))


def ekle_kontrol(kayitlar, veri):
    """Veritabanı katmanı (Antigravity BULGU-06; 5d: tablet de bu yoldan yazacak): yeni kayıt
    yalnız taslak ve rev_sira 0; no + rev tekil, var olan doküman no'su yalnız «Yeni rev»le büyür."""
    if veri["durum"] != TASLAK:
        raise KayitHatasi(_("Yeni kayıt yalnız taslak olarak eklenir."))
    if veri["rev_sira"] != 0:
        raise KayitHatasi(_("Yeni kayıt rev_sira=0 ile başlar; sıra yalnız «Yeni rev»le artar."))
    kaydet_kontrol(kayitlar, veri)


def guncelle_kontrol(kayitlar, j, veri):
    """Taslak → taslak (kaydet, aktarım) ya da onaylı (yalnız onay ve kilit görüntüsü eklenir);
    revize yalnız «Yeni rev»le."""
    eski = kayitlar[j]
    if kilitli(eski):
        raise KayitHatasi(_("Kayıt kilitli; düzenlenemez. Değişiklik için yeni rev açın."))
    if veri["durum"] == REVIZE:
        raise KayitHatasi(_("Revize durumu yalnız «Yeni rev»le verilir."))
    if veri["rev_sira"] != eski["rev_sira"]:
        raise KayitHatasi(_("Revizyon sırası değiştirilemez."))
    if veri["durum"] == ONAYLI:
        def icerik(v):
            return {a: x for a, x in v.items() if a not in ("durum", "goruntu", "onay")}
        if icerik(veri) != icerik(eski):
            raise KayitHatasi(_("Onay kaydın içeriğini değiştirmez; önce kaydedin."))
        if eski["son_aktarim"] and veri["goruntu"] != eski["son_aktarim"]:
            raise KayitHatasi(_("Onayda kilit görüntüsü son Excel aktarımıdır (müşteriye giden)."))
        return
    no = tr_fold(eski["no"].strip())
    if (tr_fold(veri["no"].strip()) != no
            and sum(tr_fold(r["no"].strip()) == no for r in kayitlar) > 1):
        raise KayitHatasi(_("Başka revizyonu olan dokümanın no'su değiştirilemez (revizyon zinciri "
                          "bölünür)."))
    kaydet_kontrol(kayitlar, veri, haric=j)


def yeni_rev_kontrol(kayitlar, j, eski, yeni):
    """Kaynak taslaksa eski = kaynağın revize hali; kilitliyse eski None (dokunulmaz). Yeni kayıt
    aynı doküman no'sunun bir sonraki taslağı (sartname.yeni_rev_kontrol ile aynı kurallar)."""
    kaynak = kayitlar[j]
    if eski is None and not kilitli(kaynak):
        raise KayitHatasi(_("Taslak kaynak yeni rev'de revize olarak kilitlenmeli."))
    if eski is not None:
        if kilitli(kaynak):
            raise KayitHatasi(_("Kayıt kilitli; düzenlenemez. Değişiklik için yeni rev açın."))
        kilitlenen_kaynak_kontrol(kaynak, eski)
    if not en_yuksek_mi(kayitlar, kaynak):
        raise KayitHatasi(_("Yeni rev yalnız en son revizyondan açılır."))
    if (yeni["durum"] != TASLAK or tr_fold(yeni["no"].strip()) != tr_fold(kaynak["no"].strip())
            or yeni["rev_sira"] != kaynak["rev_sira"] + 1):
        raise KayitHatasi(_("Yeni rev aynı dokümanın bir sonraki taslağı olmalı."))
    kaydet_kontrol(kayitlar, yeni, aile=False)


def kopyala(kayitlar, veri, yeni_no):
    no = yeni_no.strip()
    if not no:
        raise KayitHatasi(_("Doküman No boş olamaz."))
    if any(tr_fold(r["no"].strip()) == tr_fold(no) for r in kayitlar):
        raise KayitHatasi(_("{no} doküman no'su zaten var; yeni revizyon için «Yeni rev»i kullanın.").format(no=no))
    baslik = dict(veri["baslik"], dokuman_no=no, rev="0",
                  tarih=date.today().strftime("%d.%m.%Y"))
    return dict(veri, no=no, rev="0", rev_sira=0, durum=TASLAK, baslik=baslik,
                son_aktarim=None, goruntu=None, onay=None)


def sil_kontrol(veri, rol, gerekce):
    if veri["durum"] == TASLAK:
        if rol is not None and not kimlik.yetkili(rol, kimlik.DUZENLEYICI):
            raise KayitHatasi(_("Taslağı silmeye yetkiniz yok."))
        return
    if rol is not None and rol != kimlik.YONETICI:
        raise KayitHatasi(_("Kilitli revizyonu yalnız yönetici silebilir."))
    if not gerekce.strip():
        raise KayitHatasi(_("Kilitli revizyon silinirken gerekçe zorunludur."))


def durum_metni(veri):
    if veri["durum"] == ONAYLI:
        return _("🔒 Onaylı ({d})").format(d=veri['onay']['tarih'])
    if veri["durum"] == REVIZE:
        return _("🔒 Revize edildi")
    return _("Taslak")
