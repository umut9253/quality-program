# -*- coding: utf-8 -*-
# © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved.
"""Tablet APK'sını Gradle'sız derler: aapt2 → javac → d8 → zipalign → apksigner.

Çalıştırma (QUALITY PROGRAM kökünden): `python tools/apk_derle.py`
Gerekenler (kullanıcı klasörüne kurulu, yönetici izni gerekmez):
  JDK 17: %LOCALAPPDATA%/Programs/jdk17 · Android SDK: %LOCALAPPDATA%/Android/Sdk
  (platforms;android-34, build-tools;34.0.0)
İmza: %USERPROFILE%/.android/kalite-tablet.jks (yoksa üretilir; parolası yanındaki
kalite-tablet-parola.txt). Güncellemeler aynı anahtarla imzalanmalı — kaybolursa tablette
uygulama silinip yeniden kurulur. Anahtar depoya girmez.
Çıktı: tablet/android/cikti/KaliteYS.apk
"""
import os
import secrets
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import sunucu  # noqa: E402  (sertifika üretimi/parmak izi tek kaynak)

KOK = Path(__file__).resolve().parent.parent
PROJE = KOK / "tablet" / "android"
INSA = PROJE / "insa"
CIKTI = PROJE / "cikti" / "KaliteYS.apk"
YEREL = Path(os.environ["LOCALAPPDATA"])
JDK = YEREL / "Programs" / "jdk17"
SDK = YEREL / "Android" / "Sdk"
BT = SDK / "build-tools" / "34.0.0"
ANDROID_JAR = SDK / "platforms" / "android-34" / "android.jar"
IMZA = Path.home() / ".android" / "kalite-tablet.jks"
PAROLA = IMZA.with_name("kalite-tablet-parola.txt")
SURUM_KODU, SURUM_ADI = 2, "0.2"   # 0.2: HTTPS + sertifika sabitleme + kullanıcı girişi
MIN_SDK, HEDEF_SDK = 24, 34


def calistir(*komut):
    r = subprocess.run([str(k) for k in komut], capture_output=True, text=True,
                       env=dict(os.environ, JAVA_HOME=str(JDK)))
    if r.returncode != 0:
        raise SystemExit(f"HATA: {komut[0]}\n{r.stdout}\n{r.stderr}")
    return r.stdout


def ikon(hedef):
    """Uygulama ikonu (lacivert zemin + "K"); PIL ile deterministik."""
    from PIL import Image, ImageDraw, ImageFont
    for klasor, boy in (("mipmap-mdpi", 48), ("mipmap-hdpi", 72), ("mipmap-xhdpi", 96),
                        ("mipmap-xxhdpi", 144), ("mipmap-xxxhdpi", 192)):
        im = Image.new("RGBA", (boy, boy), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, boy - 1, boy - 1), radius=boy // 5, fill="#1B2A4A")
        try:
            f = ImageFont.truetype("segoeuib.ttf", int(boy * 0.62))
        except OSError:
            f = ImageFont.load_default()
        d.text((boy / 2, boy / 2), "K", font=f, fill="#C9A227", anchor="mm")
        (hedef / klasor).mkdir(parents=True, exist_ok=True)
        im.save(hedef / klasor / "ic_launcher.png")


def imza_anahtari():
    if IMZA.exists():
        return PAROLA.read_text(encoding="utf-8").strip()
    IMZA.parent.mkdir(parents=True, exist_ok=True)
    parola = secrets.token_urlsafe(18)
    PAROLA.write_text(parola + "\n", encoding="utf-8")
    calistir(JDK / "bin" / "keytool.exe", "-genkeypair", "-keystore", IMZA, "-alias", "kalite",
             "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000", "-storepass", parola,
             "-keypass", parola, "-dname", "CN=Kalite YS, O=QUALITY PROGRAM, C=TR")
    return parola


def pin_java(hedef):
    """Sunucu sertifikasının SHA-256 parmak izini Pin.java olarak üretir (APK yalnız buna güvenir).
    Sertifika yoksa üretilir; sertifika değişirse APK yeniden derlenip kurulmalı."""
    crt, _ = sunucu.sertifika_hazirla()
    iz = sunucu.parmak_izi(crt)
    yol = hedef / "com" / "kalite" / "tablet" / "Pin.java"
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text("package com.kalite.tablet;\n\n/** Otomatik üretilir (tools/apk_derle.py): "
                   "data/tls/sunucu.crt SHA-256 parmak izi. Elle düzenlemeyin. */\n"
                   f'final class Pin {{\n    static final String SHA256 = "{iz}";\n}}\n',
                   encoding="utf-8")
    return yol, iz


def main():
    for gerek in (JDK / "bin" / "javac.exe", BT / "aapt2.exe", ANDROID_JAR):
        if not gerek.exists():
            raise SystemExit(f"Eksik araç: {gerek}")
    if INSA.exists():
        shutil.rmtree(INSA)
    res, siniflar = INSA / "res", INSA / "siniflar"
    siniflar.mkdir(parents=True)
    ikon(res)

    derli = INSA / "res.zip"
    calistir(BT / "aapt2.exe", "compile", "--dir", res, "-o", derli)
    ham = INSA / "ham.apk"
    calistir(BT / "aapt2.exe", "link", "-o", ham, "-I", ANDROID_JAR, "--manifest",
             PROJE / "AndroidManifest.xml", "--min-sdk-version", MIN_SDK,
             "--target-sdk-version", HEDEF_SDK, "--version-code", SURUM_KODU,
             "--version-name", SURUM_ADI, derli)

    pin, iz = pin_java(INSA / "uretilen")
    kaynaklar = sorted((PROJE / "src").rglob("*.java")) + [pin]
    calistir(JDK / "bin" / "javac.exe", "-encoding", "UTF-8", "-source", "8", "-target", "8",
             "-bootclasspath", ANDROID_JAR, "-Xlint:-options", "-d", siniflar, *kaynaklar)
    dex = INSA / "dex"; dex.mkdir()
    calistir(BT / "d8.bat", "--lib", ANDROID_JAR, "--min-api", MIN_SDK, "--release",
             "--output", dex, *sorted(siniflar.rglob("*.class")))

    imzasiz = INSA / "imzasiz.apk"
    shutil.copy(ham, imzasiz)
    with zipfile.ZipFile(imzasiz, "a", zipfile.ZIP_DEFLATED) as z:
        z.write(dex / "classes.dex", "classes.dex")
    hizali = INSA / "hizali.apk"
    calistir(BT / "zipalign.exe", "-f", "-p", "4", imzasiz, hizali)

    parola = imza_anahtari()
    CIKTI.parent.mkdir(parents=True, exist_ok=True)
    calistir(BT / "apksigner.bat", "sign", "--ks", IMZA, "--ks-key-alias", "kalite",
             "--ks-pass", f"pass:{parola}", "--key-pass", f"pass:{parola}", "--out", CIKTI, hizali)
    print(calistir(BT / "apksigner.bat", "verify", "--verbose", CIKTI).splitlines()[0])
    print(f"APK: {CIKTI} ({CIKTI.stat().st_size // 1024} KB)")
    print(f"Sabitlenen sertifika parmak izi: {iz[:16]}…{iz[-16:]}")


if __name__ == "__main__":
    sys.exit(main())
