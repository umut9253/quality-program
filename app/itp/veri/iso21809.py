# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""ISO 21809-1 / ISO 21809-2 kaplama kabul kriterleri: BOŞ İSKELET (public depo).

Standart içeriği telif kapsamındadır ve bu depoda yoktur. Değişken adları programın
beklediği biçimdedir; tablolar boştur. Kendi lisanslı standardınızdan doldurun.

KRITERLER sütun düzeni — 15 sütun:
  1 Standart          P1 / P2
  2 Kaplama sınıfı    A / B / C / tümü
  3 Aşama             hammadde / yüzey hazırlığı / uygulanmış kaplama /
                      kalifikasyon / tamir / belge
  4 Kriter
  5 Birim
  6 Test metodu
  7 Yön               min / maks / aralık / metin / tablo
  8 Değer 1           yön=min → minimum · yön=maks → maksimum · yön=aralık → alt
  9 Değer 2           yön=aralık → üst
 10 Metin kriteri
 11 Frekans — kalifikasyon
 12 Frekans — PPT
 13 Frekans — üretim
 14 Standart atıfı
 15 Not

KALINLIK: (standart, sınıf, kalınlık sınıfı, alt, alt_dahil, üst, üst_dahil, değer, not)
SINIFLAR: (standart, sınıf, malzeme, min °C, maks °C, not)
"""

P1 = "ISO 21809-1"
P2 = "ISO 21809-2"
BATCH = "her batch (üretici sertifikası)"

KRITERLER = []
KALINLIK = []
SINIFLAR = []
