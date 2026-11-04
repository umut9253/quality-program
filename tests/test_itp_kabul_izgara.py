# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""app/itp/kabul_izgara.py: kabul parçaları → Excel ızgara satırları."""
import pytest

from app.itp.dokuman import ElleGirilecek, KalemTablosu, Metin
from app.itp.kabul_izgara import ALT_SUTUN, BASLIK, METIN, VERI, IzgaraSatiri, dagit, izgara


@pytest.mark.parametrize("n, beklenen", [
    (1, ((0, 7),)), (2, ((0, 3), (4, 7))), (3, ((0, 2), (3, 5), (6, 7))),
    (5, ((0, 1), (2, 3), (4, 5), (6, 6), (7, 7))), (8, tuple((i, i) for i in range(8))),
])
def test_dagit(n, beklenen):
    assert dagit(n) == beklenen


@pytest.mark.parametrize("n", [0, 9])
def test_dagit_sinir_disi(n):
    with pytest.raises(TypeError, match="sütun"):
        dagit(n)


def test_ardisik_metinler_tek_satir_tablo_ayri():
    p = (Metin("a"), Metin("b"), KalemTablosu(("X", "Y"), (("1", "2"), ("3", "4"))),
         Metin("c"), ElleGirilecek("Lot"))
    assert izgara(p) == (
        IzgaraSatiri(METIN, ((0, 7, "a\nb"),)),
        IzgaraSatiri(BASLIK, ((0, 3, "X"), (4, 7, "Y"))),
        IzgaraSatiri(VERI, ((0, 3, "1"), (4, 7, "2"))),
        IzgaraSatiri(VERI, ((0, 3, "3"), (4, 7, "4"))),
        IzgaraSatiri(METIN, ((0, 7, "c\nELLE GİRİLECEK: Lot"),), elle=True))


def test_bos_kabul_tek_bos_satir():
    assert izgara(()) == (IzgaraSatiri(METIN, ((0, ALT_SUTUN - 1, ""),)),)


def test_satir_uzunlugu_baslikla_esit_olmali():
    with pytest.raises(ValueError):
        izgara((KalemTablosu(("X", "Y"), (("1",),)),))


def test_tanimsiz_parca():
    with pytest.raises(TypeError, match="tanımsız kabul parçası"):
        izgara(("düz metin",))


def test_sekizden_cok_sutunlu_eski_tablo_metin_olarak():
    """Kilitli eski görüntülerde 19-20 sütunlu kimya tablosu var (doğrulama KRİTİK-1):
    hata vermez, eski düz biçimde ("a | b | …") metin satırı olarak basılır."""
    bas = tuple("abcdefghij")
    (iz,) = izgara((Metin("Product analysis"), KalemTablosu(bas, (tuple("0123456789"),)),
                    Metin("Spec. 1 Table 5")))
    assert iz == IzgaraSatiri(METIN, ((0, 7, "Product analysis\na | b | c | d | e | f | g | h | i"
                                         " | j\n0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9\n"
                                         "Spec. 1 Table 5"),))


def test_uzun_metin_birden_cok_satira_bolunur():
    """Satır yüksekliği Excel'de 409 pt ile sınırlı: uzun metin (çok et kalınlığı) bölünür."""
    satirlar = izgara(tuple(Metin(f"t = {i}") for i in range(45)))
    assert [len(s.hucreler[0][2].split("\n")) for s in satirlar] == [20, 20, 5]
    assert all(s.tur == METIN for s in satirlar)
