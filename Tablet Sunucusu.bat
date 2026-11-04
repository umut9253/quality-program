@echo off
rem Tablet sunucusu: bu bilgisayardaki veriyi yerel agda tablete acar (HTTPS + kullanici girisi).
cd /d "%~dp0"
title Tablet Sunucusu - Kalite Yonetim Sistemi
python -m app.sunucu
pause
