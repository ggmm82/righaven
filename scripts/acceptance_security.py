"""Offline native security evidence; never execute fixture source code."""
import json
try:from .acceptance_toolkit import call
except ImportError:from acceptance_toolkit import call


def opengrep(c):
    source=c.root/'source';source.mkdir();(source/'sample.py').write_text('def unsafe(value):\n    return eval(value)\n')
    rules=c.root/'rules.yaml';rules.write_text('rules:\n  - id: local-eval\n    languages: [python]\n    message: Review dynamic evaluation\n    severity: WARNING\n    pattern: eval($VALUE)\n')
    output=c.root/'Scan';result=call(c,'scan',input=str(source),rules=str(rules),output=str(output))
    report=json.loads((output/'report.json').read_text())
    c.check('Native scan finds the local rule without executing source',len(report['results'])==1 and not report.get('errors'),result)
    c.check('Reproducible rules and scanner identity preserved',(output/'rules.yaml').read_text()==rules.read_text() and json.loads((output/'scan-recipe.json').read_text())['count']==1,result)


def trivy(c):
    source=c.root/'source';source.mkdir();(source/'Dockerfile').write_text('FROM alpine:latest\nUSER root\n')
    output=c.root/'Scan';result=call(c,'config',input=str(source),output=str(output))
    report=json.loads((output/'report.json').read_text())
    findings=[f for r in report['Results'] for f in r.get('Misconfigurations',[])]
    c.check('Embedded checks identify Dockerfile risks without DB or network',bool(findings),result)
    c.check('Report and recipe identify native scanner',json.loads((output/'scan-recipe.json').read_text())['tool']=='trivy',result)


CASES={'opengrep':opengrep,'trivy':trivy}
