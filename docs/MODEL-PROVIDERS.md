# Model providers

RigHaven runs two kinds of model work: the **coordinator** (the chat that plans, delegates and
checks) and the **team** (the workers that produce files in their sandbox). Both are assigned
under *Models & resources*, together or separately.

| | OpenAI Codex | Claude Code | Antigravity | OpenAI-compatible API |
|---|---|---|---|---|
| Sign-in | Your OpenAI account | Your Anthropic account | Your Google account | Endpoint URL + API key |
| Worker | The official Codex CLI agent | The official Claude Code agent | The official Antigravity CLI | RigHaven's own tool loop |
| Skills | Native skill discovery | Native skill discovery | Native skill discovery | Skill text in the prompt, references read from disk |
| Images in the worker | Yes, and native image generation | Yes | Yes | Only if the model passes the vision check |
| Long jobs | The CLI manages its context | The CLI manages its context | The CLI manages its context | Older command outputs are shortened automatically |
| Cost | Your subscription quota | Your subscription quota | Your subscription quota | Tokens billed by the provider |

## OpenAI-compatible APIs

Any endpoint with the Chat Completions API and **tool calling** works: OpenAI, DeepSeek
(`https://api.deepseek.com`, model `deepseek-chat`), Kimi/Moonshot, OpenRouter, and
self-hosted servers that implement the same API. When you save, RigHaven:

1. calls the endpoint and checks that the model really performs a tool call (a model without
   function calling is refused, so the team is never left unable to work);
2. finds which token limit field the provider accepts (`max_tokens` or `max_completion_tokens`);
3. adapts to thinking models that refuse a forced tool choice (`required`, then automatic);
4. detects reasoning models, which get a larger reply budget;
5. tries a tiny image to learn whether the model can see previews.

What it found is stored with the connection and kept when you later change only the model.

**How the worker runs.** The worker is a bounded loop of up to 64 turns. Each turn the model can
run a shell command in the sandbox, post a progress note or submit the handoff, which is
validated like every other worker's. Compared with the native CLIs:

- one generic tool (the shell) instead of the CLI's own editing and search tools: the model writes
  files with commands;
- a reply cut by the token limit is not executed; the model is asked to continue in smaller steps
  (after three cuts in a row the job stops with a clear message);
- when the conversation grows, older command outputs are shortened so long jobs stay within the
  model's context; recent outputs stay complete;
- transient errors (timeouts, HTTP 429 and 5xx) are retried three times with backoff; a rejected
  key or model stops with a clear message;
- no native image generation and no audio; without vision, visual reviews stay "to be checked"
  and are never reported as passed.

**DeepSeek.** DeepSeek is used through this connection. Its thinking mode needs the reasoning
sent back with every tool call, which generic clients drop, so RigHaven turns thinking off for
`api.deepseek.com` unless the check found a reasoning model. Installations that used the former
DeepSeek option are migrated automatically on start: the key becomes an OpenAI-compatible
connection to `https://api.deepseek.com` with the same model, and the old key file is removed.

**Coordinator.** The coordinator uses the same endpoint through a standard OpenAI client. Models
that require their reasoning to be echoed back with tool calls may fail as coordinator; choose a
non-thinking model for the coordinator (for example `deepseek-chat`) and, if you like, a reasoning
model for the team.
