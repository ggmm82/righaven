"""Outbound proxy for assignment workers: only the domains granted to each job.

Workers on the internal network have no route to the Internet; this proxy is
their only exit. Each job authenticates with its own token (Proxy-Authorization
Basic job:token) and the Gateway writes the job's grant to RULES/<token>.json
before the worker starts and deletes it afterwards. Every refused connection is
appended to LOG/<token>.jsonl so the Gateway can report it on the assignment.

Standard library only: the proxy runs inside the worker software image.
"""
import asyncio
import base64
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import time

RULES = Path(os.getenv('RIGHAVEN_EGRESS_RULES', '/egress/rules'))
LOG = Path(os.getenv('RIGHAVEN_EGRESS_LOG', '/egress/log'))
TOKEN = re.compile(r'[0-9a-f]{32,64}')
HOST = re.compile(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,62}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,62}[A-Za-z0-9])?)+')
PORTS = {80, 443}
HEAD_LIMIT = 16384


def matches(host, domains):
    """host is granted by an exact domain or by a '.suffix' entry."""
    host = host.lower().rstrip('.')
    for domain in domains:
        domain = domain.lower()
        if domain.startswith('.') and (host.endswith(domain) or host == domain[1:]) or host == domain:
            return True
    return False


def public(host, port):
    """Resolve and refuse private, loopback and link-local targets (no pivot to the Gateway or metadata)."""
    addresses = {info[4][0] for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
    for address in addresses:
        ip = ipaddress.ip_address(address.split('%')[0])
        if not ip.is_global:
            return None
    return sorted(addresses)[0] if addresses else None


def grant(header):
    """(token, rule) for a valid Proxy-Authorization header, else (None, None)."""
    if not header or not header.lower().startswith('basic '):
        return None, None
    try:
        user, _, token = base64.b64decode(header[6:].strip()).decode().partition(':')
    except (ValueError, UnicodeDecodeError):
        return None, None
    if not TOKEN.fullmatch(token):
        return None, None
    try:
        rule = json.loads((RULES / (token + '.json')).read_text())
    except (OSError, ValueError):
        return None, None
    if not isinstance(rule, dict) or rule.get('job') != user or not isinstance(rule.get('domains'), list):
        return None, None
    return token, rule


def refuse_log(token, rule, host, port, reason):
    if not token:
        return
    try:
        LOG.mkdir(parents=True, exist_ok=True)
        with (LOG / (token + '.jsonl')).open('a') as stream:
            stream.write(json.dumps({'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'job': rule.get('job'),
                                     'host': host[:255], 'port': port, 'reason': reason}) + '\n')
    except OSError:
        pass


def decide(token, rule, host, port):
    """None when allowed, otherwise the refusal reason."""
    if rule is None:
        return 'unauthenticated'
    if port not in PORTS:
        return 'port'
    if not HOST.fullmatch(host or '') or host.rsplit('.', 1)[-1].isdigit():
        return 'address'
    if not matches(host, rule['domains']):
        return 'domain'
    return None


async def pipe(reader, writer):
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, OSError):
        pass
    finally:
        try:
            writer.close()
        except OSError:
            pass


async def reply(writer, status, text):
    writer.write(f'HTTP/1.1 {status} {text}\r\nContent-Length: 0\r\nConnection: close\r\n'.encode()
                 + (b'Proxy-Authenticate: Basic realm="righaven"\r\n' if status == 407 else b'') + b'\r\n')
    await writer.drain()
    writer.close()


async def handle(reader, writer):
    try:
        head = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 30)
    except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, asyncio.TimeoutError, ConnectionError):
        writer.close()
        return
    lines = head.decode('latin-1').split('\r\n')
    try:
        method, target, version = lines[0].split(' ')
    except ValueError:
        return await reply(writer, 400, 'Bad Request')
    headers = [line.split(':', 1) for line in lines[1:] if ':' in line]
    authorization = next((v.strip() for k, v in headers if k.strip().lower() == 'proxy-authorization'), '')
    token, rule = grant(authorization)
    if method == 'CONNECT':
        host, _, port = target.rpartition(':')
        path = None
    else:
        match = re.fullmatch(r'http://([^/:]+)(?::(\d+))?(/.*)?', target)
        if not match:
            return await reply(writer, 400, 'Bad Request')
        host, port, path = match.group(1), match.group(2) or '80', match.group(3) or '/'
    host = host.strip('[]')
    try:
        port = int(port)
    except ValueError:
        return await reply(writer, 400, 'Bad Request')
    reason = decide(token, rule, host, port)
    address = None
    if reason is None:
        try:
            address = await asyncio.get_running_loop().run_in_executor(None, public, host, port)
        except OSError:
            reason = 'dns'
        else:
            reason = None if address else 'private'
    if reason:
        refuse_log(token, rule, host, port, reason)
        return await (reply(writer, 407, 'Proxy Authentication Required') if reason == 'unauthenticated' else reply(writer, 403, 'Forbidden'))
    try:
        upstream_reader, upstream_writer = await asyncio.wait_for(asyncio.open_connection(address, port), 30)
    except (OSError, asyncio.TimeoutError):
        return await reply(writer, 502, 'Bad Gateway')
    if path is None:
        writer.write(b'HTTP/1.1 200 Connection Established\r\n\r\n')
        await writer.drain()
    else:
        kept = ''.join(f'{k}:{v}\r\n' for k, v in headers if not k.strip().lower().startswith('proxy-') and k.strip().lower() != 'connection')
        upstream_writer.write(f'{method} {path} {version}\r\n{kept}Connection: close\r\n\r\n'.encode('latin-1'))
        await upstream_writer.drain()
    await asyncio.gather(pipe(reader, upstream_writer), pipe(upstream_reader, writer))


async def serve(host='0.0.0.0', port=3128):
    server = await asyncio.start_server(handle, host, port, limit=HEAD_LIMIT)
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    asyncio.run(serve(port=int(os.getenv('RIGHAVEN_EGRESS_PORT', '3128'))))
