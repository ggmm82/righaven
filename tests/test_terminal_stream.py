import base64,struct,threading,unittest
from types import SimpleNamespace
from unittest.mock import patch
from righaven.environment_terminal import Session
from righaven.terminal_text import TerminalText


class TerminalStreamTests(unittest.TestCase):
    def session(self):
        value=Session.__new__(Session);value.id='test';value.profile='documenti';value.closed=False;value.error='';value.returncode=None;value.resources={}
        value.mutex=threading.Lock();value.condition=threading.Condition(value.mutex);value.cancelled=threading.Event()
        value.raw=bytearray();value.raw_start=value.raw_end=0;value.text='';value.decoder=TerminalText()
        return value

    def test_ansi_utf8_and_cursor_are_preserved_without_replaying_output(self):
        value=self.session();value.append_output(b'\x1b[31mCaf\xc3');first=value.public(0)
        value.append_output(b'\xa9\x1b[0m\r\n');second=value.public(first['cursor'])
        raw=base64.b64decode(first['output_base64'])+base64.b64decode(second['output_base64'])
        self.assertEqual(raw,b'\x1b[31mCaf\xc3\xa9\x1b[0m\r\n')
        self.assertEqual(value.public()['text'],'Café\r\n')
        self.assertEqual(value.public(second['cursor'])['output_base64'],'')

    def test_bounded_backlog_reports_truncation_and_streams_in_chunks(self):
        value=self.session();value.append_output(b'x'*300000)
        first=value.public(0)
        self.assertTrue(first['reset']);self.assertEqual(len(value.raw),262144)
        self.assertEqual(len(base64.b64decode(first['output_base64'])),65536)
        self.assertEqual(first['output_end'],300000)
        self.assertFalse(value.public(first['cursor'])['reset'])

    def test_output_wait_wakes_when_the_pty_writes(self):
        value=self.session();result=[];started=threading.Event()
        def read():started.set();result.append(value.public(0,1))
        thread=threading.Thread(target=read);thread.start();self.assertTrue(started.wait(1))
        value.append_output(b'prompt$ ');thread.join(.5)
        self.assertFalse(thread.is_alive());self.assertEqual(base64.b64decode(result[0]['output_base64']),b'prompt$ ')

    def test_resize_updates_the_actual_container_and_pty(self):
        value=self.session();value.fd=123;value.container='test-container';value.process=SimpleNamespace(pid=321)
        with patch('righaven.environment_terminal.fcntl.ioctl') as ioctl,patch('righaven.environment_terminal.os.kill') as signal:
            value.resize(120,40)
            self.assertEqual(struct.unpack('HHHH',ioctl.call_args.args[2]),(40,120,0,0))
            signal.assert_called_once_with(321,__import__('signal').SIGWINCH)
            with self.assertRaises(ValueError):value.resize(0,40)

    def test_finished_is_published_only_after_cleanup_and_slot_release(self):
        from righaven import docker_runtime
        from righaven.resource_slot import ResourceSlot
        import time
        value=self.session();value.fd=123;value.container='test-container';value.directory='/fixture'
        value.started=value.last_seen=time.monotonic();value.process=SimpleNamespace(poll=lambda:0,wait=lambda timeout:0)
        slot=ResourceSlot();self.assertTrue(slot.acquire());cleaning=threading.Event();resume=threading.Event()
        def cleanup(*args,**kwargs):cleaning.set();resume.wait(2)
        with patch.object(docker_runtime,'TERMINAL_LOCK',slot),patch.object(docker_runtime,'remove'),patch('righaven.environment_terminal.select.select',return_value=([],[],[])),patch('righaven.environment_terminal.os.close'),patch('righaven.environment_terminal.shutil.rmtree',side_effect=cleanup):
            thread=threading.Thread(target=value.read);thread.start()
            try:
                self.assertTrue(cleaning.wait(1));self.assertFalse(value.public()['finished']);self.assertTrue(slot.locked())
            finally:resume.set()
            thread.join(2);self.assertFalse(thread.is_alive())
        self.assertTrue(value.public()['finished']);self.assertFalse(slot.locked())

    def test_lost_browser_is_reclaimed_without_a_close_message(self):
        from righaven import docker_runtime
        from righaven.resource_slot import ResourceSlot
        import time
        value=self.session();value.fd=123;value.container='lost-browser';value.directory='/fixture'
        value.started=time.monotonic();value.last_seen=time.monotonic()-61
        value.process=SimpleNamespace(pid=321,poll=lambda:None,wait=lambda timeout:0)
        slot=ResourceSlot();self.assertTrue(slot.acquire())
        with patch.object(docker_runtime,'TERMINAL_LOCK',slot),patch.object(docker_runtime,'remove') as remove,patch('righaven.environment_terminal.os.close'),patch('righaven.environment_terminal.os.killpg'),patch('righaven.environment_terminal.shutil.rmtree'):
            value.read()
        remove.assert_called_once_with('lost-browser')
        self.assertTrue(value.closed);self.assertFalse(slot.locked())


if __name__=='__main__':unittest.main()
