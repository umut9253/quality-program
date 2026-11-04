# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Şartname düzenleyici (Plan 5b-2a): üst bilgiler + madde tablosu; madde ve grup pencereleri.

Kurallar app/itp/sartname.py'de (Qt'siz); burada yalnız girdi ve gösterim vardır. Madde metinleri
veridir ({tr, en}): tablo etkin dilde gösterir (EN boşsa TR), pencerede ikisi de düzenlenir.
Kilitli kayıt salt okunur; Yönetici «Gerekçeyle düzelt» ile düzenlemeyi açar, Kaydet gerekçe
ister (B6). Pencereler (madde, grup, girdi, klasör seçimi) testler için enjekte edilebilir.
"""
import copy

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QComboBox, QDialog, QFileDialog, QFormLayout, QGridLayout,
                             QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
                             QPushButton, QStackedWidget, QTableWidget, QTableWidgetItem,
                             QVBoxLayout, QWidget)

from . import dil, kimlik, theme
from .itp import sartname as S
from .itp.kontrol import KONTROLLER, sablonlari
from .itp_page import SABLON_SECENEKLERI, _varsayilan_mesaj
from .widgets import page_header
from .dil import N_, _

ALANLAR = (("kurum", N_("Kurum")), ("ad", N_("Şartname adı")), ("no", N_("No")),
           ("rev", N_("Rev")), ("yayim_tarihi", N_("Yayım tarihi")),
           ("kaynak_klasor", N_("Kaynak klasör")), ("not", N_("Not")))
TURLER = (("genel", N_("Genel")), ("ozel", N_("Özel teknik")))
TUR_ADLARI = {"sayisal": N_("Sayısal"), "metin": N_("Metin"), "ek_satir": N_("Ek satır"),
              "uygulanmaz": N_("Uygulanmaz")}
SUTUN_ADLARI = {"karakteristik": N_("Karakteristik"), "kabul": N_("Kabul kriteri"),
                "frekans": N_("Frekans"), "kayit": N_("Kayıt"), "denetim": N_("Denetim")}
SATIR_ADLARI = dict(SUTUN_ADLARI, aktivite=N_("Aktivite"), sorumlu=N_("Sorumlu"))
# sayısal kriterler: BoruSonucu alanları (app/itp/hesap.py)
KRITER_ADLARI = {
    "p_test": N_("Hidrostatik test basıncı"), "cap_govde": N_("Gövde dış çapı"),
    "cap_uc": N_("Boru ucu dış çapı"), "et": N_("Et kalınlığı (t)"),
    "ovallik_govde": N_("Gövde ovalitesi"), "ovallik_uc": N_("Boru ucu ovalitesi"),
    "dogrusallik_toplam": N_("Toplam doğrusallık sapması"),
    "dogrusallik_uc": N_("Boru ucu doğrusallık sapması"), "kutle": N_("Kütle toleransı"),
    "radyal_ofset": N_("Radyal kaçıklık"), "bead_ic": N_("İç dikiş yüksekliği"),
    "bead_dis": N_("Dış dikiş yüksekliği"), "bead_uc_ic": N_("Boru ucu iç dikiş yüksekliği"),
    "bead_uc_dis": N_("Boru ucu dış dikiş yüksekliği"), "lot": N_("Lot büyüklüğü"),
    "rt_rm_maks": N_("En büyük akma / çekme oranı"), "mandrel": N_("Bükme mandrel çapı"),
    "charpy": N_("Çentik darbe enerjisi")}
SABLON_ADLARI = {kod: ad for ad, kod in SABLON_SECENEKLERI}
TABLO_SUTUNLARI = (N_("Tür"), N_("Kontrol"), N_("Sütun / Kriter"), N_("Değer / Metin"),
                   N_("Grup"), N_("Kaynak"))


def metin_goster(x):
    """{tr, en} → etkin dilde (EN boşsa TR)."""
    if not isinstance(x, dict):
        return ""
    return (x.get("en") or x.get("tr", "")) if dil.etkin() == "en" else x.get("tr", "")


def kontrol_adi(anahtar):
    k = KONTROLLER.get(anahtar)
    return anahtar if k is None else k["en"] if dil.etkin() == "en" else k["tr"]


def _sayi_metni(x):
    """Gösterim = kayıt: 15 anlamlı basamak (format "g" 6 basamağa yuvarlıyordu)."""
    return "" if x is None else format(x, ".15g")


def _grup_adi(grup, gruplar):
    if not grup:
        return _("Zorunlu")
    for g in gruplar:
        if g["id"] == grup:
            return metin_goster(g["ad"]) or grup
    return grup


def madde_ozeti(m, gruplar):
    """Tablo satırı: tür, kontrol, sütun / kriter, değer / metin, grup, kaynak."""
    tur = m.get("tur")
    if tur == "sayisal":
        sk = _(KRITER_ADLARI.get(m["kriter"], m["kriter"]))
        alt, ust = _sayi_metni(m.get("alt")), _sayi_metni(m.get("ust"))
        deger = (f"{alt} – {ust}" if alt and ust else f"≥ {alt}" if alt
                 else f"≤ {ust}" if ust else "")
        deger = f"{deger} {m['birim']}".strip()
    elif tur == "metin":
        sk, deger = _(SUTUN_ADLARI.get(m["sutun"], m["sutun"])), metin_goster(m["metin"])
    elif tur == "ek_satir":
        sk, deger = (metin_goster(m["satir"].get("karakteristik")),
                     metin_goster(m["satir"].get("kabul")))
    else:
        sk, deger = "", metin_goster(m.get("gerekce"))
    return (_(TUR_ADLARI.get(tur, str(tur))), kontrol_adi(m["kontrol"]), sk, deger,
            _grup_adi(m["grup"], gruplar), m["kaynak"])


def madde_ipucu(m, deger):
    """Değer hücresinin ipucu: tam metin; ek satırda dolu tüm alanlar (tabloda kesilir)."""
    if m.get("tur") != "ek_satir":
        return deger
    return "\n".join(f"{_(SATIR_ADLARI[a])}: {metin_goster(m['satir'].get(a))}"
                     for a in S.SATIR_ALANLARI if metin_goster(m["satir"].get(a)))


def _hata_etiketi():
    lbl = QLabel()
    lbl.setWordWrap(True)
    lbl.setStyleSheet(f"color: {theme.t('danger_text')};")
    return lbl


def _tamam_vazgec(dialog):
    sat = QHBoxLayout(); sat.addStretch()
    tamam = QPushButton(_("Tamam")); tamam.setObjectName("btn_primary")
    vazgec = QPushButton(_("Vazgeç")); vazgec.setObjectName("btn_ghost")
    tamam.clicked.connect(dialog._tamam); vazgec.clicked.connect(dialog.reject)
    sat.addWidget(vazgec); sat.addWidget(tamam)
    return sat


def _panel():
    """Madde penceresinin türe göre alan paneli: pencere zemininde (tema QWidget zemini değil)."""
    w = QWidget(); w.setObjectName("madde_paneli")
    return w


def _tr_en(tr, en):
    return {"tr": tr.text().strip(), "en": en.text().strip()}


# ── madde penceresi ──────────────────────────────────────────────────
class MaddeDialog(QDialog):
    """Önce tür, sonra kontrol (bulunduğu şablonlarla), türe göre alanlar. Geçersiz madde
    pencerede hata olarak gösterilir, pencere kapanmaz."""

    def __init__(self, madde=None, gruplar=(), parent=None, yeni_id="m1"):
        super().__init__(parent)
        self.setWindowTitle(_("Madde düzenle") if madde else _("Madde ekle"))
        self.setMinimumWidth(640)
        self._id = madde["id"] if madde else yeni_id
        self._grup_idleri = [g["id"] for g in gruplar]
        self.sonuc = None
        L = QVBoxLayout(self)
        form = QFormLayout()
        self.cmb_tur = QComboBox()
        for t in S.MADDE_TURLERI:
            self.cmb_tur.addItem(_(TUR_ADLARI[t]), t)
        self.cmb_kontrol = QComboBox()
        for k in KONTROLLER:
            self.cmb_kontrol.addItem(kontrol_adi(k), k)
        self.lbl_sablon = QLabel(); self.lbl_sablon.setWordWrap(True)
        self.cmb_grup = QComboBox()
        self.cmb_grup.addItem(_("Zorunlu"), "")
        for g in gruplar:
            self.cmb_grup.addItem(metin_goster(g["ad"]) or g["id"], g["id"])
        self.ed_kaynak = QLineEdit()
        self.ed_kaynak.setPlaceholderText(_("Şartname madde no (örn. 7.2.4)"))
        form.addRow(_("Madde türü"), self.cmb_tur)
        form.addRow(_("Kontrol"), self.cmb_kontrol)
        form.addRow("", self.lbl_sablon)
        form.addRow(_("Grup"), self.cmb_grup)
        form.addRow(_("Kaynak"), self.ed_kaynak)
        L.addLayout(form)
        self.paneller = QStackedWidget(); self.paneller.setObjectName("madde_paneli")
        for kur in (self._sayisal_paneli, self._metin_paneli, self._ek_satir_paneli,
                    self._uygulanmaz_paneli):
            self.paneller.addWidget(kur())
        L.addWidget(self.paneller)
        self.lbl_hata = _hata_etiketi()
        L.addWidget(self.lbl_hata)
        L.addLayout(_tamam_vazgec(self))
        self.cmb_tur.currentIndexChanged.connect(self._tur_degisti)
        self.cmb_kontrol.currentIndexChanged.connect(self._kontrol_degisti)
        self._kontrol_degisti()
        if madde:
            self._doldur(madde)
        self._tur_degisti()

    # ── paneller ──
    def _sayisal_paneli(self):
        w = _panel(); f = QFormLayout(w); f.setContentsMargins(0, 0, 0, 0)
        self.cmb_kriter = QComboBox()
        self.lbl_kriter_yok = QLabel(_("Bu kontrolün sayısal kriteri yok; sayısal madde girilemez."))
        self.lbl_kriter_yok.setWordWrap(True)
        self.ed_alt, self.ed_ust, self.ed_birim = QLineEdit(), QLineEdit(), QLineEdit()
        self.ed_alt.setPlaceholderText(_("boş = sınırsız"))
        self.ed_ust.setPlaceholderText(_("boş = sınırsız"))
        self.ed_birim.setPlaceholderText(_("mm, bar, % …"))
        self.ed_cap_min, self.ed_cap_max = QLineEdit(), QLineEdit()
        self.ed_et_min, self.ed_et_max = QLineEdit(), QLineEdit()
        f.addRow(_("Kriter"), self.cmb_kriter)
        f.addRow("", self.lbl_kriter_yok)
        f.addRow(_("Alt sınır"), self.ed_alt)
        f.addRow(_("Üst sınır"), self.ed_ust)
        f.addRow(_("Birim"), self.ed_birim)
        for etiket, en_az, en_cok in ((_("Çap aralığı (mm, isteğe bağlı)"), self.ed_cap_min,
                                       self.ed_cap_max),
                                      (_("Et aralığı (mm, isteğe bağlı)"), self.ed_et_min,
                                       self.ed_et_max)):
            en_az.setPlaceholderText(_("en az")); en_cok.setPlaceholderText(_("en çok"))
            sat = QHBoxLayout(); sat.addWidget(en_az); sat.addWidget(en_cok)
            f.addRow(etiket, sat)
        return w

    def _metin_paneli(self):
        w = _panel(); f = QFormLayout(w); f.setContentsMargins(0, 0, 0, 0)
        self.cmb_sutun = QComboBox()
        for s in S.SUTUNLAR:
            self.cmb_sutun.addItem(_(SUTUN_ADLARI[s]), s)
        self.ed_metin_tr, self.ed_metin_en = QLineEdit(), QLineEdit()
        f.addRow(_("Değişen sütun"), self.cmb_sutun)
        f.addRow(_("Metin (TR)"), self.ed_metin_tr)
        f.addRow(_("Metin (EN)"), self.ed_metin_en)
        return w

    def _ek_satir_paneli(self):
        w = _panel(); g = QGridLayout(w); g.setContentsMargins(0, 0, 0, 0)
        g.addWidget(QLabel(_("TR")), 0, 1); g.addWidget(QLabel(_("EN")), 0, 2)
        self.ek = {}
        for r, (a, etiket) in enumerate([(a, SATIR_ADLARI[a]) for a in S.SATIR_ALANLARI]
                                        + [("yeni_bolum", N_("Yeni bölüm (isteğe bağlı)"))],
                                        start=1):
            g.addWidget(QLabel(_(etiket)), r, 0)
            self.ek[a] = (QLineEdit(), QLineEdit())
            g.addWidget(self.ek[a][0], r, 1); g.addWidget(self.ek[a][1], r, 2)
        return w

    def _uygulanmaz_paneli(self):
        w = _panel(); f = QFormLayout(w); f.setContentsMargins(0, 0, 0, 0)
        self.ed_gerekce_tr, self.ed_gerekce_en = QLineEdit(), QLineEdit()
        f.addRow(_("Gerekçe (TR)"), self.ed_gerekce_tr)
        f.addRow(_("Gerekçe (EN)"), self.ed_gerekce_en)
        return w

    # ── davranış ──
    def _tur_degisti(self, *__):
        self.paneller.setCurrentIndex(S.MADDE_TURLERI.index(self.cmb_tur.currentData()))

    def _kontrol_degisti(self, *__):
        k = self.cmb_kontrol.currentData()
        secili = self.cmb_kriter.currentData()
        self.cmb_kriter.clear()
        if k not in KONTROLLER:   # kayıttaki anahtar listeden kalkmışsa çökmesin
            self.cmb_kriter.setEnabled(False)
            self.lbl_kriter_yok.setVisible(True)
            self.lbl_sablon.setText(_("Kayıttaki kontrol listede yok; listeden bir kontrol seçin."))
            return
        for kr in KONTROLLER[k]["kriterler"]:
            self.cmb_kriter.addItem(_(KRITER_ADLARI.get(kr, kr)), kr)
        if (i := self.cmb_kriter.findData(secili)) >= 0:
            self.cmb_kriter.setCurrentIndex(i)
        self.cmb_kriter.setEnabled(self.cmb_kriter.count() > 0)
        self.lbl_kriter_yok.setVisible(self.cmb_kriter.count() == 0)
        s = sablonlari(k)
        self.lbl_sablon.setText(
            _("Bulunduğu şablonlar: {d}").format(d=", ".join(_(SABLON_ADLARI[x]) for x in s)) if s
            else _("Bu kontrolün henüz şablonu yok; madde kaydedilir, şablon gelince uygulanır."))

    def _doldur(self, m):
        self.cmb_tur.setCurrentIndex(self.cmb_tur.findData(m["tur"]))
        self.cmb_kontrol.setCurrentIndex(self.cmb_kontrol.findData(m["kontrol"]))
        self.cmb_grup.setCurrentIndex(max(0, self.cmb_grup.findData(m["grup"])))
        self.ed_kaynak.setText(m["kaynak"])
        if m["tur"] == "sayisal":
            self.cmb_kriter.setCurrentIndex(self.cmb_kriter.findData(m["kriter"]))
            self.ed_alt.setText(_sayi_metni(m.get("alt")))
            self.ed_ust.setText(_sayi_metni(m.get("ust")))
            self.ed_birim.setText(m.get("birim", ""))
            for ad, en_az, en_cok in (("cap_aralik", self.ed_cap_min, self.ed_cap_max),
                                      ("et_aralik", self.ed_et_min, self.ed_et_max)):
                if m.get(ad):
                    en_az.setText(_sayi_metni(m[ad][0])); en_cok.setText(_sayi_metni(m[ad][1]))
        elif m["tur"] == "metin":
            self.cmb_sutun.setCurrentIndex(self.cmb_sutun.findData(m["sutun"]))
            self.ed_metin_tr.setText(m["metin"]["tr"]); self.ed_metin_en.setText(m["metin"]["en"])
        elif m["tur"] == "ek_satir":
            for a in S.SATIR_ALANLARI:
                self.ek[a][0].setText(m["satir"][a]["tr"]); self.ek[a][1].setText(m["satir"][a]["en"])
            if m.get("yeni_bolum"):
                self.ek["yeni_bolum"][0].setText(m["yeni_bolum"]["tr"])
                self.ek["yeni_bolum"][1].setText(m["yeni_bolum"]["en"])
        else:
            self.ed_gerekce_tr.setText(m["gerekce"]["tr"]); self.ed_gerekce_en.setText(m["gerekce"]["en"])

    @staticmethod
    def _sayi(ed, ad):
        t = ed.text().strip().replace(",", ".")
        if not t:
            return None
        try:
            return float(t)
        except ValueError:
            raise S.SartnameHatasi(_("{ad} sayı değil: '{t}'").format(ad=ad, t=t)) from None

    def _aralik(self, en_az, en_cok, ad):
        a, b = self._sayi(en_az, ad), self._sayi(en_cok, ad)
        if a is None and b is None:
            return None
        if a is None or b is None:
            raise S.SartnameHatasi(_("{ad}: en az ve en çok birlikte girilmeli.").format(ad=ad))
        return [a, b]

    def madde(self):
        """Penceredeki madde (tam doğrulanmış); geçersizse SartnameHatasi."""
        tur = self.cmb_tur.currentData()
        m = {"id": self._id, "kontrol": self.cmb_kontrol.currentData(),
             "grup": self.cmb_grup.currentData(), "kaynak": self.ed_kaynak.text().strip(),
             "tur": tur}
        if tur == "sayisal":
            m.update(kriter=self.cmb_kriter.currentData(),
                     alt=self._sayi(self.ed_alt, _("Alt sınır")),
                     ust=self._sayi(self.ed_ust, _("Üst sınır")),
                     birim=self.ed_birim.text().strip(),
                     cap_aralik=self._aralik(self.ed_cap_min, self.ed_cap_max, _("Çap aralığı")),
                     et_aralik=self._aralik(self.ed_et_min, self.ed_et_max, _("Et aralığı")))
        elif tur == "metin":
            m.update(sutun=self.cmb_sutun.currentData(),
                     metin=_tr_en(self.ed_metin_tr, self.ed_metin_en))
        elif tur == "ek_satir":
            yb = _tr_en(*self.ek["yeni_bolum"])
            m.update(satir={a: _tr_en(*self.ek[a]) for a in S.SATIR_ALANLARI},
                     yeni_bolum=yb if yb["tr"] or yb["en"] else None)
        else:
            m.update(gerekce=_tr_en(self.ed_gerekce_tr, self.ed_gerekce_en))
        S.madde_dogrula(m, self._grup_idleri, tam=True)
        return m

    def _tamam(self):
        try:
            self.sonuc = self.madde()
        except S.SartnameHatasi as e:
            self.lbl_hata.setText(str(e))
            return
        self.accept()


# ── grup penceresi ───────────────────────────────────────────────────
class GrupDialog(QDialog):
    """İsteğe bağlı madde grupları (B2): ekle, adlandır (TR/EN), sil. Maddede kullanılan grup
    silinmez."""

    def __init__(self, gruplar, maddeler, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Gruplar"))
        self.setMinimumWidth(520)
        self._kullanilan = {m.get("grup") for m in maddeler if m.get("grup")}
        self._idler = {g["id"] for g in gruplar}
        self.sonuc = None
        L = QVBoxLayout(self)
        L.addWidget(QLabel(_("İsteğe bağlı maddeler gruplanır; siparişte grup başına tek soru "
                             "sorulur. Zorunlu maddeler gruba girmez.")))
        self.tablo = QTableWidget(0, 2)
        self.tablo.setHorizontalHeaderLabels([_("Grup adı (TR)"), _("Grup adı (EN)")])
        self.tablo.verticalHeader().setVisible(False)
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tablo.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        L.addWidget(self.tablo)
        sat = QHBoxLayout()
        b_ekle = QPushButton(_("+  Grup ekle")); b_ekle.setObjectName("btn_ghost")
        b_sil = QPushButton(_("Grubu sil")); b_sil.setObjectName("btn_ghost")
        b_ekle.clicked.connect(lambda: self.ekle())
        b_sil.clicked.connect(lambda: self.sil())
        sat.addWidget(b_ekle); sat.addWidget(b_sil); sat.addStretch()
        L.addLayout(sat)
        self.lbl_hata = _hata_etiketi()
        L.addWidget(self.lbl_hata)
        L.addLayout(_tamam_vazgec(self))
        for g in gruplar:
            self._satir(g["id"], g["ad"]["tr"], g["ad"]["en"])

    def _satir(self, gid, tr, en):
        r = self.tablo.rowCount()
        self.tablo.insertRow(r)
        it = QTableWidgetItem(tr); it.setData(Qt.ItemDataRole.UserRole, gid)
        self.tablo.setItem(r, 0, it)
        self.tablo.setItem(r, 1, QTableWidgetItem(en))

    def ekle(self, tr="", en=""):
        n = 1
        while f"g{n}" in self._idler:
            n += 1
        self._idler.add(f"g{n}")
        self._satir(f"g{n}", tr, en)
        self.tablo.setCurrentCell(self.tablo.rowCount() - 1, 0)

    def sil(self, r=None):
        r = self.tablo.currentRow() if r is None else r
        if r < 0:
            self.lbl_hata.setText(_("Önce tablodan bir grup seçin."))
            return False
        if self.tablo.item(r, 0).data(Qt.ItemDataRole.UserRole) in self._kullanilan:
            self.lbl_hata.setText(_("Bu grup maddelerde kullanılıyor; önce o maddelerin grubunu "
                                    "değiştirin."))
            return False
        self.tablo.removeRow(r)
        self.lbl_hata.setText("")
        return True

    def gruplar(self):
        out = []
        for r in range(self.tablo.rowCount()):
            tr, en = self.tablo.item(r, 0).text().strip(), self.tablo.item(r, 1).text().strip()
            if not tr:
                raise S.SartnameHatasi(_("Satır {d}: grup adı (TR) boş olamaz.").format(d=r + 1))
            out.append({"id": self.tablo.item(r, 0).data(Qt.ItemDataRole.UserRole),
                        "ad": {"tr": tr, "en": en}})
        return out

    def _tamam(self):
        try:
            self.sonuc = self.gruplar()
        except S.SartnameHatasi as e:
            self.lbl_hata.setText(str(e))
            return
        self.accept()


# ── düzenleyici ──────────────────────────────────────────────────────
class SartnamePage(QWidget):
    def __init__(self, mesaj=None, rol=None, on_kaydet=None, on_listeye_don=None,
                 on_duzelt=None, girdi=None):
        super().__init__()
        self._mesaj = mesaj or (lambda tur, b, m: _varsayilan_mesaj(self, tur, b, m))
        self.girdi = girdi or self._qt_girdi
        self.rol = rol                    # None = kullanıcısız (araç/test): tam yetki
        self.on_kaydet, self.on_listeye_don, self.on_duzelt = on_kaydet, on_listeye_don, on_duzelt
        self.madde_penceresi = self._qt_madde
        self.grup_penceresi = self._qt_gruplar
        self.klasor_sec = lambda: QFileDialog.getExistingDirectory(self, _("Kaynak klasör"))
        self.degisti = False
        self.salt_okunur = False
        self._duzeltme = False            # kilitli kayıt, Yönetici gerekçeyle düzeltiyor (B6)
        self._yukleniyor = False
        self._taban = S.kayit_kur("", "")
        self._gruplar, self._maddeler = [], []
        self._build()
        self.kaydi_yukle(None)

    # ── varsayılan pencereler ──
    def _qt_girdi(self, baslik, etiket, varsayilan=""):
        metin, ok = QInputDialog.getText(self, baslik, etiket, text=varsayilan)
        return metin if ok else None

    def _qt_madde(self, madde, gruplar, yeni_id):
        d = MaddeDialog(madde, gruplar, self, yeni_id=yeni_id or "m1")
        return d.sonuc if d.exec() == QDialog.DialogCode.Accepted else None

    def _qt_gruplar(self, gruplar, maddeler):
        d = GrupDialog(gruplar, maddeler, self)
        return d.sonuc if d.exec() == QDialog.DialogCode.Accepted else None

    def _yazabilir(self):
        return self.rol is None or kimlik.yetkili(self.rol, kimlik.DUZENLEYICI)

    # ── arayüz ──
    def _build(self):
        L = QVBoxLayout(self); L.setContentsMargins(24, 20, 24, 16); L.setSpacing(10)
        L.addWidget(page_header(_("Şartnameler"),
                                _("Müşteri şartnamesinin maddeleri: sayısal sınırlar, metin "
                                  "değişiklikleri, ek satırlar, uygulanmayan kontroller")))
        ust = QHBoxLayout()
        self.btn_liste = QPushButton(_("←  Listeye dön")); self.btn_liste.setObjectName("btn_ghost")
        self.btn_liste.clicked.connect(lambda: self.on_listeye_don and self.on_listeye_don())
        self.lbl_kayit = QLabel("")
        self.btn_duzelt = QPushButton(_("Gerekçeyle düzelt")); self.btn_duzelt.setObjectName("btn_ghost")
        self.btn_duzelt.setToolTip(_("Kilitli revizyondaki yanlışı düzeltir; gerekçe güvenlik "
                                     "kaydına geçer"))
        self.btn_duzelt.clicked.connect(self.duzelt_ac)
        self.btn_kaydet = QPushButton(_("Kaydet")); self.btn_kaydet.setObjectName("btn_primary")
        self.btn_kaydet.clicked.connect(self.kaydet)
        ust.addWidget(self.btn_liste); ust.addWidget(self.lbl_kayit); ust.addStretch()
        ust.addWidget(self.btn_duzelt); ust.addWidget(self.btn_kaydet)
        L.addLayout(ust)

        grid = QGridLayout(); grid.setHorizontalSpacing(10); grid.setVerticalSpacing(6)
        self.alanlar = {}
        for ad, etiket in ALANLAR:
            ed = QLineEdit(); ed.setPlaceholderText(_(etiket))
            ed.textChanged.connect(self._degisti)
            self.alanlar[ad] = ed
        self.cmb_tur = QComboBox()
        for kod, ad in TURLER:
            self.cmb_tur.addItem(_(ad), kod)
        self.cmb_tur.currentIndexChanged.connect(self._degisti)
        self.btn_gozat = QPushButton(_("Gözat…")); self.btn_gozat.setObjectName("btn_ghost")
        self.btn_gozat.clicked.connect(self._klasor_gozat)
        klasor = QHBoxLayout(); klasor.addWidget(self.alanlar["kaynak_klasor"], 1)
        klasor.addWidget(self.btn_gozat)
        # (etiket, alan, satır, sütun, genişlik)
        for etiket, w, r, c, gen in (
                (N_("Kurum"), self.alanlar["kurum"], 0, 0, 1),
                (N_("Şartname adı"), self.alanlar["ad"], 0, 1, 2),
                (N_("Tür"), self.cmb_tur, 0, 3, 1),
                (N_("No"), self.alanlar["no"], 0, 4, 1),
                (N_("Rev"), self.alanlar["rev"], 0, 5, 1),
                (N_("Yayım tarihi"), self.alanlar["yayim_tarihi"], 2, 0, 1),
                (N_("Kaynak klasör"), klasor, 2, 1, 2),
                (N_("Not"), self.alanlar["not"], 2, 3, 3)):
            grid.addWidget(QLabel(_(etiket)), r, c, 1, gen)
            if isinstance(w, QHBoxLayout):
                grid.addLayout(w, r + 1, c, 1, gen)
            else:
                grid.addWidget(w, r + 1, c, 1, gen)
        L.addLayout(grid)

        tb = QHBoxLayout()
        tb.addWidget(QLabel(_("Maddeler")))
        tb.addStretch()
        self.btn_madde_ekle = QPushButton(_("+  Madde ekle")); self.btn_madde_ekle.setObjectName("btn_primary")
        self.btn_madde_duzenle = QPushButton(_("Düzenle"))
        self.btn_madde_sil = QPushButton(_("Sil"))
        self.btn_yukari = QPushButton(_("▲  Yukarı"))
        self.btn_asagi = QPushButton(_("▼  Aşağı"))
        self.btn_gruplar = QPushButton(_("Gruplar…"))
        self.btn_madde_ekle.clicked.connect(self.madde_ekle)
        self.btn_madde_duzenle.clicked.connect(lambda: self.madde_duzenle())
        self.btn_madde_sil.clicked.connect(lambda: self.madde_sil())
        self.btn_yukari.clicked.connect(lambda: self.tasi(-1))
        self.btn_asagi.clicked.connect(lambda: self.tasi(1))
        self.btn_gruplar.clicked.connect(self.gruplari_duzenle)
        self._madde_dugmeleri = (self.btn_madde_ekle, self.btn_madde_duzenle, self.btn_madde_sil,
                                 self.btn_yukari, self.btn_asagi, self.btn_gruplar)
        for b in self._madde_dugmeleri:
            if b is not self.btn_madde_ekle:
                b.setObjectName("btn_ghost")
            tb.addWidget(b)
        L.addLayout(tb)

        self.tablo = QTableWidget(0, len(TABLO_SUTUNLARI))
        self.tablo.setHorizontalHeaderLabels([_(x) for x in TABLO_SUTUNLARI])
        self.tablo.verticalHeader().setVisible(False)
        self.tablo.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tablo.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tablo.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        h = self.tablo.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tablo.cellDoubleClicked.connect(
            lambda r, _c: self.madde_duzenle(r) if not self.salt_okunur else None)
        L.addWidget(self.tablo, 1)

    def _dugmeleri_ayarla(self):
        kilitli = S.kilitli(self._taban)
        yaz = self._yazabilir() and (not kilitli or self._duzeltme)
        self.salt_okunur = not yaz
        self.btn_liste.setVisible(self.on_listeye_don is not None)
        self.btn_kaydet.setVisible(yaz)
        self.btn_duzelt.setVisible(kilitli and not self._duzeltme
                                   and self.rol in (None, kimlik.YONETICI))
        for b in self._madde_dugmeleri:
            b.setVisible(yaz)
        self.btn_gozat.setVisible(yaz)
        for ad, ed in self.alanlar.items():   # düzeltmede kimlik alanları değişmez (yeni rev)
            ed.setReadOnly(not yaz or (kilitli and ad in ("kurum", "ad", "rev")))
        self.cmb_tur.setEnabled(yaz and not kilitli)

    def _degisti(self, *__):
        if not self._yukleniyor:
            self.degisti = True

    def _tabloyu_doldur(self, sec=None):
        self.tablo.setRowCount(0)
        for m in self._maddeler:
            r = self.tablo.rowCount()
            self.tablo.insertRow(r)
            ozet = madde_ozeti(m, self._gruplar)
            for c, metin in enumerate(ozet):
                self.tablo.setItem(r, c, QTableWidgetItem(str(metin)))
            self.tablo.item(r, 3).setToolTip(madde_ipucu(m, ozet[3]))
        if sec is not None and 0 <= sec < self.tablo.rowCount():
            self.tablo.selectRow(sec)

    # ── kayıt ──
    def _alanlari_doldur(self, alanlar, tur, gruplar, maddeler):
        for ad, ed in self.alanlar.items():
            ed.setText(alanlar[ad])
        self.cmb_tur.setCurrentIndex(self.cmb_tur.findData(tur))
        self._gruplar, self._maddeler = copy.deepcopy(gruplar), copy.deepcopy(maddeler)
        self._tabloyu_doldur()

    def kaydi_yukle(self, veri):
        """veri None: yeni boş şartname."""
        self._yukleniyor = True
        try:
            self._taban = copy.deepcopy(veri) if veri is not None else S.kayit_kur("", "")
            self._duzeltme = False
            v = self._taban
            self._alanlari_doldur(v, v["tur"], v["gruplar"], v["maddeler"])
        finally:
            self._yukleniyor = False
        self.lbl_kayit.setText(_("Yeni şartname") if veri is None else "{d}  ·  {d2}".format(
            d=S.kayit_adi(veri), d2=S.durum_metni(veri)))
        self._dugmeleri_ayarla()
        self.degisti = False

    def veri_oku(self):
        """Kayda gidecek hal: üst bilgiler + gruplar + maddeler; durum ve rev_sira korunur."""
        v = copy.deepcopy(self._taban)
        v.update({ad: ed.text().strip() for ad, ed in self.alanlar.items()})
        v.update(tur=self.cmb_tur.currentData(), gruplar=copy.deepcopy(self._gruplar),
                 maddeler=copy.deepcopy(self._maddeler))
        return v

    def duzelt_ac(self):
        if not (S.kilitli(self._taban) and self.rol in (None, kimlik.YONETICI)):
            return
        self._duzeltme = True
        self._dugmeleri_ayarla()

    def kaydet(self):
        if self.salt_okunur or self.on_kaydet is None:
            return False
        veri = self.veri_oku()
        if self._duzeltme:
            gerekce = self.girdi(_("Gerekçeyle düzelt"),
                                 _("Düzeltme gerekçesi (güvenlik kaydına geçer):"), "")
            if gerekce is None:
                return False
            ok = self.on_duzelt(veri, gerekce)
        else:
            ok = self.on_kaydet(veri)
        if ok:
            self.degisti = False
        return ok

    def _klasor_gozat(self):
        yol = self.klasor_sec()
        if yol:
            self.alanlar["kaynak_klasor"].setText(yol)

    # ── maddeler ──
    def _secili(self):
        r = self.tablo.currentRow()
        if r < 0 or r >= len(self._maddeler):
            self._mesaj("bilgi", _("Seçim yok"), _("Önce tablodan bir madde seçin."))
            return None
        return r

    def _yeni_id(self):
        idler, n = {m["id"] for m in self._maddeler}, 1
        while f"m{n}" in idler:
            n += 1
        return f"m{n}"

    def _maddeler_degisti(self, sec):
        self._tabloyu_doldur(sec)
        self.degisti = True

    def madde_ekle(self):
        m = self.madde_penceresi(None, self._gruplar, self._yeni_id())
        if m is not None:
            self._maddeler.append(m)
            self._maddeler_degisti(len(self._maddeler) - 1)

    def madde_duzenle(self, r=None):
        r = self._secili() if r is None else r
        if r is None:
            return
        m = self.madde_penceresi(copy.deepcopy(self._maddeler[r]), self._gruplar, None)
        if m is not None:
            self._maddeler[r] = m
            self._maddeler_degisti(r)

    def madde_sil(self, r=None):
        r = self._secili() if r is None else r
        if r is None or not self._mesaj("soru", _("Madde sil"),
                                        _("Seçili madde silinsin mi?")):
            return
        del self._maddeler[r]
        self._maddeler_degisti(min(r, len(self._maddeler) - 1))

    def tasi(self, yon):
        r = self._secili()
        if r is None:
            return
        j = r + yon
        if not 0 <= j < len(self._maddeler):
            return
        self._maddeler[r], self._maddeler[j] = self._maddeler[j], self._maddeler[r]
        self._maddeler_degisti(j)

    def gruplari_duzenle(self):
        g = self.grup_penceresi(copy.deepcopy(self._gruplar), self._maddeler)
        if g is not None:
            self._gruplar = g
            self._maddeler_degisti(self.tablo.currentRow())

    # ── tema / dil geçişinde durum taşıma ──
    def durum(self):
        return {"alanlar": {ad: ed.text() for ad, ed in self.alanlar.items()},
                "tur": self.cmb_tur.currentData(), "gruplar": copy.deepcopy(self._gruplar),
                "maddeler": copy.deepcopy(self._maddeler), "duzeltme": self._duzeltme}

    def durumu_yukle(self, d):
        """kaydi_yukle'den sonra çağrılır (taban = açık kayıt)."""
        self._yukleniyor = True
        try:
            self._alanlari_doldur(d["alanlar"], d["tur"], d["gruplar"], d["maddeler"])
        finally:
            self._yukleniyor = False
        self._duzeltme = d["duzeltme"] and S.kilitli(self._taban)
        self._dugmeleri_ayarla()
