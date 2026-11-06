"""Repeat native CLI checks on valid EPUB, broken links and invalid CSS."""
import hashlib,json,os,subprocess,sys,zipfile,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from acceptance import Case,calibre


root=Path('/mnt/user-data/outputs/calibre-headless-stress');root.mkdir(parents=True,exist_ok=True)
case=Case(root,'calibre');calibre(case)
valid=case.root/'interactive.epub';broken=case.root/'interactive-broken.epub';badcss=case.root/'invalid-css.epub'
with zipfile.ZipFile(valid) as source,zipfile.ZipFile(badcss,'w') as target:
    changed=False
    for info in source.infolist():
        data=source.read(info.filename)
        if info.filename.endswith('.css') and not changed:data=b'p { color: #gggggg; }';changed=True
        target.writestr(info,data)
    assert changed
before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (valid,broken,badcss)}
# The installed adapter itself is a symlink. Exercise that path with no
# xvfb-run available, proving structural checks do not launch a display.
bin_dir=case.root/'headless-bin';bin_dir.mkdir()
for name in ('calibre-cli','calibre-debug','python3','node'):
    binary=shutil.which(name);assert binary,name
    (bin_dir/name).symlink_to(binary)
env={**os.environ,'RIGHAVEN_OUTPUT_DIR':str(case.root),'PATH':str(bin_dir)}
counts={'valid':0,'broken_link':0,'invalid_css':0}
for index in range(60):
    book=(valid,broken,badcss)[index%3]
    result=subprocess.run(['calibre-cli','check',str(book)],capture_output=True,text=True,env=env,timeout=60)
    assert result.returncode==(0 if index%3==0 else 2),(index,result.returncode,result.stderr[-1500:])
    value=json.loads(result.stdout)
    assert value['css_engine']=='calibre-bundled-stylelint-node'
    expected='passed' if index%3==0 else 'failed'
    assert value['status']==expected
    if index%3==1:assert any(i['rule']=='DanglingLink' and i['blocking'] for i in value['issues'])
    if index%3==2:assert any(i['rule']=='css:color-no-invalid-hex' and i['blocking'] for i in value['issues'])
    assert 'GLX:' not in result.stderr and 'Sandboxing disabled' not in result.stderr
    counts[('valid','broken_link','invalid_css')[index%3]]+=1
    if (index+1)%15==0:print('Calibre headless checks completed:',index+1,flush=True)
assert all(hashlib.sha256(p.read_bytes()).hexdigest()==digest for p,digest in before.items())
(root/'report.json').write_text(json.dumps({'passed':True,'counts':counts,'inputs_preserved':True,'engine':'Calibre bundled stylelint via Node'},indent=2))
print('Calibre headless OK:',counts,'; real CLI failures preserved, inputs unchanged, no WebEngine or display for structural checks.')
