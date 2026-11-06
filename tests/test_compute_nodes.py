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
        sent = []

        def node(identifier, message):
            sent.append(message)
            if message['type'] != 'run':
                return
            def answer():
                buffer = io.BytesIO()
                with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
                    def add(name, data):
                        info = tarfile.TarInfo(name); info.size = len(data)
                        archive.addfile(info, io.BytesIO(data))
                    add('result.json', json.dumps({'returncode': 0, 'stdout': '{"ok": true}', 'oom': False}).encode())
                    add('m1/report.md', b'# fatto')
                    add('m2/status.json', b'{"phase": "done"}')
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


class HubComputeTests(unittest.TestCase):
    def test_declared_capacity_is_bounded(self):
        self.assertEqual(agent_hub.compute({'cpus': 12, 'memory_mib': 49152, 'jobs': 2, 'docker': '27.1'}),
                         {'cpus': 12.0, 'memory_mib': 49152, 'jobs': 2, 'docker': '27.1', 'running': 0})
        for wrong in (None, {}, {'cpus': 0, 'memory_mib': 4096}, {'cpus': 4, 'memory_mib': 100}, {'cpus': 4, 'memory_mib': 4096, 'jobs': 500}, {'cpus': 'x'}):
            self.assertIsNone(agent_hub.compute(wrong))


if __name__ == '__main__':
    unittest.main()
