"""Workers reach only the domains granted to their job; refusals are reported."""
import asyncio
import base64
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch

from righaven import egress_policy, egress_proxy


def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


class PolicyTests(unittest.TestCase):
    def test_provider_is_always_granted_and_roles_add_reasoned_domains(self):
        network = egress_policy.validate_network([{'domain': 'Fonts.googleapis.com', 'reason': 'Web fonts for the poster'},
                                                  {'domain': '.example.org', 'reason': 'Public dataset mirrors'}])
        self.assertEqual(network[0]['domain'], 'fonts.googleapis.com')
        domains = egress_policy.allowed_domains('openai', network, 'https://llm.internal.example.com/v1')
        self.assertEqual(domains, ['llm.internal.example.com', 'fonts.googleapis.com', '.example.org'])
        self.assertIn('api.anthropic.com', egress_policy.allowed_domains('claude'))
        self.assertEqual(egress_policy.validate_network(None), [])

    def test_invalid_grants_are_refused(self):
        for value in ([{'domain': 'example.org'}], [{'domain': '10.0.0.1', 'reason': 'x'}], [{'domain': '.org', 'reason': 'x'}],
                      [{'domain': 'localhost', 'reason': 'x'}], [{'domain': f'd{i}.example.org', 'reason': 'x'} for i in range(9)], 'example.org'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                egress_policy.validate_network(value)

    def test_roles_keep_their_reasoned_network_grants(self):
        from righaven.project_skills import validate_roles
        base = {'id': 'designer', 'title': 'Designer', 'mission': 'Poster', 'expertise': ['Layout'], 'procedure': ['Draft'],
                'checks': ['Reopen'], 'deliverables': ['PDF']}
        roles = validate_roles([{**base, 'network': [{'domain': 'fonts.googleapis.com', 'reason': 'Web fonts'}]}], [])
        self.assertEqual(roles[0]['network'], [{'domain': 'fonts.googleapis.com', 'reason': 'Web fonts'}])
        self.assertNotIn('network', validate_roles([base], [])[0])
        with self.assertRaises(ValueError):
            validate_roles([{**base, 'network': [{'domain': 'fonts.googleapis.com'}]}], [])

    def test_mode_defaults_to_open(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('RIGHAVEN_WORKER_EGRESS', None)
            self.assertEqual(egress_policy.mode(), 'open')
        with patch.dict(os.environ, {'RIGHAVEN_WORKER_EGRESS': 'allowlist'}):
            self.assertEqual(egress_policy.mode(), 'allowlist')
        with patch.dict(os.environ, {'RIGHAVEN_WORKER_EGRESS': 'closed'}), self.assertRaises(ValueError):
            egress_policy.mode()

    def test_suffix_and_exact_matching(self):
        self.assertTrue(egress_proxy.matches('www.googleapis.com', ['.googleapis.com']))
        self.assertTrue(egress_proxy.matches('googleapis.com.', ['.googleapis.com']))
        self.assertFalse(egress_proxy.matches('evilgoogleapis.com', ['.googleapis.com']))
        self.assertFalse(egress_proxy.matches('api.openai.com.evil.net', ['api.openai.com']))

    def test_private_destinations_are_refused_even_when_named(self):
        self.assertIsNone(egress_proxy.public('127.0.0.1', 80))
        self.assertIsNone(egress_proxy.public('localhost', 80))


class ProxyTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.rules, self.log = Path(temp.name) / 'rules', Path(temp.name) / 'log'
        self.rules.mkdir()
        # An upstream HTTP server standing in for the Internet.
        self.upstream = socket.socket(); self.upstream.bind(('127.0.0.1', 0)); self.upstream.listen()
        self.upstream_port = self.upstream.getsockname()[1]
        threading.Thread(target=self.serve_upstream, daemon=True).start()
        self.port = free_port()
        self.loop = asyncio.new_event_loop()
        patches = [patch.object(egress_proxy, 'RULES', self.rules), patch.object(egress_proxy, 'LOG', self.log),
                   patch.object(egress_proxy, 'PORTS', {80, 443, self.upstream_port}),
                   patch.object(egress_proxy, 'public', lambda host, port: '127.0.0.1')]
        for item in patches:
            item.start(); self.addCleanup(item.stop)
        started = threading.Event()

        def run():
            asyncio.set_event_loop(self.loop)
            server = self.loop.run_until_complete(asyncio.start_server(egress_proxy.handle, '127.0.0.1', self.port))
            started.set()
            self.loop.run_forever()
            server.close()
        threading.Thread(target=run, daemon=True).start()
        started.wait(5)
        self.addCleanup(lambda: self.loop.call_soon_threadsafe(self.loop.stop))
        self.addCleanup(self.upstream.close)
        self.token = 'a' * 32
        (self.rules / (self.token + '.json')).write_text(json.dumps({'job': 'rh-job-1', 'domains': ['allowed.example.com']}))

    def serve_upstream(self):
        while True:
            try:
                connection, _ = self.upstream.accept()
            except OSError:
                return
            with connection:
                request = connection.recv(65536)
                body = b'reached ' + request.split(b'\r\n', 1)[0]
                connection.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: ' + str(len(body)).encode() + b'\r\nConnection: close\r\n\r\n' + body)

    def ask(self, head):
        with socket.create_connection(('127.0.0.1', self.port), timeout=5) as client:
            client.sendall(head)
            data = b''
            while chunk := client.recv(65536):
                data += chunk
                if head.startswith(b'CONNECT') and b'\r\n\r\n' in data:
                    if data.startswith(b'HTTP/1.1 200'):
                        client.sendall(b'GET /inside HTTP/1.1\r\nHost: allowed.example.com\r\n\r\n')
                        data += client.recv(65536)
                    break
            return data

    def auth(self, token=None, job='rh-job-1'):
        return b'Proxy-Authorization: Basic ' + base64.b64encode(f'{job}:{token or self.token}'.encode()) + b'\r\n'

    def test_granted_domain_is_tunnelled_and_forwarded(self):
        tunnel = self.ask(b'CONNECT allowed.example.com:%d HTTP/1.1\r\n' % self.upstream_port + self.auth() + b'\r\n')
        self.assertTrue(tunnel.startswith(b'HTTP/1.1 200'))
        self.assertIn(b'reached GET /inside', tunnel)
        forwarded = self.ask(b'GET http://allowed.example.com:%d/page HTTP/1.1\r\nHost: allowed.example.com\r\n' % self.upstream_port + self.auth() + b'\r\n')
        self.assertIn(b'reached GET /page HTTP/1.1', forwarded)
        self.assertFalse((self.log / (self.token + '.jsonl')).exists())

    def test_other_domains_ports_and_credentials_are_refused_and_logged(self):
        self.assertTrue(self.ask(b'CONNECT other.example.com:443 HTTP/1.1\r\n' + self.auth() + b'\r\n').startswith(b'HTTP/1.1 403'))
        self.assertTrue(self.ask(b'CONNECT allowed.example.com:22 HTTP/1.1\r\n' + self.auth() + b'\r\n').startswith(b'HTTP/1.1 403'))
        self.assertTrue(self.ask(b'CONNECT 93.184.216.34:443 HTTP/1.1\r\n' + self.auth() + b'\r\n').startswith(b'HTTP/1.1 403'))
        self.assertTrue(self.ask(b'CONNECT allowed.example.com:443 HTTP/1.1\r\n\r\n').startswith(b'HTTP/1.1 407'))
        self.assertTrue(self.ask(b'CONNECT allowed.example.com:443 HTTP/1.1\r\n' + self.auth('b' * 32) + b'\r\n').startswith(b'HTTP/1.1 407'))
        self.assertTrue(self.ask(b'CONNECT allowed.example.com:443 HTTP/1.1\r\n' + self.auth(job='rh-job-2') + b'\r\n').startswith(b'HTTP/1.1 407'))
        events = [json.loads(line) for line in (self.log / (self.token + '.jsonl')).read_text().splitlines()]
        self.assertEqual([(e['host'], e['port'], e['reason']) for e in events],
                         [('other.example.com', 443, 'domain'), ('allowed.example.com', 22, 'port'), ('93.184.216.34', 443, 'address')])


class GrantTests(unittest.TestCase):
    def test_worker_moves_to_the_internal_network_and_the_grant_ends_with_the_job(self):
        from righaven import state, worker_egress
        with tempfile.TemporaryDirectory() as directory, patch.object(state, 'STATE', Path(directory)), \
                patch.object(worker_egress, 'STATE', Path(directory)):
            grant = worker_egress.Grant('rh-job-7', ['api.openai.com'])
            args = grant.arguments(['run', '--name', 'rh-job-7', '--network=bridge', '--tmpfs', '/tmp', 'image'])
            self.assertNotIn('--network=bridge', args)
            self.assertEqual(args[args.index('--network=righaven-egress') + 1], '--env')
            self.assertIn(f'HTTPS_PROXY=http://rh-job-7:{grant.token}@righaven-egress-proxy:3128', args)
            self.assertEqual(args[-1], 'image')
            rule = json.loads((grant.rules / (grant.token + '.json')).read_text())
            self.assertEqual(rule, {'job': 'rh-job-7', 'domains': ['api.openai.com']})
            (grant.log / (grant.token + '.jsonl')).write_text('\n'.join(json.dumps({'host': 'x.example.com', 'port': 443, 'reason': 'domain'}) for _ in range(3)))
            self.assertEqual(worker_egress.summary(grant.close()), [{'destination': 'x.example.com:443', 'attempts': 3}])
            self.assertEqual(list(grant.rules.iterdir()), [])
            self.assertEqual(list(grant.log.iterdir()), [])
            with self.assertRaises(ValueError):
                worker_egress.Grant('rh-job-8', []).arguments(['run', '--network=none', 'image'])


class StatusTests(unittest.TestCase):
    def test_the_assignment_card_receives_only_sanitized_egress_fields(self):
        from righaven.progress import public_status
        status = public_status({'egress': {'mode': 'allowlist', 'domains': ['api.openai.com', 7], 'token': 'secret',
                                           'refused': [{'destination': 'x.example.com:443', 'attempts': 2, 'job': 'rh'}, 'bad']}})
        self.assertEqual(status['egress'], {'mode': 'allowlist', 'domains': ['api.openai.com'],
                                            'refused': [{'destination': 'x.example.com:443', 'attempts': 2}]})
        self.assertNotIn('egress', public_status({'egress': {'mode': 'open'}}))


if __name__ == '__main__':
    unittest.main()
