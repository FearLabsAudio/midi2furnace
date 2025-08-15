# build/midi2furnace_ci.spec
# Build with:
#   pyinstaller --noconfirm --workpath .pyibld build/midi2furnace_ci.spec

import os
import sys
from PyInstaller.utils.hooks import collect_submodules

PROJECT_DIR = os.path.abspath(os.getcwd())
ENTRY_SCRIPT = os.path.join(PROJECT_DIR, "midi2fur.py")
APP_NAME = "midi2furnace"

# Hidden imports (runtime-discovered modules)
hidden = []
hidden += collect_submodules("imgui")
hidden += ["imgui.integrations.pygame"]
hidden += collect_submodules("pygame")
hidden += collect_submodules("OpenGL")
hidden += collect_submodules("mido")
if sys.platform.startswith("win"):
    hidden += ["OpenGL.platform.win32"]

# No extra datas in CI to avoid path snafus
datas = []

# Optional icons only if present (safe to be None)
icon_file = None
win_icon = os.path.join(PROJECT_DIR, "assets", "app.ico")
mac_icon = os.path.join(PROJECT_DIR, "assets", "app.icns")
if sys.platform == "win32" and os.path.exists(win_icon):
    icon_file = win_icon
elif sys.platform == "darwin" and os.path.exists(mac_icon):
    icon_file = mac_icon

block_cipher = None

a = Analysis(
    [ENTRY_SCRIPT],
    pathex=[PROJECT_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # turn off UPX in CI for fewer surprises
    console=False,      # GUI app
    icon=icon_file,
)

# One-dir (folder) build — safest for Pygame/OpenGL/SDL
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name=APP_NAME,
)
