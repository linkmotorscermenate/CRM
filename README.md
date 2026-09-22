# Ricerca auto da privati — AutoScout24 + Subito

Cerca su **AutoScout24** e **Subito** le auto in vendita **da privati** in una zona
scelta, le divide per **fascia di prezzo** e produce due file: un CSV da aprire in
Excel e un report HTML da guardare al volo.

Serve solo Python 3 (già presente sul Mac). Nessuna libreria da installare.

---

## Installarlo su un altro computer

Serve solo **Python 3** (`python3 --version` per controllare; su Windows si
scarica da python.org, su Linux di solito c'è già). Nessuna libreria da
installare: il programma usa solo quello che Python porta con sé.

1. Copiare la cartella dove si vuole — il percorso non conta, il programma si
   orienta da sé. Su macOS evitare Scrivania, Documenti e Scaricati se il giro
   deve partire da solo: il sistema non lascia leggere quelle cartelle ai
   processi automatici.
2. Aprire il terminale dentro la cartella e lanciare `python3 server.py`.
3. Aprire `http://localhost:8080`, entrare in **Impostazioni**, sistemare la zona
   e fare un **Giro di prova**.

Le cartelle `output/` e `dati/` non sono nel pacchetto: si creano da sole al
primo giro. Vuol dire che sul computer nuovo il primo giro non segnala novità
(non ha con cosa confrontarle) e dal secondo in poi sì.

Il giro automatico cambia col sistema:

- **Windows** — `automazione/windows/attiva.txt`: c'è il comando pronto da
  incollare e, in alternativa, i passaggi con l'Utilità di pianificazione.
- **macOS** — `automazione/attiva.sh` (launchd). Attenzione: non funziona se la
  cartella sta su Scrivania, Documenti o Scaricati.
- **Linux** — cron o systemd, con il comando `python3 cerca.py --no-apri`.

**Un posto solo.** Se il giro parte sia da un computer sia dall'altro, i "nuovi
dall'ultimo giro" si sballano: ognuno tiene il proprio `dati/storico.json`.
Meglio che a cercare sia una macchina sola, e che gli altri ne guardino i
risultati.

## Come si usa: il sito

```bash
cd "/Users/moneymaker/Desktop/Link Motors" && python3 server.py
```

Si apre da solo `http://localhost:8080`. Da lì si fa tutto:

- **Impostazioni** — zona, fasce di prezzo, filtri, quanto a fondo cercare.
  Le province si spuntano da un elenco, non si scrivono più a mano.
- **Cerca ora** — avvia il giro e mostra l'avanzamento riga per riga mentre va.
  **Giro di prova** fa lo stesso ma si ferma a 20 annunci per fascia: serve a
  controllare che una zona nuova dia i risultati giusti senza aspettare.
- **I risultati** — i numeri chiave, il grafico per fascia, e la tabella con
  ricerca libera, filtro per fascia / fonte / solo i nuovi, e ordinamento
  cliccando sulle intestazioni. **Scarica CSV** dà lo stesso elenco per Excel.

Il sito gira **sul Mac**, non su un hosting: la ricerca deve poter interrogare
AutoScout24 e Subito, cosa che una pagina statica su Netlify non può fare. Finché
la finestra del terminale resta aperta, il sito risponde; si chiude con Ctrl+C.

Quando si apre, il sito mostra **l'ultimo giro già fatto**, senza rifarlo: per
guardare i risultati di stamattina non serve cercare di nuovo.

## Come si usa: il terminale

Il programma resta usabile anche senza sito — è quello che fa partire
l'automazione, e serve quando si vuole scriptare qualcosa.

```bash
cd "/Users/moneymaker/Desktop/Link Motors" && python3 cerca.py
```

Altre varianti:

```bash
python3 cerca.py --prova
```
Giro veloce di verifica: si ferma a 20 annunci per fascia e per fonte (un paio di minuti).

```bash
python3 cerca.py --solo subito
```
Una fonte sola, se l'altra sta facendo i capricci.

```bash
python3 cerca.py --config zona-brescia.json
```
Usa un altro file di configurazione: così si tengono più zone pronte, una per file.

A fine giro si apre da solo il report nel browser (`--no-apri` per evitarlo) e in
`output/` restano due file con data e ora nel nome:

- `auto_privati_2026-09-10_1049.csv` — tutte le colonne, apribile in Excel
- `auto_privati_2026-09-10_1049.html` — il report con i grafici e le tabelle

---

## Come si cambia la zona

Tutto sta in `config.json`. I due siti ragionano in modo diverso sulla geografia,
quindi la zona va detta due volte:

```json
"zona": {
  "etichetta": "Milano e hinterland",
  "autoscout": { "cap": "20121", "raggio_km": 50 },
  "subito":    { "regione": "Lombardia", "province": ["MI", "MB", "LO", "PV"] }
}
```

- **AutoScout24** ragiona a raggio: un CAP di partenza e quanti km intorno
  (valori tipici: 10, 20, 50, 100, 200).
- **Subito** ragiona per provincia: si mette la regione e l'elenco delle sigle.
  Se si tolgono le province, cerca in tutta la regione.
  I nomi si possono scrivere anche per esteso (`"Monza e della Brianza"`).

L'elenco di regioni e province viene scaricato una volta sola e messo in
`dati/geo_subito.json`. Se Subito ne aggiunge, basta cancellare quel file.

---

## Come si cambiano fasce e filtri

```json
"fasce_prezzo": [ [0, 3000], [3000, 6000], [6000, 10000],
                  [10000, 15000], [15000, 25000], [25000, null] ]
```

Gli estremi sono **inclusi a sinistra ed esclusi a destra**: un'auto da 6.000 €
finisce in `6.000 - 10.000`, non in quella sotto. `null` come secondo valore
significa "da lì in su". Le fasce si possono aggiungere, togliere, stringere.

Ogni fascia viene chiesta ai siti come ricerca a sé: oltre a dividere i
risultati, serve a non sbattere contro il tetto di annunci che i siti
restituiscono per una singola ricerca.

```json
"filtri": {
  "anno_min": 2012,
  "km_max": 200000,
  "prezzo_min_credibile": 800,
  "escludi_parole": ["incidentata", "sinistrata", "per ricambi",
                     "non marciante", "noleggio", "leasing", "canone", "acconto"]
}
```

`prezzo_min_credibile` toglie di mezzo quello che sotto una certa cifra non è mai
un'auto in vendita: noleggi a canone mensile messi in vetrina come prezzo pieno,
acconti, esche. `escludi_parole` lavora su parole intere, quindi "rate" non fa
fuori "moderate".

```json
"limiti": { "max_annunci_per_fascia": 300, "pausa_secondi": 1.5 }
```

`max_annunci_per_fascia` vale **per fascia e per fonte**: con 6 fasce, 4 province
e AutoScout24 il tetto teorico è 300 × 6 × 5 = 9.000 annunci. `pausa_secondi` è
l'attesa fra una richiesta e l'altra: non abbassarla sotto 1, non c'è fretta e i
siti non vanno tempestati.

---

## Cosa c'è nel report

- **I quattro numeri in alto**: quanti annunci, prezzo mediano, km mediani, e
  quante auto sono comparse su tutti e due i siti.
- **Il grafico a barre**: quante auto per fascia, e da quale sito arrivano. Serve
  a vedere dove c'è mercato e dove no.
- **Le tabelle**: una per fascia, con anno, km, prezzo, comune, telefono e il link
  all'annuncio. Le auto trovate su entrambi i siti sono segnate ("anche su ...").

Il **doppione** si riconosce confrontando marca, modello, prezzo, anno e km
arrotondati: è un indizio forte, non una certezza — due Panda uguali allo stesso
prezzo esistono.

---

## Limiti da sapere

- **Il telefono c'è solo per AutoScout24.** Subito non lo espone nella ricerca:
  resta il link all'annuncio, dove si contatta il venditore.
- **La provincia c'è solo per Subito**, il CAP solo per AutoScout24: sono i due
  siti a fornire dati diversi.
- **L'anno e i km di Subito** li scrive chi pubblica l'annuncio, e ogni tanto sono
  campati per aria (una 206 immatricolata 2026). Il filtro sul prezzo ne intercetta
  una parte, il resto si vede a occhio.
- **Se un sito cambia il proprio formato** il programma si ferma su quella fonte,
  lo scrive nel report sotto "Ricerche non riuscite" e va avanti con l'altra.

---

## Due cose da tenere a mente

I dati sono gli annunci pubblici così come i due siti li mostrano; il programma li
legge alla stessa velocità di una persona che sfoglia (una richiesta ogni secondo
e mezzo) e non aggira nessun blocco. Se in futuro serve un uso più intenso, la
strada pulita è chiedere un accesso dati ai due siti, non spingere sull'acceleratore.

I numeri di telefono raccolti sono di **persone fisiche**. Prima di iniziare a
chiamare conviene verificare il Registro Pubblico delle Opposizioni, dire subito
da dove arriva il contatto, e non tenere i numeri più del necessario.

---

## Com'è fatto dentro

```
server.py           il sito: serve le pagine e le chiamate /api/…
web/                index.html, app.js, stile.css — l'interfaccia
cerca.py            il motore: cerca, confronta, salva (usato dal sito e a mano)
report.py           il report HTML che resta in output/
config.json         zona, fasce, filtri (lo riscrive anche il sito)
fonti/comune.py     tipo Annuncio, richieste HTTP, pause
fonti/autoscout.py  AutoScout24
fonti/subito.py     Subito + traduzione dei nomi di regioni e province
giro-giornaliero.sh il giro automatico
automazione/        il job delle 9:00 e lo script per attivarlo
dati/               cache della geografia di Subito, storico degli annunci visti
output/             i risultati
```

Il sito non ricalcola niente per conto suo: chiama lo stesso `cerca.esegui()` che
usa il terminale. Anche le etichette delle fasce le decide Python e le manda al
browser già scritte — se le costruissero tutti e due, prima o poi
divergerebbero.

Per aggiungere una fonte (es. AutoUncle, Bakeca) basta un nuovo file in `fonti/`
con una funzione `cerca(zona, prezzo_min, prezzo_max, filtri, massimo)` che
restituisce oggetti `Annuncio`, e una riga in `cerca.py` che la chiama.
