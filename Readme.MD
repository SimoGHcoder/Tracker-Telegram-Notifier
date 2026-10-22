# Tracker Telegram Notifier

Tracker Telegram Notifier (TTN) controlla gli episodi e i film presenti nella libreria Nuvio e invia notifiche Telegram quando trova un flusso nella lingua audio selezionata. I controlli interrogano gli addon Nuvio attivi selezionati nelle impostazioni.

## Funzionalita

- Sincronizza libreria e cronologia del profilo Nuvio selezionato.
- Supporta piu profili Nuvio, con chat Telegram principale condivisa o chat dedicata per profilo.
- Collega Telegram tramite QR code dopo aver configurato il token del proprio bot dalla Web UI.
- Controlla l'episodio successivo all'ultimo visto e i film supportati dagli addon.
- Filtra per lingua audio ITA o ENG e permette di scegliere gli addon da interrogare.
- Consente di attivare o disattivare le notifiche per singolo contenuto o in blocco, separatamente nelle schede Libreria e Cronologia, e avviare controlli manuali.
- La dashboard mostra le notifiche attive sul totale dei contenuti distinti presenti in libreria o cronologia.
- Esegue controlli periodici in background. L'intervallo impostabile dalla UI va da 1 a 24 ore, con 4 ore predefinite.
- Mostra la versione applicativa nel footer della dashboard e usa una favicon SVG dedicata.

## Requisiti

- Python 3.10 o successivo per l'avvio diretto.
- Un account Nuvio.
- Un bot Telegram e il relativo token per inviare notifiche.
- Docker e Docker Compose, se si sceglie l'avvio containerizzato.

## Avvio su Windows

1. Scarica o clona il repository e apri la cartella del progetto.
2. Avvia `start_full.bat`. Lo script crea `.venv`, installa le dipendenze e avvia il server sulla porta 8080.
3. Apri <http://localhost:8080>.

## Avvio su Linux

Dalla cartella del progetto, esegui `./start_full.sh`. Lo script crea l'ambiente virtuale, installa le dipendenze e avvia il server sulla porta 8080. Se necessario, rendilo eseguibile con `chmod +x start_full.sh`.

## Avvio con Docker Compose

Dalla cartella che contiene `docker-compose.yml`, esegui:

```bash
docker compose up --build -d
```

**Nota:** la configurazione Docker Compose e' presente, ma l'ambiente Docker non e' stato testato. Build dell'immagine e avvio del container non sono quindi verificati.

Apri <http://localhost:8080>. La porta e' pubblicata solo su localhost perche' l'app non prevede autenticazione. La cartella locale `data/` e' montata nel container per conservare i dati tra i riavvii. Per arrestare il servizio, esegui `docker compose down`.

## Configurazione

Al primo avvio viene creato `data/config.json` a partire da `config.example.json`. Per configurare Telegram, apri **Impostazioni**, vai a **Token del tuo bot Telegram** e segui le istruzioni per creare il bot con @BotFather. Incolla il token ricevuto e premi **Salva token**: l'app ne verifica la validita' prima di salvarlo nella configurazione locale. Il campo resta vuoto dopo il salvataggio; puoi sostituire o rimuovere il token dalla stessa schermata. Non condividere il token. Se viene esposto, revocalo con @BotFather e creane uno nuovo.

Nella scheda **Impostazioni** inserisci email e password Nuvio, imposta intervallo e lingua audio, quindi seleziona gli addon. Inizialmente sono selezionati tutti gli addon attivi disponibili per il profilo. Nella sezione Telegram scansiona il QR code. Per i profili secondari puoi usare la chat del profilo principale oppure collegarne una dedicata.

I controlli automatici seguono l'intervallo configurato e non sono in tempo reale. Dalla dashboard puoi avviare un controllo manuale. Le notifiche richiedono un token valido e una chat raggiungibile.

## Dati e privacy

Le impostazioni locali sono salvate in `data/config.json` e `data/users.json`; questi file sono esclusi dal controllo versione tramite `.gitignore`. Le API non restituiscono password o token, ma l'app va comunque usata solo in un ambiente fidato e non esposta direttamente su Internet. Non pubblicare token Telegram o credenziali Nuvio. Con Docker, conserva la cartella `data/` tra i riavvii.

## Struttura del progetto

```text
app/
|-- __init__.py
|-- config.py
|-- main.py
|-- telegram_bot.py
|-- tracker.py
`-- static/
    |-- index.html
    |-- favicon.svg
    |-- styles.css
    `-- js/
        `-- app.js
data/                   # Dati locali generati all'avvio
.gitignore
.dockerignore
config.example.json
docker-compose.yml
Dockerfile
LICENSE
Readme.MD
requirements.txt
start_full.bat
start_full.sh
```

## Licenza

Distribuito secondo i termini della licenza MIT; vedere [LICENSE](LICENSE).
