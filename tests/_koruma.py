# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Test güvenlik ağı: hiçbir test gerçek data/ ya da yedek/ klasörüne SQLite bağlantısı açamaz.

2026-11-01 olayı: bir test monkeypatch.undo() ile `klasor` fikstürünün yollarını da geri aldı;
ardından açılan Database() gerçek kalite.db'yi şema 5'e yükseltti (veri kaybı yok, yedek alındı).
conftest.py sqlite3.connect'i bu kontrolle sarar; bağlantı açılmadan GercekVeriHatasi verilir.
"""
import os
import re
import urllib.parse

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_KLASORLER = tuple(os.path.join(KOK, d) for d in ("data", "yedek"))
_YASAK = tuple(os.path.normcase(k) + os.sep for k in _KLASORLER)


# \\?\D:\, \\.\D:\, \\localhost\D$\, \\127.0.0.1\D$\, \\?\UNC\localhost\D$\ → D:\ (Antigravity
# 5b-1 BULGU-02: yönetici paylaşımı kapalı makinede os.stat düşer; metinle, ağa sormadan çözülür)
_YEREL = re.compile(r"^[\\/]{2}(?:[?.][\\/](?:UNC[\\/])?)?(?:(?:localhost|127\.0\.0\.1)[\\/])?"
                    r"([a-z])[$:](?=[\\/]|$)", re.IGNORECASE)


class GercekVeriHatasi(RuntimeError):
    """Test gerçek veri klasörüne bağlanmaya çalıştı."""


def _dosya_yolu(database):
    yol = os.fspath(database)
    if isinstance(yol, bytes):
        yol = yol.decode()
    if yol.startswith("file:"):
        u = urllib.parse.urlsplit(yol)
        yol = urllib.parse.unquote(u.path)
        if u.netloc and u.netloc.lower() != "localhost":
            yol = "//" + u.netloc + yol                       # file://sunucu/paylasim/...
        yol = yol.lstrip("/") if len(yol) > 2 and yol.lstrip("/")[1:2] == ":" else yol
    m = _YEREL.match(yol)
    return m.group(1) + ":" + yol[m.end():] if m else yol


def _ayni_klasorde(yol):
    """Yazımdan bağımsız (\\\\?\\, \\\\.\\, UNC, kısa ad, bağlantı): yolun var olan üst
    klasörlerinden biri gerçek data/ ya da yedek/ mi? Yalnız os.stat; dosya açılmaz."""
    p = os.path.abspath(yol)
    while True:
        for k in _KLASORLER:
            try:
                if os.path.samefile(p, k):
                    return True
            except OSError:
                pass
        ust = os.path.dirname(p)
        if ust == p:
            return False
        p = ust


def yasak_yol(database):
    yol = _dosya_yolu(database)
    if not yol or yol == ":memory:":
        return False
    return ((os.path.normcase(os.path.abspath(yol)) + os.sep).startswith(_YASAK)
            or _ayni_klasorde(yol))


def sar(connect):
    def korumali(database, *a, **k):
        if yasak_yol(database):
            raise GercekVeriHatasi(f"Test gerçek veri klasörüne bağlanmak istedi: {database}")
        return connect(database, *a, **k)
    return korumali
