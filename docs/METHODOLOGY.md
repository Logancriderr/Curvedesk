# Pricing and risk methodology

## Instruments and settlement

The engine supports USD fixed-rate, regular-coupon bullet cash flows. Frequency can be annual, semiannual or quarterly; Treasury yield convention requires semiannual payments. Coupon accrual uses Actual/Actual for a regular coupon period. Do not use it for securities requiring 30/360 or odd/stub coupons.

Dates are generated backward from maturity using the original maturity anchor. End-of-month maturity preserves end of month; other maturities preserve day of month where possible. Payments on the settlement date are excluded, and accrued interest resets to zero on a coupon date. Payment dates are not holiday-adjusted. Verify the inferred schedule and settlement date against the actual security before using the result. No issue date, first coupon or ex-coupon rule is modeled.

For annual coupon decimal `c`, frequency `f`, last coupon date `L`, next coupon `N`, and settlement `S`:

- Coupon per $100: `C = 100 c / f`.
- Elapsed fraction: `a = days(L,S) / days(L,N)`.
- Accrued interest: `AI = C a`.
- Remaining first-period fraction: `w = 1 − a`.
- Dirty price = clean price + accrued interest.

A quoted clean price of 98.25 means $98.25 per $100 face. Convert 32nds before entry: 99-16 is 99.50. Face is dollars of principal, not a number of bonds or futures contracts.

## Yield pricing

For multiple remaining payments, dirty price is the sum of `CF_k / (1+y/f)^(w+k)` for `k=0,...,n−1`. `y` is nominal annual yield with compounding frequency `f`.

Treasury mode uses simple discounting when exactly one payment remains: `CF / (1+y/f × w)`. Periodic mode retains fractional-period compounding. This last-period difference matters close to maturity. Treasury bill bank-discount yields are not supported. Zero-coupon cash flows can be represented with coupon 0, but the chosen yield convention still applies; this is not a universal bill or STRIPS convention engine.

YTM is solved by bracketed bisection. The supported yield range is −50% to +200%; unrealistic or unbracketed inputs fail visibly. Derivatives use a 0.1 bp central yield bump. Modified duration is `−(dP/dy)/P`; yield convexity is `(d²P/dy²)/P`. Macaulay duration is the present-value-weighted coupon-period time. The usual modified/Macaulay relation does not apply unchanged to the final simple-discount period.

## Treasury par curve to discount factors

The official input is a **par yield curve**, not zero rates. Treasury publishes daily indicative rates and documents its own monotone-convex construction. CurveDesk builds a separate, simplified discount model from the published rates.

1. Require nonmissing 6M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y, 20Y and 30Y rates. Other available short tenors appear in the monitor, but do not drive the discount bootstrap.
2. Linearly interpolate annual par rates onto maturities `0.5, 1.0, ..., 30.0` years.
3. Assume synthetic semiannual par bonds and recursively solve:
   `D_n = [1 − (p_n/2) Σ_(i=1 to n−1) D_i] / (1+p_n/2)`.
4. Reject nonpositive discount factors. Interpolate log discount factors between nodes, including `D(0)=1`. Below six months this implies the same continuous zero rate as the 6M point.
5. Convert to continuous zero rates with `z(t)=−ln(D(t))/t` and six-month forwards with `−ln(D_i/D_(i−1))/Δt`.

A small flat-forward extension from 30.0 to 30.1 years accommodates calendar-day overhang. Longer cash flows are rejected. Negative rates are allowed; negative derived forwards trigger a visible review warning. Positive discount factors alone do not validate every economic assumption of a curve.

Bond curve discount times use actual days from settlement divided by 365. The synthetic bootstrap grid uses exact half-years. These are intentional model conventions; exact coupon-grid par repricing tests do not imply an off-grid calendar bond must price exactly at par.

Rates are applied as a function of remaining maturity **at the chosen settlement date**. The model neither predicts changes between the observation and settlement dates nor rolls an observation-date discount curve forward. Selecting old data creates a dated-curve scenario at the chosen settlement. It is not a historical backtest.

## Quote reconciliation and spreads

There are three valuation modes:

| Mode | Input | Valuation |
|---|---|---|
| Spread | Continuous z-spread in bp | Discount contractual cash flows using curve and entered spread |
| Clean | Broker clean price per $100 | Add accrued interest, then solve a constant z-spread to match dirty price |
| Yield | Annual nominal yield in percent | Compute dirty price under the bond yield convention, then solve the z-spread |

Curve dirty price is `Σ CF_i D(t_i) exp(−s t_i)`. The z-spread is constant across cash flows and is a residual to this model. It is not a pure measure of default risk, an option-adjusted spread, or proof of cheapness. Quote timestamps are optional timezone-aware ISO 8601 strings; missing timestamps on quoted positions produce a warning. The application does not independently verify broker quotes.

Rate scenarios retain the fitted spread. A spread scenario changes it explicitly. The displayed curve-only clean value helps you see the difference between the zero-spread benchmark and the entered quote.

## Curve DV01 and key-rate risk

A 1 bp parallel shock adds `0.0001` to continuous zero rates. Curve DV01 per $100 is `[P(−1bp) − P(+1bp)]/2`. Multiply by signed face / 100 for dollar position DV01. A positive DV01 corresponds to an approximate loss on a +1 bp move. It differs from the derivative with respect to one bond’s nominal YTM.

Key tenors are 0.5, 2, 5, 10, 20 and 30 years. Piecewise linear hat weights equal one at a key point and zero at neighboring points, with flat outer endpoints. Weights sum to one at every supported cash-flow time. Apply `D'(t)=D(t) exp[−t Σ weight_j(t) shock_j/10000]` and revalue. Key DV01s approximately sum to parallel DV01; finite-bump higher-order terms prevent requiring exact equality.

Curve duration and convexity use the parallel continuous-zero shock and dirty price. Key rates are sensitivities to the **derived zero curve**, not to independently bumping the original par quotes and rebuilding the curve.

## Portfolio and hedge

All dollar values and risks retain the sign of face value. Net market value sums signed dirty values; gross value sums absolute values. Dollar DV01 is emphasized because a value-weighted duration can be unstable for a nearly market-neutral book.

The hedge calculator sizes a cash bond by `hedge face = −portfolio DV01 / hedge DV01 per dollar face`. It displays residual key-rate risk and fully repriced scenarios. Equal total DV01 does not neutralize twists, convexity or spread risk. The result is fractional theoretical face before round lots, short availability, repo funding, bid/ask, fees or liquidity. Futures would require a separate contract/CTD/conversion-factor model.

## Scenarios and approximations

Standard stresses include ±100 bp parallel shocks, a defined bear steepener, bull flattener, belly shock and +50 bp across all position spreads. The exact key-tenor shock arrays are returned in the JSON report. Custom shocks range from −1000 to +1000 bp. Large shocks are sensitivity exercises, not probability estimates.

P&L is the difference in dirty market value at unchanged settlement with fixed cash flows. No carry, coupon receipt, rolldown, default, recovery or passage of time is simulated. The duration-convexity check uses `ΔV ≈ V(−D Δz + 0.5 C Δz²)` for the same parallel-zero convention.

## Primary references

- [Treasury yield curve methodology](https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics/treasury-yield-curve-methodology)
- [Treasury daily XML feed specification](https://home.treasury.gov/treasury-daily-interest-rate-xml-feed)
- [Treasury notes and semiannual payments](https://treasurydirect.gov/marketable-securities/treasury-notes/)