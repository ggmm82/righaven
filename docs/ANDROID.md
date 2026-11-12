# RigHaven for Android

The Android app is two things in one:

- **the web interface of your RigHaven server** (chat, projects, connections, environments), in
  the app instead of the browser;
- **RigHaven Agent on the phone**: like the Windows agent, it puts the phone's Bluetooth LE, Wi-Fi
  and network at the server's disposal, so the server reaches what is next to the phone.

```
 Server (VPS) ── web interface ──▶ the app's screen
   ▲  encrypted WebSocket, opened by the phone
 Phone: RigHaven Agent (foreground service)
   ├─ Bluetooth LE: search, exploration, reads; writes approved by you, one by one
   ├─ nearby Wi-Fi networks
   ├─ search of the phone's network, test of a host and port
   └─ tunnels: a device of the phone's network to the server's workers
```

## Install and pair

1. Download `RigHaven-android.apk` from the release (the link is also in **Connections → Connected
   PCs** when you connect a PC) and open it. Android asks to allow installing apps from that
   source: allow it once.
2. On the server open **Connections → Connected PCs**, type a name ("Phone") and press **Connect a
   PC**.
3. In the app type the server address and the code. The app saves its access encrypted with a key
   of the Android Keystore, opens the web interface and starts the agent.
4. Allow **Nearby devices** (Bluetooth), **Location** (Android needs it to list Wi-Fi networks) and
   **Notifications** (the agent's notification).

In the page, *Act on the PC* now lists the phone: Find devices, Bluetooth and the network searches
work on it, and *Create connection* proposes the connection *on premise, through «Phone»*.

## The agent in the background

The agent is a **foreground service**: Android shows its notification, *RigHaven Agent active*, for
as long as it runs, and it reconnects by itself. The notification says the real state (connected,
retrying, the action the server asked while it runs, then its outcome) and has two buttons that
work with the app closed: **Stop** turns the agent off (start it again from the app's Agent menu)
and **Log** opens the activity log. The **Agent** button of the app stops or starts it,
opens the permissions and the battery settings: if the phone stops the agent when the screen is
off, let RigHaven work in the background there.

| Action | On the phone |
|---|---|
| Bluetooth search | Bluetooth LE devices heard in 8 seconds (name, signal, maker, sensor data) and the paired ones |
| Bluetooth exploration and reads | services, characteristics, readable values |
| Bluetooth writes | only the writes you approved on the server, one by one (with the device's notified answer when asked) |
| Bluetooth devices as channels | a Bluetooth device of the phone (classic or LE) opened as a byte channel for the server's tools, one client at a time |
| Wi-Fi networks | the nearby networks (Android allows a few new scans every two minutes) |
| Network search | the usual ports of devices, TVs and phones in the phone's network |
| Test of a connection | the host and port answer from the phone |
| Tunnels | a host of the phone's private network, for the server's workers |

Tunnels and tests reach only private addresses of the phone's networks, as on Windows: an internal
name that resolves to the internet is refused.

## Activity log

**Agent → Activity log** shows what the agent did on this phone, newest first, kept on the phone
(the last 300 lines): connections to the server and why they ended (HTTP code or network error),
each action the server asked with its duration and outcome (for example *✓ net-scan · 45.2 s · 2
devices*, *✗ ble-inspect · the device disconnected*), tunnels opened or refused, retries. It is
readable even when the server does not answer. The server keeps its own record of every agent's
actions in **Connections → Connected PCs → Show the activity of connected PCs**.

## Server outages and revocation

The phone stays paired while the server is down, restarting or behind a proxy error page (Traefik
answers 404 while the gateway is not running): the agent keeps retrying. Only when the server
itself answers `agent_revoked` on `/api/webhooks/righaven-agent/status` (you pressed *Revoke* in
Connected PCs) does the app ask for a new code, with the server address already filled in.

## Updates

Download the new `RigHaven-android.apk` from the release and open it: it installs over the
previous version and keeps the pairing.

Updates install over the previous version only if both are signed with the same key. The CI signs
the APK with the project key held in the repository secrets:

| Secret | Value |
|---|---|
| `ANDROID_KEYSTORE_B64` | the keystore (PKCS12), base64 on one line |
| `ANDROID_KEYSTORE_PASSWORD` | its password |
| `ANDROID_KEY_ALIAS` | the key's alias |
| `ANDROID_KEY_PASSWORD` | the key's password (the keystore's if empty) |

Without them the APK is signed with a throwaway debug key and the CI warns: a later version signed
with the project key needs one uninstall (and a new pairing). Keep the keystore safe: losing it
means every phone must uninstall to move to a new key.

## Limits

- USB (OTG) serial boards, NFC and traffic recording are not available on the phone yet.
- Wi-Fi provisioning of devices in setup mode and Wi-Fi exploration stay on the Windows agent.
- The agent logic (protocol, tunnels, network search) is tested on the JVM; the app is built by
  the CI. Not yet tried on a real phone against a real server.
