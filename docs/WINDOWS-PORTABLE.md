# Windows portable app

`RigHaven-<version>-windows-x64-portable.zip` runs a complete RigHaven on one Windows
PC, without installing Docker Desktop or deploying a server. It is attached to every
verified release, next to the Hostinger Compose.

## What runs where

```
RigHaven.exe (Windows, launcher)
  └─ WSL 2 distribution "RigHaven" (Alpine + Docker engine; disk in data\wsl\ext4.vhdx)
       └─ the release Compose: gateway, frontend, redis, local proxy (127.0.0.1:2026)
            └─ private nested runtime (runtime-docker)
                 └─ isolated containers of each role, exactly as on the server
```

- **Same software as the server.** `scripts/prepare_desktop.py` takes the sealed
  release (`compose.hostinger.yaml` and `runtime-manifest.json`), refuses it if it
  differs from what CI verified, removes the Traefik routing and adds the release's own
  proxy image with the routes of `docker/Caddyfile`. The image digests do not change.
- **Same isolation.** Roles still run in their own containers inside the private
  runtime, inside a dedicated WSL 2 virtual machine. Nothing runs directly on Windows.
- **Local only.** RigHaven is opened at `http://127.0.0.1:2026` (never `localhost`, which some
  PCs do not resolve). `RigHaven.exe` itself serves that address and carries each connection
  into the distribution, straight to the proxy's address on the Docker network (ports
  published on 127.0.0.1, here the inner port 32026 for 2026, depend on NAT rules that some
  WSL kernels do not apply, and remain only a fallback): this works in WSL NAT and mirrored
  networking alike and never depends on WSL port forwarding. "Ready" is printed only after the address answers from Windows; if Windows
  refuses the port, the error is shown and another `--port` can be chosen. `--bind IP` serves
  another address of the PC, for example its network address to reach RigHaven from other
  devices; the launcher warns that it is then exposed, and the sign-in address follows it.
- **Secrets stay in the distribution.** The installation secret is generated inside
  WSL (`/opt/righaven/.env`) and never written to the Windows folder.

## Using it

1. Extract the ZIP to an NTFS folder, for example `C:\RigHaven`.
2. Double-click `RigHaven.exe`. On the first start it imports the distribution (about a
   minute) and downloads the verified images (about 1 GB, once).
3. The browser opens `http://127.0.0.1:2026`. Keep the window open; Ctrl+C stops RigHaven
   cleanly. Closing the window also stops it, in the background.

Requirements: Windows 10 22H2 or 11 (64-bit) with virtualization enabled, WSL 2
(`RigHaven.exe` offers `wsl --install --no-distribution` once, as administrator, then a
restart), 8 GB RAM (16 GB recommended), 20 GB free disk. WSL memory follows the global
`%UserProfile%\.wslconfig`; RigHaven does not change it.

| Command | Purpose |
|---|---|
| `RigHaven.exe` / `start` | Start and open the browser; `--no-browser`, `--port 2027`, `--bind 127.0.0.1`, `--devices auto|none|/dev/ttyUSB0` (remembered) |
| `stop`, `status`, `logs [service]` | Stop, state of the services, logs (`gateway` by default) |
| `doctor` | WSL version, distribution, port, the app files against `release.json`, and the three legs of the connection (proxy inside WSL, relay, Windows address) |
| `shell` | Administrator shell in the distribution, in `/opt/righaven` |
| `repair` | Reattach `data\wsl\ext4.vhdx` after moving the folder (typed confirmation) |
| `remove` | Delete the distribution and all data of this copy (typed confirmation) |
| `usb` | List the USB peripherals and attach one to RigHaven (remembered); `usb forget BUSID` |
| `bluetooth [N]` | Search nearby and paired Bluetooth devices and read Bluetooth LE sensors (shown in Connections → Find devices); with N, repeat every N minutes |
| `matter enable\|disable\|status` | Matter controller: WSL mirrored networking, Hyper-V firewall rule, controller started with RigHaven (Windows 11) |
| `serial` | Share a Windows COM port (for example a Bluetooth OBD-II adapter) with RigHaven at every start; `serial forget COM5` |

**Peripherals from the page:** USB peripherals, COM ports, Bluetooth and Matter are handled from
*Connections* with buttons; RigHaven.exe carries out the requests on the PC while its window is open
([details](IOT.md#peripherals-of-the-pc-from-the-page)). The `usb`, `serial`, `bluetooth` and `matter`
commands do the same from a terminal.

**Images:** the first start downloads the verified images one by one (about 1 GB, progress
shown as `[n/5]`); later starts download nothing. After an update only the images that changed
are downloaded (layers already present are reused) and images of earlier versions are deleted
once the new version is running. The work environment of the roles is prepared by RigHaven on
the first start and reused afterwards.

**Updating:** stop RigHaven, replace `RigHaven.exe` and the `app` folder with those of the
new ZIP, keep `data`, start again. Every start copies the scripts and the release files
into the distribution, so the new version is used with the existing data
([data across releases](PERSISTENT-DATA.md)).

**Two copies on one PC:** start the second with `--name RigHaven-2 --port 2027`; each
copy records its folder in the distribution and refuses to use another copy's one.

## Build and verification

`.github/workflows/desktop-windows.yml` runs after every published release (stable and
PR candidates) and can be started by hand with a release tag:

1. launcher tests (`go vet`, `go test`) on Linux and again on Windows;
2. `prepare_desktop.py` validates the sealed release and writes `app/compose.yaml`,
   `app/Caddyfile`, `app/release.json` (with file fingerprints);
3. `desktop/windows/rootfs` is built and exported as `app/rootfs.tar`;
4. the exported distribution is started in a privileged container exactly as WSL does:
   `righaven-install`, `righaven-selftest` (engine and nested runtime), `righaven-start`,
   health check through the local proxy, `righaven-stop`;
5. on Windows the packaged `RigHaven.exe` runs `version` and `doctor`, which must report
   the packaged files as unchanged;
6. the ZIP and its `.sha256` are attached to the release.

Sources: `desktop/windows/launcher` (Go, standard library only),
`desktop/windows/rootfs` (distribution and `righaven-*` scripts),
`scripts/prepare_desktop.py`, `tests/test_prepare_desktop.py`.

## Current limits

- **x64 only.** The release images are built for `linux/amd64`; Windows on ARM would run
  them emulated. An ARM64 package needs multi-architecture images first.
- **Not signed yet.** Windows SmartScreen shows a warning on the first start ("More info"
  → "Run anyway"). Signing needs a code-signing certificate.
- **Console window.** The launcher is a console application that opens the browser; a
  native window and a tray icon can come later without changing the runtime.
- **Networks.** Mapping and checks of the PC's network go through the WSL 2 NAT: hosts and
  services are reachable, MAC addresses and vendors are not visible.
- **Devices.** Network devices work as on the server. USB and serial devices on the same PC are
  attached with `RigHaven.exe usb` (usbipd-win) and offered automatically; see
  [Devices and IoT](IOT.md#windows-portable-app). Bluetooth is not supported yet.
