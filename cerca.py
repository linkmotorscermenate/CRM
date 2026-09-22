#!/usr/bin/env python3
"""Ricerca auto di privati su AutoScout24 e Subito, divisa per fascia di prezzo.

Uso:
    python3 cerca.py                    # usa config.json
    python3 cerca.py --config zona-bs.json
    python3 cerca.py --solo subito      # una fonte sola
    python3 cerca.py --prova            # giro veloce: 20 annunci per fascia
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

from fonti import autoscout, comune, subito
from fonti.comune import Annuncio, ErroreFonte
from report import scrivi_report

QUI = os.path.dirname(os.path.abspath(__file__))

COLONNE = [
    ("nuovo", "Nuovo"),
    ("fascia", "Fascia"),
    ("fonte", "Fonte"),
    ("marca", "Marca"),
    ("modello", "Modello"),
    ("versione", "Versione"),
    ("prezzo", "Prezzo"),
    ("anno", "Anno"),
    ("km", "Km"),
    ("alimentazione", "Alimentazione"),
    ("cambio", "Cambio"),
    ("comune", "Comune"),
    ("provincia", "Prov"),
    ("cap", "CAP"),
    ("telefono", "Telefono"),
    ("pubblicato", "Pubblicato"),
    ("url", "Link"),
    ("doppione_di", "Doppione di"),
    ("visto_la_prima_volta", "Visto dal"),
]


# --------------------------------------------------------------------------
# Fasce di prezzo
# --------------------------------------------------------------------------

def etichetta_fascia(minimo: Optional[int], massimo: Optional[int]) -> str:
    if not minimo and massimo:
        return f"fino a {massimo:,} €".replace(",", ".")
    if minimo and not massimo:
        return f"oltre {minimo:,} €".replace(",", ".")
    if not minimo and not massimo:
        return "qualsiasi prezzo"
    return f"{minimo:,} - {massimo:,} €".replace(",", ".")


def assegna_fascia(prezzo: Optional[int], fasce: list) -> str:
    """Le fasce sono semiaperte [min, max): un'auto sta in una sola fascia."""
    if prezzo is None:
        return "prezzo non indicato"
    for minimo, massimo in fasce:
        minimo = minimo or 0
        if prezzo >= minimo and (massimo is None or prezzo < massimo):
            return etichetta_fascia(minimo, massimo)
    return "fuori fascia"


# --------------------------------------------------------------------------
# Filtri lato nostro
# --------------------------------------------------------------------------

def da_scartare(annuncio: Annuncio, filtri: dict) -> Optional[str]:
    """Motivo per cui l'annuncio non ci interessa, oppure None se va tenuto."""
    testo = comune.normalizza(f"{annuncio.titolo} {annuncio.versione}")
    for parola in filtri.get("escludi_parole") or []:
        # Parole intere: "rate" non deve far fuori "moderate".
        if re.search(rf"\b{re.escape(comune.normalizza(parola))}\b", testo):
            return f"parola esclusa: {parola}"
    if filtri.get("anno_min") and annuncio.anno and annuncio.anno < filtri["anno_min"]:
        return "troppo vecchia"
    if filtri.get("km_max") and annuncio.km and annuncio.km > filtri["km_max"]:
        return "troppi km"
    # Sotto una certa cifra non sono auto in vendita: sono noleggi mascherati,
    # acconti, o esche. Meglio non farle arrivare in lista.
    soglia = filtri.get("prezzo_min_credibile")
    if soglia and annuncio.prezzo is not None and annuncio.prezzo < soglia:
        return "prezzo non credibile"
    # Auto recente, pochi km e prezzo da utilitaria sfasciata: non esiste. È un
    # canone di noleggio, un acconto, o un'esca per farsi chiamare.
    if (
        filtri.get("scarta_incongruenti", True)
        and annuncio.prezzo is not None
        and annuncio.prezzo < 4000
        and annuncio.anno
        and annuncio.anno >= datetime.now().year - 6
        and annuncio.km is not None
        and annuncio.km < 40000
    ):
        return "prezzo incompatibile con anno e km"
    return None


def segna_novita(annunci: list[Annuncio], oggi: str, giorni_memoria: int = 120) -> bool:
    """Marca come 'nuovi' gli annunci mai visti nei giri precedenti.

    Restituisce False se è il primo giro in assoluto: lì sarebbe tutto nuovo e
    dirlo non aggiungerebbe niente.
    """
    percorso = os.path.join(QUI, "dati", "storico.json")
    storico: dict[str, str] = {}
    if os.path.exists(percorso):
        with open(percorso, encoding="utf-8") as file:
            storico = json.load(file)
    primo_giro = not storico

    for annuncio in annunci:
        chiave = f"{annuncio.fonte}:{annuncio.id}"
        prima_volta = storico.get(chiave)
        annuncio.nuovo = prima_volta is None and not primo_giro
        annuncio.visto_la_prima_volta = prima_volta or oggi
        storico[chiave] = annuncio.visto_la_prima_volta

    # Gli annunci vecchi vengono ritirati: teniamo la memoria corta.
    limite = (datetime.now() - timedelta(days=giorni_memoria)).strftime("%Y-%m-%d")
    storico = {k: v for k, v in storico.items() if v >= limite}

    os.makedirs(os.path.dirname(percorso), exist_ok=True)
    with open(percorso, "w", encoding="utf-8") as file:
        json.dump(storico, file)
    return not primo_giro


def segna_doppioni(annunci: list[Annuncio]) -> int:
    """Marca gli annunci che sembrano la stessa auto pubblicata su tutti e due
    i siti. Non li cancella: li etichetta, così si vede il doppio canale."""
    visti: dict[tuple, Annuncio] = {}
    doppioni = 0
    for annuncio in annunci:
        if annuncio.prezzo is None or not annuncio.marca:
            continue
        chiave = annuncio.chiave_confronto
        primo = visti.get(chiave)
        if primo is None:
            visti[chiave] = annuncio
        elif primo.fonte != annuncio.fonte:
            annuncio.doppione_di = f"{primo.fonte} {primo.id}"
            doppioni += 1
    return doppioni


# --------------------------------------------------------------------------
# Raccolta
# --------------------------------------------------------------------------

def raccogli(
    config: dict,
    solo: Optional[str],
    massimo_fascia: int,
    avanzamento: Callable[[str], None] = print,
) -> tuple[list[Annuncio], list[str]]:
    """`avanzamento` riceve una riga alla volta: da terminale è print, dal sito
    è la funzione che accoda i messaggi da mostrare in pagina."""
    zona = config["zona"]
    filtri = config.get("filtri") or {}
    fasce = config["fasce_prezzo"]
    annunci: list[Annuncio] = []
    avvisi: list[str] = []
    gia_visti: set[tuple[str, str]] = set()
    scartati = 0

    ricerche_subito = []
    if solo in (None, "subito"):
        try:
            ricerche_subito = subito.risolvi_zona(zona["subito"])
        except ErroreFonte as errore:
            avvisi.append(str(errore))

    for minimo, massimo in fasce:
        minimo = minimo or 0
        nome_fascia = etichetta_fascia(minimo, massimo)
        avanzamento(f"▸ fascia {nome_fascia}")

        compiti = []
        if solo in (None, "autoscout"):
            compiti.append(
                (
                    f"  AutoScout24 ({zona['autoscout']['cap']}, {zona['autoscout']['raggio_km']} km)",
                    lambda mi=minimo, ma=massimo: autoscout.cerca(
                        zona["autoscout"], mi, ma, filtri, massimo_fascia
                    ),
                )
            )
        for ricerca in ricerche_subito:
            compiti.append(
                (
                    f"  Subito ({ricerca['etichetta']})",
                    lambda r=ricerca, mi=minimo, ma=massimo: subito.cerca(
                        r, mi, ma, filtri, massimo_fascia
                    ),
                )
            )

        for descrizione, azione in compiti:
            presi = 0
            try:
                for annuncio in azione():
                    if (annuncio.fonte, annuncio.id) in gia_visti:
                        continue
                    gia_visti.add((annuncio.fonte, annuncio.id))
                    motivo = da_scartare(annuncio, filtri)
                    if motivo:
                        scartati += 1
                        continue
                    annuncio.fascia = assegna_fascia(annuncio.prezzo, fasce)
                    annunci.append(annuncio)
                    presi += 1
                avanzamento(f"{descrizione}: {presi}")
            except ErroreFonte as errore:
                avviso = f"{descrizione.strip()}: {errore}"
                avvisi.append(avviso)
                avanzamento(f"{descrizione}: ERRORE — {errore}")

    if scartati:
        avanzamento(f"{scartati} annunci scartati dai filtri")
    return annunci, avvisi


# --------------------------------------------------------------------------
# Salvataggio
# --------------------------------------------------------------------------

def scrivi_csv(percorso: str, annunci: list[Annuncio]) -> None:
    # utf-8-sig + ';' così Excel in italiano lo apre già incolonnato.
    with open(percorso, "w", encoding="utf-8-sig", newline="") as file:
        scrittore = csv.writer(file, delimiter=";")
        scrittore.writerow([intestazione for _, intestazione in COLONNE])
        for annuncio in annunci:
            riga = annuncio.dizionario()
            riga["nuovo"] = "NUOVO" if annuncio.nuovo else ""
            scrittore.writerow([riga.get(campo, "") for campo, _ in COLONNE])


def avvisa(titolo: str, messaggio: str) -> None:
    """Notifica del Mac: serve quando il giro parte da solo la mattina."""
    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                f'display notification "{messaggio}" with title "{titolo}"',
            ],
            check=False,
            capture_output=True,
            timeout=10,
        )
    except Exception:
        pass  # una notifica mancata non deve far fallire la ricerca


def esegui(
    config: dict,
    solo: Optional[str] = None,
    massimo_fascia: int = 300,
    avanzamento: Callable[[str], None] = print,
    notifica: bool = False,
) -> dict:
    """Un giro completo: cerca, confronta, salva CSV e report.

    È il motore usato sia da `python3 cerca.py` sia dal sito (`server.py`).
    """
    comune.PAUSA_SECONDI = float((config.get("limiti") or {}).get("pausa_secondi", 1.5))
    inizio = datetime.now()

    annunci, avvisi = raccogli(config, solo, massimo_fascia, avanzamento)
    doppioni = segna_doppioni(annunci)
    confronto = segna_novita(annunci, inizio.strftime("%Y-%m-%d"))
    nuovi = sum(1 for a in annunci if a.nuovo)
    annunci.sort(key=lambda a: (a.prezzo is None, a.prezzo or 0))

    cartella = os.path.join(QUI, (config.get("output") or {}).get("cartella", "output"))
    os.makedirs(cartella, exist_ok=True)
    marca_tempo = inizio.strftime("%Y-%m-%d_%H%M")
    percorso_csv = os.path.join(cartella, f"auto_privati_{marca_tempo}.csv")
    percorso_html = os.path.join(cartella, f"auto_privati_{marca_tempo}.html")

    scrivi_csv(percorso_csv, annunci)
    scrivi_report(
        percorso_html,
        annunci,
        config,
        [etichetta_fascia(mi or 0, ma) for mi, ma in config["fasce_prezzo"]],
        avvisi,
        inizio,
        confronto,
    )
    # Copia a nome fisso: comoda da mettere nei preferiti, punta sempre all'ultimo giro.
    for sorgente, nome in ((percorso_csv, "ultimo.csv"), (percorso_html, "ultimo.html")):
        shutil.copyfile(sorgente, os.path.join(cartella, nome))

    if notifica:
        titolo = f"{nuovi} auto nuove" if confronto else f"{len(annunci)} auto trovate"
        dettaglio = config["zona"].get("etichetta", "")
        if avvisi:
            dettaglio += f" — {len(avvisi)} ricerche non riuscite"
        avvisa(titolo, dettaglio.strip(" —"))

    return {
        "annunci": annunci,
        "avvisi": avvisi,
        "doppioni": doppioni,
        "nuovi": nuovi,
        "confronto": confronto,
        "inizio": inizio,
        "csv": percorso_csv,
        "html": percorso_html,
    }


def main() -> int:
    argomenti = argparse.ArgumentParser(description=__doc__)
    argomenti.add_argument("--config", default=os.path.join(QUI, "config.json"))
    argomenti.add_argument("--solo", choices=["autoscout", "subito"])
    argomenti.add_argument("--prova", action="store_true", help="giro veloce di verifica")
    argomenti.add_argument("--no-apri", action="store_true", help="non aprire il report")
    argomenti.add_argument(
        "--notifica", action="store_true", help="avvisa con una notifica del Mac a fine giro"
    )
    opzioni = argomenti.parse_args()

    with open(opzioni.config, encoding="utf-8") as file:
        config = json.load(file)

    limiti = config.get("limiti") or {}
    massimo_fascia = 20 if opzioni.prova else int(limiti.get("max_annunci_per_fascia", 300))

    print(f"Zona: {config['zona'].get('etichetta', '(senza nome)')}")
    print(f"Fasce: {len(config['fasce_prezzo'])} · max {massimo_fascia} annunci per fascia e per fonte")

    esito = esegui(config, opzioni.solo, massimo_fascia, print, opzioni.notifica)

    riepilogo = (
        f"{len(esito['annunci'])} annunci di privati · "
        f"{esito['doppioni']} presenti su entrambi i siti"
    )
    if esito["confronto"]:
        riepilogo = f"{esito['nuovi']} nuovi · {riepilogo}"
    print(f"\n{riepilogo}")
    print(f"CSV    {esito['csv']}")
    print(f"Report {esito['html']}")

    if not opzioni.no_apri:
        # as_uri() perché su Windows il percorso è C:\... e "file://" davanti
        # non basta: ci vogliono le barre giuste e gli spazi sistemati.
        webbrowser.open(Path(esito["html"]).resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
