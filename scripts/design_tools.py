"""Supervised native design models. Sources stay editable; exports stay separate."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

try:from design_models import APPS, EXTENSIONS, preflight
except ImportError:from righaven.design_models import APPS, EXTENSIONS, preflight


def version(app,cli):
    root=cli.INSTALL/'apps'/app
    if app=='d2':command=[str(root/'bin/d2'),'--version']
    elif app=='plantuml':command=['java','-Djava.awt.headless=true','-jar',str(root/'plantuml.jar'),'-version']
    elif app=='structurizr':
        # Actual pinned library metadata, not a claim about the retired CLI.
        import zipfile
        with zipfile.ZipFile(next((root/'jars').glob('structurizr-dsl-*.jar'))) as archive:
            data=archive.read('META-INF/maven/com.structurizr/structurizr-dsl/pom.properties').decode()
        print('Structurizr DSL '+next(line.split('=',1)[1] for line in data.splitlines() if line.startswith('version=')));return
    else:
        package={'mermaid':'@mermaid-js/mermaid-cli','excalidraw':'@excalidraw/excalidraw','bpmn':'bpmn-to-image'}[app]
        print(app+' '+json.loads((root/'node_modules'/package/'package.json').read_text())['version']);return
    result=subprocess.run(command,capture_output=True,text=True,check=True,timeout=90);print(result.stdout+result.stderr)


def invoke(app,action,args,cli):
    source=cli.scoped(args['input']);output=cli.scoped(args['output'],exists=False,directory=True,fresh=True)
    if source.suffix.lower()!=EXTENSIONS[app]:raise ValueError('Expected editable '+EXTENSIONS[app]+' source')
    preflight(app,source)
    root=cli.scoped(os.environ.get('RIGHAVEN_OUTPUT_DIR',str(output.parent)),exists=False,directory=True)
    root.mkdir(parents=True,exist_ok=True);output.mkdir(parents=True)
    inputs=output/'Sources';inputs.mkdir();captured=inputs/source.name;shutil.copy2(source,captured)
    original=cli.digest(source);native=cli.INSTALL/'apps'/app
    if app=='d2':
        cli.run(app,[native/'bin/d2','validate',captured],root)
        cli.run(app,[native/'bin/d2','--layout='+args.get('layout','elk'),'--bundle=true',captured,output/'diagram.svg'],root)
    elif app=='plantuml':
        # stdin avoids modifying the original or placing exports beside uploads.
        job=output/'plantuml-job.json';job.write_text(json.dumps({'source':str(captured),'target':str(output/'diagram.svg'),'jar':str(native/'plantuml.jar')}))
        cli.run(app,['python3',cli.HERE/'design_plantuml.py',job],root)
        job.unlink()
    elif app=='structurizr':
        java=native/'jdk/bin/java'
        cli.run(app,[java,'-Xmx384m','-cp',str(native/'jars/*')+os.pathsep+str(native/'classes'),'StructurizrJob',action,captured,output,args.get('format','mermaid')],root)
    else:
        cli.run(app,['node',cli.HERE/'design_browser.cjs',app,native,native/'web',captured,output],root)
    if (output/'diagram.svg').exists():
        svg=ET.parse(output/'diagram.svg').getroot()
        if not svg.tag.endswith('svg') or len(list(svg.iter()))<3:raise ValueError('Empty native SVG export')
        if not (output/'inspection.json').exists():(output/'inspection.json').write_text(json.dumps({'status':'passed','engine':app,'svg_elements':len(list(svg.iter())),'review':'Native syntax and rendering, not design quality'}))
    info=json.loads((output/'inspection.json').read_text())
    if cli.digest(source)!=original:raise RuntimeError('Original source was modified')
    recipe={'tool':app,'operation':action,'input_sha256':original,'source':captured.relative_to(output).as_posix(),'arguments':{k:v for k,v in args.items() if k not in ('input','output')},'inspection':info}
    (output/'design-recipe.json').write_text(json.dumps(recipe,ensure_ascii=False,indent=2))
    return {'output':str(output),'status':info['status'],'inspection':info,'original_preserved':True,'source':str(captured)}
