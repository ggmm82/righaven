"""Native workflows for lightweight domain CLIs: private output folders, retained sources,
native stdout/stderr, explicit exit codes and a receipt for every run."""
import json,re,shutil
from pathlib import Path
try:from .domain_specs import TOOLS
except ImportError:from domain_specs import TOOLS

APPS=set(TOOLS)
NODE={'spectral':'spectral','ajv':'ajv','mjml':'mjml'}
BINARIES={'beancount':'bean-check','openbabel':'obabel','pari':'gp','nco':'ncks','fonttools':'ttx','abcmidi':'abc2midi','miller':'mlr','maxima':'maxima-sage'}
VERSION_FLAGS={'openbabel':['-V'],'seqkit':['version'],'pari':['--version-short'],'exiftool':['-ver'],'abcm2ps':['-V'],
               'abcmidi':['-ver'],'actionlint':['-version'],'beancount':['--help'],'mat2':['--help'],'ajv':['help']}
SUFFIXES={
 ('hledger','*'):{'.journal','.hledger','.j','.ledger','.csv'},('beancount','*'):{'.beancount','.bean'},
 ('openbabel','*'):{'.smi','.smiles','.sdf','.mol','.mol2','.xyz','.pdb','.cml','.inchi'},('xtb','*'):{'.xyz'},
 ('seqkit','*'):{'.fa','.fasta','.fna','.faa','.fq','.fastq','.gz'},('samtools','*'):{'.sam','.bam','.cram'},
 ('bcftools','*'):{'.vcf','.bcf','.gz'},('minimap2','*'):{'.fa','.fasta','.fq','.fastq','.gz'},('mafft','*'):{'.fa','.fasta','.faa','.fna'},
 ('z3','*'):{'.smt2','.smt'},('minizinc','*'):{'.mzn'},('maxima','*'):{'.mac','.max','.wxm'},('pari','*'):{'.gp'},
 ('cdo','*'):{'.nc','.nc4','.grb','.grb2','.grib','.grib2'},('nco','*'):{'.nc','.nc4'},
 ('fonttools','*'):{'.ttf','.otf','.woff','.woff2'},('fontforge','*'):{'.ttf','.otf','.sfd','.woff','.woff2','.ufo'},
 ('shellcheck','*'):{'.sh','.bash','.ksh','.dash'},('actionlint','*'):{'.yml','.yaml'},('spectral','*'):{'.yaml','.yml','.json'},
 ('jq','*'):{'.json','.jsonl','.geojson'},('yq','*'):{'.yaml','.yml','.xml','.toml'},('miller','*'):{'.csv','.tsv','.json','.jsonl'},
 ('ajv','*'):{'.json','.yaml','.yml'},('mjml','*'):{'.mjml'},('abcm2ps','*'):{'.abc'},('abcmidi','*'):{'.abc'},
 ('hunspell','*'):{'.txt','.md','.tex','.html','.xml','.rst'},('vale','*'):{'.md','.txt','.rst','.adoc','.html','.org','.tex'},
}
SYMBOLOGY={'qrcode':58,'datamatrix':71,'pdf417':55,'code128':20,'ean13':13,'gs1-128':16}
NAME=re.compile(r'[A-Za-z_][A-Za-z0-9_.-]{0,63}')


def binary(app,cli):
    if app in NODE:return str(cli.INSTALL/'apps'/app/'node_modules/.bin'/NODE[app])
    return BINARIES.get(app,app)


def version_flags(app):
    return VERSION_FLAGS.get(app,['--version'])


def text_argument(value,limit,label):
    if not isinstance(value,str) or not value.strip() or len(value)>limit or '\x00' in value:
        raise ValueError(label+': testo non vuoto entro '+str(limit)+' caratteri')
    return value


def keep(path,output,name=None):
    """Copy a supporting file next to the retained input so the run can be repeated."""
    target=output/'Sources'/(name or path.name)
    if target.exists():raise ValueError('Two supporting files share the name '+target.name)
    target.parent.mkdir(exist_ok=True);shutil.copy2(path,target);return target


def invoke(app,action,args,cli):
    output=cli.scoped(args['output'],exists=False,directory=True,fresh=True)
    source=None
    if 'input' in args:
        source=cli.scoped(args['input'],directory=app=='tflint')
        if source.is_dir() and output.is_relative_to(source):raise ValueError('Output must be outside the inspected folder')
        allowed=SUFFIXES.get((app,'*'))
        if allowed and source.is_file() and source.suffix.lower() not in allowed and not (app=='hadolint'):
            raise ValueError('Formato non supportato per '+app+': '+source.suffix)
        if app=='hadolint' and not (source.name=='Dockerfile' or source.name.endswith(('.Dockerfile','.dockerfile')) or source.name.startswith('Dockerfile.')):
            raise ValueError('hadolint richiede un Dockerfile')
        if source.is_file() and source.stat().st_size>512*1024**2:raise ValueError('Input oltre 512 MiB')
    original=cli.digest(source) if source and source.is_file() else None
    output.mkdir(parents=True);(output/'Sources').mkdir()
    if source and source.is_dir():
        actual=output/'Sources'/source.name
        if any(p.is_symlink() for p in source.rglob('*')):raise ValueError('Source folders must not contain symlinks')
        shutil.copytree(source,actual)
    elif source:actual=keep(source,output)
    else:actual=None
    native=binary(app,cli);cwd=output;stdout_to=None;expected=[];codes={0};env={'OMP_NUM_THREADS':'2','HOME':str(output/'private-home')}
    (output/'private-home').mkdir()
    a=str(actual) if actual else None
    if app=='hledger':
        if action=='check':argv=[native,'-f',a,'check']+(['--strict'] if args.get('strict') else [])
        else:argv=[native,'-f',a,args['report'],'-O','csv','-o',str(output/'report.csv')];expected=[output/'report.csv']
        codes={0,1} if action=='check' else {0}
    elif app=='beancount':
        if action=='check':argv=['bean-check',a];codes={0,1}
        else:
            query=output/'Sources/query.bql';query.write_text(text_argument(args['query'],4000,'query'))
            argv=['bean-query','-f','csv','-o',str(output/'result.csv'),a,args['query']];expected=[output/'result.csv']
    elif app=='openbabel':
        if action=='convert':
            target=output/('molecule.'+args['format']);argv=[native,a,'-O',str(target)]+(['--gen3d'] if args.get('generate_3d') else []);expected=[target]
        else:argv=[native,a,'-otxt','--append','formula MW logP TPSA'];stdout_to='properties.txt'
    elif app=='xtb':
        work=output/'calculation';work.mkdir();shutil.copy2(actual,work/actual.name);cwd=work
        argv=[native,actual.name,'--opt','normal','--gfn','2','--chrg',str(args.get('charge',0)),'--uhf',str(args.get('unpaired',0))]
        stdout_to='xtb.log';expected=[work/'xtbopt.xyz'];env['OMP_STACKSIZE']='1G'
    elif app=='seqkit':
        if action=='stats':argv=[native,'stats','-a','-T',a];stdout_to='stats.tsv'
        else:
            low,high=args.get('min_length',1),args.get('max_length',100000000)
            if low>high:raise ValueError('min_length supera max_length')
            target=output/('filtered'+''.join(actual.suffixes[-2:] if actual.suffix=='.gz' else [actual.suffix]))
            argv=[native,'seq','-m',str(low),'-M',str(high)]+(['-r','-p'] if args.get('reverse_complement') else [])+[a,'-o',str(target)];expected=[target]
    elif app=='samtools':
        if action=='flagstat':argv=[native,'flagstat','-O','tsv',a];stdout_to='flagstat.tsv'
        else:
            target=output/'sorted.bam';argv=['/bin/sh','-c','samtools sort -o "$1" "$2" && samtools index "$1"','samtools-sort',str(target),a]
            expected=[target,output/'sorted.bam.bai']
    elif app=='bcftools':argv=[native,'stats',a];stdout_to='stats.txt'
    elif app=='minimap2':
        reference=keep(cli.scoped(args['reference']),output,'reference'+Path(args['reference']).suffix)
        argv=[native,'-a','-x',args.get('preset','sr'),'-t','2',str(reference),a,'-o',str(output/'alignment.sam')];expected=[output/'alignment.sam']
    elif app=='mafft':argv=[native,'--auto','--thread','2',a];stdout_to='alignment.fasta'
    elif app=='z3':argv=[native,'-smt2','-T:'+str(args.get('timeout_seconds',60)),a];stdout_to='result.txt';codes={0,1}
    elif app=='minizinc':
        argv=[native,'--solver','gecode','--time-limit',str(1000*args.get('timeout_seconds',60)),'--statistics']+(['--all-solutions'] if args.get('all_solutions') else [])+[a]
        if args.get('data'):argv.append(str(keep(cli.scoped(args['data']),output)))
        stdout_to='solutions.txt'
    elif app=='maxima':argv=[native,'--very-quiet','--batch='+a];stdout_to='transcript.txt'
    elif app=='pari':argv=['/bin/sh','-c','gp -q -f --default parisizemax=1000000000 < "$1"','gp',a];stdout_to='output.txt'
    elif app=='cdo':
        if action=='info':argv=[native,'sinfon',a];stdout_to='info.txt'
        else:argv=[native,'-f','nc',args['operator'],a,str(output/(args['operator']+'.nc'))];expected=[output/(args['operator']+'.nc')]
    elif app=='nco':
        if action=='inspect':argv=[native,'-m',a];stdout_to='metadata.txt'
        else:
            names=[v.strip() for v in args['variables'].split(',') if v.strip()]
            if not names or any(not NAME.fullmatch(v) for v in names):raise ValueError('variables: nomi separati da virgola')
            argv=[native,'-O','-v',','.join(names),a,str(output/'subset.nc')];expected=[output/'subset.nc']
    elif app=='exiftool':argv=[native,'-json','-G1','-n',a];stdout_to='metadata.json'
    elif app=='mat2':
        if action=='inspect':argv=[native,'--show',a];stdout_to='metadata.txt'
        else:
            argv=[native,a];expected=[actual.with_name(actual.stem+'.cleaned'+actual.suffix)]
    elif app=='fonttools':
        if action=='inspect':argv=['ttx','-l',a];stdout_to='tables.txt'
        else:
            flavor=args.get('flavor','woff2');target=output/('subset.'+flavor)
            argv=['pyftsubset',a,'--text='+text_argument(args['text'],20000,'text'),'--output-file='+str(target)]+([] if flavor=='ttf' else ['--flavor='+flavor])
            expected=[target]
    elif app=='fontforge':
        target=output/('font.'+args['format'])
        argv=[native,'-lang=py','-c','import fontforge,sys\nf=fontforge.open(sys.argv[1])\nf.generate(sys.argv[2])\nprint(len(list(f.glyphs())))',a,str(target)]
        stdout_to='glyphs.txt';expected=[target]
    elif app=='zint':
        data=output/'Sources/data.txt';data.write_text(text_argument(args['data'],2000,'data'))
        target=output/('code.'+args.get('format','svg'))
        argv=[native,'-b',str(SYMBOLOGY[args['symbology']]),'--input='+str(data),'-o',str(target)]+(['--gs1'] if args['symbology']=='gs1-128' else []);expected=[target]
    elif app=='shellcheck':argv=[native,'-f','json',a];stdout_to='report.json';codes={0,1}
    elif app=='hadolint':argv=[native,'-f','json','--no-color',a];stdout_to='report.json';codes={0,1}
    elif app=='actionlint':argv=[native,'-format','{{json .}}','-no-color',a];stdout_to='report.json';codes={0,1}
    elif app=='tflint':argv=[native,'--chdir='+a,'--format=json','--no-color'];stdout_to='report.json';codes={0,1,2,3}
    elif app=='spectral':
        if args.get('ruleset'):ruleset=keep(cli.scoped(args['ruleset']),output,'.spectral'+Path(args['ruleset']).suffix)
        else:
            ruleset=output/'Sources/.spectral.yaml';ruleset.write_text('extends: ["spectral:oas", "spectral:asyncapi"]\n')
        argv=[native,'lint',a,'--ruleset',str(ruleset),'--format','json','--output',str(output/'report.json'),'--fail-severity','error'];expected=[output/'report.json'];codes={0,1}
    elif app in ('jq','yq'):
        program=output/'Sources/filter.jq';program.write_text(text_argument(args['filter'],8000,'filter'))
        argv=[native]+(['-y'] if app=='yq' else [])+['-f',str(program),a];stdout_to='result.yaml' if app=='yq' else 'result.json'
    elif app=='miller':
        source_format=args.get('input_format') or {'.tsv':'tsv','.json':'json','.jsonl':'json'}.get(actual.suffix.lower(),'csv')
        target_format=args.get('output_format','csv')
        argv=[native,'--i'+source_format,'--o'+target_format]
        if args.get('script'):argv+=['put','-f',str(keep(cli.scoped(args['script']),output))]
        else:argv+=['cat']
        argv.append(a);stdout_to='result.'+{'markdown':'md'}.get(target_format,target_format)
    elif app=='ajv':
        schema=keep(cli.scoped(args['schema']),output,'schema'+Path(args['schema']).suffix)
        argv=[native,'validate','--spec='+{'2020':'draft2020','2019':'draft2019','draft7':'draft7'}[args.get('draft','2020')],'--all-errors','--errors=json','--strict=false','-s',str(schema),'-d',a]
        stdout_to='result.txt';codes={0,1}
    elif app=='mjml':argv=[native,a,'-o',str(output/'email.html'),'--config.validationLevel=strict'];expected=[output/'email.html'];codes={0,1}
    elif app=='abcm2ps':argv=[native,'-g','-O',str(output/'score'),a];stdout_to='abcm2ps.log'
    elif app=='abcmidi':argv=[native,a,'-o',str(output/'tune.mid')];expected=[output/'tune.mid'];stdout_to='abc2midi.log'
    elif app=='hunspell':argv=[native,'-l','-d',args.get('language','it_IT'),a];stdout_to='unknown-words.txt'
    elif app=='vale':
        if args.get('config'):config=keep(cli.scoped(args['config']),output,'.vale.ini')
        else:
            config=output/'Sources/.vale.ini';config.write_text('MinAlertLevel = suggestion\n\n[*]\nBasedOnStyles = Vale\n')
        argv=[native,'--config='+str(config),'--output=JSON','--no-exit',a];stdout_to='report.json'
    else:raise ValueError('Operazione di dominio non supportata: '+app)
    stdout=output/(stdout_to or 'native.stdout');stderr=output/'native.stderr'
    spec=output/'native-command.json'
    spec.write_text(json.dumps({'argv':argv,'cwd':str(cwd),'stdout':str(stdout),'stderr':str(stderr),'env':env},indent=2))
    completed=cli.run(app,['/usr/bin/python3',str(cli.HERE/'extended_runner.py'),str(spec)],output,allow_failure=True)
    code=completed.returncode
    if code not in codes:
        raise RuntimeError(app+' failed ('+str(code)+'): '+stderr.read_text(errors='replace')[-2500:]+'\n'+stdout.read_text(errors='replace')[-1500:])
    if app=='ajv':
        # ajv-cli prints the verdict and JSON errors on stderr; keep both streams in the report.
        stdout.write_bytes(stdout.read_bytes()+stderr.read_bytes())
    if stdout_to and not expected:expected=[stdout]
    if app=='abcm2ps':expected=sorted(output.glob('score*.svg'))[:1] or [output/'score001.svg']
    if any(not path.is_file() or not path.stat().st_size for path in expected):
        raise RuntimeError('Native workflow did not produce expected artifacts: '+', '.join(map(str,expected)))
    result={'output':str(output),'original_preserved':True,'status':'passed' if code==0 else 'failed','returncode':code,
            'artifacts':[str(p) for p in expected]}
    text=stdout.read_text(errors='replace') if stdout.is_file() else ''
    if app=='z3':
        first=text.strip().splitlines()[0] if text.strip() else 'unknown'
        result.update(answer=first,status='passed' if first in ('sat','unsat') and code==0 else 'uncertain')
    elif app=='minizinc':
        result.update(optimal='==========' in text,unsatisfiable='=====UNSATISFIABLE=====' in text,solutions=text.count('----------'))
        if result['unsatisfiable'] or not result['solutions']:result['status']='failed'
    elif app=='xtb':result['status']='passed' if 'GEOMETRY OPTIMIZATION CONVERGED' in text else 'failed'
    elif app in ('shellcheck','hadolint','actionlint'):
        findings=json.loads(text or '[]');result.update(findings=len(findings),status='failed' if findings else 'passed')
    elif app=='tflint':
        report=json.loads(text or '{}');result.update(findings=len(report.get('issues',[])),errors=len(report.get('errors',[])),
            status='passed' if code==0 and not report.get('errors') else 'failed')
    elif app=='spectral':
        findings=json.loads((output/'report.json').read_text() or '[]')
        result.update(findings=len(findings),errors=sum(1 for f in findings if f.get('severity')==0))
    elif app=='vale':
        alerts=json.loads(text or '{}');count=sum(len(v) for v in alerts.values())
        result.update(alerts=count,errors=sum(1 for v in alerts.values() for a in v if a.get('Severity')=='error'),status='passed' if not count else 'failed')
    elif app=='hunspell':
        words=sorted({w for w in text.split() if w});result.update(unknown_words=len(words),sample=words[:50],status='passed' if not words else 'failed')
    elif app=='exiftool':
        tags=json.loads(text)[0];result.update(tags=len(tags),sensitive=sorted(k for k in tags if re.search(r'GPS|Author|Artist|Creator|Owner|Serial|Comment',k))[:40])
    elif app=='fontforge':result['glyphs']=int(text.strip().splitlines()[-1]) if text.strip() else 0
    elif app=='openbabel' and action=='properties':result['molecules']=len([l for l in text.splitlines() if l.strip()])
    elif app=='seqkit' and action=='stats':
        rows=[l.split('\t') for l in text.splitlines() if l.strip()]
        if len(rows)>1:result['summary']=dict(zip(rows[0],rows[1]))
    elif app=='ajv':result['status']='passed' if code==0 else 'failed'
    if original and cli.digest(source)!=original:raise RuntimeError('Original input was modified')
    (output/'receipt.json').write_text(json.dumps({'app':app,'operation':action,'input_sha256':original,'result':result,
        'limits':['Native execution proves what the tool checked, not domain correctness, legal compliance or fitness for purpose.']},indent=2))
    return result
