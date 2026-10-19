"""Build six-strategy EOD research JSON; python scripts/update.py --offline for QA.
TWSE raw STOCK_DAY does not supply verified corporate-action/eligibility data.
No brokerage execution; legacy simulations are archived, not relabelled as v2.
"""
import argparse, datetime as dt, json, pathlib, time
from strategies import CATALOG, VERSION, features, scan
from legacy_v33 import get, n, calc
ROOT=pathlib.Path(__file__).resolve().parents[1]; DATA=ROOT/'docs'/'data'
TZ=dt.timezone(dt.timedelta(hours=8))

def load(path,default):
    if not path.exists():return default
    return json.loads(path.read_text(encoding='utf-8'))

def save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    temp.replace(path)

def month_data(code,y,m):
    payload=get(f'https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={y}{m:02d}01&stockNo={code}')
    if payload.get('stat')!='OK': raise ValueError('TWSE: '+str(payload.get('stat','empty response')))
    out=[]
    for row in payload.get('data',[]):
        try:
            yy,mm,dd=map(int,row[0].split('/')); date=dt.date(yy+1911,mm,dd).isoformat()
            volume,amount=n(row[1]),n(row[2]); op,hi,lo,cl=[n(row[j]) for j in (3,4,5,6)]
            if None in (volume,amount,op,hi,lo,cl) or min(op,hi,lo,cl)<=0:continue
            out.append(dict(date=date,open=op,high=hi,low=lo,close=cl,volume=int(volume),amount=amount))
        except (ValueError,IndexError):continue
    return out

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--offline',action='store_true');p.add_argument('--bootstrap',action='store_true');args=p.parse_args(argv)
    today=dt.datetime.now(TZ).date(); watch=load(ROOT/'watchlist.json',[]); cfg=load(ROOT/'strategy_config.json',{})
    history=load(DATA/'history.json',{}); errors=[]
    for w in watch:
        code=w['symbol'];old=history.get(code,[])
        if args.offline:continue
        complete=len(old)>=250 and all(x.get('amount') is not None for x in old[-21:])
        count=16 if args.bootstrap or not complete else 2
        # No hidden network retries; failure preserves previous history and is visible.
        merged={x['date']:x for x in old}
        for k in range(count):
            month=today.year*12+today.month-1-k;y,m=divmod(month,12);m+=1
            try:
                for r in month_data(code,y,m):
                    if r['date']<=today.isoformat():merged[r['date']]=r
            except Exception as ex:errors.append(f'{code} {y}-{m:02d}: {type(ex).__name__}: {ex}')
            time.sleep(.4)
        history[code]=sorted(merged.values(),key=lambda x:x['date'])[-520:]
    if not args.offline:save(DATA/'history.json',history)
    asof=max((r[-1]['date'] for k,r in history.items() if r and any(w['symbol']==k for w in watch)),default=None)
    stocks=[]; signals=[]
    for w in watch:
        rows=[x for x in history.get(w['symbol'],[]) if x['date']<=today.isoformat()]
        found,issues=scan(rows,w['symbol'],cfg,asof)
        try:legacy=calc(w['symbol'],w['name'],rows)
        except (ValueError,KeyError,TypeError,ZeroDivisionError):legacy=None
        for s in found:s['stock_name']=w['name']
        # Fetch failure on the latest requested months is also an explicit quality flag.
        own_errors=[e for e in errors if e.startswith(w['symbol']+' ')]
        if own_errors:issues.append('本次行情擷取有錯誤，請檢查更新紀錄')
        stocks.append(dict(symbol=w['symbol'],name=w['name'],date=rows[-1]['date'] if rows else None,
            price=rows[-1]['close'] if rows else None,sample_days=len(rows),issues=issues,
            legacy_score=legacy['score'] if legacy else None,
            ma20=legacy['ma20'] if legacy else None,rsi=legacy['rsi'] if legacy else None,
            signals=found))
        signals.extend(found)
    # Freeze observed snapshots, keep legacy ledger.json byte-for-byte intact.
    journal=load(DATA/'signals_v2.json',{'strategy_version':VERSION,'snapshots':{},'trades':[]})
    if asof and not args.offline:
        journal['snapshots'].setdefault(asof,dict(observed_at=dt.datetime.now(TZ).isoformat(),signals=signals))
        save(DATA/'signals_v2.json',journal)
    report=dict(schema_version='2.0',strategy_version=VERSION,asof=asof,
        generated_at=dt.datetime.now(TZ).isoformat(),mode='OFFLINE_CACHE' if args.offline else 'EOD_RESEARCH',
        universe=len(watch),data_ready=sum(x['sample_days']>=250 for x in stocks),
        execution_ready=0,catalog=CATALOG,stocks=stocks,signals=signals,errors=errors,
        performance=dict(status='NOT_STARTED',trades=[],reason='六策略尚無校驗後模擬成交；舊版次日收盤模型已隔離保存，不沿用為六策略績效。'),
        caveats=['僅掃描watchlist中的上市普通股，非全市場，尚未支援上櫃資料源。',
            '訊號以完整日K計算；日線不足250根時不輸出策略候選。',
            'STOCK_DAY為未還原日行情，尚未接入除權息校驗、交易日曆與交易狀態。候選只供研究，非可執行買點。',
            '借券可得性及成本未確認；S6只供空方觀察。',
            'V3.3分數只作背景資訊，不是六策略買進門檻。',
            '未進行歷史回測或實際成交。未公布虛構勝率、PF或MDD。',
            '初始化會抓16個月行情；API錯誤會保留舊資料並揭露。'])
    save(DATA/'latest.json',report)
    print(f'Built {len(stocks)} stocks, warm={report["data_ready"]}, candidates={len(signals)}, errors={len(errors)}, mode={report["mode"]}')

if __name__=='__main__':main()
