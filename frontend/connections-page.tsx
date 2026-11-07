"use client";
import {createContext,useContext,useEffect,useState,type Dispatch,type ReactNode,type SetStateAction} from "react";

import {ConceptMap} from "@/components/workspace/concept-map";
import {fetch} from "@/core/api/fetcher";
import {getBackendBaseURL} from "@/core/config";
import {useI18n} from "@/core/i18n/hooks";

type ProviderAccess={id:string;name:string;scope:string;status:string;manage_url:string};
type Kind="postgres"|"sqlserver"|"mysql"|"oracle"|"entra"|"device"|"network";
type Transport="network"|"serial"|"local"|"bluetooth";
/** Where a service lives: "cloud" (the internet), "server" (the network or the machine of this server), or the ID of an agent of this user (on premise, through that PC). */
type Place=string;
const agentOf=(place:Place)=>place==="cloud"||place==="server"?"":place;
const placeOf=(r:Connection):Place=>r.agent??(r.location==="on_premise"?"server":"cloud");
type Agent={id:string;name:string;platform?:string;version?:string;last_seen?:string|null;online:boolean;networks?:string[];compute?:{cpus:number;memory_mib:number;jobs:number;docker:string;running:number}|null};
/** The PC the device sections act on: "" for the PC of this server (administrators), or an agent of this user. */
const PcContext=createContext("");
const withAgent=(url:string,agent:string)=>agent?url+(url.includes("?")?"&":"?")+"agent="+encodeURIComponent(agent):url;
type Test={ok:boolean;detail:string;at:string};
type Connection={id:string;kind:Kind;name:string;description?:string;host?:string;port?:number;database?:string;username?:string;tls?:boolean;read_only?:boolean;
 authentication?:"password"|"entra"|"microsoft";entra_connection?:string;tenant_id?:string;client_id?:string;cloud?:string;has_secret:boolean;tools:string[];last_test?:Test;updated_at?:string;
 mode?:"user"|"application";signed_in?:boolean;account?:string;write_enabled?:boolean;write_schema?:string;
 transport?:Transport;protocol?:string;device?:string;topic?:string;path?:string;unit?:number;baud?:number;ranges?:string[];exclude?:string[];address?:string;agent?:string;location?:"cloud"|"on_premise";pc?:string};
type SignIn={id:string;user_code:string;verification_uri:string;interval:number;status:string;detail?:string};
type Form={id:string;kind:Kind;name:string;description:string;host:string;port:string;database:string;username:string;password:string;tls:boolean;read_only:boolean;
 authentication:"password"|"entra"|"microsoft";entra_connection:string;tenant_id:string;client_id:string;client_secret:string;cloud:string;mode:"user"|"application";access:"read"|"write";write_schema:string;
 transport:Transport;protocol:string;device:string;topic:string;path:string;unit:string;baud:string;ranges:string;exclude:string;authorized:boolean;version:string;node_id:string;address:string;place:Place};

const PORTS:Record<Kind,string>={postgres:"5432",sqlserver:"1433",mysql:"3306",oracle:"1521",entra:"",device:"",network:""};
const DEVICE_PORTS:Record<string,string>={mqtt:"1883",mqtts:"8883","modbus-tcp":"502",http:"80",https:"443",adb:"5555",tuya:"6668",tcp:""};
const LABELS:Record<Kind,string>={postgres:"PostgreSQL",sqlserver:"SQL Server / Azure SQL / Fabric",mysql:"MySQL / MariaDB",oracle:"Oracle",entra:"Microsoft Entra ID",device:"IoT",network:"Network"};
const DEFAULT_CLIENT="04b07795-8ddb-461a-bbee-02f9e1bf7b46";
const blank=(kind:Kind,place:Place="cloud"):Form=>({id:"",kind,name:"",description:"",host:"",port:PORTS[kind],database:"",username:"",password:"",tls:true,read_only:false,
 authentication:kind==="sqlserver"?"microsoft":"password",entra_connection:"",tenant_id:"",client_id:"",client_secret:"",cloud:"public",mode:"user",access:"read",write_schema:"",
 transport:"network",protocol:"mqtt",device:"",topic:"#",path:"/",unit:"1",baud:"115200",ranges:"",exclude:"",authorized:false,version:"3.3",node_id:"",address:"",place});
const slug=(text:string)=>text.normalize("NFD").replace(/\p{M}/gu,"").toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-+|-+$/g,"").replace(/^([^a-z])/,"c-$1").slice(0,40);

/** Personal database, Microsoft cloud and device connections; secrets are encrypted and never shown again. */
export default function ConnectionsPage(){
 const {locale}=useI18n();const it=locale==="it-IT";const t=(a:string,b:string)=>it?a:b;
 const base=getBackendBaseURL()+"/api/harness/connections";
 const [rows,setRows]=useState<Connection[]|null>(null),[form,setForm]=useState<Form|null>(null),[editing,setEditing]=useState<string|null>(null);
 const [error,setError]=useState(""),[notice,setNotice]=useState(""),[busy,setBusy]=useState(""),[reload,setReload]=useState(0),[deleting,setDeleting]=useState("");
 useEffect(()=>{let live=true;
  void fetch(base).then(async r=>{const v=await r.json();if(!r.ok)throw Error(typeof v.detail==="string"?v.detail:String(r.status));return v as {connections:Connection[];devices?:string[]};})
   .then(v=>{if(live){setRows(v.connections);setDevices(v.devices??[]);}}).catch(e=>{if(live)setError(e instanceof Error?e.message:String(e));});
  return()=>{live=false;};},[base,reload]);
 const [providers,setProviders]=useState<ProviderAccess[]>([]),[devices,setDevices]=useState<string[]>([]),[hostEpoch,setHostEpoch]=useState(0);
 const [agents,setAgents]=useState<Agent[]>([]),[pc,setPcState]=useState(()=>{try{return localStorage.getItem("righaven.pc")??"";}catch{return "";}});
 const [newPlace,setNewPlace]=useState<Place>("");
 const placeLabel=(place:Place)=>place==="cloud"?t("Cloud (internet)","Cloud (internet)"):place==="server"?t("On premise · rete o macchina di questo server","On premise · network or machine of this server")
  :t("On premise · tramite ","On premise · through ")+(agents.find(a=>a.id===place)?.name??place);
 const places:Place[]=["cloud","server",...agents.map(a=>a.id)];
 // What is found near a PC is on premise: next to the PC being worked on (an agent), or next to this server.
 const found=(value:Form)=>{setEditing(null);setNotice("");
  const nearAgent=pc&&value.protocol!=="matter"&&value.transport!=="local"&&!(value.transport==="serial"&&value.host);
  setForm({...value,place:value.place!=="cloud"?value.place:nearAgent?pc:"server"});};
 const setPc=(value:string)=>{setPcState(value);try{localStorage.setItem("righaven.pc",value);}catch{/* the choice is only remembered when the browser allows it */}};
 const kindLabel=(k:Kind)=>k==="device"?t("Dispositivo (rete, seriale, USB)","Device (network, serial, USB)"):k==="network"?t("Rete da mappare","Network to map"):LABELS[k];
 useEffect(()=>{let live=true;void fetch(`${getBackendBaseURL()}/api/harness/access-catalog`).then(async r=>{if(!r.ok)throw Error(String(r.status));return r.json() as Promise<{providers:ProviderAccess[]}>;}).then(v=>{if(live)setProviders(v.providers);}).catch(()=>undefined);return()=>{live=false;};},[]);
 const entras=(rows??[]).filter(r=>r.kind==="entra");
 function edit(row:Connection){setEditing(row.id);setNotice("");setError("");
  setForm({...blank(row.kind),...Object.fromEntries(Object.entries(row).filter(([,v])=>typeof v==="string"||typeof v==="boolean")),port:String(row.port??PORTS[row.kind]),password:"",client_secret:"",access:row.write_enabled?"write":"read",write_schema:row.write_schema??"",
   unit:String(row.unit??1),baud:String(row.baud??115200),place:row.agent??(row.location==="on_premise"?"server":"cloud"),ranges:(row.ranges??[]).join(", "),exclude:(row.exclude??[]).join(", "),authorized:row.kind==="network"} as Form);}
 async function save(){if(!form)return;setBusy("save");setError("");setNotice("");
  const body:Record<string,unknown>={kind:form.kind,name:form.name,description:form.description};
  if(!editing)body.id=slug(form.id)||slug(form.name);
  if(form.kind==="network")Object.assign(body,{ranges:form.ranges.split(/[\s,;]+/).filter(Boolean),exclude:form.exclude.split(/[\s,;]+/).filter(Boolean),authorized:form.authorized,access:form.access});
  else if(form.kind==="device")Object.assign(body,{transport:form.transport,access:form.access,agent:agentOf(form.place),
   ...(form.transport==="serial"&&agentOf(form.place)?{device:form.device,baud:Number(form.baud)}
    :form.transport==="bluetooth"?{address:form.address}
    :form.transport==="local"?{device:form.device,baud:Number(form.baud)}
    :form.transport==="serial"?{host:form.host,port:Number(form.port),baud:Number(form.baud),protocol:form.protocol==="socket"?"socket":"rfc2217"}
    :{host:form.host,protocol:form.protocol,tls:form.tls,...(form.port?{port:Number(form.port)}:{}),username:form.username,...(form.password?{password:form.password}:{}),
      ...(form.protocol==="mqtt"?{topic:form.topic}:form.protocol==="http"?{path:form.path}:form.protocol==="modbus-tcp"?{unit:Number(form.unit)}:form.protocol==="tuya"?{version:form.version}:form.protocol==="matter"?{node_id:Number(form.node_id)}:{})})});
  else if(form.kind==="entra")Object.assign(body,{mode:form.mode,tenant_id:form.tenant_id,client_id:form.mode==="user"&&form.client_id===DEFAULT_CLIENT?"":form.client_id,cloud:form.cloud,...(form.mode==="application"&&form.client_secret?{client_secret:form.client_secret}:{})});
  else Object.assign(body,{host:form.host,port:Number(form.port),database:form.database,tls:form.tls,read_only:form.read_only,access:form.access,write_schema:form.access==="write"?form.write_schema:"",
   agent:agentOf(form.place),authentication:form.kind==="sqlserver"?(agentOf(form.place)?"password":form.authentication):"password",
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
 const [explore,setExplore]=useState("");
 const [catalog,setCatalog]=useState<{id:string;rows:{name:string;detail:string}[]|null}|null>(null);
 async function listDatabases(row:Connection){setError("");setBusy("db-"+row.id);setCatalog({id:row.id,rows:null});try{const r=await fetch(`${base}/${row.id}/databases`,{method:"POST"});const v=await r.json();
  if(!r.ok)throw Error(typeof v.detail==="string"?v.detail:String(r.status));setCatalog({id:row.id,rows:v.databases});}catch(e){setCatalog(null);setError(e instanceof Error?e.message:String(e));}finally{setBusy("");}}
 async function selectDatabase(row:Connection,database:string){setError("");
  const body={kind:row.kind,name:row.name,description:row.description??"",host:row.host,port:row.port,database,tls:row.tls,read_only:row.read_only,access:row.write_enabled?"write":"read",write_schema:row.write_schema??"",authentication:row.authentication,
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
    "Ogni connessione è una connessione a un servizio: un database, un account Microsoft, un servizio o un dispositivo in rete, una porta seriale o USB, un dispositivo Bluetooth. Per ognuna dici dove si trova: in cloud oppure on premise, vicino a questo server o tramite un tuo PC con RigHaven Agent. Le password e i segreti sono cifrati, non vengono più mostrati e non arrivano mai al coordinatore. Sei tu a decidere l’accesso: in un lavoro scegli le connessioni dal pannello del progetto («Connessioni del lavoro»); solo i ruoli che dichiarano gli ID autorizzati le ricevono e le perdono quando finiscono.",
    "Every connection is a connection to a service: a database, a Microsoft account, a service or device on the network, a serial or USB port, a Bluetooth device. For each you say where it is: in the cloud or on premise, next to this server or through one of your PCs with RigHaven Agent. Passwords and secrets are encrypted, never shown again and never reach the coordinator. Access is your choice: in a task you pick the connections from the project panel (“Task connections”); only roles declaring the authorized IDs receive them, and lose them when they end.")}</p>
   <p className="text-muted-foreground text-sm">{t(
    "Usa account in sola lettura: gli strumenti RigHaven eseguono solo letture e rifiutano i database non dichiarati in sola lettura. Per Azure SQL e Microsoft Fabric aggiungi prima il tuo account Microsoft (accesso con autenticazione a più fattori, consigliato) oppure un’applicazione Entra ID, poi una connessione SQL Server che lo usa.",
    "Use read-only accounts: RigHaven tools only read and refuse databases not declared read-only. For Azure SQL and Microsoft Fabric first add your Microsoft account (sign-in with multi-factor authentication, recommended) or an Entra ID application, then a SQL Server connection that uses it.")}</p>
  </header>
  <ConceptMap current="connection"/>
  {error&&<p className="text-destructive text-sm" role="alert">{error}</p>}
  {notice&&<p className="text-sm">{notice}</p>}
  <section className="space-y-3 rounded-xl border p-4" data-testid="model-accesses"><h2 className="font-semibold">{t("Modelli e CLI ufficiali","Models and official CLIs")}</h2><p className="text-sm">{t("Gli stessi collegamenti di Modelli e risorse: nessun secondo login. Il modello rimane assegnabile al coordinatore, alla squadra o a entrambi. Gli accessi condivisi sono gestiti dall’amministratore.","The same connections as Models & resources: no duplicate login. Models remain assignable to coordinator, team or both. Shared connections are managed by the administrator.")}</p><ul className="space-y-2">{providers.map(p=><li key={p.id} className="flex flex-wrap justify-between gap-2"><span>{p.name} · {p.status==="configured"?t("Configurato","Configured"):t("Verifica in Modelli","Check Models")}</span><a className="underline" href={p.manage_url}>{t("Apri configurazione","Open configuration")}</a></li>)}</ul></section>
  <p className="text-sm">{t("Database e identità esterne sono facoltativi. Per analizzare documenti e creare il laboratorio sintetico non devi configurarli.","External databases and identities are optional. You do not need to configure them to analyze documents and build the synthetic laboratory.")}</p>
  {!form&&<AgentsPanel t={t} pc={pc} setPc={setPc} onAgents={setAgents}/>}
  <PcContext.Provider value={pc}>
  {!form&&<PcDevices key={"p"+pc} t={t} onChanged={()=>{setHostEpoch(n=>n+1);setReload(n=>n+1);}} onCreate={found}/>}
  {!form&&<DeviceDiscovery key={"d"+hostEpoch+pc} base={base} t={t} onCreate={found}/>}
  {!form&&!pc&&<MatterDevices key={"m"+hostEpoch} t={t} onCreate={found}/>}
  </PcContext.Provider>
  {!form&&(()=>{const place=newPlace||pc||"cloud";const agent=agentOf(place);
   // Every connection is a connection to a service: where it lives first, then which service.
   const services:[string,Kind,Transport,string][]=[["postgres","postgres","network",LABELS.postgres],["sqlserver","sqlserver","network",LABELS.sqlserver],["mysql","mysql","network",LABELS.mysql],["oracle","oracle","network",LABELS.oracle],
    ...(place==="cloud"?[["entra","entra","network",LABELS.entra] as [string,Kind,Transport,string]]:[]),
    ["device","device","network",t("Servizio di rete (MQTT, HTTP, Modbus, Android, Tuya, TCP)","Network service (MQTT, HTTP, Modbus, Android, Tuya, TCP)")],
    ...(place==="cloud"?[]:[["serial","device",agent?"serial":"local",agent?t("Porta COM / USB del PC","COM / USB port of the PC"):t("Porta seriale / USB","Serial / USB port")] as [string,Kind,Transport,string],
     ["bluetooth","device","bluetooth",t("Dispositivo Bluetooth LE","Bluetooth LE device")] as [string,Kind,Transport,string]]),
    ...(agent?[]:[["network","network","network",t("Rete da mappare","Network to map")] as [string,Kind,Transport,string]])];
   return <section className="space-y-3 rounded-xl border p-4" data-testid="new-connection">
    <h2 className="font-semibold">{t("Nuova connessione a un servizio","New connection to a service")}</h2>
    <label className="block text-sm">{t("Dove si trova il servizio","Where the service is")}<select className={field} aria-label={t("Dove si trova il servizio","Where the service is")} value={place} onChange={e=>setNewPlace(e.target.value)}>
     {places.map(p=><option key={p} value={p}>{placeLabel(p)}</option>)}</select></label>
    <p className="text-muted-foreground text-xs">{place==="cloud"?t("Servizi su internet: RigHaven li raggiunge da questo server.","Services on the internet: RigHaven reaches them from this server.")
     :place==="server"?t("Servizi nella rete o sulla macchina dove gira questo server (sul PC con RigHaven portabile: la tua rete di casa o d’ufficio).","Services in the network or on the machine this server runs on (on the PC with portable RigHaven: your home or office network).")
     :t("Servizi della rete di quel PC (ufficio o casa), le sue porte COM/USB e il suo Bluetooth: RigHaven Agent li porta a questo server con un tunnel cifrato, senza aprire porte.","Services of that PC's network (office or home), its COM/USB ports and its Bluetooth: RigHaven Agent carries them to this server through an encrypted tunnel, with no port to open.")}</p>
    <div className="flex flex-wrap gap-2">{services.map(([id,kind,transport,label])=><button key={id} className="rounded border px-3 py-2 text-sm" data-testid={"new-"+id}
     onClick={()=>{setEditing(null);setForm({...blank(kind,place),transport,...(agent&&kind==="sqlserver"?{authentication:"password" as const}:{})});}}>{t("Nuova: ","New: ")}{label}</button>)}</div>
   </section>;})()}
  {form&&<section className="space-y-3 rounded-lg border p-4" data-testid="connection-form">
   <h2 className="font-semibold">{editing?t("Modifica ","Edit ")+editing:t("Nuova connessione ","New connection ")}· {kindLabel(form.kind)} · {placeLabel(form.place)}</h2>
   <div className="grid gap-3 md:grid-cols-2">
    {input("name",t("Nome","Name"),{placeholder:t("es. ERP vendite (lettura)","e.g. Sales ERP (read)")})}
    {!editing&&<div>{input("id",t("ID (facoltativo)","ID (optional)"),{placeholder:slug(form.name)||"erp-vendite"})}
     <p className="text-muted-foreground mt-1 text-xs" data-testid="connection-id-hint">{t("Sarà salvato come","Saved as")} <code>{slug(form.id)||slug(form.name)||"…"}</code>{t(": lettere minuscole, cifre e trattini.",": lowercase letters, digits and hyphens.")}</p></div>}
    {input("description",t("Descrizione","Description"))}
    {form.kind==="network"?<NetworkFields form={form} setForm={setForm} t={t} input={input}/>:form.kind==="device"?<><PlaceField form={form} setForm={setForm} places={places} placeLabel={placeLabel} t={t}/><DeviceFields form={form} setForm={setForm} devices={devices} editing={Boolean(editing)} t={t} input={input}/></>:form.kind==="entra"?<>
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
     <PlaceField form={form} setForm={setForm} places={places} placeLabel={placeLabel} t={t}/>
     {form.kind==="sqlserver"&&!agentOf(form.place)&&<label className="block text-sm md:col-span-2">{t("Autenticazione","Authentication")}<select className={field} aria-label={t("Autenticazione","Authentication")} value={form.authentication} onChange={e=>setForm(f=>f&&{...f,authentication:e.target.value as "password"|"entra"|"microsoft"})}>
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
     <label className="block text-sm md:col-span-2">{t("Uso","Use")}<select className={field} aria-label={t("Uso della connessione","Connection use")} value={form.access} onChange={e=>setForm(f=>f&&{...f,access:e.target.value as "read"|"write"})}>
      <option value="read">{t("Sola lettura (consigliato per le sorgenti)","Read only (recommended for sources)")}</option>
      <option value="write">{t("Lettura e scrittura in uno schema dedicato (destinazione)","Read and write in a dedicated schema (destination)")}</option></select></label>
     {form.access==="read"?<label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.read_only} onChange={e=>setForm(f=>f&&{...f,read_only:e.target.checked})}/>{t("Confermo che l’account ha solo permessi di lettura","I confirm the account has read-only permissions")}</label>
      :<>{input("write_schema",t("Schema in cui RigHaven può scrivere","Schema RigHaven may write to"),{placeholder:"righaven"})}
       <p className="text-muted-foreground text-xs md:col-span-2">{t("Gli incarichi possono solo caricare tabelle già verificate in questo schema, sostituendole o accodandole: mai SQL libero. Per ogni incarico decidi tu se consentire la scrittura, nella scheda «Connessioni del lavoro». Usa un account con permessi limitati a questo schema.","Tasks can only load already verified tables into this schema, replacing or appending them: never arbitrary SQL. For each task you decide whether to allow writing, in “Task connections”. Use an account whose permissions are limited to this schema.")}</p></>}
    </>}
   </div>
   <div className="flex gap-2"><button className="bg-primary text-primary-foreground rounded px-3 py-2 text-sm disabled:opacity-50" disabled={busy==="save"||(form.kind==="device"&&form.transport==="local"&&!form.device)} onClick={()=>void save()}>{t("Salva","Save")}</button>
    <button className="rounded border px-3 py-2 text-sm" onClick={()=>{setForm(null);setEditing(null);}}>{t("Annulla","Cancel")}</button></div>
  </section>}
  {rows===null&&!error&&<p className="text-sm">{t("Caricamento…","Loading…")}</p>}
  {rows?.length===0&&!form&&<p className="text-sm">{t("Nessuna connessione registrata.","No connections registered.")}</p>}
  {places.filter(g=>(rows??[]).some(r=>placeOf(r)===g)).concat([...new Set((rows??[]).map(placeOf))].filter(g=>!places.includes(g))).map(g=><section key={g} className="space-y-2" data-testid={"connections-"+g}>
  <h3 className="text-sm font-semibold">{placeLabel(g)}</h3>
  <ul className="space-y-3">{(rows??[]).filter(r=>placeOf(r)===g).map(r=><li key={r.id} className="rounded-lg border p-4 text-sm" data-testid={"connection-"+r.id}>
   <div className="flex flex-wrap items-start justify-between gap-2">
    <div className="min-w-0 break-words [overflow-wrap:anywhere]"><p className="font-semibold">{r.name} <span className="text-muted-foreground font-normal">· {kindLabel(r.kind)} · {r.id}</span></p>
     <p className="text-muted-foreground">{r.kind==="network"?t("Reti: ","Networks: ")+(r.ranges??[]).join(", ")+((r.exclude??[]).length?t(" · escluse: "," · excluded: ")+(r.exclude??[]).join(", "):""):r.kind==="device"?deviceSummary(r,t):r.kind==="entra"?(r.mode==="user"?(r.signed_in?t("Account ","Account ")+(r.account??""):t("Accesso Microsoft da completare","Microsoft sign-in to complete"))+" · "+t("tenant ","tenant ")+r.tenant_id:t("Applicazione · tenant ","Application · tenant ")+r.tenant_id+" · "+t("app ","app ")+r.client_id):(r.host??"")+":"+String(r.port??"")+" / "+(r.database??"")+(r.authentication==="entra"?" · Entra ID ("+(r.entra_connection??"")+")":" · "+(r.username??""))+(r.authentication==="microsoft"?" · "+(r.signed_in?t("accesso Microsoft attivo","Microsoft signed in"):t("accesso Microsoft da completare","Microsoft sign-in to complete")):"")}</p>
     {r.kind==="device"&&<p>{r.write_enabled?t("Scrittura e firmware consentiti se li abiliti nell’incarico; altrimenti sola lettura","Writing and firmware allowed when you enable them in the task; otherwise read-only"):t("Sola lettura: gli incarichi possono solo leggere","Read-only: tasks can only read")}</p>}
     {r.kind==="network"&&<p>{r.write_enabled?t("Mappatura e, con la tua approvazione per ogni scansione, ricerca di vulnerabilità","Mapping and, with your approval of each scan, vulnerability checks"):t("Solo mappatura: host, porte e servizi","Mapping only: hosts, ports and services")}</p>}
     {r.kind!=="entra"&&r.kind!=="device"&&r.kind!=="network"&&<p className={r.read_only||r.write_enabled?"":"text-destructive"}>{r.write_enabled?t(`Scrittura consentita nello schema ${r.write_schema??""}, se la abiliti nell’incarico`,`Writing allowed in schema ${r.write_schema??""}, when you enable it in the task`):r.read_only?t("Sola lettura dichiarata","Read-only declared"):t("Non dichiarata in sola lettura: gli strumenti la rifiutano","Not declared read-only: tools refuse it")}</p>}
     {r.tools.length>0&&<p className="text-muted-foreground text-xs">{t("Usabile con: ","Usable with: ")}{r.tools.join(", ")}</p>}
     {r.last_test&&<p className={r.last_test.ok?"text-xs":"text-destructive text-xs"}>{t("Ultima prova ","Last test ")}{r.last_test.at.replace("T"," ").slice(0,16)}: {r.last_test.detail}</p>}
    </div>
    <div className="flex flex-wrap gap-2">
     {(r.mode==="user"||r.authentication==="microsoft")&&<button className="bg-primary text-primary-foreground rounded px-3 py-1 disabled:opacity-50" disabled={busy==="signin-"+r.id||(signIn?.id===r.id&&signIn.status==="pending")} onClick={()=>void startSignIn(r.id)}>{r.signed_in?t("Accedi di nuovo","Sign in again"):t("Accedi con Microsoft","Sign in with Microsoft")}</button>}
     {r.kind==="sqlserver"&&(r.authentication==="microsoft"||r.authentication==="entra")&&<button className="rounded border px-3 py-1 disabled:opacity-50" disabled={busy==="db-"+r.id||(r.authentication==="microsoft"&&!r.signed_in)} onClick={()=>void listDatabases(r)}>{t("Elenca database","List databases")}</button>}
     {(r.mode==="user"||r.authentication==="microsoft")&&r.signed_in&&<button className="rounded border px-3 py-1" onClick={()=>void signOut(r.id)}>{t("Scollega account","Disconnect account")}</button>}
     {r.kind==="device"&&(r.transport==="bluetooth"||r.transport==="network")&&<button className="rounded border px-3 py-1" onClick={()=>setExplore(explore===r.id?"":r.id)}>{t("Esplora","Explore")}</button>}
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
   {explore===r.id&&r.transport==="bluetooth"&&r.address&&<BleExplorer address={r.address} t={t}/>}
   {explore===r.id&&r.transport==="network"&&r.host&&<NetExplorer address={r.host} t={t}/>}
   {catalog?.id===r.id&&<div className="mt-3 space-y-2 rounded border p-3" data-testid="database-list">
    {catalog.rows===null?<p>{t("Cerco i database visibili al tuo account…","Looking for the databases your account can see…")}</p>
     :catalog.rows.length===0?<p>{t("Nessun database trovato con questo account su questo server: scrivi il nome nella connessione.","No database found with this account on this server: type the name in the connection.")}</p>
     :<ul className="space-y-1">{catalog.rows.map(d=><li key={d.name} className="flex flex-wrap items-center justify-between gap-2"><span><strong>{d.name}</strong> <span className="text-muted-foreground text-xs">{d.detail}</span></span>
       <button className="rounded border px-2 py-1 text-xs" disabled={r.database===d.name} onClick={()=>void selectDatabase(r,d.name)}>{r.database===d.name?t("In uso","In use"):t("Usa questo database","Use this database")}</button></li>)}</ul>}
   </div>}
  </li>)}</ul></section>)}
  <p className="text-muted-foreground text-xs">{t(
   "La prova verifica che il server sia raggiungibile da RigHaven e, per Microsoft Entra ID, che l’account o l’applicazione ottenga un token; utente e password dei database si verificano al primo utilizzo in un incarico. I token del tuo account valgono circa un’ora e vengono emessi all’avvio di ogni incarico. Se i lavori usano l’uscita di rete limitata (allowlist), i database non sono raggiungibili dagli incarichi.",
   "The test checks that RigHaven can reach the server and, for Microsoft Entra ID, that the account or application obtains a token; database users and passwords are verified at first use in an assignment. Tokens of your account last about one hour and are issued when each assignment starts. If tasks use restricted network egress (allowlist), databases are not reachable from assignments.")}</p>
 </div>;
}

type Translate=(a:string,b:string)=>string;
type FieldInput=(key:keyof Form,label:string,props?:Record<string,unknown>)=>ReactNode;

function deviceSummary(r:Connection,t:Translate){
 if(r.transport==="serial"&&r.agent)return t("Porta COM del PC: ","COM port of the PC: ")+(r.device??"")+(r.baud?" · "+String(r.baud)+" baud":"");
 if(r.transport==="bluetooth")return t("Bluetooth LE: ","Bluetooth LE: ")+(r.address??"");
 if(r.transport==="local")return t("Collegato a questa macchina: ","Attached to this machine: ")+(r.device??"")+(r.baud?" · "+String(r.baud)+" baud":"");
 if(r.transport==="serial")return t("Seriale in rete (RFC 2217): ","Serial over the network (RFC 2217): ")+(r.host??"")+":"+String(r.port??"")+" · "+String(r.baud??"")+" baud";
 return (r.protocol??"").toUpperCase()+" · "+(r.host??"")+":"+String(r.port??"")+(r.topic?" · topic "+r.topic:"")+(r.path&&r.path!=="/"?" · "+r.path:"")+(r.username?" · "+r.username:"");
}

/** Where the service lives: cloud, the network or machine of this server, or on premise through one of the owner's PCs. */
function PlaceField({form,setForm,places,placeLabel,t}:{form:Form;setForm:Dispatch<SetStateAction<Form|null>>;places:Place[];placeLabel:(p:Place)=>string;t:Translate}){
 const field="mt-1 w-full rounded border bg-transparent px-2 py-1";
 const allowed=places.filter(p=>form.kind==="network"?!agentOf(p):form.kind==="device"&&form.transport==="local"?p==="server":form.kind==="device"&&form.transport==="bluetooth"?p!=="cloud":true);
 function choose(place:Place){const agent=agentOf(place);setForm(f=>f&&{...f,place,
  ...(agent&&f.kind==="sqlserver"?{authentication:"password" as const}:{}),
  ...(agent&&f.transport==="local"?{transport:"serial" as const,device:""}:{}),
  ...(agent&&f.protocol==="matter"?{protocol:"mqtt"}:{}),
  ...(!agent&&f.transport==="serial"&&f.device.startsWith("COM")?{device:""}:{})});}
 return <label className="block text-sm md:col-span-2">{t("Dove si trova il servizio","Where the service is")}<select className={field} aria-label={t("Dove si trova il servizio","Where the service is")} value={form.place} onChange={e=>choose(e.target.value)}>
  {(allowed.includes(form.place)?allowed:[form.place,...allowed]).map(p=><option key={p} value={p}>{placeLabel(p)}</option>)}</select>
  {agentOf(form.place)&&form.kind!=="device"&&<span className="text-muted-foreground text-xs">{t("Il servizio è nella rete di quel PC (ufficio o casa): indica il suo indirizzo come lo vede quel PC, un IP privato o un nome interno (per esempio sql01.azienda.local). RigHaven Agent lo porta a questo server con un tunnel cifrato, solo mentre un incarico lo usa: nessuna porta da aprire.","The service is in that PC's network (office or home): give its address as that PC sees it, a private IP or an internal name (for example sql01.company.local). RigHaven Agent carries it to this server through an encrypted tunnel, only while a task uses it: no port to open.")}</span>}
  {places.length===2&&form.kind!=="network"&&<span className="text-muted-foreground block text-xs">{t("Per un servizio on premise di un’altra rete collega prima un PC di quella rete in «PC collegati (RigHaven Agent)».","For an on-premise service of another network first connect a PC of that network in “Connected PCs (RigHaven Agent)”.")}</span>}</label>;
}

/** A device or interface: on the network (MQTT, Modbus TCP, HTTP, TCP), a serial port shared over RFC 2217, or attached to this machine. */
function DeviceFields({form,setForm,devices,editing,t,input}:{form:Form;setForm:Dispatch<SetStateAction<Form|null>>;devices:string[];editing:boolean;t:Translate;input:FieldInput}){
 const agent=agentOf(form.place);
 const field="mt-1 w-full rounded border bg-transparent px-2 py-1";
 const set=(patch:Partial<Form>)=>setForm(f=>f&&{...f,...patch});
 const bauds=["1200","2400","4800","9600","19200","38400","57600","115200","230400","460800","921600"];
 return <>
  <label className="block text-sm md:col-span-2">{t("Come è collegato","How it is connected")}<select className={field} aria-label={t("Collegamento del dispositivo","Device transport")} value={form.transport} onChange={e=>set({transport:e.target.value as Transport,port:""})}>
   <option value="network">{t("In rete: MQTT, Modbus TCP, HTTP o TCP","On the network: MQTT, Modbus TCP, HTTP or TCP")}</option>
   <option value="serial">{agent?t("Porta COM del PC (scheda USB, adattatore seriale o Bluetooth)","COM port of the PC (USB board, serial or Bluetooth adapter)"):t("Porta seriale condivisa in rete (RFC 2217, per esempio ser2net o ESP-Link)","Serial port shared on the network (RFC 2217, for example ser2net or ESP-Link)")}</option>
   {form.place==="server"&&<option value="local">{t("Collegato a questa macchina (USB, seriale)","Attached to this machine (USB, serial)")}</option>}
   {form.place!=="cloud"&&<option value="bluetooth">{t("Bluetooth LE, tramite il Bluetooth del PC","Bluetooth LE, through the PC's Bluetooth")}</option>}</select></label>
  {agent&&<p className="text-muted-foreground text-xs md:col-span-2">{t("RigHaven Agent porta il servizio a questo server con un tunnel cifrato, solo quando un incarico lo usa. Le scritture restano approvate da te, una per una.","RigHaven Agent carries the service to this server through an encrypted tunnel, only while a task uses it. Writes are still approved by you, one by one.")}</p>}
  {agent&&form.transport==="serial"&&<label className="block text-sm">{t("Porta COM","COM port")}<input className={field} aria-label={t("Porta COM","COM port")} placeholder="COM5" value={form.device} onChange={e=>set({device:e.target.value.toUpperCase()})}/></label>}
  {form.transport==="bluetooth"&&<label className="block text-sm md:col-span-2">{t("Indirizzo Bluetooth","Bluetooth address")}<input className={field} aria-label={t("Indirizzo Bluetooth","Bluetooth address")} placeholder="38:A5:C9:3C:2E:9F" value={form.address} onChange={e=>set({address:e.target.value})}/>
   <span className="text-muted-foreground block text-xs">{t("Dalla ricerca Bluetooth qui sopra. Leggere il dispositivo è libero; ogni scrittura la approvi tu, una per una.","From the Bluetooth search above. Reading the device is free; you approve each write, one by one.")}</span></label>}
  {form.transport==="network"&&<>
   <label className="block text-sm">{t("Protocollo","Protocol")}<select className={field} aria-label={t("Protocollo","Protocol")} value={form.protocol} onChange={e=>set({protocol:e.target.value,port:""})}>
    <option value="mqtt">MQTT</option><option value="modbus-tcp">Modbus TCP</option><option value="http">HTTP</option>
    <option value="adb">{t("Android / Android TV (debug ADB in rete)","Android / Android TV (network ADB debugging)")}</option>
    <option value="tuya">{t("Tuya / Smart Life (protocollo locale)","Tuya / Smart Life (local protocol)")}</option>
    {!agent&&<option value="matter">{t("Matter (controller di RigHaven)","Matter (RigHaven controller)")}</option>}
    <option value="tcp">{t("TCP (righe di testo, adattatori OBD Wi-Fi)","TCP (text lines, Wi-Fi OBD adapters)")}</option></select></label>
   {form.protocol==="matter"&&<p className="text-muted-foreground text-xs md:col-span-2" data-testid="matter-hint">{form.node_id?t("Dispositivo Matter, nodo ","Matter device, node ")+form.node_id+t(", tramite il controller Matter di RigHaven. Ogni comando ti verrà chiesto nella scheda dell’incarico.",", through the RigHaven Matter controller. Every command is asked to you in the task card."):t("Crea la connessione dall’elenco «Dispositivi Matter» qui sopra.","Create the connection from the “Matter devices” list above.")}</p>}
   {form.protocol==="tuya"&&<p className="text-muted-foreground text-xs md:col-span-2" data-testid="tuya-hint">{t("Servono l’ID del dispositivo (app Smart Life → dispositivo → matita → Informazioni dispositivo → ID virtuale) e la sua local key, che si legge dal tuo account sulla piattaforma per sviluppatori Tuya (iot.tuya.com) dopo aver collegato l’app, oppure con lo strumento tinytuya wizard. Nulla passa dal cloud Tuya durante l’uso. Ogni comando (per esempio accendi o spegni) ti verrà chiesto nella scheda dell’incarico.","You need the device ID (Smart Life app → device → pencil → Device information → Virtual ID) and its local key, read from your account on the Tuya developer platform (iot.tuya.com) after linking the app, or with the tinytuya wizard tool. Nothing goes through the Tuya cloud during use. Every command (for example switch on or off) is asked to you in the task card.")}</p>}
   {form.protocol==="adb"&&<p className="text-muted-foreground text-xs md:col-span-2">{t("Sulla TV attiva Opzioni sviluppatore → Debug di rete (o Debug wireless) e annota l’indirizzo. Al primo uso la TV chiede di autorizzare RigHaven: scegli «Consenti sempre». Ogni installazione, rimozione, riavvio o aggiornamento ti verrà chiesto nella scheda dell’incarico.","On the TV enable Developer options → Network debugging (or Wireless debugging) and note the address. On first use the TV asks to authorize RigHaven: choose “Always allow”. Every install, removal, reboot or update is asked to you in the task card.")}</p>}
   {input("host",agent?t("Indirizzo come lo vede quel PC (IP privato o nome interno)","Address as that PC sees it (private IP or internal name)"):t("Indirizzo (host o IP)","Address (host or IP)"),{placeholder:agent?"192.168.1.40 · plc01.azienda.local":"broker.local · 192.168.1.40"})}
   {input("port",t("Porta","Port"),{placeholder:DEVICE_PORTS[form.protocol==="mqtt"&&form.tls?"mqtts":form.protocol==="http"&&form.tls?"https":form.protocol]??"",inputMode:"numeric"})}
   {form.protocol==="mqtt"&&input("topic",t("Topic da leggere","Topic to read"),{placeholder:"city/+/bus/#"})}
   {form.protocol==="http"&&input("path",t("Percorso","Path"),{placeholder:"/api/status"})}
   {form.protocol==="modbus-tcp"&&input("unit",t("Unità Modbus","Modbus unit"),{inputMode:"numeric"})}
   {form.protocol==="tuya"&&<>{input("username",t("ID dispositivo Tuya","Tuya device ID"),{placeholder:"bf1234567890abcdefgh"})}
   {input("password",t("Local key","Local key")+(editing?t(" (vuota = invariata)"," (empty = unchanged)"):""),{type:"password",autoComplete:"new-password"})}
   <label className="block text-sm">{t("Versione del protocollo","Protocol version")}<select className={field} aria-label={t("Versione del protocollo","Protocol version")} value={form.version} onChange={e=>set({version:e.target.value})}>
    {["3.3","3.4","3.5","3.1"].map(v=><option key={v} value={v}>{v}</option>)}</select></label></>}
   {form.protocol!=="adb"&&form.protocol!=="tcp"&&form.protocol!=="tuya"&&<>{input("username",t("Utente (facoltativo)","User (optional)"))}
   {input("password",t("Password (facoltativa)","Password (optional)")+(editing?t(" (vuota = invariata)"," (empty = unchanged)"):""),{type:"password",autoComplete:"new-password"})}</>}
   {form.protocol!=="modbus-tcp"&&form.protocol!=="tcp"&&form.protocol!=="adb"&&form.protocol!=="tuya"&&<label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.tls} onChange={e=>set({tls:e.target.checked,port:""})}/>{t("Connessione cifrata (TLS)","Encrypted connection (TLS)")}</label>}</>}
  {form.transport==="serial"&&!agent&&<>
   <label className="block text-sm md:col-span-2">{t("Tipo di server","Server type")}<select className={field} aria-label={t("Tipo di server seriale","Serial server type")} value={form.protocol==="socket"?"socket":"rfc2217"} onChange={e=>set({protocol:e.target.value})}>
    <option value="rfc2217">{t("RFC 2217 (ser2net, Raspberry Pi)","RFC 2217 (ser2net, Raspberry Pi)")}</option>
    <option value="socket">{t("TCP grezzo (porta COM condivisa dal PC)","Raw TCP (COM port shared by the PC)")}</option></select></label>
   {input("host",t("Server della porta seriale","Serial port server"),{placeholder:"raspberrypi.local"})}
   {input("port",t("Porta TCP del server","Server TCP port"),{placeholder:"4000",inputMode:"numeric"})}</>}
  {form.transport==="local"&&(devices.length?<label className="block text-sm">{t("Dispositivo","Device")}<select className={field} aria-label={t("Dispositivo","Device")} value={form.device} onChange={e=>set({device:e.target.value})}>
    <option value="">{t("Scegli…","Choose…")}</option>{devices.map(d=><option key={d} value={d}>{d}</option>)}</select></label>
   :<p className="text-muted-foreground text-xs md:col-span-2" data-testid="no-local-devices">{t("Nessuna porta seriale disponibile, quindi questa connessione non si può ancora salvare. Collega la periferica dal riquadro «Periferiche del PC» qui sopra (pulsante «Mostra periferiche USB»), poi riapri questo modulo. Per un dispositivo Wi-Fi scegli invece «In rete».","No serial port available, so this connection cannot be saved yet. Attach the peripheral from the “PC peripherals” panel above (“Show USB peripherals”), then reopen this form. For a Wi-Fi device choose “On the network” instead.")}</p>)}
  {(form.transport==="serial"||form.transport==="local")&&<label className="block text-sm">{t("Velocità (baud)","Speed (baud)")}<select className={field} aria-label={t("Velocità (baud)","Speed (baud)")} value={form.baud} onChange={e=>set({baud:e.target.value})}>{bauds.map(b=><option key={b} value={b}>{b}</option>)}</select></label>}
  <label className="block text-sm md:col-span-2">{t("Uso","Use")}<select className={field} aria-label={t("Uso della connessione","Connection use")} value={form.access} onChange={e=>set({access:e.target.value as "read"|"write"})}>
   <option value="read">{t("Solo lettura: osservare e registrare","Read-only: observe and record")}</option>
   <option value="write">{t("Anche scritture (comandi, firmware, app), ognuna approvata da te","Also writes (commands, firmware, apps), each approved by you")}</option></select></label>
  <p className="text-muted-foreground text-xs md:col-span-2">{t("I ruoli ricevono il dispositivo solo negli incarichi a cui lo assegni e solo se lo dichiarano. Leggere non richiede altro. Ogni scrittura (comando, firmware, app, riavvio, cancellazione dei codici OBD) ti viene chiesta nella scheda dell’incarico e viene eseguita una volta sola, esattamente come l’hai approvata. Un dispositivo collegato a questa macchina viene passato al contenitore in sola lettura senza il tuo consenso. Adattatori OBD Bluetooth: associali al computer, poi usali come porta seriale.","Roles receive the device only in tasks you assign it to, and only if they declare it. Reading needs nothing more. Every write (command, firmware, app, reboot, clearing OBD codes) is asked to you in the task card and runs once, exactly as you approved it. A device attached to this machine is passed to the container read-only without your consent. Bluetooth OBD adapters: pair them with the computer, then use them as a serial port.")}</p>
 </>;
}

/** Networks the owner may map: nothing outside these ranges is ever scanned. */
function NetworkFields({form,setForm,t,input}:{form:Form;setForm:Dispatch<SetStateAction<Form|null>>;t:Translate;input:FieldInput}){
 const field="mt-1 w-full rounded border bg-transparent px-2 py-1";
 const set=(patch:Partial<Form>)=>setForm(f=>f&&{...f,...patch});
 return <>
  {input("ranges",t("Reti da mappare (CIDR o indirizzi, separati da virgola)","Networks to map (CIDR or addresses, comma separated)"),{placeholder:"192.168.1.0/24, 10.0.5.20"})}
  {input("exclude",t("Indirizzi da escludere (facoltativo)","Addresses to exclude (optional)"),{placeholder:"192.168.1.1"})}
  <label className="block text-sm md:col-span-2">{t("Uso","Use")}<select className={field} aria-label={t("Uso della connessione","Connection use")} value={form.access} onChange={e=>set({access:e.target.value as "read"|"write"})}>
   <option value="read">{t("Solo mappatura: host, porte, servizi e mappa","Mapping only: hosts, ports, services and map")}</option>
   <option value="write">{t("Anche ricerca di vulnerabilità, ogni scansione approvata da te","Also vulnerability checks, each scan approved by you")}</option></select></label>
  <label className="flex items-start gap-2 text-sm md:col-span-2" data-testid="network-authorized"><input type="checkbox" checked={form.authorized} onChange={e=>set({authorized:e.target.checked})}/>
   <span>{t("Confermo che queste reti sono mie o che ho l’autorizzazione scritta a verificarle. Verificare reti altrui senza permesso è illegale.","I confirm these networks are mine or that I have written authorization to test them. Testing other people’s networks without permission is illegal.")}</span></label>
  <p className="text-muted-foreground text-xs md:col-span-2">{t("Le verifiche usano sonde TCP non privilegiate e controlli non intrusivi: niente attacchi, forza bruta o interruzioni di servizio. Sono ammesse solo reti private, salvo diversa impostazione dell’amministratore.","Checks use unprivileged TCP probes and non-intrusive checks: no attacks, brute force or service disruption. Only private networks are accepted unless the administrator allows otherwise.")}</p>
 </>;
}

type Found={address:string;ports:number[];name:string;kind:string;label:string;note?:string;mac?:string;vendor?:string;private_mac?:boolean;suggestion:{protocol:string;port:number}};
type Reading=number|boolean|{value:number;unit:string};
type Bluetooth={name:string;address:string;port:string;kind:string;paired:boolean;present?:boolean;signal?:number;connected?:boolean;maker?:string;maker_hint?:string;hint:string;sensor?:{format?:string;encrypted?:boolean;readings?:Record<string,Reading>}};
type SharedPort={name:string;label:string;host:string;port:number;hint:string};
type WifiNetwork={ssid:string;bssid:string;open:boolean;signal:number|null;hint:string};
type DiscoveryInfo={networks:string[];ports:number[];allowed:boolean;bluetooth:{scanned_at:string;devices:Bluetooth[];warnings?:string[]}|null;serial?:SharedPort[];wifi?:{scanned_at:string;networks:WifiNetwork[]}|null};

const btn="rounded border px-2 py-0.5 text-xs disabled:opacity-50";
/** The same actions on every result: Explore (read only), Create connection, and the setup step where one is needed. */
function Actions({children}:{children:ReactNode}){return <span className="ml-2 inline-flex flex-wrap gap-1 align-middle">{children}</span>;}

/** One address on the network, chosen by the owner: ports that answer, name, home page. Nothing is written. */
function NetExplorer({address,t,onCreate}:{address:string;t:Translate;onCreate?:(form:Form)=>void}){
 const base=getBackendBaseURL()+"/api/harness/connections/discovery/explore";
 const agent=useContext(PcContext);
 const [value,setValue]=useState<Found&{title?:string}|null>(null),[error,setError]=useState("");
 useEffect(()=>{let live=true;void fetch(base,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({address,...(agent?{agent}:{})})}).then(async r=>{const v=await r.json();
  if(!r.ok)throw Error(typeof v.detail==="string"?v.detail:String(r.status));if(live)setValue(v as Found);}).catch(e=>{if(live)setError(e instanceof Error?e.message:String(e));});return()=>{live=false;};},[base,address,agent]);
 return <div className="mt-2 space-y-1 rounded border p-2 text-xs" data-testid="net-explorer">
  {error?<p className="text-destructive">{error}</p>:!value?<p>{t("Leggo ","Reading ")}{address}…</p>:<>
   <p><strong>{value.label||address}</strong>{value.name?" · "+value.name:""}{value.title?" · «"+value.title+"»":""}</p>
   <p>{value.ports.length?t("Porte che rispondono: ","Ports answering: ")+value.ports.join(", "):t("Nessuna delle porte IoT note risponde.","None of the known IoT ports answers.")}</p>
   {onCreate&&value.suggestion&&<button type="button" className={btn} onClick={()=>onCreate({...blank("device"),name:(value.label||address).slice(0,80),transport:"network",host:address,protocol:value.suggestion.protocol,port:String(value.suggestion.port),topic:"#",path:"/"})}>{t("Crea connessione","Create connection")}</button>}</>}
 </div>;
}

/** Any Wi-Fi network the owner chooses: RigHaven for Windows joins it for a few seconds, reads what answers and goes back. */
function WifiExplorer({network,t,onCreate}:{network:WifiNetwork;t:Translate;onCreate:(form:Form)=>void}){
 const host=useHost();
 const [key,setKey]=useState(""),[busy,setBusy]=useState(false),[error,setError]=useState(""),[value,setValue]=useState<{title?:string;info?:string;address?:string}|null>(null);
 async function go(){setBusy(true);setError("");setValue(null);
  try{setValue(await host.ask("wifi-explore",{ssid:network.ssid,...(network.hint?{hint:network.hint}:{}),...(key?{key}:{})}) as {title?:string;info?:string;address?:string});}
  catch(e){setError(e instanceof Error?e.message:String(e));}finally{setKey("");setBusy(false);}}
 return <div className="mt-2 space-y-2 rounded border p-2 text-xs" data-testid="wifi-explorer">
  <p>{t("Il PC si collega a questa rete per qualche secondo, legge la pagina di chi risponde (il dispositivo o il router) e torna sulla rete di casa. Le reti già salvate in Windows usano il loro profilo.","The PC joins this network for a few seconds, reads the page of what answers (the device or the router) and goes back to the home network. Networks already saved in Windows use their own profile.")}</p>
  {!network.open&&<label className="block">{t("Password della rete (per un dispositivo è spesso sull’etichetta)","Network password (for a device it is often on its label)")}<input type="password" autoComplete="off" className="mt-1 block w-full rounded border bg-transparent px-2 py-1" aria-label={t("Password della rete","Network password")} value={key} onChange={e=>setKey(e.target.value)}/></label>}
  <button type="button" className={btn} disabled={busy||!host.can("wifi-explore")} onClick={()=>void go()}>{busy?t("Mi collego…","Joining…"):t("Collegati e leggi","Join and read")}</button>
  {!host.can("wifi-explore")&&<p>{t("Serve RigHaven per Windows aperto sul PC.","RigHaven for Windows must be open on the PC.")}</p>}
  {error&&<p className="text-destructive">{error}</p>}
  {value&&<><p>{value.address?value.address+" · ":""}{value.title?<strong>{value.title}</strong>:null}</p>{value.info&&<pre className="max-h-40 overflow-auto whitespace-pre-wrap break-all">{value.info}</pre>}
   {value.address&&<button type="button" className={btn} onClick={()=>onCreate({...blank("device"),name:[value.title,network.ssid].find(Boolean)!.slice(0,80),description:t("Sulla rete Wi-Fi ","On the Wi-Fi network ")+network.ssid,transport:"network",protocol:"http",host:value.address??"",port:"80",path:"/"})}>{t("Crea connessione","Create connection")}</button>}</>}
 </div>;
}

/** RigHaven Agent: the user's PCs that put their Bluetooth, Wi-Fi, COM ports and home network at the disposal of this server. */
function AgentsPanel({t,pc,setPc,onAgents}:{t:Translate;pc:string;setPc:(value:string)=>void;onAgents:(agents:Agent[])=>void}){
 const base=getBackendBaseURL()+"/api/harness/agents";
 const [rows,setRows]=useState<Agent[]|null>(null),[download,setDownload]=useState(""),[android,setAndroid]=useState(""),[server,setServer]=useState(""),[name,setName]=useState(""),[code,setCode]=useState<{code:string;expires:number}|null>(null);
 const [error,setError]=useState(""),[busy,setBusy]=useState(""),[confirm,setConfirm]=useState(""),[activity,setActivity]=useState<{at:string;agent:string;action:string;detail:string;status:string}[]|null>(null),[epoch,setEpoch]=useState(0);
 useEffect(()=>{let live=true;const load=()=>void fetch(base).then(r=>r.ok?r.json() as Promise<{agents:Agent[];download:string;android?:string;server:string}>:null).then(v=>{if(live&&v){setRows(v.agents);setDownload(v.download);setAndroid(v.android??"");setServer(v.server);onAgents(v.agents);}}).catch(()=>undefined);
  load();const timer=setInterval(load,code?4000:15000);return()=>{live=false;clearInterval(timer);};},[base,code,epoch]);// eslint-disable-line react-hooks/exhaustive-deps
 async function pair(){setBusy("pair");setError("");try{const r=await fetch(base+"/pairings",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name})});const v=await r.json();
  if(!r.ok)throw Error(typeof v.detail==="string"?v.detail:String(r.status));setCode({code:(v as {code:string}).code,expires:Date.now()+Number((v as {expires_in:number}).expires_in)*1000});}
  catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy("");}}
 async function revoke(id:string){if(confirm!==id){setConfirm(id);return;}setConfirm("");const r=await fetch(base+"/"+id,{method:"DELETE"});
  if(!r.ok){const v=await r.json();setError(typeof v.detail==="string"?v.detail:String(r.status));return;}if(pc===id)setPc("");setEpoch(n=>n+1);}
 async function showActivity(){if(activity){setActivity(null);return;}const r=await fetch(base+"/activity");if(r.ok)setActivity(((await r.json()) as {activity:typeof activity}).activity);}
 const paired=code&&rows?.some(a=>a.name===name&&a.online);
 return <section className="space-y-3 rounded-xl border p-4" data-testid="agents">
  <h2 className="font-semibold">{t("PC collegati (RigHaven Agent)","Connected PCs (RigHaven Agent)")}</h2>
  <p className="text-muted-foreground text-sm">{t("RigHaven Agent è un piccolo programma per Windows: mette Bluetooth, Wi-Fi, porte COM e rete di casa del tuo PC a disposizione di questo server, anche se il server è su un VPS. Il PC si collega lui al server: non serve aprire porte sul router.","RigHaven Agent is a small Windows program: it puts your PC's Bluetooth, Wi-Fi, COM ports and home network at the disposal of this server, even when the server is on a VPS. The PC connects to the server itself: no router port needs to be opened.")}</p>
  <label className="block text-sm">{t("Agisci sul PC","Act on the PC")}
   <select className="mt-1 block w-full rounded border bg-transparent px-2 py-1 md:w-96" aria-label={t("Agisci sul PC","Act on the PC")} value={pc} onChange={e=>setPc(e.target.value)}>
    <option value="">{t("Il PC su cui gira questo server (solo amministratori)","The PC this server runs on (administrators only)")}</option>
    {(rows??[]).map(a=><option key={a.id} value={a.id}>{a.name}{a.online?t(" · collegato"," · connected"):t(" · scollegato"," · offline")}</option>)}</select></label>
  {!!rows?.length&&<ul className="divide-y rounded border text-sm" data-testid="agent-list">{rows.map(a=><li key={a.id} className="flex flex-wrap items-center justify-between gap-2 p-2">
   <span><span className={"mr-2 inline-block h-2 w-2 rounded-full "+(a.online?"bg-green-600":"bg-gray-400")}/>{a.name} <span className="text-muted-foreground text-xs">· {a.platform??""}{a.version?" "+a.version:""}{a.online?t(" · collegato ora"," · connected now"):a.last_seen?t(" · ultimo contatto "," · last seen ")+a.last_seen.replace("T"," ").slice(0,16):""}</span>
    {a.compute&&<span className="text-muted-foreground block text-xs" data-testid="agent-compute">{t("Macchina di calcolo: ","Compute node: ")}{a.compute.cpus} CPU · {Math.round(a.compute.memory_mib/1024)} GiB · {a.compute.jobs} {t("incarichi alla volta","tasks at a time")} · Docker {a.compute.docker}{a.compute.running?t(" · in corso: "," · running: ")+String(a.compute.running):""}</span>}</span>
   <button type="button" className={"rounded border px-2 py-1 text-xs"+(confirm===a.id?" border-destructive text-destructive":"")} onClick={()=>void revoke(a.id)}>{confirm===a.id?t("Conferma revoca","Confirm revocation"):t("Revoca","Revoke")}</button></li>)}</ul>}
  {!code?<div className="flex flex-wrap items-end gap-2">
   <label className="text-sm">{t("Nome del PC da collegare","Name of the PC to connect")}<input className="mt-1 block w-56 rounded border bg-transparent px-2 py-1" aria-label={t("Nome del PC da collegare","Name of the PC to connect")} placeholder={t("PC di casa","Home PC")} value={name} onChange={e=>setName(e.target.value)}/></label>
   <button type="button" className="bg-primary text-primary-foreground rounded px-3 py-1 text-sm disabled:opacity-50" disabled={!name.trim()||busy==="pair"} onClick={()=>void pair()}>{t("Collega un PC","Connect a PC")}</button></div>
  :<div className="space-y-2 rounded border border-blue-500/30 bg-blue-500/5 p-3 text-sm" data-testid="agent-pairing" role="status">
   {paired?<p>{t("Fatto: «","Done: “")}{name}{t("» è collegato. Sceglilo in «Agisci sul PC» per usarlo.","” is connected. Choose it in “Act on the PC” to use it.")}</p>:<>
   <p>{t("1. Scarica ","1. Download ")}<a className="underline" href={download}>RigHaven-Agent-windows-x64.exe</a>{t(" e avvialo sul PC (al primo avvio Windows può mostrare l’avviso SmartScreen: «Ulteriori informazioni» → «Esegui comunque»)."," and start it on the PC (on first start Windows may show the SmartScreen warning: “More info” → “Run anyway”).")}
    {android&&<span className="block" data-testid="android-download">{t("Su un telefono Android: installa ","On an Android phone: install ")}<a className="underline" href={android}>RigHaven-android.apk</a>{t(" (consenti l’installazione da questa fonte), aprila e scrivi indirizzo e codice."," (allow installing from this source), open it and type the address and the code.")}</span>}</p>
   <p>{t("2. Quando lo chiede, scrivi l’indirizzo del server: ","2. When asked, type the server address: ")}<code className="rounded border px-1">{server}</code></p>
   <p>{t("3. Poi il codice: ","3. Then the code: ")}<code className="rounded border px-2 py-0.5 text-base font-semibold tracking-widest">{code.code}</code> {t("(vale 10 minuti, una sola volta)","(valid 10 minutes, once)")}</p>
   <p className="text-muted-foreground text-xs">{t("Questa pagina si aggiorna da sola quando il PC si collega.","This page updates by itself when the PC connects.")}</p></>}
   <button type="button" className="rounded border px-2 py-1 text-xs" onClick={()=>{setCode(null);setName("");}}>{paired?t("Chiudi","Close"):t("Annulla","Cancel")}</button></div>}
  <button type="button" className="text-xs underline" onClick={()=>void showActivity()}>{activity?t("Nascondi l’attività","Hide the activity"):t("Mostra l’attività dei PC collegati","Show the activity of connected PCs")}</button>
  {activity&&<ul className="max-h-48 overflow-auto text-xs" data-testid="agent-activity">{activity.map((a,i)=><li key={i}>{a.at.replace("T"," ").slice(0,19)} · {(rows??[]).find(r=>r.id===a.agent)?.name??a.agent} · {a.action} · {a.status}{a.detail?" · "+a.detail:""}</li>)}</ul>}
  {error&&<p className="text-destructive text-sm" role="alert">{error}</p>}
 </section>;
}

type Announced={address:string;names?:string[];services?:string[];server?:string;location?:string;kinds?:string[]};
type Talk={local:string;remote:string;name?:string;proto:string;port:number;packets:number;bytes:number};

/** Listening to the network (devices that announce themselves) and recording the PC's traffic (pktmon), both started by the owner. */
function NetworkTraffic({t,onCreate}:{t:Translate;onCreate:(form:Form)=>void}){
 const host=useHost();
 const [heard,setHeard]=useState<Announced[]|null>(null),[talks,setTalks]=useState<{packets:number;conversations:Talk[];dns?:string[];download?:boolean}|null>(null);
 const [seconds,setSeconds]=useState("60"),[busy,setBusy]=useState(""),[error,setError]=useState(""),[open,setOpen]=useState("");
 async function go(key:string,action:string,args:Record<string,string>,after:(v:Record<string,unknown>)=>void){setBusy(key);setError("");
  try{after(await host.ask(action,args));}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy("");}}
 if(!host.can("net-listen")&&!host.can("traffic-capture"))return null;
 const size=(n:number)=>n>1048576?(n/1048576).toFixed(1)+" MB":n>1024?(n/1024).toFixed(0)+" kB":n+" B";
 return <div className="space-y-2 border-t pt-3" data-testid="network-traffic">
  <h3 className="text-sm font-semibold">{t("Ascolta e registra la rete","Listen to and record the network")}</h3>
  <p className="text-muted-foreground text-xs">{t("«Ascolta la rete» trova i dispositivi che si presentano da soli (mDNS/Bonjour, UPnP), anche se non rispondono alla ricerca. «Registra il traffico» registra per un tempo limitato il traffico del PC con pktmon di Windows (Windows chiede il permesso di amministratore) e riassume chi parla con chi.","“Listen to the network” finds the devices that announce themselves (mDNS/Bonjour, UPnP), even if they answer no search. “Record the traffic” records the PC's traffic for a limited time with Windows' pktmon (Windows asks for administrator rights) and summarises who talks with whom.")}</p>
  <div className="flex flex-wrap items-center gap-2">
   {host.can("net-listen")&&<button type="button" className={btn} disabled={!!busy} onClick={()=>void go("listen","net-listen",{},v=>setHeard((v.devices as Announced[]|null)??[]))}>{busy==="listen"?t("Ascolto…","Listening…"):t("Ascolta la rete","Listen to the network")}</button>}
   {host.can("traffic-capture")&&<><select className="rounded border bg-transparent px-1 py-0.5 text-xs" aria-label={t("Durata della registrazione","Recording length")} value={seconds} onChange={e=>setSeconds(e.target.value)}>
     {["30","60","120","300","600","1800"].map(v=><option key={v} value={v}>{Number(v)<120?v+" s":String(Number(v)/60)+" min"}</option>)}</select>
    <button type="button" className={btn} disabled={!!busy} onClick={()=>void go("capture","traffic-capture",{seconds},v=>setTalks(v as typeof talks))}>{busy==="capture"?t("Registro… (conferma il permesso di Windows)","Recording… (confirm Windows' prompt)"):t("Registra il traffico","Record the traffic")}</button></>}
  </div>
  <details className="text-xs"><summary className="cursor-pointer">{t("Per vedere il traffico di un dispositivo (per esempio verso il suo cloud)","To see the traffic of one device (for example to its cloud)")}</summary>
   <p className="mt-1">{t("La scheda Wi-Fi del PC riceve solo il traffico diretto al PC. Attiva l’Hotspot mobile di Windows (Impostazioni → Rete e Internet → Hotspot mobile), collega il dispositivo a quella rete, poi premi «Registra il traffico» e usa il dispositivo: tutto il suo traffico passa dal PC.","The PC's Wi-Fi adapter only receives traffic addressed to the PC. Turn on Windows' Mobile hotspot (Settings → Network & Internet → Mobile hotspot), connect the device to it, then press “Record the traffic” and use the device: all its traffic passes through the PC.")}</p></details>
  {error&&<p className="text-destructive text-xs">{error}</p>}
  {heard&&(heard.length===0?<p className="text-xs">{t("Nessun dispositivo si è presentato.","No device announced itself.")}</p>
   :<ul className="space-y-1 text-sm" data-testid="announced">{heard.map(d=><li key={d.address}><strong>{d.names?.[0]??d.address}</strong> · {d.address}{d.server?" · "+d.server:""}
     <span className="text-muted-foreground block text-xs">{[...(d.kinds??[]),...(d.services??[]).slice(0,6)].join(" · ")}</span>
     <Actions><button type="button" className={btn} onClick={()=>setOpen(open===d.address?"":d.address)}>{t("Esplora","Explore")}</button>
      <button type="button" className={btn} onClick={()=>onCreate({...blank("device"),name:(d.names?.[0]??d.address).slice(0,80),description:[d.server,...(d.services??[])].filter(Boolean).join(" · ").slice(0,400),transport:"network",protocol:"http",host:d.address,port:"80",path:"/"})}>{t("Crea connessione","Create connection")}</button></Actions>
     {open===d.address&&<NetExplorer address={d.address} t={t}/>}</li>)}</ul>)}
  {talks&&<div className="space-y-1 text-xs" data-testid="traffic-summary">
   <p>{talks.packets} {t("pacchetti","packets")}{talks.download&&<> · <a className="underline" href={withAgent(getBackendBaseURL()+"/api/harness/connections/discovery/capture.pcapng",host.agent)} download>{t("Scarica la registrazione (.pcapng, per Wireshark)","Download the recording (.pcapng, for Wireshark)")}</a></>}</p>
   <table className="w-full text-left"><thead><tr><th>{t("Dal PC / dispositivo","From the PC / device")}</th><th>{t("Verso","To")}</th><th>{t("Servizio","Service")}</th><th>{t("Traffico","Traffic")}</th></tr></thead>
    <tbody>{talks.conversations.slice(0,30).map(c=><tr key={c.local+c.remote+c.proto+c.port}><td>{c.local}</td><td className="break-all">{c.name?c.name+" ("+c.remote+")":c.remote}</td><td>{c.proto}{c.port?" "+c.port:""}</td><td>{size(c.bytes)} · {c.packets}</td></tr>)}</tbody></table>
   {!!talks.dns?.length&&<p className="text-muted-foreground">{t("Nomi cercati: ","Names looked up: ")}{talks.dns.slice(0,20).join(", ")}</p>}
  </div>}
 </div>;
}

/** Find devices without knowing their address: the PC's network (TCP connection attempts to a few IoT
 * ports, started by the owner) and the Bluetooth devices the launcher saw. Nothing is written to devices. */
function DeviceDiscovery({base,t,onCreate}:{base:string;t:(a:string,b:string)=>string;onCreate:(form:Form)=>void}){
 const [exploring,setExploring]=useState("");
 const [info,setInfo]=useState<DiscoveryInfo|null>(null),[network,setNetwork]=useState(""),[busy,setBusy]=useState(false);
 const [found,setFound]=useState<Found[]|null>(null),[error,setError]=useState(""),[scanning,setScanning]=useState(false),[epoch,setEpoch]=useState(0);
 const host=useHost();
 const [wifiBusy,setWifiBusy]=useState(false);
 const [setup,setSetup]=useState<{ssid:string;hint:string}|null>(null),[home,setHome]=useState(""),[secret,setSecret]=useState(""),[setupBusy,setSetupBusy]=useState(false),[setupDone,setSetupDone]=useState("");
 const SETUP=["tasmota","shelly","esp","wled","openbeken"];
 async function provision(){if(!setup)return;setSetupBusy(true);setError("");setSetupDone("");
  try{const v=await host.ask("wifi-provision",{ssid:setup.ssid,hint:setup.hint,password:secret,home});
   setSetupDone(t("Fatto: ","Done: ")+setup.ssid+t(" si sta collegando a "," is joining ")+(typeof v.home==="string"?v.home:home)+t(". Tra qualche secondo premi «Cerca in questa rete» per trovarlo e crearne la connessione."," . In a few seconds press “Search this network” to find it and create its connection."));setSetup(null);}
  catch(e){setError(e instanceof Error?e.message:String(e));}finally{setSecret("");setSetupBusy(false);}}
 async function scanWifi(){setWifiBusy(true);setError("");try{await host.ask("wifi-scan");setEpoch(n=>n+1);}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setWifiBusy(false);}}
 const wifiHints:Record<string,[string,string]>={
  tuya:["Dispositivo Tuya / Smart Life in modalità di configurazione: aggiungilo al Wi-Fi di casa con l’app Smart Life, poi cercalo in rete qui sopra.","Tuya / Smart Life device in setup mode: add it to the home Wi-Fi with the Smart Life app, then find it on the network above."],
  tasmota:["Tasmota non configurato: collega il PC a questa rete, apri http://192.168.4.1 e inserisci il Wi-Fi di casa; poi cercalo in rete qui sopra.","Tasmota not set up: connect the PC to this network, open http://192.168.4.1 and enter the home Wi-Fi; then find it on the network above."],
  shelly:["Shelly non configurato: collegati a questa rete e apri http://192.168.33.1 per inserire il Wi-Fi di casa.","Shelly not set up: connect to this network and open http://192.168.33.1 to enter the home Wi-Fi."],
  openbeken:["OpenBeken non configurato: collegati a questa rete e apri http://192.168.4.1 per inserire il Wi-Fi di casa.","OpenBeken not set up: connect to this network and open http://192.168.4.1 to enter the home Wi-Fi."],
  wled:["WLED non configurato: collegati a questa rete (password wled1234) e apri http://4.3.2.1.","WLED not set up: connect to this network (password wled1234) and open http://4.3.2.1."],
  esp:["Scheda ESP / ESPHome nella rete di emergenza: collegati a questa rete e apri http://192.168.4.1 per inserire il Wi-Fi di casa.","ESP / ESPHome board on its fallback network: connect to this network and open http://192.168.4.1 to enter the home Wi-Fi."],
  daikin:["Condizionatore Daikin (adattatore Wi-Fi) in configurazione: aggiungilo al Wi-Fi di casa con l’app Daikin; poi RigHaven lo trova in rete (porta 80) e lo legge via HTTP. Per esplorarlo qui serve la chiave scritta sull’etichetta dell’adattatore.","Daikin air conditioner (Wi-Fi adapter) in setup mode: add it to the home Wi-Fi with the Daikin app; RigHaven then finds it on the network (port 80) and reads it over HTTP. Exploring it here needs the key on the adapter label."],
  lg:["Condizionatore LG ThinQ in configurazione: si aggiunge con l’app LG ThinQ e si comanda dal cloud LG (anche da Alexa e SmartThings), non in locale.","LG ThinQ air conditioner in setup mode: it is added with the LG ThinQ app and controlled through the LG cloud (also from Alexa and SmartThings), not locally."],
  direct:["Wi-Fi Direct di una stampante o di una TV.","Wi-Fi Direct of a printer or a TV."]};
 async function scanBluetooth(){setScanning(true);setError("");try{await host.ask("bluetooth-scan");setEpoch(n=>n+1);}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setScanning(false);}}
 const agent=useContext(PcContext);
 useEffect(()=>{let live=true;void fetch(withAgent(base+"/discovery",agent)).then(r=>r.ok?r.json() as Promise<DiscoveryInfo>:null).then(v=>{if(live&&v){setInfo(v);setNetwork(n=>n||(v.networks[0]??""));}}).catch(()=>undefined);return()=>{live=false;};},[base,epoch,agent]);
 async function search(){setBusy(true);setError("");setFound(null);
  try{
   // Every device of the PC's network answers the PC's ARP, whatever its ports: the launcher lists them with their MAC.
   const all=host.can("lan-devices")?host.ask("lan-devices").catch(()=>({devices:[]})):Promise.resolve({devices:[]});
   // Through an agent the search runs on the PC or phone (about a minute on a phone): it is started
   // and followed, never one request that a proxy would cut after 30 seconds.
   const r=agent?await fetch(base+"/discovery/identify",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({devices:(await host.ask("net-scan",{network})).devices??[]})})
    :await fetch(base+"/discovery",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({network})});
   const v=await r.json().catch(()=>({detail:t("Il server non ha risposto in tempo: riprova","The server did not answer in time: try again")}));
   if(!r.ok)throw Error(typeof v.detail==="string"?v.detail:String(r.status));
   const byPort=(v as {devices:Found[]}).devices;
   const lan=((await all).devices as {address:string;mac:string;vendor?:string;private_mac?:boolean}[]|undefined)??[];
   const merged=byPort.map(d=>{const n=lan.find(x=>x.address===d.address);return n?{...d,mac:n.mac,vendor:n.vendor,private_mac:n.private_mac}:d;});
   for(const n of lan)if(!merged.some(d=>d.address===n.address))merged.push({address:n.address,ports:[],name:"",kind:"present",
    label:n.vendor??(n.private_mac?t("Telefono, tablet o PC (indirizzo MAC privato)","Phone, tablet or PC (private MAC address)"):t("Dispositivo presente","Device present")),
    mac:n.mac,vendor:n.vendor,private_mac:n.private_mac,suggestion:{protocol:"tcp",port:80}});
   const num=(a:string)=>a.split(".").reduce((x,y)=>x*256+Number(y),0);
   setFound(merged.sort((a,b)=>num(a.address)-num(b.address)));}
  catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}}
 const create=(d:Found)=>onCreate({...blank("device"),name:d.label.slice(0,80),description:d.name?d.name.slice(0,400):"",transport:"network",place:agent||"server",host:d.address,
  protocol:d.suggestion.protocol,port:String(d.suggestion.port),topic:"#",path:"/"});
 const hints:Record<string,[string,string]>={
  obd:["Adattatore OBD-II: associalo in Windows, poi condividi la sua porta COM da «Periferiche del PC» e crea la connessione da «Porte seriali condivise».","OBD-II adapter: pair it in Windows, then share its COM port from “PC peripherals” and create the connection from “Serial ports shared”."],
  tuya:["Tuya/Smart Life: se ha anche il Wi-Fi, cercalo in rete qui sopra.","Tuya/Smart Life: if it also has Wi-Fi, find it on the network above."],
  esp32:["Scheda ESP32: collegala via USB da «Periferiche del PC» per leggerla o programmarla.","ESP32 board: attach it over USB from “PC peripherals” to read or program it."],
  xiaomi:["Sensore Xiaomi: trasmette dati Bluetooth LE; RigHaven non li legge ancora direttamente.","Xiaomi sensor: it broadcasts Bluetooth LE data; RigHaven does not read it directly yet."],
  shelly:["Shelly: ha anche il Wi-Fi, cercalo in rete qui sopra.","Shelly: it also has Wi-Fi, find it on the network above."],
  tv:["TV: per Android TV usa la rete (debug ADB via Wi-Fi).","TV: for Android TV use the network (ADB debugging over Wi-Fi)."]};
 const quantity=(key:string)=>({temperature:t("temperatura","temperature"),humidity:t("umidità","humidity"),battery:t("batteria","battery"),voltage:t("tensione","voltage"),
  pressure:t("pressione","pressure"),illuminance:t("luce","light"),motion:t("movimento","motion"),door:t("porta","door"),window:t("finestra","window"),opening:t("apertura","opening"),co2:"CO₂"} as Record<string,string>)[key]??key;
 return <section className="space-y-3 rounded-xl border p-4" data-testid="device-discovery">
  <h2 className="font-semibold">{t("Trova dispositivi","Find devices")}</h2>
  <p className="text-muted-foreground text-sm">{t("Non conosci l’indirizzo del dispositivo? Prese, lampadine, telecomandi IR e sensori Wi-Fi usano l’USB solo per l’alimentazione: si trovano in rete, sul Wi-Fi a cui sono collegati.","Don’t know the device’s address? Wi-Fi plugs, bulbs, IR remotes and sensors use USB only for power: they are found on the network, on the Wi-Fi they are connected to.")}</p>
  <div className="flex flex-wrap items-end gap-2">
   <label className="text-sm">{t("Rete da cercare","Network to search")}
    <input className="mt-1 block w-48 rounded border bg-transparent px-2 py-1" list="rh-local-networks" aria-label={t("Rete da cercare","Network to search")} placeholder="192.168.1.0/24" value={network} onChange={e=>setNetwork(e.target.value)}/>
    <datalist id="rh-local-networks">{(info?.networks??[]).map(n=><option key={n} value={n}/>)}</datalist></label>
   <button type="button" className="rounded border px-3 py-2 text-sm disabled:opacity-50" disabled={busy||!network.trim()} onClick={()=>void search()}>{busy?t("Ricerca in corso (fino a un minuto)…","Searching (up to a minute)…"):t("Cerca in questa rete","Search this network")}</button>
  </div>
  <p className="text-muted-foreground text-xs" data-testid="discovery-consent">{info?.networks.length?t("Rete del PC rilevata dal launcher. ","PC network detected by the launcher. "):t("Scrivi la rete del tuo Wi-Fi (di solito 192.168.1.0/24 o 192.168.0.0/24). ","Write your Wi-Fi network (usually 192.168.1.0/24 or 192.168.0.0/24). ")}
   {t("RigHaven prova solo ad aprire una connessione alle porte ","RigHaven only tries to open a connection to ports ")}{(info?.ports??[]).join(", ")}{t(" di ogni indirizzo e legge la pagina iniziale di chi risponde: nulla viene modificato. Cerca solo nelle reti tue o autorizzate."," of each address and reads the home page of those that answer: nothing is changed. Search only networks you own or are authorized for.")}</p>
  {error&&<p className="text-destructive text-sm" role="alert">{error}</p>}
  {found&&(found.length===0?<p className="text-sm" data-testid="discovery-empty">{t("Nessun dispositivo ha risposto. Controlla che sia acceso e collegato allo stesso Wi-Fi del PC.","No device answered. Check that it is on and connected to the same Wi-Fi as the PC.")}</p>
   :<ul className="divide-y rounded border" data-testid="discovery-results">{found.map(d=><li key={d.address} className="flex flex-wrap items-center justify-between gap-2 p-2 text-sm">
    <span><strong>{d.label}</strong> · {d.address}{d.name?` (${d.name})`:""} · {d.ports.length?t("porte ","ports ")+d.ports.join(", "):t("nessuna porta aperta","no open port")}{d.mac?" · MAC "+d.mac+(d.vendor&&d.label!==d.vendor?" ("+d.vendor+")":""):""}
     {d.note&&d.kind!=="tuya"&&<span className="text-muted-foreground block text-xs">{d.note}</span>}
     {d.kind==="tuya"&&<span className="text-muted-foreground block text-xs">{t("Protocollo locale Tuya: crea la connessione e inserisci ID dispositivo e local key (dal tuo account Tuya/Smart Life); poi RigHaven può leggerlo e comandarlo.","Tuya local protocol: create the connection and enter the device ID and local key (from your Tuya/Smart Life account); RigHaven can then read and control it.")}</span>}</span>
    <Actions><button type="button" className={btn} onClick={()=>setExploring(exploring==="net:"+d.address?"":"net:"+d.address)}>{t("Esplora","Explore")}</button>
     <button type="button" className={btn} onClick={()=>create(d)}>{t("Crea connessione","Create connection")}</button></Actions>
    {exploring==="net:"+d.address&&<div className="w-full"><NetExplorer address={d.address} t={t}/></div>}</li>)}</ul>)}
  {!!info?.serial?.length&&<div className="space-y-1 border-t pt-3" data-testid="shared-serial">
   <h3 className="text-sm font-semibold">{t("Porte seriali condivise dal PC","Serial ports shared by the PC")}</h3>
   <ul className="space-y-1 text-sm">{info.serial.map(p=><li key={p.name} className="flex flex-wrap items-center justify-between gap-2">
    <span>{p.label||p.name}{p.hint==="obd"?t(" · adattatore OBD-II"," · OBD-II adapter"):""}</span>
    <button type="button" className="rounded border px-2 py-1 text-xs" onClick={()=>onCreate({...blank("device"),name:(p.hint==="obd"?"OBD ":"")+p.name,description:p.label.slice(0,400),transport:"serial",protocol:"socket",host:p.host,port:String(p.port)})}>{t("Crea connessione","Create connection")}</button></li>)}</ul>
  </div>}
  <NetworkTraffic t={t} onCreate={onCreate}/>
  <div className="space-y-1 border-t pt-3" data-testid="wifi-discovery">
   <h3 className="text-sm font-semibold">{t("Reti Wi-Fi vicine","Nearby Wi-Fi networks")}</h3>
   <p className="text-muted-foreground text-xs">{t("I dispositivi non ancora configurati creano una propria rete Wi-Fi: RigHaven la riconosce e, per Tasmota, Shelly, ESPHome, WLED e OpenBeken, li porta nel Wi-Fi di casa con «Porta nel Wi-Fi di casa». La ricerca non collega il PC a nessuna rete.","Devices not set up yet open their own Wi-Fi network: RigHaven recognizes it and, for Tasmota, Shelly, ESPHome, WLED and OpenBeken, adds them to the home Wi-Fi with “Add to the home Wi-Fi”. The search does not connect the PC to any network.")}</p>
   {info?.wifi?.networks.length?<>
    <ul className="space-y-1 text-sm" data-testid="wifi-setup">{info.wifi.networks.filter(n=>n.hint).map(n=><li key={n.bssid+n.ssid}>{n.ssid} · {n.signal??"?"}% · {n.open?t("🔓 aperta","🔓 open"):t("🔒 protetta","🔒 protected")}
     {wifiHints[n.hint]&&<span className="text-muted-foreground block text-xs">{t(wifiHints[n.hint]![0],wifiHints[n.hint]![1])}</span>}
     <Actions><button type="button" className={btn} onClick={()=>setExploring(exploring==="wifi:"+n.ssid?"":"wifi:"+n.ssid)}>{t("Esplora","Explore")}</button>
     {SETUP.includes(n.hint)&&host.can("wifi-provision")&&setup?.ssid!==n.ssid&&<button type="button" className={btn} onClick={()=>{setSetup({ssid:n.ssid,hint:n.hint});setSetupDone("");}}>{t("Porta nel Wi-Fi di casa","Add to the home Wi-Fi")}</button>}</Actions>
     {exploring==="wifi:"+n.ssid&&<WifiExplorer network={n} t={t} onCreate={onCreate}/>}
     {setup?.ssid===n.ssid&&<div className="mt-2 space-y-2 rounded border p-2 text-xs" data-testid="wifi-provision">
      <p>{t("RigHaven collega il PC per qualche secondo alla rete del dispositivo, gli passa il Wi-Fi di casa e torna sulla rete di casa. La password serve solo per questa operazione: non viene salvata.","RigHaven joins the device's network for a few seconds, gives it the home Wi-Fi and goes back to the home network. The password is used only for this: it is not saved.")}</p>
      <label className="block">{t("Rete di casa","Home network")}<input className="mt-1 block w-full rounded border bg-transparent px-2 py-1" aria-label={t("Rete di casa","Home network")} placeholder={t("quella a cui è collegato il PC","the one the PC is on")} value={home} onChange={e=>setHome(e.target.value)}/></label>
      <label className="block">{t("Password del Wi-Fi di casa","Home Wi-Fi password")}<input type="password" autoComplete="off" className="mt-1 block w-full rounded border bg-transparent px-2 py-1" aria-label={t("Password del Wi-Fi di casa","Home Wi-Fi password")} value={secret} onChange={e=>setSecret(e.target.value)}/></label>
      <div className="flex gap-2"><button type="button" className="bg-primary text-primary-foreground rounded px-3 py-1 disabled:opacity-50" disabled={setupBusy||secret.length<8} onClick={()=>void provision()}>{setupBusy?t("Configuro…","Setting up…"):t("Configura","Set up")}</button>
       <button type="button" className="rounded border px-3 py-1" onClick={()=>{setSetup(null);setSecret("");}}>{t("Annulla","Cancel")}</button></div></div>}</li>)}</ul>
    {setupDone&&<p className="text-xs" role="status" data-testid="wifi-provision-done">{setupDone}</p>}
    {!info.wifi.networks.some(n=>n.hint)&&<p className="text-muted-foreground text-xs">{t("Nessun dispositivo in modalità di configurazione.","No device in setup mode.")}</p>}
    <details className="text-xs"><summary className="cursor-pointer">{t("Altre reti","Other networks")} ({info.wifi.networks.filter(n=>!n.hint).length})</summary>
     <ul className="mt-1 space-y-1">{info.wifi.networks.filter(n=>!n.hint).map(n=><li key={n.bssid+n.ssid}>{n.ssid||t("(nascosta)","(hidden)")} · {n.signal??"?"}% · {n.open?t("🔓 aperta","🔓 open"):t("🔒 protetta","🔒 protected")}
      {n.ssid&&<Actions><button type="button" className={btn} onClick={()=>setExploring(exploring==="wifi:"+n.ssid?"":"wifi:"+n.ssid)}>{t("Esplora","Explore")}</button></Actions>}
      {exploring==="wifi:"+n.ssid&&<WifiExplorer network={n} t={t} onCreate={onCreate}/>}</li>)}</ul></details></>
   :null}
   {host.can("wifi-scan")&&<button type="button" className="rounded border px-3 py-1 text-xs disabled:opacity-50" disabled={wifiBusy} onClick={()=>void scanWifi()}>{wifiBusy?t("Ricerca delle reti Wi-Fi…","Searching Wi-Fi networks…"):t("Cerca reti Wi-Fi","Search Wi-Fi networks")}</button>}
  </div>
  <div className="space-y-1 border-t pt-3" data-testid="bluetooth-discovery">
   <h3 className="text-sm font-semibold">Bluetooth</h3>
   {info?.bluetooth?.warnings?.map(w=><p key={w} className="text-xs text-amber-700" data-testid="bluetooth-warning">{w.startsWith("readings: ")?t("Letture dei sensori Bluetooth LE non disponibili su questo PC: ","Bluetooth LE sensor readings not available on this PC: ")+w.slice(10)
     :w.startsWith("devices: ")?t("Ricerca dei dispositivi Bluetooth vicini e associati non riuscita: ","Search for nearby and paired Bluetooth devices failed: ")+w.slice(9):w}</p>)}
   {info?.bluetooth?.devices.length?<>
    <p className="text-muted-foreground text-xs">{t("Ultima ricerca del PC: ","Last search on the PC: ")}{new Date(info.bluetooth.scanned_at).toLocaleString()}</p>
    {(()=>{const rows=info.bluetooth.devices.filter((d,i,all)=>!d.address||d.port||all.findIndex(x=>!x.port&&x.address.toUpperCase()===d.address.toUpperCase())===i);
     const row=(d:Bluetooth)=><li key={d.kind+d.address+d.port+d.name}>{d.name||t("(senza nome)","(no name)")}{d.maker?<span title={d.maker_hint}> · {d.maker}{d.name?"":<span className="text-muted-foreground"> ({d.maker_hint})</span>}</span>:null} · {d.port||d.address} · {d.connected?<strong>{t("collegato ora","connected now")}</strong>:d.paired?t("associato (non collegato ora)","paired (not connected now)"):t("vicino ora","nearby now")}{d.signal!==undefined&&<span className="text-muted-foreground" title={d.signal+" dBm"}> · {d.signal>=-60?t("segnale forte","strong signal"):d.signal>=-80?t("segnale medio","medium signal"):t("segnale debole (lontano)","weak signal (far)")} ({d.signal} dBm)</span>}
     {d.address&&!d.port&&<Actions><button type="button" className={btn} onClick={()=>setExploring(exploring==="bt:"+d.address.toUpperCase()?"":"bt:"+d.address.toUpperCase())}>{t("Esplora","Explore")}</button>
      <button type="button" className={btn} onClick={()=>onCreate({...blank("device"),name:(d.name||"Bluetooth "+d.address.slice(-5)).slice(0,80),transport:"bluetooth",address:d.address.toUpperCase()})}>{t("Crea connessione","Create connection")}</button></Actions>}
     {exploring==="bt:"+d.address.toUpperCase()&&<BleExplorer address={d.address.toUpperCase()} t={t}/>}
     {d.hint&&hints[d.hint]&&<span className="text-muted-foreground block text-xs">{t(hints[d.hint]![0],hints[d.hint]![1])}</span>}
     {d.sensor?.readings&&<span className="block text-xs" data-testid="ble-readings">{d.sensor.format}: {Object.entries(d.sensor.readings).map(([k,v])=>`${quantity(k)} ${typeof v==="object"?`${v.value} ${v.unit}`:String(v)}`).join(" · ")}</span>}
     {d.sensor?.encrypted&&<span className="text-muted-foreground block text-xs">{d.sensor.format}: {t("dati cifrati: per leggerli serve la bind key del sensore, oppure un firmware aperto (pvvx, BTHome).","encrypted data: reading it needs the sensor’s bind key, or an open firmware (pvvx, BTHome).")}</span>}</li>;
     const old=rows.filter(d=>d.present===false);
     // The nearest first; anonymous devices (no name, an address that changes for privacy: phones, earbuds, PCs) folded below.
     const heard=rows.filter(d=>d.present!==false).sort((a,b)=>(b.signal??-200)-(a.signal??-200));
     const known=heard.filter(d=>d.name!==""||d.paired||d.connected===true||d.sensor!==undefined||d.port!==""),anonymous=heard.filter(d=>!known.includes(d));
     return <><ul className="space-y-1 text-sm">{known.map(row)}</ul>
      {anonymous.length>0&&<details className="text-sm" data-testid="bluetooth-anonymous"><summary className="cursor-pointer text-xs">{t("Altri dispositivi anonimi vicini","Other anonymous nearby devices")} ({anonymous.length}) · {t("senza nome, con indirizzo che cambia per privacy (telefoni, auricolari, orologi, PC); anche dei vicini","no name, with an address that changes for privacy (phones, earbuds, watches, PCs); neighbours' too")}</summary>
       <ul className="mt-1 space-y-1">{anonymous.map(row)}</ul></details>}
      {old.length>0&&<details className="text-sm" data-testid="bluetooth-remembered"><summary className="cursor-pointer text-xs">{host.state?.platform==="android"?t("Associati al telefono, non sentiti ora","Paired with the phone, not heard now"):t("Ricordati da Windows, non sentiti ora","Remembered by Windows, not heard now")} ({old.length})</summary>
       <ul className="mt-1 space-y-1">{old.map(row)}</ul></details>}</>;})()}
    {info.bluetooth.devices.some(d=>d.sensor?.readings)&&<a className="text-xs underline" href={withAgent(base+"/discovery/ble-history.csv",agent)} download>{t("Scarica lo storico delle letture (CSV)","Download the readings history (CSV)")}</a>}</>
   :<p className="text-muted-foreground text-xs">{t("Nessuna ricerca Bluetooth ancora: premi «Cerca dispositivi Bluetooth».","No Bluetooth search yet: press “Search Bluetooth devices”.")}</p>}
   {host.can("bluetooth-scan")&&<button type="button" className="rounded border px-3 py-1 text-xs disabled:opacity-50" disabled={scanning} onClick={()=>void scanBluetooth()}>{scanning?t("Ricerca Bluetooth e lettura dei sensori (circa 40 s)…","Searching Bluetooth and reading sensors (about 40 s)…"):t("Cerca dispositivi Bluetooth","Search Bluetooth devices")}</button>}
   {!host.state?.connected&&<p className="text-muted-foreground text-xs">{t("Il Bluetooth lo cerca RigHaven sul PC: tieni aperta la finestra di RigHaven e ricarica la pagina.","RigHaven searches Bluetooth on the PC: keep the RigHaven window open and reload the page.")}</p>}
  </div>
 </section>;
}

type MatterReading={value:number|boolean|string;unit?:string;endpoint:number};
type MatterNode={node_id:number;available:boolean;name:string;vendor:string;product:string;readings:Record<string,MatterReading>;switchable:number[]};
type MatterInfo={available:boolean;reachable?:boolean;error?:string;url?:string;nodes:MatterNode[]};

/** Matter devices through the optional RigHaven Matter controller: join a device shared from another app with
 * its pairing code, see its state, switch it on or off, and create a connection for tasks. */
function MatterDevices({t,onCreate}:{t:(a:string,b:string)=>string;onCreate:(form:Form)=>void}){
 const base=getBackendBaseURL()+"/api/harness/matter";
 const [info,setInfo]=useState<MatterInfo|null>(null),[code,setCode]=useState(""),[busy,setBusy]=useState(""),[error,setError]=useState(""),[reload,setReload]=useState(0),[confirming,setConfirming]=useState(false);
 const pc=useHost();
 async function enableMatter(){if(!confirming){setConfirming(true);return;}setBusy("matter");setError("");
  try{await pc.ask("matter-enable");
   // RigHaven restarts: wait until the page answers again with the controller on.
   for(let i=0;i<90;i++){await new Promise(r=>setTimeout(r,4000));try{const r=await fetch(base);if(r.ok){const v=await r.json() as MatterInfo;if(v.available){setInfo(v);return;}}}catch{/* restarting */}}
   setError(t("RigHaven non è ancora tornato: ricarica la pagina tra poco.","RigHaven is not back yet: reload the page shortly."));}
  catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy("");setConfirming(false);}}
 useEffect(()=>{let live=true;void fetch(base).then(r=>r.ok?r.json() as Promise<MatterInfo>:null).then(v=>{if(live)setInfo(v);}).catch(()=>undefined);return()=>{live=false;};},[base,reload]);
 async function post(path:string,body:unknown,key:string){setBusy(key);setError("");
  try{const r=await fetch(base+path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});const v=await r.json();
   if(!r.ok)throw Error(typeof v.detail==="string"?v.detail:String(r.status));setReload(n=>n+1);return true;}
  catch(e){setError(e instanceof Error?e.message:String(e));return false;}finally{setBusy("");}}
 const host=(info?.url??"ws://172.30.42.1:5580/ws").replace(/^ws:\/\//,"").split("/")[0]??"";
 const create=(n:MatterNode)=>onCreate({...blank("device"),name:n.name.slice(0,80),description:[n.vendor,n.product].filter(Boolean).join(" ").slice(0,400),transport:"network",protocol:"matter",
  host:host.split(":")[0]??"",port:host.split(":")[1]??"5580",node_id:String(n.node_id)});
 const show=(v:MatterReading)=>typeof v.value==="boolean"?(v.value?t("sì","yes"):t("no","no")):`${String(v.value)}${v.unit?" "+v.unit:""}`;
 if(!info)return null;
 return <section className="space-y-3 rounded-xl border p-4" data-testid="matter-devices">
  <h2 className="font-semibold">{t("Dispositivi Matter","Matter devices")}</h2>
  {!info.available?<div className="space-y-2" data-testid="matter-off">
   <p className="text-muted-foreground text-sm">{t("Il controller Matter è spento. Attivandolo RigHaven imposta la rete «mirrored» di WSL (necessaria per vedere i dispositivi Matter, vale per tutto WSL), aggiunge una regola al firewall per il traffico Matter (Windows chiede il permesso una volta) e si riavvia da solo.","The Matter controller is off. Turning it on, RigHaven sets WSL “mirrored” networking (needed to see Matter devices, it applies to all of WSL), adds a firewall rule for Matter traffic (Windows asks permission once) and restarts by itself.")}</p>
   {pc.can("matter-enable")?<button type="button" className="rounded border px-3 py-2 text-sm disabled:opacity-50" disabled={!!busy} onClick={()=>void enableMatter()}>{busy==="matter"?t("Attivazione e riavvio di RigHaven…","Turning on and restarting RigHaven…"):confirming?t("Conferma: attiva e riavvia","Confirm: turn on and restart"):t("Attiva Matter","Turn on Matter")}</button>
   :<p className="text-muted-foreground text-xs">{t("Disponibile nella versione per PC di RigHaven (Windows 11 o Linux) con la finestra di RigHaven aperta.","Available in the PC version of RigHaven (Windows 11 or Linux) with the RigHaven window open.")}</p>}
   {error&&<p className="text-destructive text-sm" role="alert">{error}</p>}
  </div>:<>
  {info.reachable===false&&<p className="text-destructive text-sm" role="alert">{info.error}</p>}
  <p className="text-muted-foreground text-sm">{t("Aggiungi un dispositivo già configurato in Alexa, SmartThings, Google Home o Apple Casa: nell’app scegli «Condividi con altri hub/servizi» (o «Abilita abbinamento») e inserisci qui il codice di 11 cifre. Il dispositivo continua a funzionare anche nell’altra app.","Add a device already set up in Alexa, SmartThings, Google Home or Apple Home: in the app choose “Share with other hubs/services” (or “Turn on pairing mode”) and enter the 11-digit code here. The device keeps working in the other app.")}</p>
  <div className="flex flex-wrap items-end gap-2">
   <label className="text-sm">{t("Codice di abbinamento","Pairing code")}<input className="mt-1 block w-56 rounded border bg-transparent px-2 py-1" aria-label={t("Codice di abbinamento Matter","Matter pairing code")} placeholder="3497-011-2332" value={code} onChange={e=>setCode(e.target.value)}/></label>
   <button type="button" className="rounded border px-3 py-2 text-sm disabled:opacity-50" disabled={!!busy||!code.trim()} onClick={()=>void post("/commission",{code},"commission").then(ok=>{if(ok)setCode("");})}>{busy==="commission"?t("Abbinamento (fino a 3 minuti)…","Pairing (up to 3 minutes)…"):t("Aggiungi dispositivo Matter","Add Matter device")}</button>
  </div>
  {error&&<p className="text-destructive text-sm" role="alert">{error}</p>}
  {info.nodes.length===0?<p className="text-muted-foreground text-sm">{t("Nessun dispositivo Matter ancora.","No Matter device yet.")}</p>
  :<ul className="divide-y rounded border" data-testid="matter-nodes">{info.nodes.map(n=><li key={n.node_id} className="flex flex-wrap items-center justify-between gap-2 p-2 text-sm">
   <span><strong>{n.name}</strong>{n.vendor||n.product?` · ${[n.vendor,n.product].filter(Boolean).join(" ")}`:""} · {t("nodo","node")} {n.node_id}{n.available?"":t(" · non raggiungibile"," · unreachable")}
    {Object.keys(n.readings).length>0&&<span className="text-muted-foreground block text-xs">{Object.entries(n.readings).map(([k,v])=>`${k} ${show(v)}`).join(" · ")}</span>}</span>
   <span className="flex flex-wrap gap-1">
    {n.switchable.slice(0,1).map(e=>["On","Off"].map(c=><button key={e+c} type="button" className="rounded border px-2 py-1 text-xs disabled:opacity-50" disabled={!!busy||!n.available} onClick={()=>void post(`/nodes/${n.node_id}/command`,{endpoint:e,command:c},"cmd-"+n.node_id)}>{c==="On"?t("Accendi","On"):t("Spegni","Off")}</button>))}
    <button type="button" className="rounded border px-2 py-1 text-xs" onClick={()=>create(n)}>{t("Crea connessione","Create connection")}</button></span></li>)}</ul>}
  </>}
 </section>;
}

type HostState={connected:boolean;platform:string;actions:string[];matter?:boolean};
type HostJob={status:string;result?:Record<string,unknown>};

/** Actions on the PC (Bluetooth, USB, COM ports, Matter) carried out by the RigHaven launcher, which is
 * running next to RigHaven: the page asks, the launcher acts and answers. */
function useHost(){
 const base=getBackendBaseURL()+"/api/harness/host";
 const agent=useContext(PcContext);
 const [state,setState]=useState<HostState|null>(null);
 useEffect(()=>{let live=true;const load=()=>void fetch(withAgent(base,agent)).then(r=>r.ok?r.json() as Promise<HostState>:null).then(v=>{if(live&&v)setState(v);}).catch(()=>undefined);
  load();const timer=setInterval(load,10000);return()=>{live=false;clearInterval(timer);};},[base,agent]);
 async function ask(action:string,args:Record<string,string>={}):Promise<Record<string,unknown>>{
  const r=await fetch(base+"/requests",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action,args,...(agent?{agent}:{})})});const v=await r.json();
  if(!r.ok)throw Error(typeof v.detail==="string"?v.detail:String(r.status));
  const id=(v as {id:string}).id;const deadline=Date.now()+300000;
  while(Date.now()<deadline){await new Promise(done=>setTimeout(done,1500));
   const job=await (await fetch(`${base}/requests/${id}`)).json() as HostJob;
   if(job.status==="done")return job.result??{};
   if(job.status==="failed")throw Error(String((job.result as {error?:string}|undefined)?.error??"failed"));}
  throw Error("timeout");}
 return {state,ask,agent,can:(action:string)=>!!state?.connected&&state.actions.includes(action)};
}

type GattService={uuid:string;characteristics:{uuid:string;properties?:string[];value?:string;text?:string;error?:string}[]};
/** Well-known Bluetooth names, so a list of UUIDs means something to the owner. */
const GATT_NAMES:Record<string,[string,string]>={"1800":["Accesso generico","Generic access"],"1801":["Attributi generici","Generic attribute"],"180a":["Informazioni sul dispositivo","Device information"],
 "180f":["Batteria","Battery"],"2a00":["Nome","Name"],"2a19":["Livello batteria","Battery level"],"2a24":["Modello","Model"],"2a25":["Numero di serie","Serial number"],"2a26":["Firmware","Firmware"],
 "2a27":["Hardware","Hardware"],"2a28":["Software","Software"],"2a29":["Produttore","Manufacturer"],"181a":["Sensori ambientali","Environmental sensing"],"2a6e":["Temperatura","Temperature"],"2a6f":["Umidità","Humidity"],
 "fe95":["Xiaomi","Xiaomi"],"fd50":["Tuya","Tuya"],"a201":["Tuya","Tuya"],"ffe0":["Seriale BLE (HM-10 e simili)","BLE serial (HM-10 and similar)"],"ffe1":["Dati seriali","Serial data"]};
const gattName=(uuid:string,t:Translate)=>{const short=/^0000([0-9a-f]{4})-0000-1000-8000-00805f9b34fb$/.exec(uuid)?.[1];const name=short?GATT_NAMES[short]:undefined;return name?t(name[0],name[1])+" ("+short+")":short??uuid;};

/** What a Bluetooth LE device offers: services, characteristics and the values that can be read. Reading only. */
function BleExplorer({address,t}:{address:string;t:Translate}){
 const host=useHost();
 const [result,setResult]=useState<{name:string;services:GattService[]}|null>(null),[error,setError]=useState(""),[busy,setBusy]=useState(false);
 async function inspect(){setBusy(true);setError("");try{setResult(await host.ask("ble-inspect",{address}) as {name:string;services:GattService[]});}catch(e){setError(String((e as Error).message));}finally{setBusy(false);}}
 return <div className="mt-3 space-y-2 rounded border p-3" data-testid="ble-explorer">
  {!host.can("ble-inspect")&&<p className="text-xs">{t("Serve RigHaven per Windows aperto sul PC: è lui che usa il Bluetooth del PC.","RigHaven for Windows must be open on the PC: it uses the PC's Bluetooth.")}</p>}
  <button type="button" className="rounded border px-3 py-1 text-xs disabled:opacity-50" disabled={busy||!host.can("ble-inspect")} onClick={()=>void inspect()}>{busy?t("Mi collego al dispositivo…","Connecting to the device…"):t("Leggi servizi e valori","Read services and values")}</button>
  {error&&<p className="text-destructive text-xs">{error}</p>}
  {result&&<><p className="text-sm font-semibold">{result.name||address}</p>
   {result.services.length===0?<p className="text-xs">{t("Il dispositivo non espone servizi leggibili.","The device exposes no readable services.")}</p>
   :<ul className="space-y-2 text-xs">{result.services.map(sv=><li key={sv.uuid}><strong>{gattName(sv.uuid,t)}</strong>
     <ul className="ml-3 space-y-0.5">{sv.characteristics.map(c=><li key={c.uuid} className="break-all">{gattName(c.uuid,t)} · {(c.properties??[]).join(", ")}{c.text?<> · <strong>{c.text}</strong></>:c.value?<> · <code>{c.value}</code></>:null}{c.error?" · "+c.error:""}</li>)}</ul></li>)}</ul>}
   <p className="text-muted-foreground text-xs">{t("Per comandarlo chiedilo nella chat: ogni scrittura la approvi tu nella scheda del compito. Molti dispositivi commerciali cifrano i comandi con chiavi del produttore.","To command it ask in the chat: you approve each write in the task card. Many commercial devices encrypt their commands with vendor keys.")}</p></>}
 </div>;
}

/** USB-serial chips and boards by VID:PID: what the peripheral probably is and whether RigHaven can program it (esptool). */
const USB_CHIPS:[RegExp,string,string,boolean][]=[
 [/^10c4:ea6[03]/,"Silicon Labs CP210x (USB-seriale, tipico delle schede ESP32/ESP8266)","Silicon Labs CP210x (USB-serial, typical of ESP32/ESP8266 boards)",true],
 [/^1a86:(7523|55d4|55d3)/,"WCH CH340/CH9102 (USB-seriale, tipico delle schede ESP e Arduino compatibili)","WCH CH340/CH9102 (USB-serial, typical of ESP and Arduino-compatible boards)",true],
 [/^303a:/,"Espressif ESP32-S2/S3/C3/C6 con USB nativo","Espressif ESP32-S2/S3/C3/C6 with native USB",true],
 [/^0403:60(01|10|14|15)/,"FTDI (USB-seriale)","FTDI (USB-serial)",true],
 [/^(2341|2a03):/,"Arduino","Arduino",false],[/^2e8a:/,"Raspberry Pi Pico (RP2040/RP2350): si aggiorna copiando il file .uf2","Raspberry Pi Pico (RP2040/RP2350): updated by copying the .uf2 file",false],
 [/^0483:df11/,"STM32 in modalità DFU","STM32 in DFU mode",false],[/^1915:/,"Nordic nRF (dongle o scheda)","Nordic nRF (dongle or board)",false]];
const usbChip=(vidpid:string|undefined,t:Translate)=>{const found=USB_CHIPS.find(([pattern])=>pattern.test((vidpid??"").toLowerCase()));
 return found?{label:t(found[1],found[2]),flash:found[3]}:null;};

type UsbItem={busid:string;vidpid?:string;name:string;state:string;serial:boolean;attached:boolean;pc_bluetooth?:boolean};
type ComItem={name:string;label:string;bluetooth:boolean;shared:boolean};

/** USB peripherals and COM ports of the PC, attached or shared with RigHaven by the launcher. */
type NfcTag={id:string;technologies:string[];chip?:string;sak?:number;ndef?:{type:string;max_size:number;writable:boolean};records?:{kind:string;text?:string;uri?:string;type?:string;size?:number;data?:string}[]};
function PcDevices({t,onChanged,onCreate}:{t:(a:string,b:string)=>string;onChanged:()=>void;onCreate:(form:Form)=>void}){
 const host=useHost();
 const [ports,setPorts]=useState<Record<string,string[]>>({}),[open,setOpen]=useState("");
 const [all,setAll]=useState<{class:string;name:string;bus:string;ok:boolean;vidpid?:string;busid?:string;address?:string;chip?:string}[]|null>(null);
 async function createShared(name:string){
  if(host.agent){onCreate({...blank("device",host.agent),name,transport:"serial",device:name,baud:"38400"});return;}
  const info=await (await fetch(getBackendBaseURL()+"/api/harness/connections/discovery")).json() as DiscoveryInfo;
  const shared=(info.serial??[]).find(p=>p.name===name);
  if(!shared){setError(t("La porta è condivisa ma RigHaven non la vede ancora: riprova tra qualche secondo.","The port is shared but RigHaven does not see it yet: try again in a few seconds."));return;}
  onCreate({...blank("device"),name:(shared.hint==="obd"?"OBD ":"")+shared.name,description:shared.label.slice(0,400),transport:"serial",protocol:"socket",host:shared.host,port:String(shared.port)});}
 const [usb,setUsb]=useState<UsbItem[]|null>(null),[usbipd,setUsbipd]=useState(true),[com,setCom]=useState<ComItem[]|null>(null);
 const [busy,setBusy]=useState(""),[error,setError]=useState(""),[notice,setNotice]=useState("");
 async function run(key:string,action:string,args:Record<string,string>={},after?:(v:Record<string,unknown>)=>void){
  setBusy(key);setError("");setNotice("");
  try{const v=await host.ask(action,args);after?.(v);}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy("");}}
 const listUsb=(v:Record<string,unknown>)=>{setUsbipd(v.usbipd!==false);setUsb((v.devices as UsbItem[]|undefined)??[]);};
 const [tag,setTag]=useState<NfcTag|null>(null);
 if(!host.state?.platform)return null;
 const phone=host.state.platform==="android";
 return <section className="space-y-3 rounded-xl border p-4" data-testid="pc-devices">
  <h2 className="font-semibold">{phone?t("Periferiche del telefono","Phone peripherals"):t("Periferiche del PC","PC peripherals")}</h2>
  {phone&&host.state.connected&&<p className="text-muted-foreground text-sm" data-testid="phone-peripherals">{t("Quello che il telefono vede adesso: schede e adattatori collegati alla porta USB-C (OTG), dispositivi Bluetooth associati, NFC, infrarossi, sensori. Con «Leggi un tag NFC» avvicini un tag al telefono e RigHaven ne legge tipo e contenuto, senza scrivere nulla.","What the phone sees now: boards and adapters plugged into its USB-C port (OTG), paired Bluetooth devices, NFC, infrared, sensors. With “Read an NFC tag” you hold a tag to the phone and RigHaven reads its type and content, writing nothing.")}</p>}
  {host.can("nfc-read")&&<div className="space-y-2" data-testid="nfc-read">
   <button type="button" className="rounded border px-3 py-2 text-sm disabled:opacity-50" disabled={!!busy} onClick={()=>void run("nfc","nfc-read",{},v=>setTag(v as NfcTag))}>{busy==="nfc"?t("Avvicina il tag al telefono (tocca la notifica per aprire RigHaven)…","Hold the tag to the phone (tap the notification to open RigHaven)…"):t("Leggi un tag NFC","Read an NFC tag")}</button>
   {tag&&<dl className="rounded border p-2 text-xs" data-testid="nfc-tag"><div><strong>{tag.chip??t("Tag NFC","NFC tag")}</strong> · ID {tag.id}</div><div>{tag.technologies.join(" · ")}{tag.sak!==undefined?" · SAK "+tag.sak:""}{tag.ndef?" · NDEF "+tag.ndef.type+" · "+tag.ndef.max_size+" B"+(tag.ndef.writable?"":t(" · sola lettura"," · read only")):""}</div>
    {(tag.records??[]).map((r,i)=><div key={i} className="break-all">{r.kind==="uri"&&/^https?:\/\/[^/]+/.test(r.uri??"")&&<button type="button" className={btn+" mr-2"} onClick={()=>{const url=new URL(r.uri!);onCreate({...blank("device"),name:("NFC "+url.hostname).slice(0,80),description:("Link letto dal tag NFC "+tag.id+": "+r.uri).slice(0,400),transport:"network",protocol:"http",host:url.hostname,port:url.port!==""?url.port:(url.protocol==="https:"?"443":"80"),path:url.pathname||"/"});}}>{t("Crea connessione","Create connection")}</button>}{r.kind==="text"?t("Testo","Text")+": "+r.text:r.kind==="uri"?t("Link","Link")+": "+r.uri:r.kind==="mime"?(r.type+" · "+r.size+" B"+(r.text?": "+r.text:"")):(r.type??r.kind)+(r.data?": "+r.data:"")}</div>)}
    {tag.ndef&&!(tag.records??[]).length&&<div>{t("Nessun contenuto NDEF.","No NDEF content.")}</div>}</dl>}
  </div>}
  {!host.state.connected?<p className="text-muted-foreground text-sm">{phone?t("Il telefono non risponde: apri l’app RigHaven e controlla che l’agente sia attivo.","The phone does not answer: open the RigHaven app and check the agent is active."):t("RigHaven sul PC non risponde: tieni aperta la finestra di RigHaven, poi ricarica la pagina.","RigHaven on the PC does not answer: keep the RigHaven window open, then reload the page.")}</p>:<>
  {!phone&&<p className="text-muted-foreground text-sm">{t("Collega a RigHaven le periferiche USB (adattatori seriali, schede, adattatori OBD) e condividi le porte COM (per esempio un adattatore OBD Bluetooth associato in Windows). Windows può chiedere il permesso la prima volta.","Attach USB peripherals (serial adapters, boards, OBD adapters) to RigHaven and share COM ports (for example a Bluetooth OBD adapter paired in Windows). Windows may ask for permission the first time.")}</p>}
  <div className="flex flex-wrap gap-2">
   {host.can("usb-list")&&<button type="button" className="rounded border px-3 py-2 text-sm disabled:opacity-50" disabled={!!busy} onClick={()=>void run("usb","usb-list",{},listUsb)}>{busy==="usb"?t("Cerco…","Searching…"):t("Mostra periferiche USB","Show USB peripherals")}</button>}
   {host.can("com-list")&&<button type="button" className="rounded border px-3 py-2 text-sm disabled:opacity-50" disabled={!!busy} onClick={()=>void run("com","com-list",{},v=>setCom((v.ports as ComItem[]|undefined)??[]))}>{busy==="com"?t("Cerco…","Searching…"):t("Mostra porte COM","Show COM ports")}</button>}
   {host.can("refresh-devices")&&<button type="button" className="rounded border px-3 py-2 text-sm disabled:opacity-50" disabled={!!busy} onClick={()=>void run("refresh","refresh-devices",{},()=>{setNotice(t("Porte seriali aggiornate.","Serial ports refreshed."));onChanged();})}>{busy==="refresh"?t("Aggiorno…","Refreshing…"):t("Aggiorna porte seriali","Refresh serial ports")}</button>}
  </div>
  {!usbipd&&<div className="space-y-1 text-sm" data-testid="usbipd-missing"><p>{t("Per collegare periferiche USB serve un componente gratuito di Windows (usbipd-win).","Attaching USB peripherals needs a free Windows component (usbipd-win).")}</p>
   <button type="button" className="rounded border px-3 py-1 text-xs disabled:opacity-50" disabled={!!busy} onClick={()=>void run("usb-install","usb-install",{},listUsb)}>{busy==="usb-install"?t("Installazione…","Installing…"):t("Installa il componente USB","Install the USB component")}</button></div>}
  {usb&&usbipd&&(usb.length===0?<p className="text-sm">{t("Nessuna periferica USB collegata al PC.","No USB peripheral plugged into the PC.")}</p>
   :<ul className="divide-y rounded border" data-testid="usb-list">{usb.map(d=><li key={d.busid} className="flex flex-wrap items-center justify-between gap-2 p-2 text-sm">
    <span>{d.name}{d.serial?t(" · porta seriale"," · serial port"):""}<Actions><button type="button" className={btn} onClick={()=>setOpen(open==="usb:"+d.busid?"":"usb:"+d.busid)}>{t("Esplora","Explore")}</button></Actions></span>
    {d.attached?<span className="flex items-center gap-2 text-xs">{t("collegata a RigHaven","attached to RigHaven")}
      <button type="button" className="rounded border px-2 py-1 text-xs disabled:opacity-50" disabled={!!busy} onClick={()=>void run("detach-"+d.busid,"usb-detach",{busid:d.busid},()=>{
       setNotice(t("Restituita a Windows: ","Given back to Windows: ")+d.name);setUsb(list=>(list??[]).map(x=>x.busid===d.busid?{...x,attached:false}:x));onChanged();})}>{busy==="detach-"+d.busid?t("Restituisco…","Giving back…"):t("Restituisci a Windows","Give back to Windows")}</button></span>
     :d.pc_bluetooth?<span className="flex flex-wrap items-center gap-2 text-xs" data-testid="usb-pc-bluetooth">{t("Bluetooth del PC: se lo colleghi, Windows perde il Bluetooth finché non lo restituisci","PC Bluetooth: attached, Windows loses Bluetooth until you give it back")}
      <button type="button" className={btn} disabled={!!busy} onClick={()=>void run("attach-"+d.busid,"usb-attach",{busid:d.busid,confirm:"yes"},()=>{setNotice(t("Collegato: Windows non ha più il Bluetooth finché non premi «Restituisci a Windows».","Attached: Windows has no Bluetooth until you press “Give back to Windows”."));
       setUsb(list=>(list??[]).map(x=>x.busid===d.busid?{...x,attached:true}:x));onChanged();})}>{t("Collega comunque","Attach anyway")}</button></span>
     :<button type="button" className="rounded border px-2 py-1 text-xs disabled:opacity-50" disabled={!!busy} onClick={()=>void run("attach-"+d.busid,"usb-attach",{busid:d.busid},v=>{
       const ports=(v.ports as string[]|undefined)??[];setNotice(ports.length?t("Collegata: ","Attached: ")+ports.join(", "):t("Collegata, ma non è una porta seriale.","Attached, but it is not a serial port."));setPorts(p=>({...p,[d.busid]:ports}));
       setUsb(list=>(list??[]).map(x=>x.busid===d.busid?{...x,attached:true}:x));onChanged();})}>{busy==="attach-"+d.busid?t("Collego…","Attaching…"):t("Collega a RigHaven","Attach to RigHaven")}</button>}
    {open==="usb:"+d.busid&&<dl className="w-full rounded border p-2 text-xs" data-testid="usb-details"><div>busid {d.busid}{d.vidpid?" · VID:PID "+d.vidpid:""}</div><div>{t("Stato in Windows: ","State in Windows: ")}{d.state}</div>
     {usbChip(d.vidpid,t)&&<div><strong>{usbChip(d.vidpid,t)!.label}</strong>{usbChip(d.vidpid,t)!.flash?t(" · RigHaven può leggerne il chip e aggiornarne il firmware ESP (esptool), con la tua approvazione"," · RigHaven can read its chip and update its ESP firmware (esptool), with your approval"):t(" · RigHaven non sa ancora aggiornarne il firmware"," · RigHaven cannot update its firmware yet")}</div>}
     <div>{d.pc_bluetooth?t("È l’adattatore Bluetooth del PC.","It is the PC's Bluetooth adapter."):d.serial?t("Porta seriale: dopo «Collega a RigHaven» la leggi e la programmi da una connessione.","Serial port: after “Attach to RigHaven” you read and program it from a connection."):t("Non sembra una porta seriale: collegata a RigHaven, la vedono gli strumenti che la sanno usare.","It does not look like a serial port: attached to RigHaven, tools that know it can use it.")}</div></dl>}
    {(ports[d.busid]??[]).map(port=><button key={port} type="button" className="rounded border px-2 py-1 text-xs" onClick={()=>onCreate({...blank("device"),name:d.name.replace(/\s*\(COM\d+\)/,"").slice(0,80),transport:"local",device:port,
     description:("USB "+d.busid+(d.vidpid?" · VID:PID "+d.vidpid:"")+" · "+d.name+(usbChip(d.vidpid,t)?" · "+usbChip(d.vidpid,t)!.label:"")).slice(0,400)})}>{t("Crea connessione su ","Create connection on ")+port}</button>)}</li>)}</ul>)}
  {com&&(com.length===0?<p className="text-sm">{t("Nessuna porta COM. Per un adattatore Bluetooth associalo prima nelle impostazioni Bluetooth di Windows.","No COM port. For a Bluetooth adapter pair it first in the Windows Bluetooth settings.")}</p>
   :<ul className="divide-y rounded border" data-testid="com-list">{com.map(p=><li key={p.name} className="flex flex-wrap items-center justify-between gap-2 p-2 text-sm">
    <span>{p.label||p.name}{p.bluetooth?" · Bluetooth":""}<Actions><button type="button" className={btn} onClick={()=>setOpen(open==="com:"+p.name?"":"com:"+p.name)}>{t("Esplora","Explore")}</button>
     {p.shared&&<button type="button" className={btn} onClick={()=>void createShared(p.name)}>{t("Crea connessione","Create connection")}</button>}</Actions></span>
    {open==="com:"+p.name&&<p className="w-full rounded border p-2 text-xs" data-testid="com-details">{p.name} · {p.label}{p.bluetooth?t(" · porta di un dispositivo Bluetooth associato (per esempio un adattatore OBD-II)"," · port of a paired Bluetooth device (for example an OBD-II adapter)"):""} · {p.shared?t("condivisa con RigHaven mentre è aperto","shared with RigHaven while it runs"):t("non condivisa","not shared")}</p>}
    {p.shared?<span className="text-xs">{t("condivisa","shared")}</span>
     :<button type="button" className="rounded border px-2 py-1 text-xs disabled:opacity-50" disabled={!!busy} onClick={()=>void run("share-"+p.name,"com-share",{name:p.name},()=>{
       setNotice(t("Porta condivisa: ora puoi crearne la connessione.","Port shared: you can now create its connection."));setCom(list=>(list??[]).map(x=>x.name===p.name?{...x,shared:true}:x));onChanged();})}>{busy==="share-"+p.name?t("Condivido…","Sharing…"):t("Condividi con RigHaven","Share with RigHaven")}</button>}</li>)}</ul>)}
  {host.can("pc-devices")&&<button type="button" className="rounded border px-3 py-1 text-sm disabled:opacity-50" disabled={!!busy} onClick={()=>void run("pc-devices","pc-devices",{},v=>setAll((v.devices as typeof all)??[]))}>{busy==="pc-devices"?(phone?t("Leggo i dispositivi del telefono…","Reading the phone's devices…"):t("Leggo Gestione dispositivi…","Reading Device Manager…")):(phone?t("Mostra tutti i dispositivi del telefono","Show all the phone's devices"):t("Mostra tutti i dispositivi del PC","Show all the PC's devices"))}</button>}
  {all&&<div className="space-y-2 text-sm" data-testid="pc-all-devices">
   <p className="text-muted-foreground text-xs">{phone?t("Tutto quello che il telefono vede adesso. Un oggetto collegato all’USB-C solo per l’alimentazione non compare: non scambia dati con il telefono. I nomi di alcune periferiche USB compaiono solo dopo il permesso di Android: gli identificativi (VID:PID) ci sono sempre.","Everything the phone sees now. Something plugged into USB-C only for power does not appear: it exchanges no data with the phone. Some USB peripherals show their name only after Android's permission: their IDs (VID:PID) are always there."):t("Tutto quello che Windows vede adesso (Gestione dispositivi, solo i dispositivi presenti). Un oggetto collegato all’USB solo per l’alimentazione (molti telecomandi IR, prese, lampade) non compare: non scambia dati con il PC e si trova in rete o via Bluetooth.","Everything Windows sees now (Device Manager, present devices only). Something plugged into USB only for power (many IR remotes, plugs, lamps) does not appear: it exchanges no data with the PC and is found on the network or over Bluetooth.")}</p>
   {(["usb","bluetooth","internal","system"] as const).map(bus=>{const rows=all.filter(d=>d.bus===bus);return rows.length?<details key={bus} open={bus==="usb"}><summary className="cursor-pointer font-semibold">{bus==="usb"?(phone?t("USB-C (OTG)","USB-C (OTG)"):t("USB","USB")):bus==="bluetooth"?(phone?t("Bluetooth associati","Paired Bluetooth"):t("Bluetooth","Bluetooth")):bus==="internal"?(phone?t("Nel telefono","In the phone"):t("Interni al PC","Inside the PC")):(phone?t("Telefono e rete","Phone and network"):t("Componenti di Windows","Windows components"))} ({rows.length})</summary>
    <ul className="mt-1 space-y-0.5 text-xs">{rows.map(d=><li key={d.class+d.name}>{d.name} <span className="text-muted-foreground">· {d.class}{d.vidpid?" · "+d.vidpid:""}{d.chip?" · "+d.chip:""}</span>
     {phone&&bus==="bluetooth"&&d.address&&<button type="button" className={btn+" ml-2"} onClick={()=>onCreate({...blank("device"),name:d.name.slice(0,80),transport:"bluetooth",address:d.address!.toUpperCase()})}>{t("Crea connessione","Create connection")}</button>}
     {phone&&bus==="usb"&&d.class==="Ports"&&<span className="text-muted-foreground"> · {t("scheda seriale: il telefono la riconosce; usarla dal server tramite il telefono arriverà in un passo successivo (oggi: collegala a un PC con RigHaven Agent)","serial board: the phone recognizes it; using it from the server through the phone comes in a later step (today: plug it into a PC with RigHaven Agent)")}</span>}{!d.ok&&<span className="text-amber-700"> · {bus==="bluetooth"?t("servizio del dispositivo associato senza driver in Windows: RigHaven può usarlo dalla sua porta COM o dalla rete (vedi sotto)","service of the paired device with no Windows driver: RigHaven can use it through its COM port or the network (see below)"):t("Windows non ha un driver per questo dispositivo","Windows has no driver for this device")}</span>}
     {bus==="usb"&&(d.busid?<span> · {t("si può collegare a RigHaven (busid ","can be attached to RigHaven (busid ")}{d.busid})</span>:<span className="text-muted-foreground"> · {t("parte di un’altra periferica o hub: non si collega da sola","part of another peripheral or a hub: not attached on its own")}</span>)}</li>)}</ul></details>:null;})}
   {all.some(d=>d.bus==="bluetooth"&&!d.ok)&&<p className="text-xs">{t("I servizi Bluetooth senza driver (per esempio SerialPort, SPPSERVICE, SMS/MMS, Flow di un telefono Samsung) sono funzioni del dispositivo associato. Quelli seriali Windows li espone come porte COM: condividile con «Mostra porte COM» e crea la connessione. Un telefono Android si usa meglio dalla rete: attiva il «Debug wireless» nelle Opzioni sviluppatore e crea una connessione di rete con protocollo ADB.","Bluetooth services with no driver (for example SerialPort, SPPSERVICE, SMS/MMS, Flow of a Samsung phone) are functions of the paired device. Windows exposes the serial ones as COM ports: share them with “Show COM ports” and create the connection. An Android phone is best used over the network: turn on “Wireless debugging” in Developer options and create a network connection with protocol ADB.")}</p>}
  </div>}
  {notice&&<p className="text-sm" role="status">{notice}</p>}
  {error&&<p className="text-destructive text-sm" role="alert">{error}</p>}
  </>}
 </section>;
}

