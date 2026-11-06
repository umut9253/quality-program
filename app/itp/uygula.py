# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Şartname uygulama motoru (Plan 5c-1;
spec docs/superpowers/specs/2026-11-06-itp-plan5c1-uygulama-motoru-design.md).

Qt'siz: masaüstü ve (5d) tablet aynı kodu kullanır. olustur'un kurduğu Dokuman'a siparişte
seçilen yürürlükteki şartname revizyonlarının maddelerini uygular:
- öncelik: sipariş kararı (3) > özel teknik (2) > genel (1) > standart;
- şablonda satırı olan kontrolün ek satır maddesi o satırla birleşir (C2): "ek" standart metnin
  arkasına, "yerine" yerine; kabulün atıf parçasına "<Ş.n> <kaynak>" eklenir;
- metin maddesi sütunun yerine geçer; uygulanmaz satırları gerekçeyle işaretler (Excel'de çıkar);
  yeni bölümlü ek satır kontrolün bölümünden sonra yeni bölüm açar.
Uygulanamayan her madde UygulamaHatasi, soru (CakismaSorusu / CeviriSorusu) ya da Not üretir.
"""
import dataclasses
import re

from app.itp.dokuman import Bolum, Denetim, Iz, KalemTablosu, Metin, Not, Sartname, Satir
from app.itp.kontrol import KONTROLLER
from app.itp.olustur import ayrilmis_bolumler, numaralari_sirala
from app.itp.sartname import (_SATIR_ADI, SATIR_ALANLARI, YURURLUKTE, SartnameHatasi,
                              madde_dogrula)
from app.search_utils import tr_fold
from app.dil import _

KATMAN = {"genel": 1, "ozel": 2}
SIPARIS = 3
SUTUNLAR = ("karakteristik", "kabul", "frekans", "sorumlu", "kayit", "denetim")
BIRLESEN = ("kabul", "frekans", "sorumlu", "kayit", "denetim")   # ek satırın satıra birleşen sütunları
EKLENEBILIR = ("kabul", "frekans", "kayit", "denetim")           # "ek"; sorumlu yalnız yerine (C2)
_ATIF = re.compile(r"^(Spec\. ?\d|Ş\.\d|ISO |API |EN )")
_KALEM_EKI = re.compile(r" \((?:Kalem|Item)[^()]*\)$")
_GOMULU_ATIF = re.compile(r"(?:Spec\. ?\d+|Ş\.\d+)[^;()]*")


class UygulamaHatasi(Exception):
    """Seçim uygulanamaz; mesaj kullanıcıya gösterilir."""


class CakismaSorusu(Exception):
    """Aynı katmanda aynı hücreye farklı değer (K2/B7). 5c-2 sorar; cevap siparis_ozel'e
    ("madde": None) yazılır."""

    def __init__(self, kontrol, sutun, adaylar, ad=None):
        self.kontrol, self.sutun, self.adaylar = kontrol, sutun, tuple(adaylar)
        super().__init__(_("{k} / {s}: şartnameler farklı değer veriyor: {a}").format(
            k=ad or kontrol, s=sutun,
            a="; ".join(f"{e} {kay}: {x}" for e, kay, x in self.adaylar)))


class CeviriSorusu(Exception):
    """Maddenin doküman dilindeki metni boş (K11/C5). 5c-2 sorar; cevap siparis_ozel'e
    ("madde": [şartname id, madde id]) yazılır."""

    def __init__(self, kontrol, sutun, sartname_id, madde_id, etiket, diger, ad=None):
        self.kontrol, self.sutun, self.madde = kontrol, sutun, [sartname_id, madde_id]
        self.etiket, self.diger = etiket, diger
        super().__init__(_("{e}: «{k}» / {s} metni bu dokümanın dilinde boş (diğer dilde: {d})")
                         .format(e=etiket, k=ad or kontrol, s=sutun, d=diger))


@dataclasses.dataclass(frozen=True)
class _M:
    katman: int
    sid: object          # şartname kayıt id; sipariş kararında None
    etiket: str          # "Ş.4" / "Spec. 7"; sipariş kararında ""
    madde: dict

    @property
    def kaynak(self):
        return self.madde["kaynak"]

    @property
    def atif(self):
        return f"{self.etiket} {self.kaynak}".strip()


def _aile(k):
    return tr_fold(k["kurum"].strip()), tr_fold(k["ad"].strip())


def _secim_dogrula(secim, kayitlar):
    out, aileler = [], set()
    for s in secim:
        k = kayitlar.get(s["id"])
        if k is None:
            raise UygulamaHatasi(_("Seçili şartname (kayıt {id}) bulunamadı; silinmiş olabilir.")
                                 .format(id=s["id"]))
        ad = f"{k['ad']} Rev. {k['rev']}"
        if k["durum"] != YURURLUKTE:
            raise UygulamaHatasi(_("{ad} yürürlükte değil; siparişte yalnız yürürlükteki revizyon "
                                   "kullanılır.").format(ad=ad))
        if _aile(k) in aileler:
            raise UygulamaHatasi(_("{ad}: aynı şartnamenin iki revizyonu birlikte seçilemez.")
                                 .format(ad=k["ad"]))
        aileler.add(_aile(k))
        yok = [g for g in s["gruplar"] if g not in {x["id"] for x in k["gruplar"]}]
        if yok:
            raise UygulamaHatasi(_("{ad}: tanımsız grup {g}.").format(ad=ad, g=", ".join(yok)))
        out.append((s["id"], k, set(s["gruplar"])))
    return out


def _yeni_rev_notlari(secilen, kayitlar):
    notlar = []
    for __, k, __ in secilen:
        yeni = [r for r in kayitlar.values() if _aile(r) == _aile(k)
                and r["durum"] == YURURLUKTE and r["rev_sira"] > k["rev_sira"]]
        if yeni:
            r = max(yeni, key=lambda r: r["rev_sira"])
            notlar.append(Not("yeni_rev_var", _("{ad}: daha yeni revizyon yürürlükte (Rev. {yeni}); "
                                                "siparişte Rev. {rev} seçili.")
                              .format(ad=k["ad"], yeni=r["rev"], rev=k["rev"])))
    return notlar


def _sartname_metni(k):
    return ", ".join(x for x in (k["ad"].strip(), k["no"].strip()) if x) + f", Rev. {k['rev']}"


def _ayir(kabul):
    """(gövde parçaları, atıf metni): son parça atıf ifadesiyse ayrılır, değilse atıf ""."""
    if kabul and isinstance(kabul[-1], Metin) and _ATIF.match(kabul[-1].metin):
        return list(kabul[:-1]), kabul[-1].metin
    return list(kabul), ""


def _kabul_metni(parcalar):
    return " ".join(p.metin if isinstance(p, Metin) else _("[tablo]")
                    if isinstance(p, KalemTablosu) else f"[{p.etiket}]" for p in parcalar)


def _ekle(std, x):
    if not std.strip():
        return x
    if tr_fold(x) in tr_fold(std):
        return std
    return f"{std}; {x}"


def _sutun(s, a):
    return s.denetim.firma if a == "denetim" else getattr(s, a)


def _devam_mi(hedef, s):
    """C6: hedefin devam satırı (kalite başına devamı ya da kalem / PSL karşılığı)."""
    return (not s.no and s.kontrol == hedef.kontrol
            and (not s.karakteristik or _KALEM_EKI.sub("", s.karakteristik)
                 == _KALEM_EKI.sub("", hedef.karakteristik)))


def _etki(m):
    if m.katman == SIPARIS:
        return "siparis"
    return "metin" if m.madde["tur"] == "metin" else "yerine"


def _dolu(x):
    return isinstance(x, dict) and any(str(x.get(d) or "").strip() for d in ("tr", "en"))


def _atif_topla(parcalar):
    """(tam atıf parçaları, gövdeye gömülü atıflar): "yerine geçer"de silinen parçalardan."""
    tam, gomulu = [], []
    for p in parcalar:
        if isinstance(p, Metin):
            if _ATIF.match(p.metin):
                tam.append(p.metin)
            else:
                gomulu += [x.strip() for x in _GOMULU_ATIF.findall(p.metin)]
    return tam, gomulu


def _yeni_bolumlu(m):
    return m.madde["tur"] == "ek_satir" and bool(m.madde.get("yeni_bolum"))


class _Is:
    """Uygulama sırasında değişen doküman ([no, başlık, [Satir]] listesi) ve notlar."""

    def __init__(self, dokuman, siparis_ozel):
        self.dil, self.sablon, self.siparis_ozel = dokuman.dil, dokuman.sablon, siparis_ozel
        self.bolumler = [[b.no, b.baslik, list(b.satirlar)] for b in dokuman.bolumler]
        self.notlar, self._yeni = [], 0

    def sonuc(self):
        return numaralari_sirala(tuple(Bolum(no, baslik, tuple(s))
                                       for no, baslik, s in self.bolumler),
                                 ayrilmis_bolumler(self.sablon))

    def metin(self, x, m, sutun):
        """Doküman dilindeki metin; boşsa siparişteki çeviri cevabı; o da yoksa CeviriSorusu.
        İki dilde de boşsa ""."""
        t = (x or {}).get(self.dil, "").strip()
        if t:
            return t
        diger = (x or {}).get("en" if self.dil == "tr" else "tr", "").strip()
        if not diger or m.katman == SIPARIS:     # sipariş kararı bu siparişin cevabı: soru yok
            return diger
        for o in self.siparis_ozel:
            if o.get("madde") == [m.sid, m.madde["id"]] and o["sutun"] == sutun:
                t = o["metin"].get(self.dil, "").strip()
                if t:
                    return t
        raise CeviriSorusu(m.madde["kontrol"], sutun, m.sid, m.madde["id"], m.atif, diger,
                           self.ad(m.madde["kontrol"]))

    def ad(self, kontrol):
        return KONTROLLER[kontrol]["en" if self.dil == "en" else "tr"]

    def _bul(self, kontrol):
        for bi, (__, __, satirlar) in enumerate(self.bolumler):
            for si, s in enumerate(satirlar):
                if s.kontrol == kontrol:
                    return bi, si
        return None

    def uygula(self, ms, kontrol):
        ms = sorted(ms, key=lambda m: m.katman)          # kararlı: aynı katmanda seçim sırası
        ad = self.ad(kontrol)
        yer = self._bul(kontrol)
        if yer is None:
            for m in ms:
                self.notlar.append(Not("karsiligi_yok", _(
                    "{atif}: «{ad}» kontrolünün bu dokümanda satırı yok; madde uygulanmadı.")
                    .format(atif=m.atif or _("Sipariş kararı"), ad=ad)))
            return
        bi, si = yer
        uyg = [m for m in ms if m.madde["tur"] == "uygulanmaz"]
        diger = [m for m in ms if m.madde["tur"] != "uygulanmaz"]
        # uygulanmaz da katmana tabi (doğrulama YÜKSEK-1): üst katmanda başka madde varsa ezilir;
        # eşit ya da üstteyse kontrolün tüm satırları (yeni bölüm satırları dahil) uygulanmaz
        uyg_gecerli = bool(uyg) and (max(m.katman for m in uyg)
                                     >= max((m.katman for m in diger), default=0))
        for m in (uyg if not uyg_gecerli else ()):
            self.notlar.append(Not("ezildi", _(
                "{atif}: «{ad}» uygulanmaz maddesi üst öncelikli madde yüzünden uygulanmadı.")
                .format(atif=m.atif, ad=ad)))
        hucre = [m for m in diger if m.madde["tur"] in ("metin", "ek_satir")
                 and not _yeni_bolumlu(m)]
        if hucre:
            self._hucreler(bi, si, kontrol, hucre, ad)
        bolum = [m for m in diger if _yeni_bolumlu(m)]
        if bolum:
            self._yeni_bolum(bi, bolum)
        if uyg_gecerli:
            self._uygulanmaz(kontrol, uyg)
            for m in diger:
                self.notlar.append(Not("ezildi", _(
                    "{atif}: «{ad}» uygulanmaz ({u}); madde Excel'e yansımaz.")
                    .format(atif=m.atif or _("Sipariş kararı"), ad=ad, u=uyg[-1].atif)))

    def _kararlar(self, kontrol, ms, ad):
        """Sütun başına (sütun, kazanan [(m, metin)], ekler [(m, metin)])."""
        kararlar = []
        for sutun in SUTUNLAR:
            yerine, ekler = [], []     # (madde, ham {tr, en}); metin yalnız kullanılırsa istenir
            for m in ms:
                if m.madde["tur"] == "metin":
                    if m.madde["sutun"] == sutun and _dolu(m.madde["metin"]):
                        yerine.append((m, m.madde["metin"]))
                elif sutun in BIRLESEN and _dolu(m.madde["satir"][sutun]):
                    if m.madde.get("etki", "ek") == "yerine":
                        yerine.append((m, m.madde["satir"][sutun]))
                    elif sutun in EKLENEBILIR:
                        ekler.append((m, m.madde["satir"][sutun]))
            if not (yerine or ekler):
                continue
            ust = max((m.katman for m, __ in yerine), default=0)
            kazanan = [(m, self.metin(x, m, sutun)) for m, x in yerine if m.katman == ust]
            if len({tr_fold(x) for __, x in kazanan}) > 1:
                raise CakismaSorusu(kontrol, sutun, [(m.etiket, m.kaynak, x) for m, x in kazanan],
                                    ad)
            for m, __ in [p for p in yerine + ekler if p[0].katman < ust]:
                self.notlar.append(Not("ezildi", _(
                    "{atif}: «{ad}» {sutun} için üst öncelikli değer geçerli; madde uygulanmadı.")
                    .format(atif=m.atif, ad=ad, sutun=_(_SATIR_ADI[sutun]))))
            kararlar.append((sutun, kazanan, [(m, self.metin(x, m, sutun)) for m, x in ekler
                                              if m.katman >= ust]))
        return kararlar

    def _satira(self, s, kararlar, ek_atiflar=()):
        """Kararları satıra uygular. Döner: (satır, gömülü atıf kaybı listesi). "Yerine geçer"
        kabulde silinen tam atıf parçaları ve ek_atiflar (silinen devam satırlarınınki)
        referansa taşınır (doğrulama ORTA-1)."""
        govde, atif = _ayir(s.kabul)
        degerler = {a: _sutun(s, a) for a in SUTUNLAR if a != "kabul"}
        izler, atiflar, korunan, kayip = list(s.izler), [], list(ek_atiflar), []
        for sutun, kazanan, ekler in kararlar:
            std = _kabul_metni(govde) if sutun == "kabul" else degerler[sutun]
            if kazanan:
                if sutun == "kabul":
                    tam, gomulu = _atif_topla(govde)
                    korunan += tam
                    kayip += gomulu
                    govde = [Metin(kazanan[0][1])]
                else:
                    degerler[sutun] = kazanan[0][1]
                for m, __ in kazanan:
                    izler.append(Iz(m.etiket, m.kaynak, sutun, _etki(m), std))
                    atiflar.append(m.atif)
            for m, x in ekler:
                if sutun == "kabul":
                    if tr_fold(x) not in tr_fold(_kabul_metni(govde)):
                        govde.append(Metin(x))
                else:
                    degerler[sutun] = _ekle(degerler[sutun], x)
                izler.append(Iz(m.etiket, m.kaynak, sutun, "ek"))
                atiflar.append(m.atif)
        atiflar = [a for a in dict.fromkeys(korunan + atiflar) if a and a != atif]
        if atiflar:
            atif = "; ".join(([atif] if atif else []) + atiflar)
        return dataclasses.replace(
            s, kabul=tuple(govde) + ((Metin(atif),) if atif else ()),
            karakteristik=degerler["karakteristik"], frekans=degerler["frekans"],
            sorumlu=degerler["sorumlu"], kayit=degerler["kayit"],
            denetim=dataclasses.replace(s.denetim, firma=degerler["denetim"]),
            izler=tuple(izler)), kayip

    def _hucreler(self, bi, si, kontrol, ms, ad):
        kararlar = self._kararlar(kontrol, ms, ad)
        if not kararlar:
            return
        satirlar = self.bolumler[bi][2]
        devam = []
        j = si + 1
        while j < len(satirlar) and _devam_mi(satirlar[si], satirlar[j]):
            devam.append(j)
            j += 1
        if any(sutun == "kabul" and kazanan for sutun, kazanan, __ in kararlar):
            ek_atiflar, kayip = [], []
            for j in reversed(devam):                  # C6: yerine geçen değer tüm kalemler için
                tam, gomulu = _atif_topla(satirlar[j].kabul)
                ek_atiflar[:0], kayip[:0] = tam, gomulu
                del satirlar[j]
            s, k = self._satira(satirlar[si], kararlar, ek_atiflar)
            satirlar[si] = dataclasses.replace(s, karakteristik=_KALEM_EKI.sub("", s.karakteristik))
            kayip = list(dict.fromkeys(k + kayip))
            if kayip:
                ilk = next(m for sutun, kaz, __ in kararlar if sutun == "kabul" for m, __ in kaz)
                self.notlar.append(Not("atif_kaybi", _(
                    "{atif}: «{ad}» standart kabul metnindeki atıflar ({x}) yerine geçen metinle "
                    "kalktı; standart metin önizlemede görünür.")
                    .format(atif=ilk.atif or _("Sipariş kararı"), ad=ad, x="; ".join(kayip))))
            return
        for j in [si] + [j for j in devam if satirlar[j].karakteristik]:
            satirlar[j] = self._satira(satirlar[j], kararlar)[0]

    def _uygulanmaz(self, kontrol, ms):
        gerekce = "; ".join(dict.fromkeys(
            x for x in (self.metin(m.madde["gerekce"], m, "gerekce") for m in ms) if x))
        if not gerekce:
            raise UygulamaHatasi(_("{atif}: uygulanmaz maddesinin gerekçesi boş.")
                                 .format(atif=ms[0].atif))
        iz = tuple(Iz(m.etiket, m.kaynak, "", "uygulanmaz") for m in ms)
        for b in self.bolumler:
            b[2] = [dataclasses.replace(s, uygulanmaz=gerekce, izler=s.izler + iz)
                    if s.kontrol == kontrol else s for s in b[2]]

    def _yeni_bolum(self, bi, ms):
        for m in ms:
            baslik = self.metin(m.madde["yeni_bolum"], m, "yeni_bolum")
            hedef = next((b for b in self.bolumler
                          if b[0].startswith("Y") and tr_fold(b[1]) == tr_fold(baslik)), None)
            if hedef is None:
                self._yeni += 1
                hedef = [f"Y{self._yeni}", baslik, []]
                k = bi + 1
                while k < len(self.bolumler) and self.bolumler[k][0].startswith("Y"):
                    k += 1
                self.bolumler.insert(k, hedef)
            hedef[2].append(self._ek_satir(m, f"{hedef[0]}.{len(hedef[2]) + 1}"))

    def _ek_satir(self, m, no):
        t = {a: self.metin(m.madde["satir"][a], m, a) for a in SATIR_ALANLARI}
        return Satir(no=no, aktivite=t["aktivite"], spec=m.etiket, sorumlu=t["sorumlu"],
                     karakteristik=t["karakteristik"], frekans=t["frekans"], kayit=t["kayit"],
                     denetim=Denetim(t["denetim"]), kabul=(Metin(t["kabul"]), Metin(m.atif)),
                     kontrol=m.madde["kontrol"], izler=(Iz(m.etiket, m.kaynak, "", "yeni_satir"),))


def uygula(dokuman, secim, kayitlar, siparis_ozel=()):
    """dokuman: olustur çıktısı. secim: sipariş kaydının "sartnameler" listesi. kayitlar: şartname
    kayıt id → kayıt (aynı ailenin diğer revizyonları dahil). siparis_ozel: sipariş kaydının
    "siparis_ozel" listesi. Boş seçim ve boş siparis_ozel → dokuman aynen döner."""
    if not secim and not siparis_ozel:
        return dokuman
    dil = dokuman.dil
    secilen = _secim_dogrula(secim, kayitlar)
    n0 = len(dokuman.sartnameler)
    sartnameler, maddeler = list(dokuman.sartnameler), []
    for i, (sid, k, gruplar) in enumerate(secilen, 1):
        sartnameler.append(Sartname(n0 + i, _sartname_metni(k)))
        etiket = f"Spec. {n0 + i}" if dil == "en" else f"Ş.{n0 + i}"
        grup_idleri = [g["id"] for g in k["gruplar"]]
        for m in k["maddeler"]:
            try:                           # kayıt elle bozulmuşsa sessiz atlama yok (DÜŞÜK-2)
                madde_dogrula(m, grup_idleri, tam=True)
            except SartnameHatasi as e:
                raise UygulamaHatasi(f"{k['ad']}: {e}") from None
            if m["grup"] and m["grup"] not in gruplar:
                continue
            if m["tur"] == "sayisal":
                raise UygulamaHatasi(_("{ad} madde {kaynak}: sayısal madde henüz uygulanmıyor "
                                       "(Plan 5c-4); maddeyi ek satır ya da metin olarak girin.")
                                     .format(ad=k["ad"], kaynak=m["kaynak"]))
            maddeler.append(_M(KATMAN[k["tur"]], sid, etiket, m))
    for o in siparis_ozel:
        if o.get("madde") is None:
            maddeler.append(_M(SIPARIS, None, "", {
                "id": "", "kontrol": o["kontrol"], "grup": "", "kaynak": "", "tur": "metin",
                "sutun": o["sutun"], "metin": o["metin"]}))
    is_ = _Is(dokuman, siparis_ozel)
    for kontrol in dict.fromkeys(m.madde["kontrol"] for m in maddeler):
        is_.uygula([m for m in maddeler if m.madde["kontrol"] == kontrol], kontrol)
    return dataclasses.replace(
        dokuman, sartnameler=tuple(sartnameler), bolumler=is_.sonuc(),
        notlar=dokuman.notlar + tuple(_yeni_rev_notlari(secilen, kayitlar)) + tuple(is_.notlar))
