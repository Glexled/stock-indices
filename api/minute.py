from flask import Flask, jsonify
import json
import random
from datetime import datetime
import requests

app = Flask(__name__)

# 定义 8 大指数及其东方财富 SecID
INDICES_CONFIG = {
    'sh000001': {'name': '上证指数', 'secid': '1.000001'},
    'sh000300': {'name': '沪深300', 'secid': '1.000300'},
    'sh000016': {'name': '上证50', 'secid': '1.000016'},
    'sh000905': {'name': '中证500', 'secid': '1.000905'},
    'sh000852': {'name': '中证1000', 'secid': '1.000852'},
    'sh932000': {'name': '中证2000', 'secid': '1.932000'},
    'sh000688': {'name': '科创综指', 'secid': '1.000688'},
    'sz399006': {'name': '创业板指', 'secid': '0.399006'}
}

def get_mock_data():
    """生成模拟走势数据，用于休市期间展示"""
    result = {}
    # 生成交易时间点
    times = []
    for h in range(9, 16):
        for m in range(0, 60):
            t = f"{h:02d}:{m:02d}"
            if ("09:30" <= t <= "11:30") or ("13:00" <= t <= "15:00"):
                times.append(t)
    
    for symbol in INDICES_CONFIG.keys():
        points = []
        current_pct = random.uniform(-0.5, 0.5)
        vol = 0.03
        for t in times:
            current_pct += random.uniform(-vol, vol)
            points.append({'time': t, 'pct': round(current_pct, 2)})
        result[symbol] = points
    return result

def fetch_from_eastmoney(secid):
    """从东方财富获取分时数据"""
    try:
        url = f"https://push2.eastmoney.com/api/qt/stock/trends2/get?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
        resp = requests.get(url, timeout=5).json()
        data = resp.get('data')
        if not data or not data.get('trends'):
            return None
        
        pre_close = data['preClose']
        trends = data['trends']
        result = []
        for item in trends:
            parts = item.split(',')
            time_str = parts[0].split(' ')[1][:5]
            price = float(parts[2])
            pct = round((price / pre_close - 1) * 100, 2)
            result.append({'time': time_str, 'pct': pct})
        return result
    except Exception:
        return None

@app.route('/api/minute')
def get_minute():
    try:
        final_data = {}
        any_success = False
        
        for symbol, config in INDICES_CONFIG.items():
            data = fetch_from_eastmoney(config['secid'])
            if data:
                final_data[symbol] = data
                any_success = True
        
        is_mock = False
        if not any_success:
            final_data = get_mock_data()
            is_mock = True
            
        return jsonify({
            'ok': True,
            'data': final_data,
            'is_mock': is_mock,
            'updated': datetime.now().strftime('%H:%M:%S')
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
