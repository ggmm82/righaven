RigHaven - versione portabile per Linux (x64)
=============================================

AVVIO
  1. Scompatta l'archivio in una cartella (per esempio ~/RigHaven).
  2. Da un terminale nella cartella: ./righaven
  3. Si apre il browser su http://127.0.0.1:2026: crea il tuo account (il primo è amministratore).
  I servizi restano attivi in background; per fermarli: ./righaven stop

COSA SERVE
  - Linux x64 con Docker Engine 24 o successivo e il plugin Compose 2.20 o successivo
    (https://docs.docker.com/engine/install/). Docker rootless non basta: il runtime
    privato dei ruoli richiede un motore Docker con privilegi.
  - Un utente nel gruppo docker (sudo usermod -aG docker $USER, poi esci e rientra), oppure sudo.
  - Almeno 8 GB di RAM (16 GB consigliati) e 20 GB liberi.
  - Connessione a Internet al primo avvio: le immagini verificate (circa 1 GB) vengono
    scaricate una volta sola. Dopo un aggiornamento si scaricano solo le parti nuove e
    vengono cancellate solo le immagini delle versioni precedenti di RigHaven.

ISOLAMENTO
  Gli stessi contenitori verificati del server, con il motore Docker del PC. I ruoli lavorano
  nei contenitori isolati del runtime privato come sul server. L'indirizzo è solo 127.0.0.1;
  per raggiungerlo da altri dispositivi: ./righaven --bind <IP di questo PC>

DATI
  I dati di RigHaven stanno nei volumi Docker del progetto "righaven"; impostazioni e
  segreto interno nella cartella data accanto allo script. Per aggiornare: ./righaven stop,
  sostituisci lo script righaven e la cartella app con quelli della nuova versione
  (data resta) e riavvia. Se i servizi non vengono fermati ripartono con Docker al riavvio del PC.

COMANDI
  ./righaven              avvia e apre il browser
  ./righaven stop         ferma
  ./righaven status       stato dei servizi
  ./righaven logs         log del gateway (logs frontend, logs proxy, ...)
  ./righaven doctor       controlla Docker, Compose, file, porta e indirizzo
  ./righaven bluetooth    cerca i dispositivi Bluetooth vicini (li vedi in Connessioni)
  ./righaven remove       elimina i contenitori e TUTTI i dati di questa copia
  Opzioni (ricordate): --port 2027, --bind 127.0.0.1, --name righaven2 (seconda copia),
           --devices auto|none|/dev/ttyUSB0 (porte seriali offerte: predefinito auto, tutte quelle collegate), --no-browser


RigHaven - portable for Linux (x64)
===================================

START
  1. Extract the archive to a folder (for example ~/RigHaven).
  2. From a terminal in the folder: ./righaven
  3. The browser opens http://127.0.0.1:2026: create your account (the first one is administrator).
  The services keep running in the background; to stop them: ./righaven stop

REQUIREMENTS
  - Linux x64 with Docker Engine 24 or later and the Compose plugin 2.20 or later
    (https://docs.docker.com/engine/install/). Rootless Docker is not enough: the private
    runtime of the roles needs a Docker engine with privileges.
  - A user in the docker group (sudo usermod -aG docker $USER, then log out and in), or sudo.
  - At least 8 GB RAM (16 GB recommended) and 20 GB free.
  - Internet on the first start: the verified images (about 1 GB) are downloaded once.
    After an update only the new parts are downloaded, and only the images of earlier
    RigHaven versions are deleted.

ISOLATION
  The same verified containers as the server, with the Docker engine of the PC. Roles work
  in the isolated containers of the private runtime as on the server. The address is
  127.0.0.1 only; to reach it from other devices: ./righaven --bind <IP of this PC>

DATA
  RigHaven's data is in the Docker volumes of project "righaven"; settings and the internal
  secret are in the data folder next to the script. To update: ./righaven stop, replace the
  righaven script and the app folder with those of the new version (data stays) and start
  again. Services that are not stopped restart with Docker when the PC restarts.

COMMANDS
  ./righaven              start and open the browser
  ./righaven stop         stop
  ./righaven status       state of the services
  ./righaven logs         gateway logs (logs frontend, logs proxy, ...)
  ./righaven doctor       check Docker, Compose, files, port and address
  ./righaven bluetooth    search nearby Bluetooth devices (shown in Connections)
  ./righaven remove       delete the containers and ALL data of this copy
  Options (remembered): --port 2027, --bind 127.0.0.1, --name righaven2 (second copy),
           --devices auto|none|/dev/ttyUSB0 (serial ports offered: default auto, every port plugged in), --no-browser
