# On-premise environments: tasks on your dedicated machines

RigHaven on a server (a VPS) keeps **coordination, projects, data and approvals** in the cloud. An
environment can also **run its tasks on a dedicated machine of yours** (on premise), to use its
CPU and memory: the server sends each task's sandbox to that machine and takes the results back.

```
 VPS: web interface · chat · coordinator · projects · data · approvals
   │  task: the worker's docker command + the folders it mounts (bundle)
   ▼                                              ▲ progress while it runs, results at the end
 Dedicated machine: RigHaven Agent (compute node) ─ Docker ─ sandbox
```

## Prepare a machine

1. The machine needs **Docker**: a Linux server (`RigHaven-Agent-linux-x64` from the release), or a
   Windows PC with Docker Desktop or portable RigHaven (its WSL distribution has Docker).
2. Pair it like any PC: **Connections → Connected PCs → Connect a PC**, then on the machine
   `RigHaven-Agent agent link SERVER CODE`.
3. Offer it to the server, with the limits you want:

   ```
   RigHaven-Agent agent node on --cpus 12 --memory 48 --jobs 2
   ```

   `--cpus` and `--memory` (GiB) cap what RigHaven may use (default: all of Docker's), `--jobs`
   is how many tasks at a time (default 1), `--images` (GiB, default 40) the disk for the
   environment images the machine keeps. `agent node status` shows what is offered,
   `agent node off` stops offering it. Then keep `RigHaven-Agent agent run` running (at sign-in on
   Windows, a service on Linux).

The page lists it as **Compute node: 12 CPU · 48 GiB · 2 tasks at a time**.

## Choose where an environment runs

In **Environments → Configure → 4 · Where it runs**:

| Choice | What happens |
|---|---|
| **Cloud · this server** (default) | tasks run on the server, as before |
| **On premise · «machine»** | tasks run on that machine; if it is offline or cannot run the task, the task says why |
| **Automatic** | the machine next to the task's on-premise connections; otherwise the connected machine with most free CPU; otherwise the cloud |

The task card says where each task runs (*Running on premise on «Workstation»*).

## What happens to a task

1. The machine takes its turn (a free place within its limits) and keeps it until the end.
2. **The environment's image is prepared on the machine**, never on the server (see below).
3. It packs the folders the sandbox mounts: the project (read only), the output folder, the job's
   progress, the task's credentials, its connections and skills. Links and special files never
   leave the server.
4. The machine downloads the bundle, then **checks the command against its own sandbox rules**: no privileged
   mode, no devices, no host network, no extra capabilities, only the bundle's folders, CPU and
   memory within its limits. A command that does not pass is refused.
5. The sandbox runs with the same limits as on the server. Every few seconds the job's progress
   goes back, so the chat shows it live; a stop from the page stops it on the machine.
6. At the end the machine sends the exit code and the folders the task could write (output,
   progress, credentials refreshed by the model CLIs); the server validates and publishes the
   result as for a cloud task. If the server is not reachable, the machine keeps the result and
   sends it when the connection comes back; a machine restarted during a task ends it and reports it.

Each node has its own resources: a task waits for a free place on its machine, independently of
the server's budget.

## Environment images: each place keeps its own

The software of an environment (its tools, at the chosen versions) becomes a Docker image. In the
cloud it is prepared and cached on the server; **on premise it is prepared and kept on the
machine**, and the server's cache never holds it.

- **Reuse stays on its side.** A task in the cloud reuses only the server's images; a task on a
  machine reuses only that machine's images. An environment that needs the same tools as one the
  machine already has uses it as it is; one that needs more starts from the machine's closest image
  and installs only what is missing.
- **The preparation runs on the machine** with the same installer and the same checks as on the
  server: the machine accepts only RigHaven's installer, with the few capabilities package
  installers need (never for a task), and saves the result with `docker commit`. The first time the
  machine downloads the server's base image (`righaven-sandbox`) once.
- **Prepare** on the Environments page, for an environment placed on a machine, prepares it on
  that machine (waiting up to 10 minutes for it to connect). With *Automatic* each task prepares
  where it lands.
- **Disk.** The machine removes its least recently used environment images when they take more
  than `--images` GiB (default 40); images of running tasks stay. A removed image is prepared
  again when a task needs it.
- An agent of an older version, which does not prepare images, still receives images prepared on
  the server.

## Connections

- **Cloud connections** (a database on the internet, Microsoft accounts) work from the machine as
  from the server.
- **On premise through that same machine**: the task reaches the service **directly**, no tunnel.
- Not on a machine (the task stays in the cloud with *Automatic*, or is refused with an explicit
  machine): connections through **another** PC, COM ports through a tunnel, devices attached to
  the server, services of the server's own network.

## Limits

- The restricted network egress (*allowlist*) is enforced by the server's proxy: with it, tasks
  run in the cloud.
- The project is copied for each task: very large projects take time to send (up to 8 GiB).
- Work coordinated on premise (without the VPS) and later synchronization are not part of this
  version.
- Tested with simulated machines and, on Linux, with a real Docker container; not yet end to end
  between a real VPS and a real dedicated machine.
