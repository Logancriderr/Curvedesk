import math
import unittest
from datetime import date
from curvedesk.bonds import Bond,add_months,dirty_from_yield,yield_from_clean,yield_risk
from curvedesk.curves import bootstrap,REQUIRED,key_weights,price_flows
from curvedesk.analytics import analyze,portfolio,parallel_hedge,scenario

S=date(2026,1,15)
B=Bond('Test',date(2031,1,15),.04)
RATES={t:4 for t in REQUIRED}
ROW={'name':'Test','maturity':'2031-01-15','coupon_pct':4,'face':100000,'mode':'spread','value':0}

class BondTests(unittest.TestCase):
    def test_par_on_coupon_date(self):
        self.assertAlmostEqual(dirty_from_yield(B,S,.04),100,10)
    def test_independent_discounted_annuity(self):
        y=.055;v=1/(1+y/2)
        expected=2*(1-v**10)/(y/2)+100*v**10
        self.assertAlmostEqual(dirty_from_yield(B,S,y),expected,10)
    def test_roundtrip_between_coupons(self):
        s=date(2026,3,24);ai,_=B.cashflows(s)
        for y in [-.01,0,.042,.12]:
            p=dirty_from_yield(B,s,y)
            self.assertAlmostEqual(yield_from_clean(B,s,p-ai),y,9)
    def test_actual_actual_accrual(self):
        s=date(2026,4,15);ai,cfs=B.cashflows(s)
        self.assertAlmostEqual(ai,2*90/181)
        self.assertEqual(cfs[0]['date'],'2026-07-15')
    def test_coupon_date_accrual_zero(self):
        ai,cfs=B.cashflows(date(2026,7,15))
        self.assertEqual(ai,0);self.assertEqual(cfs[0]['date'],'2027-01-15')
    def test_final_coupon_simple_discount(self):
        b=Bond('Final',date(2026,7,15),.04);s=date(2026,4,15)
        self.assertAlmostEqual(dirty_from_yield(b,s,.05),102/(1+.05/2*91/181))
    def test_periodic_final_coupon(self):
        b=Bond('Final',date(2026,7,15),.04,2,'periodic');s=date(2026,4,15)
        self.assertAlmostEqual(dirty_from_yield(b,s,.05),102/(1+.05/2)**(91/181))
    def test_eom_leap_schedule(self):
        self.assertEqual(add_months(date(2028,8,31),-6),date(2028,2,29))
        self.assertEqual(add_months(date(2028,8,31),-12),date(2027,8,31))
    def test_non_eom_does_not_drift(self):
        self.assertEqual(add_months(date(2028,8,30),-12),date(2027,8,30))
    def test_zero_coupon(self):
        b=Bond('Zero',date(2031,1,15),0)
        self.assertAlmostEqual(dirty_from_yield(b,S,.04),100/1.02**10)
    def test_duration_against_analytic_derivative(self):
        risk=yield_risk(B,S,.04)
        weighted=sum((k/2)*(2+(100 if k==10 else 0))/1.02**k for k in range(1,11))/100
        self.assertAlmostEqual(risk['macaulay_duration'],weighted,9)
        self.assertAlmostEqual(risk['modified_duration'],weighted/1.02,6)
    def test_negative_yield(self):
        self.assertGreater(dirty_from_yield(B,S,-.01),100)
    def test_invalid_bond_dates(self):
        with self.assertRaises(ValueError):B.cashflows(date(2031,1,15))
    def test_invalid_frequency(self):
        with self.assertRaises(ValueError):Bond('Bad',date(2030,1,1),.04,4,'treasury')
    def test_nonfinite(self):
        with self.assertRaises(ValueError):Bond('Bad',date(2030,1,1),math.nan)

class CurveTests(unittest.TestCase):
    def test_flat_par_curve_discount_factors(self):
        c=bootstrap(RATES)
        for n in range(1,61):self.assertAlmostEqual(c.discounts[n],1.02**(-n),12)
    def test_all_synthetic_par_bonds_reprice(self):
        rates={t:3.5+t/30 for t in REQUIRED};c=bootstrap(rates)
        from curvedesk.mathutils import interp
        ts=sorted(rates)
        for n in range(1,61):
            coupon=interp(n/2,ts,[rates[t]/100 for t in ts])/2
            p=coupon*sum(c.discounts[1:n+1])+c.discounts[n]
            self.assertAlmostEqual(p,1,12)
    def test_short_end_log_interpolation(self):
        c=bootstrap(RATES);self.assertAlmostEqual(c.discount(.25)**2,c.discount(.5),12)
    def test_partition_of_unity(self):
        for t in [0,.1,.5,1,3,8,12,25,30.05]:self.assertAlmostEqual(sum(key_weights(t)),1)
    def test_par_not_directly_zero(self):
        rates={t:2+t/10 for t in REQUIRED};c=bootstrap(rates)
        self.assertGreater(abs(c.zero(30)-rates[30]/100),.001)
    def test_missing_required_tenor(self):
        rates=dict(RATES);del rates[10]
        with self.assertRaises(ValueError):bootstrap(rates)
    def test_no_long_extrapolation(self):
        with self.assertRaises(ValueError):bootstrap(RATES).discount(31)
    def test_negative_rates_allowed(self):
        self.assertGreater(bootstrap({t:-1 for t in REQUIRED}).discount(5),1)

class RiskTests(unittest.TestCase):
    def setUp(self):self.c=bootstrap(RATES)
    def test_clean_quote_reconciliation(self):
        r=analyze(dict(ROW,mode='clean',value=98.25),S,self.c)
        self.assertAlmostEqual(r['clean'],98.25,7)
    def test_yield_quote_reconciliation(self):
        r=analyze(dict(ROW,mode='yield',value=4.8),S,self.c)
        self.assertAlmostEqual(r['ytm_pct'],4.8,7)
    def test_short_has_opposite_dollar_risk(self):
        a=analyze(ROW,S,self.c);b=analyze(dict(ROW,face=-100000),S,self.c)
        self.assertAlmostEqual(a['curve_dv01'],-b['curve_dv01'])
        self.assertAlmostEqual(a['market_value'],-b['market_value'])
    def test_key_dv01_sum(self):
        r=analyze(ROW,S,self.c)
        self.assertAlmostEqual(sum(r['key_dv01']),r['curve_dv01'],4)
    def test_rising_rates_lose_money_long(self):
        self.assertLess(scenario(analyze(ROW,S,self.c),self.c,[100]*6),0)
    def test_zero_shock_no_pnl(self):
        self.assertAlmostEqual(scenario(analyze(ROW,S,self.c),self.c,[0]*6),0,6)
    def test_spread_and_parallel_equal_in_this_model(self):
        r=analyze(ROW,S,self.c)
        self.assertAlmostEqual(scenario(r,self.c,[50]*6),scenario(r,self.c,[0]*6,50),8)
    def test_equal_opposite_portfolio_cancels(self):
        p=portfolio([ROW,dict(ROW,face=-100000)],S,self.c)
        self.assertAlmostEqual(p['dv01'],0);self.assertAlmostEqual(p['net_market_value'],0)
        self.assertGreater(p['gross_market_value'],0)
        for s in p['scenarios']:self.assertAlmostEqual(s['pnl'],0)
    def test_same_bond_hedge_neutralizes_entire_curve(self):
        b=portfolio([ROW],S,self.c);h=parallel_hedge(b,analyze(ROW,S,self.c),self.c)
        self.assertAlmostEqual(h['signed_face'],-100000)
        for s in h['scenarios']:self.assertAlmostEqual(s['after'],0,7)
    def test_duration_convexity_approximates_small_shock(self):
        r=analyze(ROW,S,self.c);x=.001
        approx=r['market_value']*(-r['curve_duration']*x+.5*r['curve_convexity']*x*x)
        exact=scenario(r,self.c,[10]*6)
        self.assertLess(abs(approx-exact),.01)
    def test_dv01_matches_cashflow_time_weight(self):
        r=analyze(ROW,S,self.c)
        independent=sum(cf['years']*cf['pv_per100'] for cf in r['cashflows'])*.0001*1000
        self.assertAlmostEqual(independent,r['curve_dv01'],4)
    def test_invalid_position_error_identifies_row(self):
        with self.assertRaisesRegex(ValueError,'Position 2'):
            portfolio([ROW,dict(ROW,maturity='bad')],S,self.c)
