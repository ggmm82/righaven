"""Carry asyncio cancellation into one synchronous, disposable worker only."""
import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
import threading
import time

CURRENT = ContextVar('righaven_worker_cancellation', default=None)


def requested():
    event = CURRENT.get()
    return event is not None and event.is_set()


async def call(function, *args, **kwargs):
    event = threading.Event()
    token = CURRENT.set(event)
    task = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    try:
        # Cancelling the Future alone cannot stop the Python executor thread.
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        event.set()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=45)
        except (Exception, asyncio.CancelledError):
            pass  # Preserve cancellation; the worker monitor owns reclamation.
        raise
    finally:
        CURRENT.reset(token)


@contextmanager
def watch(stop, on_failure):
    event = CURRENT.get()
    if event is None:
        yield
        return
    finished = threading.Event()
    def monitor():
        while not finished.wait(.2):
            if not event.is_set():
                continue
            deadline = time.monotonic() + 30
            while not finished.is_set():
                try:
                    stop()
                    return
                except Exception:
                    # Cancellation may arrive just before docker run creates
                    # the container. Retry only this exact, label-checked job.
                    if time.monotonic() >= deadline:
                        on_failure()
                        return
                    finished.wait(.2)
    thread = threading.Thread(target=monitor, daemon=True, name='skill-worker-stop')
    thread.start()
    try:
        yield
    finally:
        finished.set()
        thread.join(timeout=1)
