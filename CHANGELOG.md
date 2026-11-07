# Changelog

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
