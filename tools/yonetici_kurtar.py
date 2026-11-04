# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Yönetici kurtarma aracı: yalnız BU BİLGİSAYARDA, veritabanı dosyası üzerinde çalışır.

Yönetici hesabı kilitlendi, devre dışı kaldı ya da şifresi unutuldu ve programda kilidi
açabilecek başka yönetici yoksa kullanılır. Ağdan (tablet sunucusu üzerinden) erişilemez;
veritabanı dosyasına erişebilen kişi zaten bu bilgisayarın başındadır.

Çalıştırma: "Yonetici Kurtarma.bat" ya da (QUALITY PROGRAM kökünden)
`python tools/yonetici_kurtar.py`. Yapılan işlem güvenlik kaydına "kurtarma" olarak yazılır.
"""
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import database, kimlik as K  # noqa: E402

YAPAN = "kurtarma aracı (bu bilgisayar)"


def yoneticiler(c):
    return [k for k in K.kullanicilar(c) if k["rol"] == K.YONETICI]


def kurtar(c, ad, yeni_sifre=None):
    """Yöneticiyi etkinleştirir, kilidini açar; yeni_sifre verilirse şifreyi sıfırlar."""
    if ad not in [y["ad"] for y in yoneticiler(c)]:
        raise K.KimlikHatasi(f"'{ad}' bir yönetici hesabı değil.")
    if yeni_sifre is not None:
        K.sifre_sifirla(c, ad, yeni_sifre, yapan=YAPAN)   # zayıf şifrede hiçbir şey değişmez
    K.aktif_yap(c, ad, yapan=YAPAN)
    K.kilit_ac(c, ad, yapan=YAPAN)
    with c:
        K._olay(c, "kurtarma", ad, yapan=YAPAN,
                ayrinti="şifre sıfırlandı" if yeni_sifre is not None else "kilit açıldı")


def main():
    yol = database.db_yolu()
    if not os.path.exists(yol):
        raise SystemExit(f"Veritabanı yok: {yol} — önce masaüstü programı açın.")
    c = database._baglan(yol)
    # Yükseltilmemiş dosyada eksik tablo kurtarmayı yarıda keserdi (önceki adımlar kaydedilmiş
    # kalırdı); yükseltme yedek alarak masaüstü programında yapılır.
    if c.execute("PRAGMA user_version").fetchone()[0] < database.SEMA_SURUMU:
        raise SystemExit("Veritabanı eski sürümde — önce masaüstü programı bir kez açın "
                         "(giriş ekranı açılınca kapatabilirsiniz). Hiçbir şey değiştirilmedi.")
    try:
        liste = yoneticiler(c)
    except Exception:
        raise SystemExit("Veritabanında kullanıcı tablosu yok — önce masaüstü programı açın.")
    if not liste:
        raise SystemExit("Yönetici hesabı yok; masaüstü programı ilk açılışta oluşturur.")
    print("Yönetici hesapları:")
    for n, y in enumerate(liste, 1):
        durum = ("devre dışı" if not y["aktif"] else "") or (f"kilit: {y['kilit']}" if y["kilit"] else "normal")
        print(f"  {n}) {y['ad']}  ({durum})")
    secim = input("Kurtarılacak hesap numarası (boş = çıkış): ").strip()
    if not secim:
        return
    try:
        ad = liste[int(secim) - 1]["ad"]
    except (ValueError, IndexError):
        raise SystemExit("Geçersiz seçim.")
    yeni = None
    if input("Şifre de sıfırlansın mı? (e/h): ").strip().lower() in ("e", "evet"):
        yeni = getpass.getpass(f"Yeni şifre (en az {K.EN_AZ_SIFRE} karakter): ")
        if getpass.getpass("Yeni şifre (tekrar): ") != yeni:
            raise SystemExit("Şifreler eşleşmiyor; hiçbir şey değiştirilmedi.")
    try:
        kurtar(c, ad, yeni)
    except K.KimlikHatasi as e:
        raise SystemExit(f"{e} Hiçbir şey değiştirilmedi.")
    print(f"'{ad}' etkin ve kilidi açık" + (", şifresi sıfırlandı." if yeni else "."))


if __name__ == "__main__":
    main()
