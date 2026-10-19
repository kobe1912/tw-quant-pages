import datetime as dt,os,pathlib,sys,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from sinopac_data import aggregate,windows,SinopacReader,ProviderError
from update import update_history,sector_summary

def ns(date,time):return int((dt.datetime.fromisoformat(date+'T'+time)-dt.datetime(1970,1,1)).total_seconds()*1e9)
def payload(scale=1000):
 return dict(ts=[ns('2026-10-19',t) for t in ['09:00:00','09:01:00','14:30:00']],
  Open=[100,101,200],High=[102,103,201],Low=[99,100,199],Close=[101,102,200],Volume=[2,3,10],Amount=[201000/1000*scale,304500/1000*scale,2000000/1000*scale])
class Reader:
 def __init__(self,fail=False):self.calls=[];self.fail=fail
 def fetch(self,symbol,market,start,end):
  self.calls.append((symbol,market,start,end))
  if self.fail:raise ProviderError('QUERY_FAILED: test')
  return [dict(date=end.isoformat(),open=100,high=101,low=99,close=100,volume=10000,amount=1000000)]
class TestSino(unittest.TestCase):
 def test_window_limit(self):
  seq=list(windows(dt.date(2025,1,1),dt.date(2026,1,1)))
  self.assertTrue(all((b-a).days<=29 for a,b in seq))
  self.assertTrue(all(seq[i][1]+dt.timedelta(days=1)==seq[i+1][0] for i in range(len(seq)-1)))
 def test_aggregate_lots_and_session(self):
  r=aggregate(payload(),dt.date(2026,10,19),dt.date(2026,10,19))[0]
  self.assertEqual((r['open'],r['close'],r['high'],r['low']),(100,102,103,99))
  self.assertEqual(r['volume'],5000);self.assertEqual(r['amount'],505500)
 def test_aggregate_shares(self):
  r=aggregate(payload(1),dt.date(2026,10,19),dt.date(2026,10,19))[0]
  self.assertEqual(r['volume'],5);self.assertEqual(r['volume_scale'],1)
 def test_ambiguous_volume_fails(self):
  p=payload();p['Amount'][0]=20
  with self.assertRaises(ValueError):aggregate(p,dt.date(2026,10,19),dt.date(2026,10,19))
 def test_duplicate_minute_fails(self):
  p=payload();p['ts'][1]=p['ts'][0]
  with self.assertRaises(ValueError):aggregate(p,dt.date(2026,10,19),dt.date(2026,10,19))
 def test_missing_secret(self):
  with patch.dict(os.environ,{},clear=True):
   with self.assertRaisesRegex(ProviderError,'MISSING_SECRETS'):
    with SinopacReader():pass
 def test_budget_and_resume(self):
  state={};h={};cfg={'max_requests_per_run':1,'bootstrap_calendar_days':90};r=Reader();w=[dict(symbol='2330',market='TWSE')];end=dt.date(2026,10,19)
  used,errors=update_history(w,h,state,cfg,r,end);self.assertEqual(used,1);self.assertFalse(errors)
  cursor=state['2330']['cursor'];update_history(w,h,state,cfg,r,end)
  self.assertEqual(r.calls[1][2],dt.date.fromisoformat(cursor)+dt.timedelta(days=1))
 def test_failure_preserves_cursor(self):
  state={'2330':{'origin':'2026-09-01','cursor':'2026-09-30'}};h={'2330':[{'date':'2026-09-30'}]};old=list(h['2330']);cfg={'max_requests_per_run':1,'bootstrap_calendar_days':90}
  _,err=update_history([dict(symbol='2330',market='TWSE')],h,state,cfg,Reader(True),dt.date(2026,10,19))
  self.assertTrue(err);self.assertEqual(state['2330']['cursor'],'2026-09-30');self.assertEqual(h['2330'],old)
 def test_sector_partial_not_ranked(self):
  s=[dict(symbol='2330',sample_days=250,date='2026-10-19',daily_return_pct=2,price=100,ma20=90,signals=[]),dict(symbol='2317',sample_days=0,date=None,daily_return_pct=None,price=None,ma20=None,signals=[])]
  out=sector_summary(s,{'groups':[dict(name='test',symbols=['2330','2317'])]},'2026-10-19')[0]
  self.assertFalse(out['complete']);self.assertIsNone(out['average_return_pct']);self.assertEqual(out['coverage_pct'],50)
 def test_no_order_methods(self):
  import ast
  code=(pathlib.Path(__file__).resolve().parents[1]/'scripts'/'sinopac_data.py').read_text();forbidden={'place_order','update_order','cancel_order','activate_ca','list_positions','account_balance'}
  calls={n.func.attr for n in ast.walk(ast.parse(code)) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
  self.assertFalse(calls&forbidden)
if __name__=='__main__':unittest.main()
