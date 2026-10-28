"""Shared bounded CLI/MCP schema primitives."""
STRING = {'type':'string'}

def tool(app,name,description,fields,required):
    return {'name':app+'.'+name,'description':description,
            'inputSchema':{'type':'object','properties':fields,'required':required,'additionalProperties':False}}
