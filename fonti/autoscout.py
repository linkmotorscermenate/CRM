"""AutoScout24.it — le pagine di ricerca sono Next.js: gli annunci stanno già
strutturati dentro lo <script id="__NEXT_DATA__">, non serve leggere l'HTML."""

from __future__ import annotations

import re
import urllib.parse
from typing import Iterator, Optional

from .comune import Annuncio, ErroreFonte, carica_json, scarica, solo_numero

NOME = "AutoScout24"
BASE = "https://www.autoscout24.it/lst"
PER_PAGINA = 20
_NEXT_DATA = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)


def _estrai_dati(html: str) -> dict:
    trovato = _NEXT_DATA.search(html)
    if not trovato:
        raise ErroreFonte(
            "AutoScout24: __NEXT_DATA__ non trovato (pagina cambiata o richiesta bloccata)"
        )
    return carica_json(trovato.group(1), "AutoScout24")["props"]["pageProps"]


def _anno(annuncio: dict) -> Optional[int]:
    # "01-2023" nel blocco tracking, altrimenti "01/2023" fra i dettagli.
    prima_immatricolazione = (annuncio.get("tracking") or {}).get("firstRegistration")
    if prima_immatricolazione:
        cifre = re.search(r"(\d{4})", prima_immatricolazione)
        if cifre:
            return int(cifre.group(1))
    for dettaglio in annuncio.get("vehicleDetails") or []:
        if dettaglio.get("ariaLabel") == "Anno":
            cifre = re.search(r"(\d{4})", dettaglio.get("data") or "")
            if cifre:
                return int(cifre.group(1))
    return None


def _telefono(annuncio: dict) -> str:
    for numero in (annuncio.get("seller") or {}).get("phones") or []:
        if numero.get("callTo"):
            return numero["callTo"]
    return ""


def _converti(annuncio: dict) -> Annuncio:
    veicolo = annuncio.get("vehicle") or {}
    luogo = annuncio.get("location") or {}
    prezzo = annuncio.get("price") or {}
    percorso = annuncio.get("url") or ""
    return Annuncio(
        fonte=NOME,
        id=annuncio.get("id") or "",
        titolo=" ".join(
            p for p in (veicolo.get("make"), veicolo.get("model"), veicolo.get("modelVersionInput")) if p
        ).strip(),
        marca=veicolo.get("make") or "",
        modello=veicolo.get("model") or "",
        versione=veicolo.get("modelVersionInput") or veicolo.get("variant") or "",
        prezzo=solo_numero(prezzo.get("priceRaw")),
        anno=_anno(annuncio),
        km=solo_numero(veicolo.get("mileageInKm")),
        alimentazione=veicolo.get("fuel") or "",
        cambio=veicolo.get("transmission") or "",
        comune=luogo.get("city") or "",
        cap=luogo.get("zip") or "",
        telefono=_telefono(annuncio),
        url=urllib.parse.urljoin("https://www.autoscout24.it", percorso) if percorso else "",
    )


def _distanza_km(annuncio: dict) -> Optional[int]:
    """Km dal centro della ricerca; None se AutoScout non l'ha calcolata."""
    return solo_numero((annuncio.get("location") or {}).get("distanceToSearchLocationInKm"))


def cerca(
    zona: dict,
    prezzo_min: Optional[int],
    prezzo_max: Optional[int],
    filtri: dict,
    massimo: int,
) -> Iterator[Annuncio]:
    """Annunci di privati nel raggio impostato, dentro una fascia di prezzo."""
    raggio = zona["raggio_km"]
    parametri = {
        "atype": "C",           # automobili
        "cy": "I",              # Italia
        "custtype": "P",        # solo privati
        "ustate": "N,U",
        "sort": "age",
        "desc": "1",            # dal più recente
        "zip": zona["cap"],
        "zipr": raggio,
    }
    if prezzo_min:
        parametri["pricefrom"] = prezzo_min
    if prezzo_max:
        parametri["priceto"] = prezzo_max
    if filtri.get("anno_min"):
        parametri["fregfrom"] = filtri["anno_min"]
    if filtri.get("km_max"):
        parametri["kmto"] = filtri["km_max"]

    raccolti = 0
    pagina = 1
    while raccolti < massimo:
        parametri["page"] = pagina
        dati = _estrai_dati(scarica(f"{BASE}?{urllib.parse.urlencode(parametri)}"))
        annunci = dati.get("listings") or []
        if not annunci:
            return

        # Se il CAP non viene riconosciuto, AutoScout scarta silenziosamente il
        # filtro zona e restituisce annunci da tutta Italia. In quel caso gli
        # annunci non hanno la distanza dal centro ricerca; quando invece il
        # raggio è attivo, ognuno la porta. Se sulla prima pagina nessun annuncio
        # ha una distanza, ci fermiamo e lo segnaliamo, invece di riempire il
        # report di auto della Calabria.
        if pagina == 1 and all(_distanza_km(a) is None for a in annunci):
            raise ErroreFonte(
                f"AutoScout24: il CAP {zona['cap']} non è stato riconosciuto, "
                "il filtro raggio è stato ignorato (risultati da tutta Italia). "
                "Controlla il CAP nella configurazione della zona."
            )
        for grezzo in annunci:
            # Il filtro custtype è già lato sito, ma non ci fidiamo a scatola chiusa.
            if (grezzo.get("seller") or {}).get("type") != "PrivateSeller":
                continue
            # AutoScout accoda anche annunci "un po' più lontani" oltre il raggio
            # (relaxed filters): li scartiamo per restare dentro la zona richiesta.
            distanza = _distanza_km(grezzo)
            if distanza is not None and distanza > raggio:
                continue
            yield _converti(grezzo)
            raccolti += 1
            if raccolti >= massimo:
                return
        if len(annunci) < PER_PAGINA:
            return
        pagina += 1
