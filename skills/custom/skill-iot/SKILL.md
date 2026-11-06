---
name: skill-iot
description: "Devices and telemetry. Read and, with the owner's consent, write devices assigned as task connections (MQTT, Modbus TCP, HTTP, serial over RFC 2217 or attached to the machine), simulate telemetry from scenarios and flash ESP boards with esptool."
---
# IoT toolkit

This is a tool capability, not a fixed professional role. Inherit the team's centrally configured provider/model. Version selection belongs to the environment interface, not this skill.

Read skill-workspace, [CAPABILITIES.md](references/CAPABILITIES.md), [CLI-RECIPE.md](references/CLI-RECIPE.md), [SCENARIOS.md](references/SCENARIOS.md) and [QUALITY.md](references/QUALITY.md). Discover exact arguments with `craft tools iot` or `iot-cli commands`.

## Devices are task connections

- A device is reachable only if the owner assigned its connection to the task and your role declares it in `roles_json` `connections`. Use the connection ID; never ask for addresses, passwords or ports in chat and never write them in files.
- Read first: `iot.capture` never writes to the device. A device attached to the machine is given to your container read-only unless the owner allowed writing for this task.
- Reading never needs the owner. **Every write needs the owner's approval of that exact change**: the coordinator asks with `harness_device_change` (command fields for `iot.send`, the file for `iot.flash` and Android install or sideload, the package, the reboot mode, `clear_codes` for vehicles), the owner decides in the task card, and the next assignment receives the approval once. Run the write exactly as approved. A refusal is a result to report, not something to work around: never open sockets, serial ports or adb with your own code to bypass it.
- `iot.inspect` resets an ESP board without changing it and needs only the task write consent.
- Android over network ADB: `iot.android` info, packages and logcat read; the TV must have authorized RigHaven once ("Always allow"). Do not offer fastboot flashing.
- Vehicles: `iot.obd` info, live and codes read; explain codes as symptoms to confirm, never as a diagnosis of a part.
- Finding and preparing devices: when the owner asks to find or use a device whose address or port is unknown (also not set up yet, or plugged into the PC), the coordinator uses `harness_find_devices` (home network, nearby Wi-Fi setup networks, Bluetooth, USB peripherals and COM ports of the PC, offered serial ports) and explains what was found; for the device the owner chooses it uses `harness_setup_device`, which attaches or shares it on the PC and creates the connection read only. Device keys (Tuya local key) are entered by the owner in Connections, never asked in the chat.
- Remote server: when RigHaven runs on a server, the owner's PC runs RigHaven Agent; the device tools use the owner's agent that is connected (or the one named), and pass `pc` (its name) when several are connected; connections are cloud or on premise, and an on-premise connection with `agent` reaches a COM port (`serial`), a host of that PC's network (`network`) or its Bluetooth LE through the agent.
- Exploring: `harness_explore_device` reads one network address, Wi-Fi network (open or setup networks only from the chat), Bluetooth device or USB peripheral the owner points to, without a connection; the owner decides what to explore.
- Bluetooth LE devices: `harness_bluetooth` inspects or reads a device by its address (no approval, no connection needed); writes need a saved Bluetooth connection with writing allowed and assigned, and one approved `harness_device_change` (action send, encoding hex, address service/characteristic) per write.
- Matter devices joined to the RigHaven Matter controller: `iot.matter` status (attributes named endpoint/cluster/attribute) and read; `command` with payload `{"endpoint": 1, "cluster": 6, "command": "On"}` and encoding `json` needs `harness_device_change` send with the same payload and encoding.
- Tuya / Smart Life (plugs, bulbs, IR remotes): `iot.tuya` status reads the data points; `set` with payload `{"1": true}` and encoding `json` is a write that needs `harness_device_change` send with the same payload and encoding. Data point meanings vary by product: read status first and say which point you change.
- Without hardware, use `iot.simulate` with an explicit scenario. Simulated telemetry tests the analysis and the hypotheses, not the real world: say so in the delivery.

## Method

1. Identify the question (what must be observed, decided or changed), the devices and the acceptance evidence before touching a device.
2. Capture a short window first (10–60 s), inspect `summary.json` (records, rate, gaps, value ranges) and only then extend.
3. For analysis, load `telemetry.csv` or `telemetry.jsonl` with DuckDB, Jupyter or Quarto in the same environment; keep queries and notebooks as sources.
4. For writes, state the intended effect and the risk, ask for the smallest change with `harness_device_change`, end the turn, and after approval run it once; read it back (Modbus does this automatically) and capture again to observe the effect.
5. For firmware, build or receive the `.bin`, record its SHA-256, `iot.inspect` the board, ask approval for that file, `iot.flash` (written and verified), then capture the serial output to observe the new firmware.

## Delivery: editable sources and compatibility

Preserve: scenario JSON, capture and send receipts, telemetry files, summaries, analysis queries/notebooks and firmware digests. Record products, sources and reports separately in `delivery.files` and `delivery.components`. State checks separately; never claim a check that did not run.

For learning, retain general, evidenced improvements rather than customer facts. Never retain device addresses, credentials or private telemetry as reusable experience.

Upstream: https://github.com/pymodbus-dev/pymodbus · https://github.com/eclipse-paho/paho.mqtt.python · https://github.com/pyserial/pyserial · https://github.com/espressif/esptool
