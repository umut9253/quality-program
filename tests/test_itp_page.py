# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""ITP sekmesi (Plan 4 Task 4): offscreen QApplication ile sayfa davranışı."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import openpyxl  # noqa: E402
import pytest  # noqa: E402
from PyQt6.QtWidgets import QApplication, QStackedWidget  # noqa: E402

from app import itp_page as modul  # noqa: E402
from app.firma import Firma  # noqa: E402
from app.itp.dokuman import Dokuman  # noqa: E402
from app.itp_page import (C_D, C_KALITE, C_PSL, C_SINIF, C_KAPLAMA, SABLON_SECENEKLERI,  # noqa: E402
                          ITPPage)

FIRMA = "ÖRNEK FİRMA"   # kurgusal firma adı (2026-11-02)


def firma_ayar():
    return Firma(FIRMA)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def mesajlar():
    return []


@pytest.fixture
def sayfa(app, mesajlar):
    return ITPPage(mesaj=lambda tur, baslik, metin: mesajlar.append((tur, baslik, metin)), firma=firma_ayar)


def test_sayfa_olusur(sayfa):
    assert sayfa.table.rowCount() == 1
    assert not sayfa.btn_excel.isEnabled()
    assert sayfa.cmb_sablon.count() == 3


def test_ornek_siparis_doldurur(sayfa):
    sayfa.ornek_yukle()
    assert sayfa.table.rowCount() == 4
    assert sayfa.alanlar["dokuman_no"].text() == "ITP-ORNEK-001"
    assert sayfa.table.cellWidget(0, C_KALITE).currentText() == "X52M"
    assert sayfa.table.cellWidget(0, C_KAPLAMA).currentText() == "3LPE"
    assert sayfa.table.cellWidget(0, C_SINIF).currentText() == "B"
    assert sayfa.table.item(0, C_D).text() == "323.9"


@pytest.mark.parametrize("indeks", range(len(SABLON_SECENEKLERI)))
def test_olustur_uc_sablon(sayfa, mesajlar, indeks):
    sayfa.ornek_yukle()
    sayfa.cmb_sablon.setCurrentIndex(indeks)
    d = sayfa.olustur()
    assert mesajlar == []
    assert isinstance(d, Dokuman)
    assert d.sablon == SABLON_SECENEKLERI[indeks][1]
    assert sayfa.tree.topLevelItemCount() > 0
    assert sayfa.btn_excel.isEnabled()
    assert "bölüm" in sayfa.lbl_durum.text()


def test_girdi_degisince_dokuman_gecersiz(sayfa):
    sayfa.ornek_yukle()
    assert sayfa.olustur() is not None
    sayfa.alanlar["rev"].setText("1")
    assert sayfa.dokuman is None
    assert not sayfa.btn_excel.isEnabled()


def test_psl_degisince_kalite_listesi_suzulur(sayfa):
    sayfa.table.cellWidget(0, C_PSL).setCurrentText("PSL 1")
    cb = sayfa.table.cellWidget(0, C_KALITE)
    kaliteler = [cb.itemText(i) for i in range(cb.count())]
    assert "B" in kaliteler and "X52M" not in kaliteler


def test_bos_d_hata_mesaji(sayfa, mesajlar):
    sayfa.ornek_yukle()
    sayfa.table.item(1, C_D).setText("")
    assert sayfa.olustur() is None
    assert len(mesajlar) == 1
    tur, _, metin = mesajlar[0]
    assert tur == "hata" and "D boş" in metin
    assert sayfa.dokuman is None and not sayfa.btn_excel.isEnabled()


def test_bos_tablo_hata_mesaji(sayfa, mesajlar):
    sayfa.table.setRowCount(0)
    assert sayfa.olustur() is None
    assert mesajlar and mesajlar[0][0] == "hata"


def test_excel_aktar(sayfa, mesajlar, tmp_path, monkeypatch):
    hedef = tmp_path / "cikti.xlsx"
    istenen = {}

    def sahte_dialog(parent, baslik, varsayilan, filtre):
        istenen["ad"] = varsayilan
        return str(hedef), filtre

    monkeypatch.setattr(modul.QFileDialog, "getSaveFileName", staticmethod(sahte_dialog))
    sayfa.ornek_yukle()
    sayfa.olustur()
    yol = sayfa.excel_aktar()
    assert istenen["ad"] == "ITP-ORNEK-001.xlsx"
    assert hedef.exists() and str(yol) == str(hedef)
    assert openpyxl.load_workbook(hedef)["ITP"].max_row > 5
    assert mesajlar[-1][0] == "bilgi" and str(hedef) in mesajlar[-1][2]


def test_menude_indeks_5(app):
    """MainWindow kurucusu data/kalite.db'yi açar ve yedek alır; test gerçek veriye dokunmasın
    diye yalnızca Sidebar kurulur (MainWindow elle smoke-test edildi)."""
    from app.main_window import Sidebar
    sb = Sidebar(QStackedWidget())
    btn = sb.btn_group.button(5)
    assert btn is not None and btn.toolTip().startswith("ITP / Kalite Planı")


# ── Cila turu: sütun genişliği, önizleme, hata yolları ──────────────
def test_amac_sutunu_metni_tam_gorunur(sayfa):
    sayfa.ornek_yukle()
    cb = sayfa.table.cellWidget(0, modul.C_AMAC)
    en_uzun = max(cb.itemText(i) for i in range(cb.count()))
    assert sayfa.table.columnWidth(modul.C_AMAC) >= cb.fontMetrics().horizontalAdvance(en_uzun)
    assert sayfa.table.columnWidth(modul.C_AMAC) >= cb.sizeHint().width()


def test_onizleme_satir_ogesi_kabul_ozeti(sayfa):
    sayfa.ornek_yukle()
    sayfa.olustur()
    bolum = sayfa.tree.topLevelItem(0)
    dolu = [bolum.child(i) for i in range(bolum.childCount())
            if bolum.child(i).childCount() and bolum.child(i).text(2)]
    assert dolu, "kabul kriteri olan satır öğesinde ilk satır görünmeli"
    assert len(dolu[0].text(2)) <= 80


def test_satir_ekle_dugmesi_duz_arti(sayfa):
    assert sayfa.btn_ekle.text().startswith("+")


def test_ornek_kayipsiz_sayi(sayfa):
    from app.itp.dokuman import Kalem
    k = sayfa.kalemleri_oku  # noqa: F841 (sayfa kurulu)
    sayfa.table.setRowCount(0)
    ornek = Kalem(no=1, psl="PSL 2", grade="X52M", D=323.9, t=12.7, boy_m=12.123456789,
                  miktar_m=1234567890123.0, amac="doğalgaz", dis_kaplama="çıplak")
    sayfa.satir_ekle(ornek)
    assert float(sayfa.table.item(0, modul.C_BOY).text()) == 12.123456789
    assert float(sayfa.table.item(0, modul.C_MIKTAR).text()) == 1234567890123.0


def test_yeni_satir_no_max_arti_bir(sayfa):
    sayfa.ornek_yukle()            # 1..4
    sayfa.table.removeRow(1)       # 1,3,4 kaldı
    sayfa.satir_ekle()
    assert sayfa.table.item(sayfa.table.rowCount() - 1, modul.C_NO).text() == "5"


def test_ornek_listede_olmayan_deger_hata_gosterir(sayfa, mesajlar, monkeypatch):
    from app.itp.dokuman import Kalem
    kotu = Kalem(no=1, psl="PSL 2", grade="X52M", D=1.0, t=1.0, boy_m=1.0, miktar_m=1.0,
                 amac="doğalgaz", dis_kaplama="çıplak")
    object.__setattr__(kotu, "grade", "YOK-KALITE")
    monkeypatch.setattr(modul, "_ornek_siparis",
                        lambda *a: (modul.Baslik(*[""] * 10), [kotu], "itp_en"))
    sayfa.ornek_yukle()
    assert mesajlar and mesajlar[-1][0] == "hata" and "YOK-KALITE" in mesajlar[-1][2]


def test_durum_yeni_sayfaya_aynen_tasinir(app, sayfa):
    # Antigravity BULGU-05 / V-4-3: tema değişiminde yeniden kurulan sayfa girdileri korur
    sayfa.ornek_yukle("kurum_a_kaplama")
    sayfa.satir_ekle()
    sayfa.table.item(1, C_D).setText("abc")          # yarım/hatalı girdi de korunur
    sayfa.alanlar["proje"].setText("Değişti")
    yeni = ITPPage(mesaj=lambda *a: None, firma=firma_ayar)
    yeni.durumu_yukle(sayfa.durum())
    assert yeni.durum() == sayfa.durum()
    assert yeni.cmb_sablon.currentData() == "kp_kaplama"
    assert yeni.table.item(1, C_D).text() == "abc"
    assert yeni.dokuman is None and not yeni.btn_excel.isEnabled()


def test_durum_olusturulmus_dokumani_korur(app, sayfa):
    sayfa.ornek_yukle()
    d = sayfa.olustur()
    yeni = ITPPage(mesaj=lambda *a: None, firma=firma_ayar)
    yeni.durumu_yukle(sayfa.durum())
    assert yeni.dokuman == d and yeni.btn_excel.isEnabled()
    assert yeni.tree.topLevelItemCount() == sayfa.tree.topLevelItemCount()
    assert yeni.kalemleri_oku() == sayfa.kalemleri_oku()


def test_satir_sil_secim_yoksa_silmez_bilgi_verir(sayfa, mesajlar):
    # U-3 (V-4-4): seçili satır yoksa son satır sessizce silinmez
    sayfa.ornek_yukle()
    sayfa.table.clearSelection()
    sayfa.satir_sil()
    assert sayfa.table.rowCount() == 4
    assert mesajlar[-1][0] == "bilgi" and "seçin" in mesajlar[-1][2]


def test_satir_sil_secili_satiri_siler(sayfa):
    sayfa.ornek_yukle()
    sayfa.table.selectRow(1)
    sayfa.satir_sil()
    assert [sayfa.table.item(r, modul.C_NO).text() for r in range(3)] == ["1", "3", "4"]


@pytest.mark.parametrize("ad, sablon, adet", [("kurum_c", "itp_en", 4), ("kurum_a", "kp_ciplak", 1),
                                              ("kurum_a_kaplama", "kp_kaplama", 1)])
def test_ornek_secimi_sablonu_ve_kalemleri_yukler(sayfa, ad, sablon, adet):
    # U-4 (V-4-5): KURUM_C (ITP) veya KURUM_A (KP) örneği seçilebilir
    sayfa.ornek_yukle(ad)
    assert sayfa.cmb_sablon.currentData() == sablon
    assert sayfa.table.rowCount() == adet
    assert sayfa.olustur() is not None


def test_ornek_menusu_uc_secenek(sayfa):
    assert [a.text() for a in sayfa.btn_ornek.menu().actions()] == [
        ad for ad, _ in modul.ORNEK_SECENEKLERI]


def _onek_hatali_olustur(gercek):
    def f(sablon, baslik, kalemler, onek_duzelt=False, *, firma):
        if not onek_duzelt:
            raise modul.NumaraOnekiHatasi(["bölüm 4 satır '1.1'"])
        return gercek(sablon, baslik, kalemler, firma=firma)
    return f


@pytest.mark.parametrize("cevap", [True, False])
def test_onek_hatasi_kullaniciya_sorulur(app, monkeypatch, cevap):
    # U-2 (V-5): önek uyumsuzluğunda uyarı + düzeltme onayı
    sorular = []

    def mesaj(tur, baslik, metin):
        if tur == "soru":
            sorular.append(metin)
            return cevap

    s = ITPPage(mesaj=mesaj, firma=firma_ayar)
    s.ornek_yukle()
    monkeypatch.setattr(modul, "olustur", _onek_hatali_olustur(modul.olustur))
    sonuc = s.olustur()
    assert sorular and "bölüm 4 satır '1.1'" in sorular[0]
    assert (sonuc is not None) is cevap
    assert s.btn_excel.isEnabled() is cevap


@pytest.mark.parametrize("hata", [modul.SablonHatasi, modul.EslesmeHatasi])
def test_olustur_sablon_eslesme_hatasi_mesaj(sayfa, mesajlar, monkeypatch, hata):
    sayfa.ornek_yukle()

    def patla(*a, **k):
        raise hata("deneme hatası")

    monkeypatch.setattr(modul, "olustur", patla)
    assert sayfa.olustur() is None
    assert mesajlar[-1][0] == "hata" and "deneme hatası" in mesajlar[-1][2]
    assert sayfa.dokuman is None and not sayfa.btn_excel.isEnabled()
    assert "deneme hatası" in sayfa.lbl_durum.text()


def test_sayi_olmayan_metin_hata(sayfa, mesajlar):
    sayfa.ornek_yukle()
    sayfa.table.item(0, C_D).setText("abc")
    assert sayfa.olustur() is None
    assert "sayı değil" in mesajlar[-1][2] and "abc" in mesajlar[-1][2]


def test_kaydet_iptal_hicbir_sey_yapmaz(sayfa, mesajlar, monkeypatch):
    cagrildi = []
    monkeypatch.setattr(modul.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: ("", "")))
    monkeypatch.setattr(modul, "excel_yaz", lambda *a, **k: cagrildi.append(1))
    sayfa.ornek_yukle(); sayfa.olustur()
    assert sayfa.excel_aktar() is None
    assert cagrildi == [] and mesajlar == []


def test_excel_yaz_oserror_mesaj(sayfa, mesajlar, monkeypatch):
    monkeypatch.setattr(modul.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: ("x.xlsx", "")))

    def patla(*a, **k):
        raise OSError("disk dolu")

    monkeypatch.setattr(modul, "excel_yaz", patla)
    sayfa.ornek_yukle(); sayfa.olustur()
    assert sayfa.excel_aktar() is None
    assert mesajlar[-1][0] == "hata" and "disk dolu" in mesajlar[-1][2]


@pytest.mark.parametrize("kaplama", ["çıplak", "FBE"])
def test_sinifsiz_kaplamada_sinif_combolari_yok_ve_pasif(sayfa, kaplama):
    sayfa.table.cellWidget(0, C_KAPLAMA).setCurrentText(kaplama)
    for c in (C_SINIF, modul.C_KALINLIK):
        cb = sayfa.table.cellWidget(0, c)
        assert cb.currentText() == modul.YOK and not cb.isEnabled()


def test_ic_kaplama_sutunu(sayfa):
    # V-5-4: iç kaplama görünür; V1'de tek seçenek "çıplak" → kilitli (gerçek seçenekler Plan 7)
    assert modul.SUTUNLAR[modul.C_IC_KAPLAMA] == "İç Kaplama"
    sayfa.ornek_yukle()
    for r in range(sayfa.table.rowCount()):
        cb = sayfa.table.cellWidget(r, modul.C_IC_KAPLAMA)
        assert cb.currentText() == "çıplak"
        assert not cb.isEnabled()
    assert {k.ic_kaplama for k in sayfa.kalemleri_oku()} == {"çıplak"}
    assert sayfa.durum()["satirlar"][0][modul.C_IC_KAPLAMA] == "çıplak"


def test_son_sutun_genis_ekranda_esnemez(sayfa):
    # tam ekranda son sütun (İç Kaplama) kalan boşluğu doldurup aşırı genişlemesin
    sayfa.resize(1900, 900); sayfa.show()
    genislik = sayfa.table.columnWidth(modul.C_IC_KAPLAMA)
    sayfa.close()
    assert genislik < 300


# ── Plan 5a: kayıt düzenleyicisi ─────────────────────────────────────
from app import kimlik as K  # noqa: E402
from app.itp import kayit as R  # noqa: E402


def _kayit(sablon="kp_ciplak"):
    b, kalemler, _ = modul._ornek_siparis("kurum_a")
    return R.kayit_kur(sablon, b, kalemler)


def test_kaydi_yukle_formu_doldurur_ve_olusturur(app, mesajlar):
    s = ITPPage(mesaj=lambda *a: mesajlar.append(a), firma=firma_ayar)
    v = _kayit()
    s.kaydi_yukle(v)
    sablon, baslik, kalemler, onek = s.girdi_verisi()
    assert (sablon, baslik, tuple(kalemler), onek) == R.girdiler(v)
    assert s.dokuman == R.dokuman_uret(v, firma=FIRMA) and not s.degisti and not s.salt_okunur


def test_girdi_degisince_degisti_bayragi(app):
    s = ITPPage(mesaj=lambda *a: None, firma=firma_ayar)
    s.kaydi_yukle(_kayit())
    s.alanlar["proje"].setText("yeni proje")
    assert s.degisti


def test_kilitli_kayit_salt_okunur_ve_goruntuden(app):
    s = ITPPage(mesaj=lambda *a: None, on_kaydet=lambda g: True, firma=firma_ayar)
    o = R.onayla(_kayit(), "05.11.2026", "", "ali", firma=FIRMA)
    s.kaydi_yukle(o)
    assert s.salt_okunur and s.dokuman == R.dokuman_uret(o, firma=FIRMA)
    assert s.alanlar["proje"].isReadOnly() and not s.cmb_sablon.isEnabled()
    assert s.btn_kaydet.isHidden() and s.btn_olustur.isHidden() and s.btn_ekle.isHidden()
    assert "Onaylı" in s.lbl_kayit.text()


def test_kaydet_dugmesi_on_kaydet_cagirir(app):
    gelen = []
    s = ITPPage(mesaj=lambda *a: None, on_kaydet=lambda g: gelen.append(g) or True, firma=firma_ayar)
    s.kaydi_yukle(_kayit())
    s.alanlar["proje"].setText("P2")
    s.btn_kaydet.click()
    assert gelen and gelen[0][1].proje == "P2" and not s.degisti


def test_kaydet_dugmesi_yalniz_kayit_kipinde(app):
    assert ITPPage(mesaj=lambda *a: None, firma=firma_ayar).btn_kaydet.isHidden()


def test_okuyucu_excel_ve_yazma_dugmelerini_gormez(app):
    s = ITPPage(mesaj=lambda *a: None, rol=K.OKUYUCU, on_kaydet=lambda g: True, firma=firma_ayar)
    s.kaydi_yukle(_kayit())
    assert s.btn_excel.isHidden() and s.btn_kaydet.isHidden() and s.salt_okunur
    assert s.dokuman is not None                 # Excel'e aktarılacak sürümü görür
    assert s.excel_aktar() is None               # doğrudan çağrı da engelli


def test_onek_duzeltme_onayi_kayda_gecer(app, monkeypatch):
    gercek = modul.olustur
    monkeypatch.setattr(modul, "olustur", _onek_hatali_olustur(gercek))
    s = ITPPage(mesaj=lambda tur, b, m: True if tur == "soru" else None, firma=firma_ayar)
    s.ornek_yukle("kurum_c")
    s.olustur()
    assert s.onek_duzelt and s.girdi_verisi()[3] is True


def test_taslak_aktarimi_on_aktarim_cagirir_kilitli_cagirmaz(app, tmp_path, monkeypatch):
    aktarilan = []
    monkeypatch.setattr(modul.QFileDialog, "getSaveFileName",
                        lambda *a, **k: (str(tmp_path / "x.xlsx"), ""))
    s = ITPPage(mesaj=lambda *a: None, on_kaydet=lambda g: True,
                on_aktarim=lambda d: aktarilan.append(d), firma=firma_ayar)
    s.kaydi_yukle(_kayit())
    assert s.excel_aktar() and aktarilan == [s.dokuman]
    s.kaydi_yukle(R.onayla(_kayit(), "05.11.2026", "", "a", firma=FIRMA))
    assert s.excel_aktar() and len(aktarilan) == 1


def test_kaydedilmemis_taslak_aktarimdan_once_kaydedilir(app, tmp_path, monkeypatch):
    sira = []
    monkeypatch.setattr(modul.QFileDialog, "getSaveFileName",
                        lambda *a, **k: (str(tmp_path / "x.xlsx"), ""))
    s = ITPPage(mesaj=lambda *a: None, on_kaydet=lambda g: sira.append("kaydet") or True,
                on_aktarim=lambda d: sira.append("aktar"), firma=firma_ayar)
    s.kaydi_yukle(_kayit())
    s.alanlar["proje"].setText("P3")
    assert s.excel_aktar() and sira == ["kaydet", "aktar"]


def test_acilan_kayitta_onek_onayi_kaydedilmeden_aktarilirsa_kayda_gecer(app, tmp_path,
                                                                         monkeypatch):
    """Doğrulama ajanı: onay yalnız bellekte kalıyordu; aktarım önce kaydetmeli."""
    gelen = []
    monkeypatch.setattr(modul, "olustur", _onek_hatali_olustur(modul.olustur))
    monkeypatch.setattr(modul.QFileDialog, "getSaveFileName",
                        lambda *a, **k: (str(tmp_path / "x.xlsx"), ""))
    s = ITPPage(mesaj=lambda tur, b, m: True if tur == "soru" else None,
                on_kaydet=lambda g: gelen.append(g) or True, on_aktarim=lambda d: None, firma=firma_ayar)
    s.kaydi_yukle(_kayit())
    assert s.onek_duzelt and s.degisti
    assert s.excel_aktar() and gelen and gelen[-1][3] is True


def test_firma_ayarlanmamissa_olusturulmaz(app):
    """Spec F4: firma adı yoksa Oluştur açık mesajla durur (sessiz yer tutucu yok)."""
    mesajlar = []
    s = ITPPage(mesaj=lambda *a: mesajlar.append(a))
    s.ornek_yukle()
    assert s.olustur() is None and not s.btn_excel.isEnabled()
    assert any("Firma adı ayarlanmamış" in m[2] for m in mesajlar)



# ── Plan 5c-2: şartname seçimi, sorular, önizleme ──
from app.itp import sartname as _S  # noqa: E402
from app.itp.uygula import CakismaSorusu as _CS  # noqa: E402


def _madde(id_, kontrol, kabul, etki="ek", en=None, tur="ek_satir", **kw):
    if tur == "uygulanmaz":
        return {"id": id_, "kontrol": kontrol, "grup": "", "kaynak": "Md. 9", "tur": tur,
                "gerekce": {"tr": kabul, "en": kabul if en is None else en}}
    satir = {a: {"tr": "", "en": ""} for a in _S.SATIR_ALANLARI}
    satir["karakteristik"] = {"tr": "Kar", "en": "Char"}
    satir["kabul"] = {"tr": kabul, "en": kabul if en is None else en}
    return {"id": id_, "kontrol": kontrol, "grup": "", "kaynak": "Md. 5.2", "tur": tur,
            "satir": satir, "yeni_bolum": None, "etki": etki, **kw}


def _sartname(maddeler, ad="Test Şartnamesi", rev="1", rev_sira=0):
    v = dict(_S.kayit_kur("KURUM", ad, "genel"), rev=rev, rev_sira=rev_sira,
             durum=_S.YURURLUKTE, maddeler=list(maddeler))
    _S.tutarlilik_kontrol(v)
    return v


def _kayitli_sayfa(mesajlar, kayitlar):
    p = ITPPage(mesaj=lambda tur, b, m: mesajlar.append((tur, b, m)) or True, firma=firma_ayar,
                sartname_kayitlari=lambda: kayitlar)
    p.ornek_yukle("kurum_a")
    p.cmb_sablon.setCurrentIndex(p.cmb_sablon.findData("kp_ciplak"))
    return p


def _sec(p, secim, temizle=False):
    p._sartname_sec = lambda satirlar, mevcut: (secim, temizle)
    p.sartname_sec()


def _satirlar(d, kontrol):
    return [s for b in d.bolumler for s in b.satirlar if s.kontrol == kontrol]


def _agac_ogeleri(p):
    out = []
    for i in range(p.tree.topLevelItemCount()):
        t = p.tree.topLevelItem(i)
        out.append(t)
        out += [t.child(j) for j in range(t.childCount())]
    return out


def test_5c2_kayitsiz_kipte_sartname_satiri_gizli(sayfa):
    assert sayfa.btn_sartname.isHidden() and sayfa.lbl_sartname.isHidden()


def test_5c2_secim_olustur_iz_isareti(app, mesajlar):
    p = _kayitli_sayfa(mesajlar, {1: _sartname([_madde("m1", "et_kalinligi", "Eksi −0,04 mm")])})
    assert not p.btn_sartname.isHidden()
    p.degisti = False
    _sec(p, [{"id": 1, "gruplar": []}])
    assert p.degisti and p.secim == [{"id": 1, "gruplar": []}]
    assert "Test Şartnamesi Rev. 1" in p.lbl_sartname.text()
    d = p.olustur()
    assert mesajlar == [] and d.sartnameler[-1].metin == "Test Şartnamesi, Rev. 1"
    oge = next(o for o in _agac_ogeleri(p) if o.text(1) == "Et kalınlığı")
    assert oge.text(0).startswith("+") and "Ş.4 Md. 5.2" in oge.toolTip(1)


def test_5c2_iki_revizyon_secilemez(app, mesajlar):
    k = {1: _sartname([_madde("m1", "et_kalinligi", "x")]),
         2: _sartname([_madde("m1", "et_kalinligi", "y")], rev="2", rev_sira=1)}
    p = _kayitli_sayfa(mesajlar, k)
    cevaplar = [([{"id": 1, "gruplar": []}, {"id": 2, "gruplar": []}], False), None]
    p._sartname_sec = lambda satirlar, mevcut: cevaplar.pop(0)   # hata → pencere yeniden; vazgeç
    p.sartname_sec()
    assert p.secim == [] and mesajlar and mesajlar[-1][0] == "hata"


def test_5c2_cakisma_sorusu_cevabi_siparise_yazilir(app, mesajlar):
    k = {1: _sartname([_madde("m1", "et_kalinligi", "A", etki="yerine")]),
         2: _sartname([_madde("m1", "et_kalinligi", "B", etki="yerine")], ad="İkinci")}
    p = _kayitli_sayfa(mesajlar, k)
    _sec(p, [{"id": 1, "gruplar": []}, {"id": 2, "gruplar": []}])
    sorular = []
    p._cakisma_sor = lambda s: sorular.append(s) or "B"
    d = p.olustur()
    assert len(sorular) == 1 and [x[2] for x in sorular[0].adaylar] == ["A", "B"]
    assert p.siparis_ozel == [{"kontrol": "et_kalinligi", "sutun": "kabul",
                               "metin": {"tr": "B", "en": ""}, "kaynak": "siparis", "madde": None}]
    assert _satirlar(d, "et_kalinligi")[0].kabul[0].metin == "B" and p.degisti


def test_5c2_cakisma_vazgecilirse_dokuman_yok(app, mesajlar):
    k = {1: _sartname([_madde("m1", "et_kalinligi", "A", etki="yerine")]),
         2: _sartname([_madde("m1", "et_kalinligi", "B", etki="yerine")], ad="İkinci")}
    p = _kayitli_sayfa(mesajlar, k)
    _sec(p, [{"id": 1, "gruplar": []}, {"id": 2, "gruplar": []}])
    p._cakisma_sor = lambda s: None
    assert p.olustur() is None and p.dokuman is None
    assert mesajlar[-1][0] == "hata" and p.siparis_ozel == []


def test_5c2_ceviri_sorusu(app, mesajlar):
    p = _kayitli_sayfa(mesajlar, {1: _sartname([_madde("m1", "et_kalinligi", "Yalnız TR", en="")])})
    p.cmb_sablon.setCurrentIndex(p.cmb_sablon.findData("itp_en"))
    _sec(p, [{"id": 1, "gruplar": []}])
    p._ceviri_sor = lambda s: "Only EN"
    d = p.olustur()
    assert d is not None and p.siparis_ozel[0]["madde"] == [1, "m1"]
    assert any(getattr(x, "metin", "") == "Only EN" for x in _satirlar(d, "et_kalinligi")[0].kabul)


def test_5c2_soru_dongusu_sinirli(app, mesajlar, monkeypatch):
    p = _kayitli_sayfa(mesajlar, {1: _sartname([_madde("m1", "et_kalinligi", "x")])})
    _sec(p, [{"id": 1, "gruplar": []}])

    def hep_soru(*a, **k):
        raise _CS("et_kalinligi", "kabul", [("Ş.4", "1", "a"), ("Ş.5", "2", "b")])
    monkeypatch.setattr(modul, "uygula", hep_soru)
    p._cakisma_sor = lambda s: "x"
    assert p.olustur() is None and "50" in mesajlar[-1][2]


def test_5c2_notlar_dugumu_ve_uygulanmaz_gri(app, mesajlar):
    k = {1: _sartname([_madde("m1", "kaplama_darbe", "x"),
                       _madde("m2", "rt_boru_ucu", "Gerekmez", tur="uygulanmaz")])}
    p = _kayitli_sayfa(mesajlar, k)
    _sec(p, [{"id": 1, "gruplar": []}])
    p.olustur()
    ust = p.tree.topLevelItem(0)
    assert ust.text(1) == "Notlar (1)" and ust.childCount() == 1
    oge = next(o for o in _agac_ogeleri(p) if o.text(1) == "Boru ucu kaynağı")
    assert oge.text(0).startswith("⊘") and "Gerekmez" in oge.toolTip(1)
    assert oge.foreground(1).color().name() == "#808080"
    assert "1 not" in p.lbl_durum.text()


def test_5c2_secimden_cikarilan_sartnamenin_cevirisi_silinir(app, mesajlar):
    p = _kayitli_sayfa(mesajlar, {1: _sartname([_madde("m1", "et_kalinligi", "x")])})
    karar = {"kontrol": "et_kalinligi", "sutun": "kabul", "metin": {"tr": "K", "en": ""},
             "kaynak": "siparis", "madde": None}
    ceviri = dict(karar, madde=[1, "m1"])
    _sec(p, [{"id": 1, "gruplar": []}])
    p.siparis_ozel = [karar, ceviri]
    _sec(p, [])
    assert p.siparis_ozel == [karar]
    _sec(p, [], temizle=True)
    assert p.siparis_ozel == []


def test_5c2_durum_secimi_tasir(app, mesajlar):
    k = {1: _sartname([_madde("m1", "et_kalinligi", "x")])}
    p = _kayitli_sayfa(mesajlar, k)
    _sec(p, [{"id": 1, "gruplar": []}])
    d = p.durum()
    q = _kayitli_sayfa(mesajlar, k)
    q.durumu_yukle(d)
    assert q.secim == [{"id": 1, "gruplar": []}] and "Test Şartnamesi" in q.lbl_sartname.text()


def test_5c2_secim_penceresi_sonuc(app):
    from PyQt6.QtCore import Qt
    from app.itp.siparis_secim import secim_satirlari
    from app.itp_page import SartnameSecDialog
    g = [{"id": "g1", "ad": {"tr": "İlk gün", "en": "First day"}}]
    k = {1: dict(_sartname([_madde("m1", "et_kalinligi", "x")]), gruplar=g),
         2: _sartname([_madde("m1", "et_kalinligi", "y")], ad="Diğer")}
    d = SartnameSecDialog(secim_satirlari(k), [{"id": 1, "gruplar": []}, {"id": 9, "gruplar": []}])
    assert d.agac.topLevelItemCount() == 3                    # 2 yürürlükte + bulunamayan 9
    ilk = d.agac.topLevelItem(1)                              # sıra: Diğer, Test, (9)
    assert ilk.data(0, Qt.ItemDataRole.UserRole) == 1
    ilk.child(0).setCheckState(0, Qt.CheckState.Checked)
    d.agac.topLevelItem(2).setCheckState(0, Qt.CheckState.Unchecked)
    assert d.sonuc() == ([{"id": 1, "gruplar": ["g1"]}], False)



# ── 5c-2 doğrulama bulguları ──
def _iki_yerine(mesajlar):
    k = {1: _sartname([_madde("m1", "et_kalinligi", "A", etki="yerine")]),
         2: _sartname([_madde("m1", "et_kalinligi", "B", etki="yerine")], ad="İkinci")}
    p = _kayitli_sayfa(mesajlar, k)
    _sec(p, [{"id": 1, "gruplar": []}, {"id": 2, "gruplar": []}])
    return p


def test_o1_dil_degisince_karar_cevirisi_sorulur_ve_karara_yazilir(app, mesajlar):
    p = _iki_yerine(mesajlar)
    p._cakisma_sor = lambda s: "B TÜRKÇE"
    p.olustur()
    p.cmb_sablon.setCurrentIndex(p.cmb_sablon.findData("itp_en"))
    sorular = []
    p._ceviri_sor = lambda s: sorular.append(s) or "B ENGLISH"
    d = p.olustur()
    assert len(sorular) == 1 and sorular[0].diger == "B TÜRKÇE"
    assert p.siparis_ozel == [{"kontrol": "et_kalinligi", "sutun": "kabul",
                               "metin": {"tr": "B TÜRKÇE", "en": "B ENGLISH"},
                               "kaynak": "siparis", "madde": None}]
    assert _satirlar(d, "et_kalinligi")[0].kabul[0].metin == "B ENGLISH"


def test_d1_tam_sinirda_soru_basarili(app, mesajlar, monkeypatch):
    p = _kayitli_sayfa(mesajlar, {1: _sartname([_madde("m1", "et_kalinligi", "x")])})
    _sec(p, [{"id": 1, "gruplar": []}])
    gercek, sayac = modul.uygula, [0]

    def elli_soru(*a, **k):
        sayac[0] += 1
        if sayac[0] <= modul.SORU_SINIRI:
            raise _CS("et_kalinligi", "kabul", [("Ş.4", "1", "a"), ("Ş.5", "2", "b")])
        return gercek(*a, **k)
    monkeypatch.setattr(modul, "uygula", elli_soru)
    p._cakisma_sor = lambda s: "x"
    assert p.olustur() is not None


def test_d3_secim_penceresi_ingilizce(app):
    import re
    from app import dil
    from app.itp.siparis_secim import secim_satirlari
    from app.itp_page import SartnameSecDialog
    g = [{"id": "g1", "ad": {"tr": "İlk gün", "en": "First day"}}]
    k = {1: dict(_sartname([_madde("m1", "et_kalinligi", "x")], ad="Test Spec"), gruplar=g),
         2: _sartname([_madde("m1", "et_kalinligi", "y")], ad="Test Spec", rev="2", rev_sira=1)}
    dil.ayarla("en")
    try:
        d = SartnameSecDialog(secim_satirlari(k), [{"id": 9, "gruplar": []}])
        metinler = [d.windowTitle(), d.chk_temizle.text()] + [
            d.agac.topLevelItem(i).text(0) for i in range(d.agac.topLevelItemCount())] + [
            d.agac.topLevelItem(0).child(0).text(0)]
    finally:
        dil.ayarla("tr")
    assert not any(re.search(r"[çğıöşüÇĞİÖŞÜ]", m) for m in metinler), metinler
    assert "newer: Rev. 2" in metinler[2] and metinler[-1] == "Group: First day"


def test_d6_yururlukte_olmayan_secili_kayit_adiyla_ve_gruplariyla_kalir(app):
    from PyQt6.QtCore import Qt
    from app.itp_page import SartnameSecDialog
    d = SartnameSecDialog([], [{"id": 7, "gruplar": ["g1"]}], adlar={7: "Eski Şartname Rev. 3"})
    oge = d.agac.topLevelItem(0)
    assert "Eski Şartname Rev. 3" in oge.text(0)
    assert oge.checkState(0) == Qt.CheckState.Checked
    assert d.sonuc() == ([{"id": 7, "gruplar": ["g1"]}], False)


def test_d7_iki_revizyon_hatasinda_pencere_yeniden_acilir(app, mesajlar):
    k = {1: _sartname([_madde("m1", "et_kalinligi", "x")]),
         2: _sartname([_madde("m1", "et_kalinligi", "y")], rev="2", rev_sira=1)}
    p = _kayitli_sayfa(mesajlar, k)
    cevaplar = [([{"id": 1, "gruplar": []}, {"id": 2, "gruplar": []}], False),
                ([{"id": 2, "gruplar": []}], False)]
    gorulen = []
    p._sartname_sec = lambda satirlar, secim: gorulen.append(secim) or cevaplar.pop(0)
    p.sartname_sec()
    assert p.secim == [{"id": 2, "gruplar": []}] and mesajlar[-1][0] == "hata"
    assert gorulen[1] == [{"id": 1, "gruplar": []}, {"id": 2, "gruplar": []}]


def test_d8_degisiklik_yoksa_gecersiz_kilinmaz(app, mesajlar):
    p = _kayitli_sayfa(mesajlar, {1: _sartname([_madde("m1", "et_kalinligi", "x")])})
    _sec(p, [{"id": 1, "gruplar": []}])
    p.olustur()
    p.degisti = False
    _sec(p, [{"id": 1, "gruplar": []}], temizle=True)
    assert not p.degisti and p.dokuman is not None


# ── Plan 5c-3: önizlemede hücre düzeltme ──
def _satir_ogesi(p, karakteristik):
    return next(o for o in _agac_ogeleri(p) if o.text(1) == karakteristik)


def _olusmus_kp(mesajlar):
    p = ITPPage(mesaj=lambda tur, b, m: mesajlar.append((tur, b, m)) or True, firma=firma_ayar)
    p.ornek_yukle("kurum_a")
    p.cmb_sablon.setCurrentIndex(p.cmb_sablon.findData("kp_ciplak"))
    p.olustur()
    return p


def test_5c3_duzelt_kaydedilir_ve_onizlemeye_yansir(app, mesajlar):
    p = _olusmus_kp(mesajlar)
    p.tree.setCurrentItem(_satir_ogesi(p, "Et kalınlığı"))
    assert p.btn_duzelt.isEnabled()
    p.degisti = False
    p._duzelt_sor = lambda satir, mevcut: ("frekans", "Her 5 boruda")
    p.hucre_duzelt()
    assert p.siparis_ozel == [{"kontrol": "et_kalinligi", "sutun": "frekans",
                               "metin": {"tr": "Her 5 boruda", "en": ""}, "kaynak": "siparis",
                               "madde": None, "satir": "Et kalınlığı", "sira": 0}]
    assert p.degisti and _satirlar(p.dokuman, "et_kalinligi")[0].frekans == "Her 5 boruda"
    assert _satir_ogesi(p, "Et kalınlığı").text(0).startswith("⇄")
    p.olustur()                                             # yeniden oluşturmada kaybolmaz (K4)
    assert _satirlar(p.dokuman, "et_kalinligi")[0].frekans == "Her 5 boruda"


def test_5c3_duzeltme_kaldirilir(app, mesajlar):
    p = _olusmus_kp(mesajlar)
    eski = _satirlar(p.dokuman, "et_kalinligi")[0].frekans
    p.tree.setCurrentItem(_satir_ogesi(p, "Et kalınlığı"))
    p._duzelt_sor = lambda satir, mevcut: ("frekans", "X")
    p.hucre_duzelt()
    p.tree.setCurrentItem(_satir_ogesi(p, "Et kalınlığı"))
    gorulen = []
    p._duzelt_sor = lambda satir, mevcut: gorulen.append(mevcut) or ("frekans", None)
    p.hucre_duzelt()
    assert "frekans" in gorulen[0] and p.siparis_ozel == []
    assert _satirlar(p.dokuman, "et_kalinligi")[0].frekans == eski


def test_5c3_secim_yokken_bilgi(app, mesajlar):
    p = _olusmus_kp(mesajlar)
    p.tree.setCurrentItem(p.tree.topLevelItem(0))           # bölüm düğümü, satır değil
    assert not p.btn_duzelt.isEnabled()
    p.hucre_duzelt()
    assert mesajlar and mesajlar[-1][0] == "bilgi"


def test_5c3_okuyucu_duzeltemez(app):
    s = ITPPage(mesaj=lambda *a: None, rol=K.OKUYUCU, firma=firma_ayar)
    assert s.btn_duzelt.isHidden()
    s._duzelt_sor = lambda satir, mevcut: ("frekans", "X")
    s.hucre_duzelt()
    assert s.siparis_ozel == []


def test_5c3_pencere_mevcut_metin_ve_kaldir(app, mesajlar):
    from app.itp_page import HucreDuzeltDialog
    p = _olusmus_kp(mesajlar)
    satir = _satirlar(p.dokuman, "et_kalinligi")[0]
    d = HucreDuzeltDialog(satir, {"frekans": "Elle"})
    d.cmb_sutun.setCurrentIndex(d.cmb_sutun.findData("kabul"))
    assert "[tablo]" in d.ed_metin.toPlainText() and not d.btn_kaldir.isEnabled()
    d.cmb_sutun.setCurrentIndex(d.cmb_sutun.findData("frekans"))
    assert d.ed_metin.toPlainText() == "Elle" and d.btn_kaldir.isEnabled()
    d.ed_metin.setPlainText("Yeni")
    d._tamam()
    assert d.sonuc == ("frekans", "Yeni")



# ── 5c-3 doğrulama bulguları ──
def test_5c3_y1_karakteristik_duzeltilemez():
    from app.itp_page import DUZELTME_SUTUNLARI
    assert "karakteristik" not in DUZELTME_SUTUNLARI      # hedef anahtarı kaymasın (V-5c3-7)


def test_5c3_o3_degistirmeden_tamam_duzeltme_yazmaz_yer_tutucu_engellenir(app, mesajlar):
    from app.itp_page import HucreDuzeltDialog
    p = _olusmus_kp(mesajlar)
    satir = _satirlar(p.dokuman, "et_kalinligi")[0]
    d = HucreDuzeltDialog(satir, {})
    d._tamam()                                              # metin değişmedi
    assert d.sonuc is None and d.result() == 0
    d.ed_metin.setPlainText(d.ed_metin.toPlainText() + " ek")   # [tablo] hâlâ metinde
    d._tamam()
    assert d.sonuc is None and "[tablo]" in d.lbl_uyari.text()
    d.ed_metin.setPlainText("")
    d._tamam()
    assert d.sonuc is None and d.lbl_uyari.text()


def test_5c3_d3_uygulanmaz_satirda_duzelt_kapali_d5_alt_ogede_acik(app, mesajlar):
    import dataclasses
    p = _olusmus_kp(mesajlar)
    oge = _satir_ogesi(p, "Et kalınlığı")
    p.tree.setCurrentItem(oge.child(0))                     # kabul parçası alt öğesi
    assert p.btn_duzelt.isEnabled()
    d = p.dokuman
    p.dokuman = dataclasses.replace(d, bolumler=tuple(
        dataclasses.replace(b, satirlar=tuple(dataclasses.replace(s, uygulanmaz="g")
                                              if s.kontrol == "et_kalinligi" else s
                                              for s in b.satirlar)) for b in d.bolumler))
    p.tree.setCurrentItem(oge)
    p._duzelt_durumu()
    assert not p.btn_duzelt.isEnabled()


# ── Antigravity 5c-2 raporu (2026-11-09) ──
def _taslak_veri(secim, siparis_ozel=()):
    from app.itp import kayit as R
    baslik, kalemler, __ = modul._ornek_siparis("kurum_a")
    return R.kayit_kur("kp_ciplak", baslik, kalemler, sartnameler=secim,
                       siparis_ozel=list(siparis_ozel))


def _iki_cakisma_kayitlari():
    return {1: _sartname([_madde("m1", "et_kalinligi", "A", etki="yerine"),
                          _madde("m2", "hidrostatik", "H1", etki="yerine")]),
            2: _sartname([_madde("m1", "et_kalinligi", "B", etki="yerine"),
                          _madde("m2", "hidrostatik", "H2", etki="yerine")], ad="İkinci")}


def test_ag1_okuyucuya_soru_sorulmaz(app, mesajlar):
    k = _iki_cakisma_kayitlari()
    p = ITPPage(mesaj=lambda tur, b, m: mesajlar.append((tur, b, m)) or True, rol=K.OKUYUCU,
                firma=firma_ayar, sartname_kayitlari=lambda: k)
    soruldu = []
    p._cakisma_sor = lambda s: soruldu.append(s) or "X"
    p.kaydi_yukle(_taslak_veri([{"id": 1, "gruplar": []}, {"id": 2, "gruplar": []}]))
    assert soruldu == [] and p.siparis_ozel == [] and p.dokuman is None
    assert mesajlar and mesajlar[-1][0] == "hata"


def test_ag2_ayni_hucreye_ikinci_karar_yazilmaz(app, mesajlar):
    k = {1: _sartname([_madde("m1", "et_kalinligi", "A", etki="yerine")])}
    p = _kayitli_sayfa(mesajlar, k)
    _sec(p, [{"id": 1, "gruplar": []}])
    karar = {"kontrol": "et_kalinligi", "sutun": "kabul", "kaynak": "siparis", "madde": None}
    p.siparis_ozel = [dict(karar, metin={"tr": "K1", "en": ""}),
                      dict(karar, metin={"tr": "K2", "en": ""})]
    p._cakisma_sor = lambda s: "K3"
    d = p.olustur()
    assert d is not None and p.siparis_ozel == [dict(karar, metin={"tr": "K3", "en": ""})]


def test_ag3_ceviri_cevabi_mevcut_kayda_yazilir(app, mesajlar):
    k = {1: _sartname([_madde("m1", "et_kalinligi", "TR", en="")])}
    p = _kayitli_sayfa(mesajlar, k)
    _sec(p, [{"id": 1, "gruplar": []}])
    p.cmb_sablon.setCurrentIndex(p.cmb_sablon.findData("itp_en"))
    p.siparis_ozel = [{"kontrol": "et_kalinligi", "sutun": "kabul", "metin": {"tr": "eski", "en": ""},
                       "kaynak": "siparis", "madde": [1, "m1"]}]
    p._ceviri_sor = lambda s: "EN"
    p.olustur()
    assert p.siparis_ozel == [{"kontrol": "et_kalinligi", "sutun": "kabul",
                               "metin": {"tr": "eski", "en": "EN"}, "kaynak": "siparis",
                               "madde": [1, "m1"]}]


def test_ag4_ikinci_soruda_vazgecince_hicbir_sey_degismez(app, mesajlar):
    p = _kayitli_sayfa(mesajlar, _iki_cakisma_kayitlari())
    _sec(p, [{"id": 1, "gruplar": []}, {"id": 2, "gruplar": []}])
    p.degisti = False
    cevaplar = ["B", None]
    p._cakisma_sor = lambda s: cevaplar.pop(0)
    assert p.olustur() is None
    assert p.siparis_ozel == [] and not p.degisti and p.dokuman is None


# ── Antigravity 5c-3 raporu (2026-11-09) ──
def _uygulanmaz_yap(p, kontrol):
    import dataclasses
    d = p.dokuman
    p.dokuman = dataclasses.replace(d, bolumler=tuple(
        dataclasses.replace(b, satirlar=tuple(dataclasses.replace(s, uygulanmaz="g")
                                              if s.kontrol == kontrol else s
                                              for s in b.satirlar)) for b in d.bolumler))


def test_ag5c3_b01_uygulanmaz_satirda_sag_tik_ve_duzelt_calismaz(app, mesajlar, monkeypatch):
    from PyQt6.QtCore import QPoint
    p = _olusmus_kp(mesajlar)
    oge = _satir_ogesi(p, "Et kalınlığı")
    _uygulanmaz_yap(p, "et_kalinligi")
    p.tree.setCurrentItem(oge)
    p._duzelt_durumu()

    class Yasak:
        def __init__(self, *a):
            raise AssertionError("uygulanmaz satırda menü açılmamalı")
    monkeypatch.setattr(modul, "QMenu", Yasak)
    p._agac_menusu(QPoint(0, 0))
    p._duzelt_sor = lambda satir, mevcut: ("frekans", "X")
    p.hucre_duzelt()
    assert p.siparis_ozel == [] and mesajlar[-1][0] == "bilgi"


def test_ag5c3_b04_olusturma_basarisizsa_duzeltme_geri_alinir(app, mesajlar):
    p = _olusmus_kp(mesajlar)
    p.tree.setCurrentItem(_satir_ogesi(p, "Et kalınlığı"))
    p.degisti = False
    p._duzelt_sor = lambda satir, mevcut: ("frekans", "X")
    p.olustur = lambda: None                                # oluşturma başarısız / vazgeçildi
    p.hucre_duzelt()
    assert p.siparis_ozel == [] and not p.degisti


def test_ag5c3_d3_geri_alma_derin_kopyadan(app, mesajlar):
    p = _olusmus_kp(mesajlar)
    eski = {"kontrol": "x", "sutun": "kabul", "metin": {"tr": "Eski", "en": ""},
            "kaynak": "siparis", "madde": [1, "m1"]}
    p.siparis_ozel = [eski]
    p.tree.setCurrentItem(_satir_ogesi(p, "Et kalınlığı"))
    p.degisti = False
    p._duzelt_sor = lambda satir, mevcut: ("frekans", "X")

    def basarisiz():                       # soru cevabı yerinde yazıldı, sonra vazgeçildi
        p.siparis_ozel[0]["metin"]["tr"] = "Yarım cevap"
        return None
    p.olustur = basarisiz
    p.hucre_duzelt()
    assert p.siparis_ozel == [{"kontrol": "x", "sutun": "kabul", "metin": {"tr": "Eski", "en": ""},
                               "kaynak": "siparis", "madde": [1, "m1"]}] and not p.degisti
