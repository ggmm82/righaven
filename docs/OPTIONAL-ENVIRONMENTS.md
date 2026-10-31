# Optional open-source environments

RigHaven's managed catalog contains 62 tools. Tool availability is not an instruction to use every tool: roles are compiled from the project's outcome, enabled skills and available environments. The core still installs no optional application. Existing environments and user-selected skills are not silently expanded when the catalog grows.

## New capabilities

| Environment | Managed tools | Native inputs and outputs |
|---|---|---|
| Data Engineering | usql, SchemaCrawler, dlt, SQLMesh, SQLGlot, DuckDB, Jupyter, Quarto, Typst | Authorized metadata and queries → schema/lineage, bounded extracts, tested local transformations and editable reports |
| Data and notebooks | DuckDB, Jupyter, Quarto | SQL and datasets → database/CSV; IPYNB → executed IPYNB; QMD → HTML |
| PDF verification | Poppler, qpdf, veraPDF | Actual PDF → page PNGs, extracted text, syntax diagnostics and explicit PDF/A report |
| Scans and archives | OCRmyPDF, Tesseract | Original PDF/image → searchable PDF, text and coordinate/confidence TSV |
| Geospatial | GDAL, QGIS Processing | Raster/layers and parameter JSON → metadata, GeoTIFF and native Processing results |
| API and web testing | Schemathesis, k6, axe-core | OpenAPI, JS scenarios and authorized URLs → JUnit, metrics and real-browser accessibility findings |
| Source and passive security | Gitleaks, OWASP ZAP | Local source or authorized URL → redacted findings and passive scan report |
| Simulation and optimization | OpenModelica, HiGHS | MO/MOS and LP/MPS → simulation data, solver solution and native status |
| Electronics | KiCad CLI, ngspice | Native KiCad documents and SPICE netlists → SVG previews and simulation data |
| 3D print preparation | PrusaSlicer | Existing mesh plus explicit printer/material INI → G-code with retained source/settings |

The existing security preset retains OpenGrep and Trivy, and the web preset retains Playwright. New tools complement these capabilities. No second coordinator, provider configuration or fixed professional role is introduced.

## Selecting and preparing

Choose a preset or create a native custom environment with a purpose and selected skills. Keep **on demand** for occasional capabilities; preload only the selected tools you expect to use. Merely viewing or activating a gallery entry does not install its software. English and Italian gallery descriptions are included; community manifests declare managed tool IDs, never arbitrary package-install commands.

Each environment uses its own software recipe and the existing assignment staging/output contract. axe-core shares the existing Playwright Chromium installation; the browser dependency does not grant a role permission to use every other browser capability.

New catalog versions are defaults, not immutable UI restrictions. Existing version selection supports explicit versions and `latest`. For Debian-packaged tools, `latest` means the stable candidate compatible with the managed Debian base, not the newest upstream version. KiCad uses the signed Debian backports repository for its native CLI. OpenModelica uses its official signed stable repository. Other sources are official GitHub releases, PyPI, npm and veraPDF's versioned distribution server; downloads have recorded SHA-256 and Python/npm dependencies are locked. Updates must pass native preparation checks before becoming ready.

## Prepared profiles as the base of assignments

Each role brings its skills and the software they require. Among the owner's
**Keep ready** profiles that are prepared and authorized, the runtime selects the
one containing most of the role's skills, then covering most of its programs
(then fewer missing programs, fewer unrequested programs, smaller image), and
adopts that profile's versions for the covered programs. Its
image is reused as is or extended with only the missing programs, through the
same incremental preparation. **When needed** profiles are not candidates until
prepared, and prepared profiles stay allocated.

Every assignment records the profile, the covered and added programs and the
reason, shown in the assignment card of the conversation. The **Environments**
page explains the criterion and shows, for each profile, how many assignments it
served and the last one.

**Configuration → Machine usage** reports who used which machine, how and how
much: assignments, work and CPU hours and peak memory per machine (profile,
dedicated environment or common base), per user and per role, with reuses and
extensions of each profile and the latest assignments linked to their
conversation. Administrators see every user; everyone else sees their own.

## What “ready” proves

Preparation checks the executable, CLI/MCP schemas and a real native workflow. The extended CI matrix installs all 20 additions in eight small environments, independently of the default core acceptance. Fixtures include known SQL totals, executed notebook outputs, PDF rendering and rejection, OCR from actual pixels, local API/browser tests, numerical simulations and native model exports.

It does not certify professional quality, engineering safety, accessibility compliance or complete security coverage. Those require project-specific checks. Rendering the exact PDF makes visual review possible; an available visual model or user still needs to inspect the images.

Every skill describes when to select the tool, its editable sources, native schema discovery, acceptance evidence and limitations. Deliver primary products separately from editable sources and technical reports. Preserve custom libraries, models, datasets, configurations and licenses that a source package needs after relocation. Do not put credentials or unredacted secret findings in deliverables or reusable lessons.

Network-testing adapters require explicit target authorization and bounded parameters. The ZAP adapter runs spider/passive/report jobs, with no active-scan job. Native scripts and schemas must be inspected before execution; API tests and crawling can affect the authorized target's data.

## Delivery and preparation reliability

Saved products are presented with RigHaven's native file tool when a coordinator ends a turn without attaching them. The presentation uses existing scoped files and hashes, does not start another model call, and does not change the quality/approval verdict. Optional `reopen: null` metadata remains an unperformed check, not a tool-wrapper exception. The application's exact resume instruction is a run control rather than a new product requirement; genuine revision requests still invalidate outdated acceptance reviews.

Review reports can declare `observation_limits` with an actual method, reason and concrete next action. Dependent criteria can identify the blocked observation with `blocked_by`; failed checks remain failed and unavailable observations remain `not_run`. This distinguishes a missing visual/listening capability from a defect requiring another production run.

Preparation records retain the trigger (manual, configuration, version activation, or startup) and an observed reason for a new recipe (base, versions, tools, or unavailable image). The interface shows the explanation in preparation details. These diagnostics do not claim to reconstruct a reason missing from historical records.

Image sizes are uncompressed totals including the base and inherited layers, not RAM or exclusive disk usage. The UI explains that shared layers must not be summed across profiles. Newly prepared images also record the added size relative to the actual parent; this is not a measurement of exclusive disk space. Heavy programs can increase image layers even when other native tools are reused. Model-provider CLIs now live in separate persistent, verified bundles, mounted read-only into workers; changing a model or CLI does not add a provider layer to every application environment.


### Reusing prepared software

Application recipes use the software platform compatibility identity and per-tool installation inputs. Catalog prose, worker code, skill instructions and the selected model do not invalidate compatible program images. Existing owned images are inspected and their compatibility metadata is cached persistently; no account or project data is mounted for inspection. Missing images and genuinely incompatible software bases still require preparation.

Preparation chooses the compatible parent with the most unchanged requested tools, including partial overlaps. It preserves those tools, removes unrequested application payloads in the disposable child, and replaces only missing or changed payloads. The parent is immutable. Shared system dependencies are retained; all required native checks run again before publication. The UI reports reused and added/updated tool counts.

Codex, Antigravity and Claude Code use a shared version selection under Models & resources. Their immutable CLI bundles contain only executable software, never account credentials. Each worker mounts the selected bundle read-only and receives its own credential session. A CLI update affects subsequent workers; it does not modify active jobs or rebuild saved environments. DeepSeek and OpenAI-compatible API connections do not need a CLI bundle. Historical provider pins in saved environment preparation records no longer affect program readiness.

## Worker network access

`RIGHAVEN_WORKER_EGRESS` selects how assignment workers reach the Internet:

| Value | Behaviour |
| --- | --- |
| `open` (default) | Workers use the Docker bridge network, as in earlier releases. |
| `allowlist` | Workers join the internal network `righaven-egress`, which has no route outside. Their only exit is the `righaven-egress-proxy` container (started from the worker software image, capabilities dropped, read-only root). |

In allowlist mode each assignment gets its own proxy token and grant:

- the domains of its model provider (Codex, Claude Code, Antigravity, DeepSeek, or the host of the OpenAI-compatible endpoint) are always granted;
- a role may add up to eight domains in its `network` field, each with the reason the coordinator declared, for example `{"domain": "fonts.googleapis.com", "reason": "Web fonts for the poster"}`; a leading dot (`.example.org`) grants subdomains;
- only ports 80 and 443 are allowed, IP literals are refused, and names that resolve to private, loopback or link-local addresses are refused even when granted;
- the grant is deleted when the assignment ends.

Every refused connection is reported on the assignment card ("Blocked connections") and in the conversation log, so the coordinator can ask the user before granting a new domain. The worker receives `HTTPS_PROXY`, `HTTP_PROXY`, `ALL_PROXY` and `NODE_USE_ENV_PROXY=1`; tools that ignore proxy variables cannot reach the Internet in this mode. CI runs `scripts/check_worker_egress.py` against the real worker image: a granted domain goes through, another domain is refused and logged, and a direct connection fails.

Each worker already receives a private copy of the provider credentials (`credential_sessions.py`): refreshed OAuth tokens are written back under the execution lock only when the shared copy has not changed meanwhile, and API keys are decrypted only into the job's disposable folder.
