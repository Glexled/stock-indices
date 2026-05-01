from http.server import BaseHTTPRequestHandler
import json
import requests
from datetime import datetime
from collections import OrderedDict
import concurrent.futures
import time

# 东方财富 API 指数代码映射
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

# 简单的内存缓存
_cache = {}
_cache_time = {}
CACHE_DURATION = 5  # 缓存 5 秒

def fetch_index_data(symbol, config):
    """获取单个指数的数据"""
    try:
        secid = config['secid']
        url = f"https://push2.eastmoney.com/api/qt/stock/trends2/get?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58&ut=fa44cfb3f7e6c18e&_={int(time.time()*1000)}"
        
        resp = requests.get(url, headers=HEADERS, timeout=2)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get('data') and 'trends' in data['data'] and data['data']['trends']:
            trends = data['data']['trends']
            pre_close = float(data['data'].get('preClose', 0))
            
            if pre_close > 0 and len(trends) > 0:
                points = []
                for trend_item in trends:
                    try:
                        parts = trend_item.split(',')
                        if len(parts) >= 3:
                            time_part = parts[0]
                            if ' ' in time_part:
                                time_str = time_part.split(' ')[1][:5]
                            else:
                                time_str = time_part[:5]
                            
                            price = float(parts[2])
                            pct = round((price / pre_close - 1) * 100, 2)
                            
                            points.append({'time': time_str, 'pct': pct})
                    except (ValueError, IndexError):
                        continue
                
                if points:
                    return symbol, points
        
        return symbol, []
    except requests.exceptions.Timeout:
        # 超时时返回缓存数据
        if symbol in _cache:
            return symbol, _cache[symbol]
        return symbol, []
    except Exception as e:
        print(f"Error fetching {symbol}: {str(e)}")
        # 出错时返回缓存数据
        if symbol in _cache:
            return symbol, _cache[symbol]
        return symbol, []

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Vercel Serverless Function for minute data"""
        global _cache, _cache_time
        
        final_data = {}
        updated_time = datetime.now().strftime('%H:%M:%S')
        
        # 检查缓存是否有效
        current_time = time.time()
        use_cache = False
        
        if _cache_time and (current_time - _cache_time.get('last_update', 0)) < CACHE_DURATION:
            # 使用缓存
            final_data = _cache.copy()
            use_cache = True
        else:
            # 获取新数据
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = {
                    executor.submit(fetch_index_data, symbol, config): symbol 
                    for symbol, config in INDICES_CONFIG.items()
                }
                
                for future in concurrent.futures.as_completed(futures, timeout=5):
                    try:
                        symbol, points = future.result()
                        if points:
                            final_data[symbol] = points
                    except Exception as e:
                        print(f"Future error: {str(e)}")
                        continue
            
            # 更新缓存
            if final_data:
                _cache = final_data.copy()
                _cache_time['last_update'] = current_time
        
        response = {
            'ok': True,
            'data': final_data,
            'updated': updated_time,
            'count': len(final_data),
            'cached': use_cache
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
