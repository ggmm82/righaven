"""Schema model and DDL jobs, executed in the pinned SQLGlot environment (no database connection)."""
import json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import pipeline_model as pm

CRON=re.compile(r'@(hourly|daily|weekly|monthly|yearly|annually|midnight)|([\d*/,\-A-Za-z?LW#]+\s+){4,6}[\d*/,\-A-Za-z?LW#]+')
DISCOVER_DIALECT={'postgresql':'postgres','mssql':'tsql','mysql':'mysql','mariadb':'mysql','oracle':'oracle','sqlite':'sqlite','duckdb':'duckdb'}


def build(spec):
    source=Path(spec['input']);dialect=spec.get('dialect')
    if source.suffix.lower()=='.sql':
        if not dialect:raise ValueError('Indica il dialetto del DDL (postgres, tsql, mysql, oracle, ...)')
        model=pm.from_ddl(source.read_text(errors='replace'),dialect,spec.get('name') or source.stem)
    else:
        data=pm.load(source)
        if isinstance(data,dict) and data.get('kind')=='sql' and isinstance(data.get('tables'),list):
            dialect=dialect or DISCOVER_DIALECT.get(data.get('dialect'),data.get('dialect'))
            if not dialect:raise ValueError('Metadati senza dialetto: indica dialect')
            model=pm.from_discover(data,dialect)
        elif isinstance(data,dict) and isinstance(data.get('tables'),list):
            model=data;model.setdefault('source',{'kind':'documented','dialect':dialect or ''})
        else:raise ValueError('Input non riconosciuto: usa DDL .sql, il result.json di dlt discover o un modello JSON/YAML con "tables"')
    if spec.get('name'):model['name']=spec['name']
    strict=spec.get('strict_references',True)
    model=pm.validate(model,strict_references=strict)
    if spec.get('overrides'):
        overrides=pm.load(spec['overrides'])
        if not isinstance(overrides,dict):raise ValueError('La documentazione deve essere un oggetto con "tables"')
        model=pm.validate(pm.merge(model,overrides),strict_references=strict)
    return model


def main():
    spec=json.loads(Path(sys.argv[1]).read_text());output=Path(spec['output'])
    if spec['action']=='model':
        model=build(spec)
        (output/'model.json').write_text(json.dumps(model,indent=2,ensure_ascii=False))
        summary=pm.summary(model)
        issues=''.join('- '+i+'\n' for i in model['issues']) or 'Nessuna segnalazione.\n'
        (output/'issues.md').write_text('# Segnalazioni sul modello "'+model['name']+'"\n\n'+issues)
        result={'model':'model.json','summary':summary,'issues':model['issues'][:50]}
    elif spec['action']=='ddl':
        model=pm.validate(pm.load(spec['input']),strict_references=False);target=spec['dialect']
        text,limits=pm.ddl(model,target,comments=spec.get('comments',True))
        statements=pm.verify_ddl(text,target)
        name='schema.'+target+'.sql';(output/name).write_text(text)
        result={'ddl':name,'dialect':target,'statements':statements,'tables':len([t for t in model['tables'] if t.get('kind','table')=='table']),'limits':limits}
    elif spec['action']=='scaffold':
        import pipeline_scaffold
        model=pm.validate(pm.load(spec['input']),strict_references=False)
        schedule={'ingest':spec.get('ingest_cron') or '7 * * * *','transform':spec.get('transform_cron') or '27 * * * *',
                  'stubs':spec.get('stubs_cron') or '*/30 * * * *','transform_model_cron':spec.get('model_cron') or '@hourly'}
        for key in ('ingest','transform','stubs'):
            if not CRON.fullmatch(schedule[key]):raise ValueError('Espressione cron non valida per '+key+': '+schedule[key])
        source=spec.get('source_dialect') or (model.get('source') or {}).get('dialect') or 'postgres'
        result=pipeline_scaffold.scaffold(model,output,target=spec['dialect'],source_dialect=source,name=spec.get('name'),schedule=schedule)
    else:raise ValueError('Azione non supportata: '+spec['action'])
    (output/'result.json').write_text(json.dumps(result,indent=2,ensure_ascii=False))
    print(json.dumps({'status':'passed','result':'result.json'}))


if __name__=='__main__':
    try:main()
    except ValueError as error:
        print(str(error),file=sys.stderr);sys.exit(3)
