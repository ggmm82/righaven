"""Observe genuine CLI JSON events while preserving the final result contract."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time


class ProviderSilence(TimeoutError):
    """A waiting budget expired; this does not assert that the provider is dead."""


def run_cli(args, *, cwd, input, env, timeout, on_event, model_wait_seconds=None, waiting_model=None):
    with tempfile.TemporaryDirectory(prefix='skill-cli-') as directory:
        output, errors = Path(directory) / 'stdout', Path(directory) / 'stderr'
        with output.open('wb') as out, errors.open('wb') as err:
            process = subprocess.Popen(args, cwd=cwd, stdin=subprocess.PIPE, stdout=out, stderr=err, env=env)
            deadline, first, pending = time.monotonic() + timeout, True, b''
            last_event = time.monotonic()
            with output.open('rb') as reader:
                try:
                    while True:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise subprocess.TimeoutExpired(args[0], timeout)
                        try:
                            process.communicate(input=input.encode() if first else None, timeout=min(0.25, remaining))
                            done = True
                        except subprocess.TimeoutExpired:
                            done = False
                        first = False
                        pending += reader.read()
                        lines = pending.split(b'\n')
                        pending = lines.pop()[-1000000:]
                        for line in lines:
                            if len(line) > 1000000:
                                continue
                            try:
                                event = json.loads(line)
                                on_event(event)
                                last_event = time.monotonic()
                            except (ValueError, TypeError, AttributeError):
                                continue
                        if done:
                            break
                        if waiting_model is not None and not waiting_model():
                            last_event = time.monotonic()  # Long native commands have their own budget.
                        elif model_wait_seconds and time.monotonic() - last_event >= model_wait_seconds:
                            raise ProviderSilence('Budget di attesa del modello esaurito senza nuovi eventi; '
                                'file salvati conservati. Ispeziona i risultati e assegna una continuazione mirata.')
                finally:
                    if process.poll() is None:
                        process.kill()
                    process.wait()
        # Large transcripts stay private in this temporary directory, not in
        # the progress API. Native result/error envelopes are at the tail.
        def tail(path):
            with path.open('rb') as stream:
                stream.seek(max(0, os.fstat(stream.fileno()).st_size - 16000000))
                return stream.read().decode('utf-8', errors='replace')
        return subprocess.CompletedProcess(args, process.returncode, tail(output), tail(errors))
