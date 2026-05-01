from http.server import BaseHTTPRequestHandler
import json
import requests
from datetime import datetime
from collections import OrderedDict
import concurrent.futures

# 同花顺 API 指数代码映射
INDICES_CONFIG = OrderedDict([
    ('sh000001', {'name': '上证指数', 'ths_code': '000001'}),
    ('sh000016', {'name': '上证50', 'ths_code': '000016'}),
    ('sh000300', {'name': '沪深300', 'ths_code': '000300'}),
    ('sh000905', {'name': '中证500', 'ths_code': '000905'}),
    ('sh000852', {'name': '中证1000', 'ths_code': '000852'}),
    ('sh932000', {'name': '中证2000', 'ths_code': '932000'}),
    ('sh000680', {'name': '科创综指', 'ths_code': '000680'}),
    ('sh000688', {'name': '科创50', 'ths_code': '000688'}),
    ('sz399006', {'name': '创业板指', 'ths_code': '399006'})
])

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

def fetch_index_data(symbol, config):
    """从同花顺获取单个指数的数据"""
    try:
        ths_code = config['ths_code']
        
        # 同花顺分时数据 API
        url = f"http://api.ifeng.com/sstock/f10/index_trends.php?code={ths_code}&type=5"
        
        resp = requests.get(url, headers=HEADERS, timeout=4)
        resp.raise_for_status()
        
        # 尝试解析 JSON
        try:
            data = resp.json()
        except:
            # 如果不是 JSON，尝试其他 API
            url2 = f"https://qt.gtimg.cn/q=s_sh{ths_code}"
            resp = requests.get(url2, headers=HEADERS, timeout=4)
            text = resp.text
            
            # 解析腾讯财经格式: v_s_sh000001="上证指数","3000.00","100.00","3.23%",...
            if 'v_s_sh' in text or 's_sh' in text:
                # 提取数据
                start = text.find('"')
                if start > 0:
                    # 简单解析
                    parts = text.split('"')
                    if len(parts) >= 5:
                        try:
                            price = float(parts[3])
                            pre_close = float(parts[5])
                            
                            if pre_close > 0:
                                pct = round((price / pre_close - 1) * 100, 2)
                                
                                # 返回当前价格作为数据点
                                now = datetime.now()
                                time_str = f"{now.hour:02d}:{now.minute:02d}"
                                return symbol, [{'time': time_str, 'pct': pct}]
                        except:
                            pass
            return symbol, []
        
        # 解析同花顺 JSON 数据
        if isinstance(data, dict) and 'data' in data:
            trends = data.get('data', [])
            if trends and len(trends) > 0:
                points = []
                
                for item in trends:
                    try:
                        if isinstance(item, dict):
                            time_str = item.get('time', '')
                            pct = float(item.get('pct', 0))
                        elif isinstance(item, list) and len(item) >= 2:
                            time_str = str(item[0])
                            pct = float(item[1])
                        else:
                            continue
                        
                        if time_str and len(str(time_str)) >= 4:
                            # 确保时间格式是 HH:MM
                            time_str = str(time_str)[-5:] if len(str(time_str)) >= 5 else time_str
                            points.append({'time': time_str, 'pct': pct})
                    except (ValueError, TypeError, IndexError):
                        continue
                
                if points:
                    return symbol, points
        
        return symbol, []
        
    except Exception as e:
        print(f"Error fetching {symbol}: {str(e)}")
        return symbol, []

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Vercel Serverless Function for minute data using Tonghuashun API"""
        final_data = {}
        updated_time = datetime.now().strftime('%H:%M:%S')
        
        # 使用线程池并发获取数据
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(fetch_index_data, symbol, config): symbol 
                for symbol, config in INDICES_CONFIG.items()
            }
            
            for future in concurrent.futures.as_completed(futures, timeout=10):
                try:
                    symbol, points = future.result()
                    if points:
                        final_data[symbol] = points
                except Exception as e:
                    print(f"Future error: {str(e)}")
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
