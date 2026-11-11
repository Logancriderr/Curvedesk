"""Regular fixed-rate bullet bonds. Prices per 100; rates are decimals internally."""
from dataclasses import dataclass
from datetime import date
import calendar
from .mathutils import finite, bisect_root


def add_months(anchor, months):
    """Always derive from the original anchor, preserving its end-of-month rule."""
    n = anchor.year * 12 + anchor.month - 1 + months
    y, m = divmod(n, 12)
    m += 1
    eom = anchor.day == calendar.monthrange(anchor.year, anchor.month)[1]
    day = calendar.monthrange(y, m)[1] if eom else min(anchor.day, calendar.monthrange(y, m)[1])
    return date(y, m, day)


@dataclass(frozen=True)
class Bond:
    name: str
    maturity: date
    coupon: float
    frequency: int = 2
    convention: str = 'treasury'

    def __post_init__(self):
        if not isinstance(self.name, str) or not 1 <= len(self.name.strip()) <= 80:
            raise ValueError('Bond name must have 1 to 80 characters')
        finite(self.coupon, 'Coupon decimal', 0, .30)
        if isinstance(self.frequency, bool) or self.frequency not in (1, 2, 4):
            raise ValueError('Frequency must be 1, 2 or 4')
        if self.convention not in ('treasury', 'periodic'):
            raise ValueError('Convention must be treasury or periodic')
        if self.convention == 'treasury' and self.frequency != 2:
            raise ValueError('Treasury convention requires semiannual coupons')

    def schedule(self, settlement):
        if not settlement < self.maturity:
            raise ValueError('Settlement must precede maturity')
        if (self.maturity - settlement).days / 365 > 30.1:
            raise ValueError('Remaining maturity exceeds the supported 30-year range')
        future = []
        for k in range(130):
            d = add_months(self.maturity, -(12 // self.frequency) * k)
            if d <= settlement:
                return d, list(reversed(future))
            future.append(d)
        raise ValueError('Coupon schedule exceeds supported range')

    def cashflows(self, settlement):
        previous, dates = self.schedule(settlement)
        elapsed = (settlement - previous).days / (dates[0] - previous).days
        # Regular Actual/Actual ICMA accrual; same-day coupon already belongs to seller.
        accrued = 100 * self.coupon / self.frequency * elapsed
        flows = [{'date': d.isoformat(), 'years': (d-settlement).days / 365,
                  'periods': 1-elapsed+k, 'coupon': 100*self.coupon/self.frequency,
                  'principal': 100.0 if d == self.maturity else 0.0}
                 for k, d in enumerate(dates)]
        for cf in flows:
            cf['amount'] = cf['coupon'] + cf['principal']
        return accrued, flows


def dirty_from_yield(bond, settlement, y):
    y = finite(y, 'Yield decimal', -.50, 2.0)
    _, flows = bond.cashflows(settlement)
    f = bond.frequency
    if bond.convention == 'treasury' and len(flows) == 1:
        return flows[0]['amount'] / (1 + y/f * flows[0]['periods'])
    return sum(cf['amount'] / (1+y/f)**cf['periods'] for cf in flows)


def yield_from_clean(bond, settlement, clean):
    clean = finite(clean, 'Clean price per 100', .01, 1000)
    ai, _ = bond.cashflows(settlement)
    return bisect_root(lambda y: dirty_from_yield(bond, settlement, y) - clean-ai, -.50, 2.0)


def yield_risk(bond, settlement, y):
    p = dirty_from_yield(bond, settlement, y)
    bump = 0.00001  # 0.1 bp derivative step
    down = dirty_from_yield(bond, settlement, y-bump)
    up = dirty_from_yield(bond, settlement, y+bump)
    ai, cfs = bond.cashflows(settlement)
    f = bond.frequency
    if bond.convention == 'treasury' and len(cfs) == 1:
        macaulay = cfs[0]['periods']/f
    else:
        macaulay = sum(cf['periods']/f*cf['amount']/(1+y/f)**cf['periods'] for cf in cfs)/p
    return {'ytm_pct': y*100, 'clean': p-ai, 'dirty': p, 'accrued': ai,
            'modified_duration': (down-up)/(2*bump*p), 'macaulay_duration': macaulay,
            'yield_convexity': (down+up-2*p)/(p*bump*bump),
            'yield_dv01_per100': (down-up)/(2*bump)*.0001}
