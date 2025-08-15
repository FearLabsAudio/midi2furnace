# build/midi2furnace_ci.spec
# Build in CI with:
#   pyinstaller --noconfirm --workpath .pyibld --distpath dist build/midi2furnace_ci.spec
import os, sys
from PyInstaller.utils.hooks import collect_submodules

PROJECT_DIR = os.path.abspath(os.getcwd())
ENTRY_SCRIPT = os.path.join(PROJECT_DIR, "midi2fur.py")
APP_NAME = "midi2furnace"

hidden = []
hidden += collect_submodules("imgui")
hidden += ["imgui.integrations.pygame"]
hidden += collect_submodules("pygame")
hidden += collect_submodules("OpenGL")
hidden += collect_submodules("mido")
if sys.platform.startswith("win"):
    hidden += ["OpenGL.platform.win32"]

datas = []  # keep CI minimal & predictable

icon_file = None
win_icon = os.path.join(PROJECT_DIR, "assets", "app.ico")
mac_icon = os.path.join(PROJECT_DIR, "assets", "app.icns")
if sys.platform == "win32" and os.path.isfile(win_icon):
    icon_file = win_icon
elif sys.platform == "darwin" and os.path.isfile(mac_icon):
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
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,       # fewer surprises in CI
    console=False,   # GUI app
    icon=icon_file,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name=APP_NAME,
)
