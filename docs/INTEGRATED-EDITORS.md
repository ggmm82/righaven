# Integrated project editors

Choose **Open with** on a conversation file. The list contains enabled editors,
with recommended sources/formats first and explicit labels for imports or formats
whose compatibility has not been verified. An association is a recommendation;
you can choose another enabled editor. Importing an image or mesh does not restore
layers or parametric construction history that the file never contained.

## Work directly on the project

New editor sessions save into the conversation's public files. There is no
mandatory draft publication or copy-back step. A browser editor opens the selected
source and its declared dependencies; the collapsible **Files and details** panel
lets you open additional project resources. Normal subsequent file pickers can
also import files from your computer. **Save to chat** is available for Craft
applications; application downloads still reach the browser.

Native editors receive the complete writable public subtree containing the
selected file at `/workspace/output`. Its directory structure, sibling files,
images, media and relative references remain available. The other public chat
folders are writable under `/workspace/chat/uploads`, `/workspace/chat/outputs`
and `/workspace/chat/workspace`. The original worker paths
`/mnt/user-data/uploads`, `/mnt/user-data/outputs` and `/mnt/user-data/workspace`
point to the same folders so generated notebooks, textures and project references
keep working. JupyterLab can browse these three public folders.
Account credentials, other conversations and
private coordinator state are not mounted.

Source ZIPs are extracted once into a persistent working folder in the chat;
the archive is retained. Reopening an unchanged archive resumes that extracted
project. Archive traversal/symlink and decompression checks still apply.

The editor opens in a normal separate browser tab. The file panel is hidden by
default to leave the application space; **Full screen** removes the browser
chrome when the browser permits it. Embedded applications support downloads,
forms, dialogs, popups and clipboard/fullscreen permissions according to the
browser's own permission prompts.

## JupyterLab and Python

Jupyter uses the full JupyterLab interface: file browser, notebook execution,
Python scripts, consoles and terminals. For a script, create a console for its
editor and run code with Lab's Run menu or Shift+Enter. Scripts are not silently
converted to notebooks or executed merely by opening them.

The selected native environment's full enabled tool set and version choices
are respected, and its execution adapters are mounted for terminals and kernels.
The notebook server has its own interface version, shown separately from the
CLI/nbconvert version. Server dependencies remain immutable; each editing session
has a persistent writable Python virtual environment for its kernel and terminals.
Native editor preferences and user-installed extensions in the editor home folder
also survive closing and reopening that session.
`%pip` or `python -m pip` can install project dependencies there. Kernel packages
and edited project files survive stopping/reopening the session. A different
editing session has its own Python dependencies. Incompatible isolated CLI tool
environments are not merged into one Python interpreter.

Project uploads and downloads stream instead of buffering all content in the
Gateway or truncating it at the old draft file limit. The host resource budget,
available disk space and the browser's memory still apply. The host sidebar is a
bounded file summary and labels truncation; native application file browsers can
explore the whole mounted folder. Browser applications fetch the selected source
and referenced assets rather than eagerly loading the entire conversation.

## Saved changes and older drafts

A direct save changes the same file used by the chat. Original selected sources
are snapshotted in private editor metadata before their first opening; HTTP file
replacements retain prior versions. Arbitrary filesystem writes made by Python
or native applications go straight to the project: they are not all intercepted
or individually versioned. Save in the application before closing it.

Older private drafts remain accessible through their existing session URLs and
the file browser. Their explicit publication workflow remains supported so a
release never discards unfinished edits. Newly opening a file uses direct editing
and does not silently resume a legacy private copy. AI assignments retain their
separate staging and output contract; this change concerns manual editor access.

## Environments and lifecycle

Jupyter, Blender and FreeCAD attach to ordinary account-owned environment
profiles, reusing compatible prepared software when available. Otherwise a
profile is registered as **When needed**. It has the same terminal, skill/version
configuration, preparation, history, sharing and transfer controls as other
environments. **Files and details → Manage environment** focuses that profile.
Historical server drafts can be linked with **Recover editor environments**.

**Environments → Options → Interactive editors** chooses interfaces to keep ready.
**When needed** uses the bounded software cache. **Keep ready** protects software;
it does not keep a live kernel or GUI process running. Changing the model provider
does not rebuild editor software. Active sessions consume the common CPU/RAM
budget under the separate interactive admission class. An editor can coexist
with AI work when resources permit.

Closing a server editor stops its process while retaining saved project files
and prepared software according to cache policy. A missing heartbeat closes a
session after three minutes, allowing for hidden-tab timer throttling. WebSocket
activity also keeps the editor alive. An active session is no longer terminated merely
because two hours have elapsed.
Restart cleanup reclaims orphan processes. Browser-only editors do not create
native runtime containers.

Administrators configure **Software cache** under **Environments → advanced
management → Resources and parallelism**: default target 20 GiB, idle expiry
14 days. Cleanup removes eligible least-recently-used images. Active work,
terminals, editors, transfers and explicitly keep-ready software are protected.
This is a soft image eviction target; project files, kernel dependencies and web
assets are separate storage, and protected software can exceed the target.

## Access and integration status

Every file/service request checks native thread ownership and enabled
capabilities. Mutations require same-origin/CSRF checks. Native WebSockets require
a scoped session cookie and matching origin. Only inspected private editor
services are proxied; no port is added to the outer Compose. The runtime system
filesystem remains read-only while project folders, temporary state and the
project Python environment are writable.

Lab's own scripts require dynamic JavaScript evaluation for their schema
validators. Its application page permits that while retaining nonce-scoped inline
scripts and scoped static assets. User HTML is served as an attachment rather
than as an application page on the account origin.

The registry distinguishes verified integrations from **Preview** integrations.
Browser distributions and APIs vary by release. EffectCraft's API loads referenced
assets before the composition and preserves reference paths on save; FilmCraft
imports media before opening its project. Unsupported API versions remain subject
to their format/integration labels, rather than being claimed to support every
feature of every CLI.

Automated checks cover direct folder saves, durable originals, legacy drafts,
concurrent revisions, archive traversal, policy disabling, account boundaries and
native environment resolution. Browser acceptance checks real UI persistence,
WordCraft/PhotoCraft WASM round trips, native JupyterLab code execution, downloads,
project writes and runtime cleanup.

## Terminal from an editor

Use **Terminal** in the editor header. JupyterLab opens its own terminal in the
same service, with the project Python environment and mounted project files.
Other tool editors open the existing RigHaven web terminal in a normal full tab,
using the editor's environment and writable project folder. A plain text/code
editor lets you choose one of your prepared environments first.

Project terminals use the ordinary session list, resource limits, retention,
reconnect and close controls. Closing a separate terminal releases that terminal,
without terminating its editor or an AI assignment. Its file changes are already
in the chat folder; they do not need a publication step.
