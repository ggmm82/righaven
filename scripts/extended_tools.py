"""Native optional workflows with private output folders and preserved recipes."""
import json,os,re,shutil,subprocess,sys
from pathlib import Path
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
try:from .extended_specs import TOOLS
except ImportError:from extended_specs import TOOLS

APPS=set(TOOLS)


def domain():
    try:from . import domain_tools
    except ImportError:import domain_tools
    return domain_tools


def pipeline():
    try:from . import pipeline_tools
    except ImportError:import pipeline_tools
    return pipeline_tools


def binary(app,cli):
    if app in domain().APPS:return domain().binary(app,cli)
    if app in pipeline().APPS:return pipeline().binary(app,cli)
    if app in ('dlt','sqlmesh'):return str(cli.INSTALL/'apps'/app/'venv/bin'/app)
    if app=='schemacrawler':
        matches=list((cli.INSTALL/'apps/schemacrawler').rglob('schemacrawler.sh'))
        if len(matches)!=1:raise RuntimeError('SchemaCrawler executable missing')
        return str(matches[0])
    if app=='schemathesis':return str(cli.INSTALL/'apps/schemathesis/venv/bin/schemathesis')
    if app=='verapdf':return str(cli.INSTALL/'apps/verapdf/runtime/verapdf')
    if app=='zap':
        paths=list((cli.INSTALL/'apps/zap').rglob('zap.sh'))
        if len(paths)!=1:raise ValueError('Expected one ZAP installation')
        return str(paths[0])
    return {'jupyter':'jupyter-nbconvert','poppler':'pdftoppm','tesseract':'tesseract',
        'gdal':'gdalinfo','qgis':'/usr/bin/qgis_process.bin' if Path('/usr/bin/qgis_process.bin').exists() else '/usr/bin/qgis_process','openmodelica':'omc','kicad':'/usr/bin/kicad-cli','prusaslicer':'prusa-slicer'}.get(app,app)


def version(app,cli):
    native=binary(app,cli)
    if app=='sqlglot':
        native=str(cli.INSTALL/'apps/sqlglot/venv/bin/python');flags=['-c','import sqlglot; print(sqlglot.__version__)']
    elif app=='axe-core':
        library=cli.INSTALL/'apps/axe-core/node_modules/@axe-core/playwright'
        native='node'
        flags=['-e','require('+json.dumps(str(library))+'); console.log(require('+json.dumps(str(library/'package.json'))+').version)']
    else:flags=None
    if app in domain().APPS:flags=domain().version_flags(app)
    if app in pipeline().APPS:flags=pipeline().version_flags(app)
    flags=flags or {'prusaslicer':['--help'],'poppler':['-v'],'tesseract':['--version'],'zap':['-cmd','-version'],'ngspice':['--version']}.get(app,['--version'])
    result=subprocess.run([native,*flags],capture_output=True,text=True,errors='replace',timeout=120,
        env={**os.environ,'QT_QPA_PLATFORM':'offscreen','QGIS_NO_OVERRIDE_IMPORT':'1'})
    if result.returncode:raise RuntimeError((result.stdout+result.stderr)[-2000:])
    record=next(row for row in json.loads((cli.INSTALL/'installed.json').read_text()) if row['id']==app)
    print('Verified installed distribution: '+record['version']+'\n'+result.stdout+result.stderr)


def url(value):
    parsed=urlsplit(value)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError('Use an explicit HTTP(S) target without embedded credentials or fragment')
    return value


def retain(source,output,resource,cli):
    target=output/'Sources'
    if resource:
        base=cli.scoped(resource,directory=True)
        if not source.is_relative_to(base) or output.is_relative_to(base):raise ValueError('Resources must contain input and exclude output')
        if any(p.is_symlink() for p in base.rglob('*')):raise ValueError('Source resources must not contain symlinks')
        shutil.copytree(base,target);return target/source.relative_to(base)
    target.mkdir();shutil.copy2(source,target/source.name);return target/source.name


def invoke(app,action,args,cli):
    if app in domain().APPS:return domain().invoke(app,action,args,cli)
    if pipeline().handles(app,action):return pipeline().invoke(app,action,args,cli)
    if app in ('usql','schemacrawler','dlt','sqlmesh','sqlglot'):
        try:from .data_tools import invoke as data_invoke
        except ImportError:from data_tools import invoke as data_invoke
        return data_invoke(app,action,args,cli)
    # Schemas validated by toolkit_cli before reaching the native dispatcher.
    if app in ('schemathesis','k6','axe-core','zap') and args.get('authorized') is not True:
        raise ValueError('Explicit target authorization is required')
    target=url(args['target_url']) if 'target_url' in args else url(args['url']) if 'url' in args else None
    source=cli.scoped(args['input'],directory=app=='gitleaks') if 'input' in args else None
    output=cli.scoped(args['output'],exists=False,directory=True,fresh=True)
    if source and source.is_dir() and output.is_relative_to(source):raise ValueError('Output must be outside inspected input')
    config=cli.scoped(args['config']) if 'config' in args else None
    allowed={
      'duckdb':{'.sql'},'jupyter':{'.ipynb'},'quarto':{'.qmd'},'poppler':{'.pdf'},'qpdf':{'.pdf'},'verapdf':{'.pdf'},'ocrmypdf':{'.pdf'},
      'qgis':{'.json'},'schemathesis':{'.json','.yaml','.yml'},'k6':{'.js'},'openmodelica':{'.mos'},'highs':{'.lp','.mps'},
      'kicad':{'.kicad_pcb','.kicad_sch'},'ngspice':{'.cir','.sp','.net'},'prusaslicer':{'.stl','.obj','.3mf'},
    }
    if source and app in allowed and source.suffix.lower() not in allowed[app]:raise ValueError('Unsupported native input format for '+app)
    original=cli.digest(source) if source and source.is_file() else None
    output.mkdir(parents=True)
    actual=retain(source,output,args.get('resource_dir'),cli) if source and source.is_file() else source
    native=binary(app,cli);argv=[];cwd=actual.parent if actual and actual.is_file() else output
    env={'QT_QPA_PLATFORM':'offscreen','OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','XDG_CONFIG_HOME':str(output/'private-home')}
    (output/'private-home').mkdir()
    result={'output':str(output),'original_preserved':True,'status':'passed'}
    expected=[]
    if app=='duckdb':
        database=output/'analysis.duckdb'
        if 'database' in args:shutil.copy2(cli.scoped(args['database']),database)
        recipe=output/'run.sql';recipe.write_text('.read '+json.dumps(str(actual))+'\n')
        argv=[native,str(database),'-csv','-init','/dev/null','-f',str(recipe)];expected=[database]
    elif app=='jupyter':
        if source.stat().st_size>16*1024**2:raise ValueError('Notebook too large')
        document=json.loads(source.read_text())
        if document.get('nbformat')!=4:raise ValueError('Use a version 4 notebook')
        argv=[native,'--to','notebook','--execute','--ExecutePreprocessor.timeout='+str(args.get('timeout_seconds',120)),
          '--output','executed.ipynb','--output-dir',str(output),str(actual)];expected=[output/'executed.ipynb']
    elif app=='quarto':
        # Never run inherited publishing hooks or project files outside the retained resources.
        argv=[native,'render',str(actual),'--to','html','--output','report.html'];expected=[actual.parent/'report.html']
    elif app=='poppler':
        if action=='text':argv=['pdftotext','-layout',str(actual),str(output/'text.txt')];expected=[output/'text.txt']
        else:
            first=args.get('first_page',1);last=args.get('last_page',first+19)
            if last<first or last-first>=100:raise ValueError('Render up to 100 pages per call')
            argv=[native,'-png','-r',str(args.get('dpi',120)),'-f',str(first),'-l',str(last),str(actual),str(output/'page')]
    elif app=='qpdf':argv=[native,'--check',str(actual)]
    elif app=='verapdf':argv=[native,'--format','xml','--flavour',args.get('flavour','2b'),str(actual)]
    elif app=='ocrmypdf':
        argv=[native,'--skip-text','--jobs','1','--language',args.get('language','eng'),
           '--output-type','pdf','--sidecar',str(output/'text.txt'),str(actual),str(output/'searchable.pdf')];expected=[output/'searchable.pdf']
    elif app=='tesseract':
        argv=[native,str(actual),str(output/'recognized'),'-l',args.get('language','eng'),'txt','tsv'];expected=[output/'recognized.txt',output/'recognized.tsv']
    elif app=='gdal':
        if action=='inspect':argv=[native,'-json',str(actual)]
        else:argv=['gdal_translate','-of','GTiff',str(actual),str(output/'raster.tif')];expected=[output/'raster.tif']
    elif app=='qgis':
        if not re.fullmatch(r'[a-z][a-z0-9_]*:[a-z0-9_]+',args['algorithm']):raise ValueError('Use a named QGIS provider algorithm')
        params=json.loads(actual.read_text())
        if not isinstance(params,dict):raise ValueError('QGIS parameters must be an object')
        converted={}
        for key,value in params.items():
            if not re.fullmatch(r'[A-Z][A-Z0-9_]*',key):raise ValueError('Invalid Processing parameter name')
            if isinstance(value,str) and (Path(value).is_absolute() or '..' in Path(value).parts or '://' in value):
                raise ValueError('Use relative local Processing resources within the retained source folder')
            if isinstance(value,str) and key in ('OUTPUT','DESTINATION'):
                path=Path(value)
                if path.is_absolute() or '..' in path.parts:raise ValueError('Use relative QGIS outputs')
                out=output/path;out.parent.mkdir(parents=True,exist_ok=True);converted[key]=str(out);expected.append(out)
            elif isinstance(value,str) and (actual.parent/value).is_file():converted[key]=str((actual.parent/value).resolve())
            else:converted[key]=value
        if not expected:raise ValueError('Declare a local OUTPUT or DESTINATION')
        argv=[native,'--json','run',args['algorithm'],'--',*[k+'='+str(v) for k,v in converted.items()]]
    elif app=='schemathesis':
        argv=[native,'run',str(actual),'--url',target,'--max-examples',str(args.get('max_examples',3)),
          '--workers','1','--phases','fuzzing','--report','junit','--report-junit-path',str(output/'junit.xml')];expected=[output/'junit.xml']
    elif app=='k6':
        runner=output/'bounded-scenario.js'
        options={'scenarios':{'bounded':{'executor':'shared-iterations','vus':args.get('virtual_users',1),
                  'iterations':args.get('iterations',1),'maxDuration':'60s'}},'setupTimeout':'30s','teardownTimeout':'30s'}
        runner.write_text('import * as scenario from '+json.dumps(str(actual))+';\nexport const options='+json.dumps(options)+';\n'
          'export default function(data){return scenario.default(data); }\n'
          'export function setup(){if(scenario.setup)return scenario.setup();}\n'
          'export function teardown(data){if(scenario.teardown)return scenario.teardown(data); }\n')
        argv=[native,'run','--no-usage-report','--summary-export',str(output/'summary.json'),str(runner)];expected=[output/'summary.json']
    elif app=='axe-core':
        argv=['node',str(cli.HERE/'extended_axe.cjs'),str(cli.INSTALL),target,str(output/'report.json')];expected=[output/'report.json']
        env['PLAYWRIGHT_BROWSERS_PATH']=str(cli.INSTALL/'playwright-browsers')
    elif app=='zap':
        plan={'env':{'contexts':[{'name':'authorized-target','urls':[target],'includePaths':[re.escape(target.rstrip('/'))+'.*']}]},
          'jobs':[{'type':'spider','parameters':{'context':'authorized-target','maxDuration':1,'maxDepth':2}},
                  {'type':'passiveScan-wait','parameters':{'maxDuration':1}},
                  {'type':'report','parameters':{'template':'traditional-xml','reportDir':str(output),'reportFile':'report.xml'}}]}
        planfile=output/'passive-plan.yaml';planfile.write_text(json.dumps(plan,indent=2))
        argv=[native,'-cmd','-dir',str(output/'zap-home'),'-autorun',str(planfile)];expected=[output/'report.xml']
    elif app=='gitleaks':
        argv=[native,'dir','--no-banner','--redact=100','--report-format','json','--report-path',str(output/'report.json'),str(source)];expected=[output/'report.json']
    elif app=='openmodelica':argv=[native,str(actual)]
    elif app=='highs':
        argv=[native,str(actual),'--solution_file',str(output/'solution.txt'),'--time_limit','60','--threads','2'];expected=[output/'solution.txt']
    elif app=='kicad':
        expected_suffix='.kicad_pcb' if args['kind']=='pcb' else '.kicad_sch'
        if source.suffix.lower()!=expected_suffix:raise ValueError('Input does not match the selected KiCad document kind')
        render=output/'SVG';render.mkdir()
        argv=[native,args['kind'],'export','svg','--output',str(render)+os.sep]
        if args['kind']=='pcb':argv+=['--mode-multi','--layers','F.Cu,Edge.Cuts']
        argv.append(str(actual))
    elif app=='ngspice':argv=[native,'-b','-r',str(output/'simulation.raw'),str(actual)];expected=[output/'simulation.raw']
    elif app=='prusaslicer':
        cfg=output/'Sources/printer.ini';shutil.copy2(config,cfg)
        argv=['xvfb-run','--auto-servernum',native,'--load',str(cfg),'--export-gcode','--output',str(output/'print.gcode'),str(actual)];expected=[output/'print.gcode']
    else:raise ValueError('Unsupported optional workflow')
    stdout=output/'native.stdout';stderr=output/'native.stderr'
    spec=output/'native-command.json';spec.write_text(json.dumps({'argv':argv,'cwd':str(cwd),'stdout':str(stdout),'stderr':str(stderr),'env':env},indent=2))
    completed=cli.run(app,['/usr/bin/python3',str(cli.HERE/'extended_runner.py'),str(spec)],output,allow_failure=True)
    code=completed.returncode
    allowed_codes={0}
    if app=='qpdf':allowed_codes={0,2,3}
    if app=='gitleaks':allowed_codes={0,1}
    if app in ('schemathesis','verapdf'):allowed_codes={0,1}
    if code not in allowed_codes:raise RuntimeError(app+' failed: '+stderr.read_text(errors='replace')[-2500:]+'\n'+stdout.read_text(errors='replace')[-1500:])
    if any(not path.is_file() or not path.stat().st_size for path in expected):
        raise RuntimeError('Native workflow did not produce expected artifacts: '+str(expected))
    if app=='duckdb':shutil.copy2(stdout,output/'results.csv')
    if app=='openmodelica':
        log=stdout.read_text(errors='replace')+stderr.read_text(errors='replace')
        if 'Error:' in log or not any(actual.parent.glob('*_res.*')):
            raise RuntimeError('OpenModelica did not produce successful native simulation results: '+log[-2000:])
    if app=='poppler' and action=='render' and not list(output.glob('page-*.png')):raise RuntimeError('No PDF pages rendered')
    if app=='kicad' and not list((output/'SVG').glob('*.svg')):raise RuntimeError('No KiCad SVG exported')
    if app=='qpdf':result['status']='passed' if code==0 else 'uncertain' if code==3 else 'failed'
    elif app=='gitleaks':
        report=json.loads((output/'report.json').read_text());result.update(status='failed' if code else 'passed',findings=len(report or []))
    elif app=='axe-core':
        report=json.loads((output/'report.json').read_text());result.update(status='failed' if report['violations'] else 'passed',violations=len(report['violations']),incomplete=len(report['incomplete']))
    elif app=='verapdf':
        report=ET.fromstring(stdout.read_bytes());batch=next((e for e in report.iter() if e.tag.split('}')[-1]=='batchSummary'),None)
        if batch is None or int(batch.get('totalJobs','0'))!=1:raise RuntimeError('veraPDF did not validate one document')
        valid=any(e.get('isCompliant')=='true' for e in report.iter() if e.tag.split('}')[-1]=='validationReport')
        shutil.copy2(stdout,output/'report.xml');result['status']='passed' if valid and code==0 else 'failed'
    elif app=='schemathesis':result['status']='passed' if code==0 else 'failed'
    elif app=='gdal' and action=='inspect':
        report=json.loads(stdout.read_text());(output/'metadata.json').write_text(json.dumps(report,indent=2))
    if original and cli.digest(source)!=original:raise RuntimeError('Original input was modified')
    result['returncode']=code
    (output/'receipt.json').write_text(json.dumps({'app':app,'operation':action,'input_sha256':original,'result':result,
        'limits':['Native execution does not certify visual quality, engineering safety or complete security coverage.']},indent=2))
    return result
