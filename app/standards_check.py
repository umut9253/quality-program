# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""
Standart güncellik kontrolü — Gemini + Google Search tabanlı.

Bu modül, çalışan tek-dosya sürümünden BİREBİR taşınmıştır; arama mantığı,
prompt biçimi ve hata/sentinel davranışı korunmuştur:
  - metin (str) -> başarılı
  - None        -> çağrı başarılı ama içerik yok ("bulunamadı")
  - API_ERROR   -> çağrı başarısız (kota/ağ/sunucu); çağıran mevcut veriyi BOZMAMALI
"""

import os
import re
import json
import time
from datetime import date

import requests

from PyQt6.QtCore import QThread, pyqtSignal


# ── API yapılandırması ──────────────────────────────────────────────
# GÜVENLİK: API anahtarı artık kaynak kodda TUTULMAZ. Sırasıyla şuradan okunur:
#   1) GEMINI_API_KEY ortam değişkeni
#   2) data/api_key.txt dosyası (ilk # ile başlamayan satır)
# Anahtar dosyası kod paylaşılırken paylaşılmamalıdır (.gitignore'da kayıtlı).
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY_FILE = os.path.join(ROOT_DIR, "data", "api_key.txt")

GEMINI_MODEL = "gemini-2.5-flash"
TIMEOUT      = 120   # 20'li setlerde Google Search araması uzun sürebilir

API_ERROR = object()   # çağrı başarısızlığı için ayırt edici sentinel


def _load_api_key():
    key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if key:
        return key
    try:
        with open(KEY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    return line
    except OSError:
        pass
    return ""


GEMINI_API_KEY = _load_api_key()


def _anahtar():
    """Anahtar program açıkken eklenirse yeniden başlatmadan görülür (Antigravity BULGU-15)."""
    global GEMINI_API_KEY
    if not GEMINI_API_KEY:
        GEMINI_API_KEY = _load_api_key()
    return GEMINI_API_KEY


def has_api_key():
    """Kullanılabilir bir API anahtarı var mı?"""
    return bool(_anahtar())


def get_gemini_endpoint():
    # Anahtar URL'ye eklenmez (log/proxy sızıntısına karşı); header ile gönderilir.
    return (f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{GEMINI_MODEL}:generateContent")


def query_gemini(prompt, temperature=0.0, max_tokens=16384, max_retries=4):
    if not _anahtar():
        print("[Gemini] API anahtarı bulunamadı (GEMINI_API_KEY veya data/api_key.txt).")
        return API_ERROR
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
        "tools": [{"googleSearch": {}}],
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(
                get_gemini_endpoint(),
                headers={"Content-Type": "application/json",
                         "x-goog-api-key": GEMINI_API_KEY},
                json=payload,
                timeout=TIMEOUT,
            )
            if response.status_code == 200:
                data = response.json()
                candidates = data.get("candidates") or []
                if not candidates:
                    print(f"[Gemini] Boş yanıt (candidates yok): {str(data)[:200]}")
                    return None
                cand = candidates[0]
                content = cand.get("content") or {}
                parts = content.get("parts") or []
                text = "".join(p.get("text", "") for p in parts).strip()
                if text:
                    return text
                finish = cand.get("finishReason")
                print(f"[Gemini] Metin yok (finishReason={finish}).")
                if finish == "MAX_TOKENS" and attempt < max_retries - 1:
                    max_tokens = min(max_tokens * 2, 65536)
                    payload["generationConfig"]["maxOutputTokens"] = max_tokens
                    time.sleep(2)
                    continue
                return None

            elif response.status_code == 429:  # kota / hız limiti
                wait = 2 ** attempt * 10
                print(f"[Gemini] 429 (kota). {attempt+1}/{max_retries} — {wait}s bekleniyor.")
                if attempt < max_retries - 1:
                    time.sleep(wait)
                    continue
                return API_ERROR
            elif response.status_code in (500, 502, 503, 504):
                wait = 2 ** attempt * 3
                print(f"[Gemini] HTTP {response.status_code}. {wait}s sonra tekrar.")
                if attempt < max_retries - 1:
                    time.sleep(wait)
                    continue
                return API_ERROR
            else:
                print(f"[Gemini] HTTP {response.status_code}: {response.text[:300]}")
                return API_ERROR
        except Exception as e:
            print(f"[Gemini] Ağ/istek hatası ({attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt * 3)
                continue
            return API_ERROR

    return API_ERROR


def _normalize_std_no(s):
    """Standart numarasını eşleştirme için sadeleştir."""
    if not s:
        return ""
    return re.sub(r"[\s\.\-/_:]+", "", str(s)).upper()


def compare_std_status(my_ver, last_ver):
    """Elimdeki sürüm ile en son sürümü karşılaştırıp 'guncel'/'guncelleme' döndürür.

    Yıl bazlı (ASME/EN ISO/AWWA...) → sayısal yıl karşılaştırması.
    Baskı/Edition bazlı (API) → metinsel eşitlik karşılaştırması.
    """
    my_ver = (my_ver or "").strip()
    last_ver = (last_ver or "").strip()
    if not last_ver:
        return "kontrol"   # son sürüm bilinmiyor: "güncel" denmez (Antigravity BULGU-02)
    if not my_ver:
        return "guncelleme"

    last_cmp = last_ver.split("+")[-1].replace("A:", "").strip() if "+" in last_ver else last_ver
    if re.fullmatch(r"\d{4}", my_ver) and re.fullmatch(r"\d{4}", last_cmp):
        return "guncelleme" if last_cmp > my_ver else "guncel"

    norm = lambda s: re.sub(r"[\s\.\-_,()]+", "", s).lower()
    return "guncel" if norm(my_ver) == norm(last_ver) else "guncelleme"


def fetch_latest_versions_bulk(standards_list):
    """Standart listesini Gemini'ye toplu sorar.

    Dönüş:
      - API_ERROR
      - ({norm_no: (last_ver, title, err)}, ordered_list)
    """
    if not standards_list:
        return {}, []

    std_text = "\n".join(
        [f"{idx+1}. Standart No: {s['no']}, Kuruluş: {s['org']}"
         for idx, s in enumerate(standards_list)]
    )

    org_by_no = {_normalize_std_no(s["no"]): (s.get("org") or "").strip().upper()
                 for s in standards_list}
    org_by_pos = [(s.get("org") or "").strip().upper() for s in standards_list]

    prompt = (
        f"Bugünün tarihi: {date.today().isoformat()}.\n"
        "Aşağıda numaralandırılmış bir standart listesi var. Her standardın en son "
        "resmi sürümünü ve başlığını internette arayarak bul. Her standart için, "
        "BUGÜNE KADAR yayımlanmış EN GÜNCEL (en yeni) baskıyı hedefle ve daha yeni "
        "bir baskı/edition yayımlanmış olup olmadığını mutlaka teyit et; eski bir "
        "baskıda kalma.\n"
        "Yanıt olarak SADECE bir JSON dizisi (array) döndür, hiçbir markdown işareti "
        "veya açıklama ekleme. Diziyi listedeki SIRAYLA ve AYNI SAYIDA eleman ile döndür.\n"
        "Her elemanda 'no' alanını sana verdiğim numara ile BİREBİR AYNI yaz.\n"
        "[\n"
        "  {\"no\": \"ASME IX\", \"version\": \"2025\", \"title\": \"Başlık\", \"status\": \"auto\"},\n"
        "  {\"no\": \"AWS D1.1\", \"version\": \"2020\", \"title\": \"Başlık\", \"status\": \"auto\"},\n"
        "  {\"no\": \"API STD 1104\", \"version\": \"22nd Edition (Errata 1, Errata 2, Addendum 1)\", \"title\": \"Başlık\", \"status\": \"auto\"},\n"
        "  {\"no\": \"EN ISO 15614-1\", \"version\": null, \"title\": \"Başlık\", \"status\": \"manuel\"}\n"
        "]\n\n"
        "Önemli notlar:\n"
        "1. Her standardı internette arayarak en güncel verilerle kontrol et (Örneğin ASME IX için güncel sürüm yılı 2025'tir).\n"
        "2. Eğer en son sürüme dair güvenilir bir bilgi yoksa version alanını null bırak ve status alanına 'manuel' yaz.\n"
        "3. Yanıt sadece geçerli bir JSON olmalıdır ve eleman sayısı giriş listesiyle aynı olmalıdır.\n"
        "4. SÜRÜM FORMATI — Her standardın 'version' alanını SADECE kuruluşuna göre yaz:\n"
        "   • Kuruluşu 'API' olan standartlar: YIL YAZMA. Bunun yerine baskı (Edition) "
        "ve yürürlükteki tüm ekleri (Errata / Addendum) yaz. Örnek: "
        "\"23rd Edition (Errata 1, Errata 2, Addendum 1)\". Eki yoksa sadece baskı: "
        "\"23rd Edition\". Sürüm metnine yayın AYI veya TARİHİ YAZMA (ör. 'May 2018' "
        "GİBİ İFADELER KULLANMA); yalnızca baskı numarası ve varsa Errata/Addendum.\n"
        "   • Kuruluşu 'API' DIŞINDA olan TÜM standartlar (ASME, AWS, EN ISO, ISO, "
        "TSE, DIN, AWWA, ASTM, ANSI, BS EN ...): version alanına SADECE 4 haneli "
        "yayın YILINI yaz (örn. \"2020\", \"2024\"). Edition/baskı ifadesi, standart "
        "numarası, harf veya ek YAZMA — yalnızca yıl. Standardın güncel baskısının "
        "yayın yılını bul ve o 4 haneli yılı döndür (ör. AWS D1.1 için \"2020\", "
        "AWWA C210 için \"2024\").\n\n"
        "Standart Listesi:\n" + std_text
    )

    response_text = query_gemini(prompt)
    if response_text is API_ERROR:
        return API_ERROR
    if not response_text:
        return {}, []

    out = response_text.strip()
    json_match = re.search(r"\[.*\]", out, re.DOTALL)
    results = {}
    ordered = []
    if json_match:
        try:
            payload = json.loads(json_match.group(0))
            for pos, item in enumerate(payload):
                if not isinstance(item, dict):
                    ordered.append((None, "", "kontrol"))
                    continue
                no = item.get("no")
                last_ver = item.get("version") or item.get("version_year") or item.get("last_ver")
                title = (item.get("title") or item.get("name") or "").strip()

                org = org_by_no.get(_normalize_std_no(no)) if no else None
                if org is None and pos < len(org_by_pos):
                    org = org_by_pos[pos]

                if last_ver and org != "API":
                    years = re.findall(r"(?:19|20)\d{2}", str(last_ver))
                    last_ver = max(years) if years else None   # "2024 (replaces 2018)": BULGU-01

                if last_ver and str(last_ver).strip().lower() not in ("null", "none", ""):
                    entry = (str(last_ver).strip(), title, None)
                elif item.get("status") == "manuel":
                    entry = (None, title, "manuel")
                else:
                    entry = (None, title, "kontrol")

                ordered.append(entry)
                if no:
                    results[_normalize_std_no(no)] = entry
        except Exception as e:
            print(f"[Bulk Parse] JSON Hatası: {e}")

    return results, ordered


# ── Arka plan işçisi ────────────────────────────────────────────────
class CheckWorker(QThread):
    progress = pyqtSignal(int, str, str, str)   # db_idx, last_ver, title, status
    finished = pyqtSignal(int, int, int)        # total, updates, manuel

    def __init__(self, standards):
        super().__init__()
        self.standards = standards
        self.chunk_size = 20
        self.chunk_pause = 12

    def _bekle(self):
        """Parçalar arası kota beklemesi; program kapanırken beklenmez (Antigravity BULGU-04)."""
        for _ in range(int(self.chunk_pause * 10)):
            if self.isInterruptionRequested():
                return
            self.msleep(100)

    def run(self):
        updates = manuel = 0
        total_standards = len(self.standards)

        for i in range(0, total_standards, self.chunk_size):
            if self.isInterruptionRequested():
                return
            chunk = self.standards[i:i + self.chunk_size]
            chunk_data = [{"no": rec["no"], "org": rec["org"]} for _, rec in chunk]

            try:
                fetched = fetch_latest_versions_bulk(chunk_data)
            except Exception as e:
                print(f"[Worker] Toplu çekim hatası: {e}")
                fetched = API_ERROR

            if fetched is API_ERROR:
                for db_idx, rec in chunk:
                    self.progress.emit(db_idx, "", "", "skip")
                if i + self.chunk_size < total_standards:
                    self._bekle()
                continue

            bulk_results, ordered_results = fetched

            for pos, (db_idx, rec) in enumerate(chunk):
                no_key = _normalize_std_no(rec["no"])
                res = bulk_results.get(no_key)
                if res is None and pos < len(ordered_results):
                    res = ordered_results[pos]

                if res:
                    last_ver, title, err = res
                else:
                    last_ver, title, err = None, None, "hata"

                if err in ("hata", "kontrol", "manuel") or last_ver is None:
                    status = err or "hata"
                    if status == "manuel":
                        manuel += 1
                    self.progress.emit(db_idx, str(rec.get("lastVer") or ""),
                                       str(title or ""), status)
                    continue

                my_ver = str(rec.get("myVer") or "").strip()
                status = compare_std_status(my_ver, last_ver)
                if status == "guncelleme":
                    updates += 1
                self.progress.emit(db_idx, last_ver, title or "", status)

            if i + self.chunk_size < total_standards:
                self._bekle()

        self.finished.emit(total_standards, updates, manuel)
