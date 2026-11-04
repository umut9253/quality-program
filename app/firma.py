# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Firma kimliği (ad + logo): kalite.db `ayarlar` tablosu (şema 6, 2026-11-02).

Her firma kendi kurulumunu kullanır; firma adı ve logo yerel veritabanında durur, yedeğe
girer, yalnız Yönetici değiştirir (spec F1). Qt'siz: masaüstü ve tablet sunucusu aynı kodu
kullanır. Firma adı boşsa belge üretilmez (F4); logo isteğe bağlıdır.
"""
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from .dil import N_, _

LOGO_EN_BUYUK = 1_000_000   # bayt
AD_YOK = N_("Firma adı ayarlanmamış. Yönetici: YÖNETİM → Firma Bilgileri.")
_IMZALAR = ((b"\x89PNG\r\n\x1a\n", "png"), (b"\xff\xd8\xff", "jpeg"))


@dataclass(frozen=True)
class Firma:
    ad: str
    logo: bytes | None = None


def ad_dogrula(ad):
    """Belgeye girecek firma adı; boşsa ValueError (sessiz yer tutucu yok)."""
    ad = (ad or "").strip()
    if not ad:
        raise ValueError(_(AD_YOK))
    return ad


def logo_turu(veri):
    if len(veri) > LOGO_EN_BUYUK:
        raise ValueError(_("Logo en çok {d} KB olabilir ({d2} KB).").format(d=LOGO_EN_BUYUK // 1000, d2=len(veri) // 1000))
    for imza, tur in _IMZALAR:
        if veri.startswith(imza):
            return tur
    raise ValueError(_("Logo PNG ya da JPEG olmalı."))


def sema_kur(c):
    c.execute("CREATE TABLE IF NOT EXISTS ayarlar (anahtar TEXT PRIMARY KEY, deger BLOB)")


def oku(c):
    d = dict(c.execute("SELECT anahtar, deger FROM ayarlar WHERE anahtar IN "
                       "('firma_adi', 'firma_logo')").fetchall())
    logo = d.get("firma_logo")
    return Firma(d.get("firma_adi") or "", bytes(logo) if logo else None)


def _ozet(f):
    """Değişiklik kaydı: logonun baytı değil, boyutu ve özeti."""
    return {"firma_adi": f.ad, "firma_logo": None if f.logo is None else
            {"bayt": len(f.logo), "sha256": hashlib.sha256(f.logo).hexdigest()}}


def yaz(c, ad, logo, beklenen, kim, kaynak):
    """Tek işlem: okunan değer `beklenen` değilse (başka oturum değiştirdi) CakismaHatasi."""
    from .database import CakismaHatasi   # geç: database bu modülü içe aktarıyor
    ad = (ad or "").strip()
    if logo is not None:
        logo_turu(logo)
    with c:
        c.execute("BEGIN IMMEDIATE")
        once = oku(c)
        if once != beklenen:
            raise CakismaHatasi(_("Firma bilgileri siz düzenlerken başka bir oturumda "
                                "değiştirildi; güncel hali yüklendi."))
        yeni = Firma(ad, logo)
        if yeni == once:
            return
        c.execute("INSERT OR REPLACE INTO ayarlar VALUES ('firma_adi', ?)", (ad,))
        c.execute("INSERT OR REPLACE INTO ayarlar VALUES ('firma_logo', ?)", (logo,))
        c.execute("INSERT INTO degisiklikler (zaman, kullanici, kaynak, bolum, kayit_id, "
                  "kayit_no, islem, once, sonra) VALUES (?, ?, ?, 'ayarlar', 0, "
                  "'Firma bilgileri', 'guncelle', ?, ?)",
                  (datetime.now().isoformat(timespec="seconds"), kim, kaynak,
                   json.dumps(_ozet(once), ensure_ascii=False),
                   json.dumps(_ozet(yeni), ensure_ascii=False)))
