"""Six causal EOD research baselines. Standard library only; no brokerage orders."""
import math
VERSION = 'research-v3-sinopac'
CATALOG = [
 ('S1','趨勢回測','MA20回檔站穩','trend_pullback','long',40),
 ('S2','整理突破','壓縮後放量突破','compression_breakout','long',30),
 ('S3','反轉確認','W底頸線突破','reversal_confirmed','long',30),
 ('S4','箱型交易','箱底止跌至箱頂','range_reversion','long',15),
 ('S5','提前反轉','假跌破收復確認','early_reversal','long',5),
 ('S6','空方反轉','M右頭轉弱','short_reversal','short',15)]
CATALOG = [dict(id=i,name=n,description=d,family=f,direction=x,max_bars=b,
               backtest_status='UNVALIDATED') for i,n,d,f,x,b in CATALOG]

def features(rows):
    c=[r['close'] for r in rows]; f=[]; atr=None
    for i,r in enumerate(rows):
        tr=max(r['high']-r['low'],abs(r['high']-c[i-1]),abs(r['low']-c[i-1])) if i else r['high']-r['low']
        if i==13: atr=sum(x['tr'] for x in f)+tr; atr/=14
        elif i>13: atr=(atr*13+tr)/14
        m={n:sum(c[i-n+1:i+1])/n if i+1>=n else None for n in (5,10,20,60)}
        w=(max(m[n] for n in (5,10,20))-min(m[n] for n in (5,10,20)))/c[i] if m[20] else None
        av=sum(x['volume'] for x in rows[i-20:i])/20 if i>=20 else None
        f.append(dict(tr=tr,atr=atr,ma=m,width=w,rv=r['volume']/av if av else None))
    return f

def tick(p):
    # TWSE ordinary share price ladder, isolated for configuration/review.
    return .01 if p<10 else .05 if p<50 else .1 if p<100 else .5 if p<500 else 1 if p<1000 else 5

def below(p):
    # At a band boundary use the tick below the boundary (e.g. 50 -> 49.95).
    return round(p-tick(max(.01,p-1e-7)),4)

def above(p): return round(p+tick(p),4)

def pivots(rows,end):
    """Only pivots confirmed no later than end-1. Equal extremes: earliest wins."""
    out=[]
    for i in range(max(2,end-60),end-2):
        w=rows[i-2:i+3]; r=rows[i]
        low=r['low']==min(x['low'] for x in w) and all(x['low']>r['low'] for x in w[:2])
        high=r['high']==max(x['high'] for x in w) and all(x['high']<r['high'] for x in w[:2])
        if low and high: continue
        kind='L' if low else 'H' if high else None
        if not kind: continue
        if out and out[-1][1]==kind:
            old=out[-1][0]; better=r['low']<rows[old]['low'] if kind=='L' else r['high']>rows[old]['high']
            if better: out[-1]=(i,kind)
        elif not out or i-out[-1][0]>=3: out.append((i,kind))
    return out

def spaced_count(indices):
    chosen=[]
    for i in indices:
        if not chosen or i-chosen[-1]>=3: chosen.append(i)
    return len(chosen)

def detect_at(rows,t,f=None):
    if t<64: return []
    f=features(rows[:t+1]) if f is None else f
    r=rows[t]; q=rows[t-1]; a=f[t]['atr']; rv=f[t]['rv']; m=f[t]['ma']
    if not a or rv is None or r['high']<=r['low']: return []
    prev=rows[t-20:t]; A=max(x['high'] for x in prev); B=min(x['low'] for x in prev)
    close=r['close']; out=[]
    def add(s,stop,target,anchor,reasons,**kw):
        if stop<=0: return
        d=next(x for x in CATALOG if x['id']==s)
        risk=close-stop if d['direction']=='long' else stop-close
        if risk<=0: return
        rr=((target-close) if d['direction']=='long' else (close-target))/risk if target else None
        out.append(dict(strategy_id=s,strategy_version=VERSION,family=d['family'],name=d['name'],
            direction=d['direction'],signal_date=r['date'],status='CONFIRMED',stop_price=round(stop,4),
            target_price=round(target,4) if target else None,estimated_rr=round(rr,3) if rr is not None else None,
            reference_price=close,atr=a,anchor_time=anchor,
            setup_id=f'{s}:{anchor}',reasons=reasons,high_risk=s in ('S5','S6'),
            backtest_status='UNVALIDATED',entry_plan='NEXT_SESSION_OPEN',**kw))
    # S1: known trend and pullback.
    pm=f[t-1]['ma']; U=pm[20]>pm[60] and pm[20]>f[t-6]['ma'][20]
    stretched=any(rows[i]['close']>f[i]['ma'][20]+f[i]['atr'] for i in range(t-10,t))
    if U and stretched and m[20]-.5*a<=r['low']<=m[20]+.3*a and close>m[20] and close>r['open'] and close>q['close']:
        add('S1',below(min(x['low'] for x in rows[t-4:t+1])),None,r['date'],['MA20/MA60多頭','回測MA20收紅站回'])
    # S2: prior box; keep original boundaries with signal.
    compressed=sum(f[i]['width']<=.015 for i in range(t-5,t))>=3
    if A/B-1<=.12 and A-B>=2*f[t-1]['atr'] and compressed and close>A+.1*a and close>r['open'] and (close-r['low'])/(r['high']-r['low'])>=.75 and rv>=1.5:
        add('S2',below(r['low']),None,rows[t-20]['date'],['20日箱體放量突破',f'RV {rv:.2f}倍','均線壓縮'],boundary=A)
    # S3: confirmed bottom pivots; no right-pivot future leakage.
    ps=pivots(rows,t)
    for z in range(len(ps)-3,-1,-1):
        seq=ps[z:z+3]
        if [x[1] for x in seq]!=['L','H','L']: continue
        i,j,k=[x[0] for x in seq]; lo=rows[i]['low']; lk=rows[k]['low']; N=rows[j]['high']; D=min(lo,lk)
        if i<20 or not 5<=k-i<=40 or not 1<=t-(k+2)<=10: continue
        if rows[i-1]['close']/rows[i-21]['close']-1>-.10: continue
        if abs(lo-lk)>max(.03*lo,f[k]['atr']) or N-max(lo,lk)<2*f[k]['atr']: continue
        if any(x['close']<D for x in rows[k+2:t]): continue
        # First crossing after confirmation only.
        if any(rows[v]['close']>N+.1*f[v]['atr'] for v in range(k+3,t)): continue
        T=N+(N-D); S=below(D)
        if close>N+.1*a and q['close']<=N+.1*f[t-1]['atr'] and rv>=1.3 and (T-close)/(close-S)>=.8:
            add('S3',S,T,rows[k]['date'],['W底已確認','突破頸線',f'頸線 {N:.2f}'],boundary=N,pivot_confirmed_at=rows[k+2]['date']);break
    # S4: fixed range, not forced to inherit trend classification.
    pa=f[t-1]['atr']; hits_hi=spaced_count([i for i,x in enumerate(prev) if x['high']>=A-.3*pa]); hits_lo=spaced_count([i for i,x in enumerate(prev) if x['low']<=B+.3*pa])
    if .04<=A/B-1<=.12 and abs(pm[20]/f[t-6]['ma'][20]-1)<=.01 and min(hits_hi,hits_lo)>=2:
        S=B-.5*a; T=A-.3*a
        if B-.3*a<=r['low']<=B+.3*a and close>B and close>r['open'] and close<=B+.3*(A-B) and close>S and (T-close)/(close-S)>=1.5:
            add('S4',S,T,rows[t-20]['date'],['箱體上下緣多次接觸','箱底收紅止跌'],boundary=B)
    # S5: g=t-1 failed breakdown; confirmation at t; entry cannot precede t+1.
    g=t-1; gr=rows[g]; prior=rows[g-20:g]; b=min(x['low'] for x in prior); top=max(x['high'] for x in prior); ga=f[g]['atr']
    decline=rows[g-1]['close']/rows[g-21]['close']-1
    if decline>=-.25 and gr['high']>gr['low'] and gr['low']<b-.1*ga and gr['close']>b and gr['close']>gr['open'] and (gr['close']-gr['low'])/(gr['high']-gr['low'])>=.5 and f[g]['rv']>=1.2:
        S=below(gr['low']); T=min(top,m[20])
        if close>gr['high']+.1*ga and r['low']>gr['low'] and close>S and (T-close)/(close-S)>=1.5:
            add('S5',S,T,gr['date'],['跌破舊低後收復','隔日收盤突破收復棒高點'],boundary=b)
    # S6: early right head, not a future-confirmed second pivot.
    for z in range(len(ps)-2,-1,-1):
        seq=ps[z:z+2]
        if [x[1] for x in seq]!=['H','L']: continue
        i,j=[x[0] for x in seq]; hi=rows[i]['high']; N=rows[j]['low']
        if i<21 or not 5<=t-i<=40 or rows[i-1]['close']/rows[i-21]['close']-1<.10 or hi-N<2*f[j]['atr']: continue
        S=above(max(hi,r['high'])); T=N-(hi-N)
        if T<=0: continue
        if abs(r['high']-hi)<=max(.03*hi,a) and close<r['open'] and close<q['close'] and (close-r['low'])/(r['high']-r['low'])<=.5 and N<close<=hi+.5*a and (close-T)/(S-close)>=1.5:
            add('S6',S,T,rows[i]['date'],['高檔右頭轉弱','尚未跌破頸線'],boundary=N);break
    return out

def validate_rows(rows):
    last=''
    for r in rows:
        if r['date']<=last: return '日期重複或非遞增'
        last=r['date']
        if any(not isinstance(r.get(k),(int,float)) or not math.isfinite(r[k]) for k in ('open','high','low','close','volume')): return 'OHLCV缺失或非有限數值'
        if min(r[k] for k in ('open','high','low','close'))<=0 or r['volume']<0 or r['low']>min(r['open'],r['close']) or r['high']<max(r['open'],r['close']): return 'OHLCV無效'
    return None

def scan(rows,symbol,config,asof):
    error=validate_rows(rows); issues=[]
    if error: issues.append(error)
    if len(rows)<250: issues.append(f'暖機不足：{len(rows)}/250根')
    if rows and rows[-1]['date']!=asof: issues.append('行情日期落後最新股票')
    amounts=[x.get('amount') for x in rows[-21:-1]]
    if len(amounts)!=20 or any(x is None or x<0 for x in amounts): issues.append('缺少20日成交金額')
    elif sum(amounts)/20<config['min_average_amount']: issues.append('20日平均成交金額不足')
    # Raw broker bars also require independent corporate-action/calendar/status checks.
    issues.extend(['除權息還原／交易日曆／交易狀態尚未校驗'])
    if error or len(rows)<250: return [],issues
    found=detect_at(rows,len(rows)-1)
    for s in found:
        s.update(symbol=symbol,setup_id=f'{symbol}:{s["setup_id"]}',status='DATA_MISSING',
                 execution_eligibility=False,data_quality=issues,action='RESEARCH_CANDIDATE')
    dirs={s['direction'] for s in found}
    for s in found:
        s['primary']=len(dirs)==1 and s is found[0]
        if len(dirs)>1:s['status']='CONFLICT'
        if s['direction']=='short':s['warnings']=['借券可得性未確認；僅空方觀察']
    return found,issues
