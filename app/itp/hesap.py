# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""SAWH boru kabul kriteri hesapları.

Database.xlsx 'ürün girişi' formüllerinin Python karşılığı. Standart sayıları
yalnızca app/itp/veri modüllerinden gelir; burada yazılmaz. Sonuçlar sayı +
atıf taşır; sayı üretilemiyorsa metin nedenini söyler (sessiz değer yok).
"""
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal

from app.itp.aralik import EslesmeHatasi, aralikta, tek_satir
from app.itp.veri import api5l_47 as API
from app.dil import _

ANLASMA = "anlaşmaya bağlı"


@dataclass(frozen=True)
class Tolerans:
    arti: float | None
    eksi: float | None
    metin: str = ""
    atif: str = ""


@dataclass(frozen=True)
class Deger:
    deger: float | None
    metin: str = ""
    atif: str = ""


@dataclass(frozen=True)
class Ovallik:
    yuzde: float | None    # D'nin yüzdesi (2.0 = %2); sabit mm satırında, maks sınırı devredeyken veya sayı üretilemediğinde None
    mm: float | None
    metin: str = ""
    atif: str = ""


def excel_round(x, basamak=2):
    """Excel ROUND gibi: yarım değer sıfırdan uzağa (Python round() bankacı yuvarlaması yapar).

    Bilinçli tercih: API 5L 47 madde 4.2 uygunluk değerlendirmesinde ISO 80000-1
    Annex B Rule A (yarımda çifte yuvarlama) ister. Burada tolerans sınırları
    Database.xlsx ile birebir tutsun diye Excel davranışı kullanılır.
    """
    # Excel 15 anlamlı basamakla çalışır; aynı gösterimden yuvarlanır
    return float(Decimal(f"{x:.15g}").quantize(Decimal(1).scaleb(-basamak),
                                               rounding=ROUND_HALF_UP))


def tol_mm(tol, ref):
    """(oran, sabit, maks) üçlüsünü mm'ye çevirir; 0,01 mm'ye yuvarlar."""
    oran, sabit, maks = tol
    if oran > 0:
        v = oran * ref
        if maks > 0:
            v = min(v, maks)
    else:
        v = sabit
    return excel_round(v)


def t_satiri(tablo, t, atif):
    return tek_satir(tablo, lambda s: aralikta(t, s["t_alt"], s["t_alt_dahil"],
                                               s["t_ust"], s["t_ust_dahil"]),
                     f"{atif} t={t}")


def cap_satiri(D):
    return tek_satir(API.CAP, lambda s: aralikta(D, s["d_alt"], s["d_alt_dahil"],
                                                 s["d_ust"], s["d_ust_dahil"]),
                     f"{API.ATIF['CAP']} D={D}")


def cap_toleransi(D, konum):
    """konum: 'govde' veya 'uc'."""
    s = cap_satiri(D)
    atif = API.ATIF["CAP"]
    if s["anlasmaya_bagli"]:
        return Tolerans(None, None, ANLASMA, atif)
    return Tolerans(tol_mm(s[f"{konum}_arti"], D), tol_mm(s[f"{konum}_eksi"], D), "", atif)


def ovallik(D, t, konum):
    s = cap_satiri(D)
    atif = API.ATIF["CAP"]
    if s["anlasmaya_bagli"]:
        return Ovallik(None, None, ANLASMA, atif)
    dt_maks = s["oval_dt_maks"]
    if dt_maks is not None and D / t > dt_maks:
        return Ovallik(None, None, f"D/t > {dt_maks:g} — {ANLASMA}", atif)
    tol = s[f"oval_{konum}"]
    oran, __, maks = tol
    if oran > 0 and maks > 0 and oran * D > maks:
        # maks sınırı devrede: nominal yüzde yanıltıcı olur, yalnızca mm verilir
        return Ovallik(None, tol_mm(tol, D), f"maks {maks:g} mm", atif)
    yuzde = excel_round(oran * 100) if oran > 0 else None
    return Ovallik(yuzde, tol_mm(tol, D), "", atif)


def et_toleransi(t):
    s = t_satiri(API.ET, t, API.ATIF["ET"])
    return Tolerans(tol_mm(s["arti"], t), tol_mm(s["eksi"], t), "", API.ATIF["ET"])


def olcu_sinirlari(nominal, tol):
    """(min, max) uygulanacak ölçü sınırları; tolerans yoksa None."""
    if tol.arti is None or tol.eksi is None:
        return None
    return excel_round(nominal - tol.eksi), excel_round(nominal + tol.arti)


def radyal_ofset(t):
    s = t_satiri(API.RADYAL_OFSET, t, API.ATIF["RADYAL_OFSET"])
    return Deger(tol_mm(s["tol"], t), "", API.ATIF["RADYAL_OFSET"])


def bead(t):
    """Gövdede (uçlar hariç) iç ve dış kaynak beadi maks yüksekliği."""
    atif = API.ATIF["BEAD"]
    s = t_satiri(API.BEAD, t, atif)
    return Deger(s["ic_maks"], "", atif), Deger(s["dis_maks"], "", atif)


def bead_uc():
    """Uç bölgede bead: iç / dış uç bölge boyları PARAMETRELER'den (dış: anlaşmaya bağlı)."""
    p, atif = API.PARAMETRELER, API.ATIF["BEAD_UC"]
    return (Deger(p["bead_ic_uc_mm"], f"uçtan {p['bead_ic_uc_bolge_mm']:g} mm içeride", atif),
            Deger(p["bead_dis_uc_mm"],
                  f"uçtan {p['bead_dis_uc_bolge_mm']:g} mm, {ANLASMA}", atif))


def dogrusallik(L_m):
    """(toplam sapma maks, uç bölge maks). Toplam için boy gereklidir."""
    p, atif = API.PARAMETRELER, API.ATIF["DOGRUSALLIK"]
    uc = Deger(p["dogrusallik_uc_mm"], f"her uçta {p['dogrusallik_uc_boy_m']:g} m", atif)
    if L_m is None:
        return Deger(None, "boy L giriniz", atif), uc
    return Deger(excel_round(L_m * 1000 * p["dogrusallik_oran"]), "", atif), uc


def malzeme(psl, grade):
    return tek_satir(API.MALZEME, lambda m: m["psl"] == psl and m["grade"] == grade,
                     f"malzeme {psl} {grade}")


def uzama_af(t, U, psl):
    """En az uzama Af (%) = C · Axc^a / U^b; Axc = min(Axc maks, numune genişliği · t)
    (C, a, b, Axc maks: PARAMETRELER).

    Fabrika uygulaması (2026-11-03): Axc yuvarlanmaz; PSL 2 bir ondalık (Table 7 dipnot f
    yuvarlama koymaz), PSL 1 tam yüzde (Table 6 dipnot c)."""
    p = API.PARAMETRELER
    axc = min(p["uzama_axc_maks_mm2"], p["uzama_numune_genislik_mm"] * t)
    af = p["uzama_af_katsayi"] * axc ** p["uzama_af_axc_us"] / U ** p["uzama_af_u_us"]
    return Deger(excel_round(af, 0 if psl == "PSL 1" else 1), "", API.ATIF[f"UZAMA_{psl}"])


def _k_satiri(amac, D, grade):
    grup = API.K_GRUP.get(grade)
    return tek_satir(API.K_FAKTORU,
                     lambda r: grup is not None and r["amac"] == amac
                     and r["grup"] in (grup, "hepsi")
                     and aralikta(D, r["d_alt"], r["d_alt_dahil"], r["d_ust"], r["d_ust_dahil"]),
                     f"k faktörü {amac} {grade} D={D}")


def k_faktoru(amac, D, grade):
    s = _k_satiri(amac, D, grade)
    # atıf satır bulunduktan sonra: geçersiz amaç KeyError değil EslesmeHatasi verir
    return Deger(s["k"], s["not_"], API.ATIF[f"K_FAKTORU_{amac}"])


def hidrostatik_basinc(amac, D, t, smys, grade):
    """P = 20 × k × SMYS × t / D (bar). P test satırın üst sınırıyla kırpılır:
    su: şirket uygulaması; doğalgaz: Table 26 dipnot a / b üst sınırları (veride)."""
    s = _k_satiri(amac, D, grade)
    k = k_faktoru(amac, D, grade)
    p = 20 * k.deger * smys * t / D
    p_hesap = Deger(p, f"k = {k.deger:g}", k.atif)
    pmax = s["pmax_bar"]
    if p > pmax:
        return p_hesap, Deger(pmax, f"{amac} borusu: {pmax:g} bar ile sınırlandı", s["pmax_atif"])
    return p_hesap, Deger(p, "", k.atif)


def pm(D, t):
    """Boru birim kütlesi kg/m. YUVARLANMAZ: kaplama Pm aralık sınırları gerçek ölçülere denk gelir."""
    return API.PARAMETRELER["pm_katsayi"] * t * (D - t)


# --- Plan 2b: CVN, mandrel, lot, kütle ----------------------------------------

@dataclass(frozen=True)
class Charpy:
    numune: str | None         # Table 22 boyutu ("Full", "3/4", "2/3", "1/2"); gerekmiyorsa None
    oran: float | None         # alt boy genişlik oranı (9.8.1.1)
    govde_ort: float | None    # J, numune boyutuna ölçekli, en yakın J
    govde_tekil: float | None  # J, cvn_tekil_oran × ortalama (V-2b-4: iki ondalık)
    kaynak_ort: float | None
    kaynak_tekil: float | None
    kaynak_madde: str = ""
    sicaklik_c: float | None = None
    metin: str = ""
    atif: str = ""


@dataclass(frozen=True)
class Mandrel:
    agb_mm: int                         # Denklem (5), gerçek t ile, en yakın 1 mm
    agb_azaltilmis_mm: int | None       # t > maks ise t = maks ile (V-2b-3); değilse None
    epsilon: float
    b_mm: float                         # çene açıklığı B = Agb + 2t + pay (Figure 9; yuvarlanmış Agb ile, V-2b-16)
    b_azaltilmis_mm: float | None       # azaltılmış kalınlık için B (t = maks); yoksa None
    metin: str = ""
    atif: str = ""


def _d_t_icinde(s, D, t):
    return (aralikta(D, s["d_alt"], s["d_alt_dahil"], s["d_ust"], s["d_ust_dahil"])
            and aralikta(t, s["t_alt"], s["t_alt_dahil"], s["t_ust"], s["t_ust_dahil"]))


def _en_fazla_bir(satirlar, kosul, aciklama):
    """0 satır → None (tablo dışı anlamlı); 2+ satır → EslesmeHatasi."""
    eslesen = [s for s in satirlar if kosul(s)]
    if len(eslesen) > 1:
        raise EslesmeHatasi(_("{aciklama}: {d} satır eşleşti (en fazla 1 bekleniyordu)").format(aciklama=aciklama, d=len(eslesen)))
    return eslesen[0] if eslesen else None


def _en_yakin_j(x):
    """En yakın joule; API 5L 4.2 gereği ISO 80000-1 Rule A (yarımda çifte, V-2b-11)."""
    return float(Decimal(f"{x:.15g}").quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def _cvn_j(tablo, D, smys, aciklama):
    return tek_satir(tablo, lambda s: aralikta(D, s["d_alt"], s["d_alt_dahil"],
                                               s["d_ust"], s["d_ust_dahil"])
                     and aralikta(smys, s["smys_alt"], s["smys_alt_dahil"],
                                  s["smys_ust"], s["smys_ust_dahil"]),
                     f"{aciklama} D={D} SMYS={smys}")


def charpy(D, t, grade, psl):
    """PSL 2 CVN minimum enerjileri (test sıcaklığı veride), Table 22 numune boyutuna ölçekli.

    Kalite grubu SMYS'den (V-2b-1). Table 22 dışı boyut: CVN gerekmez (None + metin).
    Table 8 kapsamı dışı (D, SMYS): EslesmeHatasi.
    """
    a = API.ATIF
    atif = ", ".join(a[k] for k in ("CVN_GOVDE", "CVN_KAYNAK", "CVN_NUMUNE",
                                    "CVN_ALT_BOY", "CVN_TEKIL"))
    if psl != "PSL 2":
        return Charpy(None, None, None, None, None, None, "", None,
                      f"{psl}: CVN istenmez", atif)
    numune = _en_fazla_bir(API.CVN_NUMUNE, lambda s: _d_t_icinde(s, D, t),
                           f"{a['CVN_NUMUNE']} D={D} t={t}")
    if numune is None:
        return Charpy(None, None, None, None, None, None, "", None,
                      f"{a['CVN_NUMUNE']} dışı boyut: CVN gerekmez", atif)
    smys = malzeme(psl, grade)["yield_min"]
    govde = _cvn_j(API.CVN_GOVDE, D, smys, a["CVN_GOVDE"])
    kaynak = _cvn_j(API.CVN_KAYNAK, D, smys, a["CVN_KAYNAK"])
    p = API.PARAMETRELER
    oran = numune["oran"]
    # 9.8.1.1: alt boy değer = tam boy × oran, en yakın J
    g_ort = _en_yakin_j(govde["j"] * oran)
    k_ort = _en_yakin_j(kaynak["j"] * oran)
    return Charpy(numune["boyut"], oran,
                  g_ort, excel_round(p["cvn_tekil_oran"] * g_ort, 2),
                  k_ort, excel_round(p["cvn_tekil_oran"] * k_ort, 2),
                  kaynak["madde"], p["cvn_sicaklik_c"], "", atif)


def mandrel(D, t, grade):
    """Kılavuzlu bükme mandrel boyutu Agb = k(D − 2t) / (ε·D/t − 2ε − 1) − t (k: PARAMETRELER),
    en yakın 1 mm.

    ε: kalite adından M/Q son eki atılarak (V-2b-2). t > maks: hem tam kalınlık hem
    azaltılmış kalınlık (t = maks) değeri verilir (V-2b-3; 10.2.3.6.2 azaltılmışı seçenek yapar).
    """
    a = API.ATIF
    atif = f"{a['MANDREL']}, {a['BUKME_GERINIM']}"
    anahtar = re.sub(r"[MQ]$", "", grade)
    if anahtar not in API.BUKME_GERINIM:
        raise EslesmeHatasi(_("{d} {grade}: kalite tabloda yok").format(d=a['BUKME_GERINIM'], grade=grade))
    eps = API.BUKME_GERINIM[anahtar]
    t_maks = API.PARAMETRELER["bukme_t_maks_mm"]
    k = API.PARAMETRELER["mandrel_katsayi"]

    def agb(tk):
        payda = eps * D / tk - 2 * eps - 1
        if payda <= 0:
            raise EslesmeHatasi(_("{atif} D={D} t={tk}: D/t çok küçük, payda ≤ 0 (Denklem 5 tanımsız)").format(atif=atif, D=D, tk=tk))
        return int(excel_round(k * (D - 2 * tk) / payda - tk, 0))

    pay = API.PARAMETRELER["bukme_aciklik_pay_mm"]
    atif += f", {a['BUKME_ACIKLIK']}"

    def aciklik(agb_mm, tk):
        return round(agb_mm + 2 * tk + pay, 2)

    tam = agb(t)
    if t <= t_maks:
        return Mandrel(tam, None, eps, aciklik(tam, t), None, "", atif)
    azaltilmis = agb(t_maks)
    metin = (f"t > {t_maks:g} mm: tam kalınlık numunesi {tam} mm; "
             f"azaltılmış kalınlık numunesi (t = {t_maks:g} mm) {azaltilmis} mm")
    return Mandrel(tam, azaltilmis, eps, aciklik(tam, t), aciklik(azaltilmis, t_maks), metin, atif)


def lot(psl, D):
    """Gövde çekme test birimi büyüklüğü (boru adedi)."""
    if psl != "PSL 2":
        return Deger(None, f"test birimi ({API.ATIF['TEST_BIRIMI']}) — sayısal sınır yok",
                     API.ATIF["TEST_BIRIMI"])
    atif = API.ATIF["LOT_PSL2"]
    s = tek_satir(API.LOT_PSL2, lambda r: aralikta(D, r["d_alt"], r["d_alt_dahil"],
                                                   r["d_ust"], r["d_ust_dahil"]),
                  f"{atif} D={D}")
    return Deger(s["adet"], "aynı soğuk genişletme oranı", atif)


def kutle_toleransi(D, t, grade):
    """Boru başına kütle toleransı (%). Özel hafif boyut Table 9'dan; değilse diğer borular.

    grade: 9.14.1 b) (L175/A25) SAWH kapsamında olmadığından sonucu değiştirmez.
    """
    a = API.ATIF
    oh = _en_fazla_bir(API.OZEL_HAFIF, lambda s: _d_t_icinde(s, D, t),
                       f"{a['OZEL_HAFIF']} D={D} t={t}")
    sinif = "ozel_hafif" if oh is not None else "diger"
    s = tek_satir(API.KUTLE_TOLERANSI, lambda r: r["sinif"] == sinif, f"kütle {sinif}")
    metin = f"özel hafif boyut ({a['OZEL_HAFIF']})" if oh is not None else ""
    return Tolerans(s["arti_yuzde"], s["eksi_yuzde"], metin, s["madde"])


@dataclass(frozen=True)
class BoruGirdisi:
    psl: str            # "PSL 1" | "PSL 2"
    grade: str          # "X70M"
    D: float            # dış çap, mm
    t: float            # et kalınlığı, mm
    L_m: float | None   # boy, m (doğrusallık toplam sapması için)
    amac: str           # "doğalgaz" | "su"


@dataclass(frozen=True)
class BoruSonucu:
    girdi: BoruGirdisi
    cap_govde: Tolerans
    cap_uc: Tolerans
    ovallik_govde: Ovallik
    ovallik_uc: Ovallik
    et: Tolerans
    dogrusallik_toplam: Deger
    dogrusallik_uc: Deger
    radyal_ofset: Deger
    bead_ic: Deger
    bead_dis: Deger
    bead_uc_ic: Deger
    bead_uc_dis: Deger
    malzeme: dict
    rt_rm_maks: Deger
    p_hesap: Deger
    p_test: Deger
    pm: float
    uyarilar: tuple
    charpy: Charpy
    mandrel: Mandrel
    lot: Deger
    kutle: Tolerans


def boru_hesapla(g):
    """Bir kalemin tüm boru gövdesi kabul kriterleri. Eşleşme yoksa EslesmeHatasi."""
    if not API.MALZEME or None in API.PARAMETRELER.values():   # boş veri iskeleti (public kopya)
        raise EslesmeHatasi(_("{std} {baski} verisi yüklü değil (app/itp/veri/api5l_47.py boş ya da eksik); kabul kriteri üretilemez").format(std=API.STANDART, baski=API.BASKI))
    d_maks = API.PARAMETRELER["d_maks_mm"]
    if g.D > d_maks:
        raise EslesmeHatasi(_("D={D} mm > {d_maks:g} mm: {d} izinli çap aralığı dışı ({psl}); değer uydurulmaz").format(D=g.D, d_maks=d_maks, d=API.ATIF['D_MAKS'], psl=g.psl))
    d_min_sawh = API.PARAMETRELER["sawh_d_min_mm"]
    if g.D < d_min_sawh:
        raise EslesmeHatasi(_("D={D} mm < {d_min_sawh:g} mm: {d} izinli çap aralığı dışı (helisel dikişli boru, {psl}); değer uydurulmaz").format(D=g.D, d_min_sawh=d_min_sawh, d=API.ATIF['D_MIN'], psl=g.psl))
    m = malzeme(g.psl, g.grade)
    p_hesap, p_test = hidrostatik_basinc(g.amac, g.D, g.t, m["yield_min"], g.grade)
    dog_toplam, dog_uc = dogrusallik(g.L_m)
    bead_ic, bead_dis = bead(g.t)
    uc_ic, uc_dis = bead_uc()
    uyarilar = []
    tmax = API.PARAMETRELER["kimya_t_maks_mm"]
    if g.t > tmax:
        uyarilar.append(f"t > {tmax:g} mm: kimyasal bileşim tablosu geçerli değil, anlaşmaya bağlı")
    atif_rt = API.ATIF["RT_RM"]
    d_min = API.PARAMETRELER["rt_rm_d_min_mm"]
    if m["rt_rm_maks"] is None:
        rt_rm = Deger(None, "standartta sınır yok", atif_rt)
    elif g.D <= d_min:
        rt_rm = Deger(None, f"D ≤ {d_min:g} mm: Rt0.5/Rm sınırı uygulanmaz", atif_rt)
    else:
        rt_rm = Deger(m["rt_rm_maks"], "", atif_rt)
    return BoruSonucu(
        girdi=g,
        cap_govde=cap_toleransi(g.D, "govde"), cap_uc=cap_toleransi(g.D, "uc"),
        ovallik_govde=ovallik(g.D, g.t, "govde"), ovallik_uc=ovallik(g.D, g.t, "uc"),
        et=et_toleransi(g.t),
        dogrusallik_toplam=dog_toplam, dogrusallik_uc=dog_uc,
        radyal_ofset=radyal_ofset(g.t),
        bead_ic=bead_ic, bead_dis=bead_dis, bead_uc_ic=uc_ic, bead_uc_dis=uc_dis,
        malzeme=m, rt_rm_maks=rt_rm, p_hesap=p_hesap, p_test=p_test, pm=pm(g.D, g.t),
        uyarilar=tuple(uyarilar),
        charpy=charpy(g.D, g.t, g.grade, g.psl), mandrel=mandrel(g.D, g.t, g.grade),
        lot=lot(g.psl, g.D), kutle=kutle_toleransi(g.D, g.t, g.grade),
    )
