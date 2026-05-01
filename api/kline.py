from flask import Flask, request, jsonify
import json
import re
from datetime import datetime
import requests

app = Flask(__name__)

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

def fetch_kline(symbol, scale, datalen):
    url = f'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={symbol}&scale={scale}&ma=no&datalen={datalen}'
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            return [{'time': item['day'], 'price': float(item['close'])} for item in data]
    except: pass
    return None

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
                result[code] = {'prevClose': float(parts[2]) if parts[2] else None}
    except: pass
    return result

def calc_pct(data, prev_close=None):
    if not data: return []
    base = prev_close if prev_close else data[0]['price']
    if not base: return data
    return [{**item, 'pct': round((item['price'] / base - 1) * 100, 3)} for item in data]

@app.route('/api/kline')
def get_kline():
    try:
        period = request.args.get('period', 'daily')
        days = int(request.args.get('days', 60))
        scale_map = {'5min': 5, '30min': 30, 'daily': 240}
        scale = scale_map.get(period, 240)
        datalen = days + 20 if period == 'daily' else days * 8 + 20

        rt = fetch_realtime(list(INDICES.keys()))
        result = {}
        for symbol in INDICES.keys():
            data = fetch_kline(symbol, scale, datalen)
            if data:
                if period == 'daily' and len(data) > days: data = data[-days:]
                prev_close = rt.get(symbol, {}).get('prevClose')
                result[symbol] = calc_pct(data, prev_close)

        return jsonify({
            'ok': True,
            'data': result,
            'updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
