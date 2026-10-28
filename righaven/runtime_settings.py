"""One installation-wide resource budget, inherited by every specialist."""
import json
import math
import subprocess
import time

from . import state

_cache = None


def capacity():
    global _cache
    if _cache and time.monotonic() - _cache[0] < 60:
        return _cache[1]
    try:
        data = json.loads(subprocess.check_output(['docker', 'info', '--format', '{{json .}}'], text=True, timeout=5))
        value = {'cpus': max(1, int(data['NCPU'])), 'memory_mib': int(data['MemTotal']) // 1048576, 'detected': True}
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        value = {'cpus': 2, 'memory_mib': 4096, 'detected': False}
    _cache = time.monotonic(), value
    return value


def settings():
    path = state.STATE / 'runtime.json'
    return json.loads(path.read_text()) if path.exists() else {'mode': 'auto', 'cpus': 1.5, 'memory_mib': 1536}


def effective(value=None):
    host = capacity()
    value = value or settings()
    memory_ceiling = max(512, host['memory_mib'] - 2048)
    if value['mode'] == 'auto':
        cpus = max(.5, min(4, host['cpus'] - .5))
        memory = min(6144, memory_ceiling)
    else:
        cpus, memory = value['cpus'], value['memory_mib']
        if cpus > host['cpus'] or memory > memory_ceiling:
            raise ValueError('Budget superiore alla capacità disponibile dopo la riserva per i servizi. Usa Automatico o riduci CPU/RAM.')
    return {'cpus': cpus, 'memory_mib': memory, 'tmp_mib': min(1024, max(128, memory // 4)),
            'threads': max(1, math.ceil(cpus)), 'model_wait_seconds': value.get('model_wait_seconds', 0), 'capacity_detected': host['detected'], 'max_workers': value.get('max_workers',2)}


def read():
    value = settings()
    try:
        limits = effective(value)
        warning = ''
    except ValueError as error:
        limits, warning = effective({'mode': 'auto'}), str(error)
    return {'settings': value, 'effective': limits, 'host': capacity(), 'warning': warning}


def save(value):
    if value.get('mode') not in ('auto', 'manual') or type(value.get('cpus')) not in (int, float) or not math.isfinite(value['cpus']) or not .5 <= value['cpus'] <= 32 or type(value.get('memory_mib')) is not int or not 512 <= value['memory_mib'] <= 65536:
        raise ValueError('Budget non valido: CPU 0,5–32 e RAM 512–65536 MiB')
    if type(value.get('model_wait_seconds', 0)) is not int or value.get('model_wait_seconds', 0) != 0 and not 60 <= value.get('model_wait_seconds', 0) <= 1500:
        raise ValueError('Budget di attesa modello: 0 (disattivato) oppure da 60 a 1500 secondi')
    if type(value.get('max_workers',2)) is not int or not 1<=value.get('max_workers',2)<=8:
        raise ValueError('Operazioni parallele: scegli un limite da 1 a 8')
    effective(value)
    with state.LOCK:
        state.atomic_json(state.STATE / 'runtime.json', value)
    return read()
