"use client";
import {useEffect,useState} from "react";

import {ConceptMap} from "@/components/workspace/concept-map";
import {fetch} from "@/core/api/fetcher";
import {getBackendBaseURL} from "@/core/config";
import {useI18n} from "@/core/i18n/hooks";

type ProviderAccess={id:string;name:string;scope:string;status:string;manage_url:string};
type Kind="postgres"|"sqlserver"|"mysql"|"oracle"|"entra";
type Test={ok:boolean;detail:string;at:string};
type Connection={id:string;kind:Kind;name:string;description?:string;host?:string;port?:number;database?:string;username?:string;tls?:boolean;read_only?:boolean;
 authentication?:"password"|"entra"|"microsoft";entra_connection?:string;tenant_id?:string;client_id?:string;cloud?:string;has_secret:boolean;tools:string[];last_test?:Test;updated_at?:string;
 mode?:"user"|"application";signed_in?:boolean;account?:string};
type SignIn={id:string;user_code:string;verification_uri:string;interval:number;status:string;detail?:string};
type Form={id:string;kind:Kind;name:string;description:string;host:string;port:string;database:string;username:string;password:string;tls:boolean;read_only:boolean;
 authentication:"password"|"entra"|"microsoft";entra_connection:string;tenant_id:string;client_id:string;client_secret:string;cloud:string;mode:"user"|"application"};

const PORTS:Record<Kind,string>={postgres:"5432",sqlserver:"1433",mysql:"3306",oracle:"1521",entra:""};
const LABELS:Record<Kind,string>={postgres:"PostgreSQL",sqlserver:"SQL Server / Azure SQL / Fabric",mysql:"MySQL / MariaDB",oracle:"Oracle",entra:"Microsoft Entra ID"};
const DEFAULT_CLIENT="04b07795-8ddb-461a-bbee-02f9e1bf7b46";
const blank=(kind:Kind):Form=>({id:"",kind,name:"",description:"",host:"",port:PORTS[kind],database:"",username:"",password:"",tls:true,read_only:false,
 authentication:kind==="sqlserver"?"microsoft":"password",entra_connection:"",tenant_id:"",client_id:"",client_secret:"",cloud:"public",mode:"user"});
const slug=(text:string)=>text.normalize("NFD").replace(/\p{M}/gu,"").toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-+|-+$/g,"").replace(/^([^a-z])/,"c-$1").slice(0,40);

/** Personal database and Microsoft cloud connections; secrets are encrypted and never shown again. */
export default function ConnectionsPage(){
 const {locale}=useI18n();const it=locale==="it-IT";const t=(a:string,b:string)=>it?a:b;
 const base=getBackendBaseURL()+"/api/harness/connections";
 const [rows,setRows]=useState<Connection[]|null>(null),[form,setForm]=useState<Form|null>(null),[editing,setEditing]=useState<string|null>(null);
 const [error,setError]=useState(""),[notice,setNotice]=useState(""),[busy,setBusy]=useState(""),[reload,setReload]=useState(0),[deleting,setDeleting]=useState("");
 useEffect(()=>{let live=true;
  void fetch(base).then(async r=>{const v=await r.json();if(!r.ok)throw Error(typeof v.detail==="string"?v.detail:String(r.status));return v.connections as Connection[];})
   .then(v=>{if(live)setRows(v);}).catch(e=>{if(live)setError(e instanceof Error?e.message:String(e));});
  return()=>{live=false;};},[base,reload]);
 const [providers,setProviders]=useState<ProviderAccess[]>([]);
 useEffect(()=>{let live=true;void fetch(`${getBackendBaseURL()}/api/harness/access-catalog`).then(async r=>{if(!r.ok)throw Error(String(r.status));return r.json() as Promise<{providers:ProviderAccess[]}>;}).then(v=>{if(live)setProviders(v.providers);}).catch(()=>undefined);return()=>{live=false;};},[]);
 const entras=(rows??[]).filter(r=>r.kind==="entra");
 function edit(row:Connection){setEditing(row.id);setNotice("");setError("");
  setForm({...blank(row.kind),...Object.fromEntries(Object.entries(row).filter(([,v])=>typeof v==="string"||typeof v==="boolean")),port:String(row.port??PORTS[row.kind]),password:"",client_secret:""} as Form);}
 async function save(){if(!form)return;setBusy("save");setError("");setNotice("");
  const body:Record<string,unknown>={kind:form.kind,name:form.name,description:form.description};
  if(!editing)body.id=form.id||slug(form.name);
  if(form.kind==="entra")Object.assign(body,{mode:form.mode,tenant_id:form.tenant_id,client_id:form.mode==="user"&&form.client_id===DEFAULT_CLIENT?"":form.client_id,cloud:form.cloud,...(form.mode==="application"&&form.client_secret?{client_secret:form.client_secret}:{})});
  else Object.assign(body,{host:form.host,port:Number(form.port),database:form.database,tls:form.tls,read_only:form.read_only,
   authentication:form.kind==="sqlserver"?form.authentication:"password",
   ...(form.authentication==="entra"&&form.kind==="sqlserver"?{entra_connection:form.entra_connection}
    :form.authentication==="microsoft"&&form.kind==="sqlserver"?{username:form.username,tenant_id:form.tenant_id}
    :{username:form.username,...(form.password?{password:form.password}:{})})});
  const r=await fetch(editing?`${base}/${editing}`:base,{method:editing?"PUT":"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const v=await r.json();setBusy("");
  if(!r.ok){setError(typeof v.detail==="string"?v.detail:String(r.status));return;}
  setForm(null);setEditing(null);setNotice((form.kind==="entra"&&form.mode==="user")||(form.kind==="sqlserver"&&form.authentication==="microsoft")?t("Account salvato. Usa «Accedi con Microsoft» per completare l’accesso, anche con autenticazione a più fattori.","Account saved. Use “Sign in with Microsoft” to complete the sign-in, including multi-factor authentication."):t("Connessione salvata. Usa «Prova» per verificarla.","Connection saved. Use “Test” to check it."));setReload(n=>n+1);}
 const [signIn,setSignIn]=useState<SignIn|null>(null);
 async function startSignIn(id:string){setError("");setBusy("signin-"+id);try{const r=await fetch(`${base}/${id}/sign-in`,{method:"POST"});const v=await r.json();if(!r.ok)throw Error(typeof v.detail==="string"?v.detail:String(r.status));
  setSignIn({id,user_code:v.user_code,verification_uri:v.verification_uri,interval:v.interval??5,status:"pending"});}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy("");}}
 const [catalog,setCatalog]=useState<{id:string;rows:{name:string;detail:string}[]|null}|null>(null);
 async function listDatabases(row:Connection){setError("");setBusy("db-"+row.id);setCatalog({id:row.id,rows:null});try{const r=await fetch(`${base}/${row.id}/databases`,{method:"POST"});const v=await r.json();
  if(!r.ok)throw Error(typeof v.detail==="string"?v.detail:String(r.status));setCatalog({id:row.id,rows:v.databases});}catch(e){setCatalog(null);setError(e instanceof Error?e.message:String(e));}finally{setBusy("");}}
 async function selectDatabase(row:Connection,database:string){setError("");
  const body={kind:row.kind,name:row.name,description:row.description??"",host:row.host,port:row.port,database,tls:row.tls,read_only:row.read_only,authentication:row.authentication,
   ...(row.authentication==="microsoft"?{username:row.username,tenant_id:row.tenant_id}:{entra_connection:row.entra_connection})};
  const r=await fetch(`${base}/${row.id}`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});const v=await r.json();
  if(!r.ok){setError(typeof v.detail==="string"?v.detail:String(r.status));return;}setNotice(t(`Database «${database}» scelto per ${row.name}.`,`Database “${database}” chosen for ${row.name}.`));setReload(n=>n+1);}
 async function signOut(id:string){const r=await fetch(`${base}/${id}/sign-in`,{method:"DELETE"});const v=await r.json();if(!r.ok){setError(typeof v.detail==="string"?v.detail:String(r.status));return;}setReload(n=>n+1);}
 // Microsoft asks clients to poll at the given interval until the user completes the sign-in in their browser.
 useEffect(()=>{if(signIn?.status!=="pending")return;let live=true;const timer=setTimeout(()=>{void fetch(`${base}/${signIn.id}/sign-in/poll`,{method:"POST"}).then(async r=>{const v=await r.json() as {status:string;interval?:number;detail?:string;account?:string};if(!live)return;
   if(!r.ok){setSignIn(s=>s&&{...s,status:"failed",detail:typeof v.detail==="string"?v.detail:String(r.status)});return;}
   setSignIn(s=>s&&{...s,status:v.status,interval:v.interval??s.interval,detail:v.detail??v.account});if(v.status==="signed_in")setReload(n=>n+1);}).catch(()=>undefined);},signIn.interval*1000);
  return()=>{live=false;clearTimeout(timer);};},[signIn,base]);
 async function test(id:string){setBusy(id);setError("");const r=await fetch(`${base}/${id}/test`,{method:"POST"});const v=await r.json();setBusy("");
  if(!r.ok){setError(typeof v.detail==="string"?v.detail:String(r.status));return;}setReload(n=>n+1);}
 async function remove(id:string){if(deleting!==id){setDeleting(id);return;}setDeleting("");
  const r=await fetch(`${base}/${id}`,{method:"DELETE"});const v=await r.json();if(!r.ok){setError(typeof v.detail==="string"?v.detail:String(r.status));return;}setReload(n=>n+1);}
 const field="mt-1 w-full rounded border bg-background p-2 text-sm";
 const input=(key:keyof Form,label:string,props:Record<string,unknown>={})=><label className="block text-sm">{label}
  <input className={field} value={String(form?.[key]??"")} onChange={e=>setForm(f=>f&&{...f,[key]:e.target.value})} {...props}/></label>;
 return <div className="mx-auto w-full max-w-5xl space-y-6 p-6">
  <header className="space-y-2"><h1 className="text-2xl font-semibold">{t("Connessioni e accessi","Connections & access")}</h1>
   <p className="text-muted-foreground text-sm">{t(
    "Registra qui i database e gli account Microsoft che i lavori possono usare. Le password e i segreti sono cifrati, non vengono più mostrati e non arrivano mai al coordinatore. Sei tu a decidere l’accesso: in un lavoro scegli le connessioni dal pannello del progetto («Connessioni del lavoro»); solo i ruoli che dichiarano gli ID autorizzati le ricevono e le perdono quando finiscono.",
    "Register here the databases and Microsoft accounts that tasks may use. Passwords and secrets are encrypted, never shown again and never reach the coordinator. Access is your choice: in a task you pick the connections from the project panel (“Task connections”); only roles declaring the authorized IDs receive them, and lose them when they end.")}</p>
   <p className="text-muted-foreground text-sm">{t(
    "Usa account in sola lettura: gli strumenti RigHaven eseguono solo letture e rifiutano i database non dichiarati in sola lettura. Per Azure SQL e Microsoft Fabric aggiungi prima il tuo account Microsoft (accesso con autenticazione a più fattori, consigliato) oppure un’applicazione Entra ID, poi una connessione SQL Server che lo usa.",
    "Use read-only accounts: RigHaven tools only read and refuse databases not declared read-only. For Azure SQL and Microsoft Fabric first add your Microsoft account (sign-in with multi-factor authentication, recommended) or an Entra ID application, then a SQL Server connection that uses it.")}</p>
  </header>
  <ConceptMap current="connection"/>
  {error&&<p className="text-destructive text-sm" role="alert">{error}</p>}
  {notice&&<p className="text-sm">{notice}</p>}
  <section className="space-y-3 rounded-xl border p-4" data-testid="model-accesses"><h2 className="font-semibold">{t("Modelli e CLI ufficiali","Models and official CLIs")}</h2><p className="text-sm">{t("Gli stessi collegamenti di Modelli e risorse: nessun secondo login. Il modello rimane assegnabile al coordinatore, alla squadra o a entrambi. Gli accessi condivisi sono gestiti dall’amministratore.","The same connections as Models & resources: no duplicate login. Models remain assignable to coordinator, team or both. Shared connections are managed by the administrator.")}</p><ul className="space-y-2">{providers.map(p=><li key={p.id} className="flex flex-wrap justify-between gap-2"><span>{p.name} · {p.status==="configured"?t("Configurato","Configured"):t("Verifica in Modelli","Check Models")}</span><a className="underline" href={p.manage_url}>{t("Apri configurazione","Open configuration")}</a></li>)}</ul></section>
  <p className="text-sm">{t("Database e identità esterne sono facoltativi. Per analizzare documenti e creare il laboratorio sintetico non devi configurarli.","External databases and identities are optional. You do not need to configure them to analyze documents and build the synthetic laboratory.")}</p>
  {!form&&<div className="flex flex-wrap gap-2">{(["postgres","sqlserver","mysql","oracle","entra"] as Kind[]).map(k=><button key={k} className="rounded border px-3 py-2 text-sm" onClick={()=>{setEditing(null);setForm(blank(k));}}>{t("Nuova: ","New: ")}{LABELS[k]}</button>)}</div>}
  {form&&<section className="space-y-3 rounded-lg border p-4" data-testid="connection-form">
   <h2 className="font-semibold">{editing?t("Modifica ","Edit ")+editing:t("Nuova connessione ","New connection ")}· {LABELS[form.kind]}</h2>
   <div className="grid gap-3 md:grid-cols-2">
    {input("name",t("Nome","Name"),{placeholder:t("es. ERP vendite (lettura)","e.g. Sales ERP (read)")})}
    {!editing&&input("id",t("ID (facoltativo)","ID (optional)"),{placeholder:slug(form.name)||"erp-vendite"})}
    {input("description",t("Descrizione","Description"))}
    {form.kind==="entra"?<>
     <label className="block text-sm md:col-span-2">{t("Tipo di accesso","Access type")}<select className={field} aria-label={t("Tipo di accesso","Access type")} value={form.mode} onChange={e=>setForm(f=>f&&{...f,mode:e.target.value as "user"|"application"})}>
      <option value="user">{t("Il mio account Microsoft (OAuth2, con MFA) · consigliato","My Microsoft account (OAuth2, with MFA) · recommended")}</option>
      <option value="application">{t("Applicazione Entra ID (service principal, segreto client)","Entra ID application (service principal, client secret)")}</option></select></label>
     {form.mode==="user"?<>
      <p className="text-muted-foreground text-xs md:col-span-2">{t("Dopo il salvataggio premi «Accedi con Microsoft»: si apre la pagina Microsoft dove inserisci un codice e completi password e autenticazione a più fattori. RigHaven conserva solo il token di rinnovo cifrato; gli incarichi ricevono token di accesso temporanei con i tuoi permessi sul database. Se l’organizzazione blocca questo tipo di accesso (AADSTS53003), chiedi all’amministratore di consentirlo o usa un’applicazione.","After saving press “Sign in with Microsoft”: Microsoft’s page opens, you enter a code and complete password and multi-factor authentication. RigHaven keeps only the encrypted refresh token; assignments receive temporary access tokens with your database permissions. If your organization blocks this sign-in type (AADSTS53003), ask the administrator to allow it or use an application.")}</p>
      {input("tenant_id",t("Tenant (facoltativo: dominio o ID directory)","Tenant (optional: domain or directory ID)"),{placeholder:"organizations"})}
      {input("client_id",t("ID client pubblico (facoltativo)","Public client ID (optional)"),{placeholder:DEFAULT_CLIENT})}
     </>:<>
      {input("tenant_id",t("Tenant (ID directory o dominio)","Tenant (directory ID or domain)"),{placeholder:"contoso.onmicrosoft.com"})}
      {input("client_id",t("ID applicazione (client)","Application (client) ID"),{placeholder:"00000000-0000-0000-0000-000000000000"})}
      {input("client_secret",t("Segreto client","Client secret")+(editing?t(" (vuoto = invariato)"," (empty = unchanged)"):""),{type:"password",autoComplete:"new-password"})}
     </>}
     <label className="block text-sm">{t("Cloud","Cloud")}<select className={field} value={form.cloud} onChange={e=>setForm(f=>f&&{...f,cloud:e.target.value})}>
      <option value="public">{t("Globale","Global")}</option><option value="usgov">US Government</option><option value="china">{t("Cina (21Vianet)","China (21Vianet)")}</option></select></label>
    </>:<>
     {form.kind==="sqlserver"&&<label className="block text-sm md:col-span-2">{t("Autenticazione","Authentication")}<select className={field} aria-label={t("Autenticazione","Authentication")} value={form.authentication} onChange={e=>setForm(f=>f&&{...f,authentication:e.target.value as "password"|"entra"|"microsoft"})}>
      <option value="microsoft">{t("Il mio account Microsoft (Azure SQL, Fabric · con MFA)","My Microsoft account (Azure SQL, Fabric · with MFA)")}</option>
      <option value="password">{t("Utente e password SQL","SQL user and password")}</option>
      <option value="entra">{t("Applicazione o account Entra ID già registrato","Entra ID application or account already registered")}</option></select></label>}
     {input("host",t("Server, URL o stringa di connessione","Server, URL or connection string"),{placeholder:form.kind==="sqlserver"?"vendite.database.windows.net · Server=tcp:…;Initial Catalog=…":"db.example.com · postgresql://utente@db.example.com:5432/vendite"})}
     {input("port",t("Porta","Port"),{inputMode:"numeric"})}
     {input("database",form.kind==="oracle"?t("Nome del servizio (service name)","Service name"):form.authentication==="microsoft"&&form.kind==="sqlserver"?t("Database (facoltativo: lo scegli dall’elenco dopo l’accesso)","Database (optional: pick it from the list after signing in)"):t("Database","Database"))}
     {form.kind==="sqlserver"&&form.authentication==="microsoft"&&<>
      {input("username",t("Utente (email dell’account Microsoft)","User (Microsoft account email)"),{placeholder:"nome.cognome@azienda.it",autoComplete:"username"})}
      {input("tenant_id",t("Tenant (facoltativo)","Tenant (optional)"),{placeholder:"organizations"})}
      <p className="text-muted-foreground text-xs md:col-span-2">{t("Puoi incollare l’URL o la stringa di connessione copiata dal portale Azure o da Fabric: server, porta, database e utente vengono letti da lì. Dopo il salvataggio premi «Accedi con Microsoft» e poi «Elenca database».","You can paste the URL or connection string copied from the Azure portal or Fabric: server, port, database and user are read from it. After saving press “Sign in with Microsoft”, then “List databases”.")}</p></>}
     {form.kind==="sqlserver"&&form.authentication==="entra"?<label className="block text-sm">{t("Account o applicazione Entra ID","Entra ID account or application")}<select className={field} value={form.entra_connection} onChange={e=>setForm(f=>f&&{...f,entra_connection:e.target.value})}>
       <option value="">{t("Scegli…","Choose…")}</option>{entras.map(e=><option key={e.id} value={e.id}>{e.name} · {e.mode==="user"?(e.account??t("account da collegare","account to sign in")):t("applicazione","application")}</option>)}</select>
       {entras.length===0&&<span className="text-muted-foreground text-xs">{t("Aggiungi prima il tuo account Microsoft (Nuova: Microsoft Entra ID).","Add your Microsoft account first (New: Microsoft Entra ID).")}</span>}</label>
     :form.kind==="sqlserver"&&form.authentication==="microsoft"?null:<>{input("username",t("Utente","User"))}{input("password",t("Password","Password")+(editing?t(" (vuota = invariata)"," (empty = unchanged)"):""),{type:"password",autoComplete:"new-password"})}</>}
     <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.tls} onChange={e=>setForm(f=>f&&{...f,tls:e.target.checked})}/>{t("Connessione cifrata (TLS)","Encrypted connection (TLS)")}</label>
     <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.read_only} onChange={e=>setForm(f=>f&&{...f,read_only:e.target.checked})}/>{t("Confermo che l’account ha solo permessi di lettura","I confirm the account has read-only permissions")}</label>
    </>}
   </div>
   <div className="flex gap-2"><button className="bg-primary text-primary-foreground rounded px-3 py-2 text-sm disabled:opacity-50" disabled={busy==="save"} onClick={()=>void save()}>{t("Salva","Save")}</button>
    <button className="rounded border px-3 py-2 text-sm" onClick={()=>{setForm(null);setEditing(null);}}>{t("Annulla","Cancel")}</button></div>
  </section>}
  {rows===null&&!error&&<p className="text-sm">{t("Caricamento…","Loading…")}</p>}
  {rows?.length===0&&!form&&<p className="text-sm">{t("Nessuna connessione registrata.","No connections registered.")}</p>}
  <ul className="space-y-3">{rows?.map(r=><li key={r.id} className="rounded-lg border p-4 text-sm" data-testid={"connection-"+r.id}>
   <div className="flex flex-wrap items-start justify-between gap-2">
    <div className="min-w-0 break-words [overflow-wrap:anywhere]"><p className="font-semibold">{r.name} <span className="text-muted-foreground font-normal">· {LABELS[r.kind]} · {r.id}</span></p>
     <p className="text-muted-foreground">{r.kind==="entra"?(r.mode==="user"?(r.signed_in?t("Account ","Account ")+(r.account??""):t("Accesso Microsoft da completare","Microsoft sign-in to complete"))+" · "+t("tenant ","tenant ")+r.tenant_id:t("Applicazione · tenant ","Application · tenant ")+r.tenant_id+" · "+t("app ","app ")+r.client_id):(r.host??"")+":"+String(r.port??"")+" / "+(r.database??"")+(r.authentication==="entra"?" · Entra ID ("+(r.entra_connection??"")+")":" · "+(r.username??""))+(r.authentication==="microsoft"?" · "+(r.signed_in?t("accesso Microsoft attivo","Microsoft signed in"):t("accesso Microsoft da completare","Microsoft sign-in to complete")):"")}</p>
     {r.kind!=="entra"&&<p className={r.read_only?"":"text-destructive"}>{r.read_only?t("Sola lettura dichiarata","Read-only declared"):t("Non dichiarata in sola lettura: gli strumenti la rifiutano","Not declared read-only: tools refuse it")}</p>}
     {r.tools.length>0&&<p className="text-muted-foreground text-xs">{t("Usabile con: ","Usable with: ")}{r.tools.join(", ")}</p>}
     {r.last_test&&<p className={r.last_test.ok?"text-xs":"text-destructive text-xs"}>{t("Ultima prova ","Last test ")}{r.last_test.at.replace("T"," ").slice(0,16)}: {r.last_test.detail}</p>}
    </div>
    <div className="flex flex-wrap gap-2">
     {(r.mode==="user"||r.authentication==="microsoft")&&<button className="bg-primary text-primary-foreground rounded px-3 py-1 disabled:opacity-50" disabled={busy==="signin-"+r.id||(signIn?.id===r.id&&signIn.status==="pending")} onClick={()=>void startSignIn(r.id)}>{r.signed_in?t("Accedi di nuovo","Sign in again"):t("Accedi con Microsoft","Sign in with Microsoft")}</button>}
     {r.kind==="sqlserver"&&(r.authentication==="microsoft"||r.authentication==="entra")&&<button className="rounded border px-3 py-1 disabled:opacity-50" disabled={busy==="db-"+r.id||(r.authentication==="microsoft"&&!r.signed_in)} onClick={()=>void listDatabases(r)}>{t("Elenca database","List databases")}</button>}
     {(r.mode==="user"||r.authentication==="microsoft")&&r.signed_in&&<button className="rounded border px-3 py-1" onClick={()=>void signOut(r.id)}>{t("Scollega account","Disconnect account")}</button>}
     <button className="rounded border px-3 py-1 disabled:opacity-50" disabled={busy===r.id} onClick={()=>void test(r.id)}>{busy===r.id?t("Prova…","Testing…"):t("Prova","Test")}</button>
     <button className="rounded border px-3 py-1" onClick={()=>edit(r)}>{t("Modifica","Edit")}</button>
     <button className={"rounded border px-3 py-1"+(deleting===r.id?" border-destructive text-destructive":"")} onClick={()=>void remove(r.id)}>{deleting===r.id?t("Conferma eliminazione","Confirm deletion"):t("Elimina","Delete")}</button></div>
   </div>
   {signIn?.id===r.id&&<div className="mt-3 space-y-2 rounded border border-blue-500/30 bg-blue-500/5 p-3" data-testid="microsoft-sign-in" role="status">
    {signIn.status==="pending"&&<><p>{t("1. Apri ","1. Open ")}<a className="underline" href={signIn.verification_uri} target="_blank" rel="noreferrer">{signIn.verification_uri}</a></p>
     <p>{t("2. Inserisci il codice ","2. Enter the code ")}<code className="rounded border px-2 py-0.5 text-base font-semibold tracking-widest">{signIn.user_code}</code> <button type="button" className="text-xs underline" onClick={()=>void navigator.clipboard?.writeText(signIn.user_code)}>{t("copia","copy")}</button></p>
     <p>{t("3. Accedi e completa l’autenticazione a più fattori. Questa pagina si aggiorna da sola.","3. Sign in and complete multi-factor authentication. This page updates by itself.")}</p></>}
    {signIn.status==="signed_in"&&<p>{t("Accesso completato: ","Signed in: ")}{signIn.detail}</p>}
    {signIn.status==="expired"&&<p>{t("Il codice è scaduto. Premi di nuovo «Accedi con Microsoft».","The code expired. Press “Sign in with Microsoft” again.")}</p>}
    {signIn.status==="declined"&&<p>{t("Accesso rifiutato su Microsoft.","Sign-in declined on Microsoft.")}</p>}
    {signIn.status==="failed"&&<p className="text-destructive">{t("Accesso non riuscito: ","Sign-in failed: ")}{signIn.detail}</p>}
   </div>}
   {catalog?.id===r.id&&<div className="mt-3 space-y-2 rounded border p-3" data-testid="database-list">
    {catalog.rows===null?<p>{t("Cerco i database visibili al tuo account…","Looking for the databases your account can see…")}</p>
     :catalog.rows.length===0?<p>{t("Nessun database trovato con questo account su questo server: scrivi il nome nella connessione.","No database found with this account on this server: type the name in the connection.")}</p>
     :<ul className="space-y-1">{catalog.rows.map(d=><li key={d.name} className="flex flex-wrap items-center justify-between gap-2"><span><strong>{d.name}</strong> <span className="text-muted-foreground text-xs">{d.detail}</span></span>
       <button className="rounded border px-2 py-1 text-xs" disabled={r.database===d.name} onClick={()=>void selectDatabase(r,d.name)}>{r.database===d.name?t("In uso","In use"):t("Usa questo database","Use this database")}</button></li>)}</ul>}
   </div>}
  </li>)}</ul>
  <p className="text-muted-foreground text-xs">{t(
   "La prova verifica che il server sia raggiungibile da RigHaven e, per Microsoft Entra ID, che l’account o l’applicazione ottenga un token; utente e password dei database si verificano al primo utilizzo in un incarico. I token del tuo account valgono circa un’ora e vengono emessi all’avvio di ogni incarico. Se i lavori usano l’uscita di rete limitata (allowlist), i database non sono raggiungibili dagli incarichi.",
   "The test checks that RigHaven can reach the server and, for Microsoft Entra ID, that the account or application obtains a token; database users and passwords are verified at first use in an assignment. Tokens of your account last about one hour and are issued when each assignment starts. If tasks use restricted network egress (allowlist), databases are not reachable from assignments.")}</p>
 </div>;
}
