"""Synthetic semiannual par bootstrap and continuous-zero-rate risk shocks."""
from dataclasses import dataclass
import math
from .mathutils import finite, interp

KEYS = (.5, 2., 5., 10., 20., 30.)
REQUIRED = (.5, 1., 2., 3., 5., 7., 10., 20., 30.)


@dataclass(frozen=True)
class Curve:
    times: tuple
    discounts: tuple

    def __post_init__(self):
        if len(self.times) != len(self.discounts) or len(self.times) < 2:
            raise ValueError('Invalid discount curve')
        if self.times[0] != 0 or self.discounts[0] != 1:
            raise ValueError('Curve must begin with D(0)=1')
        if any(b <= a for a, b in zip(self.times, self.times[1:])):
            raise ValueError('Curve tenors must increase strictly')
        for d in self.discounts:
            finite(d, 'Discount factor', 1e-12, 100)

    def discount(self, t):
        t = finite(t, 'Cash-flow horizon', 0, 30.1)
        logs = [math.log(x) for x in self.discounts]
        if t > self.times[-1]:
            # Only the calendar overhang of a 30-year bond is supported.
            slope = (logs[-1]-logs[-2])/(self.times[-1]-self.times[-2])
            return math.exp(logs[-1]+slope*(t-self.times[-1]))
        return math.exp(interp(t, self.times, logs))

    def zero(self, t):
        return -math.log(self.discount(t))/t if t else self.zero(.0001)


def bootstrap(rates):
    """rates: {tenor_years: annual par yield in PERCENT}. Require complete core tenors."""
    clean = {float(k): finite(v, 'Par rate percent', -5, 30) for k,v in rates.items() if v is not None}
    if any(t not in clean for t in REQUIRED):
        raise ValueError('Curve requires nonmissing 6M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y, 20Y and 30Y rates')
    xs = sorted(t for t in clean if .5 <= t <= 30)
    ys = [clean[t]/100 for t in xs]
    dfs = [1.0]
    times = [0.0]
    for n in range(1,61):
        t = n/2
        c = interp(t, xs, ys)/2
        d = (1-c*sum(dfs[1:]))/(1+c)
        if not math.isfinite(d) or d <= 0:
            raise ValueError('Par inputs imply a nonpositive discount factor; check curve shape')
        times.append(t); dfs.append(d)
    return Curve(tuple(times), tuple(dfs))


def key_weights(t):
    """Triangular continuous-zero bumps, flat at the outer endpoints; sum to 1."""
    return [interp(t, KEYS, [float(i == j) for i in range(len(KEYS))]) for j in range(len(KEYS))]


def price_flows(flows, curve, spread_bps=0, shocks=None):
    spread = finite(spread_bps, 'Spread bps', -5000, 10000)/10000
    shocks = [0.0]*len(KEYS) if shocks is None else list(shocks)
    if len(shocks) != len(KEYS):
        raise ValueError('Six key-rate shocks are required')
    for x in shocks:
        finite(x, 'Shock bps', -1000, 1000)
    pv = 0.0
    for cf in flows:
        t = cf['years']
        shift = sum(a*b for a,b in zip(shocks, key_weights(t)))/10000
        pv += cf['amount']*curve.discount(t)*math.exp(-(spread+shift)*t)
    return pv


def diagnostics(curve):
    return [{'tenor_years':t, 'discount_factor':d, 'zero_cc_pct':curve.zero(t)*100,
             'forward_cc_pct':-math.log(d/curve.discounts[i-1])/(t-curve.times[i-1])*100}
            for i,(t,d) in enumerate(zip(curve.times, curve.discounts)) if i]
