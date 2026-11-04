# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Örnek sipariş çıktıları: docs/ornek-cikti/*.xlsx üretir (QUALITY PROGRAM kökünden:
`python tools/ornek_cikti.py`). Siparişler testlerdeki golden verilerle tutarlıdır."""
import dataclasses
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from app.firma import Firma  # noqa: E402
from app.itp.dokuman import Baslik, Kalem  # noqa: E402
from app.itp.excel import excel_yaz  # noqa: E402
from app.itp.olustur import olustur  # noqa: E402

VARSAYILAN_DIZIN = KOK / "docs" / "ornek-cikti"
FIRMA = "ÖRNEK FİRMA"   # kurgusal üretici adı (örnek çıktılar)

# Kurgusal başlıklar (2026-11-02): gerçek müşteri / proje / sipariş / kişi adı yok. Teknik veri
# (çap, et, kalite, kaplama) şablonların esas alındığı siparişlerle aynı (golden testler).
# ITP (EN) başlıkları ASCII: İngilizce belgede Türkçe karakter testi.
KURUM_C_BASLIK = Baslik("ITP-ORNEK-001", "0", "B", "17.03.2026", "EXAMPLE CUSTOMER LTD.",
                     "Example Gas Pipeline Project", "PO-0001", "Quality Engineer",
                     "Quality Manager", "General Manager")
KURUM_A_BASLIK = Baslik("KP-ORNEK-001", "0", "B", "16.04.2026", "ÖRNEK MÜHENDİSLİK LTD.",
                      "Örnek Doğalgaz Deplase Projesi", "SIP-0001", "Kalite Mühendisi",
                      "Kalite Müdürü", "Genel Müdür")
KARISIK_BASLIK = Baslik("ITP-ORNEK-003", "0", "B", "27.10.2026", "EXAMPLE CUSTOMER LTD.",
                        "Mixed PSL Example", "PO-0003", "Quality Engineer", "Quality Manager",
                        "General Manager")


def _kurum_c(no, D, t, kaplama, **kw):
    return Kalem(no=no, psl="PSL 2", grade="X52M", D=D, t=t, boy_m=12, miktar_m=100,
                 amac="doğalgaz", dis_kaplama=kaplama, **kw)


KURUM_C = [_kurum_c(1, 323.9, 7.9, "3LPE", kaplama_sinifi="B", kalinlik_sinifi=2),
        _kurum_c(2, 219, 6.4, "FBE"), _kurum_c(3, 168, 5.6, "FBE"),
        _kurum_c(4, 114.3, 5.6, "3LPE", kaplama_sinifi="B", kalinlik_sinifi=2)]
KURUM_A = [Kalem(no=1, psl="PSL 2", grade="X65M", D=406.4, t=8.7, boy_m=12, miktar_m=650,
               amac="doğalgaz")]
KURUM_A_KAPLAMA = [dataclasses.replace(KURUM_A[0], dis_kaplama="3LPE", kaplama_sinifi="B",
                                     kalinlik_sinifi=2)]
KARISIK = [Kalem(no=1, psl="PSL 1", grade="B", D=219.1, t=6.4, boy_m=12, miktar_m=100,
                 amac="su"),
           Kalem(no=2, psl="PSL 2", grade="X52M", D=323.9, t=7.9, boy_m=12, miktar_m=100,
                 amac="doğalgaz")]

SIPARISLER = [
    ("ITP-ornek.xlsx", "itp_en", KURUM_C_BASLIK, KURUM_C),
    ("KP-ciplak-ornek.xlsx", "kp_ciplak", KURUM_A_BASLIK, KURUM_A),
    ("KP-kaplama-ornek.xlsx", "kp_kaplama", KURUM_A_BASLIK, KURUM_A_KAPLAMA),
    ("ITP-karisik-PSL-ornek.xlsx", "itp_en", KARISIK_BASLIK, KARISIK),
]


def main(dizin=None):
    dizin = Path(dizin) if dizin else VARSAYILAN_DIZIN
    dizin.mkdir(parents=True, exist_ok=True)
    yollar = []
    for ad, sablon, baslik, kalemler in SIPARISLER:
        yol = excel_yaz(olustur(sablon, baslik, kalemler, firma=FIRMA), dizin / ad, Firma(FIRMA))
        print(yol)
        yollar.append(yol)
    return yollar


if __name__ == "__main__":
    main()
