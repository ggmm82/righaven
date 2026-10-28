"""Local OpenAI protocol fixture, only for the isolated Compose lifecycle test.

This is not a security reviewer. It allows exactly the declared harmless fixture,
and blocks every other request. No provider credentials or external model calls.
"""
import json,os
from http.server import BaseHTTPRequestHandler,HTTPServer


class Handler(BaseHTTPRequestHandler):
    allowed=0
    def log_message(self,*args):pass
    def send(self,value):
        body=json.dumps(value).encode();self.send_response(200)
        self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)))
        self.end_headers();self.wfile.write(body)
    def do_GET(self):self.send({'allowed_fixture_requests':Handler.allowed})
    def do_POST(self):
        data=json.loads(self.rfile.read(min(int(self.headers.get('Content-Length',0)),30000)))
        messages=data.get('messages',[])
        expected='Review this content:\n-----\n'+os.environ['CI_EXPECTED_SKILL']+'\n-----'
        allowed=(self.path=='/v1/chat/completions' and data.get('model')=='ci-skill-moderation'
                 and len(messages)==2 and messages[0].get('role')=='system'
                 and 'security reviewer for AI agent skills' in messages[0].get('content','')
                 and messages[1].get('role')=='user' and messages[1].get('content','').endswith(expected))
        if allowed:Handler.allowed+=1
        result={'decision':'allow' if allowed else 'block','reason':'Declared harmless CI fixture' if allowed else 'Unknown content is outside this fixture'}
        self.send({'id':'ci-moderation','object':'chat.completion','created':0,'model':'ci-skill-moderation',
                   'choices':[{'index':0,'message':{'role':'assistant','content':json.dumps(result)},'finish_reason':'stop'}]})


if __name__=='__main__':HTTPServer(('0.0.0.0',8765),Handler).serve_forever()
