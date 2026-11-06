"""Real, portable planning models, not diagram screenshots masquerading as sources."""
import json, shutil
from pathlib import Path
try:from .acceptance_toolkit import call,rejected
except ImportError:from acceptance_toolkit import call,rejected

SAMPLES={
'd2':('model.d2','idea: Idea\nresult: Result\nidea -> result: resolves\n'),
'plantuml':('model.puml','@startuml\nactor User\nUser -> Team: Brief\nTeam --> User: Result\n@enduml\n'),
'mermaid':('model.mmd','flowchart LR\n idea[Idea] --> result[Result]\n'),
'excalidraw':('model.excalidraw',json.dumps({'type':'excalidraw','version':2,'source':'righaven','elements':[{'id':'idea','type':'rectangle','x':20,'y':20,'width':180,'height':100,'angle':0,'strokeColor':'#1e1e1e','backgroundColor':'#a5d8ff','fillStyle':'solid','strokeWidth':2,'strokeStyle':'solid','roughness':1,'opacity':100,'seed':1,'version':1,'versionNonce':1,'isDeleted':False,'boundElements':[],'updated':1,'link':None,'locked':False}],'appState':{'viewBackgroundColor':'#ffffff'},'files':{}})),
'structurizr':('model.dsl','''workspace "Project" {
 model {
  user = person "User"
  system = softwareSystem "Product"
  user -> system "Uses"
 }
 views {
  systemContext system "Context" {
   include *
   autoLayout lr
  }
 }
}'''),
'bpmn':('model.bpmn','''<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" xmlns:di="http://www.omg.org/spec/DD/20100524/DI" id="Definitions" targetNamespace="https://righaven.example/design">
<bpmn:process id="Process" isExecutable="false"><bpmn:startEvent id="Start" name="Idea"/><bpmn:task id="Task" name="Review"/><bpmn:endEvent id="End" name="Result"/><bpmn:sequenceFlow id="Flow1" sourceRef="Start" targetRef="Task"/><bpmn:sequenceFlow id="Flow2" sourceRef="Task" targetRef="End"/></bpmn:process>
<bpmndi:BPMNDiagram id="Diagram"><bpmndi:BPMNPlane id="Plane" bpmnElement="Process"><bpmndi:BPMNShape id="Shape1" bpmnElement="Start"><dc:Bounds x="80" y="100" width="36" height="36"/></bpmndi:BPMNShape><bpmndi:BPMNShape id="Shape2" bpmnElement="Task"><dc:Bounds x="170" y="78" width="100" height="80"/></bpmndi:BPMNShape><bpmndi:BPMNShape id="Shape3" bpmnElement="End"><dc:Bounds x="330" y="100" width="36" height="36"/></bpmndi:BPMNShape><bpmndi:BPMNEdge id="Edge1" bpmnElement="Flow1"><di:waypoint x="116" y="118"/><di:waypoint x="170" y="118"/></bpmndi:BPMNEdge><bpmndi:BPMNEdge id="Edge2" bpmnElement="Flow2"><di:waypoint x="270" y="118"/><di:waypoint x="330" y="118"/></bpmndi:BPMNEdge></bpmndi:BPMNPlane></bpmndi:BPMNDiagram></bpmn:definitions>''')}


def workflow(c):
    name,text=SAMPLES[c.app];source=c.root/name;source.write_text(text)
    operation='validate' if c.app=='structurizr' else 'render'
    output=c.root/'Rendered';result=call(c,operation,input=str(source),output=str(output))
    c.check('Native source is preserved with a reproducible recipe',source.read_text()==text and (output/'Sources'/name).read_text()==text and (output/'design-recipe.json').is_file(),result)
    moved=c.root/'Relocated';shutil.copytree(output/'Sources',moved);source.unlink()
    reopened=c.root/'Reopened';result=call(c,operation,input=str(moved/name),output=str(reopened))
    c.check('Transferred source reopens with the actual engine',result['status']=='passed',result['inspection'])
    if c.app=='structurizr':
        exported=c.root/'Exported';call(c,'export',input=str(moved/name),output=str(exported),format='mermaid')
        c.check('C4 views export from a single native model',any(exported.glob('view-*')) and (exported/'workspace.json').is_file(),str(exported))
    else:
        c.check('Native renderer produces a nonempty structured SVG',(reopened/'diagram.svg').stat().st_size>300,str(reopened))
        if c.app in ('excalidraw','mermaid','bpmn'):
            pixels=c.pixels(reopened/'diagram.png')
            c.check('Actual rendered PNG decodes with visible content',len(pixels)>1000 and len(set(pixels))>5,len(pixels))
    bad=c.root/('invalid'+Path(name).suffix);bad.write_text('not valid model { ]')
    rejected(c,operation,input=str(bad),output=str(c.root/'Invalid'))


CASES={app:workflow for app in SAMPLES}
