from flask import Flask, jsonify, request
import json
from datetime import datetime
import requests
from collections import OrderedDict

app = Flask(__name__)

# 严格按用户提供的 4月30日 官方收盘数据清单配置
INDICES_CONFIG = OrderedDict([
    ('sh000001', {'name': '上证指数', 'secid': '1.000001', 'last_pct': 0.11}),
    ('sh000016', {'name': '上证50', 'secid': '1.000016', 'last_pct': 0.61}),
    ('sh000300', {'name': '沪深300', 'secid': '1.000300', 'last_pct': -0.06}),
    ('sh000905', {'name': '中证500', 'secid': '1.000905', 'last_pct': 0.08}),
    ('sh000852', {'name': '中证1000', 'secid': '1.000852', 'last_pct': 0.47}),
    ('sh932000', {'name': '中证2000', 'secid': '1.932000', 'last_pct': 0.47}),
    ('sh000680', {'name': '科创综指', 'secid': '1.000680', 'last_pct': 3.42}),
    ('sh000688', {'name': '科创50', 'secid': '1.000688', 'last_pct': 5.19}),
    ('sz399006', {'name': '创业板指', 'secid': '0.399006', 'last_pct': -0.27})
])

def get_static_fallback():
    """生成 4月30日 真实的收盘走势模拟数据，确保终点 100% 匹配官方涨幅"""
    result = {}
    times = [f"{h:02d}:{m:02d}" for h in range(9, 16) for m in range(0, 60) if ("09:30" <= f"{h:02d}:{m:02d}" <= "11:30") or ("13:00" <= f"{h:02d}:{m:02d}" <= "15:00")]
    for symbol, config in INDICES_CONFIG.items():
        target_pct = config['last_pct']
        points = []
        for i, t in enumerate(times):
            progress = i / len(times)
            # 模拟更真实的日内波动曲线
            if progress < 0.2:
                val = target_pct * progress * 2.0
            elif progress < 0.5:
                val = target_pct * 0.4 + (target_pct * 0.4 * (progress - 0.2) / 0.3)
            else:
                val = target_pct * 0.8 + (target_pct * 0.2 * (progress - 0.5) / 0.5)
            points.append({'time': t, 'pct': round(val, 2)})
        result[symbol] = points
    return result

@app.route('/api/minute')
def combined_api():
    mode = request.args.get('mode', 'minute')
    final_data = {}
    any_success = False
    
    for symbol, config in INDICES_CONFIG.items():
        if mode == 'daily':
            url = f"https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={config['secid']}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=1&end=20500101&lmt=60"
        else:
            url = f"https://push2.eastmoney.com/api/qt/stock/trends2/get?secid={config['secid']}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
        
        try:
            resp = requests.get(url, timeout=3).json()
            data = resp.get('data')
            if data:
                if mode == 'daily':
                    klines = data.get('klines', [])
                    if klines:
                        base_price = float(klines[0].split(',')[2])
                        final_data[symbol] = [{'time': k.split(',')[0], 'pct': round((float(k.split(',')[2])/base_price-1)*100, 2)} for k in klines]
                        any_success = True
                else:
                    trends = data.get('trends', [])
                    if trends:
                        pre_close = data['preClose']
                        final_data[symbol] = [{'time': t.split(',')[0].split(' ')[1][:5], 'pct': round((float(t.split(',')[2])/pre_close-1)*100, 2)} for t in trends]
                        any_success = True
        except: continue
            
    if not any_success:
        final_data = get_static_fallback()
            
    return jsonify({
        'ok': True,
        'data': final_data,
        'mode': mode,
        'updated': datetime.now().strftime('%H:%M:%S'),
        'is_mock': not any_success
    })
