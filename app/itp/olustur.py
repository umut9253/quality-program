# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Şablon + kalemler → Dokuman (Plan 2).

Her kalem için Plan 1 boru_hesapla çalışır; şablonun metin parçalarındaki {yer_tutucu}'lar
kalem başına doldurulup karar C ile gruplanır, bloklar kalem tablosu, {"elle": ...}
ELLE GİRİLECEK olur. Tanımsız ad sessizce geçmez: SablonHatasi.
"""
import dataclasses
import importlib
from string import Formatter

from app.firma import ad_dogrula
from app.itp.aralik import EslesmeHatasi
from app.itp.dokuman import (DIS_KAPLAMALAR, IC_KAPLAMALAR, PSL_DEGERLERI, Bolum, Denetim,
                             Dokuman, ElleGirilecek, Metin, Sartname, Satir)
from app.itp.hesap import BoruGirdisi, boru_hesapla
from app.itp.yer_tutucu import (BLOKLAR, URETECLER, YER_TUTUCULAR, SablonHatasi, grupla,
                                kalem_etiketi)
from app.dil import _

SABLONLAR = ("itp_en", "kp_ciplak", "kp_kaplama")
KOSUL_ALANLARI = ("dis_kaplama", "ic_kaplama", "psl")
KOSUL_DEGERLERI = {"dis_kaplama": DIS_KAPLAMALAR, "ic_kaplama": IC_KAPLAMALAR,
                   "psl": PSL_DEGERLERI}


def sablon_modulu(sablon):
    if isinstance(sablon, str):
        if sablon not in SABLONLAR:
            raise SablonHatasi(_("tanımsız şablon '{sablon}' {SABLONLAR}").format(sablon=sablon, SABLONLAR=SABLONLAR))
        return importlib.import_module(f"app.itp.sablon.{sablon}")
    return sablon


def yer_tutucu_adlari(metin):
    return [ad for __, ad, __, __ in Formatter().parse(metin) if ad]


def _kapsam(kosul, kalemler, sonuclar, yer):
    if kosul is None:
        return list(zip(kalemler, sonuclar))
    alan, __, degerler = kosul.partition("=")
    if alan not in KOSUL_ALANLARI or not degerler:
        raise SablonHatasi(_("{yer}: geçersiz koşul '{kosul}'").format(yer=yer, kosul=kosul))
    izinli = degerler.split("|")
    for v in izinli:
        if v not in KOSUL_DEGERLERI[alan]:
            raise SablonHatasi(_("{yer}: bilinmeyen koşul değeri '{v}' ({alan})").format(yer=yer, v=v, alan=alan))
    return [(k, r) for k, r in zip(kalemler, sonuclar) if getattr(k, alan) in izinli]


def _kalemli(nolar, fn, *args):
    """fn(*args) çağırır; EslesmeHatasi'na kalem no(lar)ını ekler."""
    try:
        return fn(*args)
    except EslesmeHatasi as e:
        raise EslesmeHatasi(f"{kalem_etiketi(nolar, 'tr')}: {e}") from e


def _parca(p, kapsam, dil, yer, firma):
    """Kabul parçası → parça tuple'ı (blok birden çok parça döndürebilir, 2026-11-03)."""
    if isinstance(p, str):
        adlar = yer_tutucu_adlari(p)
        sabit = {"firma": firma} if "firma" in adlar else {}   # belge geneli: kalemden bağımsız
        adlar = [ad for ad in adlar if ad not in sabit]
        if not adlar:
            return (Metin(p.format_map(sabit) if sabit else p),)
        for ad in adlar:
            if ad not in YER_TUTUCULAR:
                raise SablonHatasi(_("{yer}: tanımsız yer tutucu '{ad}'").format(yer=yer, ad=ad))
        metinler = [p.format_map({**sabit, **{ad: _kalemli([k.no], YER_TUTUCULAR[ad], k, r, dil)
                                             for ad in adlar}})
                    for k, r in kapsam]
        return (Metin(grupla([k.no for k, __ in kapsam], metinler, dil)),)
    if isinstance(p, dict) and "blok" in p:
        if p["blok"] not in BLOKLAR:
            raise SablonHatasi(_("{yer}: tanımsız blok '{d}'").format(yer=yer, d=p['blok']))
        sonuc = _kalemli([k.no for k, __ in kapsam], BLOKLAR[p["blok"]],
                         [k for k, __ in kapsam], [r for __, r in kapsam], dil)
        return sonuc if isinstance(sonuc, tuple) else (sonuc,)
    if isinstance(p, dict) and "elle" in p:
        return (ElleGirilecek(p["elle"]),)
    raise SablonHatasi(_("{yer}: tanımsız kabul parçası {p!r}").format(yer=yer, p=p))


def _kabul_parcalari(d, kapsam, dil, yer, firma):
    return tuple(x for p in d["kabul"] for x in _parca(p, kapsam, dil, yer, firma))


def _satir(d, kapsam, dil, yer, firma):
    """Satır; "kosul" varsa yalnızca uyan kalemler üzerinden (uyan yoksa None). Kapsam
    bölümünkinden darsa karakteristiğe kalem etiketi eklenir."""
    yer = f"{yer} satır {d.get('no') or d.get('karakteristik')}"
    for anahtar in ("firma", "kabul"):
        if anahtar not in d:
            raise SablonHatasi(_("{yer}: satırda '{anahtar}' eksik").format(yer=yer, anahtar=anahtar))
    karakteristik = d.get("karakteristik", "")
    if "kosul" in d:
        uyan = _kapsam(d["kosul"], [k for k, __ in kapsam], [r for __, r in kapsam], yer)
        if not uyan:
            return None
        if len(uyan) < len(kapsam):
            karakteristik += f" ({kalem_etiketi([k.no for k, __ in uyan], dil)})"
        kapsam = uyan
    return Satir(no=d.get("no", ""), aktivite=d.get("aktivite", ""), spec=d.get("spec", ""),
                 sorumlu=d.get("sorumlu", ""), karakteristik=karakteristik,
                 frekans=d.get("frekans", ""), kayit=d.get("kayit", ""),
                 denetim=Denetim(d["firma"]),
                 kabul=_kabul_parcalari(d, kapsam, dil, yer, firma))


def _satirlar(d, kapsam, dil, yer, firma):
    """Şablon satırı → Satir'lar. "kalite_basina": (grade, PSL) grubu başına bir Satir (Word
    ITP çekme); ilki no/aktivite/spec/sorumlu/karakteristik ve şablonun tüm kabul
    parçalarını taşır; sonrakilerde bu alanlar boş, kabulde yalnız bloklar ve son parça (atıf)
    kalır: genel dipnotlar her kalitede tekrarlanmaz."""
    ilk = _satir(d, kapsam, dil, yer, firma)
    if ilk is None or not d.get("kalite_basina"):
        return () if ilk is None else (ilk,)
    yer = f"{yer} satır {d.get('no') or d.get('karakteristik')}"
    if "kosul" in d:
        kapsam = _kapsam(d["kosul"], [k for k, __ in kapsam], [r for __, r in kapsam], yer)
    gruplar = {}
    for k, r in kapsam:
        gruplar.setdefault((k.grade, k.psl), []).append((k, r))
    if len(gruplar) == 1:
        return (ilk,)
    son = len(d["kabul"]) - 1
    devam = dict(d, kabul=[p for i, p in enumerate(d["kabul"])
                           if i == son or (isinstance(p, dict) and "blok" in p)])
    out = []
    for i, uyelar in enumerate(gruplar.values()):
        kabul = _kabul_parcalari(d if i == 0 else devam, uyelar, dil, yer, firma)
        bos = {} if i == 0 else dict(no="", aktivite="", spec="", sorumlu="", karakteristik="")
        out.append(dataclasses.replace(ilk, kabul=kabul, **bos))
    return tuple(out)


def _araya_koy(satirlar, sonra, yeni, yer):
    """yeni (bir şablon satırının Satir'ları, sırasıyla) karakteristiği `sonra` olan son satırın
    arkasına devam satırı olarak konur (üretilmiş devam satırları gibi spec korunur)."""
    i = next((i for i in range(len(satirlar) - 1, -1, -1)
              if satirlar[i].karakteristik == sonra), None)
    if i is None:
        raise SablonHatasi(_("{yer}: '{d}' satırı bulunamadı ('sonra')").format(yer=yer, d=sonra))
    yeni = tuple(dataclasses.replace(x, no="", aktivite="") for x in yeni)
    return satirlar[:i + 1] + yeni + satirlar[i + 1:]


def _son_no(satirlar):
    return next((x.no for x in reversed(satirlar) if x.no), "")


class NumaraOnekiHatasi(SablonHatasi):
    """Satır no öneki bölüm no'su değil (V-5); `sorunlar` tüm uyumsuz satırları listeler ki
    GUI kullanıcıya düzeltme onayını tek seferde sorsun (U-2)."""

    def __init__(self, sorunlar):
        self.sorunlar = tuple(sorunlar)
        super().__init__("; ".join(f"{s}: satır no öneki bölüm no'su değil"
                                   for s in self.sorunlar))


def numaralari_sirala(bolumler, ayrilmis=(), onek_duzelt=False):
    """Bölüm/satır no'larını dokümandaki sıraya göre yeniden yazar (Task 12, V-2/V-3).

    Bölümler 1'den boşluksuz numaralanır; `ayrilmis` (ör. KP'de "2" = şartname listesi)
    atlanır. Satır no'su: "" → ""; eski bölüm no'su → yeni bölüm no'su; "B.k" (k sayı) →
    "yeni.sıra" (sıra bölüm içinde 1'den); "B.T" gibi sayısal olmayan ek korunur, yalnızca
    önek değişir. Önek eski bölüm no'su değilse NumaraOnekiHatasi (sessiz yanlış numara
    yok); kullanıcı onaylarsa `onek_duzelt=True` ile önek yok sayılır ve satır bulunduğu
    bölüme göre numaralanır (U-2). Tekrar denetimi olustur'da bundan ÖNCE, şablon
    no'larıyla yapılır."""
    if not onek_duzelt:
        sorunlar = [f"bölüm {b.no} satır '{s.no}'" for b in bolumler for s in b.satirlar
                    if s.no and s.no.partition(".")[0] != b.no]
        if sorunlar:
            raise NumaraOnekiHatasi(sorunlar)
    yeni_bolumler, n = [], 0
    for b in bolumler:
        n += 1
        while str(n) in ayrilmis:
            n += 1
        yeni, sira, satirlar = str(n), 0, []
        for s in b.satirlar:
            _onek, nokta, ek = s.no.partition(".")
            if not s.no:
                no = ""
            elif not nokta:
                no = yeni
            elif ek.isdigit():
                sira += 1
                no = f"{yeni}.{sira}"
            else:
                no = f"{yeni}.{ek}"
            satirlar.append(dataclasses.replace(s, no=no))
        yeni_bolumler.append(Bolum(yeni, b.baslik, tuple(satirlar)))
    return tuple(yeni_bolumler)


def _hesapla(k):
    try:
        return boru_hesapla(BoruGirdisi(k.psl, k.grade, k.D, k.t, k.boy_m, k.amac))
    except EslesmeHatasi as e:
        raise EslesmeHatasi(_("Kalem {no}: {e}").format(no=k.no, e=e)) from e


def olustur(sablon, baslik, kalemler, onek_duzelt=False, *, firma):
    """firma: belgeyi üreten firmanın adı (ayardan); şablondaki {firma} yer tutucusunu doldurur
    ve Dokuman.firma olur. Boşsa ValueError (sessiz yer tutucu yok)."""
    firma = ad_dogrula(firma)
    s = sablon_modulu(sablon)
    kalemler = tuple(kalemler)
    nolar = [k.no for k in kalemler]
    if not nolar:
        raise ValueError(_("en az bir kalem gerekli"))
    if nolar != sorted(set(nolar)):
        raise ValueError(_("kalem numaraları tekil ve artan olmalı: {nolar}").format(nolar=nolar))
    sonuclar = tuple(_hesapla(k) for k in kalemler)
    bolumler = []
    for sira, b in enumerate(s.BOLUMLER, 1):
        for anahtar in ("no", "baslik"):
            if anahtar not in b:
                raise SablonHatasi(_("{AD} bölüm #{sira}: bölümde '{anahtar}' eksik").format(AD=s.AD, sira=sira, anahtar=anahtar))
        yer = f"{s.AD} bölüm {b['no']}"
        kapsam = _kapsam(b.get("kosul"), kalemler, sonuclar, yer)
        if not kapsam:
            continue
        ks, rs = [k for k, __ in kapsam], [r for __, r in kapsam]
        baslik_metni = b["baslik"]
        if "kosul" in b:
            baslik_metni += f" ({kalem_etiketi([k.no for k in ks], s.DIL)})"
        satirlar = ()
        if "uret" in b:
            if b["uret"] not in URETECLER:
                raise SablonHatasi(_("{yer}: tanımsız üretici '{d}'").format(yer=yer, d=b['uret']))
            satirlar = _kalemli([k.no for k in ks], URETECLER[b["uret"]], b, ks, rs, s.DIL)
        for d in b.get("satirlar", ()):
            if "sonra" in d:
                satirlar = _araya_koy(satirlar, d["sonra"], _satirlar(d, kapsam, s.DIL, yer, firma),
                                      yer)
                continue
            for satir in _satirlar(d, kapsam, s.DIL, yer, firma):
                if satir.no and satirlar and satir.no == _son_no(satirlar):
                    if "kosul" not in d:
                        raise SablonHatasi(_("{yer}: tekrarlanan satır no '{no}'").format(yer=yer, no=satir.no))
                    # PSL 1 / PSL 2 karşılık satırları aynı no'yu taşır; ikisi de girerse devam
                    # satırı olur (no, aktivite, spec boş)
                    satir = dataclasses.replace(satir, no="", aktivite="", spec="")
                satirlar += (satir,)
        bolumler.append(Bolum(b["no"], baslik_metni, satirlar))
    return Dokuman(format=s.FORMAT, dil=s.DIL, sablon=s.AD, baslik=baslik,
                   kalemler=kalemler, sonuclar=sonuclar,
                   sartnameler=tuple(Sartname(i, m) for i, m in enumerate(s.SARTNAMELER, 1)),
                   bolumler=numaralari_sirala(bolumler,
                                              getattr(s, "AYRILMIS_BOLUMLER", ()),
                                              onek_duzelt),
                   firma=firma)
