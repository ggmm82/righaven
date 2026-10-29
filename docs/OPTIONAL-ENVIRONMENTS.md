# Optional open-source environments

RigHaven's managed catalog contains 57 tools. Tool availability is not an instruction to use every tool: roles are compiled from the project's outcome, enabled skills and available environments. The core still installs no optional application. Existing environments and user-selected skills are not silently expanded when the catalog grows.

## New capabilities

| Environment | Managed tools | Native inputs and outputs |
|---|---|---|
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

## What “ready” proves

Preparation checks the executable, CLI/MCP schemas and a real native workflow. The extended CI matrix installs all 20 additions in eight small environments, independently of the default core acceptance. Fixtures include known SQL totals, executed notebook outputs, PDF rendering and rejection, OCR from actual pixels, local API/browser tests, numerical simulations and native model exports.

It does not certify professional quality, engineering safety, accessibility compliance or complete security coverage. Those require project-specific checks. Rendering the exact PDF makes visual review possible; an available visual model or user still needs to inspect the images.

Every skill describes when to select the tool, its editable sources, native schema discovery, acceptance evidence and limitations. Deliver primary products separately from editable sources and technical reports. Preserve custom libraries, models, datasets, configurations and licenses that a source package needs after relocation. Do not put credentials or unredacted secret findings in deliverables or reusable lessons.

Network-testing adapters require explicit target authorization and bounded parameters. The ZAP adapter runs spider/passive/report jobs, with no active-scan job. Native scripts and schemas must be inspected before execution; API tests and crawling can affect the authorized target's data.
