"""Tipi e utilità condivise dalle fonti (AutoScout24, Subito)."""

from __future__ import annotations

import gzip
import json
import random
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

# Impostato da cerca.py in base a config["limiti"]["pausa_secondi"].
PAUSA_SECONDI = 1.5

_ultima_chiamata = 0.0


class ErroreFonte(RuntimeError):
    """Una fonte ha risposto in modo inatteso (blocco, formato cambiato...)."""


def _rispetta_pausa() -> None:
    """Non più di una richiesta ogni PAUSA_SECONDI, con un po' di jitter."""
    global _ultima_chiamata
    attesa = PAUSA_SECONDI - (time.monotonic() - _ultima_chiamata)
    if attesa > 0:
        time.sleep(attesa + random.uniform(0, 0.4))
    _ultima_chiamata = time.monotonic()


def scarica(url: str, accetta_json: bool = False, tentativi: int = 3) -> str:
    """GET con pausa fra le chiamate, gzip e qualche ritentativo."""
    intestazioni = {
        "User-Agent": UA,
        "Accept-Language": "it-IT,it;q=0.9",
        "Accept-Encoding": "gzip",
        "Accept": "application/json" if accetta_json else "text/html,application/xhtml+xml",
    }
    ultimo_errore: Optional[Exception] = None
    for tentativo in range(tentativi):
        _rispetta_pausa()
        try:
            richiesta = urllib.request.Request(url, headers=intestazioni)
            with urllib.request.urlopen(richiesta, timeout=30) as risposta:
                grezzo = risposta.read()
                if risposta.headers.get("Content-Encoding") == "gzip":
                    grezzo = gzip.decompress(grezzo)
                return grezzo.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as errore:
            ultimo_errore = errore
            if errore.code in (403, 429, 503):
                # Rallentiamo: è il sito che ci sta chiedendo di respirare.
                time.sleep(5 * (tentativo + 1))
            elif 400 <= errore.code < 500:
                raise ErroreFonte(f"{url} -> HTTP {errore.code}") from errore
        except (urllib.error.URLError, TimeoutError) as errore:
            ultimo_errore = errore
            time.sleep(2 * (tentativo + 1))
    raise ErroreFonte(f"{url} non raggiungibile: {ultimo_errore}")


@dataclass
class Annuncio:
    fonte: str  # "AutoScout24" | "Subito"
    id: str
    titolo: str
    marca: str = ""
    modello: str = ""
    versione: str = ""
    prezzo: Optional[int] = None
    anno: Optional[int] = None
    km: Optional[int] = None
    alimentazione: str = ""
    cambio: str = ""
    comune: str = ""
    provincia: str = ""
    cap: str = ""
    telefono: str = ""
    pubblicato: str = ""
    url: str = ""
    # Riempiti dopo, in fase di analisi.
    fascia: str = ""
    doppione_di: str = ""
    nuovo: bool = False       # non c'era nell'ultimo giro
    visto_la_prima_volta: str = ""

    def dizionario(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def chiave_confronto(self) -> tuple:
        """Chiave per accorgersi che la stessa auto è su tutti e due i siti."""
        km_arrotondati = round(self.km / 5000) if self.km else -1
        return (
            normalizza(self.marca),
            normalizza(self.modello)[:12],
            self.prezzo or -1,
            km_arrotondati,
            self.anno or -1,
        )


def normalizza(testo: str) -> str:
    """Minuscolo, senza punteggiatura né spazi doppi: serve per confrontare."""
    testo = (testo or "").lower()
    testo = re.sub(r"[^a-z0-9]+", " ", testo)
    return " ".join(testo.split())


def solo_numero(valore: Any) -> Optional[int]:
    """Estrae il primo intero da '19.000 €', '30.000 km', 19000, None..."""
    if valore is None:
        return None
    if isinstance(valore, (int, float)):
        return int(valore)
    cifre = re.sub(r"[^\d]", "", str(valore))
    return int(cifre) if cifre else None


def carica_json(testo: str, contesto: str) -> Any:
    try:
        return json.loads(testo)
    except json.JSONDecodeError as errore:
        raise ErroreFonte(f"{contesto}: risposta non è JSON valido") from errore
