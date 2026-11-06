"""Planning capabilities: editable models and native rendering, not extra professions."""
try:from .schema_types import tool, STRING
except ImportError:from schema_types import tool, STRING
TOOLS={}
for app,description in {
 'd2':'Modern structured diagrams with automatic layout from editable D2.',
 'plantuml':'Formal UML from editable PlantUML, with native syntax checking.',
 'mermaid':'Diagrams for Markdown and chat; export with the existing shared browser engine.',
 'excalidraw':'Editable visual whiteboards, using the native Excalidraw SDK.',
 'bpmn':'BPMN 2.0 process models with native bpmn-js import and rendering; not a workflow execution engine.',
}.items():
 fields={'input':STRING,'output':STRING}
 if app=='d2':fields['layout']={'type':'string','enum':['dagre','elk']}
 TOOLS[app]=[
  tool(app,'render',description+' Create a portable folder with source, SVG and receipt (browser SDKs also export PNG/PDF). Self-contained inputs only.',fields,['input','output']),
  tool(app,'check','Validate the self-contained native model and render it; an image alone does not prove design quality.',{'input':STRING,'output':STRING},['input','output'])]
TOOLS['structurizr']=[
 tool('structurizr','validate','Parse and validate a self-contained C4 DSL using the maintained Structurizr libraries in restricted mode. No server, scripts or plugins.',{'input':STRING,'output':STRING},['input','output']),
 tool('structurizr','export','Export views from one C4 model to editable PlantUML or Mermaid plus workspace JSON; renderer remains the respective existing capability.',{'input':STRING,'output':STRING,'format':{'type':'string','enum':['plantuml','mermaid']}},['input','output','format'])]
