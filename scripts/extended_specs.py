"""File-oriented operations for optional data, verification and engineering tools."""
try:from .schema_types import tool, STRING
except ImportError:from schema_types import tool, STRING

INTEGER={'type':'integer','minimum':1,'maximum':10000}
BOOL={'type':'boolean'}
def operation(app,name,description,extra=None,required=None):
    return tool(app,name,description,{'input':STRING,'output':STRING,**(extra or {})},required or ['input','output'])

TOOLS={
 'duckdb':[operation('duckdb','query','Execute a saved SQL recipe on a private database copy; retain SQL and data, return CSV results.',{'database':STRING,'resource_dir':STRING})],
 'jupyter':[operation('jupyter','execute','Execute a notebook in a copied resource folder with a bounded cell timeout; retain input and executed notebooks.',{'resource_dir':STRING,'timeout_seconds':{'type':'integer','minimum':1,'maximum':600}})],
 'quarto':[operation('quarto','render','Render a copied QMD project to standalone HTML using local resources. PDF requires a separately selected engine.',{'resource_dir':STRING})],
 'poppler':[
  operation('poppler','render','Rasterize the actual delivered PDF to numbered PNG pages for visual inspection; rendering is not visual approval.',{'dpi':{'type':'integer','minimum':72,'maximum':200},'first_page':INTEGER,'last_page':INTEGER}),
  operation('poppler','text','Extract text from the actual PDF, preserving layout where possible; not OCR or visual validation.')],
 'qpdf':[operation('qpdf','check','Check native PDF syntax and cross references. Warnings remain visible; does not certify PDF/A or visual quality.')],
 'verapdf':[operation('verapdf','validate','Validate a PDF against a selected PDF/A profile; save the native XML report and actual conformance status.',{'flavour':{'type':'string','enum':['1a','1b','2a','2b','2u','3a','3b','3u','4']}})],
 'ocrmypdf':[operation('ocrmypdf','ocr','Create a searchable PDF and text sidecar without overwriting the scan. OCR accuracy requires content review.',{'language':{'type':'string','enum':['eng','ita','eng+ita']}})],
 'tesseract':[operation('tesseract','recognize','Recognize a local image into text and TSV with confidence/coordinates; preserve the original image.',{'language':{'type':'string','enum':['eng','ita','eng+ita']}})],
 'gdal':[
  operation('gdal','inspect','Read native raster metadata, coordinate reference system, bands and extents into JSON.'),
  operation('gdal','translate','Convert a raster to GeoTIFF while preserving the original and recording the recipe.')],
 'qgis':[operation('qgis','process','Run a named QGIS Processing algorithm using an explicit JSON parameter file and copied resources. Outputs must be relative to the private job folder.',{'algorithm':STRING,'resource_dir':STRING},['input','output','algorithm'])],
 'schemathesis':[operation('schemathesis','test','Exercise an explicitly authorized HTTP API from a local OpenAPI schema. Save native JUnit evidence; may create or modify test data.',{'target_url':STRING,'authorized':BOOL,'max_examples':{'type':'integer','minimum':1,'maximum':20}},['input','output','target_url','authorized'])],
 'k6':[operation('k6','run','Execute an explicit local load-test script with bounded iterations and virtual users against an authorized test system.',{'authorized':BOOL,'virtual_users':{'type':'integer','minimum':1,'maximum':10},'iterations':{'type':'integer','minimum':1,'maximum':100}},['input','output','authorized'])],
 'axe-core':[tool('axe-core','audit','Run axe-core in real headless Chromium on an authorized page; report violations, incomplete checks and limits.',{'url':STRING,'output':STRING,'authorized':BOOL},['url','output','authorized'])],
 'zap':[tool('zap','baseline','Run ZAP Quick Start without an active attack against an explicitly authorized URL. Save native XML evidence; passive findings are not a complete penetration test.',{'url':STRING,'output':STRING,'authorized':BOOL},['url','output','authorized'])],
 'gitleaks':[operation('gitleaks','scan','Scan a local directory for leaked secrets without executing its code. Native reports are redacted; findings do not imply exploitability.')],
 'openmodelica':[operation('openmodelica','simulate','Execute an explicit MOS recipe in a copied project folder; retain Modelica models, parameters and simulation results.',{'resource_dir':STRING})],
 'highs':[operation('highs','solve','Solve an explicit LP/MPS model with bounded CPU time; retain the model, native solution and log. Interpret feasibility and optimality from the report.')],
 'kicad':[operation('kicad','export','Export PCB or schematic SVG with native KiCad CLI; preserve native project files and custom libraries.',{'kind':{'type':'string','enum':['pcb','sch']},'resource_dir':STRING},['input','output','kind'])],
 'ngspice':[operation('ngspice','simulate','Run a local SPICE netlist in batch mode, preserving models, netlist and native results.',{'resource_dir':STRING})],
 'prusaslicer':[operation('prusaslicer','slice','Slice a local mesh using an explicit printer/material configuration; preserve model, configuration and G-code. Does not certify printer safety.',{'config':STRING},['input','output','config'])],
}
