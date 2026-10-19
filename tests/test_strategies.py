import copy, datetime as dt, pathlib, sys, unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import strategies as s

def data(n=300):
    # Consecutive dates sufficient for algorithm fixtures, not a market calendar.
    return [dict(date=(dt.date(2024,1,1)+dt.timedelta(days=i)).isoformat(),open=100.,high=100.5,low=99.5,close=100.,volume=1000000,amount=100000000.) for i in range(n)]
def change(rows,i,**kw):rows[i].update(kw)
def ids(rows):return [x['strategy_id'] for x in s.detect_at(rows,len(rows)-1)]

class TestSignals(unittest.TestCase):
    def test_s1_pullback(self):
        r=data()
        for i in range(240,299):
            c=100+(i-240)*.15;change(r,i,open=c-.1,high=c+.5,low=c-.5,close=c)
        m=s.features(r)[-1]['ma'][20]
        change(r,299,open=m-.2,low=m+.1,high=110,close=109.5)
        self.assertIn('S1',ids(r))
        change(r,299,close=m-.1)
        self.assertNotIn('S1',ids(r))
    def test_s2_breakout(self):
        r=data();change(r,280,high=104);change(r,281,low=96)
        change(r,299,open=101,low=100,high=107,close=106,volume=2000000)
        self.assertIn('S2',ids(r))
        change(r,299,volume=1000000)
        self.assertNotIn('S2',ids(r))
    def test_s3_confirmed_w(self):
        r=data();change(r,249,close=115,high=116,low=99);change(r,270,low=85,close=86,open=87)
        change(r,277,high=100);change(r,290,low=86,close=87,open=88)
        change(r,299,open=100,low=99,high=102,close=101,volume=2000000)
        with patch.object(s,'pivots',return_value=[(270,'L'),(277,'H'),(290,'L')]):
            self.assertIn('S3',ids(r))
            change(r,299,close=99.5)
            self.assertNotIn('S3',ids(r))
    def test_s4_box_bounce(self):
        r=data()
        for i in (280,287):change(r,i,high=104)
        for i in (283,291):change(r,i,low=96)
        change(r,299,open=96.5,low=96,high=98,close=97)
        self.assertIn('S4',ids(r))
        change(r,299,close=96.2)
        self.assertNotIn('S4',ids(r))
    def test_s5_two_bar_confirmation(self):
        r=data()
        for x in r:x.update(open=110.,high=111.,low=109.,close=110.)
        change(r,295,low=100)
        change(r,298,open=100.5,high=102,low=99,close=101.5,volume=2000000)
        change(r,299,open=102,high=103,low=100,close=102.5)
        self.assertIn('S5',ids(r));self.assertNotIn('S5',ids(r[:-1]))
        change(r,299,low=98)
        self.assertNotIn('S5',ids(r))
    def test_s6_early_right_head(self):
        r=data();change(r,249,close=90,open=90,low=89,high=91)
        change(r,270,high=110,close=109,open=108,low=107)
        change(r,282,low=95,close=96,open=97)
        change(r,298,close=109,high=110,low=108,open=108)
        change(r,299,open=109,high=110,low=106,close=107)
        with patch.object(s,'pivots',return_value=[(270,'H'),(282,'L')]):
            self.assertIn('S6',ids(r))
            change(r,299,close=109.5)
            self.assertNotIn('S6',ids(r))
    def test_pivot_not_visible_before_confirmation(self):
        r=data(90);change(r,85,low=90)
        self.assertNotIn((85,'L'),s.pivots(r,87))
        self.assertIn((85,'L'),s.pivots(r,88))
    def test_future_does_not_repaint(self):
        r=data();change(r,280,high=104);change(r,281,low=96)
        change(r,299,open=101,low=100,high=107,close=106,volume=2000000)
        expected=s.detect_at(r,299)
        extra=copy.deepcopy(r[-1]);extra.update(date='2030-01-01',close=1,open=1,low=1,high=1000)
        self.assertEqual(expected,s.detect_at(r+[extra],299))
    def test_warmup_and_quality_gate(self):
        found,issues=s.scan(data(96),'TEST',{'min_average_amount':50000000},data(96)[-1]['date'])
        self.assertEqual(found,[]);self.assertTrue(any('暖機' in i for i in issues))
        r=data();change(r,280,high=104);change(r,281,low=96)
        change(r,299,open=101,low=100,high=107,close=106,volume=2000000)
        found,_=s.scan(r,'TEST',{'min_average_amount':50000000},r[-1]['date'])
        self.assertTrue(found);self.assertTrue(all(x['status']=='DATA_MISSING' and not x['execution_eligibility'] for x in found))
    def test_price_tick_boundaries(self):
        self.assertEqual(s.below(50),49.95);self.assertEqual(s.above(50),50.1)
        self.assertEqual(s.below(100),99.9);self.assertEqual(s.above(100),100.5)
    def test_bad_data(self):
        r=data();r[-1]['close']=float('nan');self.assertIsNotNone(s.validate_rows(r))
        r=data();r[-1]['date']=r[-2]['date'];self.assertIsNotNone(s.validate_rows(r))

if __name__=='__main__':unittest.main()
