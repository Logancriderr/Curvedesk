import json
import tempfile
import unittest
from pathlib import Path
from datetime import date
from unittest.mock import patch
from curvedesk.data import parse_xml, demo_snapshot, save_snapshot, load_snapshot, import_curve_csv, fetch_treasury
from curvedesk.service import calculation

ROOT=Path(__file__).resolve().parent.parent

def xml(rows):
    content=''.join('<entry><content><m:properties><d:NEW_DATE>'+d+'</d:NEW_DATE>'+''.join(f'<d:{k}>{v}</d:{k}>' for k,v in vals.items())+'</m:properties></content></entry>' for d,vals in rows)
    return ('<feed xmlns="http://www.w3.org/2005/Atom" xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata" xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices">'+content+'</feed>').encode()

class DataTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.folder=self.tmp.name
    def tearDown(self):self.tmp.cleanup()
    def test_xml_namespace_and_percent(self):
        r=parse_xml(xml([('2026-01-15T00:00:00',{'BC_10YEAR':'4.25'})]),2026,date(2026,2,1))
        self.assertEqual(r[0]['rates']['10.0'],4.25)
    def test_xml_missing_stays_missing(self):
        r=parse_xml(xml([('2026-01-15',{'BC_10YEAR':'4.25'})]),2026)
        self.assertIsNone(r[0]['rates']['5.0'])
    def test_xml_duplicate_rejected(self):
        with self.assertRaises(ValueError):parse_xml(xml([('2026-01-15',{}),('2026-01-15',{})]),2026)
    def test_xml_future_rejected(self):
        with self.assertRaises(ValueError):parse_xml(xml([('2026-02-15',{})]),2026,date(2026,1,1))
    def test_xml_wrong_year_rejected(self):
        with self.assertRaises(ValueError):parse_xml(xml([('2025-01-15',{})]),2026)
    def test_xml_bad_number_rejected(self):
        with self.assertRaises(ValueError):parse_xml(xml([('2026-01-15',{'BC_10YEAR':'nan'})]),2026)
    def test_html_not_feed(self):
        with self.assertRaises(ValueError):parse_xml(b'<html>blocked</html>',2026)
    def test_entities_rejected(self):
        with self.assertRaises(ValueError):parse_xml(b'<!DOCTYPE foo><feed/>',2026)
    def test_demo_explicit(self):
        snap=demo_snapshot();self.assertEqual(snap['source'],'demo');self.assertIsNone(snap['retrieved_at'])
    def test_import_template(self):
        snap=import_curve_csv((ROOT/'examples/synthetic_curve.csv').read_text(),self.folder)
        self.assertEqual(snap['source'],'custom');self.assertTrue(snap['records'][0]['usable'])
    def test_duplicate_csv_date(self):
        text=(ROOT/'examples/synthetic_curve.csv').read_text()
        with self.assertRaises(ValueError):import_curve_csv(text+text.splitlines()[1]+'\n',self.folder)
    def test_bad_import_preserves_previous_snapshot(self):
        text=(ROOT/'examples/synthetic_curve.csv').read_text();import_curve_csv(text,self.folder)
        before=(Path(self.folder)/'custom.json').read_bytes()
        with self.assertRaises(ValueError):import_curve_csv(text.replace('4.15','nan'),self.folder)
        self.assertEqual(before,(Path(self.folder)/'custom.json').read_bytes())
    def test_no_silent_demo_fallback(self):
        with self.assertRaises(ValueError):load_snapshot('treasury',self.folder)
    def test_download_failure_keeps_last_good(self):
        snap=demo_snapshot();snap['source']='treasury';save_snapshot(snap,self.folder)
        before=(Path(self.folder)/'treasury.json').read_bytes()
        def fail(*a,**kw):raise OSError('offline')
        with self.assertRaises(ValueError):fetch_treasury(self.folder,opener=fail)
        self.assertEqual(before,(Path(self.folder)/'treasury.json').read_bytes())
    def test_atomic_replace_failure_keeps_last_good(self):
        s=demo_snapshot();s['source']='custom';save_snapshot(s,self.folder)
        before=(Path(self.folder)/'custom.json').read_bytes()
        with patch('curvedesk.data.os.replace',side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):save_snapshot(s,self.folder)
        self.assertEqual(before,(Path(self.folder)/'custom.json').read_bytes())
        self.assertEqual(len(list(Path(self.folder).iterdir())),1)

class ServiceTests(unittest.TestCase):
    def setUp(self):self.p=json.loads((ROOT/'examples/request.json').read_text())
    def test_end_to_end_report(self):
        r=calculation(self.p,'unused');self.assertEqual(len(r['portfolio']['positions']),3)
        self.assertLess(r['portfolio']['scenarios'][0]['pnl'],0)
        self.assertLess(abs(r['hedge']['residual_dv01']),1e-7)
        json.dumps(r,allow_nan=False)
    def test_future_curve_not_allowed_at_settlement(self):
        self.p['settlement']='2025-12-01'
        with self.assertRaises(ValueError):calculation(self.p,'unused')
    def test_unavailable_date_not_silently_substituted(self):
        self.p['curve_date']='2001-01-01'
        with self.assertRaises(ValueError):calculation(self.p,'unused')
    def test_untimestamped_quote_warning(self):
        self.p['positions'][0].update(mode='clean',value=99)
        r=calculation(self.p,'unused')
        self.assertTrue(any('no timestamp' in w for w in r['warnings']))
    def test_quote_timestamp_requires_timezone(self):
        self.p['positions'][0].update(mode='clean',value=99,quote_asof='2026-01-15T12:00:00')
        with self.assertRaises(ValueError):calculation(self.p,'unused')
    def test_quote_timestamp_preserved(self):
        self.p['positions'][0].update(mode='clean',value=99,quote_asof='2026-01-15T12:00:00Z')
        r=calculation(self.p,'unused')
        self.assertEqual(r['portfolio']['positions'][0]['quote_asof'],'2026-01-15T12:00:00Z')
    def test_bad_shock(self):
        self.p['shocks']=[float('nan')]*6
        with self.assertRaises(ValueError):calculation(self.p,'unused')
