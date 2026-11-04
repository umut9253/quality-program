# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""app/kimlik.py: kullanıcılar, şifre özeti, kademeli kilit, oturumlar, güvenlik kaydı."""
import sqlite3

import pytest

from app import kimlik as K

SIFRE = "Guclu-Sifre-1"
T0 = 1_000_000.0   # sahte saat (sn)


@pytest.fixture
def c():
    c = sqlite3.connect(":memory:")
    K.sema_kur(c)
    K.kullanici_ekle(c, "admin", SIFRE, K.YONETICI, ad_soyad="Yönetici", yapan=None)
    K.kullanici_ekle(c, "ali", SIFRE, K.DUZENLEYICI, yapan="admin")
    K.kullanici_ekle(c, "ayse", SIFRE, K.OKUYUCU, yapan="admin")
    return c


def giris(c, ad, sifre, simdi=T0, ip="10.0.0.5"):
    return K.giris(c, ad, sifre, ip=ip, simdi=simdi)


def test_sifre_ozeti_duz_metin_saklanmaz(c):
    satir = c.execute("SELECT sifre_ozet FROM kullanicilar WHERE ad='ali'").fetchone()[0]
    assert SIFRE not in satir and satir.startswith("scrypt$")


def test_dogru_giris_ve_rol(c):
    k = giris(c, "ali", SIFRE)
    assert (k.ad, k.rol) == ("ali", K.DUZENLEYICI)


def test_kullanici_adi_buyuk_kucuk_harf_ve_bosluk(c):
    assert giris(c, "  ALİ ", SIFRE).ad == "ali"


def test_bilinmeyen_kullanici_ile_yanlis_sifre_ayni_mesaj(c):
    with pytest.raises(K.GirisHatasi) as a:
        giris(c, "yok", SIFRE)
    with pytest.raises(K.GirisHatasi) as b:
        giris(c, "ali", "yanlis-sifre")
    assert str(a.value) == str(b.value)


@pytest.mark.parametrize("sifre", ["kisa1", "", "        "])
def test_zayif_sifre_reddedilir(c, sifre):
    with pytest.raises(K.KimlikHatasi, match="en az"):
        K.kullanici_ekle(c, "veli", sifre, K.OKUYUCU, yapan="admin")


def test_ayni_ad_iki_kez_eklenemez(c):
    with pytest.raises(K.KimlikHatasi, match="zaten"):
        K.kullanici_ekle(c, "ALI", SIFRE, K.OKUYUCU, yapan="admin")


def hatali(c, n, simdi, ad="ali", ip="10.0.0.5"):
    for _ in range(n):
        with pytest.raises(K.GirisHatasi):
            giris(c, ad, "yanlis", simdi=simdi, ip=ip)


def test_ilk_uc_hata_kilitlemez_dorduncu_1_dk(c):
    hatali(c, 3, T0)
    assert giris(c, "ali", SIFRE, simdi=T0).ad == "ali"      # 3 hata serbest; başarı sıfırlar
    hatali(c, 4, T0)                                          # 4. hata → 1 dk kilit
    with pytest.raises(K.GirisHatasi, match="kilit") as e:
        giris(c, "ali", SIFRE, simdi=T0 + 30)                 # doğru şifre de reddedilir
    assert 0 < e.value.kalan_sn <= 60
    assert giris(c, "ali", SIFRE, simdi=T0 + 61).ad == "ali"


def test_kademeler_1_5_15_60_sonra_kalici(c):
    t = T0
    hatali(c, 4, t)                                           # 1 dk
    for sure in (60, 300, 900, 3600):
        t += sure + 1
        hatali(c, 1, t)                                       # kilit bitince her hata bir kademe
    with pytest.raises(K.GirisHatasi, match="yönetici") as e:
        giris(c, "ali", SIFRE, simdi=t + 10 * 3600)           # kalıcı: zaman geçse de açılmaz
    assert e.value.kalan_sn is None
    K.kilit_ac(c, "ali", yapan="admin")
    assert giris(c, "ali", SIFRE, simdi=t + 10).ad == "ali"


def test_kilitliyken_denemeler_kademeyi_artirmaz(c):
    hatali(c, 4, T0)
    hatali(c, 10, T0 + 5)                                     # kilit süresince
    with pytest.raises(K.GirisHatasi) as e:
        giris(c, "ali", SIFRE, simdi=T0 + 30)
    assert e.value.kalan_sn <= 60                             # hâlâ 1. kademe


def test_ip_kilidi_farkli_kullanici_adlariyla_atlatilamaz(c):
    for i in range(4):                                        # 4 farklı (olmayan) ad, aynı cihaz
        with pytest.raises(K.GirisHatasi):
            giris(c, f"deneme{i}", "x", ip="10.0.0.9")
    with pytest.raises(K.GirisHatasi, match="kilit"):
        giris(c, "ayse", SIFRE, ip="10.0.0.9", simdi=T0 + 10)   # bu cihaz kilitli
    assert giris(c, "ayse", SIFRE, ip="10.0.0.7", simdi=T0 + 10).ad == "ayse"


IP = "10.0.0.9"


def kilitli_cihaz(c, simdi):
    """Doğru şifreyle bile bu cihazdan giriş reddediliyor mu (cihaz kilidi)?"""
    try:
        giris(c, "ayse", SIFRE, ip=IP, simdi=simdi)
        return False
    except K.GirisHatasi as e:
        return "cihaz" in str(e)


def test_v7_15_kendi_girisi_baskalarina_yapilan_denemeleri_silmez(c):
    """BULGU-03 senaryosu: başka hesaplara deneme + kendi hesabıyla giriş cihaz sayacını
    sıfırlamamalı (yalnız kendi hataları düşer)."""
    hatali(c, 2, T0, ad="admin", ip=IP)
    hatali(c, 1, T0, ad="ali", ip=IP)
    assert giris(c, "ayse", SIFRE, ip=IP, simdi=T0 + 1).ad == "ayse"
    hatali(c, 1, T0 + 2, ad="yok", ip=IP)                  # cihazda 4. hata
    assert kilitli_cihaz(c, T0 + 3)


def test_v7_15_basarili_giris_kendi_hatalarini_dusurur(c):
    hatali(c, 2, T0, ad="ayse", ip=IP)                     # kendi şifresini yanlış yazdı
    hatali(c, 1, T0, ad="yok", ip=IP)
    assert giris(c, "ayse", SIFRE, ip=IP, simdi=T0 + 1).ad == "ayse"   # sayaç 3 → 1
    hatali(c, 2, T0 + 2, ad="yok2", ip=IP)                 # 3: hâlâ serbest
    assert not kilitli_cihaz(c, T0 + 3)
    hatali(c, 1, T0 + 4, ad="yok3", ip=IP)                 # 4: kilit
    assert kilitli_cihaz(c, T0 + 5)


def test_v7_15_cihaz_sayaci_son_hatadan_60_dk_sonra_sifirlanir(c):
    hatali(c, 3, T0, ad="yok", ip=IP)
    hatali(c, 1, T0 + 3601, ad="yok", ip=IP)               # süre doldu: sayaç 1'den başlar
    hatali(c, 2, T0 + 3602, ad="yok", ip=IP)               # 3: serbest
    assert not kilitli_cihaz(c, T0 + 3603)


def test_v7_15_60_dk_dolmadan_sayac_surer(c):
    hatali(c, 3, T0, ad="yok", ip=IP)
    hatali(c, 1, T0 + 3599, ad="yok", ip=IP)               # 4. hata
    assert kilitli_cihaz(c, T0 + 3600)


def test_v7_15_kilit_ac_cihaz_sayacini_temizler(c):
    hatali(c, 4, T0, ad="ali", ip=IP)                      # cihaz + ali kilitli
    K.kilit_ac(c, "ali", yapan="admin")
    assert not kilitli_cihaz(c, T0 + 1)
    hatali(c, 3, T0 + 2, ad="yok", ip=IP)                  # sayaç sıfırdan: 3 serbest
    assert not kilitli_cihaz(c, T0 + 3)


def test_guvenlik_kaydi(c):
    hatali(c, 1, T0)
    giris(c, "ali", SIFRE, simdi=T0 + 1)
    olaylar = [(o["olay"], o["kullanici"], o["ip"]) for o in K.guvenlik_kayitlari(c)]
    assert ("giris_basarisiz", "ali", "10.0.0.5") in olaylar
    assert ("giris", "ali", "10.0.0.5") in olaylar


def test_pasif_kullanici_giremez(c):
    K.pasif_yap(c, "ayse", yapan="admin")
    with pytest.raises(K.GirisHatasi):
        giris(c, "ayse", SIFRE)


def test_son_yonetici_korunur(c):
    with pytest.raises(K.KimlikHatasi, match="son yönetici"):
        K.rol_degistir(c, "admin", K.OKUYUCU, yapan="admin")
    with pytest.raises(K.KimlikHatasi, match="son yönetici"):
        K.pasif_yap(c, "admin", yapan="admin")
    K.rol_degistir(c, "ali", K.YONETICI, yapan="admin")
    K.rol_degistir(c, "admin", K.OKUYUCU, yapan="ali")        # artık başka yönetici var


def test_sifre_degistir_eskiyi_ister(c):
    with pytest.raises(K.GirisHatasi):
        K.sifre_degistir(c, "ali", "yanlis", "Yeni-Sifre-2")
    K.sifre_degistir(c, "ali", SIFRE, "Yeni-Sifre-2")
    assert giris(c, "ali", "Yeni-Sifre-2").ad == "ali"


def test_yonetici_sifre_sifirlar_ve_oturumlar_kapanir(c):
    k = giris(c, "ali", SIFRE)
    token = K.oturum_ac(c, k, cihaz="tablet", simdi=T0)
    K.sifre_sifirla(c, "ali", "Sifirlanan-3", yapan="admin")
    assert K.oturum_dogrula(c, token, simdi=T0 + 1) is None
    assert giris(c, "ali", "Sifirlanan-3").ad == "ali"


def test_oturum_suresi_ve_kapatma(c):
    k = giris(c, "ayse", SIFRE)
    token = K.oturum_ac(c, k, cihaz="tablet", simdi=T0)
    assert K.oturum_dogrula(c, token, simdi=T0 + 60).ad == "ayse"
    assert K.oturum_dogrula(c, token, simdi=T0 + K.OTURUM_SURESI + 1) is None
    t2 = K.oturum_ac(c, k, cihaz="tablet", simdi=T0)
    K.oturum_kapat(c, t2)
    assert K.oturum_dogrula(c, t2, simdi=T0 + 1) is None
    assert K.oturum_dogrula(c, "uydurma", simdi=T0) is None


def test_token_duz_saklanmaz(c):
    token = K.oturum_ac(c, giris(c, "ali", SIFRE), cihaz="tablet", simdi=T0)
    assert token not in str(c.execute("SELECT * FROM oturumlar").fetchall())


def test_yetki_kontrolu():
    assert K.yetkili(K.YONETICI, K.DUZENLEYICI) and K.yetkili(K.DUZENLEYICI, K.DUZENLEYICI)
    assert not K.yetkili(K.OKUYUCU, K.DUZENLEYICI)
    assert not K.yetkili(K.DUZENLEYICI, K.YONETICI)


def test_ilk_kurulum_gerekli_mi():
    c = sqlite3.connect(":memory:")
    K.sema_kur(c)
    assert K.kurulum_gerekli(c)
    K.kullanici_ekle(c, "admin", SIFRE, K.YONETICI, yapan=None)
    assert not K.kurulum_gerekli(c)


def test_masaustu_girisinde_cihaz_kilidi_yok_kullanici_kilidi_var(c):
    # Masaüstünde herkes "yerel": bir kullanıcının hataları bilgisayarı herkese kilitlemesin
    hatali(c, 4, T0, ad="ali", ip="yerel")
    assert giris(c, "admin", SIFRE, simdi=T0 + 1, ip="yerel").ad == "admin"
    with pytest.raises(K.GirisHatasi, match="kilit"):
        giris(c, "ali", SIFRE, simdi=T0 + 1, ip="yerel")      # ali'nin kendi kilidi sürer


def test_paralel_hatali_denemeler_kilidi_atlatamaz(tmp_path):
    """Denetim YÜKSEK-1: sayaç işlem dışında okunup eski değerle yazılıyordu; paralel
    denemelerin hepsi şifre denemesine ulaşıyor, sayaç ilerlemiyordu."""
    import threading
    yol = str(tmp_path / "k.db")
    c0 = sqlite3.connect(yol)
    K.sema_kur(c0)
    K.kullanici_ekle(c0, "ali", SIFRE, K.DUZENLEYICI, yapan=None)
    c0.commit()
    engel = threading.Barrier(12)
    sonuc = []

    def dene():
        c = sqlite3.connect(yol, timeout=30)
        engel.wait()
        try:
            K.giris(c, "ali", "yanlis", ip="10.0.0.9", simdi=T0)
        except K.GirisHatasi as e:
            sonuc.append(e.kalan_sn)
        c.close()

    ts = [threading.Thread(target=dene) for _ in range(12)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    hatali, bitis, kalici = c0.execute(
        "SELECT hatali, kilit_bitis, kalici_kilit FROM kullanicilar WHERE ad = 'ali'").fetchone()
    assert hatali == 4 and bitis == T0 + 60 and kalici == 0   # kilitliyken gelenler sayılmaz
    assert sum(1 for k in sonuc if k == 0) == 3                # yalnız 3 deneme serbest


def _kademeleri_bitir(c, ad, t=T0):
    """4 hata + her kilit bitiminde 1 hata: 8. hata kalıcı kilit kademesi."""
    hatali(c, 4, t, ad=ad)
    for sure in (60, 300, 900, 3600):
        t += sure + 1
        hatali(c, 1, t, ad=ad)
    return t


def test_son_yonetici_kalici_kilitlenmez_60_dk_tavan(c):
    """Kullanıcı kararı (V-7-14): tek yönetici kalıcı kilitlenirse kilidi açacak kimse kalmaz."""
    t = _kademeleri_bitir(c, "admin")
    with pytest.raises(K.GirisHatasi) as e:
        giris(c, "admin", SIFRE, simdi=t + 10)
    assert e.value.kalan_sn is not None and 0 < e.value.kalan_sn <= 3600
    t += 3601
    hatali(c, 1, t, ad="admin")                               # sonraki hatalar da 60 dk
    assert c.execute("SELECT kalici_kilit FROM kullanicilar WHERE ad='admin'").fetchone()[0] == 0
    assert giris(c, "admin", SIFRE, simdi=t + 3601).ad == "admin"


def test_baska_yonetici_varken_yonetici_kalici_kilitlenir(c):
    K.kullanici_ekle(c, "veli", SIFRE, K.YONETICI, yapan="admin")
    t = _kademeleri_bitir(c, "admin")
    with pytest.raises(K.GirisHatasi) as e:
        giris(c, "admin", SIFRE, simdi=t + 10 * 3600)
    assert e.value.kalan_sn is None


def test_diger_yonetici_kalici_kilitliyse_son_yonetici_sayilir(c):
    K.kullanici_ekle(c, "veli", SIFRE, K.YONETICI, yapan="admin")
    _kademeleri_bitir(c, "veli")                              # veli kalıcı kilitli
    t = _kademeleri_bitir(c, "admin", t=T0 + 10 * 3600)
    with pytest.raises(K.GirisHatasi) as e:
        giris(c, "admin", SIFRE, simdi=t + 10)
    assert e.value.kalan_sn is not None                       # admin kalıcı kilitlenmedi


def test_kalici_kilitli_yonetici_son_yonetici_korumasinda_sayilmaz(c):
    """Denetim: A kalıcı kilitliyken B kendini düşürürse kullanılabilir yönetici kalmıyordu."""
    K.kullanici_ekle(c, "veli", SIFRE, K.YONETICI, yapan="admin")
    _kademeleri_bitir(c, "veli")                              # veli kalıcı kilitli
    with pytest.raises(K.KimlikHatasi, match="son yönetici"):
        K.rol_degistir(c, "admin", K.OKUYUCU, yapan="admin")
    with pytest.raises(K.KimlikHatasi, match="son yönetici"):
        K.pasif_yap(c, "admin", yapan="admin")
    K.pasif_yap(c, "veli", yapan="admin")                     # kilitli olanı kapatmak serbest


# ── Antigravity 2026-10-30 BULGU-04: şifre değiştirmede mevcut şifre denemesi kilide işler ──
def test_sifre_degistirde_hatali_mevcut_sifre_kilide_ve_kayda_isler(c):
    for _ in range(3):
        with pytest.raises(K.GirisHatasi, match="Mevcut şifre hatalı"):
            K.sifre_degistir(c, "ali", "yanlis-sifre", "Yeni-Sifre-22")
    with pytest.raises(K.GirisHatasi, match="kilit"):
        K.sifre_degistir(c, "ali", "yanlis-sifre", "Yeni-Sifre-22")       # 4. hata: 1 dk kilit
    with pytest.raises(K.GirisHatasi, match="kilit"):
        K.sifre_degistir(c, "ali", SIFRE, "Yeni-Sifre-22")                # kilitliyken doğru da olmaz
    olaylar = [o for (o,) in c.execute("SELECT olay FROM guvenlik WHERE kullanici = 'ali'")]
    assert olaylar.count("giris_basarisiz") == 4


def test_sifre_degistir_dogru_mevcut_sifreyle_calisir_ve_sayaci_sifirlar(c):
    with pytest.raises(K.GirisHatasi):
        K.sifre_degistir(c, "ali", "yanlis-sifre", "Yeni-Sifre-22")
    K.sifre_degistir(c, "ali", SIFRE, "Yeni-Sifre-22")
    assert c.execute("SELECT hatali FROM kullanicilar WHERE ad = 'ali'").fetchone()[0] == 0
    assert K.giris(c, "ali", "Yeni-Sifre-22").ad == "ali"


def test_sifre_degistir_devre_disi_hesapta_dogru_mesaj(c):
    K.pasif_yap(c, "ali", yapan="admin")
    with pytest.raises(K.GirisHatasi, match="devre dışı"):
        K.sifre_degistir(c, "ali", SIFRE, "Yeni-Sifre-22")
