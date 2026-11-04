# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""API 5L 47. baskı — SAWH kabul kriteri verisi: BOŞ İSKELET (public depo).

Standart içeriği (tablo değerleri, parametreler) telif kapsamındadır ve bu depoda yoktur.
Değişken adları ve satır yapıları programın beklediği biçimdedir; tablolar boştur, bu yüzden
ITP/KP hesapları "eşleşen satır yok" hatası verir. Kendi lisanslı standardınızdan
doldurduğunuz veriyi aynı adlarla bu dosyaya koyun.

Tolerans üçlüsü (oran, sabit, maks): oran > 0 ise oran × D|t (maks > 0 ise
onunla sınırlı), oran = 0 ise sabit mm. Sınır yoksa None.
"""

STANDART = "API 5L"
BASKI = "47"
# Yalnızca madde/tablo atıfları (değer değil).
ATIF = {'CAP': 'Table 10',
 'ET': 'Table 11',
 'RADYAL_OFSET': 'Table 14',
 'BEAD': 'Table 16',
 'BEAD_UC': '9.13.2.2 c, e',
 'DOGRUSALLIK': '9.11.3.4',
 'K_FAKTORU_su': 'şirket uygulaması',
 'K_FAKTORU_doğalgaz': 'Table 26',
 'KIMYA_PSL 1': 'Table 4',
 'KIMYA_PSL 2': 'Table 5',
 'MEKANIK_PSL 1': 'Table 6',
 'MEKANIK_PSL 2': 'Table 7',
 'UZAMA_PSL 1': 'Table 6 dipnot c',
 'UZAMA_PSL 2': 'Table 7 dipnot f',
 'RT_RM': 'Table 7 dipnot c',
 'CVN_GOVDE': 'Table 8',
 'CVN_KAYNAK': '9.8.3.1',
 'CVN_NUMUNE': 'Table 22',
 'CVN_ALT_BOY': '9.8.1.1',
 'CVN_TEKIL': '9.8.1.2',
 'BUKME_GERINIM': 'Table 23',
 'MANDREL': '10.2.4.6.2 Equation (5)',
 'BUKME_ACIKLIK': 'Figure 9',
 'LOT_PSL2': 'Table 18 No. 3-5',
 'TEST_BIRIMI': '3.1.62',
 'KUTLE_TOLERANSI': '9.14.1',
 'KUTLE_KALEM': '9.14.3',
 'OZEL_HAFIF': 'Table 9',
 'D_MAKS': 'Table 9',
 'D_MIN': 'Table 2 dipnot d'}

PARAMETRELER = {k: None for k in (
    'd_maks_mm', 'sawh_d_min_mm', 'dogrusallik_oran', 'dogrusallik_uc_boy_m',
    'dogrusallik_uc_mm', 'bead_ic_uc_mm', 'bead_dis_uc_mm', 'bead_ic_uc_bolge_mm',
    'bead_dis_uc_bolge_mm', 'rt_rm_d_min_mm', 'kimya_t_maks_mm', 'pm_katsayi',
    'cvn_tekil_oran', 'cvn_sicaklik_c', 'bukme_t_maks_mm', 'bukme_aciklik_pay_mm',
    'kutle_kalem_t', 'uzama_numune_genislik_mm', 'uzama_axc_maks_mm2',
    'uzama_af_katsayi', 'uzama_af_axc_us', 'uzama_af_u_us', 'mandrel_katsayi',
    'kutle_kalem_eksi_yuzde')}

# grade → kalite grubu
K_GRUP = {}
# {'amac', 'grup', 'd_alt', 'd_alt_dahil', 'd_ust', 'd_ust_dahil', ...}
K_FAKTORU = []
# {'d_alt', 'd_alt_dahil', 'd_ust', 'd_ust_dahil', 'govde_arti': (oran, sabit, maks), ...}
CAP = []
# {'t_alt', 't_alt_dahil', 't_ust', 't_ust_dahil', 'arti': (...), 'eksi': (...)}
ET = []
# {'t_alt', 't_alt_dahil', 't_ust', 't_ust_dahil', 'tol': (...), 'not_'}
RADYAL_OFSET = []
# {'t_alt', 't_alt_dahil', 't_ust', 't_ust_dahil', 'ic_maks', 'dis_maks', ...}
BEAD = []
# {'psl', 'celik_sinifi', 'grade', 'kimya': {...}, 'kimya_not', 'yield_min', 'yield_max',
#  'tensile_min', 'tensile_max', 'rt_rm_maks', 'uzama_min', 'dikis_rm_min', 'mekanik_not'}
MALZEME = []
CVN_GOVDE = []
CVN_KAYNAK = []
CVN_NUMUNE = []
# grade → gerinim
BUKME_GERINIM = {}
# {'d_alt', 'd_alt_dahil', 'd_ust', 'd_ust_dahil', 'adet', 'no'}
LOT_PSL2 = []
# {'sinif', 'arti_yuzde', 'eksi_yuzde', 'madde'}
KUTLE_TOLERANSI = []
OZEL_HAFIF = []
