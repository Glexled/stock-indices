from http.server import BaseHTTPRequestHandler
import json
import requests
from datetime import datetime
from collections import OrderedDict

INDICES_CONFIG = OrderedDict([
    ('sh000001', {'name': '上证指数', 'secid': '1.000001'}),
    ('sh000016', {'name': '上证50', 'secid': '1.000016'}),
    ('sh000300', {'name': '沪深300', 'secid': '1.000300'}),
    ('sh000905', {'name': '中证500', 'secid': '1.000905'}),
    ('sh000852', {'name': '中证1000', 'secid': '1.000852'}),
    ('sh932000', {'name': '中证2000', 'secid': '1.932000'}),
    ('sh000680', {'name': '科创综指', 'secid': '1.000680'}),
    ('sh000688', {'name': '科创50', 'secid': '1.000688'}),
    ('sz399006', {'name': '创业板指', 'secid': '0.399006'})
])

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

def handler(request):
    """Vercel Serverless Function for minute data"""
    final_data = {}
    updated_time = datetime.now().strftime('%H:%M:%S')
    
    for symbol, config in INDICES_CONFIG.items():
        try:
            url = f"https://push2.eastmoney.com/api/qt/stock/trends2/get?secid={config['secid']}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
            resp = requests.get(url, headers=HEADERS, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            
            if data.get('data') and 'trends' in data['data'] and data['data']['trends']:
                pre_close = float(data['data'].get('preClose', 0))
                if pre_close > 0:
                    points = []
                    for t in data['data']['trends']:
                        try:
                            parts = t.split(',')
                            if len(parts) >= 3:
                                time_str = parts[0].split(' ')[1][:5]
                                price = float(parts[2])
                                pct = round((price / pre_close - 1) * 100, 2)
                                points.append({'time': time_str, 'pct': pct})
                        except:
                            continue
                    if points:
                        final_data[symbol] = points
        except Exception as e:
            print(f"Error fetching {symbol}: {str(e)}")
            continue
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Cache-Control': 'no-cache'
        },
        'body': json.dumps({
            'ok': True,
            'data': final_data,
            'updated': updated_time
        })
    }
