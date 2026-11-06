# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""ITP / Kalite Planı doküman modeli (Plan 2).

Yalnızca veri taşır; şablon + kalemlerden kurulum app/itp/olustur.py'dedir.
Kabul kriteri hücresi parçalardan oluşur (Metin / KalemTablosu / ElleGirilecek) ki
Excel katmanı (Plan 3) metin ayrıştırmadan her türü ayrı biçimlendirebilsin.
"""
from dataclasses import dataclass
from app.dil import _

PSL_DEGERLERI = ("PSL 1", "PSL 2")
AMACLAR = ("doğalgaz", "su")
DIS_KAPLAMALAR = ("çıplak", "3LPE", "3LPP", "FBE")
IC_KAPLAMALAR = ("çıplak",)          # iç kaplama (TS EN 10289) Plan 7
# ISO 21809-1 Table 1: PE → A (LDPE) / B (MDPE, HDPE); PP → C. FBE (ISO 21809-2) sınıfsız.
KAPLAMA_SINIFLARI = {"3LPE": ("A", "B"), "3LPP": ("C",)}
KALINLIK_SINIFLARI = (1, 2, 3)


@dataclass(frozen=True)
class Baslik:
    dokuman_no: str
    rev: str
    idc: str
    tarih: str
    musteri: str
    proje: str
    siparis_no: str
    hazirlayan: str
    inceleyen: str
    onaylayan: str


@dataclass(frozen=True)
class Kalem:
    no: int
    psl: str            # "PSL 1" | "PSL 2"
    grade: str          # "X52M"
    D: float            # dış çap, mm
    t: float            # et kalınlığı, mm
    boy_m: float        # boru boyu, m
    miktar_m: float     # sipariş miktarı, m
    amac: str           # "doğalgaz" | "su"
    dis_kaplama: str = "çıplak"
    ic_kaplama: str = "çıplak"
    kaplama_sinifi: str | None = None     # ISO 21809-1 A/B/C
    kalinlik_sinifi: int | None = None    # ISO 21809-1 Table 2: 1/2/3

    def __post_init__(self):
        if self.psl not in PSL_DEGERLERI:
            raise ValueError(_("Kalem {no}: psl '{psl}' desteklenmiyor {PSL_DEGERLERI}").format(no=self.no, psl=self.psl, PSL_DEGERLERI=PSL_DEGERLERI))
        if self.amac not in AMACLAR:
            raise ValueError(_("Kalem {no}: amaç '{amac}' desteklenmiyor {AMACLAR}").format(no=self.no, amac=self.amac, AMACLAR=AMACLAR))
        # etiketler GUI hata mesajlarıyla aynı (itp_page._sayi: "D", "t", "boy", "miktar")
        for alan, etiket in (("D", "D"), ("t", "t"), ("boy_m", "boy"), ("miktar_m", "miktar")):
            if not getattr(self, alan) > 0:
                raise ValueError(_("Kalem {no}: {etiket} pozitif olmalı ({d})").format(no=self.no, etiket=etiket, d=getattr(self, alan)))
        if self.dis_kaplama not in DIS_KAPLAMALAR:
            raise ValueError(_("Kalem {no}: dış kaplama '{dis_kaplama}' desteklenmiyor {DIS_KAPLAMALAR}").format(no=self.no, dis_kaplama=self.dis_kaplama, DIS_KAPLAMALAR=DIS_KAPLAMALAR))
        if self.ic_kaplama not in IC_KAPLAMALAR:
            raise ValueError(_("Kalem {no}: iç kaplama '{ic_kaplama}' desteklenmiyor {IC_KAPLAMALAR}").format(no=self.no, ic_kaplama=self.ic_kaplama, IC_KAPLAMALAR=IC_KAPLAMALAR))
        siniflar = KAPLAMA_SINIFLARI.get(self.dis_kaplama)
        if siniflar is None:
            if self.kaplama_sinifi is not None or self.kalinlik_sinifi is not None:
                raise ValueError(_("Kalem {no}: {dis_kaplama} için kaplama/kalınlık sınıfı verilmez").format(no=self.no, dis_kaplama=self.dis_kaplama))
            return
        if self.kaplama_sinifi not in siniflar:
            raise ValueError(_("Kalem {no}: {dis_kaplama} için kaplama sınıfı {siniflar} olmalı").format(no=self.no, dis_kaplama=self.dis_kaplama, siniflar=siniflar))
        if self.kalinlik_sinifi not in KALINLIK_SINIFLARI:
            raise ValueError(_("Kalem {no}: kalınlık sınıfı {KALINLIK_SINIFLARI} olmalı").format(no=self.no, KALINLIK_SINIFLARI=KALINLIK_SINIFLARI))


@dataclass(frozen=True)
class Sartname:
    no: int
    metin: str


@dataclass(frozen=True)
class Metin:
    metin: str


@dataclass(frozen=True)
class KalemTablosu:
    basliklar: tuple
    satirlar: tuple


@dataclass(frozen=True)
class ElleGirilecek:
    etiket: str


@dataclass(frozen=True)
class Denetim:
    firma: str
    ucuncu_taraf: str = ""
    musteri: str = ""


@dataclass(frozen=True)
class Iz:
    """Bir şartname maddesinin (ya da sipariş kararının) satıra etkisi (Plan 5c-1); önizlemede
    gösterilir, Excel'e yansımaz."""
    sartname: str        # "Ş.4" / "Spec. 7"; sipariş kararında ""
    kaynak: str          # şartname madde no
    sutun: str           # kabul / frekans / ...; satır düzeyindeki etkide ""
    etki: str            # ek / yerine / metin / uygulanmaz / yeni_satir / siparis
    standart: str = ""   # yerine geçilen standart metin


@dataclass(frozen=True)
class Not:
    """Dokümana uygulanamayan madde ya da bilgi (Plan 5c-1): karsiligi_yok / yeni_rev_var / ezildi."""
    tur: str
    metin: str


@dataclass(frozen=True)
class Satir:
    no: str
    aktivite: str
    spec: str
    sorumlu: str
    karakteristik: str
    frekans: str
    kayit: str
    denetim: Denetim
    kabul: tuple
    kontrol: str = ""        # ortak kontrol anahtarı (Plan 5c-1; olustur yazar)
    uygulanmaz: str = ""     # doluysa şartname gerekçesi; Excel'de satır yer almaz (K9)
    izler: tuple = ()        # Iz kayıtları


@dataclass(frozen=True)
class Bolum:
    no: str
    baslik: str
    satirlar: tuple


@dataclass(frozen=True)
class Dokuman:
    format: str          # "ITP" | "KP"
    dil: str             # "en" | "tr"
    sablon: str
    baslik: Baslik
    kalemler: tuple
    sonuclar: tuple      # Plan 1 BoruSonucu, kalemlerle aynı sıra
    sartnameler: tuple
    bolumler: tuple
    firma: str | None = None   # belgeyi üreten firma adı (2026-11-02); eski görüntülerde yok
    notlar: tuple = ()         # Not kayıtları (Plan 5c-1)

    def elle_girilecekler(self):
        """Dokümandaki ELLE GİRİLECEK etiketleri; tekrarsız, ilk görünme sırasıyla
        (Plan 2b'nin doldurulacak ayrı alanlar listesi)."""
        return tuple(dict.fromkeys(p.etiket for b in self.bolumler for s in b.satirlar
                                   for p in s.kabul if isinstance(p, ElleGirilecek)))
