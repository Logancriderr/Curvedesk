"""Shared application service used by HTTP and the command-line report."""
from datetime import date
from . import __version__
from .data import load_snapshot, utc_now
from .curves import bootstrap, diagnostics, KEYS
from .analytics import analyze, portfolio, parallel_hedge, scenario
from .mathutils import finite


def calculation(payload, folder):
    source = payload.get('source','demo')
    snap = load_snapshot(source,folder)
    eligible = [r for r in snap['records'] if r['usable']]
    selected = payload.get('curve_date') or eligible[-1]['date']
    row = next((r for r in eligible if r['date'] == selected),None)
    if row is None:
        raise ValueError('Selected curve date is unavailable or incomplete')
    settlement = date.fromisoformat(payload['settlement'])
    if settlement < date.fromisoformat(selected):
        raise ValueError('Settlement cannot precede the curve observation date')
    curve = bootstrap(row['rates'])
    book = portfolio(payload['positions'],settlement,curve)
    custom = payload.get('shocks',[0]*6)
    if len(custom) != 6:
        raise ValueError('Provide six key-rate shocks')
    custom = [finite(x,'Scenario shock bps',-1000,1000) for x in custom]
    spread_shock = finite(payload.get('spread_shock',0),'Spread shock bps',-1000,1000)
    custom_pnl = sum(scenario(r,curve,custom,spread_shock) for r in book['positions'])
    hedge = None
    if payload.get('hedge'):
        h = dict(payload['hedge']); h['face'] = 100000
        hedge = parallel_hedge(book,analyze(h,settlement,curve),curve)
        hedge['name'] = h.get('name','Hedge')
    warnings = []
    age = (date.today()-date.fromisoformat(selected)).days
    if any(r['mode'] in ('clean','yield') and not r['quote_asof'] for r in book['positions']):
        warnings.append('At least one manual quote has no timestamp. Verify freshness with your quote source.')
    if source == 'demo':
        warnings.append('Synthetic demo: all rates and example bonds are invented.')
    elif age > 5:
        warnings.append(f'Curve observation is {age} calendar days old. It is stale for current-market analysis.')
    if settlement.isoformat() != selected:
        warnings.append('Curve tenor rates are applied at the selected settlement date without forecasting their evolution.')
    if any(d['forward_cc_pct'] < 0 for d in diagnostics(curve)):
        warnings.append('Derived curve contains negative forward rates. Review the curve inputs and interpolation.')
    return {'calculated_at':utc_now(),'version':__version__,'source':source,'source_label':snap['label'],'curve_date':selected,
            'retrieved_at':snap['retrieved_at'],'provenance':snap.get('provenance',[]),'settlement':settlement.isoformat(),'rates':row['rates'],
            'key_tenors':KEYS,'curve':diagnostics(curve),'portfolio':book,'hedge':hedge,
            'custom_scenario':{'shocks':custom,'spread_shock':spread_shock,'pnl':custom_pnl},
            'warnings':warnings,'request':payload}
