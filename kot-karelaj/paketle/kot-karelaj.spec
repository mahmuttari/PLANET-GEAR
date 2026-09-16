# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller tanım dosyası
=========================

Tek dosyalık, kurulum gerektirmeyen bir uygulama üretir. Windows'ta
``KotKarelaji.exe`` adını alır ve çift tıklandığında doğrudan harita
arayüzünü açar.

Kullanım (kot-karelaj klasöründen)::

    pyinstaller paketle/kot-karelaj.spec --noconfirm --clean

Arayüz sayfası (``karelaj/web/index.html``) veri dosyası olarak pakete
gömülür; çalışma anında ``sys._MEIPASS`` altından okunur.
"""

import os

KOK = os.path.abspath(os.path.join(SPECPATH, os.pardir))

analiz = Analysis(
    [os.path.join(KOK, "karelaj.py")],
    pathex=[KOK],
    binaries=[],
    datas=[
        (os.path.join(KOK, "karelaj", "web", "index.html"), os.path.join("karelaj", "web")),
    ],
    hiddenimports=[
        "karelaj.cli",
        "karelaj.sunucu",
        "karelaj.geodezi",
        "karelaj.geometri",
        "karelaj.izgara",
        "karelaj.raster",
        "karelaj.kontur",
        "karelaj.hacim",
        "karelaj.onbellek",
        "karelaj.bicim",
        "karelaj.kaynaklar",
        "karelaj.kaynaklar.temel",
        "karelaj.kaynaklar.web",
        "karelaj.kaynaklar.yerel",
        "karelaj.yazicilar",
        "karelaj.yazicilar.ncn",
        "karelaj.yazicilar.metin",
        "karelaj.yazicilar.dxf",
        "karelaj.yazicilar.cografi",
        "karelaj.yazicilar.rapor",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Araç bu kütüphanelerin hiçbirini kullanmaz; ortamda kuruluysalar
    # bile pakete girmemeleri için dışarıda bırakılır.
    excludes=[
        "tkinter", "numpy", "pyproj", "rasterio", "PIL", "matplotlib",
        "pandas", "scipy", "pytest", "setuptools", "pip",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(analiz.pure)

exe = EXE(
    pyz,
    analiz.scripts,
    analiz.binaries,
    analiz.datas,
    [],
    name="KotKarelaji",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(SPECPATH, "kot-karelaj.ico"),
)
