#!/bin/bash
# Attiva / disattiva / controlla il giro automatico delle 9:00.
#
#   ./automazione/attiva.sh            attiva
#   ./automazione/attiva.sh stato      dice se è attivo e quando è partito l'ultima volta
#   ./automazione/attiva.sh prova      lo fa partire subito, senza aspettare le 9
#   ./automazione/attiva.sh disattiva  lo spegne

set -uo pipefail

ETICHETTA="com.linkmotors.ricerca-auto"
CARTELLA="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SORGENTE="$CARTELLA/automazione/$ETICHETTA.plist"
DESTINAZIONE="$HOME/Library/LaunchAgents/$ETICHETTA.plist"
UTENTE="gui/$(id -u)"

case "${1:-attiva}" in

  attiva)
    mkdir -p "$HOME/Library/LaunchAgents"
    # Il percorso della cartella finisce dentro il plist: lo riscriviamo qui,
    # così l'automazione continua a funzionare anche se la cartella si sposta.
    sed "s|/Users/moneymaker/Desktop/Link Motors|$CARTELLA|g" "$SORGENTE" > "$DESTINAZIONE"
    chmod +x "$CARTELLA/giro-giornaliero.sh"
    launchctl bootout "$UTENTE/$ETICHETTA" 2>/dev/null
    launchctl bootstrap "$UTENTE" "$DESTINAZIONE" || exit 1
    echo "Attivo: la ricerca parte ogni giorno alle 9:00."
    echo "Cartella: $CARTELLA"
    ;;

  disattiva)
    launchctl bootout "$UTENTE/$ETICHETTA" 2>/dev/null
    rm -f "$DESTINAZIONE"
    echo "Disattivato. La ricerca non parte più da sola (a mano funziona sempre)."
    ;;

  stato)
    if launchctl print "$UTENTE/$ETICHETTA" >/dev/null 2>&1; then
      echo "Attivo — prossimo giro alle 9:00."
      launchctl print "$UTENTE/$ETICHETTA" | grep -E "last exit code|runs" | sed 's/^ */  /'
    else
      echo "Non attivo. Per attivarlo: ./automazione/attiva.sh"
    fi
    if [ -f "$CARTELLA/output/registro.log" ]; then
      echo "  ultimo giro registrato:"
      grep "=====" "$CARTELLA/output/registro.log" | tail -n 1 | sed 's/^/    /'
    fi
    ;;

  prova)
    echo "Avvio subito (ci vogliono diversi minuti)..."
    launchctl kickstart -p "$UTENTE/$ETICHETTA" || {
      echo "Non risulta attivo: lo eseguo direttamente."
      "$CARTELLA/giro-giornaliero.sh"
    }
    ;;

  *)
    echo "Uso: $0 [attiva|disattiva|stato|prova]"
    exit 1
    ;;
esac
