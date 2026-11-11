"""Official Treasury XML ingestion, explicit synthetic demo, and atomic snapshots."""
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError
from urllib.parse import urlencode
import csv
import hashlib
import io
import json
import os
import tempfile
import xml.etree.ElementTree as ET
from .curves import bootstrap, REQUIRED
from .mathutils import finite

ENDPOINT = 'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml'
FIELDS = {'BC_1MONTH':1/12,'BC_2MONTH':2/12,'BC_3MONTH':.25,'BC_4MONTH':4/12,
          'BC_6MONTH':.5,'BC_1YEAR':1.,'BC_2YEAR':2.,'BC_3YEAR':3.,'BC_5YEAR':5.,
          'BC_7YEAR':7.,'BC_10YEAR':10.,'BC_20YEAR':20.,'BC_30YEAR':30.}
CSV_TENORS = {'6M':.5,'1Y':1.,'2Y':2.,'3Y':3.,'5Y':5.,'7Y':7.,'10Y':10.,'20Y':20.,'30Y':30.}


def parse_xml(raw, year, today=None):
    today = today or date.today()
    if len(raw) > 8_000_000 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('XML is too large or contains forbidden declarations')
    root = ET.fromstring(raw)
    records, seen = [], set()
    for el in root.iter():
        if el.tag.rsplit('}',1)[-1] != 'properties':
            continue
        props = {c.tag.rsplit('}',1)[-1]:c.text for c in el}
        if not props.get('NEW_DATE'):
            raise ValueError('Treasury record has no NEW_DATE')
        d = date.fromisoformat(props['NEW_DATE'][:10])
        if d.year != year or d > today or d in seen:
            raise ValueError('Unexpected year, future date or duplicate Treasury observation')
        seen.add(d)
        rates = {}
        for field,t in FIELDS.items():
            v = props.get(field)
            rates[str(t)] = None if v is None or v.strip() in ('','N/A','ND') else finite(v,'Treasury rate percent',-5,30)
        records.append({'date':d.isoformat(),'rates':rates})
    if not records and root.tag.rsplit('}',1)[-1] != 'feed':
        raise ValueError('Response is not a Treasury XML feed')
    return sorted(records,key=lambda r:r['date'])


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def validate_snapshot(snap):
    if snap.get('source') not in ('treasury','custom','demo'):
        raise ValueError('Unknown snapshot source')
    records = snap.get('records',[])
    if not 1 <= len(records) <= 5000:
        raise ValueError('Snapshot must contain 1 to 5000 dated observations')
    seen, usable = set(), 0
    for row in records:
        d = date.fromisoformat(row['date'])
        if d > date.today() or d in seen:
            raise ValueError('Future or duplicate curve observation date')
        seen.add(d)
        vals = {float(k):v for k,v in row['rates'].items()}
        for t,v in vals.items():
            finite(t,'Tenor',.01,30)
            if v is not None:
                finite(v,'Rate percent',-5,30)
        complete = all(vals.get(t) is not None for t in REQUIRED)
        if complete:
            bootstrap(vals)
            usable += 1
        row['usable'] = complete
    if not usable:
        raise ValueError('No complete, usable curve observations')
    snap['records'] = sorted(records,key=lambda r:r['date'])
    return snap


def save_snapshot(snap, folder):
    """Validate before publishing; os.replace gives readers an all-or-nothing snapshot."""
    validate_snapshot(snap)
    folder = Path(folder); folder.mkdir(parents=True,exist_ok=True)
    data = json.dumps(snap,allow_nan=False,indent=2).encode()
    target = folder / (snap['source']+'.json')
    fd, tmp = tempfile.mkstemp(dir=folder, prefix='.pending-')
    try:
        with os.fdopen(fd,'wb') as out:
            out.write(data); out.flush(); os.fsync(out.fileno())
        os.replace(tmp,target)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return snap


def load_snapshot(source, folder):
    if source == 'demo':
        return demo_snapshot()
    if source not in ('treasury','custom'):
        raise ValueError('Choose demo, treasury or custom data')
    path = Path(folder)/(source+'.json')
    if not path.exists():
        raise ValueError('No saved snapshot. Fetch Treasury data or import a curve CSV first.')
    return validate_snapshot(json.loads(path.read_text(encoding='utf-8')))


def fetch_treasury(folder, today=None, opener=urlopen):
    today = today or date.today()
    records, provenance = [], []
    for year in (today.year-1,today.year):
        url = ENDPOINT+'?'+urlencode({'data':'daily_treasury_yield_curve','field_tdr_date_value':year})
        request = Request(url,headers={'User-Agent':'CurveDesk/1.0 (local research dashboard)','Accept':'application/xml'})
        try:
            with opener(request,timeout=20) as response:
                raw = response.read(8_000_001)
        except (OSError, URLError) as e:
            raise ValueError('Treasury download failed. Check your connection or import a curve CSV. The last saved snapshot is unchanged.') from e
        parsed = parse_xml(raw,year,today)
        if year < today.year and not parsed:
            raise ValueError('Previous-year Treasury feed was empty; snapshot unchanged')
        records.extend(parsed)
        provenance.append({'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'rows':len(parsed)})
    snap = {'source':'treasury','label':'US Treasury daily published par rates','retrieved_at':utc_now(),
            'provenance':provenance,'records':records,'units':'annual percent'}
    return save_snapshot(snap,folder)


def import_curve_csv(text, folder):
    reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    required = {'date',*CSV_TENORS}
    if not reader.fieldnames or set(reader.fieldnames) != required or len(reader.fieldnames) != len(required):
        raise ValueError('Curve CSV headers must be date,6M,1Y,2Y,3Y,5Y,7Y,10Y,20Y,30Y')
    records = []
    for row in reader:
        rates = {str(t):finite(row[col],'CSV rate percent',-5,30) for col,t in CSV_TENORS.items()}
        records.append({'date':row['date'],'rates':rates})
    return save_snapshot({'source':'custom','label':'User-supplied par curve CSV; source not independently verified',
                          'retrieved_at':utc_now(),'units':'annual percent',
                          'provenance':[{'sha256':hashlib.sha256(text.encode()).hexdigest()}],
                          'records':records},folder)


def demo_snapshot():
    """Invented, reproducible observations. Never used as a live failure fallback."""
    base = {1/12:4.3,.25:4.25,.5:4.15,1.:4.0,2.:3.85,3.:3.9,5.:4.05,7.:4.2,10.:4.35,20.:4.65,30.:4.7}
    end = date(2026,1,15)
    records = []
    for k in range(45):
        d = end-timedelta(days=k)
        if d.weekday() < 5:
            rates = {str(t):round(v + .0015*k*(1-t/35),4) for t,v in base.items()}
            records.append({'date':d.isoformat(),'rates':rates})
    return validate_snapshot({'source':'demo','label':'SYNTHETIC DEMO — invented rates and bonds',
                              'retrieved_at':None,'units':'annual percent','provenance':[], 'records':records})
