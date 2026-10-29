"""Reuse RigHaven's validated tool decision schema with Claude structured output."""
from . import antigravity_protocol as shared


def request(*args,**kwargs):
    try:value=shared.request(*args,**kwargs)
    except (ValueError,RuntimeError) as error:raise type(error)(str(error).replace('Antigravity','Claude Code')) from None
    value['prompt']=value['prompt'].replace('Usa il tool nativo finish per consegnare una decisione conforme allo schema JSON fornito','Consegna tramite l’output strutturato della CLI una decisione conforme allo schema JSON fornito').replace('L’unico tool nativo da usare è finish;','Non utilizzare strumenti operativi locali;')
    return value


def response(*args,**kwargs):
    try:value=shared.response(*args,**kwargs)
    except (ValueError,RuntimeError) as error:raise type(error)(str(error).replace('Antigravity','Claude Code')) from None
    for call in value['tool_calls']:call['id']=call['id'].replace('agy-','claude-',1)
    return value
