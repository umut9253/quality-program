# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Yer tutucu, blok ve üretici kayıtları: Plan 1 sonuçlarını şablon metnine çevirir.

Karar C (2026-10-26): formül ifadeleri kalemler arasında gruplanır ("Items 1-4: <formül>");
somut mm değerleri her zaman kalem tablosudur (BLOKLAR). Plan 1'in Türkçe `metin`
alanları kopyalanmaz; metin sayısal alanlardan dile göre kurulur.
"""
import math
import re

from app.itp import hesap as H
from app.itp import kaplama as KAPL
from app.itp.aralik import tek_satir
from app.itp.dokuman import Denetim, KalemTablosu, Metin, Satir
from app.itp.hesap import excel_round
from app.itp.veri import api5l_47 as API
from app.itp.veri import iso21809 as KAP
from app.dil import _


class SablonHatasi(Exception):
    """Şablonda tanımsız yer tutucu/blok/üretici ya da dile çevrilemeyen değer."""


ETIKET = {"en": ("Item", "Items"), "tr": ("Kalem", "Kalem")}
ANLASMA = {"en": "As agreed", "tr": "anlaşmaya bağlı"}
MIN = {"en": "min.", "tr": "min."}
MAKS = {"en": "max.", "tr": "maks."}
_ATIF_EN = (("şirket uygulaması", "company practice"), ("dipnot", "footnote"))

YER_TUTUCULAR = {}   # ad -> f(kalem, sonuc, dil) -> str
BLOKLAR = {}         # ad -> f(kalemler, sonuclar, dil) -> KalemTablosu
URETECLER = {}       # ad -> f(bolum, kalemler, sonuclar, dil) -> tuple[Satir]


def sayi(x, dil, basamak=2):
    """En çok `basamak` ondalık, sondaki sıfırlar atılır; EN nokta, TR virgül."""
    s = f"{excel_round(x, basamak):.{basamak}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    if s == "-0":
        s = "0"
    return s.replace(".", ",") if dil == "tr" else s


def _aralik(a, b):
    return str(a) if a == b else f"{a}-{b}"


def nolar_metni(nolar):
    """Artan kalem numaraları: ardışıklar aralık, diğerleri virgül ([1,2,3,5] → '1-3,5')."""
    parcalar, bas, onceki = [], nolar[0], nolar[0]
    for n in nolar[1:]:
        if n == onceki + 1:
            onceki = n
            continue
        parcalar.append(_aralik(bas, onceki))
        bas = onceki = n
    parcalar.append(_aralik(bas, onceki))
    return ",".join(parcalar)


def kalem_etiketi(nolar, dil):
    tekil, cogul = ETIKET[dil]
    return f"{tekil if len(nolar) == 1 else cogul} {nolar_metni(nolar)}"


def grupla(nolar, metinler, dil):
    """nolar[i] kaleminin metni metinler[i]. Tek kalem → önek yok; eşit metinler tek grupta."""
    if len(nolar) == 1:
        return metinler[0]
    gruplar = {}
    for n, m in zip(nolar, metinler):
        gruplar.setdefault(m, []).append(n)
    return " / ".join(f"{kalem_etiketi(ns, dil)}: {m}" for m, ns in gruplar.items())


def atif_dil(atif, dil):
    """Plan 1 atıflarındaki Türkçe kelimeleri EN dokümanda çevirir."""
    if dil == "en":
        for tr, en in _ATIF_EN:
            atif = atif.replace(tr, en)
    return atif


# --- Boru: formül yer tutucuları (gruplanır) ---------------------------------------

KAPLAMA_AD = {"en": {"çıplak": "Bare"}, "tr": {"çıplak": "Çıplak"}}
KIMYA_ELEMENTLERI = ("C", "Si", "Mn", "P", "S", "V", "Nb", "Ti", "Nb+V+Ti", "C+Nb",
                     "Cu", "Ni", "Cr", "Mo", "B", "CE(IIW)", "CE(Pcm)")
_YOK = "-"


def tol_formul(tol, sembol, dil):
    """(oran, sabit, maks) → '<oran>D (max. <maks> mm)' / '<sabit> mm'."""
    oran, sabit, maks = tol
    if oran > 0:
        s = f"{sayi(oran, dil, 4)}{sembol}"
        return f"{s} ({MAKS[dil]} {sayi(maks, dil)} mm)" if maks > 0 else s
    return f"{sayi(sabit, dil)} mm"


def _arti_eksi(arti, eksi):
    return f"±{arti}" if arti == eksi else f"-{eksi} / +{arti}"


def _cap_formul(konum):
    def f(kalem, sonuc, dil):
        s = H.cap_satiri(kalem.D)
        if s["anlasmaya_bagli"]:
            return ANLASMA[dil]
        return _arti_eksi(tol_formul(s[f"{konum}_arti"], "D", dil),
                          tol_formul(s[f"{konum}_eksi"], "D", dil))
    return f


def _oval_formul(konum):
    def f(kalem, sonuc, dil):
        s = H.cap_satiri(kalem.D)
        if s["anlasmaya_bagli"]:
            return ANLASMA[dil]
        dt = s["oval_dt_maks"]
        if dt is not None and kalem.D / kalem.t > dt:
            return f"{ANLASMA[dil]} (D/t > {sayi(dt, dil)})"
        return tol_formul(s[f"oval_{konum}"], "D", dil)
    return f


def _et_formul(kalem, sonuc, dil):
    s = H.t_satiri(API.ET, kalem.t, API.ATIF["ET"])
    return _arti_eksi(tol_formul(s["arti"], "t", dil), tol_formul(s["eksi"], "t", dil))


def _mm_maks(alan):
    def f(kalem, sonuc, dil):
        return f"{MAKS[dil]} {sayi(getattr(sonuc, alan).deger, dil)} mm"
    return f


def _bead_uc(kalem, sonuc, dil):
    p, m = API.PARAMETRELER, MAKS[dil]
    ic, dis = sayi(sonuc.bead_uc_ic.deger, dil), sayi(sonuc.bead_uc_dis.deger, dil)
    b_ic, b_dis = sayi(p["bead_ic_uc_bolge_mm"], dil), sayi(p["bead_dis_uc_bolge_mm"], dil)
    if dil == "en":
        return (f"inside: {m} {ic} mm within {b_ic} mm of the pipe end; "
                f"outside: {m} {dis} mm within {b_dis} mm of the pipe end (if agreed)")
    return (f"iç: boru ucundan {b_ic} mm içinde {m} {ic} mm; "
            f"dış: boru ucundan {b_dis} mm içinde {m} {dis} mm ({ANLASMA[dil]})")


def _dogrusallik(kalem, sonuc, dil):
    p = API.PARAMETRELER
    oran = sayi(p["dogrusallik_oran"] * 100, dil)
    uc, boy = sayi(p["dogrusallik_uc_mm"], dil), sayi(p["dogrusallik_uc_boy_m"], dil)
    if dil == "en":
        return f"≤ {oran} % of pipe length; ≤ {uc} mm over {boy} m at each pipe end"
    return f"boru boyunun ≤ %{oran}'si; her boru ucunda {boy} m'de ≤ {uc} mm"


YER_TUTUCULAR.update({
    "cap_govde_formul": _cap_formul("govde"),
    "cap_uc_formul": _cap_formul("uc"),
    "oval_govde_formul": _oval_formul("govde"),
    "oval_uc_formul": _oval_formul("uc"),
    "et_formul": _et_formul,
    "radyal_ofset": _mm_maks("radyal_ofset"),
    "bead_ic": _mm_maks("bead_ic"),
    "bead_dis": _mm_maks("bead_dis"),
    "bead_uc": _bead_uc,
    "dogrusallik": _dogrusallik,
    "boy": lambda kalem, sonuc, dil: f"{sayi(kalem.boy_m, dil)} m",
})


# --- Boru: bloklar (her zaman kalem tablosu) --------------------------------------

def _min_max(nominal, tol, dil):
    sinir = H.olcu_sinirlari(nominal, tol)
    if sinir is None:
        return ANLASMA[dil], ANLASMA[dil]
    return sayi(sinir[0], dil), sayi(sinir[1], dil)


def _tablo(basliklar, dil, satirlar):
    return KalemTablosu(basliklar[dil], tuple(satirlar))


def _sabit(x, dil, basamak=2):
    """Sabit ondalık + binlik ayırıcı: EN 21,216.00 / TR 21.216,00 (KURUM_A KP "650,00")."""
    s = f"{excel_round(x, basamak):,.{basamak}f}"
    return s.translate(str.maketrans(",.", ".,")) if dil == "tr" else s


def _ebat(kalemler, sonuclar, dil):
    """Kalem listesi, KURUM_A KP biçimi (kullanıcı 2026-11-03): uzunluk = sipariş miktarı,
    et ve uzunluk iki ondalık, kaplama büyük harf; boru boyu ayrı satırda (Boru boyu)."""
    ad = KAPLAMA_AD[dil]

    def kaplama(x):
        return ad.get(x, x).upper() if dil == "en" else ad.get(x, x).replace("i", "İ").upper()

    return _tablo({"en": ("Item", "OD (mm)", "WT (mm)", "Length (m)", "Steel Grade", "Lining",
                          "Coating"),
                   "tr": ("Kalem", "Dış Çap (mm)", "Et Kalınlığı (mm)", "Uzunluk (m)",
                          "Çelik Kalitesi", "İç Kaplama", "Dış Kaplama")}, dil,
                  ((str(k.no), sayi(k.D, dil), _sabit(k.t, dil), _sabit(k.miktar_m, dil),
                    f"{k.grade} {k.psl}", kaplama(k.ic_kaplama), kaplama(k.dis_kaplama))
                   for k in kalemler))


_OLCU_BASLIK = {"en": ("Min. (mm)", "Max. (mm)"), "tr": ("Min. (mm)", "Maks. (mm)")}


def _tekil(satirlar):
    """Kalem sırası korunarak aynı satırlar bir kez (Word ITP: nominal başına satır)."""
    return tuple(dict.fromkeys(satirlar))


def _olcu_tablosu(nom, dil, satirlar):
    return KalemTablosu((nom,) + _OLCU_BASLIK[dil], _tekil(satirlar))


def _cap(konum):
    def f(kalemler, sonuclar, dil):
        return _olcu_tablosu("Nom. D (mm)", dil, (
            (sayi(k.D, dil), *_min_max(k.D, getattr(r, f"cap_{konum}"), dil))
            for k, r in zip(kalemler, sonuclar)))
    return f


def _cevre(sinir, dil):
    return ANLASMA[dil] if sinir is None else sayi(math.pi * sinir, dil)


def _cevre_govde(kalemler, sonuclar, dil):
    """Gövde çevresi = π × tabloda gösterilen çap sınırları (spec §4.4)."""
    satirlar = []
    for k, r in zip(kalemler, sonuclar):
        s = H.olcu_sinirlari(k.D, r.cap_govde)
        mn, mx = (None, None) if s is None else s
        satirlar.append((sayi(math.pi * k.D, dil), _cevre(mn, dil), _cevre(mx, dil)))
    return _olcu_tablosu("Nom. C (mm)", dil, satirlar)


def _et_min_max(kalemler, sonuclar, dil):
    return _olcu_tablosu("Nom. t (mm)", dil, (
        (sayi(k.t, dil), *_min_max(k.t, r.et, dil)) for k, r in zip(kalemler, sonuclar)))


def _oval_mm(o, dil):
    return ANLASMA[dil] if o.mm is None else sayi(o.mm, dil)


def _ovallik_mm(kalemler, sonuclar, dil):
    return _tablo({"en": ("Item", "D (mm)", "Body max (mm)", "End max (mm)"),
                   "tr": ("Kalem", "D (mm)", "Gövde maks (mm)", "Uç maks (mm)")}, dil,
                  ((str(k.no), sayi(k.D, dil), _oval_mm(r.ovallik_govde, dil),
                    _oval_mm(r.ovallik_uc, dil)) for k, r in zip(kalemler, sonuclar)))


def _p_hucre(r, dil):
    p = sayi(r.p_test.deger, dil)
    if r.p_test.deger == r.p_hesap.deger:
        return p
    sinir = {"en": "limited acc. to", "tr": "sınırlandırıldı:"}[dil]
    return f"{p} ({sinir} {atif_dil(r.p_test.atif, dil)})"


def _test_basinci(kalemler, sonuclar, dil):
    return _tablo({"en": ("Item", "D (mm)", "t (mm)", "Grade", "SMYS (MPa)", "k", "P (bar)"),
                   "tr": ("Kalem", "D (mm)", "t (mm)", "Kalite", "SMYS (MPa)", "k", "P (bar)")},
                  dil,
                  ((str(k.no), sayi(k.D, dil), sayi(k.t, dil), k.grade,
                    sayi(r.malzeme["yield_min"], dil),
                    sayi(H.k_faktoru(k.amac, k.D, k.grade).deger, dil), _p_hucre(r, dil))
                   for k, r in zip(kalemler, sonuclar)))


KIMYA_SUTUN = 7        # Element + 7 kalite = 8 alt sütun (kabul_izgara.ALT_SUTUN)
YUZDE_MAKS = {"en": "% max.", "tr": "% maks."}
RT = {"en": "Rt0.5", "tr": "Rt0,5"}
KAYNAK = {"en": "Weld", "tr": "Kaynak"}
UZAMA = {"en": "Elongation:", "tr": "Uzama:"}


def _kalite_gruplari(kalemler, sonuclar):
    """[((grade, psl), [(kalem, sonuc), ...]), ...] — ilk görülme sırasıyla."""
    gruplar = {}
    for k, r in zip(kalemler, sonuclar):
        gruplar.setdefault((k.grade, k.psl), []).append((k, r))
    return list(gruplar.items())


def _grup_adi(grade, psl, uyelar, dil):
    return f"{grade} {psl} ({kalem_etiketi([k.no for k, __ in uyelar], dil)})"


def _kimya(kalemler, sonuclar, dil):
    """Word ITP biçimi: Element | kalite sütunları; değeri olmayan element yazılmaz."""
    gruplar = _kalite_gruplari(kalemler, sonuclar)
    parcalar = []
    for i in range(0, len(gruplar), KIMYA_SUTUN):
        dilim = gruplar[i:i + KIMYA_SUTUN]
        kim = [uyelar[0][1].malzeme["kimya"] for __, uyelar in dilim]
        parcalar.append(KalemTablosu(
            ("Element",) + tuple(_grup_adi(g, p, u, dil) for (g, p), u in dilim),
            tuple((f"{YUZDE_MAKS[dil]} {e}",)
                  + tuple(_YOK if x[e] is None else sayi(x[e], dil, 3) for x in kim)
                  for e in KIMYA_ELEMENTLERI if any(x[e] is not None for x in kim))))
    if dil == "tr":                      # kimya_not yalnızca Türkçe (spec netleşen 5)
        parcalar += [Metin(f"{g} {p}: {u[0][1].malzeme['kimya_not']}")
                     for (g, p), u in gruplar if u[0][1].malzeme["kimya_not"]]
    return tuple(parcalar)


def _aralik_metni(mn, mx, dil):
    return f"{MIN[dil]} {sayi(mn, dil)}" if mx is None else f"{sayi(mn, dil)} - {sayi(mx, dil)}"


def _uzama_satiri(t, af, psl, dil):
    """PSL 2 hep bir ondalık (Word ITP, K6), PSL 1 tam yüzde."""
    a = sayi(af, dil, 0) if psl == "PSL 1" else f"{excel_round(af, 1):.1f}"
    a = a.replace(".", ",") if dil == "tr" else a
    return f"t = {sayi(t, dil)} mm: {MIN[dil]} {a} %" if dil == "en" else f"t = {sayi(t, dil)} için %{a}"


def _mekanik(kalemler, sonuclar, dil):
    """Word ITP biçimi: kalite grubu başına Rt0,5, Rm, Rt0,5/Rm, kaynak Rm, uzama (Af)."""
    out = []
    for (grade, psl), uyelar in _kalite_gruplari(kalemler, sonuclar):
        m = uyelar[0][1].malzeme
        out += [_grup_adi(grade, psl, uyelar, dil),
                f"{RT[dil]} = {_aralik_metni(m['yield_min'], m['yield_max'], dil)} N/mm²",
                f"Rm = {_aralik_metni(m['tensile_min'], m['tensile_max'], dil)} N/mm²"]
        rt = [r.rt_rm_maks.deger for __, r in uyelar]
        if any(x is not None for x in rt):       # sınırın uygulanmadığı çap aralığı (dipnot c)
            rt_m = [_YOK if x is None else f"{MAKS[dil]} {sayi(x, dil)}" for x in rt]
            out.append(f"{RT[dil]}/Rm: " + (rt_m[0] if len(set(rt_m)) == 1 else
                                            grupla([k.no for k, __ in uyelar], rt_m, dil)))
        if m["dikis_rm_min"] is not None:
            out.append(f"{KAYNAK[dil]}: Rm {MIN[dil]} {sayi(m['dikis_rm_min'], dil)} N/mm²")
        out.append(UZAMA[dil])
        for t in sorted({k.t for k, __ in uyelar}):
            af = (m["uzama_min"] if m["uzama_min"] is not None
                  else H.uzama_af(t, m["tensile_min"], psl).deger)
            out.append(_uzama_satiri(t, af, psl, dil))
    return tuple(Metin(x) for x in out)


def _kaplama_kalinligi(kalemler, sonuclar, dil):
    return _tablo({"en": ("Item", "Coating", "Pm (kg/m)", "Class", "Min. total thickness (mm)"),
                   "tr": ("Kalem", "Kaplama", "Pm (kg/m)", "Sınıf", "Min. toplam kalınlık (mm)")},
                  dil,
                  ((str(k.no), k.dis_kaplama, sayi(r.pm, dil),
                    f"{k.kaplama_sinifi}{k.kalinlik_sinifi}",
                    sayi(KAPL.min_kalinlik(k.kaplama_sinifi, k.kalinlik_sinifi, r.pm).deger, dil))
                   for k, r in zip(kalemler, sonuclar) if k.kaplama_sinifi is not None))


# --- Plan 2b: CVN, mandrel, lot, kütle --------------------------------------------

def _atif_tr(atif, dil):
    """atif_dil + TR dokümanda 'Table' → 'Tablo' (Plan 2b atıfları veride İngilizce)."""
    atif = atif_dil(atif, dil)
    return atif.replace("Table", "Tablo") if dil == "tr" else atif


_NUMUNE_AD = {"en": {"Full": "Full size"}, "tr": {"Full": "Tam boy"}}
_GEREKMEZ = {"en": "Not required", "tr": "Gerekmez"}


def _charpy_satiri(k, c, dil):
    if c.numune is None:
        neden = k.psl if k.psl != "PSL 2" else _atif_tr(API.ATIF["CVN_NUMUNE"], dil)
        return (str(k.no), f"{_GEREKMEZ[dil]} ({neden})") + (_YOK,) * 4
    return (str(k.no), _NUMUNE_AD[dil].get(c.numune, c.numune),
            sayi(c.govde_ort, dil), sayi(c.govde_tekil, dil),
            sayi(c.kaynak_ort, dil), sayi(c.kaynak_tekil, dil))


def _charpy(kalemler, sonuclar, dil):
    return _tablo({"en": ("Item", "Test piece size", "Body avg. min (J)", "Body individual min (J)",
                          "Weld/HAZ avg. min (J)", "Weld/HAZ individual min (J)"),
                   "tr": ("Kalem", "Numune boyutu", "Gövde ort. min (J)", "Gövde tekil min (J)",
                          "Kaynak/ITAB ort. min (J)", "Kaynak/ITAB tekil min (J)")}, dil,
                  (_charpy_satiri(k, r.charpy, dil) for k, r in zip(kalemler, sonuclar)))


def _mandrel(kalemler, sonuclar, dil):
    t_maks = sayi(API.PARAMETRELER["bukme_t_maks_mm"], dil)
    return _tablo({"en": ("Item", "t (mm)", "Grade", "ε", "Agb full thickness (mm)",
                          "Die opening B full thickness (mm)",
                          f"Agb reduced thickness, t = {t_maks} mm (mm)",
                          f"Die opening B reduced thickness, t = {t_maks} mm (mm)"),
                   "tr": ("Kalem", "t (mm)", "Kalite", "ε", "Agb tam kalınlık (mm)",
                          "Çene açıklığı B tam kalınlık (mm)",
                          f"Agb azaltılmış kalınlık, t = {t_maks} mm (mm)",
                          f"Çene açıklığı B azaltılmış kalınlık, t = {t_maks} mm (mm)")}, dil,
                  ((str(k.no), sayi(k.t, dil), k.grade, sayi(r.mandrel.epsilon, dil, 4),
                    str(r.mandrel.agb_mm), sayi(r.mandrel.b_mm, dil),
                    _YOK if r.mandrel.agb_azaltilmis_mm is None else str(r.mandrel.agb_azaltilmis_mm),
                    _YOK if r.mandrel.b_azaltilmis_mm is None else sayi(r.mandrel.b_azaltilmis_mm, dil))
                   for k, r in zip(kalemler, sonuclar)))


def _lot(kalem, sonuc, dil):
    lot = sonuc.lot
    if lot.deger is None:                    # PSL 1: test birimi tanımı, sayısal sınır yok (V-2b-5)
        atif = _atif_tr(lot.atif, dil)
        if dil == "en":
            return (f"test unit of pipe with the same cold-expansion ratio (Spec. 1 Para. {atif}); "
                    f"no numerical limit")
        return f"aynı soğuk genişletme oranlı borulardan test birimi (Ş.1 Madde {atif}); sayısal sınır yok"
    n = sayi(lot.deger, dil)
    if dil == "en":
        return f"{MAKS[dil]} {n} pipes per test unit (same cold-expansion ratio)"
    return f"test birimi başına {MAKS[dil]} {n} boru (aynı soğuk genişletme oranı)"


def _yuzde(x, dil):
    """Standart yazımı gibi en az bir ondalık."""
    s = sayi(x, dil)
    ayrac = "," if dil == "tr" else "."
    return s if ayrac in s else f"{s}{ayrac}0"


def _kutle(kalem, sonuc, dil):
    t = sonuc.kutle
    arti, eksi = _yuzde(t.arti, dil), _yuzde(t.eksi, dil)
    s = f"+{arti} % / -{eksi} %" if dil == "en" else f"+%{arti} / -%{eksi}"
    if t.metin:                              # özel hafif boyut (Table 9)
        oh = _atif_tr(API.ATIF["OZEL_HAFIF"], dil)
        s += f" (special light size, {oh})" if dil == "en" else f" (özel hafif boyut, {oh})"
    return s


YER_TUTUCULAR.update({"lot": _lot, "kutle": _kutle})


BLOKLAR.update({
    "charpy": _charpy,
    "mandrel": _mandrel,
    "ebat": _ebat,
    "cap_govde": _cap("govde"),
    "cap_uc": _cap("uc"),
    "cevre_govde": _cevre_govde,
    "et_min_max": _et_min_max,
    "ovallik_mm": _ovallik_mm,
    "test_basinci": _test_basinci,
    "kimya": _kimya,
    "mekanik": _mekanik,
    "kaplama_kalinligi": _kaplama_kalinligi,
})


# --- Kaplama (ISO 21809) ----------------------------------------------------------

KAPLAMA_ASAMALARI = ("yüzey hazırlığı", "uygulanmış kaplama", "tamir")
_YS, _UK = "yüzey hazırlığı", "uygulanmış kaplama"
P1, P2 = KAP.P1, KAP.P2

# Yer tutucu adı → (standart, aşama, kriter). ITP (EN) şablonu yalnızca sayısal kriterleri
# bu adlarla çeker; aşama anahtarın parçasıdır (ISO 21809-2'de kriter adları tekrarlanır).
KAPLAMA_YT = {
    "k1_iletkenlik": (P1, _YS, "Aşındırıcının suda çözünür kirliliği (iletkenlik)"),
    "k1_tuz": (P1, _YS, "Kumlama sonrası çözünür tuz"),
    "k1_puruzluluk": (P1, _YS, "Kumlanmış yüzey pürüzlülüğü"),
    "k1_fbe_kalinlik": (P1, _UK, "Epoksi kalınlığı — FBE"),
    "k1_yapistirici": (P1, _UK, "Yapıştırıcı kalınlığı"),
    "k1_kur": (P1, _UK, "Kür derecesi (ΔTg)"),
    "k1_darbe": (P1, _UK, "Darbe dayanımı"),
    "k1_soyulma_23": (P1, _UK, "Soyulma mukavemeti"),
    "k1_soyulma_yuksek": (P1, _UK, "Soyulma mukavemeti @ yüksek sıcaklık"),
    "k1_indentasyon_23": (P1, _UK, "Indentasyon"),
    "k1_indentasyon_tasarim": (P1, _UK, "Indentasyon @ maks. tasarım sıcaklığı"),
    "k1_uzama": (P1, _UK, "PE/PP kopmada uzama"),
    "k1_katodik_65": (P1, _UK, "Katodik ayrılma"),
    "k1_sicak_su": (P1, _UK, "Sıcak su daldırma direnci"),
    "k1_mfr": (P1, _UK, "Ürün kararlılığı — uygulama sırasında (ΔMFR)"),
    "k2_iletkenlik": (P2, _YS, "Aşındırıcının suda çözünür kirliliği (iletkenlik)"),
    "k2_tuz": (P2, _YS, "Kumlama sonrası çözünür tuz"),
    "k2_puruzluluk": (P2, _YS, "Kumlanmış yüzey pürüzlülüğü"),
    "k2_kalinlik": (P2, _UK, "Kaplama kalınlığı"),
    "k2_darbe": (P2, _UK, "Darbe"),
    "k2_katodik_65": (P2, _UK, "Katodik ayrılma"),
    "k2_arayuz": (P2, _UK, "Arayüz kirliliği"),
    "k2_sureklilik": (P2, _UK, "Süreklilik — test gerilimi"),
}


def _sinif(kalem, standart):
    return kalem.kaplama_sinifi if standart == P1 else "tümü"


def kriter_satiri(standart, sinif, asama, kriter):
    return tek_satir(KAPL.kriterler(standart, sinif),
                     lambda r: r[2] == asama and r[3] == kriter,
                     f"{standart} sınıf {sinif} {asama} '{kriter}'")


def kriter_degeri(r, dil):
    """KRITERLER satırının kabul değeri. Metin kriterleri yalnızca TR (veri Türkçe)."""
    yon, d1, d2, birim = r[6], r[7], r[8], r[4]
    b = "" if birim == "—" else f" {birim}"
    if yon == "min":
        s = f"{MIN[dil]} {sayi(d1, dil)}{b}"
    elif yon == "maks":
        s = f"{MAKS[dil]} {sayi(d1, dil)}{b}"
    elif yon == "aralık":
        s = f"{sayi(d1, dil)} – {sayi(d2, dil)}{b}"
    elif yon == "metin" and dil == "tr":
        return r[9]
    else:
        raise SablonHatasi(_("{d} '{d2}': '{yon}' kriteri {dil} dilinde sayıya çevrilemez").format(d=r[0], d2=r[3], yon=yon, dil=dil))
    if dil == "tr" and r[9]:
        s += f" ({r[9]})"
    return s


def _kaplama_yt(std, asama, kriter):
    def f(kalem, sonuc, dil):
        return kriter_degeri(kriter_satiri(std, _sinif(kalem, std), asama, kriter), dil)
    return f


for _ad, (_std, _asama, _kriter) in KAPLAMA_YT.items():
    YER_TUTUCULAR[_ad] = _kaplama_yt(_std, _asama, _kriter)


_SICAKLIK_DESENI = re.compile(r"@\s*≥\s*(\d+(?:[.,]\d+)?)\s*°C")


def _soyulma_yuksek_sicaklik(kalem, sonuc, dil):
    """Yüksek sıcaklıkta soyulma testinin sıcaklığı (ISO 21809-1 Table 7). Değer KRITERLER
    r[9]'dan regex ile alınır; r[9] başka dile sızmasın diye EN'de sayı yeniden yazılır."""
    r = kriter_satiri(P1, kalem.kaplama_sinifi, _UK, "Soyulma mukavemeti @ yüksek sıcaklık")
    if dil == "tr":
        return r[9]
    m = _SICAKLIK_DESENI.search(r[9])
    if m is None:
        raise SablonHatasi(_("{d} sınıf {kaplama_sinifi} '{d2}': sıcaklık deseni ('@ ≥ N °C') bulunamadı: {d3!r}").format(d=r[0], kaplama_sinifi=kalem.kaplama_sinifi, d2=r[3], d3=r[9]))
    n = m.group(1).replace(",", ".")
    s = f"at >= {n} °C"
    if "maks. işletme sıcaklığında" in r[9]:
        s += f" or at maximum operating temperature if above {n} °C"
    return s


YER_TUTUCULAR["k1_soyulma_yuksek_sicaklik"] = _soyulma_yuksek_sicaklik


def _kaplama_kriterleri(bolum, kalemler, sonuclar, dil):
    """KP kaplama bölümü: ISO 21809 KRITERLER'den satır satır (yalnızca TR)."""
    if dil != "tr":
        raise SablonHatasi(_("kaplama_kriterleri üreticisi yalnızca TR şablonda kullanılır "
                           "(ISO 21809 kriter metinleri Türkçe)"))
    std = bolum["standart"]
    sira = []
    for k in kalemler:
        for r in KAPL.kriterler(std, _sinif(k, std)):
            anahtar = (r[2], r[3])
            if r[2] in KAPLAMA_ASAMALARI and r[6] != "tablo" and anahtar not in sira:
                sira.append(anahtar)
    nolar = [k.no for k in kalemler]
    # no yalnız aşamanın ilk satırında: devam satırı Excel'de A sütununda birleşir
    # (KURUM_A KP'da etiket aşama başına bir kez; Antigravity BULGU-01)
    satirlar, onceki, i = [], None, 0
    for asama, kriter in sira:
        rr = [kriter_satiri(std, _sinif(k, std), asama, kriter) for k in kalemler]
        yeni = asama != onceki
        i += yeni
        satirlar.append(Satir(
            no=f"{bolum['no']}.{i}" if yeni else "", aktivite=asama if yeni else "",
            spec=bolum["spec"], sorumlu=bolum["sorumlu"], karakteristik=kriter,
            frekans=rr[0][12], kayit=bolum["kayit"], denetim=Denetim(bolum["firma"]),
            kabul=(Metin(grupla(nolar, [kriter_degeri(r, dil) for r in rr], dil)),
                   Metin(f"{std} {rr[0][13]}"))))
        onceki = asama
    return tuple(satirlar)


URETECLER["kaplama_kriterleri"] = _kaplama_kriterleri
