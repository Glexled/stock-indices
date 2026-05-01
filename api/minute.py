#!/usr/bin/env python3
"""
Vercel Serverless Function: 获取分时数据
"""
import json
import time
import re
from datetime import datetime
import requests

# ===================== 缓存（简单内存缓存，Vercel 环境下会重置）=====================
_cache = {}
CACHE_TTL = 60

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

# ===================== 分时数据（腾讯接口）=====================
def fetch_minute_data(symbol):
    """获取今日分时数据"""
    url = f'https://web.ifzq.gtimg.cn/appstock/app/minute/query?code={symbol}'
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        d = r.json()
        arr = d['data'][symbol]['data']['data']
        if not arr or len(arr) <= 1:
            return None

        result = []
        for item in arr:
            parts = item.strip().split()
            if len(parts) < 2:
                continue
            t = parts[0]
            if len(t) == 4:
                t = t[:2] + ':' + t[2:]
            try:
                price = float(parts[1])
                result.append({'time': t, 'price': price})
            except:
                pass
        return result if len(result) > 1 else None
    except Exception as e:
        print(f'Minute error {symbol}: {e}')
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
        cached = get_cache('minute_all', CACHE_TTL)
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
            data = fetch_minute_data(symbol)
            if data:
                prev_close = rt.get(symbol, {}).get('prevClose') if rt else None
                result[symbol] = calc_pct(data, prev_close)

        set_cache('minute_all', result)
        
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
