# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Ortak kontrol listesi (Plan 5b): şartname maddelerinin hedefi, şablondan bağımsız kalıcı anahtar.

Bir şartname maddesi bir kez girilir; hangi doküman (itp_en / kp_ciplak / kp_kaplama) kullanılırsa
o kontrolün satır(lar)ına uygulanır (5c). Şablon dosyalarına dokunulmaz: elle yazılmış satırlar
SATIRLAR'da karakteristik metniyle eşlenir (PSL 1/2 karşılık satırları aynı metni taşır). KP kaplama
satırları ISO 21809 verisinden üretilir; anahtarları kaplama_kontrolu(aşama, kriter) verir.
"gelecek": şablonu henüz olmayan kontrol (EN 10217-1 Plan 6; TS EN 10289, TS 5139 Plan 7);
maddesi bugünden kaydedilir, şablon gelince uygulanır.
"""
from app.search_utils import tr_fold


def _k(tr, en, kriterler=(), gelecek=False):
    return {"tr": tr, "en": en, "kriterler": tuple(kriterler), "gelecek": gelecek}


KONTROLLER = {
    # ── boru (API 5L) ──
    "ebat": _k("Ebat (kalem listesi)", "Item list"),
    "baslangic_malzemesi": _k("Başlangıç malzemesi (bobin/levha)", "Hot rolled coil / plate"),
    "bobin_kabul": _k("Bobin kabulü ve depolama", "HRC receipt & storage"),
    "bobin_izlenebilirlik": _k("Bobin besleme, döküm/bobin no", "In-feed coil, heat & coil number"),
    "form_verme": _k("Form verme", "Forming"),
    "kaynak_wps": _k("Kaynak (WPS & PQR)", "Welding (WPS & PQR)"),
    "ndt_dogrulama": _k("Tahribatsız muayene doğrulaması", "NDT verification"),
    "tamir_wps": _k("Kaynak tamiri yöntemi (WPS & PQR)", "Weld repair procedure (WPS & PQR)"),
    "ut_kaynak": _k("Ultrasonik kontrol, kaynak dikişi", "Ultrasonic test, weld seam"),
    "ut_kalibrasyon": _k("Ultrasonik kontrol kalibrasyonu", "Ultrasonic test calibration"),
    "rt_boru_ucu": _k("Radyografik kontrol, boru ucu kaynağı",
                      "Radiographic inspection, weld seam at pipe ends"),
    "boru_boyu": _k("Boru boyu", "Pipe length"),
    "gorsel_ilk": _k("İlk görsel muayene", "First visual inspection"),
    "numune_alma": _k("Test numunesi alma", "Sampling of test coupon"),
    "kaynak_agzi": _k("Kaynak ağzı", "Bevel geometry"),
    "hidrostatik": _k("Hidrostatik test", "Hydrostatic test", ("p_test",)),
    "hidrostatik_gosterge": _k("Hidrostatik test göstergeleri (kalibrasyon, kontrol)",
                               "Hydrostatic test gauges (calibration, check)"),
    "artik_manyetizma": _k("Artık manyetizma", "Residual magnetism"),
    "dis_cap": _k("Dış çap", "Diameter", ("cap_govde", "cap_uc")),
    "et_kalinligi": _k("Et kalınlığı", "Wall thickness", ("et",)),
    "ovalite": _k("Ovalite", "Out-of-roundness", ("ovallik_govde", "ovallik_uc")),
    "dogrusallik": _k("Doğrusallık", "Straightness", ("dogrusallik_toplam", "dogrusallik_uc")),
    "uc_diklik": _k("Boru ucu diklik", "Out-of-squareness"),
    "yuzey_kusurlari": _k("Yüzey kusurları", "Surface imperfections"),
    "geometrik_sapma": _k("Geometrik sapma ve ezik", "Geometric deviations and dents"),
    "kutle": _k("Kütle", "Mass", ("kutle",)),
    "kaynak_geometrisi": _k("Kaynak geometrisi ve makro yapı", "Weld geometry, macro examination",
                            ("radyal_ofset", "bead_ic", "bead_dis", "bead_uc_ic", "bead_uc_dis")),
    "lot": _k("Lot", "Lot", ("lot",)),
    "kimyasal": _k("Kimyasal kompozisyon", "Chemical composition"),
    "cekme": _k("Çekme testi", "Tensile test", ("rt_rm_maks",)),
    "kilavuzlu_bukme": _k("Kılavuzlu bükme testi", "Guided-bend test", ("mandrel",)),
    "sertlik": _k("Sertlik", "Hardness"),
    "charpy": _k("Çentik darbe testi (CVN)", "Charpy impact test (CVN)", ("charpy",)),
    "dwt": _k("DWT testi", "Drop-weight tear test"),
    "tekrar_cekme": _k("Çekme tekrar deneyi", "Tensile retest"),
    "tekrar_charpy": _k("Çentik darbe tekrar deneyi", "Charpy retest"),
    "tekrar_sertlik": _k("Sertlik tekrar deneyi", "Hardness retest"),
    "tamir_kaynagi": _k("Tamir kaynağı", "Weld repair"),
    "uygunsuz_urun": _k("Uygunsuz ürün", "Nonconforming product"),
    "markalama": _k("Markalama", "Marking"),
    "dokumantasyon": _k("Kalite dokümantasyonu", "Final documentation"),
    # ── dış kaplama (ISO 21809-1/-2) ──
    "kaplama_hammadde": _k("Kaplama malzemesi (sipariş, kabul)", "Coating material (order, receipt)"),
    "kaplama_yuzey_on": _k("Kumlama öncesi yüzey ve ısıtma", "Pipe surface & heating before blasting"),
    "kaplama_kumlama_hizi": _k("Kumlama hat hızı", "Blasting line speed"),
    "kaplama_asindirici": _k("Aşındırıcı boyut / şekil / özellikleri",
                             "Abrasive size / shape / properties"),
    "kaplama_hat_girisi": _k("Kaplama hattı girişi muayenesi (flash rust)",
                             "Pipe inspection before entering coating line (flash rust)"),
    "kaplama_yuzey_temizlik": _k("Kumlanmış yüzey temizliği", "Surface cleanliness after blasting"),
    "kaplama_asindirici_kirlilik": _k("Aşındırıcının suda çözünür kirliliği",
                                      "Water soluble contamination of abrasives"),
    "kaplama_cozunur_tuz": _k("Kumlama sonrası çözünür tuz", "Soluble salt after blasting"),
    "kaplama_puruzluluk": _k("Yüzey pürüzlülüğü", "Surface roughness"),
    "kaplama_toz": _k("Toz kirliliği", "Dust contamination"),
    "kaplama_uygulama": _k("Kaplama uygulaması (ön ısıtma, hat hızı, sıcaklıklar)",
                           "Coating application (preheating, line speed, temperatures)"),
    "kaplama_kalinlik_epoksi": _k("Epoksi kat kalınlığı", "Epoxy layer thickness"),
    "kaplama_kalinlik_yapistirici": _k("Yapıştırıcı kat kalınlığı", "Adhesive layer thickness"),
    "kaplama_kalinlik_toplam": _k("Toplam kaplama kalınlığı", "Total coating thickness"),
    "kaplama_sureklilik": _k("Süreklilik (holiday)", "Continuity (holiday)"),
    "kaplama_kur": _k("Kür derecesi", "Degree of cure"),
    "kaplama_soyulma": _k("Soyulma mukavemeti", "Peel strength"),
    "kaplama_darbe": _k("Darbe dayanımı", "Impact strength"),
    "kaplama_indentasyon": _k("İndentasyon", "Indentation"),
    "kaplama_uzama": _k("Kopmada uzama", "Elongation at break"),
    "kaplama_katodik": _k("Katodik ayrılma", "Cathodic disbondment"),
    "kaplama_sicak_su": _k("Sıcak su direnci / yapışması", "Hot water immersion / adhesion"),
    "kaplama_kararlilik": _k("Ürün kararlılığı (ΔMFR)", "Product stability (ΔMFR)"),
    "kaplama_cutback": _k("Cutback", "Cut-back"),
    "kaplama_manyetizma": _k("Kaplama sonrası artık manyetizma",
                             "Residual magnetism after coating application"),
    "kaplama_tamir": _k("Kaplama tamiri", "Coating repair"),
    "kaplama_gozeneklilik": _k("Gözeneklilik", "Porosity"),
    "kaplama_kuru_yapisma": _k("Kuru yapışma", "Dry adhesion"),
    "kaplama_arayuz_kirlilik": _k("Arayüz kirliliği", "Interface contamination"),
    "kaplama_esneklik": _k("Esneklik", "Flexibility"),
    # ── şablonu henüz olmayan (Plan 6-7) ──
    "ic_kaplama_epoksi": _k("İç kaplama, epoksi (TS EN 10289)",
                            "Internal coating, epoxy (TS EN 10289)", gelecek=True),
    "dis_kaplama_pe_ts5139": _k("Dış kaplama, polietilen (TS 5139)",
                                "External coating, polyethylene (TS 5139)", gelecek=True),
    # fabrikanın yaptığı diğer kaplamalar ve muflu boru (V-5b-11, 2026-11-03)
    "dis_kaplama_epoksi": _k("Dış kaplama, epoksi boya", "External coating, epoxy paint",
                             gelecek=True),
    "ic_kaplama_beton": _k("İç kaplama, beton (TS 8590)", "Internal lining, concrete (TS 8590)",
                           gelecek=True),
    "dis_kaplama_beton": _k("Dış kaplama, beton", "External coating, concrete", gelecek=True),
    "muflu_boru": _k("Muflu boru", "Socket-end pipe", gelecek=True),
}

SATIRLAR = {
    "itp_en": {
        "Mechanical, chemical properties, dimensional": "baslangic_malzemesi",
        "Damage, marking, dimensional": "bobin_kabul",
        "Heat & coil number": "bobin_izlenebilirlik",
        "Visual and dimensional inspection": "form_verme",
        "Calibration": "ut_kalibrasyon",
        "Inspection": "ut_kaynak",
        "Control of calibration": "ut_kalibrasyon",
        "Radiographic inspection of weld seam at pipe ends": "rt_boru_ucu",
        "Pipe length": "boru_boyu",
        "Pipe no marking by paint stenciling; visual and dimensional inspection": "gorsel_ilk",
        "Sample geometry": "numune_alma",
        "Bevel geometry": "kaynak_agzi",
        "Calibration of gauges": "hidrostatik_gosterge",
        "Checking of working gauge": "hidrostatik_gosterge",
        "Test pressure and holding time": "hidrostatik",
        "Residual magnetism": "artik_manyetizma",
        "Diameter": "dis_cap",
        "Wall thickness": "et_kalinligi",
        "Out-of-roundness": "ovalite",
        "Straightness": "dogrusallik",
        "Out-of-squareness": "uc_diklik",
        "Surface imperfections": "yuzey_kusurlari",
        "Mass": "kutle",
        "Weld geometry, macro examination": "kaynak_geometrisi",
        "Lot": "lot",
        "Chemical composition": "kimyasal",
        "Tensile test - base material and weld, transverse": "cekme",
        "Guided-bend test": "kilavuzlu_bukme",
        "Hard spots": "sertlik",
        "Charpy impact test (CVN)": "charpy",
        "Drop-weight tear test": "dwt",
        "Tensile retest": "tekrar_cekme",
        "Charpy retest": "tekrar_charpy",
        "Hardness retest": "tekrar_sertlik",
        "Properties of material": "kaplama_hammadde",
        "Damage, marking": "kaplama_hammadde",
        "Pipe surface & heating": "kaplama_yuzey_on",
        "Surface cleanliness": "kaplama_yuzey_temizlik",
        "Water soluble contamination of abrasives": "kaplama_asindirici_kirlilik",
        "Soluble salt after blasting": "kaplama_cozunur_tuz",
        "Surface roughness": "kaplama_puruzluluk",
        "Dust contamination": "kaplama_toz",
        "Preheating, line speed, extrusion temperatures": "kaplama_uygulama",
        "FBE layer thickness": "kaplama_kalinlik_epoksi",
        "Adhesive layer thickness": "kaplama_kalinlik_yapistirici",
        "Total coating thickness": "kaplama_kalinlik_toplam",
        "Continuity": "kaplama_sureklilik",
        "Degree of cure": "kaplama_kur",
        "Peel strength": "kaplama_soyulma",
        "Impact strength": "kaplama_darbe",
        "Indentation": "kaplama_indentasyon",
        "Elongation at break": "kaplama_uzama",
        "Cathodic disbondment": "kaplama_katodik",
        "Hot water immersion": "kaplama_sicak_su",
        "Product stability (ΔMFR)": "kaplama_kararlilik",
        "Cut-back": "kaplama_cutback",
        "Residual magnetism after coating application": "kaplama_manyetizma",
        "Visual inspection": "kaplama_tamir",
        "FBE coating thickness": "kaplama_kalinlik_toplam",
        "Degree of cure (DSC)": "kaplama_kur",
        "Porosity": "kaplama_gozeneklilik",
        "Dry adhesion": "kaplama_kuru_yapisma",
        "Hot-water adhesion": "kaplama_sicak_su",
        "Interface contamination": "kaplama_arayuz_kirlilik",
        "Flexibility at minimum design temperature": "kaplama_esneklik",
        "Impact": "kaplama_darbe",
        "Stencil marking": "markalama",
        "Final documentation": "dokumantasyon",
    },
    "kp_ciplak": {
        "Kalem listesi": "ebat",
        "Çelik üretim yöntemi ve bobin/levha": "baslangic_malzemesi",
        "Form verme": "form_verme",
        "Kaynak": "kaynak_wps",
        "Tahribatsız muayene": "ndt_dogrulama",
        "Kaynak tamiri": "tamir_wps",
        "Kimyasal kompozisyon": "kimyasal",
        "Lot büyüklüğü": "lot",
        "Çekme testi (ana malzeme ve kaynak, enine)": "cekme",
        "Kılavuzlu bükme testi (180°)": "kilavuzlu_bukme",
        "Çentik darbe testi (CVN)": "charpy",
        "DWT testi": "dwt",
        "Lokal sertlik": "sertlik",
        "Çekme tekrar deneyi": "tekrar_cekme",
        "CVN tekrar deneyi": "tekrar_charpy",
        "Sertlik tekrar deneyi": "tekrar_sertlik",
        "Kaynak makro yapısı ve geometrisi": "kaynak_geometrisi",
        "Dış çap": "dis_cap",
        "Et kalınlığı": "et_kalinligi",
        "Ovalite": "ovalite",
        "Boru boyu": "boru_boyu",
        "Doğrusallıktan sapma": "dogrusallik",
        "Ağırlık": "kutle",
        "Geometrik sapma ve ezik": "geometrik_sapma",
        "Boru ucu diklik": "uc_diklik",
        "Kaynak ağzı": "kaynak_agzi",
        "Test basıncı ve tutma süresi": "hidrostatik",
        "Kaynak dikişinin otomatik UT kontrolü": "ut_kaynak",
        "Kalibrasyon kontrolü": "ut_kalibrasyon",
        "Boru ucu kaynağı": "rt_boru_ucu",
        "Artık manyetizma": "artik_manyetizma",
        "Kaynak dikişi tamiri": "tamir_kaynagi",
        "Yüzey kusurları": "yuzey_kusurlari",
        "Uygunsuz ürün": "uygunsuz_urun",
        "Boru markalaması": "markalama",
        "Belgeler": "dokumantasyon",
    },
    "kp_kaplama": {
        "Kalem listesi": "ebat",
        "Toplam kaplama kalınlığı": "kaplama_kalinlik_toplam",
    },
}

# KP kaplama üretici satırları (aşama "yüzey hazırlığı" / "uygulanmış kaplama"): kriter metninde
# geçen ilk ifade kazanır (sıra önemli: özelden genele).
_KAPLAMA_KURALLARI = (
    ("gelen fbe tozu", "kaplama_hammadde"),
    ("suda çözünür", "kaplama_asindirici_kirlilik"),
    ("çözünür tuz", "kaplama_cozunur_tuz"),
    ("pürüzlülüğü", "kaplama_puruzluluk"),
    ("toz giderme", "kaplama_toz"),
    ("görsel muayenesi", "kaplama_yuzey_temizlik"),
    ("aşındırıcının boyut", "kaplama_asindirici"),
    ("ekstrüze", "kaplama_uygulama"),
    ("ön ısıtma", "kaplama_uygulama"),
    ("kumlama hat hızı", "kaplama_kumlama_hizi"),
    ("hat hızı", "kaplama_uygulama"),
    ("kumlama öncesi", "kaplama_yuzey_on"),
    ("ortam koşulları", "kaplama_yuzey_on"),
    ("kaplama hattına", "kaplama_hat_girisi"),
    ("epoksi kalınlığı", "kaplama_kalinlik_epoksi"),
    ("yapıştırıcı kalınlığı", "kaplama_kalinlik_yapistirici"),
    ("kaplama kalınlığı", "kaplama_kalinlik_toplam"),
    ("süreklilik", "kaplama_sureklilik"),
    ("kür derecesi", "kaplama_kur"),
    ("soyulma", "kaplama_soyulma"),
    ("darbe", "kaplama_darbe"),
    ("indentasyon", "kaplama_indentasyon"),
    ("kopmada uzama", "kaplama_uzama"),
    ("katodik ayrılma", "kaplama_katodik"),
    ("sıcak su", "kaplama_sicak_su"),
    ("kararlılığı", "kaplama_kararlilik"),
    ("cutback", "kaplama_cutback"),
    ("manyetizma", "kaplama_manyetizma"),
    ("gözeneklilik", "kaplama_gozeneklilik"),
    ("kuru yapışma", "kaplama_kuru_yapisma"),
    ("arayüz kirliliği", "kaplama_arayuz_kirlilik"),
    ("esneklik", "kaplama_esneklik"),
)


def satir_kontrolu(sablon, karakteristik):
    try:
        return SATIRLAR[sablon][karakteristik]
    except KeyError:
        raise KeyError(f"{sablon}: '{karakteristik}' satırının kontrol anahtarı yok") from None


def kaplama_kontrolu(asama, kriter):
    if asama == "tamir":
        return "kaplama_tamir"
    k = tr_fold(kriter)
    for ifade, anahtar in _KAPLAMA_KURALLARI:
        if tr_fold(ifade) in k:
            return anahtar
    raise KeyError(f"'{asama}' / '{kriter}' kaplama kriterinin kontrol anahtarı yok")


def sablonlari(anahtar):
    """Kontrolün satırı bulunan şablonlar (madde ekleme penceresinde gösterilir)."""
    from app.itp.veri.iso21809 import KRITERLER        # geç: veri yalnız gerektiğinde
    from app.itp.yer_tutucu import KAPLAMA_ASAMALARI
    s = [ad for ad, harita in SATIRLAR.items() if anahtar in harita.values()]
    if "kp_kaplama" not in s and any(
            r[2] in KAPLAMA_ASAMALARI and r[6] != "tablo"
            and kaplama_kontrolu(r[2], r[3]) == anahtar for r in KRITERLER):
        s.append("kp_kaplama")
    return tuple(s)
