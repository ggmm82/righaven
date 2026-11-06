# Linux portable app

`RigHaven-<version>-linux-x64-portable.tar.gz` runs a complete RigHaven on one Linux PC
with the Docker engine already installed there. It is attached to every verified release,
next to the Hostinger Compose and the [Windows portable app](WINDOWS-PORTABLE.md).

## What runs where

```
./righaven (POSIX shell launcher, next to app/ and data/)
  └─ Docker Engine of the PC, Compose project "righaven"
       └─ the release Compose: gateway, frontend, redis, local proxy (127.0.0.1:2026)
            └─ private nested runtime (runtime-docker)
                 └─ isolated containers of each role, exactly as on the server
```

- **Same software as the server and as Windows.** `app/compose.yaml`, `app/Caddyfile` and
  `app/release.json` are produced by `scripts/prepare_desktop.py` from the sealed release,
  exactly as for Windows; the image digests do not change. `doctor` checks the files against
  `release.json`.
- **No virtual machine.** Linux runs the containers natively, so there is no WSL and no
  relay: the proxy publishes `127.0.0.1:2026` (or the address chosen with `--bind`) directly.
- **Secrets stay local.** The internal secret is generated once in `data/.env` (mode 600);
  the settings chosen with the options are remembered in `data/settings`.
- **The PC's other containers are left alone.** After an update only the images of earlier
  RigHaven versions of this copy are deleted (listed in `data/images`), never other images.

## Using it

1. Extract the archive, for example to `~/RigHaven`.
2. Run `./righaven`. The first start downloads the verified images one by one (about 1 GB,
   progress `[n/4]`), starts the services and waits until `http://127.0.0.1:2026` answers.
3. The browser opens (when a desktop session is available). The services keep running in
   the background; `./righaven stop` stops them. Services that are not stopped come back
   with Docker after a restart of the PC (restart policy `unless-stopped`).

Requirements: Linux x64, Docker Engine 24+ with the Compose plugin 2.20+, a user in the
`docker` group (or `sudo`), 8 GB RAM (16 GB recommended), 20 GB free disk. Rootless Docker
is not enough: the private runtime of the roles is a privileged container, as on the server.

| Command | Purpose |
|---|---|
| `./righaven` / `start` | Start and open the browser; `--no-browser`, `--port 2027`, `--bind IP`, `--devices /dev/ttyUSB0`, `--name righaven2` (remembered) |
| `stop`, `status`, `logs [service]` | Stop, state of the services, logs (`gateway` by default) |
| `doctor` | Version, app files against `release.json`, Docker and Compose versions, services and address |
| `bluetooth` | Search nearby Bluetooth devices (BlueZ) and show them in Connections → Find devices |
| `remove` | Delete the containers, volumes and images of this copy (typed confirmation, `--yes` to skip) |

**Devices.** Serial and USB devices of the PC are offered with `--devices /dev/ttyUSB0`
(see [Devices and IoT](IOT.md)); the user running Docker must be allowed to use them.
**Two copies:** `--name righaven2 --port 2027` gives the second copy its own Compose
project and volumes.

**Updating:** `./righaven stop`, replace `righaven` and `app/` with those of the new archive,
keep `data/`, run `./righaven` again ([data across releases](PERSISTENT-DATA.md)).

## Build and verification

The `linux` job of `.github/workflows/desktop-windows.yml` runs after every published release:
`shellcheck` on the launcher, `prepare_desktop.py` on the sealed release, then on the runner's
Docker engine `doctor` (files unchanged), `start`, health and page checks through the proxy, the
installable-app manifest and icons, a second `start` that finds RigHaven already running,
`status` and `stop`. The archive and its `.sha256` are attached to the release.

## Current limits

- **x64 only**, like the release images.
- **macOS** needs a Linux virtual machine and arm64 images for Apple silicon; it is not
  packaged yet. **FreeBSD** has no Docker engine.
