import os, json, secrets, asyncio, sqlite3, logging, threading, time
from pathlib import Path
from datetime import datetime, timezone, timedelta
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
COLLECTION_STOP = threading.Event()
SWITCH_LOCKS: dict[str, threading.Lock] = {}
SWITCH_LOCKS_GUARD = threading.Lock()

def switch_lock(sid: str):
    with SWITCH_LOCKS_GUARD:
        return SWITCH_LOCKS.setdefault(str(sid), threading.Lock())

def collection_interval(): return max(30, int(os.getenv('STATS_COLLECTION_INTERVAL_SECONDS', '60')))
def retention_days(): return max(1, int(os.getenv('STATS_RETENTION_DAYS', '30')))
def live_interval(): return max(5, int(os.getenv('LIVE_COLLECTION_INTERVAL_SECONDS', '5')))
def live_ttl_seconds(): return max(10, int(os.getenv('LIVE_CLIENT_TTL_SECONDS', '15')))

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
        CREATE TABLE IF NOT EXISTS port_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT, recorded_at TEXT NOT NULL,
            switch_id INTEGER NOT NULL, port INTEGER NOT NULL, tx_pkts INTEGER,
            rx_pkts INTEGER, tx_pps REAL, rx_pps REAL, active INTEGER NOT NULL,
            speed_mbps INTEGER, speed_cfg TEXT);
        CREATE INDEX IF NOT EXISTS idx_port_samples_time ON port_samples(recorded_at);
        CREATE INDEX IF NOT EXISTS idx_port_samples_switch_port ON port_samples(switch_id, port, recorded_at);
        CREATE TABLE IF NOT EXISTS collection_status (
            switch_id INTEGER PRIMARY KEY, collected_at TEXT, last_error TEXT);
        CREATE TABLE IF NOT EXISTS switch_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT, recorded_at TEXT NOT NULL,
            switch_id INTEGER NOT NULL, vlan_count INTEGER);
        CREATE INDEX IF NOT EXISTS idx_switch_samples_time ON switch_samples(recorded_at);
        CREATE TABLE IF NOT EXISTS live_clients (
            switch_id INTEGER NOT NULL, client_id TEXT NOT NULL, expires_at TEXT NOT NULL,
            PRIMARY KEY (switch_id, client_id));
        CREATE INDEX IF NOT EXISTS idx_live_clients_expiry ON live_clients(expires_at);
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
    COLLECTION_STOP.clear()
    threading.Thread(target=collection_loop, name='lfinfo-port-collector', daemon=True).start()

@app.on_event('shutdown')
def shutdown():
    COLLECTION_STOP.set()

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
    if model.startswith('TL-SG105PE'): return 'Switch'
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
        with switch_lock(sid):
            with connected(sid) as (switch, device):
                info, ports, vlans_on, vlans, pvids = read_switch(switch, device['ports'])
                return {**switch_public(device), 'info': info, 'ports': ports, 'vlans_enabled': bool(vlans_on), 'vlans': vlans, 'pvids': pvids, 'read_at': now()}
    except Exception:
        logger.exception('Read failure for switch id=%s', sid)
        raise

def read_switch(switch, port_count):
    """Read and validate SDK objects. This function never writes to hardware."""
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
            mask = int(vlan.get(key, 0)); vlan[key.replace('_members', '_ports')] = [index + 1 for index in range(port_count) if mask & (1 << index)]
    return info, ports, vlans_on, vlans, pvids

def discover_switch(switch):
    """Découverte en lecture seule, tolérante aux ports non pris en charge."""
    info = require_mapping(
        primitive(switch.get_system_info()),
        'get_system_info()'
    )

    try:
        ports = primitive(switch.get_port_settings())
        if not isinstance(ports, list) or not all(
            isinstance(port, dict) for port in ports
        ):
            ports = []
    except (RuntimeError, ValueError, TypeError):
        ports = []

    return info, ports

def speed_mbps(value):
    """Convert SDK speed labels to Mbps; never infer throughput from packets."""
    text = str(value or '').upper()
    if '1000' in text or '1G' in text: return 1000
    if '100' in text: return 100
    if '10' in text: return 10
    return None

def packet_rate(current, previous, recorded_at):
    """Return packets/s only for monotonic counters with a positive interval."""
    if not previous or current is None: return None
    previous_value, previous_at = previous
    delta_seconds = (datetime.fromisoformat(recorded_at) - datetime.fromisoformat(previous_at)).total_seconds()
    if previous_value is None or current < previous_value or delta_seconds <= 0:
        return None  # Counter reset/reboot or an invalid timestamp: never fake a rate.
    return round((current - previous_value) / delta_seconds, 3)

def collect_switch_statistics(sid: str):
    """Read one switch once. The caller must hold its per-switch lock."""
    with connected(sid) as (switch, device):
        settings = primitive(switch.get_port_settings())
        stats = primitive(switch.get_port_statistics())
        if not isinstance(settings, list) or not all(isinstance(item, dict) for item in settings):
            raise TypeError('get_port_settings() did not return a list of mappings')
        if not isinstance(stats, list) or not all(isinstance(item, dict) for item in stats):
            raise TypeError('get_port_statistics() did not return a list of mappings')
        settings_by_port = {int(item['port']): item for item in settings if item.get('port') is not None}
        recorded_at = now()
        vlan_count = None
        try:
            dot1q = switch.get_dot1q_vlans()
            if isinstance(dot1q, tuple) and len(dot1q) == 2 and isinstance(dot1q[1], (list, tuple)):
                vlan_count = len(dot1q[1])
        except Exception:
            logger.info('VLAN count unavailable during statistics collection for switch id=%s', sid, exc_info=True)
        with db() as conn:
            for item in stats:
                port = int(item['port']); tx = item.get('tx_pkts'); rx = item.get('rx_pkts')
                if not isinstance(tx, int) or not isinstance(rx, int):
                    raise TypeError(f'get_port_statistics() port {port} returned non-integer counters')
                old = conn.execute('SELECT tx_pkts,rx_pkts,recorded_at FROM port_samples WHERE switch_id=? AND port=? ORDER BY id DESC LIMIT 1', (sid, port)).fetchone()
                previous_tx = (old['tx_pkts'], old['recorded_at']) if old else None
                previous_rx = (old['rx_pkts'], old['recorded_at']) if old else None
                setting = settings_by_port.get(port, {})
                conn.execute('INSERT INTO port_samples (recorded_at,switch_id,port,tx_pkts,rx_pkts,tx_pps,rx_pps,active,speed_mbps,speed_cfg) VALUES (?,?,?,?,?,?,?,?,?,?)', (
                    recorded_at, sid, port, tx, rx, packet_rate(tx, previous_tx, recorded_at), packet_rate(rx, previous_rx, recorded_at),
                    bool(setting.get('speed_act')), speed_mbps(setting.get('speed_act')), str(setting.get('speed_cfg') or ''),
                ))
            conn.execute('INSERT INTO switch_samples (recorded_at,switch_id,vlan_count) VALUES (?,?,?)', (recorded_at, sid, vlan_count))
            conn.execute('INSERT INTO collection_status(switch_id,collected_at,last_error) VALUES(?,?,NULL) ON CONFLICT(switch_id) DO UPDATE SET collected_at=excluded.collected_at,last_error=NULL', (sid, recorded_at))
            conn.execute("DELETE FROM port_samples WHERE recorded_at < ?", ((datetime.now(timezone.utc) - timedelta(days=retention_days())).isoformat(),))
            conn.execute("DELETE FROM switch_samples WHERE recorded_at < ?", ((datetime.now(timezone.utc) - timedelta(days=retention_days())).isoformat(),))
        return len(stats)

def live_switch_ids():
    current = now()
    with db() as conn:
        conn.execute('DELETE FROM live_clients WHERE expires_at<?', (current,))
        return {row['switch_id'] for row in conn.execute('SELECT DISTINCT switch_id FROM live_clients WHERE expires_at>=?', (current,))}

def collection_due(sid, interval):
    with db() as conn: row = conn.execute('SELECT MAX(recorded_at) AS last_at FROM port_samples WHERE switch_id=?', (sid,)).fetchone()
    if not row or not row['last_at']: return True
    return (datetime.now(timezone.utc) - datetime.fromisoformat(row['last_at'])).total_seconds() >= interval

def collect_all_statistics():
    active_live = live_switch_ids()
    with db() as conn: devices = [row['id'] for row in conn.execute('SELECT id FROM switches WHERE enabled=1')]
    for sid in devices:
        interval = live_interval() if sid in active_live else collection_interval()
        if not collection_due(sid, interval): continue
        lock = switch_lock(sid)
        if not lock.acquire(blocking=False):
            logger.info('Statistics skipped for switch id=%s: another read is active', sid)
            continue
        try:
            collect_switch_statistics(str(sid))
        except Exception as error:
            logger.exception('Statistics collection failed for switch id=%s', sid)
            with db() as conn: conn.execute('INSERT INTO collection_status(switch_id,collected_at,last_error) VALUES(?,?,?) ON CONFLICT(switch_id) DO UPDATE SET collected_at=excluded.collected_at,last_error=excluded.last_error', (sid, now(), f'{type(error).__name__}: {str(error)[:200]}'))
        finally: lock.release()

def collection_loop():
    while not COLLECTION_STOP.is_set():
        try: collect_all_statistics()
        except Exception: logger.exception('Statistics collector cycle failed')
        # A short scheduler tick enables Live Traffic without giving clients
        # direct access to switch hardware. Per-switch due checks cap polling.
        COLLECTION_STOP.wait(1)


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

class NewSwitchInput(BaseModel):
    ip: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=256)

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
def create_switch(body: NewSwitchInput, actor: str = Depends(auth)):
    try:
        # Detect every display field from the hardware before creating a record.
        # A new/unlisted Easy Smart model first uses factory autodetection, then
        # the known E-series fallback used for TL-SG105PE.
        try:
            with make_switch(body.ip, password=body.password, model='Switch') as switch:
                info, ports = discover_switch(switch)
        except ValueError:
            with make_switch(body.ip, password=body.password, model='Switch') as switch:
                info, ports = discover_switch(switch)
        model = str(info.get('hardware') or info.get('description') or 'TP-Link Easy Smart')
        name = str(info.get('description') or model)
        firmware = str(info.get('firmware') or '') or None
        with db() as conn:
            cursor = conn.execute('INSERT INTO switches (name,ip,model,firmware,ports,credentials,enabled,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)', (name, body.ip, model, firmware, len(ports), encrypt(body.password), True, now(), now()))
            row = conn.execute('SELECT * FROM switches WHERE id=?', (cursor.lastrowid,)).fetchone()
        audit(actor, 'switch.created', row['id'], ip=body.ip, model=model, discovered_ports=len(ports)); return switch_public(row)
    except sqlite3.IntegrityError: raise HTTPException(409, 'Cette adresse IP existe déjà')
    except Exception as error:
        logger.exception('Discovery failed for new switch ip=%s', body.ip)
        raise HTTPException(502, f'Découverte impossible: {type(error).__name__}: {str(error)[:200]}')

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

@app.get('/api/statistics')
def statistics(period: Literal['15m', '1h', '6h', '24h'] = '1h', switch_id: str | None = None, _: str = Depends(auth)):
    windows = {'15m': timedelta(minutes=15), '1h': timedelta(hours=1), '6h': timedelta(hours=6), '24h': timedelta(hours=24)}
    start = (datetime.now(timezone.utc) - windows[period]).isoformat()
    query, params = 'SELECT recorded_at,switch_id,port,tx_pps,rx_pps,active,speed_mbps,speed_cfg FROM port_samples WHERE recorded_at>=?', [start]
    vlan_query, vlan_params = 'SELECT recorded_at,switch_id,vlan_count FROM switch_samples WHERE recorded_at>=?', [start]
    status_query, status_params = 'SELECT switch_id,collected_at,last_error FROM collection_status', []
    if switch_id:
        query += ' AND switch_id=?'; params.append(switch_id)
        vlan_query += ' AND switch_id=?'; vlan_params.append(switch_id)
        status_query += ' WHERE switch_id=?'; status_params.append(switch_id)
    query += ' ORDER BY recorded_at ASC'; vlan_query += ' ORDER BY recorded_at ASC'
    with db() as conn:
        samples = [dict(row) for row in conn.execute(query, params)]
        vlan_samples = [dict(row) for row in conn.execute(vlan_query, vlan_params)]
        collection = [dict(row) for row in conn.execute(status_query, status_params)]
    return {'period': period, 'start': start, 'samples': samples, 'vlan_samples': vlan_samples, 'collection': collection, 'retention_days': retention_days(), 'interval_seconds': collection_interval()}

@app.get('/api/live/switches/{sid}')
def live_traffic(sid: str, client_id: str, _: str = Depends(auth)):
    """Register an in-memory-browser viewer; this endpoint only reads SQLite."""
    if not client_id or len(client_id) > 100: raise HTTPException(422, 'Identifiant Live invalide')
    try: find_switch(sid)
    except ValueError as error: raise HTTPException(404, str(error))
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=live_ttl_seconds())).isoformat()
    with db() as conn:
        conn.execute('INSERT INTO live_clients(switch_id,client_id,expires_at) VALUES(?,?,?) ON CONFLICT(switch_id,client_id) DO UPDATE SET expires_at=excluded.expires_at', (sid, client_id, expires_at))
        samples = [dict(row) for row in conn.execute('SELECT recorded_at,port,tx_pps,rx_pps,active,speed_mbps,speed_cfg FROM port_samples WHERE switch_id=? ORDER BY id DESC LIMIT 80', (sid,))]
        status = conn.execute('SELECT collected_at,last_error FROM collection_status WHERE switch_id=?', (sid,)).fetchone()
    samples.reverse()
    return {'switch_id': sid, 'samples': samples, 'collection_interval_seconds': live_interval(), 'client_expires_at': expires_at, 'collected_at': status['collected_at'] if status else None, 'last_error': status['last_error'] if status else None}

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
