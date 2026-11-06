"""Page ownership and closure before/after a terminal start response."""
import threading,time,unittest
from types import SimpleNamespace
from unittest.mock import patch
from righaven import environment_terminal as terminal


class TerminalLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.sessions=patch.dict(terminal.SESSIONS,{},clear=True);self.sessions.start();self.addCleanup(self.sessions.stop)
        self.clients=patch.dict(terminal.CLOSED_CLIENTS,{},clear=True);self.clients.start();self.addCleanup(self.clients.stop)

    def fake(self,user,name,profile,policy,client_id=None):
        session=SimpleNamespace(user=user,profile=name,client_id=client_id,id=client_id or 'legacy',closed=False,last_seen=time.monotonic(),cancelled=threading.Event())
        session.public=lambda:{'id':session.id,'finished':False,'closing':session.cancelled.is_set()}
        return session

    def test_closing_one_page_leaves_other_tabs_and_other_accounts_active(self):
        with patch.object(terminal,'Session',side_effect=self.fake):
            terminal.start('owner','docs',{}, {},client_id='a'*32)
            terminal.start('owner','docs',{}, {},client_id='b'*32)
            terminal.start('other','docs',{}, {},client_id='c'*32)
        terminal.close_client('owner','a'*32)
        self.assertTrue(terminal.SESSIONS['a'*32].cancelled.is_set())
        self.assertFalse(terminal.SESSIONS['b'*32].cancelled.is_set())
        self.assertFalse(terminal.SESSIONS['c'*32].cancelled.is_set())
        terminal.close_client('other','b'*32)
        self.assertFalse(terminal.SESSIONS['b'*32].cancelled.is_set())

    def test_a_page_closed_before_start_cannot_allocate_a_container(self):
        terminal.close_client('owner','a'*32)
        with patch.object(terminal,'Session') as create:
            with self.assertRaisesRegex(ValueError,'chiusa'):terminal.start('owner','docs',{}, {},client_id='a'*32)
            create.assert_not_called()

    def test_closing_while_constructor_is_running_cancels_the_late_session(self):
        entered=threading.Event();release=threading.Event();result=[]
        def create(*args,**kwargs):entered.set();release.wait(2);return self.fake(*args,**kwargs)
        with patch.object(terminal,'Session',side_effect=create):
            a=threading.Thread(target=lambda:result.append(terminal.start('owner','docs',{}, {},client_id='a'*32)))
            a.start();self.assertTrue(entered.wait(1))
            b=threading.Thread(target=lambda:terminal.close_client('owner','a'*32));b.start()
            try:
                until=time.monotonic()+1
                while not terminal.client_closed('owner','a'*32) and time.monotonic()<until:time.sleep(.01)
                self.assertTrue(terminal.client_closed('owner','a'*32))
            finally:release.set()
            a.join(2);b.join(2)
        self.assertFalse(a.is_alive() or b.is_alive());self.assertTrue(result[0]['closing'])
        self.assertTrue(terminal.SESSIONS['a'*32].cancelled.is_set())
