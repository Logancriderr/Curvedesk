"""Small, independently testable numerical primitives."""
import math
from bisect import bisect_right


def finite(value, name, low=-math.inf, high=math.inf):
    if isinstance(value, bool):
        raise ValueError(f'{name} must be numeric, not a boolean')
    x = float(value)
    if not math.isfinite(x) or not low <= x <= high:
        raise ValueError(f'{name} must be finite and between {low} and {high}')
    return x


def interp(x, xs, ys):
    """Piecewise linear; constant endpoints. Caller validates knot order."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    k = bisect_right(xs, x)
    w = (x - xs[k-1]) / (xs[k] - xs[k-1])
    return ys[k-1] * (1-w) + ys[k] * w


def bisect_root(func, low, high, tol=1e-11):
    fl, fh = func(low), func(high)
    if fl == 0:
        return low
    if fh == 0:
        return high
    if fl * fh > 0:
        raise ValueError('No solution in the supported range; check price, yield or spread')
    for _ in range(160):
        mid = (low + high) / 2
        fm = func(mid)
        if abs(fm) < tol or high-low < tol:
            return mid
        if fm * fl > 0:
            low, fl = mid, fm
        else:
            high = mid
    raise ValueError('Solver did not converge')
