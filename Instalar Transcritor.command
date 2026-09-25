#!/bin/bash
# ───────────────────────────────────────────────────────────────
#  Transcritor — instalador / installer
#  Instala tudo na pasta do usuário. Não precisa de senha.
#  Installs everything in your user folder. No password needed.
# ───────────────────────────────────────────────────────────────
clear
cd "$(dirname "$0")" || exit 1
SRC="$(pwd)/app"
DEST="$HOME/Library/Application Support/Transcritor"
UV="$HOME/.local/bin/uv"

B=$'\033[1m'; G=$'\033[32m'; R=$'\033[31m'; D=$'\033[2m'; N=$'\033[0m'

step() { echo; echo "${B}▸ $1${N}"; echo "  ${D}$2${N}"; }
fail() {
  echo; echo "${R}${B}✗ Algo deu errado / Something went wrong${N}"
  echo "  $1"
  echo; echo "  Tire uma foto desta tela e mande para a Paola."
  echo "  Take a screenshot of this window and send it to Paola."
  echo; read -r -p "Pressione Enter para fechar / Press Enter to close… " _
  exit 1
}

echo "${B}  Transcritor${N}"
echo "  Instalação / Setup — 5 a 15 minutos / minutes"
echo "  ${D}Deixe esta janela aberta até o fim. / Keep this window open until it finishes.${N}"

# ── 1. Check the Mac ────────────────────────────────────────────
ARCH="$(uname -m)"
OSV="$(sw_vers -productVersion)"
MAJOR="${OSV%%.*}"; REST="${OSV#*.}"; MINOR="${REST%%.*}"
[ "$MINOR" = "$OSV" ] && MINOR=0
if [ "$ARCH" = "arm64" ]; then
  if [ "$MAJOR" -lt 13 ] || { [ "$MAJOR" -eq 13 ] && [ "$MINOR" -lt 5 ]; }; then
    fail "Atualize o macOS para 13.5 ou mais novo (Ajustes do Sistema → Geral → Atualização de Software).
  Please update macOS to 13.5 or newer (System Settings → General → Software Update)."
  fi
elif [ "$MAJOR" -lt 11 ]; then
  fail "Este Mac precisa do macOS 11 ou mais novo. / This Mac needs macOS 11 or newer."
fi

if ! curl -s -m 10 -o /dev/null https://pypi.org; then
  fail "Sem internet. Conecte-se e rode o instalador de novo.
  No internet connection. Connect and run the installer again."
fi

# ── 2. Python tools (uv) ────────────────────────────────────────
step "1/4  Preparando ferramentas / Preparing tools" "uv + Python"
if [ ! -x "$UV" ]; then
  curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh >/dev/null 2>&1 \
    || fail "Não foi possível baixar o uv. / Could not download uv."
fi
[ -x "$UV" ] || fail "uv não encontrado / uv not found."

# ── 3. App files + libraries ────────────────────────────────────
step "2/4  Instalando o Transcritor / Installing Transcritor" "$DEST"
mkdir -p "$DEST" || fail "Não foi possível criar a pasta / Could not create folder."
cp -R "$SRC/." "$DEST/" || fail "Falha ao copiar arquivos / Copy failed."
xattr -dr com.apple.quarantine "$DEST" 2>/dev/null
chmod +x "$DEST/run.sh"
cd "$DEST" || fail "cd"

"$UV" venv --python 3.12 --allow-existing --quiet .venv \
  || fail "Não foi possível instalar o Python. / Could not install Python."
"$UV" pip install --python .venv/bin/python --quiet -r pyproject.toml \
  || fail "Não foi possível instalar as bibliotecas. / Could not install libraries."

# ── 4. Whisper model (~1.5 GB, once) ────────────────────────────
step "3/4  Baixando o modelo Whisper (~1,5 GB) / Downloading the Whisper model (~1.5 GB)" \
     "Pode levar alguns minutos. / This can take a few minutes."
.venv/bin/python engine.py --download \
  || fail "Não foi possível baixar o modelo. Verifique a internet e rode de novo.
  Could not download the model. Check your internet and run again."

# ── 5. Create the app icon in Applications ──────────────────────
step "4/4  Criando o app / Creating the app" ""
APPDIR="/Applications"
[ -w "$APPDIR" ] || APPDIR="$HOME/Applications"
mkdir -p "$APPDIR"
APP="$APPDIR/Transcritor.app"
rm -rf "$APP"
osacompile -o "$APP" -e "do shell script quoted form of \"$DEST/run.sh\"" \
  || fail "Não foi possível criar o app. / Could not create the app."

# custom icon (cosmetic — ignore errors)
(
  ICONSET="$(mktemp -d)/Transcritor.iconset"; mkdir -p "$ICONSET"
  for s in 16 32 128 256 512; do
    sips -z $s $s "$DEST/icon.png" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null 2>&1
    d=$((s*2)); sips -z $d $d "$DEST/icon.png" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null 2>&1
  done
  iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/applet.icns" 2>/dev/null
  touch "$APP"
) 2>/dev/null
codesign --force --deep --sign - "$APP" >/dev/null 2>&1

echo
echo "${G}${B}✓ Pronto! / All set!${N}"
echo
echo "  O app ${B}Transcritor${N} está em ${B}$APPDIR${N}."
echo "  Dica: arraste-o para o Dock para abrir mais rápido."
echo
echo "  The ${B}Transcritor${N} app is in ${B}$APPDIR${N}."
echo "  Tip: drag it to your Dock for quick access."
echo
echo "  Suas transcrições ficam em / Your transcripts are saved in:"
echo "  ${B}Documentos/Transcritor${N}  (Documents/Transcritor)"
echo
open -R "$APP"
open "$APP"
read -r -p "Pressione Enter para fechar / Press Enter to close… " _
