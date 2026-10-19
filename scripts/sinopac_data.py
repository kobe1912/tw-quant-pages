"""Read-only Shioaji transport. No account queries, certificates or order methods."""
import contextlib,datetime as dt,math,os,statistics,tempfile,time
from pathlib import Path

class ProviderError(RuntimeError):pass

@contextlib.contextmanager
def silent_native():
    """SDK may log account identifiers at native level; suppress raw SDK output."""
    import sys
    sys.stdout.flush();sys.stderr.flush()
    out,err=os.dup(1),os.dup(2)
    with open(os.devnull,'w') as sink:
        os.dup2(sink.fileno(),1);os.dup2(sink.fileno(),2)
        try:yield
        finally:
            sys.stdout.flush();sys.stderr.flush();os.dup2(out,1);os.dup2(err,2);os.close(out);os.close(err)

def windows(start,end):
    """Inclusive calendar ranges, never longer than 30 calendar days."""
    cursor=start
    while cursor<=end:
        stop=min(cursor+dt.timedelta(days=29),end)
        yield cursor,stop
        cursor=stop+dt.timedelta(days=1)

def naive_timestamp(value):
    # Shioaji Python examples encode local wall-clock in nanoseconds (pandas.to_datetime).
    # Do not add another UTC+8 to these naive integer values.
    if isinstance(value,(int,float)):
        if not math.isfinite(value):raise ValueError('timestamp nonfinite')
        return dt.datetime(1970,1,1)+dt.timedelta(microseconds=int(value)//1000)
    t=dt.datetime.fromisoformat(str(value).replace('Z','+00:00'))
    return t.astimezone(dt.timezone(dt.timedelta(hours=8))).replace(tzinfo=None) if t.tzinfo else t

def aggregate(payload,start,end):
    """Aggregate only regular-session minute bars. Infer volume scale from Amount/OHLC.
    A unit ambiguity fails closed, never guesses a multiplier from symbol/market.
    """
    if hasattr(payload,'dict'):payload=payload.dict()
    elif not isinstance(payload,dict):payload=dict(payload)
    keys=['ts','Open','High','Low','Close','Volume','Amount']
    if not all(k in payload for k in keys):raise ValueError('missing kbar fields')
    n=len(payload['ts'])
    if any(len(payload[k])!=n for k in keys):raise ValueError('unequal kbar arrays')
    bars=[];scales=[];seen=set()
    for i in range(n):
        t=naive_timestamp(payload['ts'][i]);date=t.date()
        if not start<=date<=end or not dt.time(9)<=t.time()<=dt.time(13,30):continue
        if t in seen:raise ValueError('duplicate minute timestamp')
        seen.add(t)
        o,h,l,c,v,amount=[float(payload[k][i]) for k in keys[1:]]
        if not all(math.isfinite(x) for x in (o,h,l,c,v,amount)):raise ValueError('nonfinite kbar')
        if v==0 and amount==0:continue
        if min(o,h,l,c)<=0 or v<=0 or amount<=0 or l>min(o,c) or h<max(o,c):raise ValueError('invalid kbar')
        ratio=amount/(v*((o+h+l+c)/4))
        scale=1 if .75<=ratio<=1.25 else 1000 if 750<=ratio<=1250 else None
        if scale is None:raise ValueError('volume unit not verified')
        scales.append(scale);bars.append((t,o,h,l,c,v,amount))
    if not bars:return []
    if len(set(scales))!=1:raise ValueError('inconsistent volume scale')
    scale=scales[0];days={}
    for t,o,h,l,c,v,amount in sorted(bars):
        key=t.date().isoformat()
        if key not in days:days[key]=dict(date=key,open=o,high=h,low=l,close=c,volume=0,amount=0,provider='SINOPAC_SHIOAJI',price_basis='RAW_REGULAR_SESSION',volume_scale=scale)
        r=days[key];r['high']=max(r['high'],h);r['low']=min(r['low'],l);r['close']=c;r['volume']+=int(round(v*scale));r['amount']+=amount
    return list(days.values())

class SinopacReader:
    def __init__(self,interval=.5,reserve=100*1024*1024):
        self.api=None;self.interval=interval;self.reserve=reserve;self.last=0;self.usage_summary=None
    def __enter__(self):
        key=os.environ.get('SINOPAC_API_KEY','');secret=os.environ.get('SINOPAC_SECRET_KEY','')
        if not key or not secret:raise ProviderError('MISSING_SECRETS: 設定 SINOPAC_API_KEY 與 SINOPAC_SECRET_KEY')
        self.temp=tempfile.TemporaryDirectory(prefix='sinopac-sdk-');self.cwd=Path.cwd()
        try:
            os.chdir(self.temp.name)
            with silent_native():
                import shioaji as sj
                self.api=sj.Shioaji(simulation=os.environ.get('SINOPAC_SIMULATION','true').lower()=='true')
                self.api.login(api_key=key,secret_key=secret,subscribe_trade=False)
            self.check_usage()
        except ProviderError:
            self.__exit__(None,None,None);raise
        except Exception as exc:
            self.__exit__(None,None,None)
            # Never forward exception bodies (may contain server/account/token details).
            raise ProviderError('LOGIN_FAILED: '+type(exc).__name__+'；檢查連線、API權限、簽署狀態與IP限制') from None
        finally:os.chdir(self.cwd)
        return self
    def check_usage(self):
        try:
            with silent_native():u=self.api.usage()
            remaining=int(u.remaining_bytes)
            self.usage_summary=dict(remaining_bytes=remaining,limit_bytes=int(u.limit_bytes))
            if remaining<self.reserve:raise ProviderError('QUOTA_LOW: 流量餘額低於預留門檻，已停止補抓')
        except ProviderError:raise
        except Exception as exc:raise ProviderError('USAGE_UNAVAILABLE: '+type(exc).__name__) from None
    def fetch(self,symbol,market,start,end):
        if (end-start).days>29:raise ValueError('max 30 calendar days inclusive')
        self.check_usage();time.sleep(max(0,self.interval-(time.monotonic()-self.last)))
        try:
            with silent_native():
                contract=self.api.contracts.get(symbol)
                if contract is None:raise ValueError('contract not found')
                exchange=str(getattr(contract,'exchange','')).split('.')[-1]
                expected={'TWSE':'TSE','TPEx':'OTC'}[market]
                if exchange!=expected:raise ValueError('contract exchange mismatch')
                bars=self.api.kbars(contract,start=start.isoformat(),end=end.isoformat(),timeout=30000)
            return aggregate(bars,start,end)
        except Exception as exc:raise ProviderError('QUERY_FAILED: '+type(exc).__name__+'；代號 '+symbol) from None
        finally:self.last=time.monotonic()
    def __exit__(self,*args):
        if self.api:
            try:
                with silent_native():self.api.logout()
            except Exception:pass
        if hasattr(self,'cwd'):os.chdir(self.cwd)
        if hasattr(self,'temp'):self.temp.cleanup()
