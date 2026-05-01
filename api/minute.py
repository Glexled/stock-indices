from flask import Flask, jsonify, request
import requests
from datetime import datetime
from collections import OrderedDict

app = Flask(__name__)

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

@app.route('/api/minute')
def minute_api():
    final_data = {}
    updated_time = datetime.now().strftime('%H:%M:%S')
    
    for symbol, config in INDICES_CONFIG.items():
        # 仅抓取当日分时数据
        url = f"https://push2.eastmoney.com/api/qt/stock/trends2/get?secid={config['secid']}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
        try:
            resp = requests.get(url, timeout=2).json()
            data = resp.get('data')
            if data and 'trends' in data:
                pre_close = data['preClose']
                final_data[symbol] = []
                for t in data['trends']:
                    parts = t.split(',')
                    # 仅保留时间部分 HH:mm
                    time_str = parts[0].split(' ')[1][:5]
                    price = float(parts[2])
                    # 严格按当日昨收价计算涨幅
                    pct = round((price / pre_close - 1) * 100, 2)
                    final_data[symbol].append({'time': time_str, 'pct': pct})
        except:
            continue
            
    return jsonify({
        'ok': True,
        'data': final_data,
        'updated': updated_time
    })
