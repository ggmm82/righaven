RigHaven - versione portabile per Windows (x64)
================================================

AVVIO
  1. Scompatta lo ZIP in una cartella su un disco NTFS (per esempio C:\RigHaven).
  2. Fai doppio clic su RigHaven.exe.
  3. Si apre il browser su http://127.0.0.1:2026: crea il tuo account (il primo è amministratore).
  Tieni aperta la finestra di RigHaven; premi Ctrl+C per fermarlo.

COSA SERVE
  - Windows 10 22H2 o Windows 11, 64 bit, con la virtualizzazione attiva nel BIOS.
  - WSL 2. Se manca, RigHaven.exe propone di installarlo: serve una volta sola,
    con i permessi di amministratore e un riavvio.
  - Almeno 8 GB di RAM (16 GB consigliati) e 20 GB liberi.
  - Connessione a Internet al primo avvio: le immagini verificate (circa 1 GB)
    vengono scaricate una volta sola, con l'avanzamento [1/5]...[5/5]. Dopo un
    aggiornamento si scaricano solo le parti nuove e le vecchie vengono cancellate.

ISOLAMENTO
  RigHaven gira in una distribuzione WSL dedicata ("RigHaven"), con gli stessi
  contenitori verificati del server. I ruoli lavorano in contenitori isolati come
  sul server; nessuna porta è esposta in rete: l'indirizzo è solo 127.0.0.1.
  Per raggiungerlo da altri dispositivi: RigHaven.exe --bind <IP di questo PC>.

DATI
  Tutto resta nella cartella data accanto a RigHaven.exe (disco data\wsl\ext4.vhdx).
  Per aggiornare: ferma RigHaven, sostituisci RigHaven.exe e la cartella app con
  quelli della nuova versione (la cartella data resta) e riavvia RigHaven.exe.
  Se sposti la cartella (anche su un altro PC) esegui una volta: RigHaven.exe repair

COMANDI (da Prompt dei comandi o PowerShell nella cartella)
  RigHaven.exe            avvia e apre il browser
  RigHaven.exe stop       ferma
  RigHaven.exe status     stato dei servizi
  RigHaven.exe logs       log del gateway (logs frontend, logs proxy, ...)
  RigHaven.exe doctor     controlla WSL, porta, file e distribuzione
  RigHaven.exe repair     ricollega i dati dopo aver spostato la cartella
  RigHaven.exe usb        collega una periferica USB (seriale, scheda, adattatore OBD) a RigHaven
  RigHaven.exe bluetooth  cerca i dispositivi Bluetooth vicini (li vedi in Connessioni)
  RigHaven.exe serial     condivide una porta COM (per esempio un adattatore OBD Bluetooth)
  RigHaven.exe remove     elimina la distribuzione e TUTTI i dati di questa copia
  Opzioni: --port 2027 (porta diversa), --bind 127.0.0.1 (indirizzo), --name Nome (seconda copia), --no-browser,
           --devices auto|none|/dev/ttyUSB0 (porte seriali offerte; predefinito auto)


RigHaven - portable for Windows (x64)
=====================================

START
  1. Extract the ZIP to a folder on an NTFS drive (for example C:\RigHaven).
  2. Double-click RigHaven.exe.
  3. The browser opens http://127.0.0.1:2026: create your account (the first one is administrator).
  Keep the RigHaven window open; press Ctrl+C to stop it.

REQUIREMENTS
  - Windows 10 22H2 or Windows 11, 64-bit, with virtualization enabled in the BIOS.
  - WSL 2. If missing, RigHaven.exe offers to install it: once, with administrator
    rights and a restart.
  - At least 8 GB RAM (16 GB recommended) and 20 GB free.
  - Internet on the first start: the verified images (about 1 GB) are downloaded once,
    with progress [1/5]...[5/5]. After an update only the new parts are downloaded and
    the old images are deleted.

ISOLATION
  RigHaven runs in a dedicated WSL distribution ("RigHaven") with the same verified
  containers as the server. Roles work in isolated containers as on the server; no
  port is exposed on the network: the address is 127.0.0.1 only.
  To reach it from other devices: RigHaven.exe --bind <IP of this PC>.

DATA
  Everything stays in the data folder next to RigHaven.exe (disk data\wsl\ext4.vhdx).
  To update: stop RigHaven, replace RigHaven.exe and the app folder with those of
  the new version (the data folder stays) and start RigHaven.exe again.
  If you move the folder (also to another PC) run once: RigHaven.exe repair

COMMANDS (from Command Prompt or PowerShell in the folder)
  RigHaven.exe            start and open the browser
  RigHaven.exe stop       stop
  RigHaven.exe status     state of the services
  RigHaven.exe logs       gateway logs (logs frontend, logs proxy, ...)
  RigHaven.exe doctor     check WSL, port, files and distribution
  RigHaven.exe repair     reattach the data after moving the folder
  RigHaven.exe usb        attach a USB peripheral (serial, board, OBD adapter) to RigHaven
  RigHaven.exe bluetooth  search nearby Bluetooth devices (shown in Connections)
  RigHaven.exe serial     share a COM port (for example a Bluetooth OBD adapter)
  RigHaven.exe remove     delete the distribution and ALL data of this copy
  Options: --port 2027 (another port), --bind 127.0.0.1 (address), --name Name (second copy), --no-browser,
           --devices auto|none|/dev/ttyUSB0 (serial ports offered; default auto)
