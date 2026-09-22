# Mettere il CRM online su Render

Il CRM è un'app Python (`server.py`) con login utente+password. Questi passi la
pubblicano su un indirizzo `https://…` raggiungibile dal team.

## 1. Prerequisiti
- Il codice è su GitHub: `linkmotorscermenate/CRM`.
- Un account su https://render.com (va bene "Sign in with GitHub").

## 2. Creare il servizio
1. Su Render: **New → Blueprint**.
2. Collega il repository `linkmotorscermenate/CRM`. Render legge `render.yaml`.
3. Conferma la creazione. Verrà creato un servizio web con un **disco persistente**
   da 1 GB montato su `/var/data` (piano `starter`, a pagamento: serve perché
   senza disco Render azzererebbe i dati — contatti, storico, impostazioni — a
   ogni riavvio).

## 3. Impostare gli utenti del login
Nella dashboard del servizio → **Environment** → variabile `CRM_UTENTI`:

```
mario:UnaPasswordLunga,luca:UnAltraPassword
```

Formato: `utente:password` separati da virgola. Cambiala quando serve; le
password restano solo qui su Render, non nel codice.

> Se `CRM_UTENTI` è vuota, il sito è **senza login** (aperto a chiunque abbia il
> link). Con dentro dati personali, tienila sempre valorizzata.

## 4. Fatto
Render fornisce un indirizzo tipo `https://crm-linkmotors.onrender.com`.
Aprendolo, il browser chiede utente e password. Ad ogni `git push` sul repo,
Render aggiorna il sito da solo.

## Note
- **Ricerche dal cloud**: AutoScout e Subito potrebbero rispondere in modo diverso
  a un IP di datacenter rispetto a un IP di casa/ufficio. Se una fonte inizia a
  dare 403, va verificato lì (vedi lo User-Agent in `fonti/comune.py`).
- **Uso in locale**: senza le variabili d'ambiente `CRM_DATA_DIR`/`CRM_UTENTI`,
  `python server.py` funziona esattamente come prima, su `localhost:8080` e
  senza login.
