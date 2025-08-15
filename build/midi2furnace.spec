# build/midi2furnace.spec
# Build onedir (recommended):
#   pyinstaller --noconfirm build\midi2furnace.spec
# Build onefile:
#   set ONEFILE=1 & pyinstaller --noconfirm build\midi2furnace.spec
import os, sys
from PyInstaller.utils.hooks import collect_submodules

PROJECT_DIR = os.path.abspath(os.getcwd())
ENTRY_SCRIPT = os.path.join(PROJECT_DIR, "midi2fur.py")
APP_NAME = "midi2furnace"
ONEFILE = os.environ.get("ONEFILE", "0") == "1"

hidden = []
hidden += collect_submodules("imgui")
hidden += ["imgui.integrations.pygame"]
hidden += collect_submodules("pygame")
hidden += collect_submodules("OpenGL")
hidden += collect_submodules("mido")
if sys.platform.startswith("win"):
    hidden += ["OpenGL.platform.win32"]

datas = []

def add_file(rel_path, dest="."):
    p = os.path.join(PROJECT_DIR, rel_path)
    if os.path.exists(p):
        datas.append((p, dest))

def add_tree(rel_folder, dest_folder):
    root = os.path.join(PROJECT_DIR, rel_folder)
    if not os.path.isdir(root):
        return
    for r, _d, files in os.walk(root):
        rel = os.path.relpath(r, root)
        tgt = os.path.join(dest_folder, rel) if rel != "." else dest_folder
        for f in files:
            datas.append((os.path.join(r, f), tgt))

# optional extras
add_file("readme.md")
add_file("requirements.txt")
if os.path.isdir(os.path.join(PROJECT_DIR, "sample MIDI files")):
    add_tree("sample MIDI files", "sample MIDI files")

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
    upx=True,
    console=False,
    icon=icon_file,
)

if ONEFILE:
    # single-file exe in dist\midi2furnace.exe
    coll = exe
else:
    # folder build in dist\midi2furnace\midi2furnace.exe
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        name=APP_NAME,
    )
