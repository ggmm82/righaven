# Capacità operative: iot

Versione esaminata: **3.16.2**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Observe, control and simulate devices assigned to the task: MQTT, Modbus TCP, HTTP and serial telemetry, Android and Android TV over network ADB, vehicle OBD-II diagnostics, ESP firmware flashing, each write approved by the owner.
**Sorgenti:** Scenario JSON, capture and send receipts, telemetry JSON Lines/CSV, summaries, written values and firmware digests.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Read a device without writing: MQTT topics, Modbus registers, HTTP status, serial or TCP lines, with a summary of records, gaps and value ranges | `iot.capture` |
| Write to a device with the owner consent: MQTT publish, Modbus registers or coils with read-back, HTTP POST/PUT, serial or TCP bytes | `iot.send` |
| Generate deterministic synthetic telemetry from a scenario to test hypotheses before hardware exists | `iot.simulate` |
| Identify and flash an ESP board with esptool, verifying the written image | `iot.inspect`, `iot.flash` |
| Read and manage Android and Android TV over network ADB: device info, apps, logs; install, remove, disable apps, reboot or sideload an update with the owner approval | `iot.android` |
| Diagnose vehicles through an OBD-II ELM327 adapter: protocol, VIN, live values, trouble codes; clear codes only with the owner approval | `iot.obd` |
| Read and control Tuya / Smart Life devices over their local protocol with the device ID and local key: data points; changes only with the owner approval | `iot.tuya` |
| Read and control Matter devices joined to the RigHaven Matter controller: attributes; cluster commands only with the owner approval | `iot.matter` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Captures are samples and simulated telemetry is synthetic. Every write (commands, firmware, Android apps and updates, reboots, clearing OBD codes) needs the owner approval of that exact change, delivered once; on network devices it is enforced by the toolkit, on devices attached to the machine also by the container. Firmware build toolchains and Bluetooth radios are not included: a classic Bluetooth OBD adapter paired as a COM port is shared with the task; a Bluetooth LE OBD adapter never becomes a COM port and is read by the coordinator with harness_bluetooth action obd.

## Scoperta mirata

1. `craft capabilities iot`: selezione per obiettivo e confini.
2. `craft commands iot`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools iot --out "$RIGHAVEN_OUTPUT_DIR/work/iot-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 9 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `b00eb79b88aaf5d0ae62244c429c654a09d82788c923acc61ccb3e8e0b81705e`.
Fonte: https://github.com/pymodbus-dev/pymodbus. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
