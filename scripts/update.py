"""SinoPac-only EOD builder. No trading calls. Legacy caches remain untouched."""
import argparse,datetime as dt,json,pathlib,sys
from strategies import CATALOG,VERSION,scan
from legacy_score import calc
from sinopac_data import ProviderError,SinopacReader,windows
ROOT=pathlib.Path(__file__).resolve().parents[1];DATA=ROOT/'docs'/'data';TZ=dt.timezone(dt.timedelta(hours=8))
def load(path,default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default

def save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');temp.replace(path)

def update_history(watch,history,state,cfg,reader,end):
    """Bounded single session, inclusive 30-day chunks; persisted cursor is resumable."""
    used=0;errors=[];stamp=dt.datetime.now(TZ).isoformat();budget=cfg['max_requests_per_run']
    # Fair rotation: absent/old attempts first, regardless of numeric industry order.
    queue=sorted(watch,key=lambda w:(state.get(w['symbol'],{}).get('last_attempt',''),w['symbol']))
    for w in queue:
        if used>=budget:break
        code=w['symbol'];meta=state.setdefault(code,{});old=history.get(code,[])
        origin=meta.setdefault('origin',max((end-dt.timedelta(days=cfg['bootstrap_calendar_days'])).isoformat(),w.get('listing_date') or '1900-01-01'))
        cursor=dt.date.fromisoformat(meta['cursor'])+dt.timedelta(days=1) if meta.get('cursor') else dt.date.fromisoformat(origin)
        # On an up-to-date symbol, re-query the final two dates to pick up EOD corrections.
        if cursor>end:cursor=max(dt.date.fromisoformat(origin),end-dt.timedelta(days=1))
        merged={r['date']:r for r in old};meta['last_attempt']=stamp
        for start,stop in windows(cursor,end):
            if used>=budget:break
            used+=1
            try:
                rows=reader.fetch(code,w['market'],start,stop)
                if not rows and (stop-start).days>=7:raise ProviderError('EMPTY_RANGE: 長區間未返回行情，保留游標待查')
                for r in rows:merged[r['date']]=r
                # Replace complete date windows only when returned rows exist.
                # Delisted/holiday empty periods never delete an existing day.
                meta.update(cursor=stop.isoformat(),last_error=None)
            except ProviderError as exc:
                errors.append(str(exc));meta['last_error']=str(exc)
                if str(exc).startswith(('QUOTA_LOW','USAGE_UNAVAILABLE')):
                    history[code]=sorted(merged.values(),key=lambda r:r['date'])[-520:]
                    return used,errors
                break
        history[code]=sorted(merged.values(),key=lambda r:r['date'])[-520:]
    return used,errors

def sector_summary(stocks,memberships,asof):
    by={s['symbol']:s for s in stocks};groups=[]
    for group in memberships['groups']:
        members=[by[x] for x in group['symbols'] if x in by]
        ready=[s for s in members if s['sample_days']>=250 and s['date']==asof and s['daily_return_pct'] is not None]
        # Constituents removed from active pool still count in original source total.
        total=len(group['symbols']);active=len(members);coverage=len(ready)/active if active else 0
        complete=active>0 and len(ready)==active
        groups.append(dict(name=group['name'],source_members=total,active_members=active,
            ready_members=len(ready),coverage_pct=round(coverage*100,1),complete=complete,
            average_return_pct=round(sum(s['daily_return_pct'] for s in ready)/len(ready),3) if complete else None,
            above_ma20_pct=round(sum(s['price']>s['ma20'] for s in ready)/len(ready)*100,1) if complete else None,
            candidate_count=sum(bool(s['signals']) for s in ready)))
    return sorted(groups,key=lambda g:(not g['complete'],-(g['average_return_pct'] or 0),g['name']))

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--offline',action='store_true');p.add_argument('--check-connection',action='store_true');p.add_argument('--max-requests',type=int);a=p.parse_args(argv)
    cfg=load(ROOT/'strategy_config.json',{});watch=load(ROOT/'watchlist.json',[]);memberships=load(ROOT/'sector_memberships.json',{'groups':[]})
    if a.max_requests is not None:
        if not 1<=a.max_requests<=200:raise ValueError('max-requests must be 1..200')
        cfg['max_requests_per_run']=a.max_requests
    history=load(DATA/'sinopac_history.json',{});state=load(DATA/'sinopac_sync.json',{});errors=[];used=0;usage=None
    now=dt.datetime.now(TZ);end=now.date() if now.time()>=dt.time(14,35) else now.date()-dt.timedelta(days=1)
    if not a.offline:
        # Any login error exits before writing latest; existing published data stays intact.
        with SinopacReader(cfg['min_request_interval_seconds'],cfg['min_remaining_bytes']) as reader:
            if a.check_connection:
                start=end-dt.timedelta(days=4);rows=reader.fetch('2330','TWSE',start,end)
                if not rows:raise ProviderError('EMPTY_PROBE: 登入完成但未取得測試行情')
                print(json.dumps({'provider':'SINOPAC_SHIOAJI','connection':'OK','symbol':'2330','daily_rows':len(rows),'order_calls':0},ensure_ascii=False));return
            used,errors=update_history(watch,history,state,cfg,reader,end);usage=reader.usage_summary
        save(DATA/'sinopac_history.json',history);save(DATA/'sinopac_sync.json',state)
        if used and not any(rows for rows in history.values()):
            raise ProviderError('NO_DATA: 查詢未取得任何行情，未發布新頁面；請查query錯誤與流量限制')
    asof=max((rows[-1]['date'] for rows in history.values() if rows),default=None);stocks=[];signals=[]
    for w in watch:
        code=w['symbol'];rows=history.get(code,[]);found,issues=scan(rows,code,cfg,asof)
        if state.get(code,{}).get('last_error'):issues.append('該股最近擷取失敗，保留快取')
        if not rows:issues.append('永豐歷史行情尚未初始化')
        try:legacy=calc(code,w['name'],rows)
        except (ValueError,KeyError,TypeError,ZeroDivisionError):legacy=None
        for s in found:s.update(stock_name=w['name'],groups=w.get('groups',[]),provider='SINOPAC_SHIOAJI')
        stocks.append(dict(symbol=code,name=w['name'],market=w['market'],groups=w.get('groups',[]),date=rows[-1]['date'] if rows else None,
            price=rows[-1]['close'] if rows else None,sample_days=len(rows),issues=issues,
            provider='SINOPAC_SHIOAJI',legacy_score=legacy['score'] if legacy else None,ma20=legacy['ma20'] if legacy else None,
            rsi=legacy['rsi'] if legacy else None,daily_return_pct=(rows[-1]['close']/rows[-2]['close']-1)*100 if len(rows)>=2 else None,signals=found))
        signals.extend(found)
    groups=sector_summary(stocks,memberships,asof)
    report=dict(schema_version='3.0',strategy_version=VERSION,provider='SINOPAC_SHIOAJI',asof=asof,generated_at=now.isoformat(),
        mode='OFFLINE_CACHE' if a.offline else 'EOD_RESEARCH',universe=len(watch),data_ready=sum(s['sample_days']>=250 for s in stocks),
        current_ready=sum(s['sample_days']>=250 and s['date']==asof for s in stocks),execution_ready=0,
        sync=dict(requests=used,max_requests=cfg['max_requests_per_run'],initialized=sum(bool(s['sample_days']) for s in stocks),usage=usage),
        catalog=CATALOG,stocks=stocks,signals=signals,sectors=groups,errors=errors,
        performance=dict(status='NOT_STARTED',trades=[],reason='只讀行情與研究候選。完整撮合、成本與持倉回測尚未完成，舊版績效不混入。'),
        caveats=['行情來源：永豐金證券Shioaji；由分鐘K聚合正常交易時段日K，非盤中即時網站。',
            '339檔為官方名單匹配的候選股票，含上市／上櫃；3檔終止標的已排除。',
            '首次初始化分批續跑；不足250根及未同步至最新資料日者不可當完整族群資料。',
            '每次查詢最多30天，總請求與帳戶流量保留門檻雙重限制。',
            '原始價格尚未經除權息、完整交易日曆與交易狀態校驗，訊號均為研究候選；不是可執行買點。',
            '族群平均漲跌與MA20比例僅在該族群所有啟用成員同日完成暖機時顯示；不是已驗證資金動能分數。',
            '未查詢帳戶資產／持倉，未啟用憑證，未包含任何下單呼叫。'])
    if not a.offline and asof:
        journal=load(DATA/'sinopac_signals.json',{'strategy_version':VERSION,'provider':'SINOPAC_SHIOAJI','snapshots':{}})
        # Freeze multiple observations of the same market date without replacing earlier coverage.
        journal['snapshots'].setdefault(now.date().isoformat(),[]).append(dict(observed_at=now.isoformat(),market_date=asof,current_ready=report['current_ready'],signals=signals))
        save(DATA/'sinopac_signals.json',journal)
    save(DATA/'latest.json',report)
    print(f'SINOPAC_SHIOAJI: {report["data_ready"]}/{len(watch)} warm; {len(signals)} research candidates; {used} requests; {len(errors)} errors')

if __name__=='__main__':
    try:main()
    except ProviderError as exc:print(str(exc),file=sys.stderr);sys.exit(1)
