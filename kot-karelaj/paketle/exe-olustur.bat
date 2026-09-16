@echo off
REM ---------------------------------------------------------------------
REM  Kot Karelaji - Windows uygulamasi (.exe) olusturma
REM
REM  Bu dosyaya cift tiklayin. Tek dosyalik KotKarelaji.exe uretilir ve
REM  kot-karelaj\dist klasorune yazilir.
REM
REM  Gereksinim: Python 3.8+ ve internet erisimi (PyInstaller kurulumu icin)
REM ---------------------------------------------------------------------
setlocal
chcp 65001 >nul
cd /d "%~dp0\.."

echo ============================================================
echo   KOT KARELAJI - uygulama olusturuluyor
echo ============================================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    where py >nul 2>&1
    if errorlevel 1 (
        echo HATA: Python bulunamadi.
        echo python.org adresinden Python 3.8 veya uzerini kurun ve
        echo kurulum sirasinda "Add Python to PATH" kutusunu isaretleyin.
        echo.
        pause
        exit /b 1
    )
    set PY=py
) else (
    set PY=python
)

echo [1/3] PyInstaller denetleniyor...
%PY% -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo       PyInstaller kurulu degil, kuruluyor...
    %PY% -m pip install --upgrade pyinstaller
    if errorlevel 1 (
        echo HATA: PyInstaller kurulamadi. Internet baglantinizi ve
        echo kurum vekil sunucu ^(proxy^) ayarlarinizi denetleyin.
        echo.
        pause
        exit /b 1
    )
)

echo [2/3] Uygulama paketleniyor ^(birkac dakika surebilir^)...
%PY% -m PyInstaller paketle\kot-karelaj.spec --noconfirm --clean
if errorlevel 1 (
    echo.
    echo HATA: Paketleme basarisiz oldu.
    echo.
    pause
    exit /b 1
)

echo [3/3] Denetleniyor...
if not exist "dist\KotKarelaji.exe" (
    echo HATA: dist\KotKarelaji.exe olusmadi.
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   TAMAMLANDI
echo ============================================================
echo.
echo   Uygulama: %CD%\dist\KotKarelaji.exe
echo.
echo   Bu dosyayi tek basina kopyalayip her yerde calistirabilirsiniz.
echo   Cift tiklayinca harita arayuzu tarayicida acilir.
echo   Ciktilar Belgeler\Kot Karelaji klasorune yazilir.
echo.
pause
