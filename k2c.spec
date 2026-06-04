# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path


version = os.getenv('K2C_VERSION', '0.1.0')
version_hook = Path('build') / 'k2c_version_hook.py'
version_hook.parent.mkdir(parents=True, exist_ok=True)
version_hook.write_text(
    "import os\n\n"
    f"os.environ.setdefault('K2C_VERSION', {version!r})\n",
    encoding='utf-8',
)


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(version_hook)],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='k2c',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
