#!/usr/bin/env python3
"""Canvas MCP stdio adapter. Native code remains the authority for every action.
Protocol reference: https://modelcontextprotocol.io/specification/2025-06-18
"""
import argparse
import json
from pathlib import Path
import sys
import urllib.request
import urllib.error
import urllib.parse

TOOLS = [
    dict(name='read', description='Read the Canvas workspace and candidate, or inspect an exact application subject through the same native presentation used by Canvas. Returned actions are descriptions; this agent connection cannot operate or publish them.',
         inputSchema=dict(type='object',properties={
             'target':dict(type='string',description='Exact native application subject reference. Omit for the current candidate workspace.'),
             'width':dict(type='string',description='Optional native presentation width in pixels, 160–1600.'),
             'children':dict(type='string',description='Opaque child continuation returned by the previous native page.'),
             'epoch':dict(type='string',description='Epoch accompanying that continuation.')},additionalProperties=False),
         annotations=dict(readOnlyHint=True)),
    dict(name='source',description='Read the published Grove source for an exact presentation and revision returned by read. Failed or pending source publication remains explicit.',
         inputSchema=dict(type='object',properties={'target':dict(type='string'),'revision':dict(type='string')},
                          required=['target','revision'],additionalProperties=False),annotations=dict(readOnlyHint=True)),
    dict(name='eval',description='Compile and preview one authored Grove presentation against an exact live subject. Preserves the installed receiver contract, input placements and native actions. Returns native before/after frames and diagnostics; it does not save source, install behavior or execute preview controls.',
         inputSchema=dict(type='object',properties={
             'target':dict(type='string',description='Exact workspace subject from read.'),
             'view':dict(type='string',description='Selected presentation identity.'),
             'revision':dict(type='string',description='Selected presentation revision.'),
             'publication':dict(type='string',description='Publication basis returned by read.'),
             'width':dict(type='string',description='Optional native presentation width, matching Canvas; defaults to 720.'),
             'source':dict(type='string',minLength=1,maxLength=8192,description='Grove source with one @view declaration and optional imports. Keep the selected name, receiver role, slot and native controls.')},
             required=['target','view','revision','publication','source'],additionalProperties=False),
         annotations=dict(readOnlyHint=True)),
    dict(name='continue_candidate', description='Evaluate or continue the candidate already open in Canvas. Native checks preserve prior commitments. This connection cannot publish or reserve equipment.',
         inputSchema=dict(type='object', properties={
             'operation':dict(type='string',enum=['evaluate','stage','demonstrate']),
             'expected':dict(type='string',description='Exact expected case from read.'),
             'event':dict(type='string',minLength=1,maxLength=80),
             'body':dict(type='object',description='Native action arguments; stage/evaluate: turnaround (minute string), same_person (boolean string), intent. demonstrate: exact person/equipment references, start/finish minute strings, available boolean string, label.')},
             required=['operation','expected','event','body'], additionalProperties=False))]

class Adapter:
    def __init__(self, connection):
        self.connection=Path(connection)
        self.initialized=False
        self.ready=False
    def call(self, value):
        cfg=json.loads(self.connection.read_text())
        url=urllib.parse.urlsplit(cfg['url'])
        if url.scheme!='http' or url.hostname!='127.0.0.1' or url.username or url.password:
            raise ValueError('Only the local Canvas connection is supported')
        request=urllib.request.Request(cfg['url']+'/api',json.dumps(value).encode(),
            {'Authorization':'Bearer '+cfg['token'],'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(request,timeout=50) as response:
                return False,json.loads(response.read())
        except urllib.error.HTTPError as error:
            return True,json.loads(error.read())
    def handle(self, message):
        if not isinstance(message,dict) or message.get('jsonrpc')!='2.0':
            return dict(jsonrpc='2.0',id=None,error=dict(code=-32600,message='Invalid request'))
        method=message.get('method');identity=message.get('id');params=message.get('params',{})
        if method=='notifications/initialized':
            self.ready=self.initialized;return None
        if 'id' not in message:
            return None
        result={}
        try:
            if method=='initialize':
                self.initialized=True
                result=dict(protocolVersion='2025-06-18',capabilities=dict(tools={}),
                            serverInfo=dict(name='grove-canvas',version='0.1.0'),
                            instructions='Use native cases and commitments as evidence. The customer approves publication in Canvas. Never describe an unevaluated candidate as installed.')
            elif method=='ping': pass
            elif not self.ready:
                raise ValueError('Initialize the connection first')
            elif method=='tools/list': result={'tools':TOOLS}
            elif method=='tools/call':
                name=params.get('name');args=params.get('arguments',{})
                if not isinstance(args,dict): raise ValueError('Arguments must be an object')
                if name=='read':
                    if not set(args)<=set(('target','children','epoch','width')) or any(not isinstance(value,str) for value in args.values()):
                        raise ValueError('Invalid read reference')
                    if ('children' in args or 'epoch' in args) and 'target' not in args:
                        raise ValueError('A page continuation requires its exact target')
                    failed,data=self.call(dict(operation='present' if args else 'read',expected='0',body=args))
                elif name=='source':
                    if set(args)!=set(('target','revision')) or any(not isinstance(value,str) for value in args.values()):
                        raise ValueError('Exact source target and revision required')
                    failed,data=self.call(dict(operation='source',expected='0',body=args))
                elif name=='eval':
                    required=set(('target','view','revision','publication','source'))
                    if not required<=set(args)<=required|{'width'} or any(not isinstance(value,str) for value in args.values()):
                        raise ValueError('Exact subject, presentation basis and source required')
                    if not 0<len(args['source'].encode())<=8192:
                        raise ValueError('Presentation source must contain 1–8192 bytes')
                    failed,data=self.call(dict(operation='evaluate',expected='0',body={'kind':'presentation',**args}))
                elif name=='continue_candidate':
                    if set(args)!=set(('operation','expected','event','body')) or args['operation'] not in ('evaluate','stage','demonstrate'):
                        raise ValueError('Invalid continuation envelope')
                    failed,data=self.call(args)
                else: raise ValueError('Unknown tool')
                result=dict(content=[dict(type='text',text=json.dumps(data))],structuredContent=data,isError=failed)
            else:
                return dict(jsonrpc='2.0',id=identity,error=dict(code=-32601,message='Method not found'))
        except ValueError as error:
            return dict(jsonrpc='2.0',id=identity,error=dict(code=-32602,message=str(error)))
        except (OSError,urllib.error.URLError):
            result=dict(content=[dict(type='text',text='Local native owner is unavailable.')],isError=True)
        return dict(jsonrpc='2.0',id=identity,result=result)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--connection',type=Path,required=True)
    args=parser.parse_args();adapter=Adapter(args.connection)
    while True:
        line=sys.stdin.buffer.readline(65537)
        if not line:break
        if len(line)>65536:
            raise SystemExit('MCP request exceeds 64 KiB')
        try:message=json.loads(line)
        except ValueError:
            reply=dict(jsonrpc='2.0',id=None,error=dict(code=-32700,message='Invalid JSON'))
        else:reply=adapter.handle(message)
        if reply is not None:
            print(json.dumps(reply),flush=True)
if __name__=='__main__':main()
