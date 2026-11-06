package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

// Device nodes the portable copy may give to tasks as connections (attached to WSL with usbipd).
var deviceNode = regexp.MustCompile(`^/dev/(ttyUSB\d{1,3}|ttyACM\d{1,3}|ttyS\d{1,3}|serial/by-id/[A-Za-z0-9_.:-]{1,120}|rfcomm\d{1,2}|hidraw\d{1,3}|bus/usb/\d{3}/\d{3})$`)

// Settings of one portable copy, kept in data\settings.json next to the executable.
type Settings struct {
	Port         int      `json:"port"`
	Distribution string   `json:"distribution"`
	Devices      []string `json:"devices,omitempty"`
	Bind         string   `json:"bind,omitempty"`
	// NoDevices turns off offering the serial ports present in WSL (--devices none).
	NoDevices bool `json:"no_devices,omitempty"`
	// USB lists the usbipd bus IDs attached to WSL at every start (RigHaven.exe usb).
	USB []string `json:"usb,omitempty"`
	// Serial lists the Windows COM ports shared with RigHaven while it runs (RigHaven.exe serial).
	Serial []string `json:"serial,omitempty"`
	// Matter starts RigHaven's Matter controller (RigHaven.exe matter enable).
	Matter bool `json:"matter,omitempty"`
}

type Release struct {
	Version      string            `json:"version"`
	SourceCommit string            `json:"source_commit"`
	PullRequest  *int              `json:"pull_request"`
	Files        map[string]string `json:"files"`
}

type App struct {
	Home     string
	Data     string
	Language string
	Settings Settings
}

const defaultDistribution = "RigHaven"

func newApp(home, language string) (*App, error) {
	a := &App{Home: home, Data: filepath.Join(home, "data"), Language: language,
		Settings: Settings{Port: 2026, Distribution: defaultDistribution}}
	content, err := os.ReadFile(filepath.Join(a.Data, "settings.json"))
	if err == nil {
		if err := json.Unmarshal(content, &a.Settings); err != nil {
			return nil, fmt.Errorf("data\\settings.json: %w", err)
		}
	} else if !errors.Is(err, os.ErrNotExist) {
		return nil, err
	}
	return a, a.validate()
}

func (a *App) validate() error {
	if a.Settings.Port < 1024 || a.Settings.Port > 65535 {
		return errors.New(a.T("bad_port"))
	}
	name := a.Settings.Distribution
	if name == "" || len(name) > 64 || strings.Trim(name, "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.") != "" {
		return errors.New(a.T("bad_name"))
	}
	if a.Settings.Bind != "" && net.ParseIP(a.Settings.Bind) == nil {
		return fmt.Errorf(a.T("bad_bind"), a.Settings.Bind)
	}
	for _, id := range a.Settings.USB {
		if !busID.MatchString(id) {
			return fmt.Errorf(a.T("usb_unknown"), id)
		}
	}
	for _, name := range a.Settings.Serial {
		if !comName.MatchString(name) {
			return fmt.Errorf(a.T("com_unknown"), name)
		}
	}
	for _, device := range a.Settings.Devices {
		if !deviceNode.MatchString(device) {
			return fmt.Errorf(a.T("bad_device"), device)
		}
	}
	return nil
}

func (a *App) save() error {
	if err := a.validate(); err != nil {
		return err
	}
	if err := os.MkdirAll(a.Data, 0o755); err != nil {
		return err
	}
	content, _ := json.MarshalIndent(a.Settings, "", "  ")
	return os.WriteFile(filepath.Join(a.Data, "settings.json"), append(content, '\n'), 0o644)
}

// Address RigHaven.exe serves on Windows: 127.0.0.1 unless --bind chose another address of this PC.
func (a *App) BindAddress() string {
	if a.Settings.Bind == "" {
		return "127.0.0.1"
	}
	return a.Settings.Bind
}

// Address of the browser: the bind address, or 127.0.0.1 when listening on every interface.
func (a *App) Host() string {
	ip := net.ParseIP(a.BindAddress())
	if ip.IsUnspecified() {
		return "127.0.0.1"
	}
	if ip.To4() == nil {
		return "[" + ip.String() + "]"
	}
	return ip.String()
}

func (a *App) Listen() string { return net.JoinHostPort(a.BindAddress(), fmt.Sprint(a.Settings.Port)) }

func (a *App) Loopback() bool { return net.ParseIP(a.BindAddress()).IsLoopback() }

// Port of the proxy inside the distribution, different from the Windows port so the two never clash.
func (a *App) InnerPort() int { return 30000 + a.Settings.Port%10000 }

func (a *App) URL() string { return fmt.Sprintf("http://%s:%d", a.Host(), a.Settings.Port) }

func (a *App) release() (Release, error) {
	var value Release
	content, err := os.ReadFile(filepath.Join(a.Home, "app", "release.json"))
	if err != nil {
		return value, errors.New(a.T("missing_app"))
	}
	return value, json.Unmarshal(content, &value)
}

func fileExists(path string) bool {
	info, err := os.Stat(path)
	return err == nil && !info.IsDir()
}

var messages = map[string][2]string{
	// key: {Italian, English}
	"title":               {"RigHaven %s · versione portabile per Windows", "RigHaven %s · portable for Windows"},
	"no_wsl":              {"WSL 2 non è installato. Serve una volta sola, con i permessi di amministratore e un riavvio.", "WSL 2 is not installed. It is needed once, with administrator rights and a restart."},
	"old_wsl":             {"WSL è troppo vecchio. Aggiornalo con: wsl --update", "WSL is too old. Update it with: wsl --update"},
	"ask_wsl":             {"Vuoi installarlo ora? [s/N] ", "Install it now? [y/N] "},
	"wsl_started":         {"Installazione di WSL avviata. Al termine riavvia Windows e apri di nuovo RigHaven.", "WSL installation started. When it finishes, restart Windows and open RigHaven again."},
	"wsl_manual":          {"Apri PowerShell come amministratore ed esegui: wsl --install --no-distribution", "Open PowerShell as administrator and run: wsl --install --no-distribution"},
	"importing":           {"Prima installazione: preparo l'ambiente isolato (circa un minuto)…", "First installation: preparing the isolated environment (about a minute)…"},
	"reattach":            {"Ricollego i dati esistenti di questa cartella…", "Reattaching the existing data of this folder…"},
	"other_copy":          {"La distribuzione %q appartiene a un'altra copia di RigHaven (%s). Chiudi quella copia o avvia questa con --name AltroNome.", "The %q distribution belongs to another RigHaven copy (%s). Close that copy or start this one with --name OtherName."},
	"missing_app":         {"Mancano i file nella cartella app. Scompatta di nuovo lo ZIP completo.", "Files are missing in the app folder. Extract the complete ZIP again."},
	"step_images":         {"Scarico %s immagini verificate (solo la prima volta o dopo un aggiornamento; circa 1 GB la prima volta):", "Downloading %s verified images (first time or after an update only; about 1 GB the first time):"},
	"step_start":          {"Avvio RigHaven (la prima volta prepara anche l'ambiente di lavoro: qualche minuto)…", "Starting RigHaven (the first time it also prepares the work environment: a few minutes)…"},
	"port_unavailable":    {"Windows non permette a RigHaven di usare %s: %v. Prova un'altra porta con --port 2027.", "Windows does not let RigHaven use %s: %v. Try another port with --port 2027."},
	"diag_keep":           {"RigHaven resta acceso per la diagnosi: manda queste righe o l'output di RigHaven.exe doctor. Ctrl+C per fermarlo.", "RigHaven stays up for diagnosis: send these lines or the output of RigHaven.exe doctor. Ctrl+C stops it."},
	"forwarding":          {"WSL non inoltra la porta a Windows: la inoltra RigHaven.exe.", "WSL does not forward the port to Windows: RigHaven.exe forwards it."},
	"unreachable_ui":      {"RigHaven è avviato ma %s non risponde da Windows. Dettagli: RigHaven.exe doctor", "RigHaven started but %s does not answer from Windows. Details: RigHaven.exe doctor"},
	"ready":               {"RigHaven è pronto: %s", "RigHaven is ready: %s"},
	"keep_open":           {"Tieni aperta questa finestra. Premi Ctrl+C per fermare RigHaven.", "Keep this window open. Press Ctrl+C to stop RigHaven."},
	"already":             {"RigHaven è già in esecuzione: apro %s", "RigHaven is already running: opening %s"},
	"port_busy":           {"La porta %d è occupata da un altro programma. Avvia con --port 2027 (o un'altra porta libera).", "Port %d is used by another program. Start with --port 2027 (or another free port)."},
	"stopping":            {"Fermo RigHaven, attendi…", "Stopping RigHaven, please wait…"},
	"stopped":             {"RigHaven è fermo. I dati restano nella cartella data.", "RigHaven is stopped. Your data stays in the data folder."},
	"start_failed":        {"Avvio non riuscito. Dettagli sopra; per i log: RigHaven.exe logs", "Start failed. Details above; for logs: RigHaven.exe logs"},
	"press_enter":         {"Premi Invio per chiudere.", "Press Enter to close."},
	"confirm_remove":      {"Elimina la distribuzione %q e TUTTI i dati di RigHaven di questa copia. Scrivi ELIMINA per confermare: ", "Delete the %q distribution and ALL RigHaven data of this copy. Type DELETE to confirm: "},
	"confirm_repair":      {"Ricollego alla distribuzione %q il disco di questa cartella. La registrazione precedente verrà rimossa, con gli eventuali dati rimasti nella vecchia posizione. Scrivi RICOLLEGA per confermare: ", "Reattach the disk of this folder to the %q distribution. The previous registration is removed, with any data left at the old location. Type REATTACH to confirm: "},
	"unreachable":         {"La distribuzione %q non si avvia (%s). Se hai spostato la cartella di RigHaven esegui: RigHaven.exe repair", "The %q distribution does not start (%s). If you moved the RigHaven folder run: RigHaven.exe repair"},
	"no_disk":             {"In questa cartella non ci sono dati da ricollegare (data\\wsl\\ext4.vhdx).", "This folder has no data to reattach (data\\wsl\\ext4.vhdx)."},
	"removed":             {"Distribuzione eliminata.", "Distribution deleted."},
	"cancelled":           {"Annullato.", "Cancelled."},
	"bad_port":            {"Porta non valida: usa un numero tra 1024 e 65535.", "Invalid port: use a number between 1024 and 65535."},
	"bad_bind":            {"Indirizzo non valido: %s (usa un IP di questo PC, per esempio 127.0.0.1).", "Invalid address: %s (use an IP of this PC, for example 127.0.0.1)."},
	"exposed":             {"Attenzione: RigHaven è raggiungibile dalla rete su %s. Usa --bind 127.0.0.1 per tenerlo solo su questo PC.", "Warning: RigHaven is reachable from the network on %s. Use --bind 127.0.0.1 to keep it on this PC only."},
	"bad_device":          {"Dispositivo non valido: %s (usa per esempio /dev/ttyUSB0 o /dev/ttyACM0).", "Invalid device: %s (use for example /dev/ttyUSB0 or /dev/ttyACM0)."},
	"bad_name":            {"Nome non valido: usa lettere, numeri, '-', '_' o '.'.", "Invalid name: use letters, numbers, '-', '_' or '.'."},
	"bt_searching":        {"Cerco dispositivi Bluetooth vicini e associati (circa 20 secondi; nulla viene associato o modificato)…", "Searching for nearby and paired Bluetooth devices (about 20 seconds; nothing is paired or changed)…"},
	"bt_failed":           {"Ricerca Bluetooth non riuscita: %v", "Bluetooth search failed: %v"},
	"bt_none":             {"Nessun dispositivo Bluetooth trovato. Accendi il dispositivo e mettilo in modalità di associazione, poi riprova.", "No Bluetooth device found. Turn the device on and put it in pairing mode, then try again."},
	"bt_nearby":           {"vicino", "nearby"},
	"bt_paired":           {"associato", "paired"},
	"bt_hint_obd":         {"adattatore OBD-II: associalo in Windows, poi condividi la sua porta COM con RigHaven.exe serial", "OBD-II adapter: pair it in Windows, then share its COM port with RigHaven.exe serial"},
	"bt_hint_tuya":        {"dispositivo Tuya/Smart Life: se ha anche il Wi-Fi, cercalo in rete dalla pagina Connessioni", "Tuya/Smart Life device: if it also has Wi-Fi, find it on the network from the Connections page"},
	"bt_hint_esp32":       {"scheda ESP32: collegala via USB (RigHaven.exe usb) per leggerla o programmarla", "ESP32 board: attach it over USB (RigHaven.exe usb) to read or program it"},
	"bt_hint_xiaomi":      {"sensore Xiaomi: trasmette dati Bluetooth LE; per ora RigHaven non li legge direttamente", "Xiaomi sensor: it broadcasts Bluetooth LE data; RigHaven does not read it directly yet"},
	"bt_hint_shelly":      {"Shelly: ha anche il Wi-Fi, cercalo in rete dalla pagina Connessioni", "Shelly: it also has Wi-Fi, find it on the network from the Connections page"},
	"bt_hint_tv":          {"TV: per Android TV usa la rete (debug ADB via Wi-Fi) dalla pagina Connessioni", "TV: for Android TV use the network (ADB debugging over Wi-Fi) from the Connections page"},
	"bt_sensor":           {"sensore Bluetooth LE: le letture decodificate sono in Connessioni → Trova dispositivi", "Bluetooth LE sensor: the decoded readings are in Connections → Find devices"},
	"bt_every":            {"Uso: RigHaven.exe bluetooth [minuti] (ripete la ricerca ogni N minuti, da 1 a 1440)", "Usage: RigHaven.exe bluetooth [minutes] (repeats the search every N minutes, 1 to 1440)"},
	"bt_next":             {"Prossima ricerca tra %d minuti (Ctrl+C per smettere).", "Next search in %d minutes (Ctrl+C to stop)."},
	"bt_saved":            {"Elenco passato a RigHaven: lo vedi in Connessioni → Trova dispositivi.", "List passed to RigHaven: see it in Connections → Find devices."},
	"bt_not_saved":        {"Elenco non passato a RigHaven: avvialo una volta, poi ripeti la ricerca.", "List not passed to RigHaven: start it once, then search again."},
	"com_failed":          {"Elenco delle porte COM non disponibile: %v", "COM port list unavailable: %v"},
	"com_none":            {"Nessuna porta COM. Per un adattatore Bluetooth (per esempio OBD-II) associalo prima nelle impostazioni Bluetooth di Windows.", "No COM port. For a Bluetooth adapter (for example OBD-II) pair it first in the Windows Bluetooth settings."},
	"com_list":            {"Porte seriali di Windows (* = collegamento Bluetooth):", "Windows serial ports (* = Bluetooth link):"},
	"com_choose":          {"Numero o nome della porta da condividere con RigHaven (Invio per uscire): ", "Number or name of the port to share with RigHaven (Enter to quit): "},
	"com_unknown":         {"Porta COM non trovata: %s (vedi RigHaven.exe serial).", "COM port not found: %s (see RigHaven.exe serial)."},
	"com_shared":          {"%s sarà condivisa con RigHaven a ogni avvio: in Connessioni → Trova dispositivi crea la connessione.", "%s will be shared with RigHaven at every start: create the connection in Connections → Find devices."},
	"com_restart":         {"RigHaven è già avviato: riavvialo (Ctrl+C e di nuovo RigHaven.exe) per condividerla.", "RigHaven is already running: restart it (Ctrl+C and RigHaven.exe again) to share it."},
	"com_bridged":         {"Porta seriale condivisa con RigHaven: %s %s", "Serial port shared with RigHaven: %s %s"},
	"com_unavailable":     {"%s non disponibile (%v): accendi il dispositivo; riprovo da solo.", "%s not available (%v): turn the device on; retrying automatically."},
	"matter_on":           {"Controller Matter attivo", "Matter controller on"},
	"matter_off":          {"Controller Matter spento", "Matter controller off"},
	"matter_mirrored":     {"rete WSL mirrored", "WSL mirrored networking"},
	"matter_disabled":     {"Controller Matter disattivato dal prossimo avvio. La rete mirrored di WSL resta: per tornare alla NAT rimuovi la riga networkingMode da .wslconfig.", "Matter controller off from the next start. WSL mirrored networking stays: to go back to NAT remove the networkingMode line from .wslconfig."},
	"matter_usage":        {"Uso: RigHaven.exe matter [enable|disable|status]", "Usage: RigHaven.exe matter [enable|disable|status]"},
	"matter_windows":      {"Matter richiede Windows 11 22H2 o successivo (build 22621); questo PC ha la build %d.", "Matter needs Windows 11 22H2 or later (build 22621); this PC has build %d."},
	"matter_explain":      {"Per trovare i dispositivi Matter RigHaven deve vedere la rete di casa:\n  1. imposta la rete «mirrored» di WSL in %s (vale per tutte le distribuzioni WSL; il file attuale viene salvato come copia);\n  2. consente nel firewall Hyper-V il traffico UDP 5353 (mDNS) e 5540 (Matter) verso WSL (Windows chiede il permesso una volta);\n  3. riavvia WSL (le distribuzioni WSL in esecuzione vengono chiuse).", "To find Matter devices RigHaven must see the home network:\n  1. set WSL \"mirrored\" networking in %s (applies to every WSL distribution; the current file is kept as a copy);\n  2. allow UDP 5353 (mDNS) and 5540 (Matter) into WSL in the Hyper-V firewall (Windows asks for permission once);\n  3. restart WSL (running WSL distributions are closed)."},
	"matter_ask":          {"Procedo? [s/N] ", "Proceed? [y/N] "},
	"matter_firewall":     {"Regola del firewall non aggiunta (%v): senza di essa i dispositivi potrebbero non essere trovati.", "Firewall rule not added (%v): without it devices may not be found."},
	"matter_restart":      {"RigHaven è avviato: chiudilo (Ctrl+C), esegui wsl --shutdown e riavvia RigHaven.exe.", "RigHaven is running: close it (Ctrl+C), run wsl --shutdown and start RigHaven.exe again."},
	"matter_ready":        {"Fatto. Avvia RigHaven.exe: in Connessioni trovi «Dispositivi Matter».", "Done. Start RigHaven.exe: Connections shows \"Matter devices\"."},
	"matter_not_mirrored": {"Il controller Matter è attivo ma WSL non è in rete mirrored: esegui RigHaven.exe matter enable.", "The Matter controller is on but WSL is not in mirrored networking: run RigHaven.exe matter enable."},
	"usb_missing":         {"Per collegare periferiche USB a RigHaven serve usbipd-win (gratuito, di Microsoft e della comunità).", "Attaching USB peripherals to RigHaven needs usbipd-win (free, from Microsoft and the community)."},
	"usb_ask_install":     {"Vuoi installarlo ora con winget? Windows chiederà il permesso. [s/N] ", "Install it now with winget? Windows will ask for permission. [y/N] "},
	"usb_installed":       {"usbipd-win installato. Chiudi questa finestra e riesegui: RigHaven.exe usb", "usbipd-win installed. Close this window and run again: RigHaven.exe usb"},
	"usb_install_failed":  {"Installazione non riuscita (%v). Scaricalo da https://github.com/dorssel/usbipd-win/releases e riprova.", "Installation failed (%v). Download it from https://github.com/dorssel/usbipd-win/releases and try again."},
	"usb_list":            {"Periferiche USB di questo PC (* = probabile porta seriale o scheda):", "USB peripherals of this PC (* = likely serial port or board):"},
	"usb_choose":          {"Numero o bus ID da collegare a RigHaven (Invio per uscire): ", "Number or bus ID to attach to RigHaven (Enter to quit): "},
	"usb_none":            {"Nessuna periferica USB collegata.", "No USB peripheral is plugged in."},
	"bt_no_adapter":       {"Windows non ha un adattatore Bluetooth funzionante: accendi il Bluetooth nelle impostazioni di Windows. Se l'adattatore è collegato a RigHaven, restituiscilo a Windows da «Periferiche del PC».", "Windows has no working Bluetooth adapter: turn Bluetooth on in the Windows settings. If the adapter is attached to RigHaven, give it back to Windows from “PC peripherals”."},
	"usb_pc_bluetooth":    {"%s è l'adattatore Bluetooth del PC: se lo colleghi a RigHaven, Windows perde il Bluetooth finché non lo restituisci. Conferma per collegarlo comunque.", "%s is the PC's Bluetooth adapter: attaching it to RigHaven takes Bluetooth away from Windows until you give it back. Confirm to attach it anyway."},
	"usb_detach_failed":   {"Non riesco a restituire %s a Windows: %v", "Cannot give %s back to Windows: %v"},
	"capture_seconds":     {"Durata della registrazione tra 10 e 300 secondi.", "Recording length between 10 and 300 seconds."},
	"capture_failed":      {"Registrazione del traffico non riuscita (Windows chiede il permesso di amministratore): %v", "Traffic recording failed (Windows asks for administrator rights): %v"},
	"wifi_not_read":       {"Il dispositivo sulla rete %s non ha risposto", "The device on network %s did not answer"},
	"wifi_tuya":           {"I dispositivi Tuya / Smart Life si configurano con la loro app (il protocollo di configurazione è cifrato): aggiungilo con Smart Life, poi cercalo in rete.", "Tuya / Smart Life devices are set up with their app (the setup protocol is encrypted): add it with Smart Life, then search for it on the network."},
	"wifi_unsupported":    {"Questa rete non è di un dispositivo che RigHaven sa leggere o configurare (Tasmota, Shelly, ESPHome, WLED, OpenBeken, Daikin).", "This network is not of a device RigHaven can read or set up (Tasmota, Shelly, ESPHome, WLED, OpenBeken, Daikin)."},
	"wifi_password":       {"La password del Wi-Fi di casa deve avere da 8 a 63 caratteri.", "The home Wi-Fi password must have 8 to 63 characters."},
	"wifi_home":           {"Il PC non è collegato a un Wi-Fi: scrivi il nome della rete di casa.", "The PC is not on a Wi-Fi network: type the name of the home network."},
	"wifi_join":           {"Non riesco a collegarmi alla rete %s del dispositivo: %v", "Cannot join the device's network %s: %v"},
	"wifi_not_sent":       {"Il dispositivo sulla rete %s non ha accettato la configurazione (pagina di configurazione non raggiunta)", "The device on network %s did not accept the setup (setup page not reached)"},
	"wifi_back":           {"Configurazione inviata, ma il PC non è tornato sulla rete %s: ricollegalo dalle impostazioni Wi-Fi (%v)", "Setup sent, but the PC did not go back to %s: reconnect it from the Wi-Fi settings (%v)"},
	"usb_unknown":         {"Periferica USB non trovata: %s (vedi RigHaven.exe usb).", "USB peripheral not found: %s (see RigHaven.exe usb)."},
	"usb_bind":            {"Condivido %s con WSL: Windows chiede il permesso una sola volta.", "Sharing %s with WSL: Windows asks for permission once."},
	"usb_bind_failed":     {"Condivisione di %s non riuscita: %v", "Sharing %s failed: %v"},
	"usb_attach_failed":   {"Collegamento di %s a WSL non riuscito: %s", "Attaching %s to WSL failed: %s"},
	"usb_attached":        {"Collegato a RigHaven: %s", "Attached to RigHaven: %s"},
	"usb_unplugged":       {"La periferica USB %s non è collegata: la ricollego al prossimo avvio.", "USB peripheral %s is not plugged in: it will be attached at the next start."},
	"usb_nodes":           {"Porte disponibili per le connessioni: %s", "Ports available to connections: %s"},
	"usb_no_node":         {"Collegata, ma WSL non ha creato una porta seriale: forse non è un adattatore seriale (vedi docs/IOT.md).", "Attached, but WSL created no serial port: it may not be a serial adapter (see docs/IOT.md)."},
	"usb_refresh":         {"Aggiorno RigHaven perché veda la nuova porta (gli incarichi in corso vengono interrotti)…", "Refreshing RigHaven so it sees the new port (running assignments are interrupted)…"},
	"usb_next_start":      {"La porta sarà offerta alle connessioni al prossimo avvio di RigHaven.", "The port will be offered to connections at the next start of RigHaven."},
	"usb_hint":            {"Per collegare una periferica USB (seriale, scheda, adattatore OBD): RigHaven.exe usb", "To attach a USB peripheral (serial, board, OBD adapter): RigHaven.exe usb"},
	"not_installed":       {"Questa copia non è ancora installata: avvia RigHaven.exe.", "This copy is not installed yet: run RigHaven.exe."},
	"usage": {`Uso: RigHaven.exe [comando] [opzioni]

Comandi:
  start      avvia RigHaven e apre il browser (predefinito)
  stop       ferma RigHaven
  status     stato dei servizi
  logs [s]   log di un servizio (gateway, frontend, proxy, runtime-docker, redis)
  doctor     controlla WSL, porta, file e distribuzione
  shell      terminale amministratore nella distribuzione
  repair     ricollega i dati dopo aver spostato la cartella
  remove     elimina la distribuzione e i dati di questa copia
  usb        elenca le periferiche USB e collega quella scelta (ricordata ai prossimi avvii);
             usb forget BUSID smette di collegarla
  bluetooth [N]  cerca i dispositivi Bluetooth vicini e associati e legge i sensori Bluetooth LE;
             con N ripete ogni N minuti (storico delle letture)
  matter     enable|disable|status: controller Matter per collegare dispositivi Matter (Windows 11)
  serial     condivide con RigHaven una porta COM di Windows (per esempio un adattatore OBD Bluetooth);
             serial forget COM5 smette di condividerla
  version    versione

Opzioni:
  --port N       porta locale (predefinita 2026), ricordata per i prossimi avvii
  --name NOME    nome della distribuzione WSL (predefinito RigHaven)
  --bind IP      indirizzo su cui RigHaven risponde (predefinito 127.0.0.1); un IP della rete
                 lo rende raggiungibile da altri dispositivi
  --devices L    porte da offrire alle connessioni: "auto" (predefinito, tutte le porte seriali
                 collegate), un elenco come /dev/ttyUSB0 oppure "none"
  --no-browser   non aprire il browser
  --yes          conferma senza chiedere (remove, repair)`, `Usage: RigHaven.exe [command] [options]

Commands:
  start      start RigHaven and open the browser (default)
  stop       stop RigHaven
  status     state of the services
  logs [s]   logs of one service (gateway, frontend, proxy, runtime-docker, redis)
  doctor     check WSL, port, files and distribution
  shell      administrator shell in the distribution
  repair     reattach the data after moving the folder
  remove     delete the distribution and the data of this copy
  usb        list the USB peripherals and attach the chosen one (remembered for the next starts);
             usb forget BUSID stops attaching it
  bluetooth [N]  search nearby and paired Bluetooth devices and read Bluetooth LE sensors;
             with N it repeats every N minutes (history of readings)
  matter     enable|disable|status: Matter controller to connect Matter devices (Windows 11)
  serial     share a Windows COM port with RigHaven (for example a Bluetooth OBD adapter);
             serial forget COM5 stops sharing it
  version    version

Options:
  --port N       local port (default 2026), remembered for the next starts
  --name NAME    WSL distribution name (default RigHaven)
  --bind IP      address RigHaven answers on (default 127.0.0.1); a network IP makes it
                 reachable from other devices
  --devices L    ports offered to connections: "auto" (default, every serial port attached),
                 a list such as /dev/ttyUSB0, or "none"
  --no-browser   do not open the browser
  --yes          confirm without asking (remove, repair)`},
}

func (a *App) T(key string) string {
	value, ok := messages[key]
	if !ok {
		return key
	}
	if a.Language == "it" {
		return value[0]
	}
	return value[1]
}
