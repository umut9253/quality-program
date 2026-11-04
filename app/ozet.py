# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Ana sayfa özeti: kaynak prosedürleri (WPS/PQR), belge takibi (standart/sertifika) ve
öncelik sıralı "dikkat gerektirenler" listesi.

Saf mantık (Qt yok): masaüstü ana sayfa ve tablet API'si aynı özeti kullanır.
"""
from . import config as C
from .database import parse_iso
from .dil import _

# stacked sayfa indeksleri (CLAUDE.md: sekme indeksleri sabit)
SEKME = {"ana": 0, "wps": 1, "pqr": 2, "std": 3, "cert": 4, "itp": 5}
SEVIYELER = ("kritik", "uyari", "bilgi")
AD_SINIRI = 3           # dikkat metninde gösterilen en fazla kayıt adı


def _adlar(kayitlar):
    adlar = [k.get("no") or k.get("ad") or "—" for k in kayitlar]
    ek = f" +{len(adlar) - AD_SINIRI}" if len(adlar) > AD_SINIRI else ""
    return ", ".join(adlar[:AD_SINIRI]) + ek


def _cert_adi(c):
    return c.get("ad") or c.get("folder_no") or c.get("no") or "—"


def ozet(wps, pqr, std, cert, bugun, uyari_gun=C.CERT_UYARI_GUN):
    """{"kaynak": {...}, "belge": {...}, "dikkat": [{seviye, metin, sekme, sayi}]}"""
    wps_aktif = [w for w in wps if w.get("durum") == "Aktif"]
    wps_rev = [w for w in wps if w.get("durum") == "Revizyon Bekliyor"]
    wps_iptal = [w for w in wps if w.get("durum") == "İptal"]
    wps_pqrsiz = [w for w in wps if not (w.get("pqr") or "").strip()]
    bagli_pqr = {(w.get("pqr") or "").strip() for w in wps}
    pqr_gecti = [p for p in pqr if p.get("test") == "Geçti"]
    pqr_bek = [p for p in pqr if p.get("test") == "Beklemede"]
    pqr_bas = [p for p in pqr if p.get("test") == "Başarısız"]
    pqr_wpssiz = [p for p in pqr if p.get("no") not in bagli_pqr]

    std_guncel = [s for s in std if s.get("status") == "guncel"]
    std_gunc = [s for s in std if s.get("status") == "guncelleme"]
    std_kontrol = [s for s in std if s.get("status") not in ("guncel", "guncelleme")]
    kontroller = [s.get("lastCheck") for s in std if s.get("lastCheck")]

    durum = {"gecerli": [], "yakinda": [], "dolmus": [], "belirsiz": []}
    en_yakin = None
    for c in cert:
        st, kalan = _cert_durum(c, bugun, uyari_gun)
        durum[st].append(c)
        if kalan is not None and kalan >= 0 and (en_yakin is None or kalan < en_yakin[1]):
            en_yakin = (_cert_adi(c), kalan)

    kaynak = {
        "wps_toplam": len(wps), "wps_aktif": len(wps_aktif), "wps_revizyon": len(wps_rev),
        "wps_iptal": len(wps_iptal), "wps_pqrsiz": len(wps_pqrsiz),
        "pqr_toplam": len(pqr), "pqr_gecti": len(pqr_gecti), "pqr_bekliyor": len(pqr_bek),
        "pqr_basarisiz": len(pqr_bas), "pqr_wpssiz": len(pqr_wpssiz),
    }
    belge = {
        "std_toplam": len(std), "std_guncel": len(std_guncel), "std_guncelleme": len(std_gunc),
        "std_kontrol": len(std_kontrol), "std_son_kontrol": max(kontroller) if kontroller else None,
        "cert_toplam": len(cert), "cert_gecerli": len(durum["gecerli"]),
        "cert_yakinda": len(durum["yakinda"]), "cert_dolmus": len(durum["dolmus"]),
        "cert_tarihsiz": len(durum["belirsiz"]), "cert_en_yakin": en_yakin,
    }

    dikkat = []
    def ekle(seviye, kayitlar, metin, sekme):
        if kayitlar:
            dikkat.append({"seviye": seviye, "metin": metin, "sekme": SEKME[sekme],
                           "sayi": len(kayitlar)})

    ekle("kritik", durum["dolmus"],
         _("{d} sertifikanın süresi dolmuş: {d2}").format(d=len(durum['dolmus']), d2=_adlar([{'no': _cert_adi(c)} for c in durum['dolmus']])), "cert")
    ekle("kritik", pqr_bas, _("{d} PQR başarısız: {d2}").format(d=len(pqr_bas), d2=_adlar(pqr_bas)), "pqr")
    yakin = sorted(durum["yakinda"], key=lambda c: c.get("bitis") or "")
    ekle("uyari", yakin, _("{d} sertifika {uyari_gun} gün içinde dolacak: {d2}").format(d=len(yakin), uyari_gun=uyari_gun, d2=_adlar([{'no': _cert_adi(c)} for c in yakin])), "cert")
    ekle("uyari", std_gunc, _("{d} standartta yeni sürüm var: {d2}").format(d=len(std_gunc), d2=_adlar(std_gunc)),
         "std")
    ekle("uyari", wps_pqrsiz, _("{d} WPS'in bağlı PQR'si yok: {d2}").format(d=len(wps_pqrsiz), d2=_adlar(wps_pqrsiz)),
         "wps")
    ekle("uyari", wps_rev, _("{d} WPS revizyon bekliyor: {d2}").format(d=len(wps_rev), d2=_adlar(wps_rev)), "wps")
    ekle("bilgi", pqr_bek, _("{d} PQR test sonucu bekliyor: {d2}").format(d=len(pqr_bek), d2=_adlar(pqr_bek)), "pqr")
    ekle("bilgi", std_kontrol, _("{d} standart elle kontrol bekliyor (manuel / hata / hiç kontrol edilmedi)").format(d=len(std_kontrol)), "std")
    ekle("bilgi", durum["belirsiz"], _("{d} sertifikanın bitiş tarihi yok").format(d=len(durum['belirsiz'])),
         "cert")
    dikkat.sort(key=lambda x: SEVIYELER.index(x["seviye"]))   # kararlı: grup içi sıra korunur
    return {"kaynak": kaynak, "belge": belge, "dikkat": dikkat}


def _cert_durum(c, bugun, uyari_gun):
    """database.cert_status'un verilen günle hali (cert_status bugünü kendi alır; test edilemez)."""
    bitis = parse_iso(c.get("bitis"))
    if bitis is None:
        return "belirsiz", None
    kalan = (bitis - bugun).days
    if kalan < 0:
        return "dolmus", kalan
    if kalan <= uyari_gun:
        return "yakinda", kalan
    return "gecerli", kalan
