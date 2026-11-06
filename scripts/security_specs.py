"""Local, explicit security checks with portable evidence, not autonomous attacks."""
try:from .schema_types import tool, STRING
except ImportError:from schema_types import tool, STRING
TOOLS={
 'opengrep':[tool('opengrep','scan','Scan a local source directory with a local YAML rules file. Preserve rules, source identity and JSON findings. Findings are not a scanner crash.',{'input':STRING,'rules':STRING,'output':STRING},['input','rules','output'])],
 'trivy':[
  tool('trivy','config','Check local infrastructure configuration using embedded rules, without updating remote checks. Save JSON findings and scanner identity.',{'input':STRING,'output':STRING},['input','output']),
  tool('trivy','sbom','Create a CycloneDX software inventory of a local directory. An inventory is not a vulnerability verdict.',{'input':STRING,'output':STRING},['input','output']),
  tool('trivy','database_update','Download the official vulnerability database into a new workspace cache folder and record its metadata. This downloads data, not executable tools.',{'output':STRING},['output']),
  tool('trivy','vulnerabilities','Scan local dependencies with an existing, explicitly identified database cache. No silent database updates; missing data is an error, not zero findings.',{'input':STRING,'database':STRING,'output':STRING},['input','database','output'])]}
