#!/usr/bin/env python3
"""
Vercel Serverless Function: 获取K线数据
"""
import json
import time
import re
from datetime import datetime
import requests

# ===================== 缓存 =====================
_cache = {}
CACHE_TTL = {'5min': 120, '30min': 300, 'daily': 300}

def get_cache(key, ttl=300):
    item = _cache.get(key)
    if item and time.time() - item['ts'] < ttl:
        return item['data']
    return None

def set_cache(key, data):
    _cache[key] = {'data': data, 'ts': time.time()}

# ===================== 指数配置 =====================
INDICES = {
    'sh000300': '沪深300',
    'sh000016': '上证50',
    'sh000905': '中证500',
    'sh000852': '中证1000',
    'sh932000': '中证2000',
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://finance.sina.com.cn/',
}

# ===================== K线数据（新浪接口）=====================
def fetch_kline(symbol, scale, datalen):
    """
    scale: 5=5分钟, 30=30分钟, 240=日线
    """
    url = f'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={symbol}&scale={scale}&ma=no&datalen={datalen}'
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            result = []
            for item in data:
                result.append({
                    'time': item['day'],
                    'open': float(item['open']),
                    'high': float(item['high']),
                    'low': float(item['low']),
                    'close': float(item['close']),
                })
            return result
    except Exception as e:
        print(f'Kline error {symbol} scale={scale}: {e}')
    return None

# ===================== 实时行情（新浪）=====================
def fetch_realtime(symbols):
    codes = ','.join(symbols)
    url = f'https://hq.sinajs.cn/list={codes}'
    result = {}
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.encoding = 'gbk'
        pattern = r'hq_str_(\w+)="([^"]*)"'
        for m in re.finditer(pattern, r.text):
            code = m.group(1)
            parts = m.group(2).split(',')
            if len(parts) > 5 and parts[0]:
                try:
                    result[code] = {
                        'name': parts[0],
                        'open': float(parts[1]) if parts[1] else None,
                        'prevClose': float(parts[2]) if parts[2] else None,
                        'current': float(parts[3]) if parts[3] else None,
                        'high': float(parts[4]) if parts[4] else None,
                        'low': float(parts[5]) if parts[5] else None,
                    }
                except:
                    pass
    except Exception as e:
        print(f'Realtime error: {e}')
    return result

# ===================== 计算涨跌幅 =====================
def calc_pct(data, prev_close=None):
    """将价格序列转换为相对涨跌幅"""
    if not data:
        return []
    base = prev_close if prev_close else data[0].get('price') or data[0].get('close')
    if not base:
        return data
    result = []
    for item in data:
        price = item.get('price') or item.get('close')
        if price is None:
            result.append({**item, 'pct': None})
        else:
            result.append({**item, 'pct': round((price / base - 1) * 100, 3)})
    return result

# ===================== Vercel Handler =====================
def handler(request):
    """Main handler for Vercel"""
    try:
        period = request.args.get('period', 'daily') if hasattr(request, 'args') else 'daily'
        days = int(request.args.get('days', 60)) if hasattr(request, 'args') else 60

        scale_map = {'5min': 5, '30min': 30, 'daily': 240}
        scale = scale_map.get(period, 240)

        # 数据量估算
        if period == '5min':
            datalen = min(days * 48 + 50, 2000)
        elif period == '30min':
            datalen = min(days * 8 + 20, 2000)
        else:
            datalen = max(days + 20, 300)

        cache_key = f'kline_{period}_{days}'
        cached = get_cache(cache_key, CACHE_TTL.get(period, 300))
        if cached:
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'ok': True, 'data': cached, 'cached': True})
            }

        # 获取实时行情
        rt = fetch_realtime(list(INDICES.keys()))

        result = {}
        for symbol in INDICES.keys():
            data = fetch_kline(symbol, scale, datalen)
            if data:
                if period == 'daily' and days > 0 and len(data) > days:
                    data = data[-days:]
                
                prev_close = rt.get(symbol, {}).get('prevClose') if rt else None
                result[symbol] = calc_pct(
                    [{'time': d['time'], 'price': d['close']} for d in data],
                    prev_close
                )

        set_cache(cache_key, result)
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'ok': True,
                'data': result,
                'realtime': rt,
                'updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'ok': False, 'error': str(e)})
        }
