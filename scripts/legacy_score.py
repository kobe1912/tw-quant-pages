"""V3.3 background score only. No network, portfolio or execution code."""
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
