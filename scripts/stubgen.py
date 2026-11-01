#!/usr/bin/env python3
"""Deterministic, foreign-key consistent stub data from a RigHaven schema model.

Every row is a pure function of (seed, table, batch, row): a child row can
reference any parent row of the same or an earlier batch without storing keys,
and re-running a batch reproduces identical files. Periodic runs use increasing
batch numbers; dates move forward one period per batch. Values are synthetic:
columns marked as personal data are always fake.

Requires Faker and DuckDB. Usage:
  stubgen.py --model model.json --output DIR [--database stub.duckdb] [--batch N|auto]
             [--rows N] [--seed N] [--locale it_IT] [--formats duckdb,parquet,csv,jsonl,xml]
"""
import argparse,csv,datetime as dt,decimal,hashlib,json,random,re,shutil,sys,uuid
from pathlib import Path
from xml.sax.saxutils import escape

ANCHOR=dt.datetime(2026,1,1,8,0,0)
META_TABLE='_righaven_stub_batches'
NULL='\\N'
FORMATS=('duckdb','parquet','csv','jsonl','xml')
MAX_ROWS=100000


def stable(*parts):
    return int.from_bytes(hashlib.sha256('\x1f'.join(map(str,parts)).encode()).digest()[:8],'big')


def qualified(table):
    return (table['schema']+'.' if table.get('schema') else '')+table['name']


def tkey(schema,name):
    return ((schema or '').lower(),name.lower())


def base_type(text):
    match=re.match(r'\s*([A-Za-z ]+?)\s*(\((.*)\))?\s*$',text or 'TEXT')
    name=(match.group(1) if match else 'TEXT').upper().strip()
    params=[p.strip() for p in (match.group(3) or '').split(',') if p.strip()] if match else []
    return name,params


def order(tables):
    index={tkey(t['schema'],t['name']):t for t in tables};state={};done=[]
    def visit(k):
        if state.get(k):return
        state[k]='active'
        for fk in index[k]['foreign_keys']:
            parent=tkey(fk['references']['schema'],fk['references']['table'])
            if parent in index and parent!=k and state.get(parent)!='active':visit(parent)
        state[k]='done';done.append(index[k])
    for k in index:visit(k)
    return done


CHECK_IN=re.compile(r'^\(*\s*"?(\w+)"?\s+IN\s*\((.+)\)\s*\)*$',re.I|re.S)
CHECK_CMP=re.compile(r'^\(*\s*"?(\w+)"?\s*(>=|>|<=|<)\s*(?:CAST\(\(?)?\(?(-?\d+(?:\.\d+)?)\)?',re.I)
CHECK_BETWEEN=re.compile(r'^\(*\s*"?(\w+)"?\s+BETWEEN\s+(-?\d+(?:\.\d+)?)\s+AND\s+(-?\d+(?:\.\d+)?)',re.I)


def hints_from_checks(table):
    """Simple CHECK constraints become generator hints; anything else is reported, not guessed."""
    hints={};skipped=[]
    for check in table.get('checks') or []:
        text=check['expression'].strip()
        if (m:=CHECK_IN.match(text)):
            values=[v.strip().strip("'") for v in re.split(r",(?=(?:[^']*'[^']*')*[^']*$)",m.group(2))]
            hints.setdefault(m.group(1).lower(),{})['values']=values
        elif (m:=CHECK_BETWEEN.match(text)):
            hints.setdefault(m.group(1).lower(),{}).update(min=float(m.group(2)),max=float(m.group(3)))
        elif (m:=CHECK_CMP.match(text)):
            bound=float(m.group(3));op=m.group(2);h=hints.setdefault(m.group(1).lower(),{})
            if op in ('>=','>'):h['min']=bound+(1 if op=='>' else 0)
            else:h['max']=bound-(1 if op=='<' else 0)
        else:skipped.append(qualified(table)+': CHECK non interpretato per i dati di prova: '+text[:120])
    return hints,skipped


NAME_RULES=[
 (r'e_?mail|posta','email'),(r'telefono|phone|cellulare|mobile|tel$','phone_number'),
 (r'^(first_?name|nome|given_name)$','first_name'),(r'^(last_?name|cognome|surname|family_name)$','last_name'),
 (r'ragione_sociale|company|azienda|societa|fornitore|supplier|customer_name|cliente_nome','company'),
 (r'^(full_?name|name|nominativo|display_name)$','name'),(r'citta|city|comune|localita|town','city'),
 (r'indirizzo|address|via|street','street_address'),(r'^(cap|zip|zip_?code|postcode|postal_code)$','postcode'),
 (r'provincia|province|state','state'),(r'nazione|country|paese','country'),(r'iban','iban'),
 (r'partita_?iva|p_?iva|vat','company_vat'),(r'codice_fiscale|fiscal_?code|cod_fisc|ssn|tax_?code','ssn'),
 (r'url|website|sito','url'),(r'descrizione|description|note|notes|comment|commento','sentence'),
 (r'username|login|user_?name','user_name'),(r'job|mansione|ruolo|role','job'),(r'colore|color','color_name'),
 (r'currency|valuta','currency_code'),(r'ip(_?address)?$','ipv4'),
]
MONEY=re.compile(r'prezzo|price|importo|amount|totale|total|costo|cost|imponibile|iva_amount|saldo|balance|fee|valore|value')
QUANTITY=re.compile(r'quantita|quantity|qty|pezzi|count|numero_|num_')
STATUS=re.compile(r'^(stato|status|state_code|tipo|type|categoria|category)$')
CREATED=re.compile(r'creat|insert|registr|data_ins|inserted')
UPDATED=re.compile(r'updat|modif|changed|last_')


class Generator:
    def __init__(self,model,*,rows,seed,locale):
        from faker import Faker
        self.model=model;self.seed=seed;self.locale=locale;self.faker=Faker(locale);self.faker_en=Faker('en_US')
        self.tables={tkey(t['schema'],t['name']):t for t in model['tables'] if t.get('kind','table')=='table'}
        self.rows={k:max(1,min(MAX_ROWS,int(t.get('rows') or rows))) for k,t in self.tables.items()}
        self.issues=[];self.hints={}
        for k,t in self.tables.items():
            hints,skipped=hints_from_checks(t);self.hints[k]=hints;self.issues.extend(skipped)
        self.cache={}

    def gen_hint(self,table,column):
        hint=dict(self.hints[tkey(table['schema'],table['name'])].get(column['name'].lower(),{}))
        hint.update(column.get('generator') or {})
        return hint

    def key_value(self,table,column,batch,row):
        """Deterministic, non-overlapping identifiers per batch."""
        name,params=base_type(column['type']);index=batch*self.rows[tkey(table['schema'],table['name'])]+row
        hint=self.gen_hint(table,column)
        if name in ('UUID','UNIQUEIDENTIFIER'):return str(uuid.uuid5(uuid.NAMESPACE_URL,'righaven:'+qualified(table)+':'+str(index)))
        if self.integer(name) or name.startswith('DECIMAL') or name=='NUMERIC':return int(hint.get('start',1))+index*int(hint.get('step',1))
        prefix=re.sub(r'[^A-Z]','',table['name'].upper())[:3] or 'K'
        value=prefix+'-'+str(index+1).zfill(7)
        length=int(params[0]) if params and params[0].isdigit() else None
        if length and len(value)>length:value=str(index+1).zfill(min(length,7))[-length:]
        return value

    @staticmethod
    def integer(name):
        return name in ('INT','INTEGER','BIGINT','SMALLINT','TINYINT','HUGEINT','INT64','INT32','SERIAL','BIGSERIAL','UBIGINT','UINTEGER','USMALLINT','UTINYINT')

    def parent_row(self,parent_key,batch,row):
        k=(parent_key,batch,row)
        if k not in self.cache:
            if len(self.cache)>200000:self.cache.clear()
            self.cache[k]=self.row(self.tables[parent_key],batch,row)
        return self.cache[k]

    def row(self,table,batch,row):
        k=tkey(table['schema'],table['name'])
        rng=random.Random(stable(self.seed,qualified(table),batch,row))
        self.faker.seed_instance(stable(self.seed,qualified(table),batch,row,'faker'))
        values={};pk={c.lower() for c in table['primary_key']}
        fk_columns={}
        for fk in table['foreign_keys']:
            parent=tkey(fk['references']['schema'],fk['references']['table'])
            if parent not in self.tables:continue
            for child,parent_column in zip(fk['columns'],fk['references']['columns']):fk_columns[child.lower()]=(fk,parent,parent_column)
        chosen={}
        for column in table['columns']:
            lowered=column['name'].lower();hint=self.gen_hint(table,column)
            if lowered in fk_columns:
                fk,parent,parent_column=fk_columns[lowered]
                if parent==k:
                    if row==0 and batch==0:values[column['name']]=None if column['nullable'] else self.key_value(table,column,batch,row);continue
                    pb,pr=(batch,rng.randrange(row)) if row else (rng.randrange(batch),rng.randrange(self.rows[k]))
                    values[column['name']]=self.key_value(table,next(c for c in table['columns'] if c['name'].lower()==parent_column.lower()),pb,pr) if parent_column.lower() in {c.lower() for c in table['primary_key']} else None
                    continue
                if column['nullable'] and rng.random()<float(hint.get('null_ratio',0.05)):values[column['name']]=None;continue
                if id(fk) not in chosen:
                    pb=rng.choice(self.available.get(parent) or [batch])
                    chosen[id(fk)]=self.parent_row(parent,pb,rng.randrange(self.rows[parent]))
                parent_values=chosen[id(fk)];values[column['name']]=next(v for n,v in parent_values.items() if n.lower()==parent_column.lower())
                continue
            if lowered in pk and len(table['primary_key'])==1:values[column['name']]=self.key_value(table,column,batch,row);continue
            unique=any(len(u)==1 and u[0].lower()==lowered for u in table['unique'])
            values[column['name']]=self.value(table,column,hint,rng,batch,row,unique=unique)
        return values

    def value(self,table,column,hint,rng,batch,row,*,unique=False):
        name,params=base_type(column['type']);lowered=column['name'].lower()
        if 'constant' in hint:return hint['constant']
        if column['nullable'] and not unique and rng.random()<float(hint.get('null_ratio',0.08 if not column.get('pii') else 0.02)):return None
        if hint.get('values'):
            weights=hint.get('weights')
            choice=rng.choices(hint['values'],weights=weights)[0] if weights else rng.choice(hint['values'])
            return self.cast(choice,name)
        if hint.get('pattern'):return self.faker.bothify(hint['pattern'])
        if hint.get('faker'):
            provider=getattr(self.faker,hint['faker'],None) or getattr(self.faker_en,hint['faker'],None)
            if provider is None:raise ValueError(qualified(table)+'.'+column['name']+': provider Faker sconosciuto '+hint['faker'])
            return self.fit(provider(),name,params,unique,batch,row)
        if self.integer(name):
            low=int(hint.get('min',1 if QUANTITY.search(lowered) else 0));high=int(hint.get('max',50 if QUANTITY.search(lowered) else 100000))
            if name in ('SMALLINT',):high=min(high,32767)
            if name in ('TINYINT','UTINYINT'):high=min(high,127)
            return batch*1000003+row if unique else rng.randint(low,max(low,high))
        if name in ('DECIMAL','NUMERIC','NUMBER','MONEY','SMALLMONEY'):
            precision=int(params[0]) if params else 18;scale=int(params[1]) if len(params)>1 else 0
            ceiling=min(10**(precision-scale)-1,float(hint.get('max',5000 if MONEY.search(lowered) else 100000)))
            low=float(hint.get('min',0.01 if MONEY.search(lowered) else 0))
            amount=decimal.Decimal(str(round(rng.uniform(low,max(low,ceiling)),scale)))
            return str(amount.quantize(decimal.Decimal(1).scaleb(-scale))) if scale else str(int(amount))
        if name in ('FLOAT','DOUBLE','REAL','DOUBLE PRECISION','FLOAT4','FLOAT8'):
            return round(rng.uniform(float(hint.get('min',0)),float(hint.get('max',1000))),int(hint.get('decimals',4)))
        if name in ('BOOLEAN','BOOL','BIT'):return rng.random()<0.5
        if name in ('DATE',):return self.moment(lowered,hint,rng,batch).date().isoformat()
        if name.startswith('TIMESTAMP') or name in ('DATETIME','DATETIME2','SMALLDATETIME','DATETIMEOFFSET','TIMESTAMPTZ','TIMESTAMPNTZ'):
            moment=self.moment(lowered,hint,rng,batch)
            return moment.isoformat(sep=' ')+('+00:00' if name in ('TIMESTAMPTZ','DATETIMEOFFSET') or 'TIME ZONE' in name else '')
        if name in ('TIME',):return (dt.datetime.min+dt.timedelta(seconds=rng.randrange(86400))).time().isoformat()
        if name in ('UUID','UNIQUEIDENTIFIER'):return str(uuid.UUID(int=rng.getrandbits(128),version=4))
        if name in ('JSON','JSONB','VARIANT'):return json.dumps({'codice':self.faker.bothify('??-###'),'valore':rng.randint(1,100)})
        if name in ('BLOB','BYTEA','VARBINARY','BINARY','IMAGE'):return None if column['nullable'] else ''
        return self.fit(self.text(lowered,rng,column),name,params,unique,batch,row)

    def text(self,lowered,rng,column):
        for pattern,provider in NAME_RULES:
            if re.search(pattern,lowered):
                function=getattr(self.faker,provider,None) or getattr(self.faker_en,provider,None)
                if function is not None:return str(function())
        if STATUS.search(lowered):return rng.choice(['attivo','sospeso','chiuso'] if self.locale=='it_IT' else ['active','suspended','closed'])
        if lowered.startswith(('cod','code','sku','ref','numero','number')):return self.faker.bothify('??-#####').upper()
        if column.get('pii'):return self.faker.name()
        return self.faker.word()

    def fit(self,value,name,params,unique,batch,row):
        text=str(value)
        if unique:text=(text.split('@')[0]+'.'+str(batch)+'.'+str(row)+'@example.org') if '@' in text else text+'-'+str(batch)+'-'+str(row)
        if params and params[0].isdigit():
            length=int(params[0])
            if len(text)>length:text=(text[:max(0,length-len(str(row))-1)]+'-'+str(row))[-length:] if unique else text[:length]
        return text

    def moment(self,lowered,hint,rng,batch):
        window_end=ANCHOR+dt.timedelta(days=batch+1)
        if UPDATED.search(lowered):start=ANCHOR+dt.timedelta(days=batch)
        elif CREATED.search(lowered):start=ANCHOR+dt.timedelta(days=batch)
        else:start=window_end-dt.timedelta(days=int(hint.get('days_back',365)))
        seconds=int((window_end-start).total_seconds())
        return (start+dt.timedelta(seconds=rng.randrange(max(1,seconds)))).replace(microsecond=0)

    @staticmethod
    def cast(value,name):
        if Generator.integer(name):return int(value)
        if name in ('BOOLEAN','BOOL','BIT'):return str(value).lower() in ('1','true','t','yes','si')
        return value

    def run(self,batch,available):
        self.available=available
        result={}
        for table in order(list(self.tables.values())):
            k=tkey(table['schema'],table['name'])
            rows=[self.row(table,batch,i) for i in range(self.rows[k])]
            seen=set();clean=[]
            for values in rows:
                identity=tuple(values[c] for c in table['primary_key']) if table['primary_key'] else None
                if identity is not None and identity in seen:continue
                if identity is not None:seen.add(identity)
                clean.append(values)
            if len(clean)<len(rows):self.issues.append(qualified(table)+': '+str(len(rows)-len(clean))+' righe scartate per chiave composta duplicata')
            result[k]=(table,clean)
        return result


def csv_value(value):
    if value is None:return NULL
    if isinstance(value,bool):return 'true' if value else 'false'
    return value


def write_files(output,data,batch,formats):
    files=[]
    for k,(table,rows) in data.items():
        folder=output/(table['schema'] or 'main');folder.mkdir(parents=True,exist_ok=True)
        stem=str(folder/(table['name']+'.batch-'+str(batch).zfill(5)))
        path=Path(stem+'.csv')
        with path.open('w',newline='') as stream:
            writer=csv.writer(stream);writer.writerow([c['name'] for c in table['columns']])
            for values in rows:writer.writerow([csv_value(values[c['name']]) for c in table['columns']])
        files.append(path)
        if 'jsonl' in formats:
            target=Path(stem+'.jsonl');target.write_text(''.join(json.dumps(r,ensure_ascii=False,default=str)+'\n' for r in rows));files.append(target)
        if 'xml' in formats:
            target=Path(stem+'.xml');tag=re.sub(r'\W','_',table['name'])
            lines=['<?xml version="1.0" encoding="UTF-8"?>','<'+tag+'_records batch="'+str(batch)+'">']
            for values in rows:
                fields=''.join('<'+re.sub(r'\W','_',n)+('/>' if v is None else '>'+escape(str(v))+'</'+re.sub(r'\W','_',n)+'>') for n,v in values.items())
                lines.append('  <'+tag+'>'+fields+'</'+tag+'>')
            lines.append('</'+tag+'_records>');target.write_text('\n'.join(lines)+'\n');files.append(target)
    return files


def duck_type(text):
    return 'VARCHAR' if not text else text


def load_duckdb(database,data,batch,output,formats):
    import duckdb
    con=duckdb.connect(str(database))
    try:
        con.execute('CREATE TABLE IF NOT EXISTS '+META_TABLE+' (batch INTEGER, table_name VARCHAR, row_count INTEGER, generated_at TIMESTAMP)')
        if con.execute('SELECT count(*) FROM '+META_TABLE+' WHERE batch=?',[batch]).fetchone()[0]:
            raise ValueError('Il lotto '+str(batch)+' è già presente nel database di prova: usa il lotto successivo')
        con.execute('BEGIN TRANSACTION')
        exported=[]
        for k,(table,rows) in data.items():
            name=('"'+table['schema']+'".' if table['schema'] else '')+'"'+table['name']+'"'
            exists=con.execute("SELECT count(*) FROM information_schema.tables WHERE lower(table_name)=lower(?) AND lower(table_schema)=lower(?)",
                               [table['name'],table['schema'] or 'main']).fetchone()[0]
            source=(output/(table['schema'] or 'main')/(table['name']+'.batch-'+str(batch).zfill(5)+'.csv'))
            if exists:
                columns=con.execute('SELECT column_name,data_type FROM information_schema.columns WHERE lower(table_name)=lower(?) AND lower(table_schema)=lower(?) ORDER BY ordinal_position',
                                    [table['name'],table['schema'] or 'main']).fetchall()
            else:
                if table['schema']:con.execute('CREATE SCHEMA IF NOT EXISTS "'+table['schema']+'"')
                columns=[(c['name'],'VARCHAR') for c in table['columns']]
                con.execute('CREATE TABLE '+name+' ('+', '.join('"'+c+'" '+t for c,t in columns)+')')
            spec='{'+', '.join("'"+c.replace("'","''")+"': '"+t+"'" for c,t in columns)+'}'
            con.execute('INSERT INTO '+name+' SELECT * FROM read_csv(?, header=true, nullstr=?, auto_detect=false, columns='+spec+')',[str(source),NULL])
            con.execute('INSERT INTO '+META_TABLE+' VALUES (?,?,?,current_timestamp)',[batch,qualified(table),len(rows)])
            if 'parquet' in formats:
                target=Path(str(source)[:-4]+'.parquet')
                con.execute("COPY (SELECT * FROM read_csv(?, header=true, nullstr=?, auto_detect=false, columns="+spec+")) TO '"+str(target).replace("'","''")+"' (FORMAT parquet)",[str(source),NULL])
                exported.append(target)
        con.execute('COMMIT')
        counts={qualified(t):con.execute('SELECT count(*) FROM '+('"'+t['schema']+'".' if t['schema'] else '')+'"'+t['name']+'"').fetchone()[0] for t,_ in data.values()}
        return exported,counts
    except Exception:
        try:con.execute('ROLLBACK')
        except Exception:pass
        raise
    finally:con.close()


def parquet_only(output,data,batch):
    import duckdb
    con=duckdb.connect();exported=[]
    for k,(table,rows) in data.items():
        source=output/(table['schema'] or 'main')/(table['name']+'.batch-'+str(batch).zfill(5)+'.csv')
        target=Path(str(source)[:-4]+'.parquet')
        con.execute("COPY (SELECT * FROM read_csv(?, header=true, nullstr=?, all_varchar=true)) TO '"+str(target).replace("'","''")+"' (FORMAT parquet)",[str(source),NULL])
        exported.append(target)
    return exported


def existing_batches(database,tables):
    if not database or not Path(database).exists():return {}
    import duckdb
    con=duckdb.connect(str(database),read_only=True)
    try:
        present=con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name=?",[META_TABLE]).fetchone()[0]
        if not present:return {}
        rows=con.execute('SELECT table_name,batch FROM '+META_TABLE).fetchall()
    finally:con.close()
    index={qualified(t).lower():k for k,t in tables.items()};result={}
    for name,batch in rows:
        if name.lower() in index:result.setdefault(index[name.lower()],[]).append(batch)
    return {k:sorted(set(v)) for k,v in result.items()}


def generate(model,output,*,database=None,batch='auto',rows=50,seed=20260101,locale='it_IT',formats=('duckdb','csv')):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    unknown=set(formats)-set(FORMATS)
    if unknown:raise ValueError('Formati ammessi: '+', '.join(FORMATS))
    generator=Generator(model,rows=rows,seed=seed,locale=locale)
    previous=existing_batches(database,generator.tables) if 'duckdb' in formats else {}
    if batch=='auto':batch=max([b for v in previous.values() for b in v],default=-1)+1
    batch=int(batch)
    available={k:sorted(set(v)|{batch}) for k,v in previous.items()}
    for k in generator.tables:available.setdefault(k,list(range(batch+1)) if 'duckdb' not in formats else [batch])
    data=generator.run(batch,available)
    files=write_files(output,data,batch,formats);counts={}
    if 'duckdb' in formats:
        if not database:raise ValueError('Il formato duckdb richiede il database di prova (copia della replica)')
        exported,counts=load_duckdb(Path(database),data,batch,output,formats);files.extend(exported)
    elif 'parquet' in formats:
        files.extend(parquet_only(output,data,batch))
        generator.issues.append('Parquet senza database di prova: le colonne sono testuali; usa anche il formato duckdb per i tipi della replica')
    if 'csv' not in formats:
        for path in list(files):
            if path.suffix=='.csv':path.unlink();files.remove(path)
    manifest={'batch':batch,'seed':seed,'locale':locale,'rows_per_table':{qualified(t):len(r) for t,r in data.values()},
              'database_totals':counts,'formats':list(formats),
              'files':[{'path':str(p.relative_to(output)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(files)],
              'issues':generator.issues,
              'limits':['Dati sintetici: distribuzioni e correlazioni non riproducono quelle reali.',
                        'Le date avanzano di un giorno per lotto a partire dal 2026-01-01; le chiavi dei lotti non si sovrappongono.',
                        'I lotti successivi aggiungono righe; aggiornamenti e cancellazioni non sono simulati.']}
    (output/('manifest.batch-'+str(batch).zfill(5)+'.json')).write_text(json.dumps(manifest,indent=2,ensure_ascii=False))
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--model',required=True);parser.add_argument('--output',required=True);parser.add_argument('--database')
    parser.add_argument('--batch',default='auto');parser.add_argument('--rows',type=int,default=50);parser.add_argument('--seed',type=int,default=20260101)
    parser.add_argument('--locale',default='it_IT');parser.add_argument('--formats',default='duckdb,csv')
    args=parser.parse_args()
    model=json.loads(Path(args.model).read_text())
    manifest=generate(model,args.output,database=args.database,batch=args.batch if args.batch=='auto' else int(args.batch),rows=args.rows,seed=args.seed,
                      locale=args.locale,formats=tuple(f for f in args.formats.split(',') if f))
    print(json.dumps({'batch':manifest['batch'],'rows':manifest['rows_per_table'],'issues':len(manifest['issues'])},ensure_ascii=False))


if __name__=='__main__':
    try:main()
    except (ValueError,OSError) as error:print(str(error),file=sys.stderr);sys.exit(1)
