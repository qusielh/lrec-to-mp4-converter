# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files

UI = 'ui'


def ui_datas(*names):
    """Bundle the free edition front end."""
    out = []
    for n in names:
        src = os.path.join(UI, n)
        if not os.path.exists(src):
            raise SystemExit('missing UI file: %s' % src)
        out.append((src, UI))
    fdir = os.path.join(UI, 'fonts')
    if os.path.isdir(fdir):
        for f in sorted(os.listdir(fdir)):
            if f.lower().endswith(('.woff2', '.woff', '.ttf', '.otf')):
                out.append((os.path.join(fdir, f), os.path.join(UI, 'fonts')))
    return out


datas = ui_datas('index.html', 'app_common.js', 'app.js', 'style.css')
datas += collect_data_files('webview')
datas += collect_data_files('clr_loader')

hiddenimports = [
    'webview',
    'webview.platforms.edgechromium',
    'webview.platforms.winforms',
    'clr',
    'clr_loader',
    'pythonnet',
    'bottle',
]

a = Analysis(
    ['l2m_ui.py'],
    pathex=[],
    binaries=[('bin/ffmpeg.exe', '.'), ('bin/tsdecode.exe', '.')],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'cryptography',
    ],
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
    name='L2M',
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
    icon=['assets/l2m.ico'],
    version='version_info.txt',
)
