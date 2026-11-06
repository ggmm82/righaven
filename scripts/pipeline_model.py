"""Engine-neutral schema model for the end-to-end data pipeline recipe.

The model is plain JSON: tables, columns with portable types, declared keys,
documented descriptions, privacy labels and stub-data hints. It is built from
observed metadata (dlt discover), from DDL in any SQLGlot dialect, or from a
model written from project documentation, and it emits DDL for another engine.
Runs in the pinned SQLGlot environment; it never connects to a database.
"""
import copy,json,re
from pathlib import Path

VERSION=1
NAME=re.compile(r'^[A-Za-z_][A-Za-z0-9_$#@ -]{0,127}$')
TARGETS=('duckdb','postgres','tsql','fabric','mysql','oracle','sqlite')
SOURCES=('postgres','tsql','mysql','oracle','sqlite','duckdb','fabric','snowflake','bigquery','databricks','redshift')
MAX_TABLES=1000
MAX_COLUMNS=1000
GENERATOR_KEYS={'faker','values','weights','min','max','null_ratio','unique','pattern','start','step','decimals','days_back','length','constant'}
TABLE_KEYS={'schema','name','description','kind','columns','primary_key','unique','foreign_keys','checks','labels','rows','owner','grain','refresh'}
COLUMN_KEYS={'name','type','source_type','nullable','default','description','pii','labels','generator','example'}


def sqlglot():
    import sqlglot as module
    return module


def portable_type(text,dialect=None):
    """Canonical SQLGlot type text; unknown vendor types are kept with an issue."""
    from sqlglot import exp
    try:
        canonical=exp.DataType.build(str(text),dialect=dialect or None).sql()
        if re.fullmatch(r'N?(VAR)?CHAR\(MAX\)|VARBINARY\(MAX\)',canonical):canonical='VARBINARY' if 'BINARY' in canonical else 'TEXT'
        if canonical in UNSIGNED:
            return UNSIGNED[canonical],'intero senza segno '+str(text)+' reso portabile come '+UNSIGNED[canonical]
        return canonical,None
    except Exception:
        return 'TEXT','tipo non riconosciuto '+repr(str(text))+' trattato come TEXT'


def key(schema,name):
    return ((schema or '').lower(),name.lower())


def qualified(table):
    return (table['schema']+'.' if table.get('schema') else '')+table['name']


def empty(name,source):
    return {'model_version':VERSION,'name':name,'description':'','source':source,'tables':[],'issues':[]}


def column(name,type_text,dialect,nullable=True,default=None,description=''):
    canonical,issue=portable_type(type_text,dialect)
    return {'name':name,'type':canonical,'source_type':str(type_text),'nullable':bool(nullable),
            'default':None if default in (None,'') else str(default),'description':description or '','pii':False},issue


def from_discover(data,dialect):
    """Observed SQLAlchemy metadata produced by dlt discover."""
    if data.get('kind')!='sql':raise ValueError('Il modello relazionale richiede metadati SQL, non una scoperta MongoDB')
    model=empty(data.get('database') or 'database',{'kind':'metadata','dialect':dialect})
    for item in data['tables']:
        table={'schema':item.get('schema') or '','name':item['name'],'description':item.get('comment') or '','kind':item.get('kind','table'),
               'columns':[],'primary_key':list((item.get('primary_key') or {}).get('constrained_columns') or []),
               'unique':[list(u['column_names']) for u in item.get('unique_constraints') or [] if u.get('column_names')],
               'foreign_keys':[],'checks':[{'name':c.get('name') or '','expression':c['sqltext']} for c in item.get('check_constraints') or [] if c.get('sqltext')],'labels':[]}
        for c in item['columns']:
            value,issue=column(c['name'],c['type'],dialect,c.get('nullable',True),c.get('default'),c.get('comment') or '')
            table['columns'].append(value)
            if issue:model['issues'].append(qualified(table)+'.'+c['name']+': '+issue)
        for fk in item.get('foreign_keys') or []:
            if not fk.get('referred_table'):continue
            table['foreign_keys'].append({'name':fk.get('name') or '','columns':list(fk['constrained_columns']),
                'references':{'schema':fk.get('referred_schema') or table['schema'],'table':fk['referred_table'],'columns':list(fk['referred_columns'])},'declared':True})
        model['tables'].append(table)
    return model


def split_script(text,dialect):
    if dialect in ('tsql','fabric'):text=re.sub(r'(?im)^\s*GO\s*;?\s*$',';',text)
    return text


def statements(text,dialect):
    """Parse a whole script; on failure parse statement by statement and keep the rest as issues."""
    module=sqlglot();issues=[]
    try:return [s for s in module.parse(text,read=dialect) if s is not None],issues
    except Exception:pass
    parsed=[]
    for chunk in re.split(r';\s*(?:\n|$)',text):
        if not chunk.strip() or re.fullmatch(r'(\s*--[^\n]*\n?)*\s*',chunk):continue
        try:parsed.extend(s for s in module.parse(chunk,read=dialect) if s is not None)
        except Exception as error:issues.append('istruzione non interpretata: '+chunk.strip().splitlines()[0][:120]+' ('+str(error).splitlines()[0][:80]+')')
    return parsed,issues


def ident(node):
    return node.name if hasattr(node,'name') else str(node)


def names(node):
    """Column names from a Schema, an (Non)Clustered list of Ordered, or plain identifiers."""
    from sqlglot import exp
    if node is None:return []
    if isinstance(node,list):return [n for item in node for n in names(item)]
    if isinstance(node,exp.Schema):return [ident(c) for c in node.expressions] or [ident(node.this)]
    if isinstance(node,(exp.ClusteredColumnConstraint,exp.NonClusteredColumnConstraint)):return names(node.this)
    if isinstance(node,exp.Ordered):return names(node.this)
    return [ident(node)]


UNSIGNED={'UTINYINT':'SMALLINT','USMALLINT':'INT','UMEDIUMINT':'INT','UINT':'BIGINT','UBIGINT':'DECIMAL(20, 0)'}


def from_ddl(text,dialect,name):
    from sqlglot import exp
    model=empty(name,{'kind':'ddl','dialect':dialect});parsed,model['issues']=statements(split_script(text,dialect),dialect)
    tables={}
    def find(schema,table):
        return tables.get(key(schema,table)) or next((t for (s,n),t in tables.items() if n==table.lower() and not schema),None)
    def add_fk(table,columns,reference,name=''):
        target=reference.this if isinstance(reference,exp.Reference) else reference
        parent=target.this if isinstance(target,exp.Schema) else target
        refs=[ident(c) for c in target.expressions] if isinstance(target,exp.Schema) else []
        table['foreign_keys'].append({'name':name,'columns':columns,'references':{'schema':parent.db or table['schema'],'table':parent.name,'columns':refs},'declared':True})
    for statement in parsed:
        if isinstance(statement,exp.Create) and (statement.kind or '').upper() in ('TABLE','VIEW'):
            target=statement.this;relation=target.this if isinstance(target,exp.Schema) else target
            table={'schema':relation.db or '','name':relation.name,'description':'','kind':statement.kind.lower(),'columns':[],
                   'primary_key':[],'unique':[],'foreign_keys':[],'checks':[],'labels':[]}
            if statement.kind.upper()=='VIEW':
                table['definition']=statement.expression.sql(dialect=dialect) if statement.expression else ''
                model['issues'].append(qualified(table)+': vista registrata senza colonne dichiarate; documentala o ricavala dal database')
            for item in (target.expressions if isinstance(target,exp.Schema) else []):
                if isinstance(item,exp.ColumnDef):
                    kind=item.args.get('kind');value,issue=column(item.name,kind.sql(dialect=dialect) if kind else 'TEXT',dialect)
                    if issue:model['issues'].append(qualified(table)+'.'+item.name+': '+issue)
                    for constraint in item.constraints:
                        c=constraint.kind
                        if isinstance(c,exp.NotNullColumnConstraint) and not c.args.get('allow_null'):value['nullable']=False
                        elif isinstance(c,exp.PrimaryKeyColumnConstraint):table['primary_key']=[item.name];value['nullable']=False
                        elif isinstance(c,exp.UniqueColumnConstraint):table['unique'].append([item.name])
                        elif isinstance(c,exp.DefaultColumnConstraint):value['default']=c.this.sql(dialect=dialect)
                        elif isinstance(c,exp.CheckColumnConstraint):table['checks'].append({'name':'','expression':c.this.sql(dialect=dialect)})
                        elif isinstance(c,exp.Reference):add_fk(table,[item.name],c)
                        elif isinstance(c,exp.CommentColumnConstraint):value['description']=c.this.name
                    table['columns'].append(value)
                elif isinstance(item,(exp.PrimaryKey,exp.Constraint,exp.ForeignKey,exp.UniqueColumnConstraint,exp.CheckColumnConstraint)):
                    constraint_name=item.name if isinstance(item,exp.Constraint) else ''
                    parts=item.expressions if isinstance(item,exp.Constraint) else [item]
                    for i,part in enumerate(parts):
                        if isinstance(part,exp.PrimaryKeyColumnConstraint):
                            table['primary_key']=names(parts[i+1]) if i+1<len(parts) else []
                        elif isinstance(part,exp.PrimaryKey):table['primary_key']=[ident(c) for c in part.expressions]
                        elif isinstance(part,exp.ForeignKey):add_fk(table,[ident(c) for c in part.expressions],part.args['reference'],constraint_name)
                        elif isinstance(part,exp.UniqueColumnConstraint) and part.this is not None:
                            table['unique'].append(names(part.this))
                        elif isinstance(part,exp.CheckColumnConstraint):table['checks'].append({'name':constraint_name,'expression':part.this.sql(dialect=dialect)})
            for col in table['columns']:
                if col['name'] in table['primary_key']:col['nullable']=False
            tables[key(table['schema'],table['name'])]=table;model['tables'].append(table)
        elif isinstance(statement,exp.Alter):
            relation=statement.this;table=find(relation.db,relation.name)
            if table is None:model['issues'].append('ALTER su tabella non dichiarata: '+relation.sql());continue
            for action in statement.args.get('actions') or []:
                parts=action.expressions if isinstance(action,exp.Constraint) else [action]
                for part in parts if not isinstance(action,exp.AddConstraint) else action.expressions:
                    inner=part.expressions if isinstance(part,exp.Constraint) else [part]
                    constraint_name=part.name if isinstance(part,exp.Constraint) else ''
                    for piece in inner:
                        if isinstance(piece,exp.ForeignKey):add_fk(table,[ident(c) for c in piece.expressions],piece.args['reference'],constraint_name)
                        elif isinstance(piece,exp.PrimaryKey):table['primary_key']=[ident(c) for c in piece.expressions]
                        elif isinstance(piece,exp.UniqueColumnConstraint) and piece.this is not None:table['unique'].append(names(piece.this))
                        elif isinstance(piece,exp.CheckColumnConstraint):table['checks'].append({'name':constraint_name,'expression':piece.this.sql(dialect=dialect)})
        elif isinstance(statement,exp.Comment):
            target=statement.this;kind=(statement.args.get('kind') or '').upper();text_value=statement.expression.name
            if kind=='TABLE':
                table=find(target.db,target.name)
                if table:table['description']=text_value
            elif kind=='COLUMN':
                parts=target.sql(dialect=dialect).replace('"','').split('.')
                table=find(parts[-3] if len(parts)>2 else '',parts[-2]) if len(parts)>1 else None
                col=next((c for c in (table or {}).get('columns',[]) if c['name'].lower()==parts[-1].lower()),None)
                if col:col['description']=text_value
        elif isinstance(statement,(exp.Create,exp.Set,exp.Command,exp.Use,exp.Drop)) or statement.key in ('select','set','transaction','commit'):
            continue
    if not model['tables']:raise ValueError('Nessuna CREATE TABLE riconosciuta nel DDL per il dialetto '+dialect)
    return model


def validate(model,*,strict_references=True):
    """Normalize a model and return it with issues; structural errors raise."""
    if not isinstance(model,dict) or not isinstance(model.get('tables'),list) or not model['tables']:
        raise ValueError('Il modello richiede almeno una tabella in "tables"')
    if len(model['tables'])>MAX_TABLES:raise ValueError('Al massimo '+str(MAX_TABLES)+' tabelle per modello')
    result={'model_version':VERSION,'name':str(model.get('name') or 'database')[:120],'description':str(model.get('description') or '')[:4000],
            'source':model.get('source') or {'kind':'documented'},'tables':[],'issues':list(model.get('issues') or [])}
    seen=set()
    for raw in model['tables']:
        if not isinstance(raw,dict) or set(raw)-TABLE_KEYS-{'definition'}:
            raise ValueError('Tabella con campi non ammessi: '+', '.join(sorted(set(raw)-TABLE_KEYS-{'definition'})) if isinstance(raw,dict) else 'Tabella non valida')
        name=raw.get('name');schema=raw.get('schema') or ''
        if not isinstance(name,str) or not NAME.fullmatch(name) or (schema and not NAME.fullmatch(schema)):raise ValueError('Nome di tabella o schema non valido: '+repr(name))
        if key(schema,name) in seen:raise ValueError('Tabella duplicata: '+schema+'.'+name)
        seen.add(key(schema,name))
        columns=raw.get('columns') or []
        if not columns and raw.get('kind')!='view':raise ValueError(name+': nessuna colonna')
        if len(columns)>MAX_COLUMNS:raise ValueError(name+': troppe colonne')
        table={'schema':schema,'name':name,'description':str(raw.get('description') or ''),'kind':raw.get('kind') or 'table','columns':[],
               'primary_key':list(raw.get('primary_key') or []),'unique':[list(u) for u in raw.get('unique') or []],
               'foreign_keys':[],'checks':[{'name':str(c.get('name') or ''),'expression':str(c['expression'])} for c in raw.get('checks') or []],
               'labels':[str(l) for l in raw.get('labels') or []]}
        for extra in ('rows','owner','grain','refresh','definition'):
            if raw.get(extra) not in (None,''):table[extra]=raw[extra]
        if 'rows' in table and (type(table['rows']) is not int or not 0<=table['rows']<=1000000):raise ValueError(name+': rows tra 0 e 1000000')
        names=set()
        for c in columns:
            if not isinstance(c,dict) or set(c)-COLUMN_KEYS:raise ValueError(name+': colonna con campi non ammessi')
            if not isinstance(c.get('name'),str) or not NAME.fullmatch(c['name']) or c['name'].lower() in names:raise ValueError(name+': colonna senza nome valido o duplicata')
            names.add(c['name'].lower())
            canonical,issue=portable_type(c.get('type') or 'TEXT')
            if issue:result['issues'].append(qualified(table)+'.'+c['name']+': '+issue)
            generator=c.get('generator') or {}
            if not isinstance(generator,dict) or set(generator)-GENERATOR_KEYS:raise ValueError(name+'.'+c['name']+': generator con chiavi '+', '.join(sorted(GENERATOR_KEYS)))
            value={'name':c['name'],'type':canonical,'nullable':bool(c.get('nullable',True)),'default':c.get('default'),'description':str(c.get('description') or ''),
                   'pii':bool(c.get('pii',False))}
            for extra in ('source_type','labels','example'):
                if c.get(extra) not in (None,'',[]):value[extra]=c[extra]
            if generator:value['generator']=generator
            table['columns'].append(value)
        lowered={c['name'].lower():c for c in table['columns']}
        for group in [table['primary_key'],*table['unique']]:
            for col in group:
                if col.lower() not in lowered:raise ValueError(qualified(table)+': la chiave usa la colonna inesistente '+col)
        for col in table['primary_key']:lowered[col.lower()]['nullable']=False
        for fk in raw.get('foreign_keys') or []:
            ref=fk.get('references') or {}
            if not fk.get('columns') or not ref.get('table'):raise ValueError(qualified(table)+': foreign key incompleta')
            missing=[c for c in fk['columns'] if c.lower() not in lowered]
            if missing:raise ValueError(qualified(table)+': foreign key su colonne inesistenti '+', '.join(missing))
            table['foreign_keys'].append({'name':str(fk.get('name') or ''),'columns':list(fk['columns']),
                'references':{'schema':ref.get('schema') if ref.get('schema') is not None else schema,'table':ref['table'],'columns':list(ref.get('columns') or [])},
                'declared':bool(fk.get('declared',True)),**({'description':fk['description']} if fk.get('description') else {})})
        result['tables'].append(table)
    index={key(t['schema'],t['name']):t for t in result['tables']}
    for table in result['tables']:
        for fk in table['foreign_keys']:
            parent=index.get(key(fk['references']['schema'],fk['references']['table'])) or index.get(key('',fk['references']['table']))
            if parent is None:
                message=qualified(table)+': riferimento a tabella assente '+fk['references']['table']
                if strict_references:raise ValueError(message)
                result['issues'].append(message);continue
            fk['references']['schema']=parent['schema']
            if not fk['references']['columns']:fk['references']['columns']=list(parent['primary_key'])
            if len(fk['references']['columns'])!=len(fk['columns']):raise ValueError(qualified(table)+': colonne della foreign key e del riferimento in numero diverso')
            parent_cols={c['name'].lower() for c in parent['columns']}
            if any(c.lower() not in parent_cols for c in fk['references']['columns']):raise ValueError(qualified(table)+': il riferimento usa colonne inesistenti in '+qualified(parent))
    result['issues']=list(dict.fromkeys(result['issues']))
    return result


def merge(model,overrides):
    """Apply documentation: descriptions, labels, PII, virtual relations and stub hints, never silent structure changes."""
    model=copy.deepcopy(model);notes=[]
    index={key(t['schema'],t['name']):t for t in model['tables']}
    for field in ('name','description'):
        if overrides.get(field):model[field]=overrides[field]
    for raw in overrides.get('tables') or []:
        table=index.get(key(raw.get('schema') or '',raw['name'])) or next((t for (s,n),t in index.items() if n==raw['name'].lower()),None)
        if table is None:
            if raw.get('columns'):model['tables'].append(raw);notes.append('tabella aggiunta dalla documentazione: '+raw['name']);continue
            raise ValueError('La documentazione descrive una tabella assente dallo schema: '+raw['name'])
        for field in ('description','labels','rows','owner','grain','refresh'):
            if raw.get(field) not in (None,'',[]):table[field]=raw[field]
        for fk in raw.get('foreign_keys') or []:
            table['foreign_keys'].append({**fk,'declared':False});notes.append(qualified(table)+': relazione documentata non dichiarata nel database')
        columns={c['name'].lower():c for c in table['columns']}
        for c in raw.get('columns') or []:
            target=columns.get(c['name'].lower())
            if target is None:
                if c.get('type'):table['columns'].append(c);notes.append(qualified(table)+'.'+c['name']+': colonna aggiunta dalla documentazione')
                else:raise ValueError('Colonna documentata assente: '+qualified(table)+'.'+c['name'])
                continue
            for field in ('description','pii','labels','generator','example'):
                if c.get(field) not in (None,'',[]):target[field]=c[field]
            if c.get('type') and portable_type(c['type'])[0]!=target['type']:
                notes.append(qualified(table)+'.'+c['name']+': tipo documentato '+c['type']+' diverso dal tipo osservato '+target['type']+' (mantenuto quello osservato)')
    model['issues']=list(model.get('issues') or [])+notes
    return model


def order(model):
    """Parents before children; cycles return the edges to add after creation."""
    index={key(t['schema'],t['name']):t for t in model['tables']};done=[];state={};deferred=[]
    def visit(k,path):
        if state.get(k)=='done':return
        state[k]='active'
        for fk in index[k]['foreign_keys']:
            parent=key(fk['references']['schema'],fk['references']['table'])
            if parent not in index or parent==k:continue
            if state.get(parent)=='active':deferred.append((k,fk));continue
            visit(parent,path+[k])
        state[k]='done';done.append(index[k])
    for k in index:visit(k,[])
    return done,deferred


def quote(name,target):
    from sqlglot import exp
    return exp.to_identifier(name,quoted=True).sql(dialect=target)


def ref(table,target):
    if target=='sqlite' or not table.get('schema'):return quote(table['name'],target)
    return quote(table['schema'],target)+'.'+quote(table['name'],target)


def ddl(model,target,*,schemas=True,comments=True):
    """DDL for one engine plus the list of structures it cannot enforce."""
    if target not in TARGETS:raise ValueError('Dialetto di destinazione tra '+', '.join(TARGETS))
    from sqlglot import exp
    module=sqlglot();lines=['-- Generated by RigHaven from model "'+model['name']+'" for '+target+'. Review before running on a shared server.'];limits=[]
    ordered,deferred=order(model)
    deferred_ids={id(fk) for _,fk in deferred}
    if schemas and target!='sqlite':
        for schema in sorted({t['schema'] for t in model['tables'] if t['schema']}):
            if target in ('tsql','fabric'):lines.append("IF SCHEMA_ID('"+schema+"') IS NULL EXEC('CREATE SCHEMA "+quote(schema,target)+"');")
            elif target=='oracle':limits.append('Oracle: lo schema '+schema+' corrisponde a un utente da creare separatamente')
            elif target=='mysql':lines.append('CREATE DATABASE IF NOT EXISTS '+quote(schema,target)+';')
            else:lines.append('CREATE SCHEMA IF NOT EXISTS '+quote(schema,target)+';')
    enforce_keys=target!='fabric'
    if not enforce_keys:limits.append('Fabric Warehouse: chiavi, vincoli CHECK e valori DEFAULT non sono applicati; restano come commenti e vanno coperti dagli audit')
    for table in ordered:
        if table.get('kind')=='view':
            if table.get('definition'):
                try:body=module.transpile(table['definition'],read=model['source'].get('dialect') or None,write=target)[0]
                except Exception:body=None
                if body:lines.append('CREATE VIEW '+ref(table,target)+' AS '+body+';')
                else:limits.append(qualified(table)+': vista non traducibile automaticamente')
            else:limits.append(qualified(table)+': vista senza definizione, non creata')
            continue
        parts=[]
        for c in table['columns']:
            data_type=exp.DataType.build(c['type']).sql(dialect=target)
            if target=='fabric':data_type=re.sub(r'^(N?VARCHAR)\(MAX\)$',r'\1(8000)',data_type)
            if target=='duckdb':data_type=re.sub(r'^TEXT\(.*\)$','TEXT',data_type)
            part=quote(c['name'],target)+' '+data_type+('' if c['nullable'] else ' NOT NULL')
            if c.get('default') not in (None,'') and target!='fabric':
                try:
                    default=module.transpile(str(c['default']),read=model['source'].get('dialect') or None,write=target)[0]
                    if target=='tsql':default={'(1 = 0)':'0','(1 = 1)':'1'}.get(default,default)
                    part+=' DEFAULT '+default
                except Exception:limits.append(qualified(table)+'.'+c['name']+': default non traducibile omesso')
            parts.append(part)
        constraint=lambda body:('-- ' if not enforce_keys else '')+body
        if table['primary_key']:parts.append(constraint('PRIMARY KEY ('+', '.join(quote(c,target) for c in table['primary_key'])+')'))
        for group in table['unique']:parts.append(constraint('UNIQUE ('+', '.join(quote(c,target) for c in group)+')'))
        index={key(t['schema'],t['name']):t for t in model['tables']}
        for fk in table['foreign_keys']:
            parent=index.get(key(fk['references']['schema'],fk['references']['table']))
            if parent is None or not fk.get('declared',True) or id(fk) in deferred_ids:continue
            if target=='duckdb' and parent is table:
                limits.append(qualified(table)+': DuckDB non supporta foreign key verso la stessa tabella; relazione documentata');continue
            parts.append(constraint('FOREIGN KEY ('+', '.join(quote(c,target) for c in fk['columns'])+') REFERENCES '+ref(parent,target)+' ('+', '.join(quote(c,target) for c in fk['references']['columns'])+')'))
        for check in table['checks']:
            try:parts.append(constraint('CHECK ('+module.transpile(check['expression'],read=model['source'].get('dialect') or None,write=target)[0]+')'))
            except Exception:limits.append(qualified(table)+': vincolo CHECK non traducibile omesso')
        rendered=[]
        for i,p in enumerate(parts):
            last=i==len(parts)-1 or all(q.startswith('--') for q in parts[i+1:])
            rendered.append('  '+p+('' if last or p.startswith('--') else ','))
        lines.append('CREATE TABLE '+ref(table,target)+' (\n'+'\n'.join(rendered)+'\n);')
        if comments and target in ('postgres','oracle','duckdb'):
            if table['description']:lines.append('COMMENT ON TABLE '+ref(table,target)+' IS '+exp.Literal.string(table['description'][:2000]).sql(dialect=target)+';')
            for c in table['columns']:
                if c.get('description'):lines.append('COMMENT ON COLUMN '+ref(table,target)+'.'+quote(c['name'],target)+' IS '+exp.Literal.string(c['description'][:2000]).sql(dialect=target)+';')
    for table,fk in deferred:
        child={key(t['schema'],t['name']):t for t in model['tables']}[table]
        parent={key(t['schema'],t['name']):t for t in model['tables']}.get(key(fk['references']['schema'],fk['references']['table']))
        if target in ('duckdb','sqlite','fabric'):
            limits.append(qualified(child)+': foreign key ciclica verso '+qualified(parent)+' non applicabile con '+target+'; documentata');continue
        lines.append('ALTER TABLE '+ref(child,target)+' ADD FOREIGN KEY ('+', '.join(quote(c,target) for c in fk['columns'])+') REFERENCES '+ref(parent,target)+' ('+', '.join(quote(c,target) for c in fk['references']['columns'])+');')
    if any(not fk.get('declared',True) for t in model['tables'] for fk in t['foreign_keys']):
        limits.append('Le relazioni documentate ma non dichiarate nel database non sono create come vincoli: restano nel catalogo e nei test')
    text='\n\n'.join(lines)+'\n'
    return text,limits


def verify_ddl(text,target):
    """Re-parse every generated statement with the target dialect; return how many parsed."""
    module=sqlglot();count=0
    for chunk in text.split(';\n\n'):
        body=re.sub(r'(?m)^\s*--.*$','',chunk).strip().rstrip(';')
        if not body:continue
        try:parsed=[s for s in module.parse(body,read=target) if s is not None]
        except Exception as error:raise ValueError('DDL generato non rileggibile in '+target+': '+body.splitlines()[0][:100]+' ('+str(error).splitlines()[0][:120]+')')
        if not parsed:raise ValueError('DDL generato vuoto in '+target+': '+body[:100])
        count+=1
    return count


def summary(model):
    tables=[t for t in model['tables']]
    columns=sum(len(t['columns']) for t in tables)
    described=sum(1 for t in tables for c in t['columns'] if c.get('description'))
    return {'tables':len(tables),'columns':columns,'foreign_keys':sum(len(t['foreign_keys']) for t in tables),
            'documented_relations':sum(1 for t in tables for fk in t['foreign_keys'] if not fk.get('declared',True)),
            'pii_columns':sum(1 for t in tables for c in t['columns'] if c.get('pii')),
            'table_description_coverage':round(sum(1 for t in tables if t['description'])/len(tables),3) if tables else 0,
            'column_description_coverage':round(described/columns,3) if columns else 0,'issues':len(model.get('issues') or [])}


def load(path):
    path=Path(path);text=path.read_text()
    if path.suffix.lower() in ('.yaml','.yml'):
        import yaml
        return yaml.safe_load(text)
    return json.loads(text)
