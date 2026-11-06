"""RigHaven tool: delegate one task using the specialist's configured CLI."""
from langchain.tools import tool
from righaven_core.tools.types import Runtime
from righaven_core.config.paths import get_paths
from righaven_core.runtime.user_context import resolve_runtime_user_id
from .docker_runtime import delegate
from .projects import archive_plan, create_plan, execute_step, read_project, set_policy_plan, sync_acceptance, sync_project_context
from .project_brief import briefing_issue
import functools
import json
import threading


def workspace_for(runtime):
    thread = runtime.config.get('configurable', {}).get('thread_id')
    if not thread:
        raise ValueError('La delega richiede una conversazione RigHaven')
    user = resolve_runtime_user_id(runtime)
    paths = get_paths()
    paths.ensure_thread_dirs(thread, user_id=user)
    return paths.sandbox_user_data_dir(thread, user_id=user)


# A model may call harness_plan and harness_delegate in one response; the tools then
# run concurrently and the assignment could start before the plan it needs exists.
_PLAN_CALLS = {}
_PLAN_CALLS_LOCK = threading.Lock()
PLAN_WAIT_SECONDS = 120


def _plan_event(call_id):
    with _PLAN_CALLS_LOCK:
        if len(_PLAN_CALLS) > 2000:
            for key in [k for k, e in _PLAN_CALLS.items() if e.is_set()][:1000]:
                _PLAN_CALLS.pop(key, None)
        return _PLAN_CALLS.setdefault(call_id, threading.Event())


def signals_plan(function):
    """Mark this harness_plan call as finished, whatever its outcome."""
    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        finally:
            call_id = getattr(kwargs.get('runtime'), 'tool_call_id', None)
            if call_id:
                _plan_event(call_id).set()
    return wrapper


def sibling_plan_calls(runtime, names=('harness_plan','harness_journey','harness_method')):
    """IDs of harness_plan calls issued in the same model response as this tool call."""
    call_id = getattr(runtime, 'tool_call_id', None)
    messages = (getattr(runtime, 'state', None) or {}).get('messages', []) if call_id else []
    for message in reversed(messages):
        calls = getattr(message, 'tool_calls', None) or (message.get('tool_calls') if isinstance(message, dict) else None) or []
        if any(c.get('id') == call_id for c in calls):
            return [c['id'] for c in calls if c.get('name') in names and c.get('id')]
    return []


def wait_for_sibling_plans(runtime):
    """Start an assignment only after the plan updates of the same response are recorded."""
    for call_id in sibling_plan_calls(runtime):
        _plan_event(call_id).wait(PLAN_WAIT_SECONDS)


def experience_root(runtime):
    return get_paths().user_dir(resolve_runtime_user_id(runtime)) / 'righaven-experience'


@tool('harness_package_check', parse_docstring=True)
async def harness_package_check(runtime: Runtime, package_path: str) -> str:
    """Build and execute the actual exported data package in an isolated, resource-limited runtime.

    Uses the managed Dockerfile and hashed locks only. It mounts no model or production
    credentials, runs synthetic cycles across replacement and saves a verification report.
    Read the report and correct failures before submitting the package phase.

    Args:
        runtime: Injected RigHaven runtime.
        package_path: Existing exported package directory inside this conversation outputs.
    """
    from .package_checks import check
    from .capability_policy import runtime_policy, require_tools
    require_tools(runtime_policy(runtime),['dlt','sqlmesh','faker','duckdb','supercronic'])
    from .cancellation import call
    return json.dumps(await call(check, workspace_for(runtime), package_path), ensure_ascii=False)


@tool('harness_journey', parse_docstring=True)
@signals_plan
def harness_journey(runtime: Runtime, stage_id: str = '', evidence_json: str = '[]', steps_json: str = '[]', note: str = '', expected_revision: int = 0, propose_skip: bool = False) -> str:
    """Read the selected guided project, submit one phase for owner approval or propose skipping it.

    Read first. Compile dynamic roles and native activities for the current phase.
    Read the attachments before asking questions; connections are optional.
    This tool cannot approve or skip a phase or change the user's answers: the owner
    decides with the buttons in the project card, never through a chat reply.

    Args:
        runtime: Injected RigHaven runtime.
        stage_id: Empty reads; otherwise the current guided phase ID.
        evidence_json: JSON list of actual saved artifact paths, including verification reports; empty starts a phase linked to native activities.
        steps_json: JSON list of native activity IDs producing this phase.
        note: Explain the useful result and remaining limits without credentials.
        expected_revision: Revision read from the guided project, required on submission.
        propose_skip: True asks the owner to skip this phase because it adds nothing to the stated goal; note gives the reason.
    """
    from .journeys import view, record, compact
    for call_id in sibling_plan_calls(runtime, names=('harness_plan',)):
        _plan_event(call_id).wait(PLAN_WAIT_SECONDS)
    workspace = workspace_for(runtime)
    result = record(workspace, stage_id, json.loads(evidence_json), json.loads(steps_json), note, expected_revision, propose_skip) if stage_id else view(workspace)
    value = compact(result)
    if stage_id and value and value['awaiting_owner']:
        value['instruction'] = ('The owner decides in the project card («Tocca a te»). End this turn with a short summary of the result and how it serves the goal; '
                                'do not ask for approval or confirmation in the chat.')
    return json.dumps({'journey': value}, ensure_ascii=False)


@tool('harness_find_devices', parse_docstring=True)
def harness_find_devices(runtime: Runtime, where: str = 'all', network: str = '') -> str:
    """Identify devices near the owner's PC when the owner asks, without knowing their address.

    Read only: nothing is written to any device and the PC joins no network. Sources: the home
    network (TCP connection attempts to the usual ports of IoT devices, TVs, phones and cameras on a private network, at most 4096
    addresses), the nearby Wi-Fi networks (devices not set up yet open their own setup network),
    Bluetooth (nearby and paired devices, Bluetooth LE sensor readings), the USB peripherals and
    COM ports of the PC, and the serial ports already offered to connections. Wi-Fi, Bluetooth,
    USB and COM are read by the RigHaven launcher on the PC. Report what was found with its hint,
    then offer harness_setup_device for the one the owner wants to use.

    Args:
        runtime: Injected RigHaven runtime.
        where: all, network, wifi, bluetooth, usb, com or serial.
        network: Private network to search, for example 192.168.1.0/24; empty means the PC's network.
    """
    from . import connections, device_discovery, host_bridge
    if where not in ('all', 'network', 'wifi', 'bluetooth', 'usb', 'com', 'serial'):
        raise ValueError('where: all, network, wifi, bluetooth, usb, com o serial')
    found, notes = {}, []
    try:
        agent, folder = _pc(runtime)
    except ValueError as error:
        agent, folder = False, None
        notes.append(str(error))
    state = host_bridge.state(agent) if agent is not False else {'connected': False, 'actions': []}
    if where in ('all', 'serial'):
        found['serial'] = {'offered': [] if agent else connections.local_devices(), 'shared_com_ports': device_discovery.serial_ports(folder)}
    if where in ('all', 'network'):
        networks = state.get('networks') if agent else device_discovery.local_networks()
        target = network or next(iter(networks or []), '')
        if target:
            try:
                found['network'] = device_discovery.scan_from_agent(agent, target) if agent else device_discovery.scan(target)
            except ValueError as error:
                notes.append(str(error))
        else:
            notes.append('Rete del PC non nota: indica network, per esempio 192.168.1.0/24')
    steps = (('usb', 'usb-list', None), ('com', 'com-list', None),
             ('wifi', 'wifi-scan', device_discovery.wifi), ('bluetooth', 'bluetooth-scan', device_discovery.bluetooth))
    for kind, action, read in steps:
        if where not in ('all', kind):
            continue
        if not state['connected']:
            notes.append(kind + ': disponibile con RigHaven per PC aperto (lo legge il launcher sul PC)')
            continue
        if action not in state['actions']:
            notes.append(kind + ': non serve su questo PC, le porte seriali collegate sono già offerte (vedi serial)'
                         if kind in ('usb', 'com') else kind + ': non disponibile su questo PC')
            continue
        try:
            answer = host_bridge.run(action, timeout=150, agent=agent or None)
            found[kind] = read(folder) if read else answer
        except ValueError as error:
            notes.append(kind + ': ' + str(error))
    return json.dumps({'found': found, 'notes': notes, 'instruction':
        'Tell the owner what was found, what each device probably is and what can be done with it (Explore with harness_explore_device, Create connection or prepare it with harness_setup_device). Report only what these results show (a network, address or name not in them was not seen) and say when a guess is a guess. Offer '
        'harness_setup_device for the device the owner wants (USB peripheral by busid, COM port by name, network '
        'device by address and protocol, Matter device by pairing code). Devices in setup mode are first added to '
        'the home Wi-Fi: Tuya with its app; Tasmota, Shelly, ESPHome, WLED and OpenBeken with «Porta nel Wi-Fi di casa» in Connections, where the owner types the home Wi-Fi password (never ask for it in the chat). Do not search again unless the owner asks.'}, ensure_ascii=False, default=str)


def _pc(runtime, agent=''):
    """The PC a chat tool works on: an agent of this user (named, or the one online), or the launcher next to this server."""
    from . import agents, host_bridge
    target = host_bridge.pick(resolve_runtime_user_id(runtime), agent or None)
    return target, (str(agents.folder(target)) if target else None)


def _connection_id(user, name):
    import re as regex
    from . import connections
    base = regex.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:32] or 'dispositivo'
    if not base[0].isalpha():
        base = 'd-' + base
    taken = {row['id'] for row in connections.listing(user)}
    candidate, number = base, 2
    while candidate in taken:
        candidate, number = f'{base}-{number}', number + 1
    return candidate


@tool('harness_setup_device', parse_docstring=True)
def harness_setup_device(runtime: Runtime, kind: str, target: str, name: str = '', protocol: str = '', port: int = 0, note: str = '',
                         agent_network: bool = False) -> str:
    """Prepare a device the owner asked to use and create its connection, read only.

    Use it only after the owner chose the device (usually from harness_find_devices). It does
    the steps on the PC through the RigHaven launcher and creates the connection in the owner's
    Connections, read only: writing to the device stays off until the owner enables it there,
    and every write still needs harness_device_change. Steps by kind:
    usb (target = busid): shares the peripheral with RigHaven (Windows asks the owner's
    permission the first time) and connects its serial port; com (target = COM5): shares the
    Windows COM port (for example a paired Bluetooth OBD-II adapter); network (target = IP
    address, protocol mqtt, http, modbus-tcp, adb, tcp or tuya); matter (target = the 11-digit
    pairing code from Alexa, SmartThings, Google Home or Apple Home); bluetooth (target = the
    Bluetooth LE address from the Bluetooth search, then use harness_bluetooth). Tuya devices also need
    the device ID and local key, which the owner enters in Connections, never in the chat.

    Args:
        runtime: Injected RigHaven runtime.
        kind: usb, com, network, bluetooth or matter.
        target: busid, COM port, IP address, Bluetooth address or Matter pairing code.
        name: Name of the connection shown to the owner.
        protocol: For network: mqtt, http, modbus-tcp, adb, tcp or tuya.
        port: For network: port if not the protocol default.
        note: What the owner wants to do with the device.
        agent_network: For network: the device is in the home network of the owner's RigHaven Agent (the server reaches it through the agent).
    """
    from . import connections, device_discovery, host_bridge, matter
    user = resolve_runtime_user_id(runtime)
    label = (name or target).strip()[:80] or 'Dispositivo'
    body = {'kind': 'device', 'name': label, 'description': note[:400], 'access': 'read'}
    agent = None
    if kind in ('usb', 'com', 'bluetooth') or (kind == 'network' and agent_network):
        agent, _ = _pc(runtime)
    if agent and kind in ('usb', 'com'):
        # Through an agent a USB serial board is a COM port of the PC, carried to the server by a tunnel.
        if kind == 'usb':
            raise ValueError('Tramite RigHaven Agent una scheda USB si usa come porta COM: usa kind com con il nome della porta (per esempio COM5)')
        body.update(transport='agent', agent=agent, target='com:' + target.strip().upper(), baud=115200)
    elif kind == 'usb':
        answer = host_bridge.run('usb-attach', {'busid': target}, timeout=240)
        ports = [p for p in answer.get('ports') or [] if p in connections.local_devices()]
        if not ports:
            return json.dumps({'attached': True, 'connection': None, 'instruction':
                'The peripheral is attached but it exposes no serial port: tell the owner it may need a driver or is not a serial device.'}, ensure_ascii=False)
        body.update(transport='local', device=ports[0], baud=115200)
    elif agent and kind == 'network':
        if protocol not in ('mqtt', 'http', 'modbus-tcp', 'adb', 'tcp', 'tuya'):
            raise ValueError('protocol: mqtt, http, modbus-tcp, adb, tcp o tuya')
        if protocol == 'tuya':
            return json.dumps({'connection': None, 'instruction': 'A Tuya device needs its device ID and local key: ask the owner to create '
                               'the connection in Connections; never ask for the local key in the chat.'}, ensure_ascii=False)
        body.update(transport='agent', agent=agent, target='tcp:' + target.strip() + ':' + str(port or connections.PROTOCOLS[protocol][0] or 80),
                    protocol=protocol)
    elif kind == 'com':
        host_bridge.run('com-share', {'name': target}, timeout=60)
        shared = next((p for p in device_discovery.serial_ports() if p['name'] == target), None)
        if shared is None:
            raise ValueError('Porta COM condivisa ma non ancora visibile: riprova tra qualche secondo')
        body.update(transport='serial', protocol='socket', host=shared['host'], port=shared['port'], baud=38400)
        label = name or shared['label'] or target
        body['name'] = label[:80]
    elif kind == 'network':
        if protocol == 'tuya':
            return json.dumps({'connection': None, 'instruction':
                'A Tuya device needs its device ID and local key: ask the owner to open Connections, Find devices, and use '
                'Create connection on this address; never ask for the local key in the chat.'}, ensure_ascii=False)
        if protocol not in ('mqtt', 'http', 'modbus-tcp', 'adb', 'tcp'):
            raise ValueError('protocol: mqtt, http, modbus-tcp, adb, tcp o tuya')
        body.update(transport='network', protocol=protocol, host=target, **({'port': port} if port else {}))
    elif kind == 'bluetooth':
        body.update(transport='bluetooth', address=target.strip().upper(), **({'agent': agent} if agent else {}))
    elif kind == 'matter':
        node = matter.commission(target)
        url = matter.url().removeprefix('ws://').split('/')[0]
        body.update(transport='network', protocol='matter', host=url.split(':')[0], port=int(url.split(':')[1]), node_id=node['node_id'])
        body['name'] = (name or node.get('name') or 'Matter')[:80]
    else:
        raise ValueError('kind: usb, com, network, bluetooth o matter')
    body['id'] = _connection_id(user, body['name'])
    saved = connections.save(user, body)
    return json.dumps({'connection': {k: saved.get(k) for k in ('id', 'name', 'transport', 'protocol', 'host', 'port', 'device')},
                       'instruction': 'Tell the owner the connection is ready, read only. To let RigHaven send commands the owner '
                                      'enables writing on it in Connections; each command then still needs harness_device_change. '
                                      'To use it in this project the owner assigns it in the task card.'}, ensure_ascii=False, default=str)


@tool('harness_explore_device', parse_docstring=True)
def harness_explore_device(runtime: Runtime, kind: str, target: str) -> str:
    """Explore one thing found near the PC, as Explore does in Connections: read only, no connection needed.

    network (target = IP address): which IoT ports answer, its name and home page. wifi
    (target = network name): the launcher joins that Wi-Fi network for a few seconds, reads the
    page of what answers there (a device's setup page or a router) and goes back; from the chat
    only open networks and setup networks with a factory key, because a Wi-Fi password is typed
    by the owner in Connections, never in the chat. bluetooth (target = address): services,
    characteristics and readable values. usb (target = busid): name, IDs and state of the
    peripheral. listen (target empty): the devices that announce themselves on the PC's network
    (mDNS, UPnP) with their names and services. Recording the PC's traffic is started by the owner
    in Connections (Windows asks for administrator rights). Explore what the owner asks; the owner
    decides what to explore.

    Args:
        runtime: Injected RigHaven runtime.
        kind: network, wifi, bluetooth, usb or listen.
        target: IP address, Wi-Fi network name, Bluetooth address or USB busid.
    """
    from . import device_discovery, host_bridge
    agent, _ = _pc(runtime) if kind != 'network' else (None, None)
    if kind == 'network':
        try:
            agent, _ = _pc(runtime)
        except ValueError:
            agent = None
        return json.dumps(device_discovery.explore_from_agent(agent, target) if agent else device_discovery.explore(target), ensure_ascii=False)
    if kind == 'wifi':
        hint = device_discovery.wifi_hint(target)
        return json.dumps(host_bridge.run('wifi-explore', {'ssid': target, **({'hint': hint} if hint else {})}, timeout=120, agent=agent), ensure_ascii=False)
    if kind == 'bluetooth':
        return json.dumps(host_bridge.run('ble-inspect', {'address': target}, timeout=150, agent=agent), ensure_ascii=False)
    if kind == 'listen':
        return json.dumps(host_bridge.run('net-listen', timeout=60, agent=agent), ensure_ascii=False)
    if kind == 'usb':
        listed = host_bridge.run('usb-list', timeout=60, agent=agent)
        found = [d for d in listed.get('devices') or [] if d.get('busid') == target]
        if not found:
            raise ValueError('Periferica USB non trovata: ' + str(target)[:20])
        return json.dumps(found[0], ensure_ascii=False)
    raise ValueError('kind: network, wifi, bluetooth, usb o listen')


@tool('harness_bluetooth', parse_docstring=True)
def harness_bluetooth(runtime: Runtime, connection: str = '', action: str = 'inspect', service: str = '', characteristic: str = '', value: str = '', address: str = '') -> str:
    """Work with a Bluetooth LE device connection through the PC's Bluetooth (RigHaven launcher).

    inspect lists the device's services and characteristics with their properties and the
    values that can be read; read reads one characteristic. Neither needs approval nor a saved
    connection: pass the address found by the Bluetooth search. write sends
    bytes to one characteristic of a saved connection (harness_setup_device kind bluetooth creates
    it; the owner allows writing on it and assigns it to the task) and only after the owner
    approved that exact write: first call
    harness_device_change with action send and command_json
    {"payload": "<hex>", "encoding": "hex", "address": "<service>/<characteristic>"}, end the turn,
    and call write after the approval. Short UUIDs such as 180a are accepted. Many commercial
    devices encrypt their commands: say so when the characteristics look vendor specific.

    Args:
        runtime: Injected RigHaven runtime.
        connection: ID of the Bluetooth LE device connection (needed to write).
        action: inspect, read or write.
        service: Service UUID (read and write).
        characteristic: Characteristic UUID (read and write).
        value: Bytes to write, in hexadecimal (write).
        address: Bluetooth address from the search, to inspect or read without a connection.
    """
    from . import connections, device_changes, host_bridge
    if address and not connection:
        if action == 'write':
            raise ValueError('Writing needs a saved Bluetooth LE connection: create it with harness_setup_device')
        row = {'address': address}
    else:
        user = resolve_runtime_user_id(runtime)
        row = next((c for c in connections.listing(user) if c.get('id') == connection), None)
        if not row or row.get('kind') != 'device' or row.get('transport') != 'bluetooth':
            raise ValueError('Not a Bluetooth LE device connection: ' + str(connection))
    agent, _ = _pc(runtime, row.get('agent', ''))
    if action == 'inspect':
        return json.dumps(host_bridge.run('ble-inspect', {'address': row['address']}, timeout=150, agent=agent), ensure_ascii=False)
    if action == 'read':
        return json.dumps(host_bridge.run('ble-read', {'address': row['address'], 'service': service, 'characteristic': characteristic}, timeout=90, agent=agent), ensure_ascii=False)
    if action != 'write':
        raise ValueError('action: inspect, read o write')
    command = device_changes.bluetooth_command({'payload': value, 'encoding': 'hex', 'address': service + '/' + characteristic})
    workspace = workspace_for(runtime)
    change = device_changes.consume(workspace, connection, device_changes.command_fingerprint(command))
    if change is None:
        return json.dumps({'written': False, 'instruction': 'This exact write has no approval: call harness_device_change with action send and '
                           'command_json ' + json.dumps(command) + ', explain it, end the turn and write after the owner approves.'}, ensure_ascii=False)
    host_bridge.run('ble-write', {'address': row['address'], 'service': service, 'characteristic': characteristic, 'value': command['payload']}, timeout=90, agent=agent)
    from .audit_log import append
    append(workspace, 'Dispositivi', 'Scrittura Bluetooth LE eseguita', 'completed', connection + ' · ' + command['address'] + ' · ' + command['payload'][:64])
    return json.dumps({'written': True, 'change': change['id']}, ensure_ascii=False)


@tool('harness_device_change', parse_docstring=True)
def harness_device_change(runtime: Runtime, connection: str, action: str, file_path: str = '', package: str = '', mode: str = '', note: str = '', command_json: str = '',
                          targets: str = '', profile: str = '') -> str:
    """Ask the owner to approve one write to an external device before any role does it.

    Every write needs it: iot.send commands, Bluetooth LE writes (harness_bluetooth), iot.flash, Android changes (install, uninstall,
    disable, enable, reboot, sideload), clearing vehicle trouble codes and netscan vulnerability
    scans (action scan on a network connection). Reading and network mapping never do.
    The owner sees device, action and the exact file digest, package or command in the task
    card; an approval is delivered once, to the next assignment that receives this device, and
    the toolkit refuses anything that does not match it exactly.

    Args:
        runtime: Injected RigHaven runtime.
        connection: ID of the device connection assigned to the task with write consent.
        action: send, flash, sideload, install, uninstall, disable, enable, reboot, clear_codes or scan.
        file_path: Saved firmware .bin (flash), OTA .zip (sideload) or .apk (install) in this conversation.
        package: Android package for uninstall, disable or enable.
        mode: Reboot target: system, recovery, bootloader or sideload.
        note: What changes on the device, why, the risk, and how the result will be checked.
        command_json: For send, the exact iot.send fields as JSON (payload, encoding, topic, retain, method, address, values, coil).
        targets: For scan, networks or addresses inside the connection, separated by commas; empty means all its networks.
        profile: For scan, safe (vulnerability checks that do not disrupt services) or tls (TLS configuration).
    """
    from .device_changes import request
    value = request(workspace_for(runtime), connection, action, file_path, package, mode, note, json.loads(command_json) if command_json else None,
                    [t for t in targets.replace(';', ',').split(',') if t.strip()] or None, profile)
    return json.dumps({'device_change': value, 'instruction': 'The owner approves or rejects this change in the task card (Task connections). '
                       'End this turn with what will change, why, the risk and how it will be verified; do not ask for approval in the chat. '
                       'After approval delegate the iot operation once, to a role that declares this connection.'}, ensure_ascii=False)


@tool('harness_skills',parse_docstring=True)
def harness_skills(runtime:Runtime,query:str='',name:str='',reference:str='SKILL.md',offset:int=0)->str:
    """Discover authorized native skills or read one method/reference in pages.

    Also lists owner environment profiles, all authorized tool capabilities and
    the recipes (tested multi-tool workflows) whose skill is authorized.
    Skills describe methods and tool expertise; available tools and runtime
    images are separate. Read relevant methods before composing a project role.

    Args:
        runtime: Injected RigHaven runtime.
        query: Search words in skill names and descriptions; empty returns a compact catalog.
        name: Exact authorized native skill name to read; empty searches metadata only.
        reference: SKILL.md or a relative file under references/ in that skill.
        offset: Character offset; follow next_offset until null.
    """
    from .capability_policy import runtime_policy
    from .skill_composition import inventory,package_revision,environment_inventory
    from pathlib import Path
    import hashlib
    policy=runtime_policy(runtime)
    if not name:
        from .recipes import coordinator_index
        from .journeys import view as guided_view, compact
        return json.dumps({**inventory(policy,query),'environments':environment_inventory(policy),
                           'guided_project': compact(guided_view(workspace_for(runtime))),
                           'recipes':coordinator_index(set(policy.get('skill_names',[])),policy.get('user_id'))},ensure_ascii=False)
    source=policy.get('skill_sources',{}).get(name)
    if not source or name not in policy.get('skill_names',[]):raise ValueError('Skill non autorizzata nel profilo')
    root=Path(source).resolve();path=root/reference
    if '..' in Path(reference).parts or (reference!='SKILL.md' and not reference.startswith('references/')) or not path.resolve().is_relative_to(root) or path.is_symlink() or not path.is_file() or path.stat().st_size>200000:
        raise ValueError('Riferimento della skill non valido')
    revision=package_revision(source);text=path.read_text()
    if type(offset) is not int or offset<0 or offset>len(text):raise ValueError('Offset non valido')
    end=min(len(text),offset+8000)
    return json.dumps({'name':name,'reference':reference,'revision':revision,'sha256':hashlib.sha256(text.encode()).hexdigest(),
                       'content':text[offset:end],'next_offset':end if end<len(text) else None},ensure_ascii=False)


@tool('harness_read_context', parse_docstring=True)
def harness_read_context(runtime: Runtime, path: str, sha256: str, offset: int = 0) -> str:
    """Read a hash-verified project context reference in bounded pages.

    Use for details_path/details_sha256, saved requests, compiled roles and design source_path/sha256 references.
    Use the compact state first. Read only the pages relevant to the current decision, not entire plans or lesson archives.

    Args:
        runtime: Injected RigHaven runtime.
        path: Exact virtual path supplied by a project context reference.
        sha256: Exact SHA-256 supplied with that reference.
        offset: Character offset; zero initially, then the returned next_offset.
    """
    from .context_reader import read_context
    return json.dumps(read_context(workspace_for(runtime), path, sha256, offset), ensure_ascii=False)


def preserve_experience(workspace, runtime):
    from .experience import collect
    from .lessons import pending, propose_findings, automatic
    try:
        thread = (getattr(runtime, 'config', None) or {}).get('configurable', {}).get('thread_id')
        saved = collect(workspace, experience_root(runtime), thread)
        proposals = propose_findings(experience_root(runtime), thread)
        if proposals:
            sync_project_context(workspace, experience_root=experience_root(runtime))
        if saved or proposals:
            from .audit_log import append
            append(workspace, 'Memoria', 'Fonti esperienza archiviate', 'completed',
                   detail=f'{saved} nuove fonti; {len(proposals)} proposte. Archiviazione e apprendimento sono distinti.')
        sources = pending(experience_root(runtime), limit=3, source_thread=thread)
        return {'saved': saved, 'proposed_lessons': len(proposals), 'pending': len(pending(experience_root(runtime))),
                'technical_active_in_library': len(automatic(experience_root(runtime))),
                'notice': 'saved conta fonti archiviate, non lezioni apprese. Solo lezioni tecniche verificate o metodi accettati entrano nelle skills pertinenti.',
                'sources_to_evaluate': [{k: s.get(k) for k in ('id', 'criterion', 'status')} for s in sources],
                'instruction': 'Usa harness_lessons per valutare queste evidenze: generalizza poche cause/procedure utili, anche dai fallimenti, oppure motiva perché non sono trasferibili. Non inventare benefici né trasferire fatti specifici nelle skills. Un metodo proposto richiede accettazione; un test operativo serve solo per attivare automaticamente conoscenza tecnica.'}
    except (OSError, ValueError, TypeError):
        return {'error': 'Esperienza non archiviata: conserva il volume dati e riprova il recupero dalla scheda Esperienza.'}


def interaction_id(runtime):
    messages = (getattr(runtime, 'state', None) or {}).get('messages', [])
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        kind = message.get('type', message.get('role')) if isinstance(message, dict) else getattr(message, 'type', '')
        if kind in ('human', 'user'):
            identifier = message.get('id') if isinstance(message, dict) else getattr(message, 'id', None)
            return str(identifier or ('human-' + str(index)))[:150]
    return ''


def source_turn(runtime):
    config = (getattr(runtime, 'config', None) or {}).get('configurable') or {}
    if 'righaven_user_turn' in config:
        return config['righaven_user_turn'] or ''
    return interaction_id(runtime)


def user_requests(runtime):
    from .project_skills import request_text
    captured = (getattr(runtime, 'config', None) or {}).get('configurable', {}).get('righaven_user_messages')
    context = getattr(runtime, 'context', None) or {}
    is_subagent = context.get('is_subagent', False) if isinstance(context, dict) else getattr(context, 'is_subagent', False)
    if is_subagent:
        # Child HumanMessages are instructions generated by the coordinator.
        # Inherit only the gateway's actual user input, never relabel those tasks.
        if not isinstance(captured, list):
            return []
        return [request_text(s) for s in captured if isinstance(s, str) and s.strip()]
    result = []
    for message in (getattr(runtime, 'state', None) or {}).get('messages', []):
        kind = message.get('type', message.get('role')) if isinstance(message, dict) else getattr(message, 'type', '')
        if kind not in ('human', 'user'):
            continue
        content = message.get('content', '') if isinstance(message, dict) else getattr(message, 'content', '')
        if isinstance(content, list):
            content = '\n'.join(b.get('text', '') for b in content if isinstance(b, dict) and b.get('type') == 'text')
        if isinstance(content, str) and content.strip():
            result.append(request_text(content))
    for text in captured if isinstance(captured, list) else []:
        if isinstance(text, str) and text.strip() and request_text(text) not in result:
            result.append(request_text(text))
    return result


def lesson_reply(runtime, value):
    """Keep learning reports below upstream synopsis limits, with full private detail."""
    text = json.dumps(value, ensure_ascii=False)
    if len(text) <= 8000:
        return text
    from .acceptance import fingerprint
    from .project_skills import scoped_file
    document = scoped_file(workspace_for(runtime), 'learning-results/' + fingerprint(value) + '.json', text)
    compact = [{k: source.get(k) for k in ('id', 'status', 'tools', 'impact')} |
               {'criterion': str(source.get('criterion', ''))[:160], 'evidence': str(source.get('evidence', ''))[:300]}
               for source in value.get('pending_sources', [])[:6]]
    result = {'saved_lesson': value.get('saved_lesson'), 'decision': value.get('decision'),
              'pending_sources': compact, 'source_count': len(value.get('pending_sources', [])),
              'details_path': document['path'], 'details_sha256': document['sha256'],
              'details_reader': 'harness_read_context',
              'instruction': 'Usa harness_read_context con details_path e details_sha256 prima di generalizzare; non trasferirne i fatti specifici nelle skills.'}
    while compact and len(json.dumps(result, ensure_ascii=False)) > 8000:
        compact.pop()
    return json.dumps(result, ensure_ascii=False)


@tool('harness_lessons', parse_docstring=True)
def harness_lessons(runtime: Runtime, source_ids_json: str = '', lesson_json: str = '', dismiss_reason: str = '', impact_json: str = '', current_project_only: bool = False) -> str:
    """Generalize saved evidence into conditional reusable lessons, never project facts.

    Read without arguments to inspect up to six pending evidence records. Extract
    the transferable cause, procedure, verification and limits, including CLI usage
    findings reported by sandboxes. Inspect suggested_lesson, evidence_files and
    producer_method; distinguish reported operations from independent verification.
    Omit names,
    story content, file paths and project choices. Group related observations.
    A user preference is not technical verification; preserve that distinction.
    Save only individual lessons with a useful transferable insight, not every
    observation. Prioritize substantial improvements, not trivial tips. Distinguish
    measured gains from observations and hypotheses; never invent percentages.
    Dismiss unhelpful sources with a reason; keep their evidence.
    Production methods require individual owner acceptance in the Lessons panel.
    Tool-operation knowledge is activated by runtime-checked tests, never by model self-approval.
    Accepted lessons guide future roles only when relevant and compatible with tool versions.
    Do not block useful production on the learning backlog.

    Args:
        runtime: Injected RigHaven runtime.
        current_project_only: Restrict pending evidence to this conversation; use when evaluating its old observations without producing new work.
        source_ids_json: JSON list of one to six real saved evidence IDs.
        impact_json: Optional JSON level major/minor/unknown, basis measured/observed/hypothesis and reason grounded in the selected evidence. No fabricated measurements. This ranks proposals, not a product quality certificate.
        dismiss_reason: Instead of saving a lesson, explain why the selected source IDs do not warrant one. Do not combine with lesson_json.
        lesson_json: JSON category (production_method for realization strategy, tool_operation for CLI usage), title, applies_when, procedure (list), verification (list), limits and tools (installed IDs or empty for a general principle). Conditions and limits are required; no facts of the source project.
    """
    from .lessons import learn, pending, dismiss
    root = experience_root(runtime)
    preserve_experience(workspace_for(runtime), runtime)
    thread = (getattr(runtime,'config',None) or {}).get('configurable',{}).get('thread_id') if current_project_only else None
    if dismiss_reason:
        if lesson_json:
            raise ValueError('Salva o scarta la singola lezione, non entrambe')
        dismiss(root, json.loads(source_ids_json), dismiss_reason)
        return lesson_reply(runtime, {'decision': 'not_generalized', 'pending_sources': pending(root,source_thread=thread)})
    if bool(source_ids_json) != bool(lesson_json):
        raise ValueError('Indica sia le fonti sia la lezione generale')
    identifier = learn(root, json.loads(source_ids_json), json.loads(lesson_json), json.loads(impact_json) if impact_json else None) if lesson_json else None
    if identifier:
        sync_project_context(workspace_for(runtime), experience_root=root)
    return lesson_reply(runtime, {'saved_lesson': identifier, 'pending_sources': pending(root,source_thread=thread),
                       'instruction': 'Conserva solo la lezione generale e condizionale; le fonti restano separate e non dimostrano più di quanto verificato.'})


@tool('harness_method', parse_docstring=True)
@signals_plan
def harness_method(runtime: Runtime, recipe_json: str = '', objective: str = '') -> str:
    """Read the shared method or propose a reusable recipe for owner review.

    Use harness_plan(strategy_json) for the method and up to three alternatives.
    The owner chooses in Method. Test that chosen method and record hashed
    evidence before proposing a generalized recipe here. Never save or publish
    a recipe on behalf of the owner. No connection IDs, private data or job paths.

    Args:
        runtime: Injected RigHaven runtime.
        objective: Optional new objective, verbatim from the latest genuine user message.
            Starts a new open work scope, retaining prior results and sources as
            references and archiving old recipe gates. Use for an explicitly new
            goal or a new revision after delivery; never for a continuation control.
        recipe_json: Optional JSON recipe editor draft: title, summary, when,
            outputs, phases (title, detail, checkpoint), skills, tools, optional
            environment, attach_required/attach_optional/attach_never, questions,
            prerequisites, keywords and guidance. Use reusable steps and checks,
            not the facts of this project. Empty reads current choices only.
    """
    from . import collaboration
    root = workspace_for(runtime)
    if objective:
        context=getattr(runtime,'context',None) or {}
        if isinstance(context,dict) and context.get('is_subagent'):
            raise ValueError('Only the coordinator can apply the user objective')
        from . import objectives
        requests=user_requests(runtime)
        if recipe_json or not requests or objective.strip()!=requests[-1].strip():
            raise ValueError('A new objective must quote the latest user request; do not infer one from coordinator instructions')
        current=objectives.view(root)
        return json.dumps(objectives.redirect(root,objective,current['signature'],source_turn(runtime),requests),ensure_ascii=False)
    if not recipe_json:
        return json.dumps(collaboration.view(root), ensure_ascii=False)
    from .capability_policy import native_policy
    owner = resolve_runtime_user_id(runtime)
    policy = native_policy(owner)
    return json.dumps(collaboration.propose(root, owner, json.loads(recipe_json),
                      policy['skill_names'], policy['allowed']), ensure_ascii=False)


@tool('harness_plan', parse_docstring=True)
@signals_plan
def harness_plan(runtime: Runtime, brief: str = '', steps_json: str = '',
                project_type: str = '', omissions_json: str = '{}', revise_step_id: str = '',
                archive: bool = False, summary: str = '', next_action: str = '', status: str = '',
                product_path: str = '', requirements_json: str = '', criteria_json: str = '', roles_json: str = '', memory_json: str = '', outcome_json: str = '', strategy_json: str = '', designs_json: str = '', policies_json: str = '') -> str:
    """Maintain a concise, adaptive production workspace and visible user status.

    Read without arguments. Update the brief, activity board or current status as
    the work evolves; existing attempts and files are preserved. Activities may
    be reordered, added, reassigned or skipped. depends_on is an input hint, not
    a blocking pipeline. Compile project-specific professional roles from the actual brief; installed tools are capabilities, not a list of professions.
    Discover capabilities with harness_skills before composing roles. Roles without tools or skills require capability_rationale explaining how the base runtime can produce and verify the product.
    Prefer a representative preview at the intended finish; shorten its scope before lowering fidelity. Improve the observed bottleneck with focused specialist work.
    Avoid long plans and technical recaps: summary and next_action appear beside
    the chat input. Use purpose=delivery on the final integration to check media.
    The runtime enforces Brief -> Execution Plan + Policy Plan -> policy-aware
    assignments -> harness_validate -> delivery; governance.phase shows the stage.

    Args:
        runtime: Injected RigHaven runtime.
        brief: Desired product and key acceptance criteria.
        steps_json: Optional JSON list of id, agent, goal, depends_on and optional status pending/review/skipped; updates existing activities by ID.
        project_type: custom or animated_video; the latter defaults to video with audio, without forcing a fixed team.
        omissions_json: Compatibility field for explicit user exclusions, such as soundcraft for a silent video.
        revise_step_id: Reopen this activity while applying steps_json, outcome_json and other supplied plan updates in the same call; retain past attempts and reusable results. Update activity goals for the current revision; explicitly mark obsolete pending activities skipped instead of leaving the previous plan as current.
        archive: Archive an inactive abandoned project, preserving files.
        summary: One short sentence explaining the current practical work to the user.
        next_action: One short sentence describing the next useful result or action.
        status: clarifying, working, review, ready, blocked or idle.
        product_path: Existing verified final product to show prominently; ready requires it.
        requirements_json: Media acceptance requirements such as {"audio":true,"video":true}; follow the user's brief.
        roles_json: JSON roles compiled for this project: id, title, mission, expertise, procedure, checks, deliverables, skills (exact authorized native names discovered with harness_skills), tools (available catalog IDs, optional), inputs and risks; optional connections: project-authorized connection IDs needed by this role only (empty by default); optional network: up to eight {domain, reason} the role must reach beyond the model provider (for example fonts or a public dataset), granted only when the installation restricts worker egress. Selected skill requirements add their tools automatically. Roles are dynamic, not tool identities; scope and package versions are recorded. Each role requires capability_rationale: explain why the selected capabilities can construct its actual content/model, not merely export the delivery format; consider relevant owner environments and justify simpler alternatives. Do not assign every available tool or impose a fixed team.
        memory_json: JSON object with project-specific decisions, facts, questions and asset references; merge top-level keys, keep evidence and uncertainty explicit.
        outcome_json: JSON intended result with title, result, format (delivery form, not necessarily a file extension), use, quality, constraints, assumptions, questions. Questions are at most three decisive missing user choices; ask them with ask_clarification, then replace the object with the real answers and questions empty before delegating. Do not ask again for choices already explicit in the brief. tool_options lists up to four tool decisions when several catalog tools could produce the result: id, decision, 2–4 options (id, label, tools, pros, cons), recommended option and recommendation_reason, chosen empty. Present them with ask_clarification and set chosen only after the user's reply; production waits for every choice and roles cannot use tools of rejected options.
        strategy_json: Optional method selection, especially after a failed sample: method, reason, state (exploring/selected/needs_user), up to three alternatives with method, reason, tools, status (candidate/tested/unavailable) and evidence_paths (existing workspace files required for tested). To pause for user help include stop_reason (missing_input/capability_limit/user_choice/budget) and concrete user_action. A quality failure alone cannot establish an external blocker. Revisit team assumptions before requesting assets; changing method does not authorize lowering user requirements.
        designs_json: Optional JSON list of visual models: id, title, tool, source_path, optional preview_path, bindings (element_id with step_id/role_id/criterion_id/delivery_id) and expected_revision when updating. Register existing editable design files; read current revisions first and preserve user edits. No fixed diagram notation is required.
        policies_json: Policy Plan beside the Execution Plan: JSON list of optional Policy Book sheets that apply, each with id, reason and optional steps (activity IDs; empty means every production activity). [] records that no optional sheet applies. Mandatory sheets are always added by the runtime. Production assignments wait until the plan is settled.
        criteria_json: JSON acceptance criteria for any product: id, requirement, method (content, visual, listening, structural, functional, reference), critical and reference_paths. Optional origin=user requires source_quote copied from actual user messages; origin=proposal identifies team choices. Proposals remain checked until explicitly revised; never weaken user requirements to pass. Preserve requested references; no invented substitutions.
    """
    workspace = workspace_for(runtime)
    from .capability_policy import runtime_policy, public, require_tools
    policy = runtime_policy(runtime)
    if strategy_json:
        from .strategy import check_capability_choice
        check_capability_choice(json.loads(strategy_json), policy)
    if roles_json:
        from .project_brief import rejected_tools
        from .journeys import view as journey_view
        excluded = rejected_tools((read_project(workspace) or {}).get('outcome'))
        specs = json.loads(roles_json)
        journey = journey_view(workspace)
        if journey and isinstance(specs, list):
            from .journeys import with_recipe_skills
            specs = with_recipe_skills(specs, journey, policy.get('skill_names', []))
            roles_json = json.dumps(specs, ensure_ascii=False)
        for spec in specs:
            require_tools(policy, spec.get('tools', []))
            if excluded & set(spec.get('tools', [])):
                raise ValueError('Il ruolo ' + str(spec.get('id')) + ' usa programmi di alternative non scelte dall’utente: '
                                 + ', '.join(sorted(excluded & set(spec.get('tools', [])))) + '. Rispetta la scelta registrata nel brief.')
            if not isinstance(spec.get('capability_rationale'),str) or not spec['capability_rationale'].strip():
                raise ValueError('Consulta harness_skills e indica capability_rationale per ogni ruolo: quali capacità costruiscono il contenuto/modello, quali lo impaginano o esportano e quali lo verificano; confronta gli ambienti pertinenti. Il formato finale non giustifica da solo la scelta dello strumento. Anche il solo runtime base richiede una motivazione.')
    learning = {}
    from .journeys import view as guided_view
    guided = guided_view(workspace)
    requests = user_requests(runtime)
    if read_project(workspace):
        sync_acceptance(workspace, requests, json.loads(criteria_json) if criteria_json else None)
    if status == 'ready' and not ((read_project(workspace) or {}).get('acceptance') or {}).get('user_requests'):
        raise ValueError('Impossibile dichiarare concluso il prodotto senza la richiesta originale dell’utente nel contesto verificabile.')
    if archive:
        value = archive_plan(workspace, brief)
    elif any((revise_step_id, brief, steps_json, summary, next_action, status, product_path, requirements_json, project_type, criteria_json, roles_json, memory_json, outcome_json, strategy_json)):
        value = create_plan(workspace, brief, json.loads(steps_json or '[]'), project_type,
            json.loads(omissions_json), summary=summary, next_action=next_action, status=status,
            product_path=product_path, requirements=json.loads(requirements_json) if requirements_json else None,
            outcome=json.loads(outcome_json) if outcome_json else None, source_turn=source_turn(runtime),
            revise_step_id=revise_step_id,revision_reason=brief or summary or next_action)
    else:
        value = read_project(workspace)
    if not value and guided:
        from .journeys import compact
        return json.dumps({'journey': compact(guided), 'instruction': 'Read attached documentation and compile the first dynamic roles and native activities. Preserve the owner goal and selected destinations. Connections are optional only when the goal does not need them.'}, ensure_ascii=False)
    if value and not value.get('archived'):
        sync_acceptance(workspace, requests, json.loads(criteria_json) if criteria_json else None)
        if strategy_json:
            create_plan(workspace, '', [], strategy=json.loads(strategy_json), status='blocked' if status == 'blocked' else '')
        if designs_json:
            from .project_design import register
            register(workspace,json.loads(designs_json),set(policy['allowed']))
        learning = preserve_experience(workspace, runtime)
        sync_project_context(workspace, json.loads(roles_json) if roles_json else None, json.loads(memory_json) if memory_json else None, experience_root=experience_root(runtime),skill_policy=policy)
        if policies_json:
            set_policy_plan(workspace, json.loads(policies_json))
        value = read_project(workspace)
    if value and not value.get('archived'):
        # The user board contains all versions. Repeating its entire inventory
        # used to overflow tool context and hide the actual product/brief.
        value = {**value, 'results': value.get('results', [])[:8],
                 'deliveries': value.get('deliveries', [])[:5]}
    from .control_memory import reply
    from .state import team
    from .acceptance import generation_capabilities
    from .policy_book import catalog
    return reply(workspace, {'project': value, 'learning': learning, 'capability_policy': public(policy), 'policy_book': catalog(),
        'generation_capabilities': generation_capabilities(team('squad')['engine'], (value or {}).get('user_direction'))}, 'plan')


@tool('harness_delegate', parse_docstring=True)
def harness_delegate(agent: str, task: str, runtime: Runtime, step_id: str = '', purpose: str = 'work', role_id: str = '', phase_id: str = '') -> str:
    """Assign focused work to any useful RigHaven specialist, reusing available files.

    Activities are flexible. step_id is optional and an activity is created when
    needed. A failed colleague, optional check or missing handoff must not block
    useful review or integration of existing files. Inspect partial work rather
    than rebuilding it. Provider quota/auth failures pause work and require the
    shared provider to become available; never retry the same outage in a loop.
    Use purpose=preview for a small complete prototype before expensive renders;
    purpose=integration assembles available parts; purpose=delivery validates the
    final media requirements in the worker. Deliver editable sources and genuine
    opening evidence. Independent activities may run concurrently within the configured CPU/RAM and worker limits. Issue independent harness_delegate calls together; wait for required colleague outputs before dependent work.

    Args:
        agent: Use workspace for a dynamic project role; its selected skills/tools determine the runtime. Historical tool specialist IDs remain compatible with old chats.
        role_id: ID of a project-specific compiled role created with harness_plan roles_json. Required for workspace; uses its procedure and tool skills.
        task: Concrete result, pertinent input paths and acceptance checks; avoid broad rediscovery.
        runtime: Injected RigHaven runtime.
        step_id: Optional activity identifier, reusable for targeted revisions.
        purpose: work, preview, review, integration or delivery.
        phase_id: Current guided phase ID. Binds and starts this planned activity automatically; never approves a phase.
    """
    return delegate_step(agent, task, runtime, step_id=step_id, purpose=purpose, role_id=role_id, phase_id=phase_id)


def delegate_step(agent, task, runtime, *, step_id='', purpose='work', role_id='', policy_sheet=None, phase_id=''):
    """One assignment; policy_sheet turns a review into that sheet's final validation."""
    wait_for_sibling_plans(runtime)
    workspace = workspace_for(runtime)
    requests = user_requests(runtime)
    if not read_project(workspace):
        create_plan(workspace, requests[0] if requests else task, [])
    sync_acceptance(workspace, requests)
    project = read_project(workspace) or {}
    from .capability_policy import runtime_policy, require_tools
    policy = runtime_policy(runtime)
    issue = briefing_issue(project.get('outcome'))
    if issue:
        create_plan(workspace, '', [], status='clarifying', summary='Prima definiamo il risultato da ottenere.',
                    next_action='Rispondi alle domande sul risultato e sulla forma della consegna.')
        return json.dumps({'ok': False, 'needs_briefing': True, 'error': issue,
                           'outcome': project.get('outcome'), 'instruction': 'Usa ask_clarification per le scelte decisive mancanti; aggiorna harness_plan(outcome_json) prima di riprovare. Non è un errore del provider e non richiede tentativi ripetuti.'}, ensure_ascii=False)
    from .state import team
    profile = team('squad')
    request_id = interaction_id(runtime)
    preserve_experience(workspace, runtime)
    sync_project_context(workspace, experience_root=experience_root(runtime),skill_policy=policy)
    project = read_project(workspace) or {}
    if not role_id and step_id:
        role_id = next((s.get('role_id', '') for s in project.get('steps', []) if s['id'] == step_id), '')
    role = next((r for r in project.get('roles', []) if r['id'] == role_id), None) if role_id else None
    if (role_id and not role) or (agent == 'workspace' and not role):
        raise ValueError('Definisci prima il ruolo concreto con harness_plan roles_json')
    require_tools(policy, ([agent] if agent != 'workspace' else []) + (role or {}).get('tools', []))
    from .project_brief import rejected_tools
    excluded = rejected_tools(project.get('outcome')) & set((role or {}).get('tools', []) + ([agent] if agent != 'workspace' else []))
    if excluded:
        raise ValueError('L’utente ha scelto un’altra alternativa: questo incarico userebbe ' + ', '.join(sorted(excluded)) + '. Aggiorna il ruolo.')
    # A first-result workflow delivers its checked product in this assignment;
    # it must not require another worker solely to run the same media checks.
    requirements = project.get('requirements', {}) if purpose == 'delivery' or (
        (project.get('journey') or {}).get('mode')=='first_result' and purpose=='preview') else {}
    policy_review = {}
    if policy_sheet is not None and policy_sheet['final_checks'] != 'acceptance':
        from .policy_book import contract
        policy_review = {'policy_review': {'sheet': policy_sheet['id'], 'revision': policy_sheet['revision'],
                                           'contract': contract(policy_sheet, None)}}
    result = json.loads(execute_step(workspace, agent, task, step_id,
        lambda instructions, started=None: delegate(agent, instructions, workspace,
            tool_call_id=getattr(runtime, 'tool_call_id', None), on_started=started,
            requirements=requirements, purpose=purpose, acceptance=project.get('acceptance'), role=role,
            capability_policy=policy, **policy_review), provider={k: profile[k] for k in ('engine', 'model', 'connection_id') if k in profile},
        purpose=purpose, request_id=request_id, role=role, policy_sheet=policy_sheet, phase_id=phase_id))
    from .journeys import reconcile, compact as phase_summary
    result['journey'] = phase_summary(reconcile(workspace))
    try:
        return delegation_reply(workspace, runtime, result, project, profile, purpose)
    except Exception as error:
        # The assignment is already recorded: never report it as failed or invite a re-run.
        from .progress import clean_summary
        from .audit_log import append
        append(workspace, 'Coordinatore', 'Riepilogo dell’incarico non disponibile', 'failed', detail=clean_summary(error))
        return json.dumps({k: result[k] for k in ('ok', 'activity', 'output_dir', 'error', 'checkpoint', 'policy_violations') if k in result}
                          | {'available_files': result.get('available_files', [])[:20], 'summary_unavailable': True,
                             'instruction': 'L’incarico è registrato con il suo esito: non rilanciarlo. Il riepilogo completo non è disponibile; '
                                            'leggi i file indicati o lo stato con harness_plan.'}, ensure_ascii=False)


def delegation_reply(workspace, runtime, result, project, profile, purpose):
    """Compact coordinator view of a recorded assignment."""
    experience = preserve_experience(workspace, runtime)
    handoff = result.get('handoff') or {}
    from .handoff import blocking_checks
    from .control_memory import counts
    from .progress import clean_summary
    compact = {k: result[k] for k in ('ok', 'duplicate', 'activity', 'journey', 'output_dir', 'attention', 'recovery', 'retry_blocked', 'checkpoint_reassessment','goal','instruction',
        'product_verified', 'verified_products', 'available_results', 'policy_violations', 'policy_compliance', 'checkpoint') if k in result}
    compact.update(error=clean_summary(result.get('error', '')),
        check_counts=counts(handoff.get('checks', [])),
        blocking_failed_checks=len(list(blocking_checks(handoff.get('checks', [])))),
        available_files=result.get('available_files', [])[:20],
        source_status=handoff.get('delivery', {}).get('source_status'),
        outputs=[{**{k: clean_summary(f.get(k, '')) for k in ('path', 'role', 'format', 'open_with', 'editability')},
                  'reopen': {'status': (f.get('reopen') or {}).get('status', 'not_run'),
                             'evidence': clean_summary((f.get('reopen') or {}).get('evidence', ''))},
                  'limitations': [clean_summary(s) for s in f.get('limitations', [])[:3]]}
                 for f in handoff.get('delivery', {}).get('files', [])[:20]],
        checks=[{'name': clean_summary(c.get('name')), 'status': c.get('status'),
                 **{k: c[k] for k in ('scope','superseded_by') if k in c},
                 'evidence': clean_summary(c.get('evidence'))} for c in sorted(handoff.get('checks', []), key=lambda c: c.get('status') == 'passed')[:10]],
        warnings=[clean_summary(w) for w in handoff.get('warnings', [])[:5]],
        review_notes=result.get('review_notes', [])[:8])
    if result.get('output_dir') and handoff:
        compact['handoff_path'] = result['output_dir'] + '/handoff.json'
    record = result.get('delivery_record') or {}
    compact['delivery'] = {k: record.get(k) for k in ('id', 'title', 'technical_status', 'issues', 'source_status', 'finalization_pending', 'reused_archive_checks')}
    compact['quality_review'] = result.get('quality_review')
    compact['correction_focus'] = (read_project(workspace) or {}).get('correction_focus', [])
    compact['learning_review'] = result.get('learning_review')
    from .acceptance import capabilities
    compact['experience'] = experience
    compact['verification_capabilities'] = capabilities(profile['engine'])
    from .acceptance import generation_capabilities
    current_direction = (read_project(workspace) or {}).get('user_direction')
    compact['user_direction'] = current_direction
    if current_direction != project.get('user_direction'):
        compact['direction_changed'] = 'L’utente ha cambiato le scelte durante questo incarico: rileggi harness_plan e ripianifica prima di produrre o approvare. Conserva i file validi.'
    compact['generation_capabilities'] = generation_capabilities(profile['engine'], current_direction)
    from .control_memory import reply, counts
    compact['check_counts'] = counts(handoff.get('checks', []))
    compact['output_count'] = len(handoff.get('delivery', {}).get('files', []))
    if result.get('ok') and purpose in ('preview', 'delivery'):
        files = handoff.get('delivery', {}).get('files', [])
        from .handoff import product_files
        primary = next((f['path'] for f in product_files(files)), None)
        if primary:
            sources = sorted((f for f in files if f.get('role') in ('source_archive', 'editable_source')),
                             key=lambda f: f['role'] != 'source_archive')
            compact['presentation'] = {'paths': list(dict.fromkeys([primary, *[f['path'] for f in sources[:2]]])),
                'instruction': 'Presenta questi file con present_files prima della prossima delega. Spiega cosa è cambiato e i difetti rimasti. Un campione o un prodotto non approvato resta una bozza; non dichiararlo finito e non nascondere la versione disponibile mentre continui le correzioni.'}
    return reply(workspace, compact, 'delegate')


async def _harness_delegate_async(agent: str, task: str, runtime: Runtime, step_id: str = '', purpose: str = 'work', role_id: str = '', phase_id: str = '') -> str:
    from .cancellation import call
    return await call(harness_delegate.func, agent=agent, task=task, runtime=runtime,
                      step_id=step_id, purpose=purpose, role_id=role_id, phase_id=phase_id)


# Keep the synchronous function for direct callers; LangGraph awaits this
# coroutine, so an explicit run cancellation reaches the Docker worker too.
harness_delegate.coroutine = _harness_delegate_async


@tool('harness_delegate_batch',parse_docstring=True)
def harness_delegate_batch(assignments_json:str,runtime:Runtime)->str:
    """Run independent role assignments concurrently, each with isolated staging.

    Use for genuinely independent contributions. Dependent work waits for its
    prerequisite activities and consumes their published outputs in a later batch.

    Args:
        assignments_json: JSON list of 2–8 objects with agent, task, role_id and optional step_id/purpose, as for harness_delegate.
        runtime: Injected RigHaven runtime.
    """
    from concurrent.futures import ThreadPoolExecutor
    from contextvars import copy_context
    assignments=json.loads(assignments_json)
    allowed={'agent','task','role_id','step_id','purpose','phase_id'}
    if not isinstance(assignments,list) or not 2<=len(assignments)<=8 or any(not isinstance(a,dict) or set(a)-allowed or not a.get('agent') or not a.get('task') for a in assignments):
        raise ValueError('Indica da 2 a 8 incarichi indipendenti con agente, ruolo e compito')
    named=[a['step_id'] for a in assignments if a.get('step_id')]
    if len(set(named))!=len(named):raise ValueError('Non eseguire due volte la stessa attività nel gruppo')
    def invoke(assignment):
        try:return json.loads(harness_delegate.func(runtime=runtime,**assignment))
        except Exception as error:return {'ok':False,'error':str(error)[:1000]}
    # Submit the whole bounded batch to the live FIFO/budget admission layer.
    # A second pool limit captured here would ignore later configuration changes
    # and hide pending assignments from cancellation and queue monitoring.
    with ThreadPoolExecutor(max_workers=len(assignments),thread_name_prefix='rh-team') as pool:
        futures=[pool.submit(copy_context().run,invoke,a) for a in assignments]
        results=[f.result() for f in futures]
    return json.dumps({'ok':all(r.get('ok') for r in results),'assignments':results},ensure_ascii=False)


@tool('harness_validate', parse_docstring=True)
def harness_validate(runtime: Runtime, role_id: str, task: str = '') -> str:
    """Run the final multi-policy validation of the finished product before delivery.

    Requires a completed Execution Plan and a product_path. The runtime first checks
    delivery integrity, then runs the executable probes the sheets require (qpdf,
    pdftotext, veraPDF, ffprobe, gitleaks on the exact file, without network), then runs one separate review per Policy Plan sheet that has
    no valid verdict for this exact product: independent sheets in parallel, dependent
    sheets after their prerequisites. All violations are returned together. Delivery
    (status=ready) is refused until every sheet passes. Correct violations on the
    sources, deliver a new version, then validate again; a passed sheet is reused.

    Args:
        runtime: Injected RigHaven runtime.
        role_id: Reviewer role compiled with harness_plan roles_json; it must not have produced the product.
        task: Optional guidance for the reviewers: product context, references and what to inspect.
    """
    from concurrent.futures import ThreadPoolExecutor
    from contextvars import copy_context
    from . import policy_workflow
    from .projects import governance_state, save_policy_validation
    workspace = workspace_for(runtime)
    from .journeys import view as guided_view
    guided = guided_view(workspace)
    if guided and not guided['complete']:
        # Not an error to investigate: final validation belongs to the finished product, after the last guided phase.
        current = next((s for s in guided['stages'] if s['id'] == guided['current']), None)
        return json.dumps({'ok': False, 'deferred': True, 'current_phase': guided['current'],
                           'instruction': 'Final policy validation runs once, on the finished product, after every guided phase is settled. '
                                          'Nothing is blocked: continue with the current phase' + (' «' + current['title']['it'] + '»' if current else '') +
                                          ' using harness_journey and native activities. Do not ask the owner about this and do not investigate it.'}, ensure_ascii=False)
    value = governance_state(workspace)
    if not policy_workflow.governed(value):
        raise ValueError('Questo progetto è precedente al Policy Book: usa purpose=review per la revisione di qualità')
    stage = policy_workflow.phase(value)
    if stage in ('briefing', 'planning'):
        raise ValueError('Completa prima brief, Execution Plan e Policy Plan (fase attuale: ' + stage + ')')
    if stage == 'execution':
        open_steps = [s['id'] for s in value['steps'] if s.get('kind') != 'validation' and s['status'] not in policy_workflow.SETTLED]
        raise ValueError('La validazione finale riguarda il prodotto finito: ' + (
            'attività ancora aperte: ' + ', '.join(open_steps) if open_steps else 'indica product_path del prodotto consegnato con purpose=delivery'))
    if not any(r['id'] == role_id for r in value.get('roles', [])):
        raise ValueError('Indica il ruolo revisore compilato con harness_plan roles_json')
    from .projects import artifact_path
    product = artifact_path(workspace, value.get('product_path', ''))
    authors = {a.get('role_id') for s in value['steps'] if s.get('kind') != 'validation' for a in s['attempts']
               if product and any(artifact_path(workspace, p) == product for p in a.get('output_files', []))}
    if role_id in authors:
        raise ValueError('La validazione finale richiede un revisore indipendente: il ruolo ' + role_id + ' ha prodotto il file da validare')
    report = policy_workflow.validation(workspace, value)
    runs = []
    if report['integrity']['status'] == 'passed':
        probes = policy_workflow.run_probes(workspace, value)
        if probes:
            value = governance_state(workspace)
            report = policy_workflow.validation(workspace, value)
        sheets = {s['id']: s for s in value['policy_plan']['sheets']}
        to_run = [sheets[s['id']] for s in report['sheets'] if s['status'] == 'pending']
        guidance = task.strip() or 'Valida il prodotto finito ' + value.get('product_path', '') + ' senza modificarlo.'

        def review(sheet):
            try:
                result = json.loads(delegate_step('workspace', guidance, runtime, step_id='policy-' + sheet['id'],
                                                  purpose='review', role_id=role_id, policy_sheet=sheet))
            except Exception as error:
                result = {'ok': False, 'error': str(error)[:500]}
            return {'sheet': sheet['id'], 'ok': bool(result.get('ok')), 'error': result.get('error', '')}
        for wave in policy_workflow.waves(to_run, {s['id'] for s in report['sheets'] if s['status'] != 'pending'}):
            current = {s['id']: s['status'] for s in report['sheets']}
            ready = [s for s in wave if all(current.get(d) == 'passed' for d in s['depends_on'])]
            runs += [{'sheet': s['id'], 'ok': False, 'error': 'In attesa delle sheet da cui dipende: ' + ', '.join(s['depends_on'])}
                     for s in wave if s not in ready]
            if ready:
                with ThreadPoolExecutor(max_workers=len(ready), thread_name_prefix='rh-policy') as pool:
                    runs += [f.result() for f in [pool.submit(copy_context().run, review, s) for s in ready]]
            report = policy_workflow.validation(workspace, governance_state(workspace))
    saved = save_policy_validation(workspace, report)
    instruction = {'passed': 'Tutte le policy sono superate: dichiara la consegna con harness_plan(status=ready).',
                   'failed': 'Correggi tutte le violazioni elencate sui sorgenti, consegna una nuova versione e ripeti harness_validate.',
                   'blocked': 'Il prodotto non supera il controllo di integrità: correggi la consegna con purpose=delivery.',
                   }.get(report['status'], 'Alcune verifiche non sono state eseguite o richiedono un metodo non disponibile: '
                                           'non dichiarare la consegna; spiega all’utente cosa manca.')
    return json.dumps({'ok': report['status'] == 'passed', 'status': report['status'], 'integrity': report['integrity'],
                       'sheets': saved['sheets'], 'reviews': runs, 'instruction': instruction}, ensure_ascii=False)


async def _harness_validate_async(runtime: Runtime, role_id: str, task: str = '') -> str:
    from .cancellation import call
    return await call(harness_validate.func, runtime=runtime, role_id=role_id, task=task)


harness_validate.coroutine = _harness_validate_async
