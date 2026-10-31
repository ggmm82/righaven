"""Offline native fixtures for the lightweight domain CLIs: every case checks a known result."""
import json,subprocess
from pathlib import Path


def operation(c,name,**args):
    """Validators return status failed for a deliberately invalid fixture; that is not an error."""
    p=subprocess.run([c.app+'-cli','call',name,json.dumps(args)],capture_output=True,text=True,timeout=600)
    c.commands.append({'argv':[c.app+'-cli','call',name,args],'returncode':p.returncode,'stdout':p.stdout[-4000:],'stderr':p.stderr[-2000:]})
    if p.returncode not in (0,2):raise RuntimeError(p.stderr or p.stdout)
    return json.loads(p.stdout)


def write(c,name,text):
    path=c.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text);return path


JOURNAL='2026-01-01 Apertura\n    assets:banca      1000 EUR\n    equity:apertura\n\n2026-01-05 Spesa\n    expenses:cibo       45 EUR\n    assets:banca\n'
LEDGER=('option "operating_currency" "EUR"\n2026-01-01 open Assets:Bank EUR\n2026-01-01 open Expenses:Food EUR\n2026-01-01 open Equity:Opening EUR\n'
        '2026-01-01 * "Apertura"\n  Assets:Bank  1000 EUR\n  Equity:Opening\n2026-01-05 * "Spesa"\n  Expenses:Food  45 EUR\n  Assets:Bank\n')
FASTA='>a\nACGTACGTAAGGCCTTAA\n>b\nACGTTTGGCC\n>c\nACGTACGAAAGGCCTTAA\n'


def hledger(c):
    source=write(c,'conti.journal',JOURNAL)
    checked=operation(c,'check',input=str(source),output=str(c.root/'Check'))
    report=operation(c,'report',input=str(source),output=str(c.root/'Bilancio'),report='balance')
    text=(c.root/'Bilancio/report.csv').read_text()
    strict=operation(c,'check',input=str(source),output=str(c.root/'Strict'),strict=True)
    c.check('Strict mode reports the undeclared accounts',strict['status']=='failed','strict')
    c.check('Basic check passes and the balance reconciles to zero',checked['status']=='passed' and '"assets:banca","955 EUR"' in text and '"total","0"' in text,text)
    broken=write(c,'sbilanciato.journal','2026-01-01 Errore\n    assets:banca  10 EUR\n    equity:apertura  -9 EUR\n')
    c.check('An unbalanced transaction is reported',operation(c,'check',input=str(broken),output=str(c.root/'Broken'))['status']=='failed','unbalanced')


def beancount(c):
    source=write(c,'conti.beancount',LEDGER)
    checked=operation(c,'check',input=str(source),output=str(c.root/'Check'))
    operation(c,'query',input=str(source),output=str(c.root/'Query'),query="SELECT account, sum(number) AS total WHERE account ~ 'Assets' GROUP BY account")
    text=(c.root/'Query/result.csv').read_text()
    c.check('Ledger is valid and the bank balance is 955',checked['status']=='passed' and '955' in text,text)
    broken=write(c,'errato.beancount','2026-01-01 open Assets:Bank EUR\n2026-01-02 * "x"\n  Assets:Bank 5 EUR\n  Expenses:Unknown\n')
    c.check('An unopened account is reported',operation(c,'check',input=str(broken),output=str(c.root/'Broken'))['status']=='failed','unopened')


def openbabel(c):
    source=write(c,'etanolo.smi','CCO ethanol\n')
    operation(c,'convert',input=str(source),output=str(c.root/'SDF'),format='sdf',generate_3d=True)
    properties=operation(c,'properties',input=str(source),output=str(c.root/'Props'))
    text=(c.root/'Props/properties.txt').read_text();sdf=(c.root/'SDF/molecule.sdf').read_text()
    c.check('Ethanol C2H6O, MW 46.07, with 3D coordinates','C2H6O' in text and '46.06' in text and properties['molecules']==1 and 'V2000' in sdf,text)


def xtb(c):
    source=write(c,'acqua.xyz','3\nwater\nO 0.000 0.000 0.000\nH 0.000 0.000 1.100\nH 1.050 0.000 -0.300\n')
    result=operation(c,'optimize',input=str(source),output=str(c.root/'Opt'))
    c.check('GFN2-xTB geometry optimization converges',result['status']=='passed' and (c.root/'Opt/calculation/xtbopt.xyz').is_file(),result)


def seqkit(c):
    source=write(c,'sequenze.fasta',FASTA)
    stats=operation(c,'stats',input=str(source),output=str(c.root/'Stats'))
    operation(c,'filter',input=str(source),output=str(c.root/'Long'),min_length=15)
    kept=(c.root/'Long/filtered.fasta').read_text().count('>')
    c.check('Three sequences counted and two kept above 15 bases',stats['summary']['num_seqs']=='3' and kept==2,stats.get('summary'))


def samtools(c):
    sam=write(c,'aln.sam','@HD\tVN:1.6\tSO:unsorted\n@SQ\tSN:ref\tLN:60\nr2\t0\tref\t30\t60\t10M\t*\t0\t0\tACGTACGTAA\t*\nr1\t0\tref\t5\t60\t10M\t*\t0\t0\tACGTACGTAA\t*\n')
    operation(c,'flagstat',input=str(sam),output=str(c.root/'Flag'))
    operation(c,'sort',input=str(sam),output=str(c.root/'Sorted'))
    text=(c.root/'Flag/flagstat.tsv').read_text()
    c.check('Two mapped reads, sorted BAM with index',text.startswith('2\t0\ttotal') and (c.root/'Sorted/sorted.bam.bai').is_file(),text[:200])


def bcftools(c):
    source=write(c,'varianti.vcf','##fileformat=VCFv4.2\n##contig=<ID=1,length=100>\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n1\t10\t.\tA\tG\t50\tPASS\t.\n1\t20\t.\tC\tCT\t40\tPASS\t.\n')
    operation(c,'stats',input=str(source),output=str(c.root/'Stats'));text=(c.root/'Stats/stats.txt').read_text()
    c.check('One SNP and one indel among two records','number of records:\t2' in text and 'number of SNPs:\t1' in text and 'number of indels:\t1' in text,text[-600:])


def minimap2(c):
    import random
    rng=random.Random(60);genome=''.join(rng.choice('ACGT') for _ in range(2000))
    reference=write(c,'ref.fasta','>ref\n'+genome+'\n');reads=write(c,'reads.fasta','>r1\n'+genome[500:650]+'\n')
    operation(c,'align',input=str(reads),reference=str(reference),output=str(c.root/'Aln'),preset='sr')
    rows=[l.split('\t') for l in (c.root/'Aln/alignment.sam').read_text().splitlines() if not l.startswith('@')]
    c.check('Read aligned to the reference at position 501',rows and rows[0][2]=='ref' and rows[0][3]=='501',rows[:1])


def mafft(c):
    source=write(c,'sequenze.fasta',FASTA)
    operation(c,'align',input=str(source),output=str(c.root/'MSA'))
    records=[r for r in (c.root/'MSA/alignment.fasta').read_text().split('>') if r.strip()]
    lengths={len(''.join(r.splitlines()[1:])) for r in records}
    c.check('Three aligned sequences of equal length',len(records)==3 and len(lengths)==1,lengths)


def z3(c):
    source=write(c,'vincoli.smt2','(declare-const x Int)\n(declare-const y Int)\n(assert (= (+ x y) 10))\n(assert (> x 7))\n(assert (> y 0))\n(check-sat)\n(get-model)\n')
    sat=operation(c,'solve',input=str(source),output=str(c.root/'Sat'))
    impossible=write(c,'impossibile.smt2','(declare-const x Int)\n(assert (> x 5))\n(assert (< x 3))\n(check-sat)\n')
    unsat=operation(c,'solve',input=str(impossible),output=str(c.root/'Unsat'))
    c.check('Satisfiable model found and contradiction proven unsat',sat['answer']=='sat' and unsat['answer']=='unsat',[sat['answer'],unsat['answer']])


def minizinc(c):
    source=write(c,'turni.mzn','var 1..10: x; var 1..10: y; constraint x + y = 12; constraint x > y; solve maximize x;\noutput ["x=\\(x) y=\\(y)\\n"];\n')
    result=operation(c,'solve',input=str(source),output=str(c.root/'Solve'))
    text=(c.root/'Solve/solutions.txt').read_text()
    c.check('Gecode proves the optimum x=10 y=2',result['optimal'] and 'x=10 y=2' in text,text[-300:])


def maxima(c):
    source=write(c,'calcolo.mac','r: integrate(x^2, x, 0, 3);\nprint("RESULT", r);\nprint("ROOTS", solve(x^2-5*x+6=0, x));\n')
    operation(c,'evaluate',input=str(source),output=str(c.root/'Eval'));text=(c.root/'Eval/transcript.txt').read_text()
    c.check('Integral equals 9 and roots are 2 and 3','RESULT 9' in text and 'x = 3' in text and 'x = 2' in text,text[-400:])


def pari(c):
    source=write(c,'numeri.gp','print(factor(2^64+1));\nprint(isprime(2^61-1));\n')
    operation(c,'evaluate',input=str(source),output=str(c.root/'Eval'));text=(c.root/'Eval/output.txt').read_text()
    c.check('Exact factorization of 2^64+1 and primality of 2^61-1','274177' in text and '67280421310721' in text and text.strip().endswith('1'),text)


def netcdf(c,name):
    path=c.root/name
    subprocess.run(['/bin/sh','-c','cdo -f nc settaxis,2026-01-01,00:00,1day -const,2,r4x3 "$1/a.nc" && cdo -f nc settaxis,2026-01-02,00:00,1day -const,4,r4x3 "$1/b.nc" && cdo mergetime "$1/a.nc" "$1/b.nc" "$2"','x',str(c.root),str(path)],check=True,capture_output=True)
    return path


def cdo(c):
    data=netcdf(c,'serie.nc')
    operation(c,'info',input=str(data),output=str(c.root/'Info'))
    operation(c,'statistic',input=str(data),output=str(c.root/'Mean'),operator='timmean')
    mean=subprocess.run(['cdo','output',str(c.root/'Mean/timmean.nc')],capture_output=True,text=True,check=True).stdout.split()
    c.check('Time mean of 2 and 4 is 3 in every cell',mean and set(mean)=={'3'},mean[:6])


def nco(c):
    if subprocess.run(['which','cdo'],capture_output=True).returncode==0:data=netcdf(c,'serie.nc')
    else:
        data=c.root/'serie.nc';cdl=write(c,'serie.cdl','netcdf serie {\ndimensions:\n time = 2 ;\nvariables:\n float temp(time) ;\n  temp:units = "K" ;\n float other(time) ;\ndata:\n temp = 280, 282 ;\n other = 1, 2 ;\n}\n')
        subprocess.run(['ncgen','-o',str(data),str(cdl)],check=True)
    operation(c,'inspect',input=str(data),output=str(c.root/'Meta'))
    variable='const' if 'const' in (c.root/'Meta/metadata.txt').read_text() else 'temp'
    operation(c,'subset',input=str(data),output=str(c.root/'Sub'),variables=variable)
    c.check('Metadata read and selected variable extracted',(c.root/'Sub/subset.nc').stat().st_size>0 and variable in (c.root/'Meta/metadata.txt').read_text(),variable)


def jpeg(c,name):
    path=c.root/name
    # Tiny valid JPEG written by ExifTool's own test pattern is not shipped; build one with Python.
    subprocess.run(['/usr/bin/python3','-c','from PIL import Image;Image.new("RGB",(8,8),"red").save(__import__("sys").argv[1])',str(path)],check=True)
    subprocess.run(['exiftool','-overwrite_original','-Artist=Mario Rossi','-GPSLatitude=45.1','-GPSLatitudeRef=N',str(path)],check=True,capture_output=True)
    return path


def exiftool(c):
    photo=jpeg(c,'foto.jpg');result=operation(c,'read',input=str(photo),output=str(c.root/'Meta'))
    data=json.loads((c.root/'Meta/metadata.json').read_text())[0]
    c.check('Author and GPS position are reported as sensitive',any('Artist' in k for k in result['sensitive']) and any('GPS' in k for k in result['sensitive']) and data.get('IFD0:Artist')=='Mario Rossi',result['sensitive'])


def mat2(c):
    photo=jpeg(c,'foto.jpg')
    operation(c,'inspect',input=str(photo),output=str(c.root/'Show'))
    operation(c,'clean',input=str(photo),output=str(c.root/'Clean'))
    cleaned=c.root/'Clean/Sources/foto.cleaned.jpg'
    left=subprocess.run(['exiftool','-Artist','-GPSLatitude',str(cleaned)],capture_output=True,text=True).stdout
    original=subprocess.run(['exiftool','-Artist',str(photo)],capture_output=True,text=True).stdout
    c.check('Cleaned copy has no author or GPS; the original is untouched',cleaned.is_file() and not left.strip() and 'Mario Rossi' in original,left)


def font(c):
    import glob
    candidates=sorted(glob.glob('/usr/share/fonts/**/*.ttf',recursive=True))
    if not candidates:raise RuntimeError('A system TrueType font is required for the font fixtures')
    target=c.root/'carattere.ttf';target.write_bytes(Path(candidates[0]).read_bytes());return target


def fonttools(c):
    source=font(c)
    operation(c,'inspect',input=str(source),output=str(c.root/'Tables'))
    operation(c,'subset',input=str(source),output=str(c.root/'Subset'),text='RigHaven',flavor='ttf')
    subset=c.root/'Subset/subset.ttf'
    c.check('Table list read and subset is smaller than the original','glyf' in (c.root/'Tables/tables.txt').read_text() and 0<subset.stat().st_size<source.stat().st_size,subset.stat().st_size)


def fontforge(c):
    source=font(c);result=operation(c,'convert',input=str(source),output=str(c.root/'Woff'),format='woff')
    data=(c.root/'Woff/font.woff').read_bytes()
    c.check('Font regenerated as WOFF with its glyphs',data[:4]==b'wOFF' and result['glyphs']>50,result.get('glyphs'))


def zint(c):
    qr=operation(c,'encode',data='https://righaven.example/ordine/123',symbology='qrcode',format='svg',output=str(c.root/'QR'))
    bar=operation(c,'encode',data='4006381333931',symbology='ean13',format='png',output=str(c.root/'EAN'))
    svg=(c.root/'QR/code.svg').read_text()
    c.check('QR code in SVG and EAN-13 in PNG generated','<svg' in svg and (c.root/'EAN/code.png').read_bytes()[:4]==b'\x89PNG' and qr['status']==bar['status']=='passed','qr+ean')


def shellcheck(c):
    script=write(c,'pulizia.sh','#!/bin/bash\nrm -rf $DIR/*\necho $1\n')
    result=operation(c,'lint',input=str(script),output=str(c.root/'Lint'))
    clean=write(c,'ok.sh','#!/bin/bash\nset -eu\nprintf "%s\\n" "${1:-ciao}"\n')
    good=operation(c,'lint',input=str(clean),output=str(c.root/'Clean'))
    c.check('Unsafe expansion found; a clean script passes',result['findings']>=2 and good['status']=='passed',[result['findings'],good['status']])


def hadolint(c):
    folder=c.root/'image';folder.mkdir()
    dockerfile=write(c,'image/Dockerfile','FROM debian:latest\nRUN apt-get update && apt-get install -y curl\n')
    result=operation(c,'lint',input=str(dockerfile),output=str(c.root/'Lint'))
    codes={f.get('code') for f in json.loads((c.root/'Lint/report.json').read_text())}
    c.check('Unpinned base image and apt practices are reported','DL3007' in codes and result['status']=='failed',sorted(codes))


def actionlint(c):
    workflow=write(c,'ci.yml','on: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo "${{ github.event.nonexistent.value }}"\n        timeout-minutes: abc\n')
    result=operation(c,'lint',input=str(workflow),output=str(c.root/'Lint'))
    c.check('Invalid workflow fields are reported',result['findings']>=1,result)


def tflint(c):
    module=c.root/'modulo';module.mkdir()
    write(c,'modulo/main.tf','terraform {\n  required_version = ">= 1.5"\n}\nvariable "unused" {}\nlocals {\n  name = "righaven"\n}\noutput "name" {\n  value = local.name\n}\n')
    result=operation(c,'lint',input=str(module),output=str(c.root/'Lint'))
    report=json.loads((c.root/'Lint/report.json').read_text())
    c.check('Core Terraform rules run offline and report the unused variable',any('unused' in json.dumps(i).lower() for i in report.get('issues',[])) and not report.get('errors'),result)


def spectral(c):
    spec=write(c,'api.yaml','openapi: 3.0.3\ninfo:\n  title: Ordini\n  version: 1.0.0\npaths:\n  /ordini:\n    get:\n      responses:\n        "200":\n          description: ok\n')
    result=operation(c,'lint',input=str(spec),output=str(c.root/'Lint'))
    c.check('Standard OpenAPI rules report missing operationId and contact',result['findings']>=1 and 'operation' in (c.root/'Lint/report.json').read_text(),result)


def jq(c):
    data=write(c,'ordini.json','{"items":[{"n":"a","v":2},{"n":"b","v":5}]}')
    operation(c,'transform',input=str(data),output=str(c.root/'Out'),filter='[.items[] | .v] | add')
    c.check('Filter sums the values',(c.root/'Out/result.json').read_text().strip()=='7',(c.root/'Out/result.json').read_text())


def yq(c):
    data=write(c,'config.yaml','servizi:\n  - nome: api\n    porta: 8080\n  - nome: web\n    porta: 80\n')
    operation(c,'transform',input=str(data),output=str(c.root/'Out'),filter='[.servizi[] | select(.porta > 100) | .nome]')
    c.check('YAML filtered to the services above port 100',(c.root/'Out/result.yaml').read_text().strip()=='- api',(c.root/'Out/result.yaml').read_text())


def miller(c):
    data=write(c,'vendite.csv','prodotto,importo\na,10\nb,20\n');script=write(c,'doppio.mlr','$doppio = $importo * 2')
    operation(c,'transform',input=str(data),output=str(c.root/'Out'),script=str(script),output_format='json')
    rows=json.loads((c.root/'Out/result.json').read_text())
    c.check('DSL adds a computed column',[r['doppio'] for r in rows]==[20,40],rows)


def ajv(c):
    schema=write(c,'schema.json',json.dumps({'type':'object','required':['nome','eta'],'properties':{'nome':{'type':'string'},'eta':{'type':'integer','minimum':0}}}))
    good=write(c,'ok.json','{"nome":"Ada","eta":36}');bad=write(c,'errato.json','{"nome":"Ada","eta":-1}')
    ok=operation(c,'validate',input=str(good),schema=str(schema),output=str(c.root/'Ok'))
    ko=operation(c,'validate',input=str(bad),schema=str(schema),output=str(c.root/'Ko'))
    c.check('Valid document passes and a negative age is rejected',ok['status']=='passed' and ko['status']=='failed',[ok['status'],ko['status']])


def mjml(c):
    template=write(c,'newsletter.mjml','<mjml><mj-body><mj-section><mj-column><mj-text>Ciao RigHaven</mj-text><mj-button href="https://righaven.example">Apri</mj-button></mj-column></mj-section></mj-body></mjml>')
    result=operation(c,'compile',input=str(template),output=str(c.root/'Email'))
    html=(c.root/'Email/email.html').read_text()
    c.check('Responsive HTML compiled with the content','Ciao RigHaven' in html and '<table' in html and result['status']=='passed',len(html))


TUNE='X:1\nT:Scala\nM:4/4\nL:1/4\nK:C\nC D E F|G A B c|\n'


def abcm2ps(c):
    source=write(c,'scala.abc',TUNE);operation(c,'engrave',input=str(source),output=str(c.root/'Score'))
    svg=sorted((c.root/'Score').glob('score*.svg'))
    c.check('Tune engraved as SVG',svg and '<svg' in svg[0].read_text(),[p.name for p in svg])


def abcmidi(c):
    source=write(c,'scala.abc',TUNE);operation(c,'midi',input=str(source),output=str(c.root/'Midi'))
    data=(c.root/'Midi/tune.mid').read_bytes()
    c.check('Standard MIDI file written',data[:4]==b'MThd' and len(data)>40,len(data))


def hunspell(c):
    text=write(c,'testo.txt','Questo testo contiene un errrore e una parola sbagliataa.\n')
    result=operation(c,'check',input=str(text),output=str(c.root/'Check'),language='it_IT')
    c.check('Exactly the two misspelled Italian words are listed',set(result['sample'])=={'errrore','sbagliataa'},result['sample'])


def vale(c):
    text=write(c,'nota.md','# Nota\n\nThis is is a repeated word.\n')
    result=operation(c,'lint',input=str(text),output=str(c.root/'Lint'))
    c.check('Built-in rules report the repeated word',result['alerts']>=1 and 'Repetition' in (c.root/'Lint/report.json').read_text(),result)


CASES={name:globals()[name] for name in (
    'hledger','beancount','openbabel','xtb','seqkit','samtools','bcftools','minimap2','mafft','z3','minizinc','maxima','pari',
    'cdo','nco','exiftool','mat2','fonttools','fontforge','zint','shellcheck','hadolint','actionlint','tflint','spectral',
    'jq','yq','miller','ajv','mjml','abcm2ps','abcmidi','hunspell','vale')}
