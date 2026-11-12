# Changelog

## 1.2.0

- **Bluetooth is a transport.** A Bluetooth connection (one per device, classic or LE) reaches a
  task like a serial port: RigHaven Agent on the PC or phone opens it as a byte channel (classic
  through its serial profile, LE through one write characteristic and the notifications of
  another, the connection's optional channel profile) through the agents' tunnel, and any tool of
  the environment speaks its own protocol over it. No protocol knowledge in the core: the
  OBD-specific chat action is gone, `iot.obd` and manual sessions (`iot.send` with `reply_until`)
  work on the channel. Without a task, the chat inspects, reads and exchanges bytes (end marker
  and timeout) and the page has a manual terminal; writes keep their approvals. Older agents keep
  today's behaviour. Needs the new Agent and app.
- **Bluetooth channels in practice.** The owner's zone of trust now covers writes inside a task too
  (manual sessions such as ATZ, ATRV, ATSP no longer need one approval each); the chat finds the
  device's channel the way the agent does and keeps it on the connection, so the chat and the
  tasks use the same characteristics; the chat waits while a task holds the device; `iot.obd`
  returns the adapter's version and voltage when the vehicle does not answer (a socket with power
  and no data lines is reported as a physical limit).
- **Replies in the same connection.** `iot.send` on MQTT can subscribe to the topic where the
  device answers (`reply_topic`, e.g. `stat/plug/#`) before publishing, so an immediate answer is
  not missed; serial and TCP replies can end at a prompt (`reply_until`, e.g. `>` or `OK`) instead
  of waiting the whole `reply_seconds`, and bare carriage returns split the lines.
- **RigHaven for Android.** The app shows the server's web interface and runs RigHaven Agent on
  the phone as a foreground service: Bluetooth LE search, exploration and approved writes, nearby
  Wi-Fi networks, search of the phone's network, connection tests and tunnels to hosts of its
  private network. Pairing with the same code as a PC, token encrypted with the Android Keystore.
  `RigHaven-android.apk` in the release.
- **Android: no unpairing on outages.** A proxy 404 or a server restart no longer drops the
  pairing: only the server's `agent_revoked` answer does, and the address stays filled in.
- **Android: stable signing.** The CI signs the APK with a key from the repository secrets, so a
  new version installs over the previous one.

## 1.1.0

- **On-premise images stay on the machine.** An environment placed on a machine is prepared there
  (same installer and checks, `docker commit`), never in the server's cache; each place reuses
  only its own images (the machine starts from its closest one), and the machine removes its least
  used images beyond `agent node on --images GiB` (default 40).
- **On-premise environments.** Coordination, projects and data stay on the server; an environment
  can run its tasks on a dedicated machine of the owner (*Cloud*, *On premise · «machine»* or
  *Automatic*). RigHaven Agent becomes a compute node with `agent node on`: it declares CPU,
  memory and tasks at a time, checks each sandbox command against its own rules, runs it with its
  Docker and sends progress and results back. Per-node resources, live progress, stop, results
  kept while offline. `RigHaven-Agent-linux-x64` for Linux machines.

## 1.0.0

First stable version.

- **RigHaven Agent for Windows.** A small executable, with no WSL and no Docker, that pairs once
  with a code from the server's web interface and puts the PC's Bluetooth, BLE, Wi-Fi, COM ports,
  devices of the PC and of the home network, network listening and traffic recording at the
  disposal of a RigHaven server (for example on a VPS). Device connections *through an agent*
  reach COM ports and home-network devices with tunnels.
- **Connections to services, cloud or on premise.** A new connection asks where the service is
  (cloud, on premise next to this server, on premise through «PC») and then which service:
  database, network service, serial/USB port, Bluetooth LE, network to map. The list is grouped
  by place.
- **On-premise connection gateway.** Postgres, SQL Server, MySQL and Oracle databases of an
  office or home network are reached *through* the agent of a PC of that network: a private
  address or an internal name the PC resolves, a test run from that PC, a tunnel only while a
  task uses it, no port opened. Cloud databases keep going from the server.
- **The chat asks which PC.** With several of the owner's PCs connected, the chat's device
  tools take the PC by name and ask for it instead of choosing one.
- **Connected PCs in the web interface.** Connect a PC with a code, see its state, revoke it,
  read its activity, choose the PC the device sections act on.
- **Permissions on actions on the PC.** The PC the server runs on is for administrators, an
  agent for its owner; every action asked to an agent is recorded.
- **Devices.** Searches of the network (ports, neighbour table, TVs and phones), Wi-Fi (setup
  networks, exploration, home Wi-Fi setup for open firmwares), Bluetooth (devices heard now,
  makers, BLE GATT exploration, approved writes), USB (chips, attach, connection on the port),
  COM ports, all the PC's devices, network listening (mDNS, UPnP) and traffic recording (pktmon).
- **Same actions everywhere.** Explore, Create connection and the setup step on every result
  and saved connection, from the page and from the chat.

## 0.1.0

The code of RigHaven up to the device features above, published as the first version of this
repository: Community edition (server, Windows and Linux portable apps), projects, environments,
recipes, Policy Book, connections and approvals.
