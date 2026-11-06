# Integrated editor file handling

### Browser files and compatibility

Browser editors open the selected saved source automatically after the application's
startup handshake. Open and Save As distinguish **Chat files (server)** from **This
device**. A server save is acknowledged only after the owned project API accepts it;
a device download does not silently change the server project. Existing private
drafts keep their publication workflow. New project sessions edit chat files directly.

Browser editor tabs appear as editing activity on their ordinary environment profile.
This indicates an open browser editor, not a reserved server worker. Presence expires
within 90 seconds without a heartbeat. Server editors retain their process monitoring.
EffectCraft defaults to a clean WebGL2 session without render workers. Its browser
store uses isolated memory, avoiding upstream's startup mirror of all previously
persisted projects/media. Chat files remain on the server; this does not clear the
browser's existing archive. Cache budgets are 64 MB for layers, 64 MB for media and
128 MB for preview frames, with idle frame caching and disk caching disabled. These
are cache budgets, **not a hard limit on Chrome RAM or the WASM heap**.

Source buffers are transferred to the EffectCraft iframe and released after import,
avoiding retained parent/iframe copies. The rendering selector offers optional GPU
acceleration; changing it reloads the saved project and asks users to save first.
Neither mode converts the project format or changes its recorded CLI version.

When upstream reports graphics-device loss, the bridge stops playback and attempts
to save current edits through the ordinary versioned chat-file API. It reports
success only after the server acknowledges the write. A failed recovery keeps an
explicit warning and the editor's Save Project download available; it never reloads
the editor automatically or claims that unsaved edits have been recovered.

### Closing editors and removing environments

An open server editor belongs to one environment profile, even when other profiles
reuse the same immutable software image. Shared image availability does not make
all those profiles busy.

In Environments, **Close editor · release CPU/RAM** ends the selected server session
without deleting prepared software or saved chat files. Save pending edits first.
**Free software disk space** removes cached programs and leaves the profile needing
preparation; it does not close editors or remove the profile. **Remove profile**
removes the ordinary native Agent configuration after typed confirmation, keeping
project files and shared software. Active sessions and preparations block removal.

Jupyter's internal server token stays on the Gateway-to-notebook connection. Lab's
browser requests authenticate to RigHaven with its account cookie and CSRF echo;
the internal token is removed from page configuration and scoped browser headers.
