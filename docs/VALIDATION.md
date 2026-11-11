# Validation record and local acceptance

## Verified during packaging

- Python 3.12: 62 unit/integration tests passed.
- Independent annuity pricing and time-weighted derivative checks.
- Coupon-date, off-coupon, leap-year and final-period cases.
- Synthetic par bonds reprice at every bootstrap node.
- Clean-price and yield inputs reconcile through the spread solver.
- Long/short cancellation, key-rate decomposition and hedge identities.
- Corrupt/missing data, bad dates, nonfinite values and failed updates.
- Local HTTP calculation, session token, host validation and static routes.
- JavaScript syntax checked with Node.


## Local acceptance steps

1. Run `python -m unittest discover -s tests -v`.
2. Start `python -m curvedesk`, open the local address, and confirm the source reads SYNTHETIC DEMO.
3. Verify the five navigation views, chart labels and the cash-flow table on desktop and your normal display size.
4. In Bond lab, select clean-price mode and enter 98.25. Confirm clean price reconciles to 98.2500; check the accrued/dirty relationship.
5. In Scenario studio, apply +100 bp and confirm a long-only example book loses value.
6. Export holdings, reimport the exported file, and confirm the same values. Check a short face position gives the opposite sign of dollar risk.
7. Fetch Treasury data. Confirm the source changes only on success, dates are plausible and all required tenors exist. Compare several rates directly with the official table for the exact observation date.
8. If network access is blocked, import a sourced dated curve CSV. An imported CSV remains labeled as user-supplied.
9. Compare one real supported bond against a trusted broker valuation using identical settlement, coupon schedule, quote and conventions. Investigate differences rather than assuming the broker or model must be wrong.
10. For a failed calculation, confirm the error banner appears and analysis export becomes unavailable; older results are dimmed.

```bash
npm install
npx playwright install chromium
npm run test:browser
```

The test starts its own Python server on port 8876, exercises the demo, quote editing, shocks, exports, portfolio import, curve import and an intentionally failed refresh, then saves desktop/mobile images in `test-results/`. Set `CURVEDESK_PYTHON` to your environment’s Python executable if `python` is not the appropriate command. Browser automation requires a machine allowed to install Chromium.

