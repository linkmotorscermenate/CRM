'use strict';

const COLORE = { AutoScout24: 'var(--serie-1)', Subito: 'var(--serie-2)' };
const A_PAGINA = 100;

// Chi può aver contattato l'annuncio, e gli stati dell'affare. Per cambiarli
// basta modificare queste due liste.
const VENDITORI = ['Thomas', 'Roberta', 'Oussama'];
const STATI_AFFARE = ['da contrattare', 'in pagamento', 'chiuso'];

let stato = {
  config: null,
  zone: [],
  annunci: [],
  momento: '',
  fasce: [],
  riepilogo: {},
  avvisi: [],
  organizzazione: {},
  mostrati: A_PAGINA,
  ordine: { campo: 'prezzo', crescente: true },
  sondaggio: null,
};

const $ = (id) => document.getElementById(id);
// Intl in italiano non separa le migliaia sotto le 5 cifre ("7800"), mentre il
// resto del programma scrive "7.800": raggruppiamo a mano per non avere due stili.
const raggruppa = (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
const euro = (n) => (n == null ? '—' : raggruppa(n) + ' €');
const numero = (n) => (n == null ? '—' : raggruppa(n));

function testo(valore) {
  const div = document.createElement('div');
  div.textContent = valore == null ? '' : String(valore);
  return div.innerHTML;
}

// Come testo(), ma va bene anche dentro un attributo tra virgolette doppie.
const attr = (valore) => testo(valore).replace(/"/g, '&quot;');

// ---------------------------------------------------------------- fasce

function righeFasce() {
  // Leggiamo solo le cifre: così "4.000", "4000" e "4 000" valgono tutti 4000.
  // Senza questo, i campi type=number leggono il punto come decimale (4.000 -> 4).
  const cifre = (valore) => {
    const n = parseInt(String(valore).replace(/\D/g, ''), 10);
    return Number.isNaN(n) ? null : n;
  };
  return [...$('fasce').querySelectorAll('.fascia-riga')].map((riga) => {
    const campi = riga.querySelectorAll('input');
    return [cifre(campi[0].value) || 0, cifre(campi[1].value)];
  });
}

function aggiungiFascia(min = 0, max = null) {
  const riga = document.createElement('div');
  riga.className = 'fascia-riga';
  riga.innerHTML =
    `<input type="text" inputmode="numeric" placeholder="da" value="${min ?? 0}">` +
    `<input type="text" inputmode="numeric" placeholder="a (vuoto = in su)" value="${max ?? ''}">` +
    `<button title="togli questa fascia">✕</button>`;
  riga.querySelector('button').onclick = () => riga.remove();
  $('fasce').appendChild(riga);
}

// ---------------------------------------------------------------- form

function riempiForm(config) {
  const zona = config.zona, filtri = config.filtri || {}, limiti = config.limiti || {};
  $('etichetta').value = zona.etichetta || '';
  $('cap').value = zona.autoscout.cap || '';
  $('raggio').value = zona.autoscout.raggio_km || 50;
  $('massimo').value = limiti.max_annunci_per_fascia || 300;
  $('pausa').value = limiti.pausa_secondi || 1.5;
  $('anno-min').value = filtri.anno_min || '';
  $('km-max').value = filtri.km_max || '';
  $('prezzo-min').value = filtri.prezzo_min_credibile || '';
  $('incongruenti').checked = filtri.scarta_incongruenti !== false;
  $('parole').value = (filtri.escludi_parole || []).join('\n');

  $('fasce').innerHTML = '';
  (config.fasce_prezzo || []).forEach(([min, max]) => aggiungiFascia(min, max));

  const scelta = $('regione');
  scelta.innerHTML = stato.zone.map((r) => `<option>${testo(r.nome)}</option>`).join('');
  scelta.value = zona.subito.regione || '';
  disegnaProvince(zona.subito.province || []);
  scelta.onchange = () => disegnaProvince([]);
}

function disegnaProvince(selezionate) {
  const regione = stato.zone.find((r) => r.nome === $('regione').value);
  // Nel file le province possono stare come sigla ("MI") o per esteso
  // ("Milano"): riconosciamo tutte e due, altrimenti la scelta si perde.
  const scelte = new Set(selezionate.map((p) => String(p).trim().toLowerCase()));
  $('province').innerHTML = !regione
    ? '<span class="vuota">Scegli prima la regione.</span>'
    : regione.province
        .map(({ nome, sigla }) => {
          const spuntata =
            scelte.has(nome.toLowerCase()) || (sigla && scelte.has(sigla.toLowerCase()))
              ? 'checked'
              : '';
          return `<label><input type="checkbox" value="${testo(nome)}" ${spuntata}>${testo(nome)}` +
                 (sigla ? ` <span class="sotto">${testo(sigla)}</span>` : '') + `</label>`;
        })
        .join('');
}

function leggiForm() {
  const caselle = $('province').querySelectorAll('input[type=checkbox]');
  const modulo = {
    etichetta: $('etichetta').value,
    cap: $('cap').value,
    raggio_km: $('raggio').value,
    regione: $('regione').value,
    fasce_prezzo: righeFasce(),
    anno_min: $('anno-min').value,
    km_max: $('km-max').value,
    prezzo_min_credibile: $('prezzo-min').value,
    scarta_incongruenti: $('incongruenti').checked,
    escludi_parole: $('parole').value.split('\n').map((p) => p.trim()).filter(Boolean),
    max_annunci_per_fascia: $('massimo').value,
    pausa_secondi: $('pausa').value,
  };
  // Il campo si manda solo se le caselle esistono davvero: se l'elenco non si
  // è caricato, il server tiene le province già salvate.
  if (caselle.length) {
    modulo.province = [...caselle].filter((c) => c.checked).map((c) => c.value);
  }
  return modulo;
}

// ---------------------------------------------------------------- rete

async function chiedi(rotta, opzioni) {
  const risposta = await fetch(rotta, opzioni);
  const dati = await risposta.json();
  if (!risposta.ok) throw new Error(dati.errore || `errore ${risposta.status}`);
  return dati;
}

async function avvia(prova = false) {
  const corpo = { ...leggiForm(), prova };
  $('avvia').disabled = true;
  try {
    await chiedi('/api/cerca', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(corpo),
    });
    $('impostazioni').hidden = true;
    $('registro').textContent = '';
    $('avanzamento').hidden = false;
    $('titolo-avanzamento').textContent = prova ? 'Giro di prova in corso…' : 'Ricerca in corso…';
    sondaggio(true);
  } catch (errore) {
    $('avvia').disabled = false;
    alert(errore.message);
  }
}

function sondaggio(subito) {
  clearInterval(stato.sondaggio);
  const passo = async () => {
    let dati;
    try {
      dati = await chiedi('/api/stato');
    } catch (e) {
      return;
    }
    const registro = $('registro');
    registro.textContent = dati.righe.join('\n');
    registro.scrollTop = registro.scrollHeight;

    if (!dati.in_corso) {
      clearInterval(stato.sondaggio);
      stato.sondaggio = null;
      $('avvia').disabled = false;
      $('avanzamento').hidden = dati.righe.length === 0;
      $('titolo-avanzamento').textContent = dati.errore ? 'Ricerca interrotta' : 'Ricerca conclusa';
      document.querySelector('.pulsante-carica').style.display = 'none';
      stato.riepilogo = dati.riepilogo || {};
      stato.avvisi = dati.avvisi || [];
      await caricaAnnunci();
    }
  };
  stato.sondaggio = setInterval(passo, 1500);
  if (subito) passo();
}

async function caricaAnnunci() {
  const [dati, organizzazione] = await Promise.all([
    chiedi('/api/annunci'),
    chiedi('/api/organizzazione').catch(() => ({})),
  ]);
  stato.annunci = dati.annunci || [];
  stato.momento = dati.momento || '';
  stato.fasce = dati.fasce || [];
  stato.organizzazione = organizzazione || {};
  stato.mostrati = A_PAGINA;
  disegnaTutto();
}

async function salvaOrganizzazione(riga) {
  const url = riga.dataset.url;
  if (!url) return;
  const voce = {
    contattato: riga.querySelector('.org-contattato').checked,
    chi: riga.querySelector('.org-chi').value,
    stato: riga.querySelector('.org-stato').value,
  };
  stato.organizzazione[url] = voce;               // subito, così i filtri e i ridisegni la vedono
  riga.classList.toggle('contattato', voce.contattato);
  // Se è attivo un filtro per agente/contattati, la riga potrebbe non
  // appartenere più all'elenco filtrato: ridisegniamo per tenerlo coerente.
  if ($('filtro-chi').value) disegnaTabella();
  try {
    await chiedi('/api/organizzazione', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, ...voce }),
    });
  } catch (errore) {
    console.error('Salvataggio non riuscito:', errore.message);
  }
}

// ---------------------------------------------------------------- vista

function annunciFiltrati() {
  const cercato = $('testo').value.trim().toLowerCase();
  const fascia = $('filtro-fascia').value;
  const fonte = $('filtro-fonte').value;
  const soloNuovi = $('filtro-nuovi').value === 'nuovi';
  const chi = $('filtro-chi').value;

  let elenco = stato.annunci.filter((a) => {
    if (fascia && a.fascia !== fascia) return false;
    if (fonte && a.fonte !== fonte) return false;
    if (soloNuovi && !a.nuovo) return false;
    if (chi) {
      const voce = stato.organizzazione[a.url] || {};
      // "__contattati": qualunque annuncio marcato come contattato.
      // Altrimenti: solo gli annunci presi in carico da quell'agente.
      if (chi === '__contattati') {
        if (!voce.contattato) return false;
      } else if (voce.chi !== chi) {
        return false;
      }
    }
    if (cercato) {
      const dove = `${a.nome} ${a.versione} ${a.comune} ${a.provincia}`.toLowerCase();
      if (!dove.includes(cercato)) return false;
    }
    return true;
  });

  const { campo, crescente } = stato.ordine;
  elenco.sort((x, y) => {
    const a = x[campo], b = y[campo];
    if (a == null && b == null) return 0;
    if (a == null) return 1;
    if (b == null) return -1;
    const confronto = typeof a === 'string' ? a.localeCompare(b, 'it') : a - b;
    return crescente ? confronto : -confronto;
  });
  return elenco;
}

function disegnaNumeri() {
  const r = stato.riepilogo;
  const prezzi = stato.annunci.map((a) => a.prezzo).filter((p) => p != null).sort((a, b) => a - b);
  const kms = stato.annunci.map((a) => a.km).filter((k) => k != null).sort((a, b) => a - b);
  const mediana = (v) => (v.length ? v[Math.floor(v.length / 2)] : null);

  const voci = [];
  if (r.confronto) voci.push([String(r.nuovi ?? 0), "nuovi dall'ultimo giro"]);
  voci.push(
    [String(stato.annunci.length), 'annunci di privati'],
    [euro(mediana(prezzi)), 'prezzo mediano'],
    [kms.length ? numero(mediana(kms)) + ' km' : '—', 'km mediani'],
    [String(r.doppioni ?? 0), 'su entrambi i siti']
  );
  $('numeri').innerHTML = voci
    .map(([v, e]) => `<div class="numero"><div class="valore">${testo(v)}</div><div class="etichetta">${testo(e)}</div></div>`)
    .join('');
}

function disegnaGrafico() {
  const perFascia = new Map();
  for (const a of stato.annunci) {
    if (!perFascia.has(a.fascia)) perFascia.set(a.fascia, { AutoScout24: 0, Subito: 0 });
    perFascia.get(a.fascia)[a.fonte] = (perFascia.get(a.fascia)[a.fonte] || 0) + 1;
  }
  const ordine = stato.fasce;
  const fasce = [
    ...ordine.filter((f) => perFascia.has(f)),
    ...[...perFascia.keys()].filter((f) => !ordine.includes(f)),
  ];
  const massimo = Math.max(0, ...[...perFascia.values()].map((c) => c.AutoScout24 + c.Subito));

  if (!massimo) {
    $('grafico').innerHTML = '<p class="vuota">Nessun annuncio: avvia una ricerca.</p>';
    return;
  }
  const legenda = ['AutoScout24', 'Subito']
    .map((f) => `<span><i class="pastiglia" style="background:${COLORE[f]}"></i>${f}</span>`)
    .join('');
  const righe = fasce
    .map((fascia) => {
      const conteggi = perFascia.get(fascia);
      const totale = conteggi.AutoScout24 + conteggi.Subito;
      const segmenti = ['AutoScout24', 'Subito']
        .filter((f) => conteggi[f])
        .map(
          (f) =>
            `<div class="segmento" style="width:${(conteggi[f] / massimo) * 100}%;background:${COLORE[f]}"` +
            ` data-info="${testo(fascia)} · ${f}: ${conteggi[f]}"></div>`
        )
        .join('');
      return `<div class="barra-nome">${testo(fascia)}</div><div class="barra-pista">${segmenti}</div><div class="barra-valore">${totale}</div>`;
    })
    .join('');
  $('grafico').innerHTML = `<div class="legenda">${legenda}</div><div class="barre">${righe}</div>`;
  agganciaSuggerimenti();

  const scelta = $('filtro-fascia');
  const precedente = scelta.value;
  scelta.innerHTML = '<option value="">Tutte le fasce</option>' + fasce.map((f) => `<option>${testo(f)}</option>`).join('');
  scelta.value = precedente;
}

function celleOrganizzazione(a) {
  const voce = stato.organizzazione[a.url] || {};
  const opzioni = (elenco, scelta) =>
    ['<option value="">—</option>']
      .concat(elenco.map((v) => `<option ${voce[scelta] === v ? 'selected' : ''}>${testo(v)}</option>`))
      .join('');
  return (
    `<td class="org-spunta"><input type="checkbox" class="org-contattato"${voce.contattato ? ' checked' : ''}></td>` +
    `<td><select class="org-chi">${opzioni(VENDITORI, 'chi')}</select></td>` +
    `<td><select class="org-stato">${opzioni(STATI_AFFARE, 'stato')}</select></td>`
  );
}

function disegnaTabella() {
  const elenco = annunciFiltrati();
  const corpo = document.querySelector('#tabella tbody');
  const visibili = elenco.slice(0, stato.mostrati);

  corpo.innerHTML = visibili
    .map((a) => {
      const nuovo = a.nuovo ? '<span class="targhetta">nuovo</span>' : '';
      const versione = a.versione ? `<div class="sotto">${testo(a.versione)}</div>` : '';
      const doppio = a.doppione_di ? `<div class="sotto">anche su ${testo(String(a.doppione_di).split(' ')[0])}</div>` : '';
      const luogo = [a.comune, a.provincia].filter(Boolean).join(', ');
      const telefono = a.telefono ? `<a href="tel:${testo(a.telefono)}">${testo(a.telefono)}</a>` : '';
      const contattato = stato.organizzazione[a.url]?.contattato ? ' class="contattato"' : '';
      return (
        `<tr data-url="${attr(a.url)}"${contattato}>` +
        `<td>${nuovo}${testo(a.nome)}${versione}${doppio}</td>` +
        `<td class="num">${testo(a.anno ?? '—')}</td>` +
        `<td class="num">${numero(a.km)}</td>` +
        `<td class="num">${euro(a.prezzo)}</td>` +
        `<td>${testo(luogo)}</td>` +
        `<td>${telefono}</td>` +
        `<td><span class="fonte"><i class="pastiglia" style="background:${COLORE[a.fonte] || 'var(--testo-3)'}"></i>` +
        `<a href="${testo(a.url)}" target="_blank" rel="noopener">apri</a></span></td>` +
        `<td>${a.pubblicato ? testo(a.pubblicato) : '—'}</td>` +
        celleOrganizzazione(a) +
        '</tr>'
      );
    })
    .join('');

  $('quanti').textContent =
    elenco.length === stato.annunci.length
      ? `${elenco.length} auto`
      : `${elenco.length} di ${stato.annunci.length} auto`;
  $('altre').hidden = elenco.length <= stato.mostrati;

  document.querySelectorAll('th.ordinabile').forEach((intestazione) => {
    const attiva = intestazione.dataset.campo === stato.ordine.campo;
    intestazione.querySelector('.freccia')?.remove();
    if (attiva) {
      const freccia = document.createElement('span');
      freccia.className = 'freccia';
      freccia.textContent = stato.ordine.crescente ? ' ↑' : ' ↓';
      intestazione.appendChild(freccia);
    }
  });
}

function disegnaAvvisi() {
  $('avvisi').innerHTML = stato.avvisi.length
    ? `<div class="avvisi"><strong>Ricerche non riuscite</strong>${stato.avvisi.map((a) => `<div>· ${testo(a)}</div>`).join('')}</div>`
    : '';
}

function disegnaTutto() {
  const zona = stato.config?.zona?.etichetta || '';
  $('sottotitolo').textContent = stato.momento ? `${zona} · ultimo giro ${stato.momento}` : zona;
  const csv = stato.riepilogo.csv;
  $('scarica-csv').hidden = !csv;
  if (csv) $('scarica-csv').href = `/scarica/${encodeURIComponent(csv)}`;
  disegnaAvvisi();
  disegnaNumeri();
  disegnaGrafico();
  disegnaTabella();
}

function agganciaSuggerimenti() {
  const box = $('suggerimento');
  document.querySelectorAll('[data-info]').forEach((elemento) => {
    elemento.onmouseenter = () => { box.textContent = elemento.dataset.info; box.style.opacity = 1; };
    elemento.onmousemove = (e) => {
      box.style.left = e.clientX + 14 + 'px';
      box.style.top = e.clientY - 30 + 'px';
    };
    elemento.onmouseleave = () => { box.style.opacity = 0; };
  });
}

// ---------------------------------------------------------------- avvio

function riempiFiltroAgenti() {
  // Un'opzione per ogni venditore, in coda a "Tutti gli agenti" e "Tutti i
  // contattati" già presenti nell'HTML. Così il menu segue la lista VENDITORI.
  const scelta = $('filtro-chi');
  const precedente = scelta.value;
  scelta.querySelectorAll('option[data-agente]').forEach((o) => o.remove());
  for (const nome of VENDITORI) {
    const opzione = document.createElement('option');
    opzione.value = nome;
    opzione.textContent = nome;
    opzione.dataset.agente = '1';
    scelta.appendChild(opzione);
  }
  scelta.value = precedente;
}

async function inizio() {
  riempiFiltroAgenti();
  const dati = await chiedi('/api/avvio');
  stato.config = dati.config;
  stato.fasce = dati.fasce || [];
  stato.zone = dati.zone || [];
  stato.riepilogo = dati.stato.riepilogo || {};
  stato.avvisi = dati.stato.avvisi || [];
  riempiForm(dati.config);
  await caricaAnnunci();
  if (dati.stato.in_corso) {
    $('avanzamento').hidden = false;
    $('avvia').disabled = true;
    sondaggio(true);
  }
  if (!stato.annunci.length) $('impostazioni').hidden = false;
}

$('avvia').onclick = () => avvia(false);
$('salva-cerca').onclick = () => avvia(false);
$('prova').onclick = () => avvia(true);
$('mostra-impostazioni').onclick = () => { $('impostazioni').hidden = !$('impostazioni').hidden; };
$('chiudi-impostazioni').onclick = () => { $('impostazioni').hidden = true; };
$('aggiungi-fascia').onclick = () => aggiungiFascia(0, null);
$('altre').onclick = () => { stato.mostrati += A_PAGINA; disegnaTabella(); };

$('salva').onclick = async () => {
  try {
    await chiedi('/api/impostazioni', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(leggiForm()),
    });
    stato.config = (await chiedi('/api/avvio')).config;
    $('salva').textContent = 'Salvato ✓';
    setTimeout(() => ($('salva').textContent = 'Salva'), 1600);
    disegnaTutto();
  } catch (errore) {
    alert(errore.message);
  }
};

// Spunta e menu di ogni riga: un solo ascoltatore sul corpo tabella, che
// resta valido anche quando la tabella viene ridisegnata.
document.querySelector('#tabella tbody').addEventListener('change', (evento) => {
  if (!evento.target.matches('.org-contattato, .org-chi, .org-stato')) return;
  const riga = evento.target.closest('tr[data-url]');
  if (riga) salvaOrganizzazione(riga);
});

['testo', 'filtro-fascia', 'filtro-fonte', 'filtro-nuovi', 'filtro-chi'].forEach((id) => {
  $(id).addEventListener('input', () => { stato.mostrati = A_PAGINA; disegnaTabella(); });
});

document.querySelectorAll('th.ordinabile').forEach((intestazione) => {
  intestazione.onclick = () => {
    const campo = intestazione.dataset.campo;
    stato.ordine = {
      campo,
      crescente: stato.ordine.campo === campo ? !stato.ordine.crescente : true,
    };
    disegnaTabella();
  };
});

inizio().catch((errore) => {
  document.querySelector('.foglio').insertAdjacentHTML(
    'afterbegin',
    `<div class="avvisi">Il sito non riesce a parlare col programma: ${testo(errore.message)}</div>`
  );
});
