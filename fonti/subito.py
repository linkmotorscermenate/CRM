"""Subito.it — il sito parla con la propria API JSON (hades), che espone un
filtro nativo "solo privati" (advt=0,2). Usiamo quella, non l'HTML."""

from __future__ import annotations

import json
import os
import urllib.parse
from typing import Iterator, Optional

from .comune import Annuncio, ErroreFonte, carica_json, normalizza, scarica, solo_numero

NOME = "Subito"
API = "https://hades.subito.it/v1"
CATEGORIA_AUTO = "2"
SOLO_PRIVATI = "0,2"
PER_PAGINA = 50

_CACHE_GEO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dati", "geo_subito.json")


# --------------------------------------------------------------------------
# Geografia: Subito ragiona per regione / provincia / comune, non per raggio.
# --------------------------------------------------------------------------

def _valori(percorso: str) -> list[dict]:
    return carica_json(scarica(f"{API}{percorso}", accetta_json=True), f"Subito {percorso}")["values"]


FORMATO_GEO = 2  # cambiando i campi della cache, si alza: i vecchi file si rifanno


def _carica_geo() -> dict:
    """Elenco regioni + province, scaricato una volta sola e messo in cache."""
    if os.path.exists(_CACHE_GEO):
        with open(_CACHE_GEO, encoding="utf-8") as file:
            salvato = json.load(file)
        if salvato.get("formato") == FORMATO_GEO:
            return salvato

    geo = {"formato": FORMATO_GEO, "regioni": {}, "province": {}}
    for regione in _valori("/geo/regions"):
        geo["regioni"][normalizza(regione["value"])] = regione["key"]
        for provincia in _valori(f"/geo/regions/{regione['key']}/cities"):
            voce = {
                "id": provincia["key"],
                "regione_id": regione["key"],
                "nome": provincia["value"],
                "sigla": provincia.get("short_name", ""),
            }
            geo["province"][normalizza(provincia["value"])] = voce
            if provincia.get("short_name"):
                geo["province"][normalizza(provincia["short_name"])] = voce

    os.makedirs(os.path.dirname(_CACHE_GEO), exist_ok=True)
    with open(_CACHE_GEO, "w", encoding="utf-8") as file:
        json.dump(geo, file, ensure_ascii=False, indent=1)
    return geo


def elenco_zone() -> list[dict]:
    """Regioni con le loro province, per i menù del sito."""
    geo = _carica_geo()
    per_regione: dict[str, dict] = {}
    for id_regione in geo["regioni"].values():
        per_regione[id_regione] = {"id": id_regione, "nome": "", "province": {}}
    for nome_regione, id_regione in geo["regioni"].items():
        per_regione[id_regione]["nome"] = nome_regione.title()
    for voce in geo["province"].values():
        regione = per_regione.get(voce["regione_id"])
        if regione:
            # La sigla serve al sito per riconoscere le province salvate come
            # "MI" e non come "Milano".
            regione["province"][voce["id"]] = {
                "nome": voce["nome"],
                "sigla": voce.get("sigla", ""),
            }

    elenco = []
    for regione in per_regione.values():
        elenco.append(
            {
                "nome": regione["nome"],
                "province": sorted(regione["province"].values(), key=lambda p: p["nome"]),
            }
        )
    return sorted(elenco, key=lambda r: r["nome"])


def risolvi_zona(zona: dict) -> list[dict]:
    """Traduce nomi ("Lombardia", "MI", "Monza e della Brianza") in id Subito.

    Restituisce una lista di ricerche da fare: una per provincia indicata,
    oppure una sola sulla regione se non è stata indicata nessuna provincia.
    """
    geo = _carica_geo()
    nome_regione = normalizza(zona.get("regione", ""))
    if nome_regione and nome_regione not in geo["regioni"]:
        raise ErroreFonte(f"Subito: regione '{zona.get('regione')}' non riconosciuta")
    id_regione = geo["regioni"].get(nome_regione)

    ricerche = []
    for sigla in zona.get("province") or []:
        voce = geo["province"].get(normalizza(sigla))
        if not voce:
            raise ErroreFonte(f"Subito: provincia '{sigla}' non riconosciuta")
        ricerche.append({"etichetta": voce["nome"], "r": voce["regione_id"], "ci": voce["id"]})

    if not ricerche:
        if not id_regione:
            raise ErroreFonte("Subito: indicare almeno 'regione' o 'province' nella zona")
        ricerche.append({"etichetta": zona["regione"], "r": id_regione})
    return ricerche


# --------------------------------------------------------------------------
# Ricerca
# --------------------------------------------------------------------------

def _caratteristiche(grezzo: dict) -> dict[str, dict]:
    """Da lista di features a mappa uri -> primo valore."""
    mappa = {}
    for caratteristica in grezzo.get("features") or []:
        valori = caratteristica.get("values") or []
        if valori:
            mappa[caratteristica["uri"]] = valori[0]
    return mappa


def _auto(grezzo: dict) -> dict[str, str]:
    """Il pacchetto /car contiene marca (level 0), modello (1), versione (2)."""
    parti = {0: "", 1: "", 2: ""}
    for caratteristica in grezzo.get("features") or []:
        if caratteristica.get("uri") == "/car":
            for valore in caratteristica.get("values") or []:
                livello = valore.get("level")
                if livello in parti:
                    # Per il modello preferiamo il gruppo ("Panda" invece di
                    # "Panda 3ª serie"): rende confrontabili i due siti.
                    parti[livello] = valore.get("group_label") or valore.get("value") or ""
    return {"marca": parti[0].title(), "modello": parti[1], "versione": parti[2]}


def _converti(grezzo: dict) -> Annuncio:
    caratteristiche = _caratteristiche(grezzo)
    geo = grezzo.get("geo") or {}
    auto = _auto(grezzo)
    return Annuncio(
        fonte=NOME,
        id=(grezzo.get("urn") or "").split(":")[-1],
        titolo=grezzo.get("subject") or "",
        marca=auto["marca"],
        modello=auto["modello"],
        versione=auto["versione"],
        prezzo=solo_numero(caratteristiche.get("/price", {}).get("key")),
        anno=solo_numero(caratteristiche.get("/year", {}).get("value")),
        km=solo_numero(caratteristiche.get("/mileage_scalar", {}).get("key")),
        alimentazione=caratteristiche.get("/fuel", {}).get("value", ""),
        cambio=caratteristiche.get("/gearbox", {}).get("value", ""),
        comune=(geo.get("town") or {}).get("value", ""),
        provincia=(geo.get("city") or {}).get("short_name", ""),
        pubblicato=(grezzo.get("dates") or {}).get("display", ""),
        url=(grezzo.get("urls") or {}).get("default", ""),
    )


def cerca(
    ricerca_zona: dict,
    prezzo_min: Optional[int],
    prezzo_max: Optional[int],
    filtri: dict,
    massimo: int,
) -> Iterator[Annuncio]:
    """Annunci di privati in una provincia/regione, dentro una fascia di prezzo."""
    parametri = {
        "c": CATEGORIA_AUTO,
        "t": "s",              # in vendita
        "advt": SOLO_PRIVATI,
        "sort": "datedesc",
        "lim": PER_PAGINA,
        "r": ricerca_zona["r"],
    }
    if ricerca_zona.get("ci"):
        parametri["ci"] = ricerca_zona["ci"]
    if prezzo_min:
        parametri["ps"] = prezzo_min
    if prezzo_max:
        parametri["pe"] = prezzo_max
    if filtri.get("anno_min"):
        parametri["ys"] = filtri["anno_min"]
    if filtri.get("km_max"):
        parametri["me"] = filtri["km_max"]

    raccolti = 0
    inizio = 0
    while raccolti < massimo:
        parametri["start"] = inizio
        risposta = carica_json(
            scarica(f"{API}/search/items?{urllib.parse.urlencode(parametri)}", accetta_json=True),
            "Subito ricerca",
        )
        annunci = risposta.get("ads") or []
        if not annunci:
            return
        for grezzo in annunci:
            # advt filtra già lato Subito; ricontrolliamo sul singolo annuncio.
            if (grezzo.get("advertiser") or {}).get("company"):
                continue
            yield _converti(grezzo)
            raccolti += 1
            if raccolti >= massimo:
                return
        if len(annunci) < PER_PAGINA:
            return
        inizio += PER_PAGINA
