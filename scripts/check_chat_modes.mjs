import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

// Execute the actual integrated upstream helper, not a duplicate implementation.
const root = process.argv[2] ?? '/app/frontend';
const { getResolvedMode, reasoningEffortForMode, supportsThinking } = await import(
  pathToFileURL(path.resolve(root, 'src/core/models/reasoning.ts')).href
);
const unsupported = { supports_thinking: false, supports_reasoning_effort: false };
const optional = { supports_thinking: true, supports_reasoning_effort: true };
const required = { reasoning: { thinking: 'required', effort: null, source: 'declared' } };
const declaredUnsupported = { reasoning: { thinking: 'unsupported', effort: null, source: 'declared' } };

for (const model of [unsupported, declaredUnsupported, null]) {
  for (const mode of ['flash', 'pro', 'ultra']) {
    assert.equal(getResolvedMode(mode, model), mode, `select ${mode}`);
    const saved = JSON.parse(JSON.stringify({ mode }));
    assert.equal(getResolvedMode(saved.mode, model), mode, `restore ${mode}`);
    assert.equal(getResolvedMode(getResolvedMode(mode, optional), model), mode, `switch provider in ${mode}`);
    assert.equal(reasoningEffortForMode(mode, model), undefined, 'no unsupported effort sent');
  }
  assert.equal(getResolvedMode('thinking', model), 'flash');
  assert.equal(getResolvedMode(undefined, model), 'flash');
  assert.equal(supportsThinking(model), false);
}
for (const mode of ['flash', 'thinking', 'pro', 'ultra']) {
  assert.equal(getResolvedMode(mode, optional), mode);
  assert.equal(getResolvedMode(mode, required), mode === 'flash' ? 'thinking' : mode);
}
assert.equal(reasoningEffortForMode('pro', optional), 'medium');
assert.equal(reasoningEffortForMode('ultra', optional), 'high');
assert.equal(getResolvedMode(undefined, optional), 'pro');
assert.equal(getResolvedMode(undefined, required), 'pro');
console.log('Chat modes: selection, restore, model switches and reasoning capabilities verified');

const { getRunStartTime } = await import(
  pathToFileURL(path.resolve(root, 'src/core/messages/run-start-time.ts')).href
);
const start = Date.parse('2026-10-16T06:00:00Z');
const now = start + 12 * 60 * 1000;
const run = { run_id: 'one', thread_id: 'chat', status: 'running', created_at: new Date(start).toISOString() };
// Reopened tabs have no submitted run ID; the same persisted start survives reload.
assert.equal(getRunStartTime([run], null, 'chat', now), start);
assert.equal(getRunStartTime(JSON.parse(JSON.stringify([run])), null, 'chat', now + 60000), start);
assert.equal((now - getRunStartTime([run], null, 'chat', now)) / 1000, 720);
assert.equal(getRunStartTime([run], 'two', 'chat', now), null, 'new submit must not reuse old clock');
assert.equal(getRunStartTime([run], null, 'other-chat', now), null);
assert.equal(getRunStartTime([{ ...run, status: 'success' }], null, 'chat', now), null);
assert.equal(getRunStartTime([{ ...run, status: 'success' }], 'one', 'chat', now), null);
assert.equal(getRunStartTime([{ ...run, created_at: 'invalid' }], null, 'chat', now), null);
assert.equal(getRunStartTime([{ ...run, created_at: new Date(now + 10000).toISOString() }], null, 'chat', now), null);
assert.equal(getRunStartTime(undefined, null, 'chat', now), null);
console.log('Run clock: reopen, reload, new submissions, thread ownership and invalid dates verified');

const { hasPendingDelegate, jobHealth } = await import(
  pathToFileURL(path.resolve(root, 'src/components/workspace/messages/delegate-progress-state.ts')).href
);
const call = { type: 'ai', tool_calls: [{ id: 'delegate-1', name: 'harness_delegate' }] };
assert.equal(hasPendingDelegate([call]), true);
assert.equal(hasPendingDelegate([call, { type: 'tool', tool_call_id: 'delegate-1' }]), false);
assert.equal(hasPendingDelegate([{ type: 'ai', tool_calls: [{ id: 'read-1', name: 'read_file' }] }]), false);
const job = { phase: 'running_tool', heartbeat_at: new Date(now).toISOString(),
  last_activity_at: new Date(now - 120000).toISOString(), deadline_at: new Date(now + 10000).toISOString() };
assert.match(jobHealth(job, now), /Nessun nuovo avanzamento/);
assert.match(jobHealth({ ...job, heartbeat_at: '' }, now), /Segnale del worker assente/);
assert.match(jobHealth(job, now + 11000), /Tempo limite superato/);
assert.equal(jobHealth({ ...job, phase: 'completed' }, now), null);
globalThis.__righavenUiLanguage = 'en';
assert.match(jobHealth(job, now), /No new progress/);
assert.match(jobHealth({ ...job, heartbeat_at: '' }, now), /No signal from the worker/);
delete globalThis.__righavenUiLanguage;
console.log('Delegate status: pending tool correlation, idle worker, missing heartbeat and deadline verified');

for (const relative of ['src/components/workspace/chats/chat-page.tsx', 'src/app/workspace/agents/[agent_name]/chats/[thread_id]/page.tsx']) {
  const source=fs.readFileSync(path.join(root,relative),'utf8');
  assert.equal(source.split('<DelegateProgress ').length,2,'one project dock per chat');
  assert.ok(source.indexOf('<DelegateProgress ') > source.indexOf('<MessageList'),'outside historical messages');
  assert.ok(source.indexOf('<DelegateProgress ') < source.indexOf('<InputBox'),'beside the composer');
  assert.match(source,/onPause=\{\(\) => thread\.stop\(\)\}/,'pause uses the authenticated thread cancellation');
  assert.match(source,/onContinue=\{\(message\) => handleSubmit/,'continue uses the normal authenticated submit flow');
}
assert.ok(!fs.readFileSync(path.join(root,'src/components/workspace/messages/message-list.tsx'),'utf8').includes('<DelegateProgress'),'no project panel hidden in scrolling history');
console.log('Project dock: normal and agent chats, fixed composer placement, authenticated continue and no duplicate transcript panel verified');

const memoryPage=fs.readFileSync(path.join(root,'src/components/workspace/settings/memory-settings-page.tsx'),'utf8');
assert.ok(!memoryPage.includes('description={t.settings.memory.description}'),'no false automatic-learning claim');
assert.ok(memoryPage.includes('sono disattivati'),'disabled profile memory is explicit');
assert.ok(memoryPage.includes('separatamente nei dati delle conversazioni'),'project memory is distinct');
console.log('Memory settings: disabled profile learning and separate project memory explained');
