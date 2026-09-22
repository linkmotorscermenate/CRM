"""Genera il report HTML: quante auto per fascia, da quale sito, e l'elenco."""

from __future__ import annotations

import html
from collections import Counter, defaultdict
from datetime import datetime
from statistics import median
from typing import Optional

from fonti.comune import Annuncio

COLORE_FONTE = {"AutoScout24": "--serie-1", "Subito": "--serie-2"}

# Quante righe al massimo per tabella: oltre, il report diventa pesante da aprire
# e comunque l'elenco completo sta nel CSV.
MASSIMO_IN_PAGINA = 250

STILE = """
:root {
  color-scheme: light;
  --sfondo: #f4f3f0;
  --superficie: #fcfcfb;
  --bordo: #e2e0da;
  --testo: #0b0b0b;
  --testo-2: #52514e;
  --testo-3: #78776f;
  --serie-1: #2a78d6;
  --serie-2: #eb6834;
  --griglia: #eceae4;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --sfondo: #131312;
    --superficie: #1a1a19;
    --bordo: #333330;
    --testo: #ffffff;
    --testo-2: #c3c2b7;
    --testo-3: #94938a;
    --serie-1: #3987e5;
    --serie-2: #d95926;
    --griglia: #262624;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--sfondo);
  color: var(--testo);
  font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  -webkit-font-smoothing: antialiased;
}
.foglio { max-width: 1180px; margin: 0 auto; padding: 40px 24px 80px; }
header { margin-bottom: 32px; }
h1 { font-size: 26px; font-weight: 620; margin: 0 0 6px; letter-spacing: -0.01em; }
.sottotitolo { color: var(--testo-2); font-size: 14px; margin: 0; }
.riquadro {
  background: var(--superficie);
  border: 1px solid var(--bordo);
  border-radius: 12px;
  padding: 22px 24px;
  margin-bottom: 22px;
}
h2 { font-size: 15px; font-weight: 600; margin: 0 0 18px; letter-spacing: -0.005em; }

/* --- numeri in evidenza --- */
.numeri { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 1px;
          background: var(--bordo); border: 1px solid var(--bordo); border-radius: 12px;
          overflow: hidden; margin-bottom: 22px; }
.numero { background: var(--superficie); padding: 18px 20px; }
.numero .valore { font-size: 27px; font-weight: 600; letter-spacing: -0.02em;
                  font-variant-numeric: tabular-nums; white-space: nowrap; }
.numero .etichetta { color: var(--testo-2); font-size: 12.5px; margin-top: 3px; }

/* --- grafico a barre --- */
.legenda { display: flex; gap: 18px; margin-bottom: 20px; font-size: 13px; color: var(--testo-2); }
.legenda span { display: inline-flex; align-items: center; gap: 7px; }
.pastiglia { width: 11px; height: 11px; border-radius: 3px; }
.barre { display: grid; grid-template-columns: max-content 1fr max-content; gap: 10px 14px; align-items: center; }
.barra-nome { font-size: 13px; color: var(--testo-2); white-space: nowrap; font-variant-numeric: tabular-nums; }
.barra-pista { background: var(--griglia); border-radius: 4px; height: 22px; display: flex; overflow: hidden; }
.segmento { height: 100%; }
.segmento + .segmento { margin-left: 2px; }
.segmento:first-child { border-radius: 4px 0 0 4px; }
.segmento:last-child { border-radius: 0 4px 4px 0; }
.segmento:only-child { border-radius: 4px; }
.barra-valore { font-size: 13px; font-variant-numeric: tabular-nums; color: var(--testo); min-width: 3ch; text-align: right; }
.vuota { color: var(--testo-3); font-size: 13px; }

/* --- tabelle --- */
details { border-top: 1px solid var(--bordo); }
details:first-of-type { border-top: none; }
summary { cursor: pointer; padding: 14px 2px; font-size: 14px; font-weight: 550;
          display: flex; align-items: center; gap: 11px; list-style: none; }
summary::-webkit-details-marker { display: none; }
/* Freccetta disegnata coi bordi: nessun glifo, quindi nessuna sorpresa di font. */
summary::before {
  content: ""; flex: 0 0 auto;
  border-left: 5px solid var(--testo-3);
  border-top: 4px solid transparent;
  border-bottom: 4px solid transparent;
  transition: transform .15s;
}
details[open] summary::before { transform: rotate(90deg); }
summary > span:first-of-type { margin-right: auto; }
.conteggio { color: var(--testo-2); font-weight: 400; font-variant-numeric: tabular-nums; }
table { width: 100%; border-collapse: collapse; font-size: 13.5px; margin-bottom: 10px; }
th { text-align: left; font-weight: 550; color: var(--testo-2); font-size: 12px;
     text-transform: uppercase; letter-spacing: 0.04em; padding: 8px 10px;
     border-bottom: 1px solid var(--bordo); }
td { padding: 9px 10px; border-bottom: 1px solid var(--griglia); vertical-align: top; }
tr:last-child td { border-bottom: none; }
.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.fonte { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; color: var(--testo-2); }
a { color: var(--serie-1); text-decoration: none; }
a:hover { text-decoration: underline; }
.doppione { color: var(--testo-3); font-size: 11.5px; }
.targhetta { display: inline-block; background: var(--serie-1); color: #fff; font-size: 10.5px;
             font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;
             padding: 2px 6px; border-radius: 4px; margin-right: 7px; vertical-align: 1px; }
.avvisi { border-left: 3px solid var(--serie-2); padding: 12px 16px; background: var(--superficie);
          border-radius: 0 8px 8px 0; margin-bottom: 22px; font-size: 13.5px; color: var(--testo-2); }
footer { color: var(--testo-3); font-size: 12.5px; margin-top: 30px; line-height: 1.7; }
#suggerimento {
  position: fixed; pointer-events: none; opacity: 0; transition: opacity .12s;
  background: var(--testo); color: var(--sfondo); padding: 6px 9px; border-radius: 6px;
  font-size: 12.5px; white-space: nowrap; z-index: 10;
}
"""

SCRIPT = """
const box = document.getElementById('suggerimento');
document.querySelectorAll('[data-info]').forEach(el => {
  el.addEventListener('mouseenter', () => { box.textContent = el.dataset.info; box.style.opacity = 1; });
  el.addEventListener('mousemove', e => {
    box.style.left = (e.clientX + 14) + 'px';
    box.style.top = (e.clientY - 30) + 'px';
  });
  el.addEventListener('mouseleave', () => { box.style.opacity = 0; });
});
"""


def _euro(valore: Optional[float]) -> str:
    if valore is None:
        return "—"
    return f"{int(round(valore)):,} €".replace(",", ".")


def _km(valore: Optional[int]) -> str:
    if valore is None:
        return "—"
    return f"{valore:,}".replace(",", ".")


def _e(testo) -> str:
    return html.escape(str(testo or ""))


def _numeri(annunci: list[Annuncio], doppioni: int, confronto: bool) -> str:
    prezzi = [a.prezzo for a in annunci if a.prezzo]
    chilometraggi = [a.km for a in annunci if a.km]
    voci = []
    if confronto:
        voci.append((str(sum(1 for a in annunci if a.nuovo)), "nuovi dall'ultimo giro"))
    voci += [
        (str(len(annunci)), "annunci di privati"),
        (_euro(median(prezzi)) if prezzi else "—", "prezzo mediano"),
        (_km(int(median(chilometraggi))) + " km" if chilometraggi else "—", "km mediani"),
        (str(doppioni), "su entrambi i siti"),
    ]
    celle = "".join(
        f'<div class="numero"><div class="valore">{_e(v)}</div>'
        f'<div class="etichetta">{_e(e)}</div></div>'
        for v, e in voci
    )
    return f'<div class="numeri">{celle}</div>'


def _grafico(per_fascia: dict[str, Counter], ordine: list[str]) -> str:
    massimo = max((sum(c.values()) for c in per_fascia.values()), default=0)
    if not massimo:
        return '<p class="vuota">Nessun annuncio trovato.</p>'

    legenda = "".join(
        f'<span><i class="pastiglia" style="background:var({COLORE_FONTE[f]})"></i>{f}</span>'
        for f in ("AutoScout24", "Subito")
    )

    righe = []
    for fascia in ordine:
        conteggi = per_fascia.get(fascia, Counter())
        totale = sum(conteggi.values())
        segmenti = ""
        for fonte in ("AutoScout24", "Subito"):
            quantita = conteggi.get(fonte, 0)
            if not quantita:
                continue
            larghezza = quantita / massimo * 100
            segmenti += (
                f'<div class="segmento" style="width:{larghezza:.2f}%;'
                f'background:var({COLORE_FONTE[fonte]})" '
                f'data-info="{_e(fascia)} · {fonte}: {quantita}"></div>'
            )
        righe.append(
            f'<div class="barra-nome">{_e(fascia)}</div>'
            f'<div class="barra-pista">{segmenti}</div>'
            f'<div class="barra-valore">{totale}</div>'
        )
    return f'<div class="legenda">{legenda}</div><div class="barre">{"".join(righe)}</div>'


def _tabella(annunci: list[Annuncio], limite: Optional[int] = None) -> str:
    """Se gli annunci sono tanti, in pagina ne mettiamo una parte: il report
    deve restare leggero da aprire. L'elenco completo è nel CSV."""
    troncati = 0
    if limite and len(annunci) > limite:
        troncati = len(annunci) - limite
        annunci = annunci[:limite]

    righe = []
    for annuncio in annunci:
        nome = " ".join(p for p in (annuncio.marca, annuncio.modello) if p) or annuncio.titolo
        if annuncio.nuovo:
            nome = f'<span class="targhetta">nuovo</span>{_e(nome)}'
        else:
            nome = _e(nome)
        versione = f'<div class="doppione">{_e(annuncio.versione)}</div>' if annuncio.versione else ""
        doppio = '<div class="doppione">anche su ' + _e(annuncio.doppione_di.split()[0]) + "</div>" if annuncio.doppione_di else ""
        luogo = ", ".join(p for p in (annuncio.comune, annuncio.provincia) if p)
        contatto = _e(annuncio.telefono) if annuncio.telefono else ""
        righe.append(
            "<tr>"
            f"<td>{nome}{versione}{doppio}</td>"
            f'<td class="num">{_e(annuncio.anno or "—")}</td>'
            f'<td class="num">{_km(annuncio.km)}</td>'
            f'<td class="num">{_euro(annuncio.prezzo)}</td>'
            f"<td>{_e(luogo)}</td>"
            f"<td>{contatto}</td>"
            f'<td><span class="fonte"><i class="pastiglia" style="background:var({COLORE_FONTE.get(annuncio.fonte, "--testo-3")})"></i>'
            f'<a href="{_e(annuncio.url)}" target="_blank" rel="noopener">{_e(annuncio.fonte)}</a></span></td>'
            "</tr>"
        )
    coda = (
        f'<p class="vuota">…e altre {troncati} auto in questa fascia: sono tutte nel CSV.</p>'
        if troncati
        else ""
    )
    return (
        "<table><thead><tr>"
        "<th>Auto</th><th class='num'>Anno</th><th class='num'>Km</th>"
        "<th class='num'>Prezzo</th><th>Zona</th><th>Telefono</th><th>Annuncio</th>"
        "</tr></thead><tbody>" + "".join(righe) + "</tbody></table>" + coda
    )


def scrivi_report(
    percorso: str,
    annunci: list[Annuncio],
    config: dict,
    ordine_fasce: list[str],
    avvisi: list[str],
    momento: datetime,
    confronto: bool = False,
) -> None:
    per_fascia: dict[str, Counter] = defaultdict(Counter)
    elenchi: dict[str, list[Annuncio]] = defaultdict(list)
    for annuncio in annunci:
        per_fascia[annuncio.fascia][annuncio.fonte] += 1
        elenchi[annuncio.fascia].append(annuncio)

    # Le fasce configurate in ordine, più eventuali code ("prezzo non indicato").
    fasce = [f for f in ordine_fasce if f in per_fascia]
    fasce += [f for f in per_fascia if f not in ordine_fasce]

    doppioni = sum(1 for a in annunci if a.doppione_di)
    filtri = config.get("filtri") or {}
    zona = config.get("zona") or {}

    dettaglio = []
    for fascia in fasce:
        elenco = sorted(elenchi[fascia], key=lambda a: a.prezzo or 0)
        conteggi = per_fascia[fascia]
        riepilogo = " · ".join(f"{f} {n}" for f, n in conteggi.most_common())
        dettaglio.append(
            f"<details><summary><span>{_e(fascia)}</span>"
            f'<span class="conteggio">{len(elenco)} auto — {_e(riepilogo)}</span></summary>'
            f"{_tabella(elenco, MASSIMO_IN_PAGINA)}</details>"
        )

    # La sezione che serve davvero quando il giro parte da solo ogni mattina.
    blocco_novita = ""
    if confronto:
        nuovi = sorted(
            (a for a in annunci if a.nuovo), key=lambda a: (a.prezzo is None, a.prezzo or 0)
        )
        contenuto = (
            _tabella(nuovi, MASSIMO_IN_PAGINA)
            if nuovi
            else '<p class="vuota">Nessun annuncio nuovo rispetto al giro precedente.</p>'
        )
        blocco_novita = (
            f'<div class="riquadro"><h2>Comparse dall\'ultimo giro '
            f'<span class="conteggio">({len(nuovi)})</span></h2>{contenuto}</div>'
        )

    blocco_avvisi = ""
    if avvisi:
        voci = "".join(f"<div>· {_e(a)}</div>" for a in avvisi)
        blocco_avvisi = f'<div class="avvisi"><strong>Ricerche non riuscite</strong>{voci}</div>'

    condizioni = []
    if filtri.get("anno_min"):
        condizioni.append(f"dal {filtri['anno_min']}")
    if filtri.get("km_max"):
        condizioni.append(f"max {_km(filtri['km_max'])} km")
    if filtri.get("escludi_parole"):
        condizioni.append("escluse: " + ", ".join(filtri["escludi_parole"]))

    documento = f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Auto da privati — {_e(zona.get('etichetta', ''))}</title>
<style>{STILE}</style></head><body>
<div class="foglio">
<header>
  <h1>Auto da privati — {_e(zona.get('etichetta', 'zona non indicata'))}</h1>
  <p class="sottotitolo">Estrazione del {momento.strftime('%d/%m/%Y alle %H:%M')} ·
     AutoScout24 e Subito · solo venditori privati{' · ' + _e(' · '.join(condizioni)) if condizioni else ''}</p>
</header>
{blocco_avvisi}
{_numeri(annunci, doppioni, confronto)}
{blocco_novita}
<div class="riquadro">
  <h2>Quante auto per fascia di prezzo</h2>
  {_grafico(per_fascia, fasce)}
</div>
<div class="riquadro">
  <h2>Gli annunci, fascia per fascia</h2>
  {''.join(dettaglio) if dettaglio else '<p class="vuota">Nessun annuncio.</p>'}
</div>
<footer>
  Gli stessi dati sono nel CSV accanto a questo file, apribile in Excel.<br>
  I contatti raccolti riguardano persone fisiche: prima di telefonare, verificare il
  Registro Pubblico delle Opposizioni e conservare i numeri solo per il tempo necessario.
</footer>
</div>
<div id="suggerimento"></div>
<script>{SCRIPT}</script>
</body></html>"""

    with open(percorso, "w", encoding="utf-8") as file:
        file.write(documento)
