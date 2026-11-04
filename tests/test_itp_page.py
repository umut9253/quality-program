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

