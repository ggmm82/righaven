"use client";
import {useEffect,useState} from "react";

import {fetch} from "@/core/api/fetcher";
import {getBackendBaseURL} from "@/core/config";
import {useI18n} from "@/core/i18n/hooks";

type Kind="postgres"|"sqlserver"|"mysql"|"oracle"|"entra";
type Test={ok:boolean;detail:string;at:string};
type Connection={id:string;kind:Kind;name:string;description?:string;host?:string;port?:number;database?:string;username?:string;tls?:boolean;read_only?:boolean;
 authentication?:"password"|"entra";entra_connection?:string;tenant_id?:string;client_id?:string;cloud?:string;has_secret:boolean;tools:string[];last_test?:Test;updated_at?:string};
type Form={id:string;kind:Kind;name:string;description:string;host:string;port:string;database:string;username:string;password:string;tls:boolean;read_only:boolean;
 authentication:"password"|"entra";entra_connection:string;tenant_id:string;client_id:string;client_secret:string;cloud:string};

const PORTS:Record<Kind,string>={postgres:"5432",sqlserver:"1433",mysql:"3306",oracle:"1521",entra:""};
const LABELS:Record<Kind,string>={postgres:"PostgreSQL",sqlserver:"SQL Server / Azure SQL / Fabric",mysql:"MySQL / MariaDB",oracle:"Oracle",entra:"Microsoft Entra ID"};
const blank=(kind:Kind):Form=>({id:"",kind,name:"",description:"",host:"",port:PORTS[kind],database:"",username:"",password:"",tls:true,read_only:false,
 authentication:"password",entra_connection:"",tenant_id:"",client_id:"",client_secret:"",cloud:"public"});
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
 const entras=(rows??[]).filter(r=>r.kind==="entra");
 function edit(row:Connection){setEditing(row.id);setNotice("");setError("");
  setForm({...blank(row.kind),...Object.fromEntries(Object.entries(row).filter(([,v])=>typeof v==="string"||typeof v==="boolean")),port:String(row.port??PORTS[row.kind]),password:"",client_secret:""} as Form);}
 async function save(){if(!form)return;setBusy("save");setError("");setNotice("");
  const body:Record<string,unknown>={kind:form.kind,name:form.name,description:form.description};
  if(!editing)body.id=form.id||slug(form.name);
  if(form.kind==="entra")Object.assign(body,{tenant_id:form.tenant_id,client_id:form.client_id,cloud:form.cloud,...(form.client_secret?{client_secret:form.client_secret}:{})});
  else Object.assign(body,{host:form.host,port:Number(form.port),database:form.database,tls:form.tls,read_only:form.read_only,
   authentication:form.kind==="sqlserver"?form.authentication:"password",
   ...(form.authentication==="entra"&&form.kind==="sqlserver"?{entra_connection:form.entra_connection}:{username:form.username,...(form.password?{password:form.password}:{})})});
  const r=await fetch(editing?`${base}/${editing}`:base,{method:editing?"PUT":"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const v=await r.json();setBusy("");
  if(!r.ok){setError(typeof v.detail==="string"?v.detail:String(r.status));return;}
  setForm(null);setEditing(null);setNotice(t("Connessione salvata. Usa «Prova» per verificarla.","Connection saved. Use “Test” to check it."));setReload(n=>n+1);}
 async function test(id:string){setBusy(id);setError("");const r=await fetch(`${base}/${id}/test`,{method:"POST"});const v=await r.json();setBusy("");
  if(!r.ok){setError(typeof v.detail==="string"?v.detail:String(r.status));return;}setReload(n=>n+1);}
 async function remove(id:string){if(deleting!==id){setDeleting(id);return;}setDeleting("");
  const r=await fetch(`${base}/${id}`,{method:"DELETE"});const v=await r.json();if(!r.ok){setError(typeof v.detail==="string"?v.detail:String(r.status));return;}setReload(n=>n+1);}
 const field="mt-1 w-full rounded border bg-background p-2 text-sm";
 const input=(key:keyof Form,label:string,props:Record<string,unknown>={})=><label className="block text-sm">{label}
  <input className={field} value={String(form?.[key]??"")} onChange={e=>setForm(f=>f&&{...f,[key]:e.target.value})} {...props}/></label>;
 return <div className="mx-auto w-full max-w-5xl space-y-6 p-6">
  <header className="space-y-2"><h1 className="text-2xl font-semibold">{t("Connessioni","Connections")}</h1>
   <p className="text-muted-foreground text-sm">{t(
    "Registra qui i database e gli account Microsoft che i lavori possono usare. Le password e i segreti sono cifrati, non vengono più mostrati e non arrivano mai al coordinatore. Sei tu a decidere l’accesso: in un lavoro scegli le connessioni dal pannello del progetto («Connessioni del lavoro»); solo gli incarichi di quel lavoro le ricevono, e le perdono quando finiscono.",
    "Register here the databases and Microsoft accounts that tasks may use. Passwords and secrets are encrypted, never shown again and never reach the coordinator. Access is your choice: in a task you pick the connections from the project panel (“Task connections”); only that task's assignments receive them, and lose them when they end.")}</p>
   <p className="text-muted-foreground text-sm">{t(
    "Usa account in sola lettura: gli strumenti RigHaven eseguono solo letture e rifiutano i database non dichiarati in sola lettura. Per Azure SQL e Microsoft Fabric crea prima l’applicazione Microsoft Entra ID, poi una connessione SQL Server che la usa.",
    "Use read-only accounts: RigHaven tools only read and refuse databases not declared read-only. For Azure SQL and Microsoft Fabric create the Microsoft Entra ID application first, then a SQL Server connection that uses it.")}</p>
  </header>
  {error&&<p className="text-destructive text-sm" role="alert">{error}</p>}
  {notice&&<p className="text-sm">{notice}</p>}
  {!form&&<div className="flex flex-wrap gap-2">{(["postgres","sqlserver","mysql","oracle","entra"] as Kind[]).map(k=><button key={k} className="rounded border px-3 py-2 text-sm" onClick={()=>{setEditing(null);setForm(blank(k));}}>{t("Nuova: ","New: ")}{LABELS[k]}</button>)}</div>}
  {form&&<section className="space-y-3 rounded-lg border p-4" data-testid="connection-form">
   <h2 className="font-semibold">{editing?t("Modifica ","Edit ")+editing:t("Nuova connessione ","New connection ")}· {LABELS[form.kind]}</h2>
   <div className="grid gap-3 md:grid-cols-2">
    {input("name",t("Nome","Name"),{placeholder:t("es. ERP vendite (lettura)","e.g. Sales ERP (read)")})}
    {!editing&&input("id",t("ID (facoltativo)","ID (optional)"),{placeholder:slug(form.name)||"erp-vendite"})}
    {input("description",t("Descrizione","Description"))}
    {form.kind==="entra"?<>
     {input("tenant_id",t("Tenant (ID directory o dominio)","Tenant (directory ID or domain)"),{placeholder:"contoso.onmicrosoft.com"})}
     {input("client_id",t("ID applicazione (client)","Application (client) ID"),{placeholder:"00000000-0000-0000-0000-000000000000"})}
     {input("client_secret",t("Segreto client","Client secret")+(editing?t(" (vuoto = invariato)"," (empty = unchanged)"):""),{type:"password",autoComplete:"new-password"})}
     <label className="block text-sm">{t("Cloud","Cloud")}<select className={field} value={form.cloud} onChange={e=>setForm(f=>f&&{...f,cloud:e.target.value})}>
      <option value="public">{t("Globale","Global")}</option><option value="usgov">US Government</option><option value="china">{t("Cina (21Vianet)","China (21Vianet)")}</option></select></label>
    </>:<>
     {input("host",t("Server","Server"),{placeholder:form.kind==="sqlserver"?"server.database.windows.net":"db.example.com"})}
     {input("port",t("Porta","Port"),{inputMode:"numeric"})}
     {input("database",form.kind==="oracle"?t("Nome del servizio (service name)","Service name"):t("Database","Database"))}
     {form.kind==="sqlserver"&&<label className="block text-sm">{t("Autenticazione","Authentication")}<select className={field} value={form.authentication} onChange={e=>setForm(f=>f&&{...f,authentication:e.target.value as "password"|"entra"})}>
      <option value="password">{t("Utente e password SQL","SQL user and password")}</option><option value="entra">{t("Microsoft Entra ID (service principal)","Microsoft Entra ID (service principal)")}</option></select></label>}
     {form.kind==="sqlserver"&&form.authentication==="entra"?<label className="block text-sm">{t("Applicazione Entra ID","Entra ID application")}<select className={field} value={form.entra_connection} onChange={e=>setForm(f=>f&&{...f,entra_connection:e.target.value})}>
       <option value="">{t("Scegli…","Choose…")}</option>{entras.map(e=><option key={e.id} value={e.id}>{e.name}</option>)}</select>
       {entras.length===0&&<span className="text-muted-foreground text-xs">{t("Crea prima una connessione Microsoft Entra ID.","Create a Microsoft Entra ID connection first.")}</span>}</label>
     :<>{input("username",t("Utente","User"))}{input("password",t("Password","Password")+(editing?t(" (vuota = invariata)"," (empty = unchanged)"):""),{type:"password",autoComplete:"new-password"})}</>}
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
    <div><p className="font-semibold">{r.name} <span className="text-muted-foreground font-normal">· {LABELS[r.kind]} · {r.id}</span></p>
     <p className="text-muted-foreground">{r.kind==="entra"?t("Tenant ","Tenant ")+r.tenant_id+" · "+t("app ","app ")+r.client_id:(r.host??"")+":"+String(r.port??"")+" / "+(r.database??"")+(r.authentication==="entra"?" · Entra ID ("+(r.entra_connection??"")+")":" · "+(r.username??""))}</p>
     {r.kind!=="entra"&&<p className={r.read_only?"":"text-destructive"}>{r.read_only?t("Sola lettura dichiarata","Read-only declared"):t("Non dichiarata in sola lettura: gli strumenti la rifiutano","Not declared read-only: tools refuse it")}</p>}
     {r.tools.length>0&&<p className="text-muted-foreground text-xs">{t("Usabile con: ","Usable with: ")}{r.tools.join(", ")}</p>}
     {r.last_test&&<p className={r.last_test.ok?"text-xs":"text-destructive text-xs"}>{t("Ultima prova ","Last test ")}{r.last_test.at.replace("T"," ").slice(0,16)}: {r.last_test.detail}</p>}
    </div>
    <div className="flex gap-2"><button className="rounded border px-3 py-1 disabled:opacity-50" disabled={busy===r.id} onClick={()=>void test(r.id)}>{busy===r.id?t("Prova…","Testing…"):t("Prova","Test")}</button>
     <button className="rounded border px-3 py-1" onClick={()=>edit(r)}>{t("Modifica","Edit")}</button>
     <button className={"rounded border px-3 py-1"+(deleting===r.id?" border-destructive text-destructive":"")} onClick={()=>void remove(r.id)}>{deleting===r.id?t("Conferma eliminazione","Confirm deletion"):t("Elimina","Delete")}</button></div>
   </div>
  </li>)}</ul>
  <p className="text-muted-foreground text-xs">{t(
   "La prova verifica che il server sia raggiungibile da RigHaven e, per Microsoft Entra ID, che l’applicazione ottenga un token; utente e password dei database si verificano al primo utilizzo in un incarico. Se i lavori usano l’uscita di rete limitata (allowlist), i database non sono raggiungibili dagli incarichi.",
   "The test checks that RigHaven can reach the server and, for Microsoft Entra ID, that the application obtains a token; database users and passwords are verified at first use in an assignment. If tasks use restricted network egress (allowlist), databases are not reachable from assignments.")}</p>
 </div>;
}
