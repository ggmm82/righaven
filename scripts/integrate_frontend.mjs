import fs from 'node:fs';
const root=process.argv[2] ?? '/app/frontend';
const file=root+'/src/components/workspace/workspace-sidebar.tsx';
let source=fs.readFileSync(file,'utf8');
const marker='          <WorkspaceNavChatList />';
if(!source.includes(marker) || !source.includes('import { ThreadDeleteDialogProvider }'))throw Error('RigHaven sidebar changed; review integration before building');
source=source.replace(marker, '          <TeamOnboarding />\n'+marker+'\n          <Link href="/workspace/harness" className="mx-3 rounded-md px-3 py-2 text-sm hover:bg-accent">Harness Control</Link>\n          <Link href="/workspace/environments" className="mx-3 rounded-md px-3 py-2 text-sm hover:bg-accent">Environments</Link>\n          <Link href="/workspace/gallery" className="mx-3 rounded-md px-3 py-2 text-sm hover:bg-accent">Community Gallery</Link>\n          <Link href="/workspace/cloud" className="mx-3 rounded-md px-3 py-2 text-sm hover:bg-accent">Cloud Portal</Link>');
source=source.replace('import { ThreadDeleteDialogProvider }', 'import { TeamOnboarding } from \"./team-onboarding\";\nimport { ThreadDeleteDialogProvider }');
source=source.replace('"use client";', '"use client";\n\nimport Link from "next/link";');
fs.writeFileSync(file,source);

// Pro/Ultra select the workflow, independently of provider thinking controls.
// Patch the shared resolver so selection, saved settings and model switches agree.
const reasoningFile=root+'/src/core/models/reasoning.ts';
let reasoning=fs.readFileSync(reasoningFile,'utf8');
const unsupportedMode='  if (thinking === "unsupported") {\n    return "flash";\n  }';
if(reasoning.split(unsupportedMode).length !== 2)throw Error('RigHaven reasoning resolver changed; review mode integration before building');
reasoning=reasoning.replace(unsupportedMode, '  if (thinking === "unsupported") {\n    // Workflow modes do not require a provider-level thinking toggle.\n    return mode === "pro" || mode === "ultra" ? mode : "flash";\n  }');
fs.writeFileSync(reasoningFile,reasoning);

// A resumable stream alone does not keep a run alive: the Gateway defaults to
// cancelling the creating run when its SSE connection closes. Cover new turns
// and edit/regenerate replay submissions, while leaving explicit Stop intact.
const hooksFile=root+'/src/core/threads/hooks.ts';
let hooks=fs.readFileSync(hooksFile,'utf8');
const resumable='streamResumable: true,';
if(hooks.split(resumable).length !== 3)throw Error('RigHaven submit paths changed; review background run integration before building');
hooks=hooks.replaceAll(resumable, 'onDisconnect: "continue",\n            '+resumable);

function replaceRequired(text, before, after, label) {
  if(text.split(before).length !== 2)throw Error('RigHaven '+label+' changed; review timer integration before building');
  return text.replace(before, after);
}
// The shipped configuration disables upstream profile-memory learning and
// injection. Do not advertise automatic learning on an empty profile screen.
const memoryFile=root+'/src/components/workspace/settings/memory-settings-page.tsx';
let memoryPage=fs.readFileSync(memoryFile,'utf8');
memoryPage=replaceRequired(memoryPage, 'title={t.settings.memory.title}',
  'title="Memoria personale"', 'profile memory title');
memoryPage=replaceRequired(memoryPage, 'description={t.settings.memory.description}',
  'description="In questa versione l’apprendimento automatico e l’uso di questa memoria nelle risposte sono disattivati. Puoi conservare ed esportare annotazioni personali. La memoria dei progetti, le revisioni e le skills compilate sono conservate separatamente nei dati delle conversazioni: questa schermata vuota non indica che siano state perse."', 'profile memory explanation');
fs.writeFileSync(memoryFile,memoryPage);
hooks=replaceRequired(hooks, 'import { getMessageRunId } from "../messages/run-duration";',
  'import { getMessageRunId } from "../messages/run-duration";\nimport { getRunStartTime } from "../messages/run-start-time";', 'timer import');
hooks=replaceRequired(hooks, '      submittedRunIdRef.current = meta.run_id;',
  '      submittedRunIdRef.current = meta.run_id;\n      void queryClient.invalidateQueries({ queryKey: ["thread", meta.thread_id], exact: true });', 'run creation');
hooks=replaceRequired(hooks, '    stop: stopThread,',
  '    stop: stopThread,\n    harnessRunStartedAt: getRunStartTime(runsQuery.data, submittedRunIdRef.current, currentViewThreadId),', 'run timer metadata');
hooks=replaceRequired(hooks, '  } as typeof thread;',
  '  } as typeof thread & { harnessRunStartedAt: number | null };', 'merged thread type');
fs.writeFileSync(hooksFile,hooks);

const messagesFile=root+'/src/components/workspace/messages/message-list.tsx';
let messages=fs.readFileSync(messagesFile,'utf8');
messages=replaceRequired(messages, '  thread: BaseStream<AgentThreadState>;',
  '  thread: BaseStream<AgentThreadState> & { harnessRunStartedAt?: number | null };', 'message list props');
messages=replaceRequired(messages,
  '  // The backend exposes no live start timestamp, so a mid-run mount measures\n  // from mount until authoritative persisted turn_duration replaces it.',
  '  // Reconnects use the persisted run clock, not the time this page mounted.\n  const serverStartTime = thread.harnessRunStartedAt ?? null;', 'message timer start');
messages=replaceRequired(messages, '    thread.isLoading ? Date.now() : null,',
  '    thread.isLoading ? (serverStartTime ?? Date.now()) : null,', 'initial timer');
messages=replaceRequired(messages, '  const prevIsLoading = useRef(thread.isLoading);',
  '  const prevIsLoading = useRef(thread.isLoading);\n  const timerThreadRef = useRef(threadId);', 'timer thread ownership');
messages=replaceRequired(messages,
  '    if (thread.isLoading && !prevIsLoading.current) {\n      const now = Date.now();\n      turnStartTimeRef.current = now;\n      setTurnStartTime(now);',
  '    if (timerThreadRef.current !== threadId) {\n      timerThreadRef.current = threadId;\n      turnStartTimeRef.current = null;\n    }\n    if (thread.isLoading) {\n      const start = serverStartTime ?? turnStartTimeRef.current ?? Date.now();\n      if (turnStartTimeRef.current !== start) {\n        turnStartTimeRef.current = start;\n        setTurnStartTime(start);\n      }', 'live timer reconciliation');
messages=replaceRequired(messages, '  }, [groupedMessages, thread.error, thread.isLoading, threadId]);',
  '  }, [groupedMessages, thread.error, thread.isLoading, threadId, serverStartTime]);', 'timer effect');
fs.writeFileSync(messagesFile,messages);

// Put one compact project control next to the composer, outside the scrolling
// transcript. Cover normal chats and custom-agent chats, with no duplicate panel.
for (const relative of [
  '/src/components/workspace/chats/chat-page.tsx',
  '/src/app/workspace/agents/[agent_name]/chats/[thread_id]/page.tsx',
]) {
  const pageFile=root+relative;
  let page=fs.readFileSync(pageFile,'utf8');
  page=replaceRequired(page, '"use client";', '"use client";\n\nimport { DelegateProgress } from "@/components/workspace/messages/delegate-progress";\nimport { hasPendingDelegate } from "@/components/workspace/messages/delegate-progress-state";', 'project dock import');
  const anchor='                  {(hasGoal || goalOutcome !== null || hasTodos) && (';
  const dock='                  {!isNewThread && !isMock && <DelegateProgress threadId={threadId} active={thread.isLoading} pending={thread.isLoading && hasPendingDelegate(thread.messages)} coordinatorError={!!thread.error} onPause={() => thread.stop()} onContinue={(message) => handleSubmit({ text: message ?? "Riprendi il progetto dal punto attuale. Considera le mie risposte e le scelte aperte sul risultato, conserva i file validi e procedi con la prossima attività utile.", files: [] })} />}\n';
  page=replaceRequired(page, anchor, dock+anchor, 'project composer placement');
  fs.writeFileSync(pageFile,page);
}
