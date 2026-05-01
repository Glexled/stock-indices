#!/usr/bin/env python3
"""
Vercel Serverless Function: 获取实时行情
"""
import json
import time
import re
from datetime import datetime
import requests

# ===================== 缓存 =====================
_cache = {}
CACHE_TTL = 30

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

# ===================== Vercel Handler =====================
def handler(request):
    """Main handler for Vercel"""
    try:
        cached = get_cache('realtime', CACHE_TTL)
        if cached:
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'ok': True, 'data': cached})
            }
        
        data = fetch_realtime(list(INDICES.keys()))
        if data:
            set_cache('realtime', data)
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'ok': True, 'data': data})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'ok': False, 'error': str(e)})
        }
