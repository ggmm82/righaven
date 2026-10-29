"""Offline native fixtures for every optional data, verification and engineering CLI."""
import contextlib,csv,hashlib,http.server,json,math,os,shutil,subprocess,threading
from pathlib import Path
try:from .acceptance_toolkit import call
except ImportError:from acceptance_toolkit import call


def operation(c,name,**args):
    """Validators legitimately return failed for a deliberately invalid fixture."""
    p=subprocess.run([c.app+'-cli','call',name,json.dumps(args)],capture_output=True,text=True,timeout=300)
    c.commands.append({'argv':[c.app+'-cli','call',name,args],'returncode':p.returncode,'stdout':p.stdout[-4000:],'stderr':p.stderr[-2000:]})
    if p.returncode not in (0,2):raise RuntimeError(p.stderr or p.stdout)
    return json.loads(p.stdout)


def pdf(path):
    # Exact small PDF with xref offsets; intentionally not PDF/A.
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
      b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
      b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    text=b'BT /F1 20 Tf 30 100 Td (RigHaven 60) Tj ET';objects.append(b'<< /Length '+str(len(text)).encode()+b' >>\nstream\n'+text+b'\nendstream')
    data=b'%PDF-1.4\n';offsets=[]
    for i,obj in enumerate(objects,1):offsets.append(len(data));data+=str(i).encode()+b' 0 obj\n'+obj+b'\nendobj\n'
    xref=len(data);data+=b'xref\n0 6\n0000000000 65535 f \n'+b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets)
    data+=b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n'+str(xref).encode()+b'\n%%EOF\n';path.write_bytes(data)


def duckdb(c):
    source=c.root/'analysis.sql';source.write_text('CREATE TABLE amounts AS SELECT * FROM (VALUES (10),(20),(30)) t(amount); SELECT SUM(amount) AS total FROM amounts;')
    output=c.root/'Run';call(c,'query',input=str(source),output=str(output))
    c.check('Native SQL returns actual aggregate', '60' in (output/'results.csv').read_text() and (output/'analysis.duckdb').is_file(),(output/'results.csv').read_text())
    relocated=c.root/'relocated.sql';shutil.copy2(output/'Sources/analysis.sql',relocated)
    rebuilt=c.root/'Rebuilt';call(c,'query',input=str(relocated),output=str(rebuilt))
    c.check('SQL reruns independently after relocation',(output/'results.csv').read_text()==(rebuilt/'results.csv').read_text(),'same aggregate')


def jupyter(c):
    source=c.root/'analysis.ipynb';source.write_text(json.dumps({'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'name':'python3','display_name':'Python 3','language':'python'}},'cells':[{'id':'sum','cell_type':'code','metadata':{},'execution_count':None,'outputs':[],'source':['print(sum([10,20,30]))']}]}))
    out=c.root/'Run';call(c,'execute',input=str(source),output=str(out))
    nb=json.loads((out/'executed.ipynb').read_text());c.check('Fresh kernel executes saved notebook','60' in str(nb['cells'][0]['outputs']),nb['cells'][0]['outputs'])


def quarto(c):
    source=c.root/'report.qmd';source.write_text('---\ntitle: Reproducible report\nformat: html\n---\n\n# Result\n\nRigHaven total: **60**.\n')
    out=c.root/'Run';call(c,'render',input=str(source),output=str(out))
    c.check('Native standalone HTML preserves content','RigHaven total' in (out/'Sources/report.html').read_text() and '60' in (out/'Sources/report.html').read_text(),'rendered HTML')


def poppler(c):
    source=c.root/'input.pdf';pdf(source);out=c.root/'Pages';call(c,'render',input=str(source),output=str(out),dpi=72)
    images=list(out.glob('page-*.png'));c.check('Actual PDF rasterized',len(images)==1 and images[0].read_bytes().startswith(b'\x89PNG'),'one native rendered page')
    text=c.root/'Text';call(c,'text',input=str(source),output=str(text));c.check('Text extracted from actual PDF','RigHaven 60' in (text/'text.txt').read_text(),'exact marker')


def qpdf(c):
    source=c.root/'input.pdf';pdf(source);result=call(c,'check',input=str(source),output=str(c.root/'Check'))
    c.check('Valid PDF passes actual structural check',result['status']=='passed',result)
    source=c.root/'broken.pdf';source.write_text('not a PDF');bad=operation(c,'check',input=str(source),output=str(c.root/'Broken'))
    c.check('Malformed PDF does not become a pass',bad['status']=='failed',bad)


def verapdf(c):
    source=c.root/'ordinary.pdf';pdf(source);out=c.root/'Validation';result=operation(c,'validate',input=str(source),output=str(out),flavour='2b')
    c.check('Nonconforming ordinary PDF is rejected by actual validator',result['status']=='failed' and 'validationReport' in (out/'report.xml').read_text(),result)


def text_image(path):
    from PIL import Image,ImageDraw,ImageFont
    image=Image.new('RGB',(1000,220),'white');font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',58)
    ImageDraw.Draw(image).text((35,70),'RIGHAVEN TOTAL 60',fill='black',font=font);image.save(path);return image


def tesseract(c):
    source=c.root/'scan.png';text_image(source);out=c.root/'OCR';call(c,'recognize',input=str(source),output=str(out),language='eng')
    text=(out/'recognized.txt').read_text();c.check('Real OCR recognizes known pixels','TOTAL 60' in text and (out/'recognized.tsv').is_file(),text)


def ocrmypdf(c):
    source=c.root/'scan.pdf';text_image(c.root/'scan.png').save(source,'PDF',resolution=150)
    out=c.root/'OCR';call(c,'ocr',input=str(source),output=str(out),language='eng')
    c.check('Actual scan produces OCR layer and text','TOTAL 60' in (out/'text.txt').read_text() and (out/'searchable.pdf').read_bytes().startswith(b'%PDF'),(out/'text.txt').read_text())


def gdal(c):
    source=c.root/'pixels.pgm';source.write_bytes(b'P5\n2 2\n255\n'+bytes([10,20,30,40]))
    out=c.root/'Inspect';call(c,'inspect',input=str(source),output=str(out))
    info=json.loads((out/'metadata.json').read_text());c.check('Native raster dimensions are measured',info['size']==[2,2],info)
    converted=c.root/'Converted';call(c,'translate',input=str(source),output=str(converted))
    check=c.root/'Reopened';call(c,'inspect',input=str(converted/'raster.tif'),output=str(check))
    c.check('GeoTIFF reopens with actual expected dimensions',json.loads((check/'metadata.json').read_text())['size']==[2,2],'roundtrip raster')


def qgis(c):
    resources=c.root/'resources';resources.mkdir();(resources/'point.geojson').write_text(json.dumps({'type':'FeatureCollection','features':[{'type':'Feature','properties':{},'geometry':{'type':'Point','coordinates':[0,0]}}]}))
    source=resources/'parameters.json';source.write_text(json.dumps({'INPUT':'point.geojson','DISTANCE':1,'SEGMENTS':8,'END_CAP_STYLE':0,'JOIN_STYLE':0,'MITER_LIMIT':2,'DISSOLVE':False,'OUTPUT':'buffer.geojson'}))
    out=c.root/'Analysis';call(c,'process',input=str(source),output=str(out),resource_dir=str(resources),algorithm='native:buffer')
    data=json.loads((out/'buffer.geojson').read_text());c.check('Native GIS processing creates polygon from point',data['features'][0]['geometry']['type'] in ('Polygon','MultiPolygon'),data)


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/status'):
            data=b'{"ok":true}';kind='application/json'
        else:
            data=b'<!doctype html><html lang="en"><head><title>Local fixture</title></head><body><main><h1>Fixture</h1><button></button></main></body></html>';kind='text/html'
        self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def log_message(self,*args):pass


@contextlib.contextmanager
def server():
    server_instance=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server_instance.serve_forever,daemon=True);thread.start()
    try:yield 'http://127.0.0.1:'+str(server_instance.server_port)
    finally:server_instance.shutdown();server_instance.server_close();thread.join()


def schemathesis(c):
    source=c.root/'openapi.json';source.write_text(json.dumps({'openapi':'3.0.3','info':{'title':'Fixture','version':'1.0'},'paths':{'/status':{'get':{'responses':{'200':{'description':'OK','content':{'application/json':{'schema':{'type':'object','required':['ok'],'properties':{'ok':{'type':'boolean'}}}}}}}}}}}))
    with server() as target:
        out=c.root/'Test';call(c,'test',input=str(source),output=str(out),target_url=target,authorized=True,max_examples=2)
    c.check('Real API schema requests have a JUnit result','testsuite' in (out/'junit.xml').read_text(),'local HTTP target exercised')


def k6(c):
    with server() as target:
        source=c.root/'scenario.js';source.write_text("import http from 'k6/http'; import {check} from 'k6'; export default function(){const r=http.get("+json.dumps(target+'/status')+");check(r,{'status':r=>r.status===200});}")
        out=c.root/'Load';call(c,'run',input=str(source),output=str(out),authorized=True,iterations=2,virtual_users=1)
    report=json.loads((out/'summary.json').read_text());c.check('Actual bounded requests measured',report['metrics']['http_reqs']['count']==2,report['metrics']['http_reqs'])


def axe_core(c):
    with server() as target:
        out=c.root/'Audit';result=operation(c,'audit',url=target,output=str(out),authorized=True)
    report=json.loads((out/'report.json').read_text());c.check('Real Chromium detects unnamed button',any(v['id']=='button-name' for v in report['violations']) and result['status']=='failed',result)


def zap(c):
    with server() as target:
        out=c.root/'Passive';call(c,'baseline',url=target,output=str(out),authorized=True)
    plan=json.loads((out/'passive-plan.yaml').read_text());c.check('Actual passive scan yields XML without active attack job',(out/'report.xml').is_file() and all(j['type']!='activeScan' for j in plan['jobs']),[j['type'] for j in plan['jobs']])


def gitleaks(c):
    source=c.root/'repository';source.mkdir();token='ghp_'+hashlib.sha256(b'public deterministic fake scanner fixture').hexdigest()[:36]
    (source/'example.env').write_text('GITHUB_TOKEN='+token+'\n');out=c.root/'Scan';result=operation(c,'scan',input=str(source),output=str(out))
    report=(out/'report.json').read_text();c.check('Real scanner detects a fixture and redacts it',result['findings']>=1 and token not in report and token not in (out/'native.stdout').read_text() and token not in (out/'native.stderr').read_text(),result)


def openmodelica(c):
    resources=c.root/'models';resources.mkdir();(resources/'Decay.mo').write_text('model Decay\n Real x(start=1,fixed=true);\nequation\n der(x)=-x;\nend Decay;\n')
    source=resources/'run.mos';source.write_text('loadFile("Decay.mo");\nsimulate(Decay,stopTime=1.0,numberOfIntervals=10,outputFormat="csv");\ngetErrorString();\n')
    out=c.root/'Simulation';call(c,'simulate',input=str(source),resource_dir=str(resources),output=str(out))
    rows=list(csv.DictReader((out/'Sources/Decay_res.csv').open()));value=float(rows[-1]['x'])
    c.check('Native compiled simulation matches exp(-1)',abs(value-math.exp(-1))<.01,value)


def highs(c):
    source=c.root/'model.lp';source.write_text('Minimize\n cost: x + y\nSubject To\n first: x >= 1\n second: y >= 2\nBounds\n x >= 0\n y >= 0\nEnd\n')
    out=c.root/'Solve';call(c,'solve',input=str(source),output=str(out));text=(out/'solution.txt').read_text()
    c.check('Native solver proves the known optimum','Optimal' in text and ('Objective 3' in text or 'Objective value: 3' in text),text)


def kicad(c):
    source=c.root/'board.kicad_pcb';source.write_text('''(kicad_pcb (version 20240108) (generator "pcbnew")
 (general (thickness 1.6)) (paper "A4")
 (layers (0 "F.Cu" signal) (31 "B.Cu" signal) (44 "Edge.Cuts" user))
 (setup (pad_to_mask_clearance 0)) (net 0 "")
 (gr_rect (start 10 10) (end 40 30) (stroke (width 0.05) (type default)) (fill none) (layer "Edge.Cuts"))
)''')
    out=c.root/'Export';call(c,'export',input=str(source),output=str(out),kind='pcb')
    paths=list((out/'SVG').glob('*.svg'));c.check('Native KiCad board exports actual SVG',bool(paths) and '<svg' in paths[0].read_text(),'native board and SVG preserved')


def ngspice(c):
    source=c.root/'divider.cir';source.write_text('Voltage divider\nV1 in 0 DC 10\nR1 in out 1k\nR2 out 0 1k\n.op\n.end\n')
    out=c.root/'Simulation';call(c,'simulate',input=str(source),output=str(out))
    import struct,re
    raw=(out/'simulation.raw').read_bytes();header,separator,data=raw.partition(b'Binary:\n')
    text=header.decode();variables=int(re.search(r'No. Variables:\s*(\d+)',text)[1])
    names=[line.split()[1] for line in text.split('\nVariables:\n',1)[1].splitlines() if line.strip()]
    values=struct.unpack('<'+'d'*variables,data[:8*variables])
    measured=dict(zip(names,values))
    c.check('Native voltage divider actually measures five volts',bool(separator) and abs(measured['v(out)']-5)<1e-6,measured)


def prusaslicer(c):
    source=c.root/'cube.stl'
    vertices=[(0,0,0),(10,0,0),(10,10,0),(0,10,0),(0,0,10),(10,0,10),(10,10,10),(0,10,10)]
    faces=[(0,2,1),(0,3,2),(4,5,6),(4,6,7),(0,1,5),(0,5,4),(1,2,6),(1,6,5),(2,3,7),(2,7,6),(3,0,4),(3,4,7)]
    text='solid cube\n'
    for face in faces:
        text+='facet normal 0 0 0\nouter loop\n'+''.join('vertex '+' '.join(map(str,vertices[i]))+'\n' for i in face)+'endloop\nendfacet\n'
    source.write_text(text+'endsolid cube\n');config=c.root/'printer.ini';config.write_text('layer_height = 0.2\nnozzle_diameter = 0.4\nfilament_diameter = 1.75\nperimeters = 2\nfill_density = 15%\nbed_shape = 0x0,200x0,200x200,0x200\n')
    out=c.root/'Slice';call(c,'slice',input=str(source),output=str(out),config=str(config))
    text=(out/'print.gcode').read_text();c.check('Native slicer produces extrusion paths and preserves printer settings','G1 ' in text and ' E' in text and (out/'Sources/printer.ini').is_file(),'actual G-code; no physical print claimed')

CASES={name:globals()[name.replace('-','_')] for name in ('duckdb','jupyter','quarto','poppler','qpdf','verapdf','ocrmypdf','tesseract','gdal','qgis','schemathesis','k6','axe-core','zap','gitleaks','openmodelica','highs','kicad','ngspice','prusaslicer')}
