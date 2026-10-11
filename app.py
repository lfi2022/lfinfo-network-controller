import os, json, secrets, asyncio, sqlite3, logging
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager
from typing import Literal
from dataclasses import asdict, is_dataclass

from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field, field_validator
from tplink_tool import make_switch

ROOT = Path(__file__).parent
load_dotenv(ROOT / '.env')
STATIC_DIR, REACT_DIR = ROOT / 'static', ROOT / 'static' / 'react'
DB_PATH = ROOT / 'data' / 'controller.db'
LEGACY_SWITCHES = [
    {'name': 'TL-SG108E', 'ip': '10.0.60.200', 'model': 'TL-SG108E', 'ports': 8, 'env': 'SW_108E_PASSWORD'},
    {'name': 'TL-SG108PE', 'ip': '10.0.60.201', 'model': 'TL-SG108PE', 'ports': 8, 'env': 'SW_108PE_PASSWORD'},
    {'name': 'TL-SG105PE', 'ip': '10.0.60.252', 'model': 'TL-SG105PE', 'ports': 5, 'env': 'SW_105PE_PASSWORD'},
    {'name': 'TL-SG105E', 'ip': '10.0.60.253', 'model': 'TL-SG105E', 'ports': 5, 'env': 'SW_105E_PASSWORD'},
]

app = FastAPI(title='LFINFO Switch Controller', docs_url=None, redoc_url=None)
app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')
security = HTTPBasic()
logger = logging.getLogger('lfinfo.switches')

def now(): return datetime.now(timezone.utc).isoformat()

def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection

def init_db():
    with db() as conn:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS switches (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, ip TEXT NOT NULL UNIQUE,
            model TEXT NOT NULL, firmware TEXT, ports INTEGER NOT NULL DEFAULT 8,
            credentials BLOB NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
            last_status TEXT NOT NULL DEFAULT 'unknown', last_tested_at TEXT, last_error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL, actor TEXT NOT NULL,
            action TEXT NOT NULL, switch_id INTEGER, details TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS configuration_backups (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, actor TEXT NOT NULL,
            switch_id INTEGER NOT NULL, reason TEXT NOT NULL, snapshot TEXT NOT NULL);
        ''')
        # Lightweight forward migration for controllers created before last_error existed.
        columns = {row['name'] for row in conn.execute('PRAGMA table_info(switches)')}
        if 'last_error' not in columns: conn.execute('ALTER TABLE switches ADD COLUMN last_error TEXT')

@app.on_event('startup')
def startup():
    key = os.getenv('SWITCH_DB_ENCRYPTION_KEY', '')
    if not key:
        raise RuntimeError('SWITCH_DB_ENCRYPTION_KEY est obligatoire')
    try: Fernet(key.encode())
    except Exception as error: raise RuntimeError('SWITCH_DB_ENCRYPTION_KEY doit être une clé Fernet valide') from error
    init_db()

def cipher(): return Fernet(os.environ['SWITCH_DB_ENCRYPTION_KEY'].encode())
def encrypt(password: str): return cipher().encrypt(password.encode()).decode()
def decrypt(value: str):
    try: return cipher().decrypt(value.encode()).decode()
    except InvalidToken as error: raise ValueError('Identifiants chiffrés illisibles') from error

def auth(credentials: HTTPBasicCredentials = Depends(security)):
    expected_user, expected_password = os.getenv('ADMIN_USER', 'admin'), os.getenv('ADMIN_PASSWORD', '')
    if not expected_password or expected_password.startswith('A_REMPLIR') or not (secrets.compare_digest(credentials.username, expected_user) and secrets.compare_digest(credentials.password, expected_password)):
        raise HTTPException(401, 'Identifiants invalides', headers={'WWW-Authenticate': 'Basic'})
    return credentials.username

def audit(actor: str, action: str, switch_id: int | None = None, **details):
    with db() as conn: conn.execute('INSERT INTO audit_log (occurred_at,actor,action,switch_id,details) VALUES (?,?,?,?,?)', (now(), actor, action, switch_id, json.dumps(details)))

def switch_public(row):
    return {'id': str(row['id']), 'name': row['name'], 'ip': row['ip'], 'model': row['model'], 'firmware': row['firmware'], 'ports': row['ports'], 'enabled': bool(row['enabled']), 'last_status': row['last_status'], 'last_tested_at': row['last_tested_at'], 'last_error': row['last_error']}

def find_switch(sid: str):
    with db() as conn: row = conn.execute('SELECT * FROM switches WHERE id=?', (sid,)).fetchone()
    if not row: raise ValueError('Switch inconnu')
    return row

def primitive(value):
    # tplink-tool uses @dataclass for all public read models.  Convert these
    # before the generic fallback: str(Dot1QVlanEntry) would otherwise turn a
    # VLAN into text and fail later at vlan.get(...).
    if is_dataclass(value) and not isinstance(value, type): return primitive(asdict(value))
    if hasattr(value, '_asdict'): return primitive(value._asdict())
    if isinstance(value, dict): return {str(k): primitive(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)): return [primitive(v) for v in value]
    if isinstance(value, (int, float, str, bool)) or value is None: return value
    if hasattr(value, 'name') and hasattr(value, 'value'): return str(value.name)
    return str(value)

def model_override(device):
    """Use the correct protocol family without forcing all devices to Switch."""
    model = str(device['model']).strip().upper()
    # TL-SG105PE V2 is known to require the E-series driver despite unreliable
    # autodetection. The other supported E-series devices may autodetect.
    if model == 'TL-SG105PE': return 'Switch'
    if model.endswith('DE'): return 'SwitchDE'
    if model in {'SWITCH', 'SWITCHDE'}: return model.title().replace('De', 'DE')
    return None

def require_mapping(value, source):
    if not isinstance(value, dict):
        raise TypeError(f'{source} returned {type(value).__name__}, expected a mapping')
    return value

def normalize_vlan_entries(entries):
    if not isinstance(entries, (list, tuple)):
        raise TypeError(f'get_dot1q_vlans() returned entries as {type(entries).__name__}, expected a list')
    normalized = []
    for index, entry in enumerate(entries):
        vlan = require_mapping(primitive(entry), f'get_dot1q_vlans()[{index}]')
        normalized.append(vlan)
    return normalized

@contextmanager
def connected(sid: str):
    device = find_switch(sid)
    if not device['enabled']: raise ValueError('Switch désactivé')
    override = model_override(device)
    kwargs = {'password': decrypt(device['credentials'])}
    if override: kwargs['model'] = override
    with make_switch(device['ip'], **kwargs) as switch: yield switch, device

def fetch(sid: str):
    try:
        with connected(sid) as (switch, device):
            info = require_mapping(primitive(switch.get_system_info()), 'get_system_info()')
            ports = primitive(switch.get_port_settings())
            if not isinstance(ports, list) or not all(isinstance(port, dict) for port in ports):
                raise TypeError('get_port_settings() did not return a list of port mappings')
            dot1q = switch.get_dot1q_vlans()
            if not isinstance(dot1q, tuple) or len(dot1q) != 2:
                raise TypeError(f'get_dot1q_vlans() returned {type(dot1q).__name__}, expected (enabled, entries)')
            vlans_on, raw_vlans = dot1q
            vlans = normalize_vlan_entries(raw_vlans)
            pvids = primitive(switch.get_pvids())
            if not isinstance(pvids, list): raise TypeError(f'get_pvids() returned {type(pvids).__name__}, expected a list')
            for vlan in vlans:
                for key in ('tagged_members', 'untagged_members'):
                    mask = int(vlan.get(key, 0)); vlan[key.replace('_members', '_ports')] = [index + 1 for index in range(device['ports']) if mask & (1 << index)]
            return {**switch_public(device), 'info': info, 'ports': ports, 'vlans_enabled': bool(vlans_on), 'vlans': vlans, 'pvids': pvids, 'read_at': now()}
    except Exception:
        logger.exception('Read failure for switch id=%s', sid)
        raise

def backup(sid: str, actor: str, reason: str):
    snapshot = fetch(sid)
    # Snapshot is explicitly built from fetch(), which contains no encrypted credential field.
    with db() as conn: conn.execute('INSERT INTO configuration_backups (created_at,actor,switch_id,reason,snapshot) VALUES (?,?,?,?,?)', (now(), actor, sid, reason, json.dumps(snapshot)))

class SwitchInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    ip: str = Field(min_length=3, max_length=255)
    model: str = Field(min_length=1, max_length=80)
    firmware: str | None = Field(default=None, max_length=80)
    ports: int = Field(ge=1, le=52)
    password: str = Field(min_length=1, max_length=256)
    enabled: bool = True

    @field_validator('ip')
    @classmethod
    def no_space_ip(cls, value):
        if any(char.isspace() for char in value): raise ValueError('Adresse IP invalide')
        return value

class SwitchUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    ip: str = Field(min_length=3, max_length=255)
    model: str = Field(min_length=1, max_length=80)
    firmware: str | None = Field(default=None, max_length=80)
    ports: int = Field(ge=1, le=52)
    password: str | None = Field(default=None, min_length=1, max_length=256)
    enabled: bool = True

class PortChange(BaseModel): enabled: bool; confirm: bool = False
class PvidChange(BaseModel): pvid: int = Field(ge=1, le=4094); confirm: bool = False

@app.get('/')
def index(_: str = Depends(auth)):
    index_file = REACT_DIR / 'index.html'
    if index_file.exists(): return FileResponse(index_file)
    raise HTTPException(503, 'Frontend React non compilé : exécutez npm run build')

@app.get('/api/controller/status')
def controller_status(_: str = Depends(auth)): return {'writes_enabled': os.getenv('ENABLE_WRITES', 'false').lower() == 'true'}

@app.get('/api/switches')
def switches(_: str = Depends(auth)):
    with db() as conn: return [switch_public(row) for row in conn.execute('SELECT * FROM switches ORDER BY name')]

@app.post('/api/switches', status_code=201)
def create_switch(body: SwitchInput, actor: str = Depends(auth)):
    try:
        with db() as conn:
            cursor = conn.execute('INSERT INTO switches (name,ip,model,firmware,ports,credentials,enabled,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)', (body.name, body.ip, body.model, body.firmware, body.ports, encrypt(body.password), body.enabled, now(), now()))
            row = conn.execute('SELECT * FROM switches WHERE id=?', (cursor.lastrowid,)).fetchone()
        audit(actor, 'switch.created', row['id'], ip=body.ip, model=body.model); return switch_public(row)
    except sqlite3.IntegrityError: raise HTTPException(409, 'Cette adresse IP existe déjà')

@app.put('/api/switches/{sid}')
def update_switch(sid: str, body: SwitchUpdate, actor: str = Depends(auth)):
    try: current = find_switch(sid)
    except ValueError as error: raise HTTPException(404, str(error))
    credentials = encrypt(body.password) if body.password else current['credentials']
    try:
        with db() as conn:
            conn.execute('UPDATE switches SET name=?,ip=?,model=?,firmware=?,ports=?,credentials=?,enabled=?,updated_at=? WHERE id=?', (body.name, body.ip, body.model, body.firmware, body.ports, credentials, body.enabled, now(), sid))
            row = conn.execute('SELECT * FROM switches WHERE id=?', (sid,)).fetchone()
        audit(actor, 'switch.updated', int(sid), ip=body.ip, password_changed=bool(body.password)); return switch_public(row)
    except sqlite3.IntegrityError: raise HTTPException(409, 'Cette adresse IP existe déjà')

@app.delete('/api/switches/{sid}', status_code=204)
def delete_switch(sid: str, actor: str = Depends(auth)):
    try: current = find_switch(sid)
    except ValueError as error: raise HTTPException(404, str(error))
    with db() as conn: conn.execute('DELETE FROM switches WHERE id=?', (sid,))
    audit(actor, 'switch.deleted', int(sid), ip=current['ip']); return None

@app.post('/api/switches/{sid}/test')
async def test_switch(sid: str, actor: str = Depends(auth)):
    try:
        detail = await asyncio.wait_for(asyncio.to_thread(fetch, sid), timeout=25)
        with db() as conn: conn.execute("UPDATE switches SET last_status='online',last_tested_at=?,last_error=NULL WHERE id=?", (now(), sid))
        audit(actor, 'switch.test_succeeded', int(sid)); return {'ok': True, 'switch': detail}
    except Exception as error:
        # The message is capped before storage and response; credentials are never interpolated here.
        message = f'{type(error).__name__}: {str(error)[:200]}'
        with db() as conn: conn.execute("UPDATE switches SET last_status='offline',last_tested_at=?,last_error=? WHERE id=?", (now(), message, sid))
        audit(actor, 'switch.test_failed', int(sid), error=type(error).__name__)
        raise HTTPException(502, message)

@app.post('/api/switches/import-legacy')
def import_legacy(actor: str = Depends(auth)):
    added, skipped = [], []
    for item in LEGACY_SWITCHES:
        password = os.getenv(item['env'], '')
        if not password or password.startswith('A_REMPLIR'): skipped.append({'ip': item['ip'], 'reason': 'mot de passe absent'}); continue
        with db() as conn:
            exists = conn.execute('SELECT id FROM switches WHERE ip=?', (item['ip'],)).fetchone()
            if exists: skipped.append({'ip': item['ip'], 'reason': 'déjà importé'}); continue
            cursor = conn.execute('INSERT INTO switches (name,ip,model,ports,credentials,enabled,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)', (item['name'], item['ip'], item['model'], item['ports'], encrypt(password), True, now(), now()))
        added.append(item['ip']); audit(actor, 'switch.legacy_imported', cursor.lastrowid, source=item['env'])
    return {'added': added, 'skipped': skipped}

@app.get('/api/audit')
def audit_entries(_: str = Depends(auth)):
    with db() as conn: return [dict(row) for row in conn.execute('SELECT * FROM audit_log ORDER BY id DESC LIMIT 100')]

@app.get('/api/backups')
def backups(_: str = Depends(auth)):
    with db() as conn: return [dict(row) for row in conn.execute('SELECT id,created_at,actor,switch_id,reason FROM configuration_backups ORDER BY id DESC LIMIT 100')]

@app.get('/api/switches/{sid}')
async def details(sid: str, _: str = Depends(auth)):
    try: return await asyncio.wait_for(asyncio.to_thread(fetch, sid), timeout=25)
    except Exception as error: raise HTTPException(502, f'{type(error).__name__}: {str(error)[:200]}')

def write_check(confirm: bool):
    if os.getenv('ENABLE_WRITES', 'false').lower() != 'true': raise HTTPException(403, 'Écriture désactivée (ENABLE_WRITES=false)')
    if not confirm: raise HTTPException(400, 'Confirmation explicite requise')

def apply_port(sid, port, enabled, actor):
    backup(sid, actor, f'port {port}: enabled={enabled}')
    with connected(sid) as (switch, _): switch.set_port(port, enabled=enabled); switch.save_config()
    audit(actor, 'port.enabled_changed', int(sid), port=port, enabled=enabled); return fetch(sid)

@app.post('/api/switches/{sid}/ports/{port}/enabled')
async def port_enabled(sid: str, port: int, body: PortChange, actor: str = Depends(auth)):
    write_check(body.confirm)
    try:
        device = find_switch(sid)
        if port < 1 or port > device['ports']: raise ValueError('Port inconnu')
        return await asyncio.wait_for(asyncio.to_thread(apply_port, sid, port, body.enabled, actor), timeout=30)
    except Exception as error: raise HTTPException(502, f'Écriture non confirmée: {type(error).__name__}: {str(error)[:200]}')

def apply_pvid(sid, port, pvid, actor):
    backup(sid, actor, f'port {port}: pvid={pvid}')
    with connected(sid) as (switch, _): switch.set_pvid([port], pvid); switch.save_config()
    audit(actor, 'port.pvid_changed', int(sid), port=port, pvid=pvid); return fetch(sid)

@app.post('/api/switches/{sid}/ports/{port}/pvid')
async def set_pvid(sid: str, port: int, body: PvidChange, actor: str = Depends(auth)):
    write_check(body.confirm)
    try:
        device = find_switch(sid)
        if port < 1 or port > device['ports']: raise ValueError('Port inconnu')
        return await asyncio.wait_for(asyncio.to_thread(apply_pvid, sid, port, body.pvid, actor), timeout=30)
    except Exception as error: raise HTTPException(502, f'Écriture non confirmée: {type(error).__name__}: {str(error)[:200]}')

@app.get('/{full_path:path}', include_in_schema=False)
def frontend_route(full_path: str, _: str = Depends(auth)):
    index_file = REACT_DIR / 'index.html'
    if index_file.exists(): return FileResponse(index_file)
    raise HTTPException(404, 'Frontend React non compilé')
