# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""app/ozet.py: ana sayfa özeti ve "dikkat gerektirenler" listesi (GUI'siz)."""
from datetime import date

from app.ozet import SEKME, ozet

BUGUN = date(2026, 10, 29)


def veri(**kw):
    v = dict(wps=[], pqr=[], std=[], cert=[])
    v.update(kw)
    return v


def test_bos_veride_dikkat_yok():
    o = ozet(**veri(), bugun=BUGUN)
    assert o["dikkat"] == []
    assert o["kaynak"]["wps_toplam"] == 0 and o["belge"]["cert_toplam"] == 0


def test_kaynak_grubu():
    o = ozet(**veri(
        wps=[{"no": "W1", "durum": "Aktif", "pqr": "P1"},
             {"no": "W2", "durum": "Revizyon Bekliyor", "pqr": ""},
             {"no": "W3", "durum": "İptal", "pqr": "P9"}],
        pqr=[{"no": "P1", "test": "Geçti"}, {"no": "P2", "test": "Beklemede"},
             {"no": "P3", "test": "Başarısız"}]), bugun=BUGUN)
    k = o["kaynak"]
    assert (k["wps_toplam"], k["wps_aktif"], k["wps_revizyon"], k["wps_iptal"]) == (3, 1, 1, 1)
    assert k["wps_pqrsiz"] == 1                      # boş pqr alanı
    assert (k["pqr_toplam"], k["pqr_gecti"], k["pqr_bekliyor"], k["pqr_basarisiz"]) == (3, 1, 1, 1)
    assert k["pqr_wpssiz"] == 2                       # P2, P3'e bağlı WPS yok


def test_belge_grubu_ve_en_yakin():
    o = ozet(**veri(
        std=[{"no": "S1", "status": "guncel"}, {"no": "S2", "status": "guncelleme"},
             {"no": "S3", "status": "manuel"}, {"no": "S4", "status": "hata"},
             {"no": "S5", "status": "kontrol", "lastCheck": "2026-10-20"}],
        cert=[{"no": "C1", "bitis": "2026-10-01"},                 # dolmuş
              {"no": "C2", "ad": "ISO 9001", "bitis": "2026-11-10"},  # 12 gün
              {"no": "C3", "bitis": "2026-12-20"},                 # 52 gün
              {"no": "C4", "bitis": "2028-01-01"},                 # geçerli
              {"no": "C5", "bitis": ""}]), bugun=BUGUN)
    b = o["belge"]
    assert (b["std_toplam"], b["std_guncel"], b["std_guncelleme"], b["std_kontrol"]) == (5, 1, 1, 3)
    assert b["std_son_kontrol"] == "2026-10-20"
    assert (b["cert_toplam"], b["cert_gecerli"], b["cert_yakinda"], b["cert_dolmus"],
            b["cert_tarihsiz"]) == (5, 1, 2, 1, 1)
    assert b["cert_en_yakin"] == ("ISO 9001", 12)


def test_dikkat_onceligi_ve_sekmeler():
    o = ozet(**veri(
        wps=[{"no": "W1", "durum": "Revizyon Bekliyor", "pqr": ""}],
        pqr=[{"no": "P1", "test": "Başarısız"}],
        std=[{"no": "API 5L", "status": "guncelleme"}],
        cert=[{"no": "C1", "bitis": "2026-10-01"}, {"no": "C2", "bitis": "2026-11-10"}]),
        bugun=BUGUN)
    d = o["dikkat"]
    seviyeler = [x["seviye"] for x in d]
    assert seviyeler == sorted(seviyeler, key=["kritik", "uyari", "bilgi"].index)
    assert d[0]["seviye"] == "kritik"
    sekmeler = {x["sekme"] for x in d}
    assert {SEKME["cert"], SEKME["pqr"], SEKME["std"], SEKME["wps"]} <= sekmeler
    metin = " ".join(x["metin"] for x in d)
    assert "API 5L" in metin and "süresi dolmuş" in metin


def test_uzun_ad_listesi_kisaltilir():
    std = [{"no": f"S{i}", "status": "guncelleme"} for i in range(10)]
    o = ozet(**veri(std=std), bugun=BUGUN)
    m = o["dikkat"][0]["metin"]
    assert "S0" in m and "S9" not in m and "+7" in m
