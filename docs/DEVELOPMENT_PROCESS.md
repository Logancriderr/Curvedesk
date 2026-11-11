# How CurveDesk was built

## Start with the decision

The practical question was: “Given my bond holdings or a current quote, what do I own in dollar rate risk, and how would the value change under another curve?” The scope centers on conventional fixed-rate cash flows and transparent sensitivity calculations.

The interface separates curve monitoring, single-position inspection, portfolio aggregation, scenarios and data provenance. The same Python service serves browser calculations and reproducible command-line reports.

## Define conventions before formulas

The engine explicitly states price units, coupon frequency, Actual/Actual accrual, settlement treatment and the final Treasury coupon convention. That prevents apparently precise outputs from concealing incompatible assumptions. Unsupported structures fail or are excluded by the stated instrument scope.

## Separate quotes from the discount model

The public Treasury feed supplies par yields. The curve module converts those rates into a simplified discount curve through a semiannual par bootstrap. Bond prices entered by the user are then reconciled by fitting a constant continuous spread. Rate risk is measured from the reconciled starting value.

This distinction is central to the project: a par rate is not a zero rate, a quoted yield is not a coupon, and a Treasury curve value is not automatically the market quote of an individual bond.

## Build and test the numerical layer

Cash-flow scheduling, yield pricing, accrual and numerical solving were implemented independently of the interface. Tests compared results with an annuity formula and analytic time-weighted sensitivities, rather than only duplicating code paths. Later checks addressed coupon-date boundaries, leap years, quote calibration and long/short portfolio identities.

A test caught a small zero-shock P&L caused by using a yield-reconstructed price instead of the exact calibrated curve value as the base. The base dirty price was changed to the actual curve valuation. Zero shocks now preserve value directly.

## Add durable data ingestion

The connector follows Treasury’s documented XML contract. It validates observations before publishing a complete snapshot. Atomic replacement prevents a failed refresh from publishing only part of a dataset. A synthetic mode and a CSV route allow offline exploration and networks that cannot reach Treasury. Sources are explicitly labeled.


#