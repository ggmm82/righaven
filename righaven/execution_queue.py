"""FIFO worker admission, durable waiting status, and explicit restart recovery.

The Gateway admits a configured number of isolated workers. Waiting does not consume the worker budget
or require a browser connection. Restart recovery never silently replays work.
"""
from pathlib import Path
from contextlib import nullcontext
import threading
import time

from .progress import job_path, read_status, update, utcnow
from .state import atomic_json


class ExecutionQueue:
    def __init__(self):
        self.condition = threading.Condition()
        self.waiters = []

    def acquire(self, slot, progress, state, cancelled):
        # Keep foreground demand registered between non-blocking FIFO probes.
        # Otherwise another preload could overtake a queued chat after cleanup.
        with getattr(slot,'foreground_request',nullcontext)():
            return self._acquire(slot,progress,state,cancelled)

    def _acquire(self, slot, progress, state, cancelled):
        progress = Path(progress)
        ticket = Path(state) / 'execution-queue' / (progress.parent.name + '.json')
        ticket.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        admitted = False
        with self.condition:
            self.waiters.append(progress)
            try:
                atomic_json(ticket, {'progress': str(progress), 'queued_at': utcnow()})
                update(progress, can_stop=True)
                refreshed = 0
                while True:
                    status = read_status(progress)
                    if cancelled() or status.get('cancel_requested'):
                        update(progress, 'failed', 'Incarico annullato prima dell’avvio',
                               cancel_requested=True, resources_reclaimed=True, queue_position=0,
                               error_code='queue_cancelled')
                        return False
                    if self.waiters[0] == progress and slot.acquire(blocking=False):
                        admitted = True
                        update(progress, 'starting', queue_position=0,queue_reason='',queue_detail='',queue_activity_since='')
                        return True
                    position = self.waiters.index(progress) + 1
                    info=slot.waiting_info() if hasattr(slot,'waiting_info') else {}
                    if status.get('queue_position') != position or status.get('queue_reason')!=info.get('queue_reason') or time.monotonic() - refreshed >= 3:
                        update(progress, queue_position=position, heartbeat_at=utcnow(),**info)
                        refreshed = time.monotonic()
                    self.condition.wait(timeout=.25)
            except BaseException:
                if admitted:
                    slot.release()
                raise
            finally:
                self.waiters.remove(progress)
                try:
                    ticket.unlink(missing_ok=True)
                except OSError:
                    pass  # A journal cleanup failure cannot strand the execution slot.
                self.condition.notify_all()

    def cancel(self, progress):
        with self.condition:
            if read_status(progress)['phase'] != 'queued':
                return False
            update(progress, cancel_requested=True)
            self.condition.notify_all()
            return True


def recover_waiters(state):
    """A restarted Gateway cannot continue a lost Python call; expose recovery."""
    for ticket in (Path(state) / 'execution-queue').glob('*.json'):
        import json
        try:
            if ticket.is_symlink():
                continue
            progress = Path(json.loads(ticket.read_text())['progress'])
            workspace = progress.parents[2]
            if progress != job_path(workspace, ticket.stem):
                continue
            if read_status(progress)['phase'] == 'queued':
                update(progress, 'failed', 'Attesa interrotta dal riavvio del servizio; riprendi il progetto',
                       queue_position=0, resources_reclaimed=True, error_code='queue_restart',
                       action='Riprendi dalla chat: nessun container era stato avviato.')
        except (OSError, ValueError, KeyError, IndexError, TypeError):
            pass
        finally:
            try:
                ticket.unlink(missing_ok=True)
            except OSError:
                pass


QUEUE = ExecutionQueue()
