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
   is how many tasks at a time (default 1). `agent node status` shows what is offered,
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

1. The server prepares the environment's image and the task as for the cloud.
2. It packs the folders the sandbox mounts: the project (read only), the output folder, the job's
   progress, the task's credentials, its connections and skills. Links and special files never
   leave the server.
3. The machine downloads the bundle and, the first time, the image (`docker save` from the server,
   or the registry), then **checks the command against its own sandbox rules**: no privileged
   mode, no devices, no host network, no extra capabilities, only the bundle's folders, CPU and
   memory within its limits. A command that does not pass is refused.
4. The sandbox runs with the same limits as on the server. Every few seconds the job's progress
   goes back, so the chat shows it live; a stop from the page stops it on the machine.
5. At the end the machine sends the exit code and the folders the task could write (output,
   progress, credentials refreshed by the model CLIs); the server validates and publishes the
   result as for a cloud task. If the server is not reachable, the machine keeps the result and
   sends it when the connection comes back; a machine restarted during a task ends it and reports it.

Each node has its own resources: a task waits for a free place on its machine, independently of
the server's budget.

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
- Images are prepared on the server and copied once to each machine.
- Work coordinated on premise (without the VPS) and later synchronization are not part of this
  version.
- Tested with simulated machines and, on Linux, with a real Docker container; not yet end to end
  between a real VPS and a real dedicated machine.
