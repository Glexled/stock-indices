#!/usr/bin/env python3
"""
Vercel Serverless Function: 获取分时数据 (支持 8 大指数)
"""
import json
import time
import re
from datetime import datetime
import requests

# ===================== 指数配置 =====================
INDICES = {
    'sh000001': '上证指数',
    'sh000300': '沪深300',
    'sh000016': '上证50',
    'sh000905': '中证500',
    'sh000852': '中证1000',
    'sh932000': '中证2000',
    'sh000688': '科创综指',
    'sz399006': '创业板指',
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://finance.sina.com.cn/',
}

def fetch_minute_data(symbol):
    # 中证2000 (sh932000) 优先尝试东方财富接口
    if symbol == 'sh932000':
        try:
            dfcf_url = "https://push2.eastmoney.com/api/qt/stock/trends2/get?secid=1.932000&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
            r = requests.get(dfcf_url, timeout=5)
            d = r.json()
            trends = d.get('data', {}).get('trends', [])
            if trends:
                return [{'time': t.split(',')[0].split(' ')[1], 'price': float(t.split(',')[2])} for t in trends]
        except: pass

    # 其他指数使用腾讯接口
    url = f'https://web.ifzq.gtimg.cn/appstock/app/minute/query?code={symbol}'
    try:
        r = requests.get(url, headers=HEADERS, timeout=5)
        d = r.json()
        arr = d['data'][symbol]['data']['data']
        if not arr: return None
        result = []
        for item in arr:
            parts = item.strip().split()
            if len(parts) < 2: continue
            t = parts[0]
            if len(t) == 4: t = t[:2] + ':' + t[2:]
            result.append({'time': t, 'price': float(parts[1])})
        return result
    except: return None

def fetch_realtime(symbols):
    codes = ','.join(symbols)
    url = f'https://hq.sinajs.cn/list={codes}'
    result = {}
    try:
        r = requests.get(url, headers=HEADERS, timeout=5)
        r.encoding = 'gbk'
        pattern = r'hq_str_(\w+)="([^"]*)"'
        for m in re.finditer(pattern, r.text):
            code = m.group(1)
            parts = m.group(2).split(',')
            if len(parts) > 5 and parts[0]:
                result[code] = {
                    'name': parts[0],
                    'prevClose': float(parts[2]) if parts[2] else None,
                    'current': float(parts[3]) if parts[3] else None,
                }
    except: pass
    return result

def calc_pct(data, prev_close=None):
    if not data: return []
    base = prev_close if prev_close else data[0]['price']
    if not base: return data
    return [{**item, 'pct': round((item['price'] / base - 1) * 100, 3)} for item in data]

def handler(request):
    try:
        rt = fetch_realtime(list(INDICES.keys()))
        result = {}
        for symbol in INDICES.keys():
            data = fetch_minute_data(symbol)
            if data:
                prev_close = rt.get(symbol, {}).get('prevClose')
                result[symbol] = calc_pct(data, prev_close)

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Cache-Control': 'no-cache, no-store, must-revalidate'
            },
            'body': json.dumps({
                'ok': True,
                'data': result,
                'realtime': rt,
                'updated': datetime.now().strftime('%H:%M:%S'),
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'ok': False, 'error': str(e)})
        }
