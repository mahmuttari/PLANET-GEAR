@echo off
REM ---------------------------------------------------------------------
REM  Kot Karelaji - harita arayuzunu baslatir
REM
REM  Bu dosyaya cift tiklayin. Tarayicida arayuz acilir.
REM  Kapatmak icin bu pencerede Ctrl+C yapin ya da pencereyi kapatin.
REM
REM  Gereksinim: Python 3.8 veya uzeri
REM ---------------------------------------------------------------------
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Kot Karelaji

where python >nul 2>&1
if errorlevel 1 (
    where py >nul 2>&1
    if errorlevel 1 (
        echo.
        echo  HATA: Python bulunamadi.
        echo.
        echo  python.org adresinden Python 3.8 veya uzerini kurun.
        echo  Kurulum sirasinda "Add Python to PATH" kutusunu isaretlemeyi
        echo  unutmayin, sonra bu dosyaya yeniden cift tiklayin.
        echo.
        pause
        exit /b 1
    )
    set PY=py
) else (
    set PY=python
)

%PY% karelaj.py arayuz %*
if errorlevel 1 (
    echo.
    pause
)
