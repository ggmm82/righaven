"""On-premise environments: a compute node runs the worker's sandbox, coordinated by this server."""
import io
import json
import os
import subprocess
import tarfile
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from righaven import agent_hub, agents, compute_nodes


def node_state(identifier, offered):
    return {'connected': True, 'compute': offered} if offered else {'connected': False, 'compute': None}


class ComputeNodeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        for p in (patch.object(agents, 'STATE', root / 'state'), patch('righaven.state.STATE', root / 'state'),
                  patch.dict(os.environ, {'RIGHAVEN_DOCKER_SCOPE': 'internal'})):
            p.start()
            self.addCleanup(p.stop)
        (root / 'state').mkdir()
        compute_nodes.LEASES.clear()
        compute_nodes.RUNS.clear()
        self.root = root
        self.offered = {'ag_000000000001': {'cpus': 16.0, 'memory_mib': 65536, 'jobs': 2, 'docker': '27.1', 'running': 0}}
        state = patch.object(agent_hub, 'state', side_effect=lambda i: node_state(i, self.offered.get(i)))
        state.start()
        self.addCleanup(state.stop)
        online = patch.object(agent_hub, 'online', side_effect=lambda i: i in ('ag_000000000001', 'ag_000000000002'))  # 2: a PC, not a node
        online.start()
        self.addCleanup(online.stop)

    def folders(self):
        project, output, progress, job = (self.root / n for n in ('project', 'output', 'progress', 'job.json'))
        project.mkdir(); output.mkdir(); progress.mkdir()
        (project / 'dati.csv').write_text('a,b\n1,2\n')
        os.symlink('/etc/passwd', project / 'link')
        job.write_text('{"task": "x"}')
        args = ['run', '--name', 'rh-job-0123456789ab', '--init', '--cap-drop=ALL', '--memory=4096m', '--cpus=2', '--network=bridge',
                '--mount', f'type=bind,src={project},dst=/mnt/user-data,readonly', '--mount', f'type=bind,src={output},dst=/mnt/user-data/outputs/x',
                '--mount', f'type=bind,src={progress},dst=/mnt/user-data/.righaven-jobs/x', '--mount', f'type=bind,src={job},dst=/job.json,readonly',
                '--env', 'A=1', 'righaven-env:abc', 'python3', '/opt/righaven-worker/run_agent.py', '/job.json']
        return args, project, output, progress

    def test_the_worker_command_is_carried_with_its_folders_and_nothing_else(self):
        args, project, output, progress = self.folders()
        run, template = compute_nodes.prepare('ag_000000000001', args, progress)
        self.assertEqual(compute_nodes._image(template), 'righaven-env:abc')
        self.assertIn('type=bind,src={m0},dst=/mnt/user-data,readonly', template)
        self.assertIn('type=bind,src={m3},dst=/job.json,readonly', template)
        self.assertEqual([(m['key'], m['mode'], m['kind']) for m in run.mounts],
                         [('m0', 'ro', 'dir'), ('m1', 'rw', 'dir'), ('m2', 'live', 'dir'), ('m3', 'ro', 'file')])
        self.assertNotIn(str(project), ' '.join(template))
        with tarfile.open(run.folder / 'bundle.tar.gz') as archive:
            names = archive.getnames()
        self.assertIn('m0/dati.csv', names)
        self.assertIn('m3', names)
        self.assertNotIn('m0/link', names)  # links never leave the server
        for extra in (['--device', '/dev/ttyUSB0'], ['--network=righaven-egress'], ['--privileged'], ['-v', '/:/host']):
            with self.assertRaises(ValueError):
                compute_nodes.prepare('ag_000000000001', args[:3] + extra + args[3:], progress)

    def test_a_run_waits_for_the_node_and_takes_back_only_its_writable_folders(self):
        args, project, output, progress = self.folders()
        (progress / 'progress.json').write_text(json.dumps({'phase': 'starting', 'summary': 'avvio', 'cancel_requested': False}))
        sent = []

        def node(identifier, message):
            sent.append(message)
            if message['type'] != 'run':
                return
            def answer():
                # Meanwhile the owner asked to stop: the server wrote it, the node's copy does not know.
                status = json.loads((progress / 'progress.json').read_text())
                (progress / 'progress.json').write_text(json.dumps({**status, 'cancel_requested': True}))
                buffer = io.BytesIO()
                with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
                    def add(name, data):
                        info = tarfile.TarInfo(name); info.size = len(data)
                        archive.addfile(info, io.BytesIO(data))
                    add('result.json', json.dumps({'returncode': 0, 'stdout': '{"ok": true}', 'oom': False}).encode())
                    add('m1/report.md', b'# fatto')
                    add('m2/status.json', b'{"phase": "done"}')
                    add('m2/progress.json', json.dumps({'phase': 'finalizing', 'summary': 'fatto', 'cancel_requested': False}).encode())
                    add('m0/dati.csv', b'overwritten')       # read only: ignored
                    add('m1/../../escape.txt', b'x')          # outside: ignored
                buffer.seek(0)
                compute_nodes.receive_result(identifier, message['id'], buffer)
            threading.Timer(.1, answer).start()
        with patch.object(agent_hub, 'send', side_effect=node), patch.object(agent_hub, 'owner', return_value='alice'), \
                patch.object(agents, 'log'):
            completed = compute_nodes.run('ag_000000000001', args, timeout=10, live=progress)
        self.assertEqual((completed.returncode, completed.stdout, completed.oom), (0, '{"ok": true}', False))
        self.assertEqual(sent[0]['image'], 'righaven-env:abc')
        self.assertEqual((output / 'report.md').read_text(), '# fatto')
        self.assertEqual((progress / 'status.json').read_text(), '{"phase": "done"}')
        merged = json.loads((progress / 'progress.json').read_text())
        self.assertEqual((merged['phase'], merged['summary'], merged['cancel_requested']), ('finalizing', 'fatto', True))
        self.assertEqual((project / 'dati.csv').read_text(), 'a,b\n1,2\n')
        self.assertFalse((self.root / 'escape.txt').exists())
        self.assertEqual(compute_nodes.RUNS, {})
        with self.assertRaises(LookupError):
            compute_nodes.bundle('ag_000000000001', 'rh-job-0123456789ab')

    def test_a_node_that_never_answers_is_stopped_at_the_deadline(self):
        args, _, _, progress = self.folders()
        sent = []
        with patch.object(agent_hub, 'send', side_effect=lambda i, m: sent.append(m)), patch.object(agent_hub, 'owner', return_value='alice'), \
                patch.object(agents, 'log'):
            with patch('threading.Event.wait', return_value=False):
                with self.assertRaises(subprocess.TimeoutExpired):
                    compute_nodes.run('ag_000000000001', args, timeout=1, live=progress)
        self.assertEqual([m['type'] for m in sent], ['run', 'stop'])

    def test_each_node_shares_its_limits_among_the_tasks_it_accepts(self):
        first = compute_nodes.acquire('ag_000000000001', 'rh-job-000000000001')
        compute_nodes.acquire('ag_000000000001', 'rh-job-000000000002')
        self.assertEqual((first['cpus'], first['memory_mib'], first['threads'], first['node']), (8.0, 32768, 8, 'ag_000000000001'))
        with self.assertRaises(RuntimeError):
            compute_nodes.acquire('ag_000000000001', 'rh-job-000000000003', timeout=.3)
        compute_nodes.release('rh-job-000000000001')
        self.assertEqual(compute_nodes.acquire('ag_000000000001', 'rh-job-000000000003', timeout=1)['cpus'], 8.0)
        self.assertEqual(compute_nodes.free('ag_000000000001'), (0.0, 0))

    def test_where_a_task_runs_follows_its_environment_and_its_connections(self):
        def choose(place, records=(), egress='open'):
            with patch('righaven.environments.preferences', return_value={'dati': {'placement': place}}), \
                    patch.object(agents, 'owned', side_effect=lambda u, i: {'id': i, 'name': 'Workstation'}), \
                    patch.object(agents, 'listing', return_value=[{'id': 'ag_000000000001', 'name': 'Workstation'}, {'id': 'ag_000000000002', 'name': 'PC'}]):
                return compute_nodes.choose('alice', 'dati', list(records), egress=egress)
        db = {'id': 'erp', 'kind': 'sqlserver', 'host': 'sql01.office.local', 'agent': 'ag_000000000001'}
        other = {'id': 'erp2', 'kind': 'postgres', 'host': '10.0.0.4', 'agent': 'ag_000000000002'}
        cloud = {'id': 'saas', 'kind': 'postgres', 'host': 'db.example.org'}
        self.assertIsNone(choose('cloud', [db]))
        self.assertEqual(choose('ag_000000000001', [db, cloud]), 'ag_000000000001')
        self.assertEqual(choose('auto', [db]), 'ag_000000000001')   # next to its on-premise data
        self.assertEqual(choose('auto', [cloud]), 'ag_000000000001')  # the free node
        self.assertIsNone(choose('auto', [other]))                    # through a PC that runs no sandboxes
        self.assertIsNone(choose('auto', [cloud], egress='allowlist'))
        for records, egress in (([other], 'open'), ([cloud], 'allowlist'), ([{'id': 'usb', 'kind': 'device', 'transport': 'local'}], 'open'),
                                ([{'id': 'nas', 'kind': 'postgres', 'host': '172.18.0.9'}], 'open')):
            with self.assertRaises(ValueError):
                choose('ag_000000000001', records, egress)
        with self.assertRaises(ValueError):
            choose('ag_000000000002')  # a PC with no compute offered
        self.offered.clear()
        self.assertIsNone(choose('auto', [cloud]))


FIXTURE = Path(__file__).parents[1] / 'desktop/windows/launcher/testdata/server-args.json'


def server_template():
    """A worker command as delegate writes it, with the node's bundle keys: what the node checks."""
    from righaven import docker_runtime
    with patch.object(docker_runtime, 'OWNER', 'harness'):  # the gateway's host name, which differs on each machine
        args = docker_runtime.base_arguments('rh-job-0123456789ab', {'memory_mib': 2048, 'cpus': 2.0, 'tmp_mib': 512, 'threads': 2})
    args += ['--tmpfs', '/opt/righaven/apps/ffmpeg:ro,size=1m', '--env', 'PATH=/opt/righaven-provider/bin:/usr/bin:/bin',
             '--label', 'org.righaven.harness.installation=0f3c2a9e-5d41-4b7a-9c1e-2b8d7f6a5e40',
             '--label', 'org.righaven.harness.workspace=' + 'a' * 64,
             '--mount', 'type=bind,src={m0},dst=/mnt/user-data,readonly', '--mount', 'type=bind,src={m1},dst=/mnt/user-data/outputs/x',
             '--mount', 'type=bind,src={m2},dst=/job.json,readonly',
             'righaven-env:abc', 'python3', '/opt/righaven-worker/run_agent.py', '/job.json']
    return args


PREPARE_FIXTURE = Path(__file__).parents[1] / 'desktop/windows/launcher/testdata/server-prepare-args.json'


def preparation_template():
    """An environment preparation as the server sends it to a node, with the node's bundle keys."""
    import re
    from righaven import docker_runtime, environment_runtime
    worker = ['--mount', 'type=bind,src=/state/runtime/righaven-worker,dst=/opt/righaven-worker,readonly',
              '--mount', 'type=bind,src=/state/runtime/prepare_environment.py,dst=/opt/righaven/prepare_environment.py,readonly']
    with patch.object(docker_runtime, 'OWNER', 'harness'), patch.object(docker_runtime, 'runtime_arguments', return_value=worker), \
            patch.object(docker_runtime, 'host_path', side_effect=str), \
            patch.object(environment_runtime, 'installation', return_value='0f3c2a9e-5d41-4b7a-9c1e-2b8d7f6a5e40'):
        args = environment_runtime.preparation_arguments('rh-env-0123456789ab-a1b2c3', {'memory_mib': 4096, 'cpus': 4.0, 'tmp_mib': 512, 'threads': 4},
                                                         'b' * 64, 'sha256:' + 'c' * 64, Path('/state/compute-runs/x/environment-request.json'))
    keys = iter(range(10))
    return [re.sub(r'src=[^,]+', lambda m: 'src={m%d}' % next(keys), a) if a.startswith('type=bind') else a for a in args]


class OfflineMachineTests(unittest.TestCase):
    """What happens to a task whose machine is offline: wait N minutes, or run it in the cloud."""
    def setUp(self):
        compute_nodes.LEASES.clear()
        self.online = set()
        for p in (patch.object(agent_hub, 'online', side_effect=lambda i: i in self.online),
                  patch.object(agent_hub, 'state', side_effect=lambda i: node_state(i, {'cpus': 8.0, 'memory_mib': 8192, 'jobs': 1} if i in self.online else None)),
                  patch.object(agents, 'owned', side_effect=lambda u, i: {'id': i, 'name': 'devPc'})):
            p.start()
            self.addCleanup(p.stop)

    def choose(self, unavailable, notes):
        with patch('righaven.environments.preferences', return_value={'dati': {'placement': 'ag_000000000001', 'unavailable': unavailable}}):
            return compute_nodes.choose('alice', 'dati', [], notes=notes)

    def test_an_offline_machine_waits_or_hands_the_task_to_the_cloud_as_chosen(self):
        notes = []
        self.assertIsNone(self.choose('cloud', notes))
        self.assertIn('devPc', notes[0])
        self.assertIn('cloud', notes[0])
        self.assertEqual(self.choose('wait:15', []), 'ag_000000000001')
        with patch('righaven.environments.preferences', return_value={'dati': {'placement': 'ag_000000000001'}}):
            self.assertEqual(compute_nodes.waiting_minutes('alice', 'dati'), 15)  # the default
        for wrong in ('wait:0', 'wait:999', 'later', 'wait:x'):
            with self.assertRaises(ValueError):
                compute_nodes.check_unavailable(wrong)

    def test_the_wait_counts_only_the_time_offline(self):
        with self.assertRaises(RuntimeError) as offline:
            compute_nodes.acquire('ag_000000000001', 'rh-job-000000000001', offline_timeout=.6, label='devPc')
        self.assertIn('devPc', str(offline.exception))
        self.assertIn('scollegata', str(offline.exception))
        threading.Timer(.3, lambda: self.online.add('ag_000000000001')).start()
        lease = compute_nodes.acquire('ag_000000000001', 'rh-job-000000000002', offline_timeout=5, label='devPc')
        self.assertEqual(lease['cpus'], 8.0)
        # Connected but busy: a queue, not an offline machine.
        with self.assertRaises(RuntimeError) as busy:
            compute_nodes.acquire('ag_000000000001', 'rh-job-000000000003', offline_timeout=.3, timeout=1.2, label='devPc')
        self.assertIn('occupata', str(busy.exception))


class ServerArgumentsTests(unittest.TestCase):
    def test_the_nodes_fixture_is_what_the_server_writes(self):
        """The Go test checks this fixture against the node's sandbox rules (TestNodeAcceptsTheServersCommand)."""
        self.assertEqual(json.loads(FIXTURE.read_text())['args'], server_template(),
                         'docker_runtime changed the worker command: update the fixture and the node rules together')


    def test_the_preparation_fixture_is_what_the_server_writes(self):
        """The Go test checks it against the node's rules (TestNodePreparesOnlyRigHavensInstaller)."""
        self.assertEqual(json.loads(PREPARE_FIXTURE.read_text())['args'], preparation_template(),
                         'the environment preparation changed: update the fixture and the node rules together')


class NodeEnvironmentTests(unittest.TestCase):
    """On premise the environment image is prepared and kept on the machine; each place reuses only its own."""
    NODE = 'ag_000000000001'

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name) / 'state'
        root.mkdir()
        from righaven import environment_runtime as env
        self.images = []
        self.runs = []
        self.specs = {}
        def recipe(tools, versions=None, **_):
            key = ''.join(sorted(tools)).encode().hex().ljust(64, '0')[:64]
            return key, {'version': 1, 'core': 'sha256:' + 'c' * 64, 'tools': sorted(tools),
                         'tool_fingerprints': {t: 'f-' + t for t in tools}}
        def run(node, args, *, timeout, live=None, preparation=None):
            self.runs.append((args, preparation))
            image = 'sha256:' + str(len(self.runs)) * 64
            return SimpleNamespace(returncode=0, stdout='{"phase":"verified","installed_versions":{"blender":"4.2"}}\n', stderr='',
                                   oom=False, image_id=image, size_bytes=1 << 30)
        for p in (patch('righaven.state.STATE', root), patch.object(env, 'recipe', side_effect=recipe),
                  patch.object(env, 'write_descriptor', side_effect=lambda path, *a: path),
                  patch.object(env, 'preparation_arguments', side_effect=lambda name, limits, key, base, *a: ['run', '--name', name, base]),
                  patch.object(env, 'image_tag', side_effect=lambda key: 'skill-environment:000000000000-' + key),
                  patch.object(compute_nodes, 'run', side_effect=run),
                  patch.object(agent_hub, 'state', side_effect=lambda i: {'compute': {'cpus': 4.0, 'memory_mib': 8192, 'jobs': 1, 'images': list(self.images)}}),
                  patch.object(agent_hub, 'note_image', side_effect=lambda node, image: self.images.append(image))):
            p.start()
            self.addCleanup(p.stop)
        self.env = env

    def prepare(self, tools):
        return compute_nodes.prepare_environment(self.NODE, 'rh-job-0123456789ab', tools, resources={'cpus': 4.0}, label='devPc')

    def test_prepared_on_the_machine_then_reused_there(self):
        first = self.prepare(['blender'])
        self.assertEqual(len(self.runs), 1)
        args, preparation = self.runs[0]
        self.assertEqual(args[-1], 'sha256:' + 'c' * 64)  # from the core image, not from a server environment
        self.assertEqual(preparation['environment'], first['id'])
        self.assertEqual((first['node'], first['installed_versions']), (self.NODE, {'blender': '4.2'}))
        again = self.prepare(['blender'])
        self.assertEqual((len(self.runs), again['image_id']), (1, first['image_id']))
        # Nothing of the machine's environments is in this server's cache.
        self.assertEqual(list(self.env._records()), [])

    def test_a_larger_environment_starts_from_the_machines_closest_image(self):
        first = self.prepare(['blender'])
        self.prepare(['blender', 'ffmpeg'])
        self.assertEqual(self.runs[1][0][-1], first['image_id'])

    def test_an_image_the_machine_removed_is_prepared_again(self):
        self.prepare(['blender'])
        self.images.clear()  # the node pruned it
        self.prepare(['blender'])
        self.assertEqual(len(self.runs), 2)

    def test_the_servers_images_are_never_used_on_the_machine(self):
        from righaven.state import atomic_json
        key, spec = self.env.recipe(['blender'])
        self.env.folder()
        atomic_json(self.env.record_path(key), {'id': key, 'status': 'ready', 'tools': ['blender'], 'core': spec['core'],
                                                'tool_fingerprints': spec['tool_fingerprints'], 'image_id': 'sha256:' + 'e' * 64, 'image': 'x'})
        self.images.append('sha256:' + 'e' * 64)  # even an image with the same ID on the machine
        self.prepare(['blender'])
        self.assertEqual(len(self.runs), 1)
        self.assertEqual(self.runs[0][0][-1], 'sha256:' + 'c' * 64)

    def test_only_the_preparation_may_add_the_installers_capabilities(self):
        args = ['run', '--name', 'rh-env-0123456789ab-a1b2c3', '--cap-drop=ALL', '--cap-add', 'CHOWN', 'img', 'python3', 'x']
        with patch('righaven.state.STATE', Path(self.temp.name) / 'state'):
            _, template = compute_nodes.prepare(self.NODE, args, None, preparation=True)
        self.assertEqual(template[3:6], ['--cap-drop=ALL', '--cap-add', 'CHOWN'])
        with self.assertRaises(ValueError):
            compute_nodes.prepare(self.NODE, args, None)  # a task never
        with self.assertRaises(ValueError):
            compute_nodes.prepare(self.NODE, args[:5] + ['SYS_ADMIN'] + args[6:], None, preparation=True)


class HubComputeTests(unittest.TestCase):
    def test_declared_capacity_is_bounded(self):
        self.assertEqual(agent_hub.compute({'cpus': 12, 'memory_mib': 49152, 'jobs': 2, 'docker': '27.1'}),
                         {'cpus': 12.0, 'memory_mib': 49152, 'jobs': 2, 'docker': '27.1', 'running': 0})
        for wrong in (None, {}, {'cpus': 0, 'memory_mib': 4096}, {'cpus': 4, 'memory_mib': 100}, {'cpus': 4, 'memory_mib': 4096, 'jobs': 500}, {'cpus': 'x'}):
            self.assertIsNone(agent_hub.compute(wrong))
        reported = agent_hub.compute({'cpus': 4, 'memory_mib': 8192, 'images': ['sha256:' + 'a' * 64, 'nginx:latest', 3]})
        self.assertEqual(reported['images'], ['sha256:' + 'a' * 64])


if __name__ == '__main__':
    unittest.main()
