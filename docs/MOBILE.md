# Phones and the installable app

RigHaven has no separate mobile backend: a phone opens the same RigHaven, on the server or on
a PC, in the browser or as an installed app.

## Installing the app

- **Android (Chrome, Edge, Samsung Internet):** open RigHaven, then the menu → *Install app*
  (or *Add to Home screen*). It opens full screen with its own icon.
- **iPhone and iPad (Safari):** Share → *Add to Home Screen*.
- **Desktop (Chrome, Edge):** the install icon in the address bar.

The app is a web app manifest (`/manifest.webmanifest`) with icons in `/rh-app/`. Nothing is
cached offline: every page and every answer still comes from your RigHaven, with the same
account and sign-in. On the server, only the manifest and its icons are served without the
password gate, because browsers fetch them without credentials; they contain no data.
Installing needs HTTPS (the server) or `127.0.0.1` on the same device.

## Using RigHaven on a phone

The project card above the chat collapses to its status line (**Collapse** / **Show
project**). On a narrow screen it starts collapsed, so the chat and the team's questions
stay visible; the choice is remembered by the browser. The project details open in a full
screen panel.

## Reaching a PC copy from the phone

The portable apps listen on `127.0.0.1` only. To use a PC copy from a phone on the same
network, start it with the PC's address, for example `RigHaven.exe --bind 192.168.1.20` or
`./righaven --bind 192.168.1.20`, and open `http://192.168.1.20:2026` on the phone. The
launcher warns that RigHaven is then reachable from the network. Browsers install apps only
from HTTPS or `127.0.0.1`, so over plain HTTP on the network the phone uses it in the browser;
for the installed app use the server deployment (HTTPS).
