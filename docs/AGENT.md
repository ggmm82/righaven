# RigHaven Agent: your PC and on-premise gateway for a RigHaven server

RigHaven can run on a server (for example a VPS, installed from `compose.hostinger.yaml` of a
release) with its own web interface: chat, projects, environments, data and executions. A server
cannot see your Bluetooth, your Wi-Fi, the boards plugged into your PC or the devices of your
home network. **RigHaven Agent** is the small Windows program that puts them at the server's
disposal, with no WSL and no Docker on the PC.

```
 Browser / phone ──HTTPS──▶  VPS: proxy ─ web interface ─ gateway ─ workers
                                             ▲  encrypted WebSocket, opened by the PC
 Home PC: RigHaven Agent ────────────────────┘
   ├─ Bluetooth, BLE, Wi-Fi, COM ports, devices of the PC and of the home network
   ├─ network listening, traffic recording, port search of the home network
   └─ tunnels: a COM port, a home-network device or an on-premise database to the server's workers
```

The PC connects to the server itself: no port of the home router is opened.

## Connect a PC

1. On the server open **Connections → Connected PCs (RigHaven Agent)**, type a name ("Home PC")
   and press **Connect a PC**. The page shows the server address (on Hostinger the HTTPS address
   Traefik serves, `https://<project>.<TRAEFIK_HOST>`) and a code valid ten minutes, usable once.
2. Download `RigHaven-Agent-windows-x64.exe` from the release (the link is on the page) and start
   it. On first start Windows may show the SmartScreen warning for an unsigned program: *More
   info → Run anyway*.
3. Type the server address and the code. The page notices the PC and lists it as connected.

RigHaven Agent then starts at every Windows sign-in (`RigHaven-Agent.exe agent autostart off` to
stop that) and reconnects by itself when the network or the server comes back.

| Command | What it does |
|---|---|
| `RigHaven-Agent.exe` | pairs if needed, then runs |
| `RigHaven-Agent.exe agent link SERVER CODE` | pairs this PC |
| `RigHaven-Agent.exe agent run` | runs (used at sign-in) |
| `RigHaven-Agent.exe agent unlink` | forgets the server |
| `RigHaven-Agent.exe agent autostart on\|off` | starts with Windows or not |

## Use it

In **Connections**, *Act on the PC* chooses the PC the device sections act on: the PC this server
runs on (administrators only) or one of your agents. With an agent chosen:

- **Find devices** searches the agent's home network (port search and the PC's neighbour table),
  its Wi-Fi networks and its Bluetooth devices; *Explore* and *Create connection* work as on a
  local PC, and *Create connection* proposes the device **through this agent**.
- **PC peripherals** lists the agent's COM ports (a USB board is a COM port on Windows) and all
  its devices.
- **Listen to the network** and **Record the traffic** run on the agent; the recording is sent to
  the server for download.
- The chat uses the same PC: the agent named, otherwise the PC of the server when it is there,
  otherwise your agent that is connected.

## Connections to services: cloud or on premise

Every connection is a connection to a **service**: a database, a broker or a device on the
network (MQTT, HTTP, Modbus, Android, Tuya, TCP), a serial or USB port, a Bluetooth LE device, a
network to map. *New connection to a service* asks first **where the service is**, then which
service; the list of connections is grouped the same way.

| Where the service is | What RigHaven does | Services |
|---|---|---|
| **Cloud (internet)** | reaches it from the server | databases (Azure SQL, Fabric, managed Postgres…), Microsoft Entra ID, network services with a public address, networks to map |
| **On premise · network or machine of this server** | reaches it from the server's own network or machine (on the PC with portable RigHaven: the home or office network) | databases and network services with a private address, serial ports (attached or shared over RFC 2217), Bluetooth LE through the launcher, networks to map, Matter |
| **On premise · through «PC»** | reaches it through that PC's RigHaven Agent, with a tunnel | databases and network services of that PC's network (a private IP or an internal name such as `sql01.office.local`, as that PC sees it), its COM/USB ports, its Bluetooth LE |

The place is part of the connection: change it in the form and the fields follow (a COM port
through an agent, a serial server from the server; user and password for a database through an
agent). What *Find devices*, *PC peripherals* and *Matter devices* find is on premise: *Create
connection* proposes the PC being worked on, or this server.

When a task uses a connection through an agent, the server opens a tunnel: the worker receives an
address of the server, the agent opens the COM port or the host and carries the bytes. Reading
and writing follow the usual rules: the connection is read only until you allow writing, and each
write is approved by you, one by one.

**Test** of a connection through an agent runs on that PC: the PC resolves the name and opens the
port, so the result is what the tasks will find. When a task uses the connection, the server opens
a tunnel to the agent and the task receives the tunnel's address; for SQL Server the certificate
is checked against the real server name (`hostNameInCertificate`). An internal name must resolve,
on the PC, to private addresses only: a name that leads to the internet is refused.

**Several PCs.** Each agent has a name. The page acts on the PC chosen in *Act on the PC*; a
connection always uses the PC it names; the chat uses the PC the owner names (by name or ID), the
PC of the server when it is there, the only agent connected, and with several connected it asks
which one instead of choosing.

## Security

- **One owner.** An agent belongs to the user who paired it. Its actions, searches, recordings
  and tunnels are available to that user only; the PC the server runs on is for administrators
  only.
- **Pairing.** The code is valid ten minutes and once; wrong codes are throttled. The server keeps
  only a hash of the agent's token; the PC keeps the token encrypted for the Windows account
  (DPAPI). *Revoke* on the page disconnects the agent and invalidates its token at once.
- **Outside the site password.** The site password protects the web interface (Caddy's in the
  portable release; on Hostinger, where Traefik routes `/api` straight to the gateway, the
  gateway's own login). The agent's endpoints (`/api/webhooks/righaven-agent/pair`, `/connect`,
  `/capture`) authenticate themselves, with the code and with the token in the
  `X-RigHaven-Agent` header. Traefik and Caddy both carry the WebSocket of `/connect` as it is:
  no extra router, label or port is needed.
- **What the agent opens.** Tunnels reach only COM ports of the PC and private addresses of its
  networks, never the internet. Wi-Fi passwords typed in the page go to the agent for that action
  only and are not stored.
- **Activity.** Every action asked to an agent, every tunnel, connection and disconnection is
  recorded in *Show the activity of connected PCs*.

## Limits

- Windows only for now; the Linux and phone agents are planned.
- USB peripherals are used through their COM port (USB-serial boards, ESP, Arduino); other USB
  classes are not forwarded.
- Matter needs the controller in the home network: it stays available with the full portable
  RigHaven on the PC, not through an agent.
- On-premise databases use user and password: Microsoft and Entra ID sign-in are for cloud
  databases, from the server. *Networks to map* (vulnerability scans) run from the server; the
  home network of an agent is searched with *Find devices*.
- The tunnel port is on the server's internal network, where the workers run; on a server shared
  by several users the database account (or the device) is what protects the data, as on any
  network connection.
- Tunnels carry TCP and serial bytes; in the *allowlist* egress mode workers reach the internet
  only through the egress proxy, as for every device connection.
- Not yet tested end to end on a real VPS with a real PC: the protocol, pairing, actions and
  tunnels are tested with simulated peers on both sides.
