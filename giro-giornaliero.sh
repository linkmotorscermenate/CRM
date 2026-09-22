#!/bin/bash
# Il giro che parte da solo ogni mattina. Lo lancia launchd (vedi automazione/).
# A mano si può sempre eseguire: ./giro-giornaliero.sh

set -uo pipefail
CARTELLA="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$CARTELLA" || exit 1

REGISTRO="$CARTELLA/output/registro.log"
mkdir -p "$CARTELLA/output"

echo "" >> "$REGISTRO"
echo "===== $(date '+%d/%m/%Y %H:%M') =====" >> "$REGISTRO"

# --no-apri: nessuna finestra che salta su da sola.
# --notifica: a fine giro arriva la notifica del Mac con quante auto nuove.
/usr/bin/python3 cerca.py --no-apri --notifica >> "$REGISTRO" 2>&1
ESITO=$?

if [ $ESITO -ne 0 ]; then
  echo "GIRO FALLITO (codice $ESITO)" >> "$REGISTRO"
  /usr/bin/osascript -e 'display notification "Guarda output/registro.log" with title "Ricerca auto non riuscita"' 2>/dev/null
fi

# Il registro non deve crescere all'infinito: teniamo le ultime 2000 righe.
tail -n 2000 "$REGISTRO" > "$REGISTRO.tmp" && mv "$REGISTRO.tmp" "$REGISTRO"

exit $ESITO
