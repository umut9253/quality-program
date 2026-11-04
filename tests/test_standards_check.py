# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Standart sürüm kontrolünün saf mantığı (Antigravity tam program denetimi 2026-11-02:
BULGU-01, 02, 15, 18). Gemini'ye istek gitmez: yanıt metni yamalanır."""
import pytest

from app import standards_check as S


@pytest.mark.parametrize("benim, son, beklenen", [
    ("2020", "2024", "guncelleme"),
    ("2024", "2024", "guncel"),
    ("", "2024", "guncelleme"),
    ("2015", "", "kontrol"),      # son sürüm bilinmiyor: "Güncel" denmez (BULGU-02)
    ("2015", None, "kontrol"),
    ("", "", "kontrol"),
])
def test_surum_karsilastirma(benim, son, beklenen):
    assert S.compare_std_status(benim, son) == beklenen


def _yanit(monkeypatch, metin):
    monkeypatch.setattr(S, "query_gemini", lambda *a, **k: metin)


@pytest.mark.parametrize("surum", ["2024 (replaces 2018)", "2018, 2024", "2024 (first published 1999)"])
def test_birden_fazla_yilda_en_yenisi_secilir(monkeypatch, surum):
    """Model "yalnız yıl" kuralına uymazsa eski yıl seçilip güncelleme kaçmasın (BULGU-01)."""
    _yanit(monkeypatch, f'[{{"no": "ASME IX", "version": "{surum}", "title": "T", "status": "auto"}}]')
    sonuc, sirali = S.fetch_latest_versions_bulk([{"no": "ASME IX", "org": "ASME"}])
    assert sirali[0][0] == "2024"


def test_api_standardinda_baski_metni_korunur(monkeypatch):
    _yanit(monkeypatch, '[{"no": "API 5L", "version": "46th Edition (Errata 1, 2018)", '
                        '"title": "T", "status": "auto"}]')
    _, sirali = S.fetch_latest_versions_bulk([{"no": "API 5L", "org": "API"}])
    assert sirali[0][0] == "46th Edition (Errata 1, 2018)"


def test_program_acikken_eklenen_anahtar_gorulur(monkeypatch, tmp_path):
    """data/api_key.txt program açıkken konursa yeniden başlatmadan kullanılır (BULGU-15)."""
    dosya = tmp_path / "api_key.txt"
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(S, "KEY_FILE", str(dosya))
    monkeypatch.setattr(S, "GEMINI_API_KEY", "")
    assert not S.has_api_key()
    dosya.write_text("# yorum\ndeneme-anahtari\n", encoding="utf-8")
    assert S.has_api_key()
