#!/usr/bin/env python3
"""Fault-inject one renderer crash, then verify a real native PDF and intact source."""
import hashlib,json,os,shutil,subprocess,tempfile
from pathlib import Path


def main():
    base=Path('/mnt/user-data/outputs');base.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='calibre-render-recovery-',dir=base) as temporary:
        root=Path(temporary);source=root/'source.xhtml';book=root/'source.epub';pdf=root/'recovered.pdf'
        source.write_text('<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Native recovery</title></head><body><h1>CALIBRE-NATIVE-RECOVERY</h1><p>Testo reale dopo il recupero.</p></body></html>')
        env={**os.environ,'RIGHAVEN_OUTPUT_DIR':str(root)}
        subprocess.run(['calibre-cli','convert',str(source),str(book),'--title','Native recovery'],env=env,check=True,capture_output=True,text=True,timeout=120)
        original=hashlib.sha256(book.read_bytes()).hexdigest();binary=str(Path(shutil.which('ebook-convert')).resolve())
        launch=root/'bin';launch.mkdir();marker=root/'injected-crash'
        wrapper=launch/'ebook-convert'
        wrapper.write_text('#!/usr/bin/python3\nimport os,signal,sys\nfrom pathlib import Path\nmarker=Path('+repr(str(marker))+')\nif not marker.exists():\n marker.write_text("one controlled crash")\n Path(sys.argv[2]).write_bytes(b"partial output")\n os.kill(os.getpid(),signal.SIGSEGV)\nos.execv('+repr(binary)+',["ebook-convert",*sys.argv[1:]])\n');wrapper.chmod(0o755)
        env['PATH']=str(launch)+os.pathsep+env['PATH']
        result=subprocess.run(['calibre-cli','convert',str(book),str(pdf)],env=env,check=True,capture_output=True,text=True,timeout=120)
        report=json.loads(result.stdout)
        assert 'Rendering recuperato con backend software' in report['log'],report
        assert pdf.read_bytes().startswith(b'%PDF-') and pdf.stat().st_size>1000
        text=subprocess.check_output(['pdfcraft-cli','text',str(pdf)],text=True,timeout=60)
        assert 'CALIBRE-NATIVE-RECOVERY' in text,text
        assert hashlib.sha256(book.read_bytes()).hexdigest()==original
        statuses=[json.loads(p.read_text()) for p in root.glob('work/operations/*/status.json')]
        assert {139,0}<={s['returncode'] for s in statuses},statuses
        assert sum(s['returncode']==139 for s in statuses)==1,statuses
        print('Calibre renderer recovery OK: one real SIGSEGV, partial export discarded, native PDF text verified, EPUB unchanged and both attempt records preserved.')


if __name__=='__main__':main()
