from flask import Flask, jsonify, request
import json
import random
from datetime import datetime, timedelta
import requests

app = Flask(__name__)

INDICES_CONFIG = {
    'sh000001': {'name': '上证指数', 'secid': '1.000001', 'color': '#FFFFFF'},
    'sh000300': {'name': '沪深300', 'secid': '1.000300', 'color': '#4B9EFF'},
    'sh000016': {'name': '上证50', 'secid': '1.000016', 'color': '#2ECC71'},
    'sh000905': {'name': '中证500', 'secid': '1.000905', 'color': '#FFD700'},
    'sh000852': {'name': '中证1000', 'secid': '1.000852', 'color': '#FF69B4'},
    'sh932000': {'name': '中证2000', 'secid': '1.932000', 'color': '#9370DB'},
    'sh000688': {'name': '科创综指', 'secid': '1.000688', 'color': '#00FFFF'},
    'sz399006': {'name': '创业板指', 'secid': '0.399006', 'color': '#00FA9A'}
}

def get_history_kline(secid):
    """获取日线历史数据"""
    try:
        url = f"https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={secid}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=1&end=20500101&lmt=60"
        resp = requests.get(url, timeout=5).json()
        klines = resp.get('data', {}).get('klines', [])
        if not klines: return None
        
        # 计算涨跌幅相对于第一天
        base_price = float(klines[0].split(',')[2]) # 第一天的开盘价
        result = []
        for k in klines:
            parts = k.split(',')
            date = parts[0]
            close = float(parts[2])
            pct = round((close / base_price - 1) * 100, 2)
            result.append({'time': date, 'pct': pct})
        return result
    except: return None

def get_realtime_minute(secid):
    """获取实时分时数据"""
    try:
        url = f"https://push2.eastmoney.com/api/qt/stock/trends2/get?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
        resp = requests.get(url, timeout=5).json()
        data = resp.get('data')
        if not data or not data.get('trends'): return None
        pre_close = data['preClose']
        result = []
        for item in data['trends']:
            parts = item.split(',')
            time_str = parts[0].split(' ')[1][:5]
            pct = round((float(parts[2]) / pre_close - 1) * 100, 2)
            result.append({'time': time_str, 'pct': pct})
        return result
    except: return None

@app.route('/api/minute')
def combined_api():
    mode = request.args.get('mode', 'minute') # minute or daily
    final_data = {}
    any_success = False
    
    for symbol, config in INDICES_CONFIG.items():
        if mode == 'daily':
            data = get_history_kline(config['secid'])
        else:
            data = get_realtime_minute(config['secid'])
            
        if data:
            final_data[symbol] = data
            any_success = True
            
    # 兜底逻辑：如果接口全挂了或休市，返回一组固定的演示数据
    if not any_success:
        times = [f"{h:02d}:{m:02d}" for h in range(9, 16) for m in range(0, 60) if ("09:30" <= f"{h:02d}:{m:02d}" <= "11:30") or ("13:00" <= f"{h:02d}:{m:02d}" <= "15:00")]
        for symbol in INDICES_CONFIG.keys():
            final_data[symbol] = [{'time': t, 'pct': round(random.uniform(-1, 1), 2)} for t in times[:100]]
            
    return jsonify({
        'ok': True,
        'data': final_data,
        'mode': mode,
        'updated': datetime.now().strftime('%H:%M:%S'),
        'is_mock': not any_success
    })
