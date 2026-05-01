#!/usr/bin/env python3
"""
Vercel Serverless Function: 获取实时行情
"""
import json
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
                result[code] = {
                    'name': parts[0],
                    'current': float(parts[3]) if parts[3] else None,
                    'prevClose': float(parts[2]) if parts[2] else None,
                }
    except: pass
    return result

def handler(request):
    try:
        data = fetch_realtime(list(INDICES.keys()))
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'ok': True, 'data': data, 'updated': datetime.now().strftime('%H:%M:%S')})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'ok': False, 'error': str(e)})
        }
