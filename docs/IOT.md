# Devices, IoT and embedded

RigHaven can observe and, when you allow it, control real devices: sensors, PLCs, meters,
MQTT brokers, ESP boards, Android and Android TV devices, vehicles through an OBD-II adapter.
Roles keep working in their isolated containers; a device reaches a role only as a **task
connection** you assign, exactly like a database.

**Reading never asks you anything. Every write does**: each command, firmware, app, update,
reboot or clearing of vehicle trouble codes is asked to you in the task card and runs once,
exactly as you approved it.

## What you get

| Piece | Where | Purpose |
|---|---|---|
| **Device connection** | Connections → *New: Device* | Address of a device or interface; secrets encrypted, never shown to roles or the coordinator |
| **iot toolkit** | Environments → *IoT & Embedded* | `iot.capture`, `iot.send`, `iot.simulate`, `iot.inspect`, `iot.flash`, `iot.android`, `iot.obd`, `iot.tuya`, `iot.matter` |
| **IoT & Embedded environment** | Environments, Community Gallery | iot toolkit with DuckDB, Jupyter and Quarto for analysis and reports |
| **Device monitoring** recipe | Recipes | Connect, sample, analyse, set thresholds, dashboard, optional device changes |
| **Urban IoT simulation** recipe | Recipes | Hypotheses, scenario, simulated telemetry, comparison and report, no hardware needed |

## Device connections

| Transport | Use it for | What the role receives |
|---|---|---|
| **Network** | MQTT broker (topic filter), Modbus TCP (unit), HTTP endpoint (path), Android over network ADB, TCP text lines (also Wi-Fi OBD adapters) | Address and, if set, user and password (for ADB, the connection's own key), in a private file for that task |
| **Serial over the network** | A serial port shared with RFC 2217 (ser2net, ESP-Link, a Raspberry Pi next to the board) | `rfc2217://host:port` and the baud rate |
| **Attached to this machine** | USB serial adapters, ESP/Arduino boards, HID devices on the server or the Windows portable PC | That single device node inside the task container |

**Access.** Three levels, all decided by you:

1. The connection is read-only unless you choose *Also writes*.
2. Each task needs your tick in *Task connections* (*Allow writes to this device in this task*).
   Without it a device attached to the machine is passed to the container **read-only**
   (`--device …:r`), so even custom code cannot write to it.
3. **Each write needs your approval of that exact change.** The coordinator asks with
   `harness_device_change`; you see device, action and the exact command, file (name, size,
   SHA-256), app package or reboot mode under *Device writes to approve* in the task card, and
   approve or reject. An approved change is handed once to the next assignment that receives the
   device; the toolkit refuses any write that does not match it (a different command, another
   file, a second run). A file that changed after the request cannot be approved.

| Write | What you approve |
|---|---|
| `iot.send` | The exact command: topic and payload, Modbus address and values, HTTP body, serial or TCP bytes |
| `iot.flash` | The firmware `.bin` by SHA-256 |
| `iot.android` install / sideload | The `.apk` or OTA `.zip` by SHA-256 |
| `iot.android` uninstall / disable / enable | The app package |
| `iot.android` reboot | The mode (system, recovery, bootloader, sideload) |
| `iot.obd` clear_codes | Clearing the stored trouble codes |
| `iot.tuya` set | The exact data points and values (`send` fingerprint of payload and encoding) |
| `iot.matter` command | The exact cluster command (`send` fingerprint of payload and encoding) |

`iot.inspect` resets an ESP board into its bootloader without changing it: it needs the task
write consent, not a per-change approval.

Network devices are reached over the network: the toolkit enforces the consent, but a role that
ran its own network code could not be stopped by the device itself. Use device accounts with
the permissions you intend (for example an MQTT user that can only subscribe).

**Administrator settings** (Gateway environment):

- `RIGHAVEN_CONNECTIONS_PRIVATE_NETWORKS=allow`: devices are usually on private networks
  (192.168.x.x, 10.x.x.x); without it they are refused. The Windows portable app allows them
  by default.
- `RIGHAVEN_DEVICES=/dev/ttyUSB0,/dev/ttyACM0`: the device nodes that may be offered to tasks.
  Only interface classes are accepted (serial, USB, HID, GPIO, I²C, SPI, video), never disks.
  The devices must exist when RigHaven starts.
- With `RIGHAVEN_WORKER_EGRESS=allowlist`, device hosts are added to the task's allowed domains,
  but the egress proxy carries HTTP(S) only: MQTT, Modbus and raw TCP need the default open egress.

Every delivery of a device to a task is written in the task's audit log, with read or write.

## The iot toolkit

| Operation | Writes to the device | Output |
|---|---|---|
| `iot.capture` | Never | `telemetry.jsonl`, `telemetry.csv`, `summary.json` (records, rate, gaps over 5 s, min/max/mean of numeric fields, also from `T=21.5 H:40` lines) |
| `iot.send` | Yes, with approval | `written.json` (Modbus writes are read back), reply lines |
| `iot.simulate` | No device | Deterministic synthetic telemetry from a scenario: see [SCENARIOS.md](../skills/custom/skill-iot/references/SCENARIOS.md) |
| `iot.inspect` | Resets the board, with consent | Chip, MAC and flash size from esptool |
| `iot.flash` | Yes, with approval | Firmware written and verified with esptool; image SHA-256 recorded |
| `iot.android` | info, packages, logcat: never; install, uninstall, disable, enable, reboot, sideload: with approval | `device.json`, `packages.json`, logs, `android.json` with the approval used |
| `iot.obd` | info, live, codes: never; clear_codes: with approval | `vehicle.json`, live telemetry, `codes.json`, `cleared.json` |
| `iot.tuya` | status: never; set: with approval | `status.json`, `set.json` with the state before and after |
| `iot.matter` | status, read: never; command: with approval | `node.json`, `attribute.json`, `command.json` with the cluster before and after |

Limits: a capture lasts up to 10 minutes and 100 000 records; payloads up to 64 KiB; a
simulation up to 5000 devices, 744 hours and 2 million readings. Firmware *build* toolchains
(PlatformIO, ESP-IDF) are not included yet: bring the `.bin` or build it outside.

Libraries (pinned with hashes in `config/toolkit/python/iot.txt`): pyserial 3.5, paho-mqtt
2.2.0, pymodbus 3.16.2, esptool 5.6.0, python-OBD 0.7.3; `adb` from Debian. The acceptance fixture (`scripts/acceptance_iot.py`)
checks a deterministic simulation, a Modbus read without writes, a refused write without
consent and a verified write with consent.

## Android and Android TV over Wi-Fi

1. On the TV: Settings → Device preferences → About → press *Build* seven times; then Developer
   options → *Network debugging* (or *Wireless debugging*). Note the address.
2. Connections → *New: Device* → In rete → *Android / Android TV*, address and port (5555).
   RigHaven creates a key for this connection.
3. The first time a task reads the TV, it shows *Allow USB debugging?* with RigHaven's key:
   tick *Always allow from this computer*.

What is reliable over Wi-Fi: device information, the app list, logs, installing or updating an
APK, disabling or removing preinstalled apps for the user (reversible), rebooting. A full system
update (`sideload`) works only if the TV's recovery accepts ADB on the network; many require USB.
Flashing partitions with fastboot is deliberately not offered: it needs an unlocked bootloader
and can make the TV unusable.

## Vehicle diagnostics (OBD-II)

Works with ELM327 adapters on the standard OBD-II data (engine, emissions, trouble codes):

- **Bluetooth**: pair the adapter with the machine running RigHaven (on Linux `rfcomm bind` gives
  `/dev/rfcomm0`, which the administrator adds to `RIGHAVEN_DEVICES`), then *Attached to this
  machine*. On Windows a Bluetooth adapter is a COM port that WSL cannot see: share it with an
  RFC 2217 server, or use a USB or Wi-Fi adapter.
- **USB**: *Attached to this machine* (`/dev/ttyUSB0`; on Windows via usbipd).
- **Wi-Fi**: *In rete* → *TCP*, usually `192.168.0.10:35000`.

`iot.obd` reads protocol, battery voltage, VIN when available, supported values, live values
(RPM, speed, temperatures…) and stored trouble codes. Clearing codes is a write: it needs your
approval and also resets the readiness monitors. Manufacturer-specific systems (ABS, airbags,
body) are outside standard OBD-II.

## Peripherals of the PC, from the page

On the portable apps everything on the PC is done from **Connections**, with buttons: RigHaven.exe
(or the Linux launcher's agent) runs next to RigHaven, receives the page's requests and carries
them out on the PC, answering in the page.

| Panel | Buttons | What happens on the PC |
|---|---|---|
| PC peripherals | *Show USB peripherals*, *Attach to RigHaven* | usbipd-win shares the peripheral with WSL (Windows asks permission the first time), it is attached at every start and its serial port is offered to connections |
| PC peripherals | *Install the USB component* | installs usbipd-win with winget when it is missing |
| PC peripherals | *Show COM ports*, *Share with RigHaven* | the COM port (for example a paired Bluetooth OBD-II adapter) is carried into RigHaven while it runs |
| PC peripherals (Linux) | *Refresh serial ports* | serial ports plugged in after the start are offered |
| Find devices → Nearby Wi-Fi networks | *Search Wi-Fi networks* | the setup networks of devices not set up yet (Tuya/Smart Life, Tasmota, Shelly, OpenBeken, WLED, ESP/ESPHome) with how to add them to the home Wi-Fi; the PC does not connect to them |
| Find devices → Bluetooth | *Search Bluetooth devices* | nearby and paired devices and Bluetooth LE sensor readings |
| Matter devices | *Turn on Matter* | WSL mirrored networking, firewall rule (Windows asks permission once), automatic restart |

The RigHaven window must stay open (it is RigHaven itself). The commands below remain available
for scripts and for troubleshooting.

### A remote RigHaven

When RigHaven runs on a server, the PC with the devices runs **RigHaven Agent** instead of the
full portable app: the same actions and searches, carried to the server through the agent's
encrypted channel, and device connections *through an agent* reach COM ports and home-network
devices with tunnels. See [RigHaven Agent](AGENT.md).

### The same actions everywhere

Every result of a search, and every saved device connection, offers the same actions:

- **Explore** reads, without a connection and without changing anything.
- **Create connection** saves the device, read only.
- **A setup step** where one is needed.

| Found | Explore reads | Setup step |
|---|---|---|
| Device on the network (or a saved network device) | ports that answer, name, home page | — |
| Any Wi-Fi network | RigHaven for Windows joins it for a few seconds (with the password typed by the owner when it is protected; networks already saved in Windows keep their own profile), reads the page of what answers there (the device's setup page or the router) and goes back; *Create connection* uses that address | *Add to the home Wi-Fi* for Tasmota, Shelly, ESPHome, WLED, OpenBeken; Tuya, Daikin and LG are added with their app |
| Bluetooth device, paired or not (or a saved Bluetooth connection); devices heard now come first, those Windows only remembers are in a closed list; any device that advertises (also a phone with an advertiser app) is listed | services, characteristics and readable values | pair it in Windows for serial devices (OBD-II, HC-05) |
| USB peripheral | busid, VID:PID, state, whether it is a serial port, the chip (CP210x, CH340, FTDI, Espressif native USB…) and whether RigHaven can update its firmware (ESP boards, esptool) | *Attach to RigHaven*, then *Create connection on /dev/ttyUSB0* |
| COM port | name, Bluetooth or not, shared or not | *Share with RigHaven*, then *Create connection* |
| Matter device | name, vendor, state | pairing code, then *Create connection* |

*Show all the PC's devices* lists what Device Manager sees, grouped by USB, Bluetooth and inside
the PC, and says which USB ones can be attached (the others are parts of a peripheral or hubs).
Something plugged into USB only for power does not appear: it is found on the network or over
Bluetooth. Bluetooth services without a Windows driver (for example those of a paired Samsung
phone) are used through their COM port, or the phone over the network with ADB.

*Listen to the network* asks once, as a phone app does, for the devices that announce
themselves (mDNS / Bonjour and SSDP / UPnP) and lists them with name, services and server, with
Explore and Create connection: it finds devices that answer no port of the search.

*Record the traffic* runs Windows' own packet monitor (`pktmon`, administrator rights: Windows
asks) on the PC's network adapters for 30 seconds to 5 minutes, then summarises the
conversations (local address, remote address with the name it was looked up as, protocol and
port, bytes) and keeps the recording as `.pcapng` for Wireshark. The PC's Wi-Fi adapter only
receives the PC's own traffic (Windows has no monitor mode); to see what one device sends, for
example to its cloud, connect it to Windows' Mobile hotspot and record while using it. Only
the PC's own adapters are recorded. Available on Windows.

The owner decides what to explore; RigHaven does not filter. The chat has the same actions:
`harness_explore_device` (network, Wi-Fi, Bluetooth, USB), `harness_setup_device` and
`harness_bluetooth`. From the chat, Wi-Fi networks that need a password are explored only from
the page, because a password is never asked in the chat.

The setup and explore requests per firmware follow their documented setup pages; they are
unit-tested against simulated devices, not yet against every real one.

### Bluetooth LE devices

Devices that are commanded over Bluetooth LE (LED controllers, lamps, scales, boards with an
HM-10 or ESP32 BLE module) are reached through the PC's Bluetooth by RigHaven for Windows:

- **Explore** next to a device of the Bluetooth search, or on its connection, lists services and
  characteristics with the values that can be read (name, manufacturer, firmware, battery).
  Reading needs no connection and no approval; the chat does the same with `harness_bluetooth`
  and the address.
- **Create connection** saves it (`transport: bluetooth`, read only). To command the device the
  owner allows writing on it and assigns it to the task; each write of bytes to one
  characteristic is then approved one by one in the task card (`harness_device_change` action
  `send`, `encoding: hex`, `address: service/characteristic`) and used once.
- The page cannot write by itself: writes go only through the chat, after the approval.
- Many commercial devices encrypt their commands with vendor keys: they can be read, not
  commanded, without the vendor's key. Available on Windows; the Linux launcher does not offer it yet.

### Asking the chat

The same steps can be asked in the chat, in plain words ("find my IR remote", "I plugged a board
into the USB port", "use my Bluetooth OBD adapter"):

- `harness_find_devices` identifies what is around the PC: home network, nearby Wi-Fi setup
  networks, Bluetooth (devices and BLE sensors), USB peripherals and COM ports of the PC, serial
  ports already offered. It only reads, and explains what each device probably is.
- `harness_setup_device` prepares the device the owner chose and creates its connection, **read
  only**: USB peripheral (attached through usbipd, Windows asks permission the first time; its
  serial port is offered without restarting RigHaven), COM port (shared while RigHaven runs),
  network device (address and protocol), Matter device (with the pairing code given by the owner).
  Tuya devices also need the device ID and local key: the chat never asks for them, the owner
  enters them in Connections. Writing stays off until the owner enables it on the connection, and
  every write is still approved one by one.

## Finding devices

Most Wi-Fi gadgets (plugs, bulbs, IR remotes, sensors) use USB only for power: they are reached
on the network, not over USB. In **Connections → Find devices**:

- **Network.** The portable apps pass the PC's local networks to RigHaven (inside WSL or a
  container the Wi-Fi network is not visible); elsewhere type it, for example `192.168.1.0/24`.
  *Search this network* tries a TCP connection to ports 80, 443, 502, 1883, 5555, 6053, 6668,
  8080 and 8883 and the ports of TVs, phones and cameras, of each address (at most 4096); with RigHaven for Windows open, the PC's own neighbour table (ARP) adds every other device of its network with its MAC address and maker, even without open ports and reads the home page of the hosts that answer
  on HTTP. Nothing is written to any device; only private networks, and only when private
  networks are allowed. Results are identified when possible (Tuya/Smart Life on 6668, ESPHome,
  Tasmota, OpenBeken, Shelly, WLED, Home Assistant, MQTT brokers, Android/ADB, Modbus TCP) and
  *Create connection* opens the device form already filled in.
- **Tuya / Smart Life.** Create the connection with protocol *Tuya / Smart Life*: the device ID (Smart
  Life app → device → pencil → Device information → Virtual ID), its *local key* (from the Tuya
  developer platform iot.tuya.com after linking the Smart Life app, or the `tinytuya wizard` tool)
  and the protocol version (3.3 for most devices, 3.4/3.5 for newer ones). `iot.tuya` then reads the
  data points and, with your approval of each command, changes them (for example `{"1": true}`
  switches on). Nothing goes through the Tuya cloud during use.
- **Bluetooth.** The PC's Bluetooth does not reach inside RigHaven: run `RigHaven.exe bluetooth`
  (Windows, about 20 seconds) or `./righaven bluetooth` (Linux, BlueZ `bluetoothctl`). Nearby and
  paired devices, and the COM ports Windows created for paired devices, are listed with what
  RigHaven can do with them, and appear in *Find devices*. Nothing is paired or written. 
- **Bluetooth LE sensors.** Sensors that never connect (thermometers, hygrometers, door and motion
  sensors) broadcast their readings. The same Bluetooth search listens for 15 seconds and RigHaven
  decodes the open formats: BTHome v2 (Shelly BLU and custom firmwares), ATC1441 and pvvx (Xiaomi
  LYWSD03MMC with a custom firmware) and Xiaomi MiBeacon when not encrypted. Readings appear in
  *Find devices*; `RigHaven.exe bluetooth 5` repeats every 5 minutes and *Download the readings
  history (CSV)* gives the series (the latest 50 000 readings) to use in a project. Encrypted
  MiBeacon data needs the sensor's bind key or an open firmware.
- **Windows COM ports** (a paired Bluetooth OBD-II adapter, or any serial device Windows shows as
  COM): `RigHaven.exe serial` lists them and shares the chosen one at every start. RigHaven.exe
  opens the port and carries it to a TCP port inside the distribution that only RigHaven's
  containers reach; *Find devices → Serial ports shared by the PC* creates the connection
  (serial, raw TCP). One task uses the port at a time; the speed is the one set in Windows.

## Matter devices

The portable apps include an optional **Matter controller** (the official `python-matter-server`
image, pinned by digest). Matter finds devices with multicast and IPv6 on the home network, so
the controller uses the host network and listens only on the RigHaven network gateway
(`172.30.42.1:5580`), reached by RigHaven's containers.

- **Windows 11 (22H2 or later):** `RigHaven.exe matter enable` asks for confirmation, sets WSL
  "mirrored" networking in `%UserProfile%\.wslconfig` (it applies to every WSL distribution; the
  previous file is kept as `.wslconfig.righaven-backup`), adds a Hyper-V firewall rule for UDP 5353
  and 5540 (one administrator prompt) and restarts WSL. Windows 10 has no mirrored networking.
- **Linux:** `./righaven --matter`.
- **Joining a device:** RigHaven joins devices already set up in Alexa, SmartThings, Google Home or
  Apple Home: in that app choose *share with other hubs/services* (or *turn on pairing mode*) and
  enter the 11-digit code in *Connections → Matter devices*. The device keeps working in the other
  app (Matter multi-admin). New devices are first set up with their app: setting them up from
  scratch needs Bluetooth, which does not reach RigHaven.
- **Using it:** the page shows each device, its state (on/off, level, temperature, humidity,
  occupancy, contact, battery) with *On*/*Off*, and *Create connection*; tasks use `iot.matter`.
- **Limits:** any process in RigHaven's containers can reach the controller's API, which has no
  password of its own; turn the controller off with `RigHaven.exe matter disable` when you do not
  need it. Not verified with real Matter devices yet.

## Windows portable app

Devices on the network work as on the server. For a USB device on the same PC (serial adapter,
ESP/Arduino board, USB OBD-II adapter):

1. Run `RigHaven.exe usb`. It lists the USB peripherals of the PC (likely serial ones marked `*`)
   and attaches the one you choose to RigHaven's WSL. The first time it offers to install
   [usbipd-win](https://github.com/dorssel/usbipd-win) with winget, and sharing a peripheral asks
   Windows for administrator permission once.
2. Its serial port (`/dev/ttyUSB0`, `/dev/ttyACM0`) is offered to connections automatically
   (`--devices auto`, the default; `--devices none` turns it off, a list such as
   `--devices /dev/ttyUSB0` restricts it). A running RigHaven is refreshed to see it; running
   assignments are interrupted.
3. In Connections create *New: Device* → *Attached to this machine* and pick it.

The peripheral is attached again at every start while it is plugged in; `RigHaven.exe usb forget
1-4` stops that. Bluetooth adapters that Windows shows only as a COM port cannot be attached this
way: use a USB or Wi-Fi adapter.

## Linux portable app

Serial ports plugged in when RigHaven starts are offered automatically (`--devices auto`); after
plugging one in, run `./righaven` again. The user running Docker must be allowed to use them.
