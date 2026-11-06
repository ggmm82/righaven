# Changelog

## 1.0.0

First stable version.

- **RigHaven Agent for Windows.** A small executable, with no WSL and no Docker, that pairs once
  with a code from the server's web interface and puts the PC's Bluetooth, BLE, Wi-Fi, COM ports,
  devices of the PC and of the home network, network listening and traffic recording at the
  disposal of a RigHaven server (for example on a VPS). Device connections *through an agent*
  reach COM ports and home-network devices with tunnels.
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
