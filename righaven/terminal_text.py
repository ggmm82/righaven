"""Incremental UTF-8/ANSI decoding for CLI login output (including OSC hyperlinks)."""
import codecs
import re
from urllib.parse import parse_qs, urlsplit


class TerminalText:
    def __init__(self):
        self.decoder = codecs.getincrementaldecoder('utf-8')('replace')
        self.state = 'text'
        self.osc = ''

    def hyperlink(self,result):
        if self.osc.startswith('8;;https://'):
            url=self.osc[3:];parsed=urlsplit(url)
            if parsed.netloc in ('claude.ai','console.anthropic.com','platform.claude.com') and parsed.path.startswith('/oauth'):
                result.append(' '+url+' ')
        self.osc=''

    def feed(self, data):
        result = []
        for char in self.decoder.decode(data):
            if self.state == 'text':
                if char == '\x1b':
                    self.state = 'escape'
                elif char in '\r\n\t' or ord(char) >= 32:
                    result.append(char)
            elif self.state == 'escape':
                self.state = {'[': 'csi', ']': 'osc', '(': 'charset', ')': 'charset'}.get(char, 'text')
                if self.state=='osc':self.osc=''
            elif self.state == 'csi':
                if '@' <= char <= '~':
                    self.state = 'text'
            elif self.state == 'osc':
                if char == '\x07':
                    self.hyperlink(result);self.state = 'text'
                elif char == '\x1b':
                    self.state = 'osc_escape'
                elif len(self.osc)<12000:self.osc+=char
            elif self.state == 'osc_escape':
                if char=='\\':self.hyperlink(result);self.state='text'
                else:self.state='osc'
            elif self.state == 'charset':
                self.state = 'text'
        return ''.join(result)


def authorization_url(text, engine):
    matches = re.finditer(r'https://[^\s\x00-\x20<>"\x7f-\uffff]+', text)
    valid = []
    for match in matches:
        url = match.group(0)
        parsed = urlsplit(url)
        if engine == 'codex' and parsed.netloc == 'auth.openai.com':
            valid.append(url)
        if engine == 'claude' and parsed.netloc in ('claude.ai','console.anthropic.com','platform.claude.com') and parsed.path.startswith('/oauth'):
            valid.append(url)
        if engine == 'gemini' and parsed.netloc == 'accounts.google.com' and match.end() < len(text):
            query = parse_qs(parsed.query)
            if (query.get('response_type') == ['code'] and
                    all(key in query for key in ('client_id', 'code_challenge', 'redirect_uri', 'scope', 'state'))):
                valid.append(url)
    return valid[-1] if valid else None
