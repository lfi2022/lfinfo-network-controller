import os, json, secrets, asyncio
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field
from tplink_tool import make_switch

load_dotenv(Path(__file__).parent / '.env')
app=FastAPI(title='LFINFO Switch Controller',docs_url=None,redoc_url=None)
security=HTTPBasic()
STATIC_DIR = Path(__file__).parent / 'static'
REACT_DIR = STATIC_DIR / 'react'
app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')
SWITCHES={
 '108e': {'name':'TL-SG108E','ip':'10.0.60.200','ports':8,'env':'SW_108E_PASSWORD'},
 '108pe': {'name':'TL-SG108PE','ip':'10.0.60.201','ports':8,'env':'SW_108PE_PASSWORD'},
 '105pe': {'name':'TL-SG105PE','ip':'10.0.60.252','ports':5,'env':'SW_105PE_PASSWORD'},
 '105e': {'name':'TL-SG105E','ip':'10.0.60.253','ports':5,'env':'SW_105E_PASSWORD'},
}
def auth(c:HTTPBasicCredentials=Depends(security)):
 u=os.getenv('ADMIN_USER','admin'); p=os.getenv('ADMIN_PASSWORD','')
 if not p or p.startswith('A_REMPLIR') or not (secrets.compare_digest(c.username,u) and secrets.compare_digest(c.password,p)):
  raise HTTPException(401,'Identifiants invalides',headers={'WWW-Authenticate':'Basic'})
 return c.username

def primitive(o):
 if hasattr(o,'_asdict'): return primitive(o._asdict())
 if isinstance(o,dict): return {str(k):primitive(v) for k,v in o.items()}
 if isinstance(o,(tuple,list)): return [primitive(x) for x in o]
 if isinstance(o,(int,float,str,bool)) or o is None:return o
 if hasattr(o,'name') and hasattr(o,'value'):return str(o.name)
 return str(o)

@contextmanager
def connected(sid):
 if sid not in SWITCHES:raise ValueError('Switch inconnu')
 d=SWITCHES[sid]; password=os.getenv(d['env'],'')
 if not password or password=='A_REMPLIR':raise ValueError('Mot de passe switch non configuré')
 with make_switch(d['ip'],password=password,model='Switch') as sw:yield sw

def fetch(sid):
 with connected(sid) as sw:
  info=primitive(sw.get_system_info()); ports=primitive(sw.get_port_settings())
  vlans_on,vlans=sw.get_dot1q_vlans()
  pvid=primitive(sw.get_pvids())
  vlans=[primitive(x) for x in vlans]
  for v in vlans:
   for k in ('tagged_members','untagged_members'):
    mask=int(v.get(k,0));v[k.replace('_members','_ports')]=[i+1 for i in range(SWITCHES[sid]['ports']) if mask & (1<<i)]
  return {'id':sid,'name':SWITCHES[sid]['name'],'ip':SWITCHES[sid]['ip'],'info':info,'ports':ports,'vlans_enabled':vlans_on,'vlans':vlans,'pvids':pvid,'read_at':datetime.now(timezone.utc).isoformat()}

@app.get('/')
def index(_:str=Depends(auth)):
 # Production serves the compiled React single-page application.
 index_file = REACT_DIR / 'index.html'
 if index_file.exists(): return FileResponse(index_file)
 raise HTTPException(503, 'Frontend React non compilé : exécutez npm run build')
@app.get('/api/controller/status')
def controller_status(_:str=Depends(auth)):
 return {'writes_enabled':os.getenv('ENABLE_WRITES','false').lower()=='true'}

@app.get('/api/switches')
def switches(_:str=Depends(auth)):
 return [{'id':k,'name':v['name'],'ip':v['ip'],'ports':v['ports']} for k,v in SWITCHES.items()]
@app.get('/api/switches/{sid}')
async def details(sid:str,_:str=Depends(auth)):
 try:return await asyncio.wait_for(asyncio.to_thread(fetch,sid),timeout=25)
 except Exception as e:raise HTTPException(502,f'{type(e).__name__}: {str(e)[:200]}')

@app.get('/{full_path:path}', include_in_schema=False)
def frontend_route(full_path:str, _:str=Depends(auth)):
 # Serve the React entry point for client-side navigation such as /ports.
 index_file = REACT_DIR / 'index.html'
 if index_file.exists(): return FileResponse(index_file)
 raise HTTPException(404, 'Frontend React non compilé')

class PortChange(BaseModel):
 enabled:bool
 confirm:bool=False

class PvidChange(BaseModel):
 pvid:int=Field(ge=1,le=4094)
 confirm:bool=False

def write_check(confirm):
 if os.getenv('ENABLE_WRITES','false').lower()!='true':raise HTTPException(403,'Écriture désactivée (ENABLE_WRITES=false)')
 if not confirm:raise HTTPException(400,'Confirmation explicite requise')

def apply_port(sid,port,enabled):
 with connected(sid) as sw:
  sw.set_port(port,enabled=enabled)
  sw.save_config()
 return fetch(sid)

@app.post('/api/switches/{sid}/ports/{port}/enabled')
async def port_enabled(sid:str,port:int,body:PortChange,_:str=Depends(auth)):
 write_check(body.confirm)
 if sid not in SWITCHES or port<1 or port>SWITCHES[sid]['ports']:raise HTTPException(404,'Port ou switch inconnu')
 try:return await asyncio.wait_for(asyncio.to_thread(apply_port,sid,port,body.enabled),timeout=30)
 except Exception as e:raise HTTPException(502,f'Écriture non confirmée: {type(e).__name__}: {str(e)[:200]}')

def apply_pvid(sid,port,pvid):
 with connected(sid) as sw:
  sw.set_pvid([port],pvid)
  sw.save_config()
 return fetch(sid)

@app.post('/api/switches/{sid}/ports/{port}/pvid')
async def set_pvid(sid:str,port:int,body:PvidChange,_:str=Depends(auth)):
 write_check(body.confirm)
 if sid not in SWITCHES or port<1 or port>SWITCHES[sid]['ports']:raise HTTPException(404,'Port ou switch inconnu')
 try:return await asyncio.wait_for(asyncio.to_thread(apply_pvid,sid,port,body.pvid),timeout=30)
 except Exception as e:raise HTTPException(502,f'Écriture non confirmée: {type(e).__name__}: {str(e)[:200]}')
