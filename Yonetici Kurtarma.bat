@echo off
rem Yonetici kurtarma: yalniz bu bilgisayarda; kilitli/devre disi yoneticiyi acar, istenirse sifre sifirlar.
cd /d "%~dp0"
title Yonetici Kurtarma - Kalite Yonetim Sistemi
python tools\yonetici_kurtar.py
pause
