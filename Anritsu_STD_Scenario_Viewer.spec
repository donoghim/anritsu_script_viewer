# -*- mode: python ; coding: utf-8 -*-
import os
import re

version_str = ""
if os.path.exists("version.py"):
    with open("version.py", "r", encoding="utf-8") as f:
        match = re.search(r'VERSION\s*=\s*["\']([^"\']+)["\']', f.read())
        if match:
            version_str = f"v{match.group(1)}"

exe_name = f"Anritsu_STD_Scenario_Viewer_{version_str}" if version_str else "Anritsu_STD_Scenario_Viewer"

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('parameter_tree.config', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
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
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

