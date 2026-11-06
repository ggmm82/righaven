"""RigHaven Agent: pairing, tokens, the channel, actions and tunnels between the server and a PC."""
import asyncio
import json
import os
import struct
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from righaven import agent_hub, agents, host_bridge


class FakeSocket:
    """The server side of an agent's WebSocket: frames the agent sends, frames the server sent."""
    def __init__(self):
        self.incoming = asyncio.Queue()
        self.sent = []
        self.closed = None

    async def receive(self):
        return await self.incoming.get()

    async def send_text(self, text):
        self.sent.append(json.loads(text))

    async def send_bytes(self, data):
        self.sent.append(data)

    async def close(self, code=1000):
        self.closed = code
        await self.incoming.put({'type': 'websocket.disconnect'})

    def text(self, value):
        self.incoming.put_nowait({'type': 'websocket.receive', 'text': json.dumps(value)})


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        for p in (patch.object(agents, 'STATE', Path(self.temp.name)), patch.dict(os.environ, {'RIGHAVEN_HOST_DIR': self.temp.name + '/host'})):
            p.start()
            self.addCleanup(p.stop)
        agents._failures.clear()
        agent_hub.SESSIONS.clear(), agent_hub.JOBS.clear(), agent_hub.TUNNELS.clear()

    def test_a_pairing_code_is_used_once_and_tokens_are_kept_as_hashes(self):
        code = agents.create_code('alice', 'PC di casa')['code']
        paired = agents.redeem(code.lower(), 'windows', '1.0.0')
        self.assertTrue(paired['token'].startswith('rha_'))
        stored = (Path(self.temp.name) / agents.FILE).read_text()
        self.assertNotIn(paired['token'], stored)
        self.assertNotIn(code.replace('-', ''), stored)
        self.assertEqual(agents.authenticate(paired['token'])['user'], 'alice')
        self.assertIsNone(agents.authenticate('rha_wrong'))
        with self.assertRaises(PermissionError):
            agents.redeem(code)
        self.assertEqual([a['name'] for a in agents.listing('alice')], ['PC di casa'])
        self.assertEqual(agents.listing('bob'), [])
        with self.assertRaises(ValueError):
            agents.owned('bob', paired['agent'])
        agents.revoke('alice', paired['agent'])
        self.assertIsNone(agents.authenticate(paired['token']))
        self.assertEqual([r['action'] for r in agents.activity('alice')][:2], ['revoked', 'paired'])

    def test_guessing_codes_is_blocked(self):
        for _ in range(agents.MAX_FAILED_REDEEMS):
            with self.assertRaises(PermissionError):
                agents.redeem('AAAAA-AAAAA')
        good = agents.create_code('alice', 'PC')['code']
        with self.assertRaises(PermissionError):
            agents.redeem(good)

    def test_actions_and_tunnels_go_through_the_channel(self):
        paired = agents.redeem(agents.create_code('alice', 'PC di casa')['code'], 'windows', '1.0.0')
        agent = agents.authenticate(paired['token'])
        socket = FakeSocket()
        outcome = {}

        def server_thread(loop):
            # Calls made by the page and the chat run in worker threads.
            while not agent_hub.online(agent['id']):
                pass
            while 'net-scan' not in agent_hub.state(agent['id'])['actions']:
                pass
            self.assertEqual(host_bridge.pick('alice'), agent['id'])
            with self.assertRaises(ValueError):
                host_bridge.pick('bob', agent['id'])
            outcome['scan'] = host_bridge.run('net-scan', {'network': '192.168.1.0/24'}, timeout=10, poll=0.05, agent=agent['id'])
            outcome['tunnel'] = agent_hub.tunnel(agent['id'], 'com:COM5')

        async def agent_side():
            loop = asyncio.get_running_loop()
            serving = asyncio.create_task(agent_hub.serve(socket, agent))
            socket.text({'type': 'hello', 'platform': 'windows', 'version': '1.0.0', 'actions': ['net-scan', 'bluetooth-scan'],
                         'networks': ['192.168.1.0/24', '8.8.8.0/24']})
            worker = threading.Thread(target=server_thread, args=(loop,))
            worker.start()
            while not any(isinstance(m, dict) and m.get('type') == 'request' for m in socket.sent):
                await asyncio.sleep(0.01)
            request = next(m for m in socket.sent if isinstance(m, dict) and m.get('type') == 'request')
            self.assertEqual((request['action'], request['args']), ('net-scan', {'network': '192.168.1.0/24'}))
            socket.text({'type': 'result', 'id': request['id'], 'result': {'devices': [{'address': '192.168.1.44', 'ports': [6668]}]}})
            while 'tunnel' not in outcome and worker.is_alive():
                await asyncio.sleep(0.01)
            host, port = outcome['tunnel']
            # A worker opens the tunnel: the agent is asked to open COM5, then bytes flow both ways.
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            while not any(isinstance(m, dict) and m.get('type') == 'open' for m in socket.sent):
                await asyncio.sleep(0.01)
            opened = next(m for m in socket.sent if isinstance(m, dict) and m.get('type') == 'open')
            self.assertEqual(opened['target'], 'com:COM5')
            socket.text({'type': 'opened', 'stream': opened['stream']})
            writer.write(b'AT\r')
            await writer.drain()
            while not any(isinstance(m, bytes) for m in socket.sent):
                await asyncio.sleep(0.01)
            frame = next(m for m in socket.sent if isinstance(m, bytes))
            self.assertEqual(frame, struct.pack('>I', opened['stream']) + b'AT\r')
            socket.incoming.put_nowait({'type': 'websocket.receive', 'bytes': struct.pack('>I', opened['stream']) + b'ELM327 v1.5\r'})
            self.assertEqual(await asyncio.wait_for(reader.read(100), 5), b'ELM327 v1.5\r')
            writer.close()
            worker.join(10)
            self.assertEqual(agent_hub.state(agent['id'])['networks'], ['192.168.1.0/24'])  # only private networks
            await socket.close()
            await serving
            for server, _ in agent_hub.TUNNELS.values():
                server.close()

        asyncio.run(asyncio.wait_for(agent_side(), 30))
        self.assertEqual(outcome['scan'], {'devices': [{'address': '192.168.1.44', 'ports': [6668]}]})
        self.assertFalse(agent_hub.online(agent['id']))
        actions = [r['action'] for r in agents.activity('alice')]
        for expected in ('connected', 'net-scan', 'tunnel', 'disconnected'):
            self.assertIn(expected, actions)

    def test_a_disconnected_agent_fails_pending_work_and_cannot_be_asked(self):
        with self.assertRaises(ValueError):
            agent_hub.request('ag_000000000000', 'net-scan', {'network': '192.168.1.0/24'})
        with self.assertRaises(ValueError):
            agent_hub.tunnel('ag_000000000000', 'com:COM5')
        with self.assertRaises(ValueError):
            host_bridge.pick('alice')


HOSTINGER = Path(__file__).parents[1] / 'config/compose.hostinger.template.yaml'


class PublicAddressTests(unittest.TestCase):
    class Request:
        def __init__(self, headers, scheme='http', netloc='gateway:8001'):
            from types import SimpleNamespace
            self.headers, self.url = headers, SimpleNamespace(scheme=scheme, netloc=netloc)

    def test_behind_traefik_the_agent_gets_the_https_address(self):
        from righaven.agents import public_address
        with patch.dict(os.environ, {'BETTER_AUTH_URL': 'https://righaven.example.org/', 'RIGHAVEN_PUBLIC_URL': ''}):
            self.assertEqual(public_address(self.Request({'host': 'gateway:8001'})), 'https://righaven.example.org')
        with patch.dict(os.environ, {'BETTER_AUTH_URL': 'http://localhost:2026', 'RIGHAVEN_PUBLIC_URL': ''}):
            forwarded = {'host': 'pc.lan:2026', 'x-forwarded-proto': 'https', 'x-forwarded-host': 'rh.example.org'}
            self.assertEqual(public_address(self.Request(forwarded)), 'https://rh.example.org')
            self.assertEqual(public_address(self.Request({'host': 'pc.lan:2026'})), 'http://pc.lan:2026')

    @unittest.skipUnless(HOSTINGER.exists(), 'the gateway image check mounts only the tests')
    def test_the_hostinger_compose_routes_the_agent_to_the_gateway_without_a_password_middleware(self):
        import yaml
        compose = yaml.safe_load(HOSTINGER.read_text())
        labels = compose['services']['gateway']['labels']
        rule = next(l for l in labels if '-gateway.rule=' in l)
        self.assertIn('PathPrefix(`/api`)', rule)  # /api/webhooks/righaven-agent/* and its WebSocket
        self.assertFalse([l for l in labels if '-gateway.middlewares=' in l or 'basicauth' in l.lower()])


if __name__ == '__main__':
    unittest.main()
