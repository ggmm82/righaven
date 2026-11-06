# Open chat: resources, shared methods and reusable recipes

You can start with an objective, files or an idea. A recipe and a live database connection are optional. The coordinator should explain a proportionate approach, ask only questions that change the result, and offer alternatives when their trade-offs matter.

## Choose resources before starting

- **Paperclip:** upload files. It does not open the skill picker.
- **Skills:** select enabled competencies. The picker shows skills only; the existing `@` menu remains available for other references.
- **Connections:** authorize existing database or Microsoft connections for this conversation, including before its first message or production plan. Opening the selector prepares a native conversation but does not start production. Credentials stay in the connection store; the coordinator receives public metadata. Writing requires the existing separate connection and task consent.

Connections selected here persist with the conversation. Only compiled roles requesting the authorized IDs receive their credentials, for the duration of an assignment. Removing a selection affects future assignments; it does not revoke credentials already handed to a running worker. Model-provider accounts continue to be configured in model settings.

## Develop the method together

1. Explain the result, intended audience, delivery format and important constraints.
2. The coordinator explains its recommendation and, where useful, up to three alternatives. Reasons should include benefits, limitations and effort, rather than a list of CLI commands.
3. When a consequential choice is needed, the coordinator records a method with `state=needs_user`, `stop_reason=user_choice` and a concrete question. It waits before producing the result.
4. Open **Status → Method and alternatives**, select an approach, add constraints if necessary, and choose **Choose and continue**. The decision is saved before the team resumes. A resume failure leaves the decision saved; use Continue without approving again.
5. Test a representative sample and compare it against the agreed requirements. Explain what the trial demonstrates, what remains uncertain, and what changes next. Routine implementation decisions do not require repeated approval.

Method decisions have a history. They are owner instructions over the existing project strategy, not another activity scheduler. Native skills, disabled-tool policy, environment selection, staging and delivery checks remain in force. Guided projects still use their own phase-approval cards; choosing a method never approves a guided phase.

## Turn experience into a recipe

Ask the coordinator to propose a reusable recipe after the method has been tried. The coordinator uses `harness_method(recipe_json)` to prepare a **private draft**, not to save or publish a recipe.

A proposal requires an explicit owner method choice and hashed evidence from a completed, validated assignment. Changed evidence or a changed strategy invalidates the proposal. These checks establish provenance, not professional quality: evaluate the actual result before reusing the method.

Choose **Review and save the recipe** to open the existing recipe editor. Generalize the goal, input requirements, stages, competencies and checks. Remove project-specific facts and private information. Attachments may be optional. Review the human-readable card and save it; the recipe is private by default. Publishing to the gallery remains a separate action. Project evidence paths, connection IDs and credentials are not copied into the saved recipe automatically.

## Preview and edit a text source

Markdown, HTML and CSV/TSV deliveries have a native document-preview link separate from download. The reader offers **Edit a copy** for supported UTF-8 text sources up to 1 MiB, after the full file has loaded.

Saving creates a new file under `outputs/source-revisions/`. The original source, PDF and other exports are retained. The coordinator sees the source-copy reference on its next turn; return to chat to request its integration and regeneration of exports. A saved copy is not an approved final delivery. Concurrent source changes are detected by SHA-256, and editing is refused while production is active.

Binary projects, images, audio and PDFs are not edited as text. Use their editable source and the appropriate tool.

## Evolve a delivery or change direction

After a delivery, keep chatting about what you want next. For a new objective or revision, the coordinator can use `harness_method(objective)` with your actual latest request. You can also choose **Evolve result**, describe what to keep and change, and start the new objective.

The previous project, its recipe decisions, delivery and sources are retained in objective history. The new work starts in open collaboration, with the prior result as an explicit base; old recipe gates, task statuses, accepted checks and production-method assumptions do not govern it. The previous recipe remains a reference, not a mandatory checklist. Relevant organization policies and enabled-capability restrictions still apply to every new assignment. Connection selections are retained; writing requires new consent.

This works in the same conversation and does not require repeating the recipe. New deliverables belong to the new objective. The **Objective** view distinguishes the base files from current work and retains previous goals. Ask only consequential questions; reuse existing sources rather than rebuilding unchanged content.

## Temporary environments and the web terminal

Assignment environments use the same **Open terminal** window as saved, prepared
profiles. In **Environments**, open it from a temporary assignment card or from
an assignment using a saved profile. It starts the same verified software and
currently enabled skills in an ordinary terminal container. The assignment's
project is available read-only at `/workspace/project`; its private staged files,
when present, are read-only at `/workspace/output`. This does not attach to the
specialist's process, mount its credentials, change its files or publish terminal
experiments as project deliveries. Worker cleanup and delivery validation proceed
normally. If the exact software image is no longer available, save its configuration
and prepare it; opening a terminal never silently rebuilds a different version.

**Save as environment** opens the existing environment configuration editor with
the assignment's skills and verified software selections. Review its name and
purpose, then choose **When needed** or **Keep ready** and save. Prompts, credentials,
connection grants, processes, files and local terminal installations are excluded.
Keeping a saved profile ready preserves reusable software, not a running worker.

All terminals close when their window leaves, with a 60-second disconnected-client
fallback. In that same terminal window, **Keep for 10 minutes** or **Keep for 30
minutes** explicitly keeps the session available even after its window closes.
This uses the normal terminal resource budget. The absolute session lifetime is
30 minutes from creation; extending retention cannot bypass it. **Open terminals**
on the Environments page shows expiry and offers **Open terminal** (same PTY,
no duplicate machine) and **End session**. Restore automatic closing to remove
retention, or end the session to request immediate cleanup. A Gateway restart
reclaims temporary terminals; retention is not a persistent machine backup.

## One delivery and the requested destination

New **A working result first** projects have one approval stage. The first
assignment includes the product, editable sources, concise instructions and its
checks. After its independent review and the owner's approval, present those same
files. A new packaging job or repeated quality review is not needed just to label
them final. Corrections remain possible when requested or when a concrete unmet
requirement needs work. Existing saved workflows keep their recorded stages.

The owner's intake goal stays in the acceptance contract even after message
compaction. Application-generated Continue messages do not narrow that goal.
Connections are optional resources, but an explicitly selected writable
**destination** is part of the result. The team must declare it in an appropriate
role, use its authorized access and preserve evidence of actual remote read-back.
The guarded `dlt.load` operation now produces `connection-verification.json` after
checking destination rows. The handoff references that output in
`connection_receipts`. A local database, exported SQL or a connection probe does
not establish that the destination was populated.

The Connections panel distinguishes pending, verified and owner-deferred
destinations. **Defer writing: I accept the local result for now** is an explicit
owner decision; the coordinator cannot set it. Without execution evidence or this
decision, the result remains partial and final completion is rejected. Missing
connection access is reported as a blocker rather than silently omitted. These
records describe the checked execution and its limits; they do not continuously
monitor a remote database after delivery.
