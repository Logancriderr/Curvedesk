# CurveDesk

**A local Python yield-curve and cash-bond risk workbench.** Track published Treasury rates, reconcile a bond quote, inspect cash flows, aggregate portfolio DV01, and evaluate curve shocks and a cash-bond hedge.

Python 3.11+ · standard-library runtime · no API key · offline demo · browser dashboard

![CurveDesk yield curve dashboard](docs/screenshots/curve-monitor.png)

*CurveDesk's curve monitor, showing yield comparisons and interest-rate analytics. 

## What you can do

| Workspace | Practical use |
|---|---|
| Curve monitor | Compare dated Treasury par curves, 2s10s and 5s30s slopes, derived zeros and forward rates |
| Bond lab | Enter a clean price, yield or spread; calculate accrued interest, dirty price, YTM, duration, convexity and DV01 |
| Portfolio and hedge | Import signed holdings; aggregate risk; size a theoretical cash-bond hedge and inspect residual risk |
| Scenario studio | Reprice parallel shifts, steepeners, flatteners, a belly shock and spread widening |
| Data and methods | Inspect dates, source, discount factors and conventions; import a custom par-curve CSV |

### What “real time” means here

Risk recalculates when you commit an input change in the browser. The market-data connector fetches **daily published US Treasury par rates**, not an intraday bond-price stream. A refresh button and optional 15-minute checks look for a new publication. Observation and retrieval timestamps are visible.

For intraday use, enter a current broker **clean price or yield** and optional quote timestamp. The engine calibrates a constant spread so its starting value matches that input, then calculates rate and spread sensitivity. A broker connection, CUSIP security master, streaming quote entitlement and trade execution are not included.

This is a practical research tool for supported regular fixed-rate bonds. Reconcile the security’s terms and price conventions with your broker before relying on a calculation. It is not a universal pricing system for every product called a bond.

## Start in VS Code

1. Extract the archive and open the **`curvedesk` folder** in VS Code. The integrated terminal should show this folder; it contains this README and the `curvedesk/` Python package.
2. Install Python 3.11 or later and VS Code’s Python extension if needed. No runtime packages need to be downloaded.
3. Optionally create an isolated environment, then start the app.

**Windows PowerShell**

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m curvedesk
```

Open **http://127.0.0.1:8765**. Start with the clearly labeled synthetic demo. Stop with Ctrl+C.

If you already have a suitable Python interpreter, the only required command is:

```bash
python -m curvedesk
```

## First useful analysis

1. Click **Fetch latest Treasury data**. On success the source switches to Treasury and the newest complete curve is selected. Confirm the observation date. Historical dates remain available for comparison.
2. Set the **actual settlement date**. There is no automatic holiday calendar. The curve observation cannot be later than settlement.
3. Open **Bond lab** and replace an example with a real regular-coupon bond’s name, maturity, annual coupon and face value. Review the generated cash-flow dates against the security’s terms.
4. Select **Quoted clean price / 100** or **Quoted annual yield %**. Enter your current quote. Use decimal price, e.g. 99.50, not a 32nds string such as 99-16. For yield, enter `4.25` for 4.25%.
5. Optionally enter a quote timestamp such as `2026-09-16T14:30:00Z`; replace it with the quote’s actual time. It must include a timezone and cannot be in the future. The app does not independently verify the quote.
6. Check dirty price, accrued interest, yield duration and position curve DV01. The curve-only price is a benchmark; the fitted z-spread reconciles the entered quote to the discount curve.
7. Use **Scenario studio → Parallel +100 bp**, then try a steepener. Compare full revaluation with the duration-convexity approximation.
8. In **Portfolio & hedge**, specify a hedge bond and inspect its signed theoretical face amount. Check the remaining key-rate exposure and stressed P&L; matching total DV01 does not remove all risk.
9. Export the analysis JSON, positions CSV and cash-flow CSV before closing. Positions are held in the browser session, not automatically saved to disk.

**Input units:** coupon and yield in annual percent; spread and shocks in basis points; prices per $100 face; face in dollars of principal. Positive face is long and negative face is short. One basis point is 0.01 percentage point.

### Bond valuation example

Inspect an example bond's price, yield, duration, and dollar sensitivity to interest-rate changes.

![CurveDesk Bond lab showing valuation and risk calculations](docs/screenshots/bond-lab.png)

*The key-rate DV01 chart shows which parts of the yield curve contribute to the position's rate sensitivity.*

### Supported bond conventions

Regular fixed-rate bullet cash flows, Actual/Actual coupon accrual, and roughly 30 years or less remaining maturity. Treasury mode is semiannual and includes simple discounting for its final coupon period. Generic periodic mode supports annual, semiannual or quarterly compounding under the same accrual convention.

Odd first/last coupons, 30/360 securities, callable/putable bonds, amortization, TIPS, floaters, ex-coupon periods and Treasury bill discount-yield quotations need different models. Coupon dates are inferred backward from maturity and are unadjusted. See [the full methodology](docs/METHODOLOGY.md).

## Use real curve data

The public [Treasury XML feed](https://home.treasury.gov/treasury-daily-interest-rate-xml-feed) needs no API key. The connector requests the current and previous calendar years. It validates data and saves a normalized snapshot at `data/treasury.json`; a failed update retains the last good snapshot. Demo data are never substituted for a failed live request.

You can update from the terminal too:

```bash
python -m curvedesk sync
```

Then select **US Treasury daily** in the dashboard. The source dropdown reads a saved snapshot; **Fetch latest Treasury data** requests a fresh one. Optional polling operates while the page is visible and Treasury is selected, and switches to the newest available curve. A five-calendar-day age warning is a basic freshness check, not a market-calendar guarantee.

### CSV fallback or custom curve

If Treasury is blocked by your network, open **Data & methods** and import a CSV with these exact headers:

```csv
date,6M,1Y,2Y,3Y,5Y,7Y,10Y,20Y,30Y
2026-01-15,4.15,4.00,3.85,3.90,4.05,4.20,4.35,4.65,4.70
```

**Those values are synthetic formatting examples.** Replace them with dated, sourced rates from the [official Treasury data table](https://home.treasury.gov/resource-center-data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve) or an authorized provider. Rates are percent, not decimals. One or more rows are allowed; dates must be unique and no later than today. Every row must have all required tenors. Download a template from the dashboard or use `examples/synthetic_curve.csv`.

Imported curves remain labeled as user-supplied and unverified. The app does not discover the source of a CSV. Do not label an imported synthetic template as real market data.

## Import your portfolio

Start with `examples/positions.csv` or export the displayed holdings. Required columns:

| Column | Meaning |
|---|---|
| `name` | Your label; no automatic CUSIP lookup |
| `maturity` | YYYY-MM-DD |
| `coupon_pct` | Annual coupon percent, e.g. 4.25 |
| `face` | Signed face dollars, e.g. 100000 or -50000 |
| `frequency` | 1, 2 or 4 |
| `convention` | `treasury` or `periodic` |
| `mode` | `clean`, `yield` or `spread` |
| `value` | Clean price per 100, yield percent, or spread bp, according to mode |
| `quote_asof` | Optional timezone-aware ISO timestamp for a manual quote |

Keep 1–100 positions. Any invalid position prevents publication of a new portfolio calculation; the server never silently skips a holding. The source curve and settlement date apply to the entire book. You can also edit the CSV text in the Holdings panel.

Do not commit personal holdings or private broker data to a public repository. The default ignore file excludes data snapshots and an `exports/` directory; export private files there or elsewhere outside the repository.

### Portfolio risk and hedge example

Combine position-level exposures and examine a theoretical cash-bond hedge.

![CurveDesk portfolio exposures and cash-bond hedge](docs/screenshots/portfolio-risk.png)

*Matching total DV01 can leave exposure to changes in the shape of the yield curve. The chart compares key-rate risk before and after the hedge.*

## Transparent model choices

- Par rates are interpolated on a semiannual grid and bootstrapped into discount factors. The app does **not** treat par rates as zero rates or claim to reproduce Treasury’s official fit.
- Cash-flow discounting uses actual days / 365 from settlement; interpolation is linear in log discount factors.
- Quote-based positions are matched with a continuous z-spread. Rate stresses hold it fixed unless an explicit spread shock is applied.
- Dollar curve DV01 is the central difference for ±1 bp of continuous zero rates. Key risks use six local rate bumps.
- Portfolio values and risks preserve long/short signs. The cash-bond hedge neutralizes parallel DV01 before rounding and costs.
- Scenarios are instantaneous revaluations, not probabilistic forecasts or realized trading returns.

Read [METHODOLOGY.md](docs/METHODOLOGY.md) for formulas, boundary cases and limitations.

## Scenario analysis example

Apply parallel rate changes, curve-shape changes, and spread shocks to the example portfolio.

![CurveDesk scenario analysis with a parallel 100 basis point increase](docs/screenshots/scenario-studio.png)

*The selected scenario raises continuous zero rates by 100 basis points. P&L comes from repricing the remaining cash flows; it is an instantaneous stress result, not a forecast of investment returns.*