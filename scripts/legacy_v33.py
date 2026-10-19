"""Daily EOD static build. No API keys. TWSE monthly historical endpoint, listed shares only."""
import csv, datetime as dt, io, json, os, pathlib, time, urllib.request
from collections import defaultdict

ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/'docs'/'data'; DATA.mkdir(parents=True,exist_ok=True)
WATCH=json.loads((ROOT/'watchlist.json').read_text(encoding='utf-8'))
HISTORY=DATA/'history.json'; LEDGER=DATA/'ledger.json'; OUT=DATA/'latest.json'
TODAY=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()

def load(p,default):
    try:return json.loads(p.read_text(encoding='utf-8'))
    except (FileNotFoundError,json.JSONDecodeError):return default

def save(p,obj):
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')

def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=25) as r:return json.load(r)

def n(s):
    try:return float(str(s).replace(',','').strip())
    except (TypeError,ValueError):return None

def month_data(code,year,month):
    payload=get(f'https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={year}{month:02d}01&stockNo={code}')
    if payload.get('stat')!='OK':return []
    result=[]
    for row in payload.get('data',[]):
        try:
            y,m,d=map(int,row[0].split('/')); date=f'{y+1911:04d}-{m:02d}-{d:02d}'
            vol=n(row[1]); op,hi,lo,cl=[n(row[i]) for i in (3,4,5,6)]
            if None in (vol,op,hi,lo,cl) or min(op,hi,lo,cl)<=0:continue
            result.append(dict(date=date,open=op,high=hi,low=lo,close=cl,volume=int(vol)))
        except (ValueError,IndexError):continue
    return result

def calc(code,name,rows):
    if len(rows)<65:return None
    p=rows[-1]; prev=rows[-2]; c=[x['close'] for x in rows]
    ma20=sum(c[-20:])/20;ma60=sum(c[-60:])/60
    hi20=max(x['high'] for x in rows[-21:-1]);v20=sum(x['volume'] for x in rows[-21:-1])/20
    up=sum(max(c[i]-c[i-1],0) for i in range(len(c)-14,len(c)))
    down=sum(max(c[i-1]-c[i],0) for i in range(len(c)-14,len(c)))
    rsi=100 if down==0 else 100-100/(1+up/down)
    atr=sum(max(rows[i]['high']-rows[i]['low'],abs(rows[i]['high']-rows[i-1]['close']),abs(rows[i]['low']-rows[i-1]['close'])) for i in range(len(rows)-14,len(rows)))/14
    lo60=min(x['low'] for x in rows[-60:]);hi60=max(x['high'] for x in rows[-60:])
    tests=[(p['close']>ma20>ma60,30,'收盤價 > MA20 > MA60'),(p['close']>hi20,25,'突破前20日高點'),(p['volume']>v20*1.3,20,'成交量 > 20日均量1.3倍'),(50<=rsi<=75,15,'RSI14位於50至75'),(p['close']>(lo60+hi60)/2,10,'收盤位於60日價格區間上半部')]
    score=sum(w for ok,w,_ in tests if ok)
    exits=[]
    if p['close']<ma20:exits.append('收盤跌破MA20')
    if p['close']<ma60:exits.append('收盤跌破MA60')
    if rsi<45:exits.append('RSI14低於45')
    if p['close']<prev['close'] and p['volume']>v20*1.5:exits.append('放量下跌')
    action='EXIT_WATCH' if exits else ('BUY_WATCH' if score>=65 else 'HOLD_WATCH')
    return dict(date=p['date'],symbol=code,name=name,score=score,action=action,price=p['close'],stop=round(max(.01,p['close']-2*atr),2),target=round(p['close']+3*atr,2),reasons=[label for ok,_,label in tests if ok],exit_reasons=exits,ma20=round(ma20,2),rsi=round(rsi,2),sample_days=len(rows))

def main():
    history=load(HISTORY,{})
    errors=[]
    # Initial bootstrap: five recent months; subsequent runs: current + previous month.
    for item in WATCH:
        code=item['symbol']; old=history.get(code,[])
        months=5 if len(old)<65 else 2
        allrows={r['date']:r for r in old}
        for k in range(months):
            y=TODAY.year; m=TODAY.month-k
            while m<=0:y-=1;m+=12
            try:
                for row in month_data(code,y,m):allrows[row['date']]=row
            except Exception as exc:errors.append(f'{code} {y}-{m:02d}: {type(exc).__name__}: {exc}')
            time.sleep(0.3)
        history[code]=sorted(allrows.values(),key=lambda x:x['date'])[-260:]
    save(HISTORY,history)
    signals=[]
    for item in WATCH:
        s=calc(item['symbol'],item['name'],history.get(item['symbol'],[]))
        if s:signals.append(s)
    signals.sort(key=lambda s:(-s['score'],s['symbol']))
    dates=[s['date'] for s in signals]
    asof=max(dates) if dates else None
    # Only archive signals from a single current trading date, never stale mixes.
    current=[s for s in signals if s['date']==asof]
    ledger=load(LEDGER,{'snapshots':{},'trades':[]})
    if asof and asof not in ledger['snapshots']:
        ledger['snapshots'][asof]=current
    # Automated paper portfolio: next available trading close AFTER recommendation (conservative proxy, not fill).
    # Exit triggers checked at subsequent closes; mark all such results as hypothetical.
    existing={(t['symbol'],t['signal_date']) for t in ledger['trades']}
    for signal_date,items in sorted(ledger['snapshots'].items()):
        for s in items:
            if s['action']!='BUY_WATCH' or (s['symbol'],signal_date) in existing:continue
            future=[r for r in history.get(s['symbol'],[]) if r['date']>signal_date]
            if not future:continue
            entry=future[0]
            ledger['trades'].append(dict(symbol=s['symbol'],name=s['name'],signal_date=signal_date,entry_date=entry['date'],entry_price=entry['close'],qty=1000,stop=s['stop'],target=s['target'],exit_date=None,exit_price=None,exit_reason=None))
            existing.add((s['symbol'],signal_date))
    for t in ledger['trades']:
        if t['exit_date']:continue
        for r in history.get(t['symbol'],[]):
            if r['date']<=t['entry_date']:continue
            # EOD-only: use close for exit, not intraday hypothetical execution.
            reason='收盤跌破初始停損' if r['close']<=t['stop'] else ('收盤達到初始目標' if r['close']>=t['target'] else None)
            if reason:
                t.update(exit_date=r['date'],exit_price=r['close'],exit_reason=reason);break
    save(LEDGER,ledger)
    fee=.001425;tax=.003
    enriched=[]
    for t in ledger['trades']:
        rows=history.get(t['symbol'],[])
        mark=t['exit_price'] if t['exit_date'] else (rows[-1]['close'] if rows else None)
        if mark is None:continue
        buy=t['entry_price']*t['qty'];sell=mark*t['qty']
        pnl=round(sell*(1-fee-tax)-buy*(1+fee),2) if t['exit_date'] else round(sell-buy*(1+fee),2)
        enriched.append({**t,'mark_price':mark,'pnl':pnl,'return_pct':round(pnl/buy*100,2)})
    closed=[t for t in enriched if t['exit_date']];wins=[t for t in closed if t['pnl']>0]
    grossplus=sum(t['pnl'] for t in closed if t['pnl']>0);grossminus=-sum(t['pnl'] for t in closed if t['pnl']<0)
    weekly=defaultdict(lambda:{'realized':0,'closed':0,'wins':0})
    for t in closed:
        key=dt.date.fromisoformat(t['exit_date']).strftime('%G-W%V')
        weekly[key]['realized']+=t['pnl'];weekly[key]['closed']+=1;weekly[key]['wins']+=t['pnl']>0
    report={
        'asof':asof,'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),
        'universe':len(WATCH),'data_ready':len(signals),'signals':current,'errors':errors,
        'performance':{'realized':round(sum(t['pnl'] for t in closed),2),
            'unrealized':round(sum(t['pnl'] for t in enriched if not t['exit_date']),2),
            'closed':len(closed),'open':len(enriched)-len(closed),
            'win_rate':round(len(wins)/len(closed)*100,2) if closed else None,
            'profit_factor':round(grossplus/grossminus,2) if grossminus else None,
            'weekly':[{'week':k,**v,'realized':round(v['realized'],2)} for k,v in sorted(weekly.items())],
            'trades':enriched},
        'caveats':['只掃描 watchlist 指定上市股票，非全市場','每日收盤資料，非即時行情',
            '以次一交易日收盤價模擬進場，非真實成交','停損停利採收盤判斷，無盤中成交保證',
            '模擬損益假設一般股票手續費0.1425%、賣出證交稅0.3%，未計滑價及最低手續費',
            '未平倉損益未扣未來賣出費稅','若 API 失敗會保留舊資料並揭露錯誤']}

    save(OUT,report)
    print(f'Wrote {OUT}; signals={len(current)} errors={len(errors)}')

if __name__=='__main__':main()
