#!/bin/bash
# Remove o Transcritor (as transcrições em Documentos/Transcritor são mantidas).
# Removes Transcritor (your transcripts in Documents/Transcritor are kept).
clear
echo "Isto vai remover o Transcritor deste Mac. Suas transcrições NÃO serão apagadas."
echo "This will remove Transcritor from this Mac. Your transcripts will NOT be deleted."
echo
read -r -p "Continuar? / Continue? (s/y = sim/yes) " ans
case "$ans" in s|S|y|Y|sim|yes) ;; *) exit 0 ;; esac

curl -s -m 2 -X POST http://127.0.0.1:51789/quit >/dev/null 2>&1
rm -rf "$HOME/Library/Application Support/Transcritor"
rm -rf "/Applications/Transcritor.app" "$HOME/Applications/Transcritor.app" 2>/dev/null
rm -rf "$HOME/.cache/huggingface/hub/models--mlx-community--whisper-large-v3-turbo" \
       "$HOME/.cache/huggingface/hub/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo" 2>/dev/null
echo
echo "✓ Removido / Removed."
read -r -p "Enter para fechar / Enter to close… " _
