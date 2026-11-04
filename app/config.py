# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""
Uygulama sabitleri: seçim listeleri, tablo sütunları, durum renkleri ve
Türkçe alan etiketleri. UI'nın her yerinde tek kaynaktan beslenir.
"""
from .dil import N_, _

_ONBELLEK_ANAHTARI = "b3d508a34fed74202ce45f4f9f1f96ed"   # tema / ayar önbelleği sürüm anahtarı

# ── Seçim listeleri ──────────────────────────────────────────────────
PROSESLER   = ["SMAW", "GTAW", "GMAW", "FCAW", "SAW", "PAW"]
POZISYONLAR = ["1G", "2G", "3G", "4G", "5G", "6G", "1F", "2F", "3F", "4F",
               "PA", "PB", "PC", "PD", "PE", "PF", "PG"]
POLARITELER = ["DCEP", "DCEN", "DC(+)", "DC(-)", "AC"]
DURUMLAR    = [N_("Aktif"), N_("Revizyon Bekliyor"), N_("İptal")]
PWHT_SEC    = [N_("Yok"), N_("Var")]
TEST_SEC    = [N_("Geçti"), N_("Başarısız"), N_("Beklemede")]
ORGANIZASYONLAR = ["ASME", "AWS", "EN ISO", "TSE", "ISO", "API", "DIN",
                   "AWWA", "ASTM", "ANSI", "BS EN"]

# Sertifika sekmesi için kuruluş/tip önerileri (serbest metin de girilebilir)
CERT_TIPLERI = [
    "ISO 9001", "ISO 14001", "ISO 45001", "ISO 3834-2", "ISO 3834-3",
    "EN 1090-1 (CE)", "EN 1090-2", "API Q1", "API 5L", "PED 2014/68/EU",
    "AD 2000-Merkblatt", "ISO 50001",
]
CERT_KURULUSLAR = ["TÜV NORD", "TÜV SÜD", "TÜV AUSTRIA", "SGS", "Bureau Veritas",
                   "DNV", "Lloyd's Register", "TSE", "DEKRA"]

# Sertifika "yakında dolacak" eşiği (gün)
CERT_UYARI_GUN = 60

# Otomatik standart taraması haftalık döngüsünün BAŞLANGIÇ günü
# (0=Pazartesi, 1=Salı ... 6=Pazar). Tarama haftada 1 kez yapılır ama güne
# bağlı değildir: bu günde başlayan hafta içinde henüz taranmamış kayıtlar,
# programın o haftaki İLK açılışında taranır (pazartesi açılmazsa kaçmaz).
# Manuel "Güncelleme Kontrol" butonu her gün kullanılabilir.
STD_OTO_KONTROL_GUNU = 0

# NOT: Durum renkleri (STATUS_WPS/PQR/STD/CERT) tema bağımlı olduğundan
# app/theme.py içine taşındı; theme.status("wps"|"pqr"|"std"|"cert") ile alınır.

# ── Tablo sütunları: (başlık, veri anahtarı, genişlik) ───────────────
COLS_WPS = [
    (N_("WPS No"), "no", 130), (N_("Rev."), "rev", 60), (N_("Tarih"), "tarih", 100),
    (N_("Bağlı PQR"), "pqr", 150), (N_("Proses"), "proses", 88),
    (N_("Metal Grubu"), "metal", 118), (N_("Dolgu Malz."), "dolgu", 118),
    (N_("Pozisyon"), "pozisyon", 95), (N_("Ön Isıtma"), "onisitma", 100),
    (N_("PWHT"), "pwht", 72), (N_("Akım (A)"), "akim", 92), (N_("Voltaj (V)"), "voltaj", 95),
    (N_("Hız"), "hiz", 80), (N_("Durum"), "durum", 140),
]
COLS_PQR = [
    (N_("PQR No"), "no", 170), (N_("Rev."), "rev", 60), (N_("Tarih"), "tarih", 100),
    (N_("Proses"), "proses", 88), (N_("Metal Grubu"), "metal", 118),
    (N_("Dolgu Malz."), "dolgu", 120), (N_("Ön Isıtma"), "onisitma", 100),
    (N_("PWHT"), "pwht", 72), (N_("Akım (A)"), "akim", 92), (N_("Voltaj (V)"), "voltaj", 95),
    (N_("Test Sonucu"), "test", 118), (N_("Test Kuruluşu"), "lab", 138),
    (N_("Bağlı WPS"), "_wps_count", 98),
]
COLS_STD = [
    (N_("Standart No"), "no", 150), (N_("Başlık"), "title", 280), (N_("Kuruluş"), "org", 90),
    (N_("Elimdeki Sürüm"), "myVer", 135), (N_("Son Sürüm"), "lastVer", 140),
    (N_("Son Kontrol"), "lastCheck", 115), (N_("Durum"), "status", 165),
]
COLS_CERT = [
    (N_("Belge No"), "no", 150), (N_("Sertifika / Standart"), "ad", 200),
    (N_("Kuruluş"), "org", 130), (N_("Kapsam"), "kapsam", 220),
    (N_("Düzenleme"), "tarih", 100), (N_("Bitiş"), "bitis", 100),
    (N_("Kalan"), "_kalan", 110), (N_("Durum"), "_durum", 150),
]

# ── Pas-by-pas (paso) tablo kolonları: (anahtar, başlık) ─────────────
PASS_COLS = [
    ("paso", N_("Paso")), ("yontem", N_("Yöntem")), ("cap", N_("Çap")),
    ("sinif", N_("Sınıf/Marka")), ("akim", N_("Akım (A)")), ("voltaj", N_("Voltaj (V)")),
    ("polarite", N_("Polarite")), ("tel_surme", N_("Tel Sürme")),
    ("isi_girdisi", N_("Isı Girdisi")),
]

# ── Test alt-tablo kolonları ────────────────────────────────────────
CEKME_COLS = [("no", N_("Numune")), ("reh", N_("ReH (N/mm²)")), ("rm", N_("Rm (N/mm²)")),
              ("uzama", N_("Uzama %")), ("kirilma", N_("Kırılma Yeri")), ("sonuc", N_("Sonuç"))]
EGME_COLS  = [("no", N_("Numune")), ("tur", N_("Tür")), ("aci", N_("Açı")), ("sonuc", N_("Sonuç"))]
CENTIK_COLS = [("yer", N_("Konum")), ("sicaklik", N_("Sıcaklık")),
               ("degerler", N_("Değerler (J)")), ("ort", N_("Ortalama (J)")), ("sonuc", N_("Sonuç"))]

# Skalar (tek satırlık) test alanları: anahtar → etiket
SCALAR_TESTS = {
    "gozle": N_("Gözle Muayene (VT)"), "penetrant": N_("Penetrant (PT)"),
    "manyetik": N_("Manyetik Parçacık (MT)"), "radyografik": N_("Radyografik (RT)"),
    "ultrasonik": N_("Ultrasonik (UT)"), "makro": N_("Makro İnceleme"),
    "sertlik": N_("Sertlik Testi"),
}

# ── Detay skalar alanları (WPS/PQR ortak) ───────────────────────────
# (anahtar, etiket, placeholder)
DETAY_ALANLARI = [
    ("standart",        N_("İlgili Standart"),       N_("Ör: EN ISO 15609")),
    ("yeterlilik",      N_("Yeterlilik Standardı"),  N_("Ör: EN ISO 15614-1")),
    ("kaynak_tipi",     N_("Kaynak Tipi"),           N_("Ör: BW – Alın Kaynağı")),
    ("malzeme",         N_("Malzeme Spesifikasyonu"),N_("Ör: S355J2 / S355J2")),
    ("malzeme_grubu",   N_("Malzeme Grubu"),         N_("Ör: Grup 1.2")),
    ("kalinlik",        N_("Malzeme Kalınlığı"),     N_("Ör: 3–20 mm")),
    ("gaz",             N_("Koruyucu Gaz"),          N_("Ör: EN ISO 14175 M21")),
    ("gaz_debisi",      N_("Gaz Debisi"),            N_("Ör: 12–15 lt/min")),
    ("tungsten",        N_("Tungsten Elektrot"),     N_("Ör: WT20 Ø2.4")),
    ("pasolar_arasi",   N_("Pasolar Arası Sıcaklık"),N_("Ör: Max. 200 °C")),
    ("paso_tipi",       N_("Paso Tipi"),             N_("Ör: Düz Paso")),
    ("joint_design",    N_("Kaynak Ağzı"),           N_("Ör: 60° V kaynak ağzı")),
    ("kaynakci",        N_("Kaynakçı"),              ""),
    ("muayene_kurulusu",N_("Muayene Kuruluşu"),      ""),
    ("rapor_no",        N_("Rapor No"),              ""),
    ("hazirlayan",      N_("Hazırlayan"),            ""),
    ("onaylayan",       N_("Onaylayan"),             ""),
    ("belge_no",        N_("Belge No"),              ""),
]

# Detay penceresinde gösterim için Türkçe etiketler (özet + detay)
DETAIL_LABELS = {
    "no": N_("No"), "rev": N_("Revizyon"), "tarih": N_("Tarih"), "pqr": N_("Bağlı PQR"),
    "proses": N_("Kaynak Yöntemi"), "metal": N_("Ana Metal"), "dolgu": N_("Dolgu Malzemesi"),
    "pozisyon": N_("Kaynak Pozisyonu"), "onisitma": N_("Ön Isıtma (°C)"), "pwht": N_("PWHT"),
    "akim": N_("Akım (A)"), "voltaj": N_("Voltaj (V)"), "hiz": N_("Hız (mm/dk)"),
    "polarite": N_("Polarite"), "durum": N_("Durum"), "test": N_("Test Sonucu"),
    "lab": N_("Test Kuruluşu"),
}
DETAIL_LABELS.update({k: lbl for k, lbl, __ in DETAY_ALANLARI})
