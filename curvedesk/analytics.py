"""Quote reconciliation, portfolio aggregation, curve scenarios and cash-bond hedges."""
from datetime import date, datetime, timezone
from .bonds import Bond, dirty_from_yield, yield_from_clean, yield_risk
from .curves import KEYS, price_flows
from .mathutils import finite, bisect_root


def parse_position(row):
    frequency = finite(row.get('frequency', 2), 'Coupon frequency', 1, 4)
    if frequency != int(frequency):
        raise ValueError('Coupon frequency must be an integer')
    bond = Bond(str(row.get('name','Bond')), date.fromisoformat(row['maturity']),
                finite(row['coupon_pct'],'Coupon percent',0,30)/100, int(frequency),
                row.get('convention','treasury'))
    face = finite(row.get('face',100000),'Signed face value',-1e10,1e10)
    mode = row.get('mode','spread')
    if mode not in ('spread','clean','yield'):
        raise ValueError('Valuation mode must be spread, clean or yield')
    value = finite(row.get('value',0),'Valuation input')
    return bond, face, mode, value


def analyze(row, settlement, curve):
    bond, face, mode, value = parse_position(row)
    ai, flows = bond.cashflows(settlement)
    quote_asof = row.get('quote_asof','')
    if quote_asof:
        quoted = datetime.fromisoformat(quote_asof.replace('Z','+00:00'))
        if quoted.tzinfo is None or quoted > datetime.now(timezone.utc):
            raise ValueError('Quote timestamp needs a timezone and cannot be in the future')
    raw = price_flows(flows,curve)
    if mode == 'clean':
        target = finite(value,'Clean price',.01,1000)+ai
    elif mode == 'yield':
        target = dirty_from_yield(bond, settlement, value/100)
    else:
        target = None
    spread = (bisect_root(lambda z:price_flows(flows,curve,z)-target,-5000,10000)
              if target is not None else finite(value,'Spread bps',-1000,3000))
    pv = price_flows(flows,curve,spread)
    y = yield_from_clean(bond,settlement,pv-ai)
    result = yield_risk(bond,settlement,y)
    down = price_flows(flows,curve,spread,[-1]*6)
    up = price_flows(flows,curve,spread,[1]*6)
    dv = (down-up)/2
    key = []
    for k in range(6):
        shift = [float(j == k) for j in range(6)]
        key.append((price_flows(flows,curve,spread,[-s for s in shift])-price_flows(flows,curve,spread,shift))/2)
    result.update({'name':bond.name,'maturity':bond.maturity.isoformat(),'coupon_pct':bond.coupon*100,
                   'dirty':pv,'clean':pv-ai,'quote_asof':quote_asof,'face':face,'mode':mode,'input_value':value,'curve_clean':raw-ai,'z_spread_bps':spread,
                   'market_value':pv*face/100,'accrued_dollars':ai*face/100,
                   'curve_dv01':dv*face/100,'curve_duration':dv/(.0001*pv),
                   'curve_convexity':(down+up-2*pv)/(.0001**2*pv),
                   'key_dv01':[x*face/100 for x in key], 'cashflows':flows})
    for cf in result['cashflows']:
        cf['pv_per100'] = price_flows([cf],curve,spread)
        cf['position_cashflow'] = cf['amount']*face/100
    return result


def scenario(result, curve, shocks, spread_shock=0):
    pv = price_flows(result['cashflows'],curve,result['z_spread_bps']+spread_shock,shocks)
    return (pv-result['dirty'])*result['face']/100


SCENARIOS = {
    'Rates +100 bp': [100]*6,
    'Rates −100 bp': [-100]*6,
    'Bear steepener': [0,10,25,50,75,100],
    'Bull flattener': [0,-10,-25,-50,-75,-100],
    'Belly +50 bp': [0,0,50,25,0,0],
}


def portfolio(rows, settlement, curve):
    if not isinstance(rows,list) or not 1 <= len(rows) <= 100:
        raise ValueError('Supply 1 to 100 positions')
    results = []
    for n,row in enumerate(rows,1):
        try:
            results.append(analyze(row,settlement,curve))
        except (ValueError, KeyError, TypeError) as e:
            raise ValueError(f'Position {n}: {e}') from e
    total = sum(r['market_value'] for r in results)
    gross = sum(abs(r['market_value']) for r in results)
    keys = [sum(r['key_dv01'][i] for r in results) for i in range(6)]
    stresses = [{'name':name,'shocks':shocks,'pnl':sum(scenario(r,curve,shocks) for r in results)}
                for name,shocks in SCENARIOS.items()]
    stresses.append({'name':'All spreads +50 bp','shocks':[0]*6,
                     'pnl':sum(scenario(r,curve,[0]*6,50) for r in results)})
    return {'positions':results,'net_market_value':total,'gross_market_value':gross,
            'dv01':sum(r['curve_dv01'] for r in results),'key_dv01':keys,'scenarios':stresses}


def parallel_hedge(book, hedge, curve):
    unit = hedge['curve_dv01'] / hedge['face'] if hedge['face'] else 0
    if abs(unit) < 1e-10:
        raise ValueError('Hedge bond has too little DV01')
    face = -book['dv01']/unit
    remaining = [a+b*face/hedge['face'] for a,b in zip(book['key_dv01'],hedge['key_dv01'])]
    stresses = []
    for s in book['scenarios']:
        spread_shift = 50 if s['name'] == 'All spreads +50 bp' else 0
        hedge_pnl = scenario(hedge,curve,s['shocks'],spread_shift)*face/hedge['face']
        stresses.append({'name':s['name'],'before':s['pnl'],'after':s['pnl']+hedge_pnl})
    return {'signed_face':face,'residual_key_dv01':remaining,
            'residual_dv01':book['dv01']+unit*face,'scenarios':stresses}
