#!/usr/bin/env python3
"""Il sito: interfaccia web alla ricerca auto.

    python3 server.py            → apre http://localhost:8080

Gira sul Mac, non su un hosting: la ricerca deve poter interrogare AutoScout24
e Subito, cosa che una pagina statica non può fare.
"""

from __future__ import annotations

import base64
import csv
import hmac
import json
import os
import shutil
import sys
import threading
import urllib.parse
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

import cerca
from fonti import subito
from fonti.comune import ErroreFonte

QUI = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(QUI, "web")
# Su un hosting (Render) il disco dell'app è effimero: quel che l'app scrive va
# perso a ogni riavvio. Se è montato un disco persistente si punta lì con
# CRM_DATA_DIR, così storico, report, impostazioni e stato dei contatti restano.
# In locale, senza quella variabile, tutto resta nella cartella del progetto.
BASE_DATI = os.environ.get("CRM_DATA_DIR", QUI)
USCITA = os.path.join(BASE_DATI, "output")
DATI = os.path.join(BASE_DATI, "dati")
CONFIG = os.path.join(BASE_DATI, "config.json")
# Lo stato di lavorazione di ogni annuncio (contattato / da chi / status affare),
# agganciato all'URL dell'annuncio così sopravvive ai nuovi giri di ricerca.
ORGANIZZAZIONE = os.path.join(DATI, "organizzazione.json")
# Render fornisce la porta in PORT; in locale si usa PORTA (default 8080).
PORTA = int(os.environ.get("PORT") or os.environ.get("PORTA") or "8080")

# Login: attivo solo se sono configurati degli utenti (variabile CRM_UTENTI, con
# coppie "utente:password" separate da virgola). Senza, in locale, niente login.
def _utenti_configurati() -> dict[str, str]:
    utenti: dict[str, str] = {}
    for coppia in (os.environ.get("CRM_UTENTI") or "").split(","):
        utente, separatore, password = coppia.partition(":")
        if separatore and utente.strip():
            utenti[utente.strip()] = password
    return utenti


UTENTI = _utenti_configurati()

TIPI = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
        ".js": "text/javascript; charset=utf-8", ".csv": "text/csv; charset=utf-8"}


# --------------------------------------------------------------------------
# Lo stato di un giro di ricerca (uno alla volta: non tempestiamo i siti)
# --------------------------------------------------------------------------

class Giro:
    def __init__(self) -> None:
        self.blocco = threading.Lock()
        self.in_corso = False
        self.righe: list[str] = []
        self.errore = ""
        self.riepilogo: dict[str, Any] = {}
        self.annunci: list[dict] = []
        self.avvisi: list[str] = []
        self.momento = ""

    def scrivi(self, riga: str) -> None:
        with self.blocco:
            self.righe.append(riga)

    def istantanea(self) -> dict:
        with self.blocco:
            return {
                "in_corso": self.in_corso,
                "righe": list(self.righe),
                "errore": self.errore,
                "riepilogo": dict(self.riepilogo),
                "avvisi": list(self.avvisi),
                "momento": self.momento,
                "quanti": len(self.annunci),
            }

    def avvia(self, config: dict, massimo: int, solo: Optional[str]) -> bool:
        with self.blocco:
            if self.in_corso:
                return False
            self.in_corso = True
            self.righe = []
            self.errore = ""
        threading.Thread(
            target=self._lavora, args=(config, massimo, solo), daemon=True
        ).start()
        return True

    def _lavora(self, config: dict, massimo: int, solo: Optional[str]) -> None:
        try:
            esito = cerca.esegui(config, solo, massimo, self.scrivi)
            with self.blocco:
                self.annunci = [_in_dizionario(a) for a in esito["annunci"]]
                self.avvisi = esito["avvisi"]
                self.momento = esito["inizio"].strftime("%d/%m/%Y alle %H:%M")
                self.riepilogo = {
                    "totale": len(esito["annunci"]),
                    "nuovi": esito["nuovi"],
                    "doppioni": esito["doppioni"],
                    "confronto": esito["confronto"],
                    "csv": os.path.basename(esito["csv"]),
                    "report": os.path.basename(esito["html"]),
                }
            self.scrivi("Fatto.")
        except Exception as errore:  # il sito non deve morire con la ricerca
            with self.blocco:
                self.errore = f"{type(errore).__name__}: {errore}"
            self.scrivi(f"Interrotto: {errore}")
        finally:
            with self.blocco:
                self.in_corso = False


giro = Giro()


def _in_dizionario(annuncio) -> dict:
    dati = annuncio.dizionario()
    dati["nome"] = " ".join(p for p in (annuncio.marca, annuncio.modello) if p) or annuncio.titolo
    return dati


def carica_ultimo() -> None:
    """All'apertura del sito mostriamo l'ultimo giro, senza rifarlo."""
    percorso = os.path.join(USCITA, "ultimo.csv")
    if not os.path.exists(percorso):
        return
    campo_per_intestazione = {intestazione: campo for campo, intestazione in cerca.COLONNE}
    annunci = []
    with open(percorso, encoding="utf-8-sig", newline="") as file:
        for riga in csv.DictReader(file, delimiter=";"):
            dati = {campo_per_intestazione[k]: v for k, v in riga.items() if k in campo_per_intestazione}
            for numerico in ("prezzo", "anno", "km"):
                dati[numerico] = int(dati[numerico]) if dati.get(numerico) else None
            dati["nuovo"] = dati.get("nuovo") == "NUOVO"
            dati["nome"] = " ".join(p for p in (dati.get("marca"), dati.get("modello")) if p)
            annunci.append(dati)
    giro.annunci = annunci
    giro.momento = datetime.fromtimestamp(os.path.getmtime(percorso)).strftime("%d/%m/%Y alle %H:%M")
    giro.riepilogo = {
        "totale": len(annunci),
        "nuovi": sum(1 for a in annunci if a["nuovo"]),
        "doppioni": sum(1 for a in annunci if a.get("doppione_di")),
        "confronto": any(a["nuovo"] for a in annunci),
        "csv": "ultimo.csv",
        "report": "ultimo.html",
    }


# --------------------------------------------------------------------------
# Configurazione
# --------------------------------------------------------------------------

def leggi_config() -> dict:
    with open(CONFIG, encoding="utf-8") as file:
        return json.load(file)


def salva_config(config: dict) -> None:
    os.makedirs(os.path.dirname(CONFIG) or ".", exist_ok=True)
    with open(CONFIG, "w", encoding="utf-8") as file:
        json.dump(config, file, ensure_ascii=False, indent=2)


def config_da_modulo(modulo: dict) -> dict:
    """Dai campi della pagina alla forma di config.json, senza fidarsi."""
    config = leggi_config()
    zona = config["zona"]
    zona["etichetta"] = (modulo.get("etichetta") or "").strip() or "zona senza nome"
    zona["autoscout"]["cap"] = "".join(c for c in str(modulo.get("cap", "")) if c.isdigit())[:5]
    zona["autoscout"]["raggio_km"] = max(1, min(500, int(modulo.get("raggio_km") or 50)))
    zona["subito"]["regione"] = (modulo.get("regione") or "").strip() or zona["subito"]["regione"]
    # Se la pagina non ha mandato le province (elenco non caricato) teniamo
    # quelle che ci sono: una lista vuota per sbaglio allargherebbe la ricerca
    # a tutta la regione senza che nessuno l'abbia chiesto.
    if "province" in modulo:
        zona["subito"]["province"] = [p for p in modulo["province"] if p]

    fasce = []
    for coppia in modulo.get("fasce_prezzo") or []:
        minimo = int(coppia[0] or 0)
        massimo = None if coppia[1] in (None, "", 0) else int(coppia[1])
        fasce.append([minimo, massimo])
    if fasce:
        config["fasce_prezzo"] = fasce

    filtri = config.setdefault("filtri", {})
    for campo in ("anno_min", "km_max", "prezzo_min_credibile"):
        if modulo.get(campo) not in (None, ""):
            filtri[campo] = int(modulo[campo])
    if isinstance(modulo.get("escludi_parole"), list):
        filtri["escludi_parole"] = [p.strip() for p in modulo["escludi_parole"] if p.strip()]
    filtri["scarta_incongruenti"] = bool(modulo.get("scarta_incongruenti", True))

    limiti = config.setdefault("limiti", {})
    limiti["max_annunci_per_fascia"] = max(10, min(1000, int(modulo.get("max_annunci_per_fascia") or 300)))
    limiti["pausa_secondi"] = max(1.0, float(modulo.get("pausa_secondi") or 1.5))
    return config


# --------------------------------------------------------------------------
# Organizzazione: stato di lavorazione per annuncio
# --------------------------------------------------------------------------

_blocco_org = threading.Lock()


def leggi_organizzazione() -> dict:
    """La mappa URL → {contattato, chi, stato}. File mancante o rotto: mappa vuota."""
    with _blocco_org:
        try:
            with open(ORGANIZZAZIONE, encoding="utf-8") as file:
                dati = json.load(file)
            return dati if isinstance(dati, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}


def salva_voce_organizzazione(url: str, voce: dict) -> None:
    """Aggiorna la riga di un annuncio. Se non c'è più nulla da tenere la
    togliamo, così il file non si riempie di voci vuote."""
    with _blocco_org:
        try:
            with open(ORGANIZZAZIONE, encoding="utf-8") as file:
                dati = json.load(file)
            if not isinstance(dati, dict):
                dati = {}
        except (FileNotFoundError, json.JSONDecodeError):
            dati = {}

        pulita = {
            "contattato": bool(voce.get("contattato")),
            "chi": str(voce.get("chi") or "").strip()[:80],
            "stato": str(voce.get("stato") or "").strip()[:40],
        }
        if pulita["contattato"] or pulita["chi"] or pulita["stato"]:
            dati[url] = pulita
        else:
            dati.pop(url, None)

        os.makedirs(DATI, exist_ok=True)
        with open(ORGANIZZAZIONE, "w", encoding="utf-8") as file:
            json.dump(dati, file, ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------
# Server
# --------------------------------------------------------------------------

class Gestore(BaseHTTPRequestHandler):
    server_version = "RicercaAuto"

    def log_message(self, formato: str, *argomenti) -> None:
        pass  # niente rumore nel terminale

    # -- accesso ------------------------------------------------------------

    def _autenticato(self) -> bool:
        """Login utente+password (HTTP Basic). Se non ci sono utenti configurati
        (uso in locale) non chiede niente. Il confronto è a tempo costante per
        non far trapelare la password un carattere alla volta."""
        if not UTENTI:
            return True
        intestazione = self.headers.get("Authorization", "")
        if intestazione.startswith("Basic "):
            try:
                decodificato = base64.b64decode(intestazione[6:]).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                decodificato = ""
            utente, _, password = decodificato.partition(":")
            attesa = UTENTI.get(utente)
            if attesa is not None and hmac.compare_digest(password, attesa):
                return True
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="CRM Link Motors", charset="UTF-8"')
        self.send_header("Content-Length", "0")
        self.end_headers()
        return False

    # -- risposte -----------------------------------------------------------

    def _json(self, dati: Any, codice: int = 200) -> None:
        corpo = json.dumps(dati, ensure_ascii=False).encode("utf-8")
        self.send_response(codice)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _file(self, percorso: str, scarica: bool = False) -> None:
        if not os.path.isfile(percorso):
            self._json({"errore": "non trovato"}, 404)
            return
        with open(percorso, "rb") as file:
            corpo = file.read()
        self.send_response(200)
        self.send_header("Content-Type", TIPI.get(os.path.splitext(percorso)[1], "application/octet-stream"))
        if scarica:
            self.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(percorso)}"')
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    # -- rotte --------------------------------------------------------------

    def _fasce(self, config: dict) -> list[str]:
        """Le etichette le decide Python: se le ricostruisse anche il browser,
        prima o poi divergerebbero (e le fasce non si allineerebbero più)."""
        return [cerca.etichetta_fascia(mi or 0, ma) for mi, ma in config["fasce_prezzo"]]

    def do_GET(self) -> None:
        if not self._autenticato():
            return
        percorso = urllib.parse.urlparse(self.path).path

        if percorso in ("/", "/index.html"):
            return self._file(os.path.join(WEB, "index.html"))
        if percorso in ("/app.js", "/stile.css"):
            return self._file(os.path.join(WEB, percorso.lstrip("/")))

        if percorso == "/api/avvio":
            try:
                zone = subito.elenco_zone()
            except ErroreFonte as errore:
                zone = []
                giro.scrivi(f"Elenco province non caricato: {errore}")
            config = leggi_config()
            return self._json({
                "config": config,
                "fasce": self._fasce(config),
                "zone": zone,
                "stato": giro.istantanea(),
            })

        if percorso == "/api/stato":
            return self._json(giro.istantanea())

        if percorso == "/api/annunci":
            with giro.blocco:
                return self._json({
                    "annunci": giro.annunci,
                    "momento": giro.momento,
                    "fasce": self._fasce(leggi_config()),
                })

        if percorso == "/api/organizzazione":
            return self._json(leggi_organizzazione())

        if percorso.startswith("/scarica/"):
            nome = os.path.basename(urllib.parse.unquote(percorso[len("/scarica/"):]))
            return self._file(os.path.join(USCITA, nome), scarica=nome.endswith(".csv"))

        self._json({"errore": "rotta sconosciuta"}, 404)

    def do_POST(self) -> None:
        if not self._autenticato():
            return
        percorso = urllib.parse.urlparse(self.path).path
        lunghezza = int(self.headers.get("Content-Length") or 0)
        try:
            corpo = json.loads(self.rfile.read(lunghezza) or b"{}")
        except json.JSONDecodeError:
            return self._json({"errore": "richiesta non valida"}, 400)

        if percorso == "/api/cerca":
            try:
                config = config_da_modulo(corpo)
            except (ValueError, TypeError, KeyError) as errore:
                return self._json({"errore": f"impostazioni non valide: {errore}"}, 400)
            salva_config(config)
            massimo = 20 if corpo.get("prova") else config["limiti"]["max_annunci_per_fascia"]
            solo = corpo.get("solo") or None
            if not giro.avvia(config, massimo, solo):
                return self._json({"errore": "c'è già una ricerca in corso"}, 409)
            return self._json({"avviata": True})

        if percorso == "/api/organizzazione":
            url = str(corpo.get("url") or "").strip()
            if not url:
                return self._json({"errore": "manca l'URL dell'annuncio"}, 400)
            salva_voce_organizzazione(url, corpo)
            return self._json({"ok": True})

        if percorso == "/api/impostazioni":
            try:
                salva_config(config_da_modulo(corpo))
            except (ValueError, TypeError, KeyError) as errore:
                return self._json({"errore": f"impostazioni non valide: {errore}"}, 400)
            return self._json({"salvate": True})

        self._json({"errore": "rotta sconosciuta"}, 404)


def _prepara_dati() -> None:
    """Crea le cartelle dati e, se si parte su un disco vuoto (es. il disco
    persistente di Render al primo avvio), copia lì il config di partenza dal
    repo così l'app trova le impostazioni."""
    os.makedirs(USCITA, exist_ok=True)
    os.makedirs(DATI, exist_ok=True)
    config_repo = os.path.join(QUI, "config.json")
    if not os.path.exists(CONFIG) and os.path.exists(config_repo):
        shutil.copyfile(config_repo, CONFIG)


def main() -> int:
    _prepara_dati()
    carica_ultimo()
    # In cloud (Render fornisce PORT) si ascolta su tutte le interfacce e non si
    # apre nessun browser; in locale si resta su 127.0.0.1 come prima.
    in_cloud = bool(os.environ.get("PORT"))
    host = os.environ.get("HOST") or ("0.0.0.0" if in_cloud else "127.0.0.1")
    server = ThreadingHTTPServer((host, PORTA), Gestore)
    print(f"Ricerca auto — in ascolto su {host}:{PORTA}")
    if UTENTI:
        print(f"Login attivo per: {', '.join(UTENTI)}")
    print("Per fermarlo: Ctrl+C")
    if not in_cloud and "--no-apri" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(f"http://localhost:{PORTA}")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nChiuso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
