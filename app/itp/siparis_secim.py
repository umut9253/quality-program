# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Sipariş ekranında şartname seçimi ve önizleme yardımcıları (Plan 5c-2).

Qt'siz: masaüstü ITP sayfası ve (5d) tablet aynı kodu kullanır. Seçim biçimi sipariş kaydının
`sartnameler` alanıdır: [{"id": şartname kayıt id, "gruplar": [grup id]}].
"""
from app.itp.sartname import _SATIR_ADI, YURURLUKTE
from app.itp.dokuman import KalemTablosu, Metin
from app.itp.uygula import UygulamaHatasi, _ayir
from app.search_utils import tr_fold
from app.dil import N_, _

ETKI_ADI = {"ek": N_("ek şart"), "yerine": N_("yerine geçer"), "metin": N_("metin değişikliği"),
            "uygulanmaz": N_("uygulanmaz"), "yeni_satir": N_("şartnameden yeni satır"),
            "siparis": N_("sipariş kararı")}
ISARET = {"yerine": "⇄", "metin": "⇄", "siparis": "⇄", "ek": "+", "yeni_satir": "★"}
UYGULANMAZ_ISARETI = "⊘"
NOT_ADI = {"karsiligi_yok": N_("karşılığı yok"), "yeni_rev_var": N_("yeni revizyon var"),
           "ezildi": N_("uygulanmadı"), "atif_kaybi": N_("atıf kaybı")}
_ALFABE = "abcçdefgğhıijklmnoöprsştuüvyz"


def _sira(metin):
    """Türk alfabesi sırası (ç c ile d, ğ g ile h, ö o ile p, ş s ile t, ü u ile v arasında).
    tr_fold ı/i ve I/İ'yi aynı harfe katladığından ı ile i ayrılmaz (doğrulama D-5)."""
    return tuple(_ALFABE.index(c) if c in _ALFABE else 100 + ord(c) for c in tr_fold(metin.strip()))


def _aile(k):
    return tr_fold(k["kurum"].strip()), tr_fold(k["ad"].strip())


def _etiket(k):
    parcalar = [k["ad"].strip()] + ([k["no"].strip()] if k["no"].strip() else [])
    return f"{', '.join(parcalar)} Rev. {k['rev']}"


def secim_satirlari(kayitlar):
    """Seçim penceresinin satırları: yalnız yürürlükteki revizyonlar (B5), kurum / ad / rev_sira
    sırasıyla (V-5c2-3). yeni_rev: aynı ailede daha yeni yürürlükteki revizyon varsa "Rev. n"."""
    yururlukte = [(i, k) for i, k in kayitlar.items() if k["durum"] == YURURLUKTE]
    yururlukte.sort(key=lambda p: (_sira(p[1]["kurum"]), _sira(p[1]["ad"]), p[1]["rev_sira"]))
    satirlar = []
    for i, k in yururlukte:
        yeni = [r for __, r in yururlukte if _aile(r) == _aile(k) and r["rev_sira"] > k["rev_sira"]]
        son = max(yeni, key=lambda r: r["rev_sira"]) if yeni else None
        satirlar.append({"id": i, "etiket": _etiket(k), "tur": k["tur"],
                         "gruplar": [(g["id"], g["ad"]) for g in k["gruplar"]],
                         "yeni_rev": f"Rev. {son['rev']}" if son else ""})
    return satirlar


def secim_kontrol(secim, kayitlar):
    """Pencereden dönen seçim: aynı ailenin iki revizyonu birlikte seçilemez (motorla aynı kural)."""
    gorulen = set()
    for s in secim:
        k = kayitlar.get(s["id"])
        if k is None:
            continue
        if _aile(k) in gorulen:
            raise UygulamaHatasi(_("{ad}: aynı şartnamenin iki revizyonu birlikte seçilemez.")
                                 .format(ad=k["ad"]))
        gorulen.add(_aile(k))


def ozel_temizle(siparis_ozel, secim, kararlar_da=False):
    """Seçimden çıkarılan şartnamenin çeviri cevapları atılır; hücre kararları (madde None)
    yalnız kararlar_da ise (V-5c2-7)."""
    secili = {s["id"] for s in secim}
    return [o for o in siparis_ozel
            if (o.get("madde") is None and not kararlar_da)
            or (o.get("madde") is not None and o["madde"][0] in secili)]


def secim_ozeti(secim, kayitlar):
    parcalar = []
    for s in secim:
        k = kayitlar.get(s["id"])
        if k is None:
            parcalar.append(_("(kayıt {id} bulunamadı)").format(id=s["id"]))
            continue
        metin = f"{k['ad']} Rev. {k['rev']}"
        if s["gruplar"]:
            metin += " " + _("(+{n} grup)").format(n=len(s["gruplar"]))
        parcalar.append(metin)
    return "; ".join(parcalar)


def iz_metni(iz):
    """Önizleme ipucu satırı: "Ş.4 Md. 5.2 — kabul kriteri: yerine geçer · standart: …"."""
    kim = f"{iz.sartname} {iz.kaynak}".strip() or _("Sipariş kararı")
    ne = _(ETKI_ADI.get(iz.etki, iz.etki))
    if iz.sutun in _SATIR_ADI:
        ne = f"{_(_SATIR_ADI[iz.sutun])}: {ne}"
    metin = f"{kim} — {ne}"
    if iz.standart:
        std = iz.standart if len(iz.standart) <= 200 else iz.standart[:199] + "…"
        metin += " · " + _("standart: {s}").format(s=std)
    return metin


def isaret(satir):
    """Satırın önizleme işareti (V-5c2-8): uygulanmaz önce, sonra en güçlü etki."""
    if satir.uygulanmaz:
        return UYGULANMAZ_ISARETI
    etkiler = {iz.etki for iz in satir.izler}
    for etki in ("yeni_satir", "yerine", "metin", "siparis", "ek"):
        if etki in etkiler:
            return ISARET[etki]
    return ""


# ── önizlemede düzeltme (Plan 5c-3) ─────────────────────────────────
def satir_hedefi(dokuman, bi, si):
    """Önizlemedeki satırın kalıcı hedefi (V-5c3-2): (kontrol, karakteristik, sıra). Karakteristik
    kalem etiketiyle birlikte (kalem silinince düzeltme başka kaleme kaymasın; doğrulama ORTA-1);
    sıra = aynı kontrol ve karakteristikteki satırlardan kaçıncısı (0'dan)."""
    hedef = dokuman.bolumler[bi].satirlar[si]
    kok = hedef.karakteristik
    sira = 0
    for b_i, b in enumerate(dokuman.bolumler):
        for s_i, s in enumerate(b.satirlar):
            if (b_i, s_i) == (bi, si):
                return hedef.kontrol, kok, sira
            if s.kontrol == hedef.kontrol and s.karakteristik == kok:
                sira += 1
    raise IndexError((bi, si))


def hucre_metni(satir, sutun):
    """Düzeltme penceresinin başlangıç metni; kabulde atıf parçası hariç (V-5c3-4)."""
    if sutun == "kabul":
        govde, __ = _ayir(satir.kabul)
        return "\n".join(p.metin if isinstance(p, Metin) else _("[tablo]")
                         if isinstance(p, KalemTablosu) else f"[{p.etiket}]" for p in govde)
    return satir.denetim.firma if sutun == "denetim" else getattr(satir, sutun)


def _ayni_hedef(o, hedef, sutun):
    return (o.get("madde") is None and o.get("satir") is not None and o["sutun"] == sutun
            and (o["kontrol"], o["satir"], o.get("sira")) == hedef)


def duzeltme_bul(siparis_ozel, hedef, sutun):
    return next((o for o in siparis_ozel if _ayni_hedef(o, hedef, sutun)), None)


def duzeltme_yaz(siparis_ozel, hedef, sutun, dil, metin):
    """Aynı hedef ve sütunun önceki düzeltmesi atılır; metin None ise yalnız silinir. Diğer dil
    boş bırakılır (değişen metnin eski çevirisi geçersiz; gerekirse sorulur)."""
    kalan = [o for o in siparis_ozel if not _ayni_hedef(o, hedef, sutun)]
    if metin is None:
        return kalan
    kontrol, kok, sira = hedef
    diger = "en" if dil == "tr" else "tr"
    return kalan + [{"kontrol": kontrol, "sutun": sutun, "metin": {dil: metin, diger: ""},
                     "kaynak": "siparis", "madde": None, "satir": kok, "sira": sira}]
