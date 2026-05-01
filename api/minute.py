from http.server import BaseHTTPRequestHandler
import json
import requests
from datetime import datetime
from collections import OrderedDict

# 新浪财经 API 指数代码映射
INDICES_CONFIG = OrderedDict([
    ('sh000001', {'name': '上证指数', 'sina_code': 'sh000001'}),
    ('sh000016', {'name': '上证50', 'sina_code': 'sh000016'}),
    ('sh000300', {'name': '沪深300', 'sina_code': 'sh000300'}),
    ('sh000905', {'name': '中证500', 'sina_code': 'sh000905'}),
    ('sh000852', {'name': '中证1000', 'sina_code': 'sh000852'}),
    ('sh932000', {'name': '中证2000', 'sina_code': 'sh932000'}),
    ('sh000680', {'name': '科创综指', 'sina_code': 'sh000680'}),
    ('sh000688', {'name': '科创50', 'sina_code': 'sh000688'}),
    ('sz399006', {'name': '创业板指', 'sina_code': 'sz399006'})
])

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Vercel Serverless Function for minute data using Sina Finance API"""
        final_data = {}
        updated_time = datetime.now().strftime('%H:%M:%S')
        
        for symbol, config in INDICES_CONFIG.items():
            try:
                # 使用新浪财经 API
                sina_code = config['sina_code']
                url = f"https://hq.sinajs.cn/rn={int(datetime.now().timestamp()*1000)}&list={sina_code}"
                
                resp = requests.get(url, headers=HEADERS, timeout=5)
                resp.raise_for_status()
                
                # 解析新浪财经数据格式
                # 格式: var hq_str_sh000001="上证指数,3000.00,100.00,3.23%,..."
                text = resp.text
                if 'hq_str_' in text:
                    # 提取引号内的数据
                    start = text.find('"') + 1
                    end = text.rfind('"')
                    if start > 0 and end > start:
                        data_str = text[start:end]
                        parts = data_str.split(',')
                        
                        if len(parts) >= 3:
                            try:
                                current_price = float(parts[3])
                                pre_close = float(parts[2])
                                
                                if pre_close > 0:
                                    pct = round((current_price / pre_close - 1) * 100, 2)
                                    
                                    # 获取分时数据 - 使用新浪的分时接口
                                    trend_url = f"https://vip.stock.finance.sina.com.cn/q_show.php?symbol={sina_code}&bdate=&edate=&begin=0&num=1000&sort=&asc=&page=1"
                                    trend_resp = requests.get(trend_url, headers=HEADERS, timeout=5)
                                    
                                    points = []
                                    if trend_resp.status_code == 200:
                                        # 尝试解析分时数据
                                        lines = trend_resp.text.split('\n')
                                        for line in lines:
                                            if ',' in line:
                                                try:
                                                    time_str, price_str = line.strip().split(',')[:2]
                                                    if len(time_str) == 5 and ':' in time_str:
                                                        price = float(price_str)
                                                        p = round((price / pre_close - 1) * 100, 2)
                                                        points.append({'time': time_str, 'pct': p})
                                                except:
                                                    continue
                                    
                                    # 如果没有获取到分时数据，至少返回当前价格
                                    if not points:
                                        now = datetime.now()
                                        time_str = f"{now.hour:02d}:{now.minute:02d}"
                                        points.append({'time': time_str, 'pct': pct})
                                    
                                    if points:
                                        final_data[symbol] = points
                            except (ValueError, IndexError):
                                continue
            except Exception as e:
                print(f"Error fetching {symbol}: {str(e)}")
                continue
        
        response = {
            'ok': True,
            'data': final_data,
            'updated': updated_time
        }
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.end_headers()
