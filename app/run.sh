#!/bin/bash
# Starts the Transcritor server (if it isn't running yet) and opens it in the browser.
DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=51789
URL="http://127.0.0.1:$PORT"

if curl -s -m 2 "$URL/ping" >/dev/null 2>&1; then
  open "$URL"
  exit 0
fi

cd "$DIR" || exit 1
# model was downloaded by the installer; never go online at runtime
export HF_HUB_OFFLINE=1
# caffeinate keeps the Mac from sleeping while the app is running a transcription
nohup /usr/bin/caffeinate -i "$DIR/.venv/bin/python" "$DIR/server.py" \
  > "$DIR/server.log" 2>&1 < /dev/null &

for _ in $(seq 1 60); do
  sleep 0.5
  if curl -s -m 1 "$URL/ping" >/dev/null 2>&1; then
    open "$URL"
    exit 0
  fi
done

osascript -e 'display alert "Transcritor" message "Não foi possível abrir o Transcritor. / Transcritor could not start.\n\nTente instalar de novo. / Try running the installer again."' >/dev/null 2>&1
exit 1
