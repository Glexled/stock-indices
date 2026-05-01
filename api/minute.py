from http.server import BaseHTTPRequestHandler
import json
import requests
from datetime import datetime
from collections import OrderedDict

# 东方财富 API 指数代码映射
INDICES_CONFIG = OrderedDict([
    ('sh000001', {'name': '上证指数', 'secid': '1.000001'}),
    ('sh000016', {'name': '上证50', 'secid': '1.000016'}),
    ('sh000300', {'name': '沪深300', 'secid': '1.000300'}),
    ('sh000905', {'name': '中证500', 'secid': '1.000905'}),
    ('sh000852', {'name': '中证1000', 'secid': '1.000852'}),
    ('sh932000', {'name': '中证2000', 'secid': '1.932000'}),  # 修复：确保 secid 正确
    ('sh000680', {'name': '科创综指', 'secid': '1.000680'}),
    ('sh000688', {'name': '科创50', 'secid': '1.000688'}),
    ('sz399006', {'name': '创业板指', 'secid': '0.399006'})
])

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Vercel Serverless Function for minute data using Eastmoney API"""
        final_data = {}
        updated_time = datetime.now().strftime('%H:%M:%S')
        
        for symbol, config in INDICES_CONFIG.items():
            try:
                secid = config['secid']
                # 东方财富分时数据 API
                url = f"https://push2.eastmoney.com/api/qt/stock/trends2/get?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58&ut=fa44cfb3f7e6c18e&_=1"
                
                resp = requests.get(url, headers=HEADERS, timeout=8)
                resp.raise_for_status()
                data = resp.json()
                
                # 检查数据结构
                if data.get('data') and 'trends' in data['data'] and data['data']['trends']:
                    trends = data['data']['trends']
                    pre_close = float(data['data'].get('preClose', 0))
                    
                    if pre_close > 0 and len(trends) > 0:
                        points = []
                        for trend_item in trends:
                            try:
                                # 东方财富数据格式: "2024-05-01 09:30,3000.00,3100.00,..."
                                parts = trend_item.split(',')
                                if len(parts) >= 3:
                                    # 提取时间部分
                                    time_part = parts[0]
                                    if ' ' in time_part:
                                        time_str = time_part.split(' ')[1][:5]  # 取 HH:MM
                                    else:
                                        time_str = time_part[:5]
                                    
                                    # 提取价格
                                    price = float(parts[2])
                                    pct = round((price / pre_close - 1) * 100, 2)
                                    
                                    points.append({'time': time_str, 'pct': pct})
                            except (ValueError, IndexError):
                                continue
                        
                        if points:
                            final_data[symbol] = points
                else:
                    # 如果没有分时数据，记录错误但不中断
                    print(f"No trends data for {symbol}: {data.get('data', {}).get('trends', 'N/A')}")
                    
            except requests.exceptions.Timeout:
                print(f"Timeout fetching {symbol}")
                continue
            except requests.exceptions.RequestException as e:
                print(f"Request error for {symbol}: {str(e)}")
                continue
            except Exception as e:
                print(f"Error fetching {symbol}: {str(e)}")
                continue
        
        response = {
            'ok': True,
            'data': final_data,
            'updated': updated_time,
            'count': len(final_data)
        }
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.end_headers()
        self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.end_headers()
