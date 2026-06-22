# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        # yfinance internals
        'yfinance',
        'yfinance.base',
        'yfinance.ticker',
        'yfinance.tickers',
        'yfinance.download',
        'multitasking',
        'peewee',
        'platformdirs',
        # pandas / numpy
        'pandas',
        'pandas._libs.tslibs.base',
        'numpy',
        'numpy.core._multiarray_umath',
        # requests / urllib
        'requests',
        'urllib3',
        'charset_normalizer',
        'certifi',
        # html parsing
        'bs4',
        'lxml',
        'lxml.etree',
        'lxml._elementpath',
        # anthropic (optional news feature)
        'anthropic',
        'anthropic._client',
        'anthropic._base_client',
        'anthropic.types',
        'anthropic.resources',
        'anthropic.resources.messages',
        'httpx',
        'httpcore',
        'anyio',
        'sniffio',
        # dotenv
        'dotenv',
        'dotenv.main',
        # stdlib extras that get missed
        'decimal',
        'json',
        'csv',
        'pathlib',
    ],
    excludes=[
        'tkinter',
        'matplotlib',
        'IPython',
        'jupyter',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='stock-analyzer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,   # CLI tool — keep console open
    onefile=True,
)
