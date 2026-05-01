from flask import Flask, jsonify
import json
import re
import random
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

def get_mock_data():
    """休市期间或接口失败时返回模拟数据，确保用户能看到曲线"""
    result = {}
    times = [f"{h:02d}:{m:02d}" for h in range(9, 16) for m in range(0, 60)]
    times = [t for t in times if ("09:30" <= t <= "11:30") or ("13:00" <= t <= "15:00")]
    
    for symbol in INDICES.keys():
        points = []
        current_pct = 0
        volatility = 0.05 if symbol != 'sh932000' else 0.1
        for t in times:
            current_pct += random.uniform(-volatility, volatility)
            points.append({'time': t, 'price': 3000 * (1 + current_pct/100), 'pct': round(current_pct, 3)})
        result[symbol] = points
    return result

def fetch_minute_data(symbol):
    try:
        if symbol == 'sh932000':
            url = "https://push2.eastmoney.com/api/qt/stock/trends2/get?secid=1.932000&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
            r = requests.get(url, timeout=5)
            d = r.json()
            trends = d.get('data', {}).get('trends', [])
            if trends:
                pre_close = d['data']['preClose']
                return [{'time': t.split(',')[0].split(' ')[1][:5], 'price': float(t.split(',')[2]), 'pct': round((float(t.split(',')[2])/pre_close-1)*100, 3)} for t in trends]
        
        url = f'https://web.ifzq.gtimg.cn/appstock/app/minute/query?code={symbol}'
        r = requests.get(url, timeout=5)
        d = r.json()
        arr = d['data'][symbol]['data']['data']
        if arr:
            pre_close = float(d['data'][symbol]['data']['qt'][symbol][4])
            return [{'time': f"{i.split()[0][:2]}:{i.split()[0][2:]}", 'price': float(i.split()[1]), 'pct': round((float(i.split()[1])/pre_close-1)*100, 3)} for i in arr]
    except: pass
    return None

@app.route('/api/minute')
def get_minute():
    try:
        result = {}
        has_data = False
        for symbol in INDICES.keys():
            data = fetch_minute_data(symbol)
            if data:
                result[symbol] = data
                has_data = True
        
        # 如果是休市期间（如现在）且没有抓到实时数据，返回模拟数据供预览
        if not has_data:
            result = get_mock_data()
            
        return jsonify({
            'ok': True,
            'data': result,
            'is_mock': not has_data,
            'updated': datetime.now().strftime('%H:%M:%S'),
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
