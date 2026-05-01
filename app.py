#!/usr/bin/env python3
"""
A股主要指数数据API后端
支持: 沪深300, 上证50, 中证500, 中证1000, 中证2000
周期: 分时(1min), 5min, 30min, 日线
"""
import json, time, threading, re
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory
import requests

app = Flask(__name__, static_folder='.')

# ===================== 缓存 =====================
_cache = {}
_cache_lock = threading.Lock()

CACHE_TTL = {
    'minute': 60,    # 分时缓存60秒
    '5min':   120,   # 5分钟缓存2分钟
    '30min':  300,   # 30分钟缓存5分钟
    'daily':  300,   # 日线缓存5分钟
    'realtime': 30,  # 实时行情缓存30秒
}

def get_cache(key, ttl=300):
    with _cache_lock:
        item = _cache.get(key)
        if item and time.time() - item['ts'] < ttl:
            return item['data']
    return None

def set_cache(key, data):
    with _cache_lock:
        _cache[key] = {'data': data, 'ts': time.time()}

# ===================== 指数配置 =====================
INDICES = {
    'sh000300': '沪深300',
    'sh000016': '上证50',
    'sh000905': '中证500',
    'sh000852': '中证1000',
    'sh932000': '中证2000',
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://finance.sina.com.cn/',
}

# ===================== 分时数据（腾讯接口 + 东方财富备用）=====================
def fetch_minute_data(symbol):
    """获取今日分时数据，格式: [{time:'09:30', price:4810.3, pct:0.12}, ...]"""
    
    # 中证2000 (sh932000) 优先尝试东方财富接口，因为它在腾讯/新浪上可能不全
    if symbol == 'sh932000':
        try:
            # 东方财富分时接口 (secid: 1.932000)
            dfcf_url = "https://push2.eastmoney.com/api/qt/stock/trends2/get?secid=1.932000&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
            r = requests.get(dfcf_url, timeout=10)
            d = r.json()
            trends = d.get('data', {}).get('trends', [])
            if trends:
                result = []
                for t in trends:
                    parts = t.split(',')
                    # f51: time (YYYY-MM-DD HH:MM), f52: open, f53: close, f54: high, f55: low
                    time_str = parts[0].split(' ')[1]
                    price = float(parts[2]) # 使用当前价格
                    result.append({'time': time_str, 'price': price})
                return result
        except Exception as e:
            print(f'DFCF error {symbol}: {e}')

    url = f'https://web.ifzq.gtimg.cn/appstock/app/minute/query?code={symbol}'
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        d = r.json()
        arr = d['data'][symbol]['data']['data']
        if not arr or len(arr) <= 1:
            return None

        # 格式: "HHMM price cumvol amount"
        result = []
        for item in arr:
            parts = item.strip().split()
            if len(parts) < 2:
                continue
            t = parts[0]
            if len(t) == 4:
                t = t[:2] + ':' + t[2:]
            try:
                price = float(parts[1])
                result.append({'time': t, 'price': price})
            except:
                pass
        return result if len(result) > 1 else None
    except Exception as e:
        print(f'Minute error {symbol}: {e}')
        return None

# ===================== K线数据（新浪接口 + 东方财富备用）=====================
def fetch_kline(symbol, scale, datalen):
    """
    scale: 5=5分钟, 30=30分钟, 240=日线
    """
    # 中证2000 (sh932000) 优先尝试东方财富接口
    if symbol == 'sh932000':
        try:
            # 东方财富K线接口 (secid: 1.932000, klt: 101=日线, 5=5分, 30=30分)
            klt_map = {5: 5, 30: 30, 240: 101}
            klt = klt_map.get(scale, 101)
            dfcf_url = f"https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.932000&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58&klt={klt}&fqt=1&lmt={datalen}"
            r = requests.get(dfcf_url, timeout=10)
            d = r.json()
            klines = d.get('data', {}).get('klines', [])
            if klines:
                result = []
                for k in klines:
                    parts = k.split(',')
                    # f51: time, f52: open, f53: close, f54: high, f55: low
                    result.append({
                        'time': parts[0],
                        'open': float(parts[1]),
                        'close': float(parts[2]),
                        'high': float(parts[3]),
                        'low': float(parts[4]),
                    })
                return result
        except Exception as e:
            print(f'DFCF Kline error {symbol}: {e}')

    url = f'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={symbol}&scale={scale}&ma=no&datalen={datalen}'
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            result = []
            for item in data:
                result.append({
                    'time': item['day'],
                    'open': float(item['open']),
                    'high': float(item['high']),
                    'low': float(item['low']),
                    'close': float(item['close']),
                })
            return result
    except Exception as e:
        print(f'Kline error {symbol} scale={scale}: {e}')
    return None

# ===================== 实时行情（新浪）=====================
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
                try:
                    result[code] = {
                        'name': parts[0],
                        'open': float(parts[1]) if parts[1] else None,
                        'prevClose': float(parts[2]) if parts[2] else None,
                        'current': float(parts[3]) if parts[3] else None,
                        'high': float(parts[4]) if parts[4] else None,
                        'low': float(parts[5]) if parts[5] else None,
                    }
                except:
                    pass
    except Exception as e:
        print(f'Realtime error: {e}')
    return result

# ===================== Yahoo Finance（中证2000备用）=====================
def fetch_yahoo(yahoo_symbol, range_str='1y'):
    try:
        import sys
        sys.path.append('/opt/.manus/.sandbox-runtime')
        from data_api import ApiClient
        client = ApiClient()
        response = client.call_api('YahooFinance/get_stock_chart', query={
            'symbol': yahoo_symbol, 'region': 'CN', 'interval': '1d', 'range': range_str,
        })
        result = response.get('chart', {}).get('result', [{}])[0]
        timestamps = result.get('timestamp', [])
        closes = result.get('indicators', {}).get('quote', [{}])[0].get('close', [])
        data = []
        for ts, c in zip(timestamps, closes):
            if c is None: continue
            d = datetime.fromtimestamp(ts)
            data.append({'time': d.strftime('%Y-%m-%d'), 'close': round(c, 3)})
        return data
    except Exception as e:
        print(f'Yahoo error: {e}')
    return None

# ===================== 计算涨跌幅 =====================
def calc_pct(data, prev_close=None):
    """将价格序列转换为相对涨跌幅（以第一个点为基准）"""
    if not data:
        return []
    base = prev_close if prev_close else data[0].get('price') or data[0].get('close')
    if not base:
        return data
    result = []
    for item in data:
        price = item.get('price') or item.get('close')
        if price is None:
            result.append({**item, 'pct': None})
        else:
            result.append({**item, 'pct': round((price / base - 1) * 100, 3)})
    return result

# ===================== API 路由 =====================

@app.route('/api/minute')
def api_minute():
    """获取所有指数今日分时数据（涨跌幅）"""
    cached = get_cache('minute_all', CACHE_TTL['minute'])
    if cached:
        return jsonify({'ok': True, 'data': cached, 'cached': True})

    # 先获取实时行情（用于获取昨收价作为基准）
    rt = fetch_realtime(list(INDICES.keys()))

    result = {}
    for symbol in INDICES.keys():
        data = fetch_minute_data(symbol)
        if data:
            prev_close = rt.get(symbol, {}).get('prevClose') if rt else None
            result[symbol] = calc_pct(data, prev_close)

    set_cache('minute_all', result)
    return jsonify({
        'ok': True,
        'data': result,
        'realtime': rt,
        'updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    })


@app.route('/api/kline')
def api_kline():
    """获取K线数据: period=5min|30min|daily, days=天数"""
    period = request.args.get('period', 'daily')
    days = int(request.args.get('days', 60))

    scale_map = {'5min': 5, '30min': 30, 'daily': 240}
    scale = scale_map.get(period, 240)

    # 数据量估算
    if period == '5min':
        datalen = min(days * 48 + 50, 2000)   # 每天约48根5分钟K线
    elif period == '30min':
        datalen = min(days * 8 + 20, 2000)    # 每天约8根30分钟K线
    else:
        datalen = max(days + 20, 300)

    cache_key = f'kline_{period}_{days}'
    cached = get_cache(cache_key, CACHE_TTL.get(period, 300))
    if cached:
        return jsonify({'ok': True, 'data': cached, 'cached': True})

    # 获取实时行情
    rt = fetch_realtime(list(INDICES.keys()))

    result = {}
    for symbol in INDICES.keys():
        # 中证2000日线用Yahoo Finance
        if symbol == 'sh932000' and period == 'daily':
            range_map = {10:'1mo', 60:'3mo', 120:'6mo', 250:'1y', 500:'2y', 1250:'5y', 0:'max'}
            data = fetch_yahoo('932000.SS', range_map.get(days, '1y'))
            if data:
                # 转换格式并计算涨跌幅
                prev_close = rt.get(symbol, {}).get('prevClose') if rt else None
                result[symbol] = calc_pct(
                    [{'time': d['time'], 'price': d['close']} for d in data],
                    prev_close
                )
            continue

        data = fetch_kline(symbol, scale, datalen)
        if data:
            # 截取天数
            if period == 'daily' and days > 0 and len(data) > days:
                data = data[-days:]
            elif period == '5min' and days > 0:
                # 只保留最近N天的数据
                pass
            elif period == '30min' and days > 0:
                pass

            prev_close = rt.get(symbol, {}).get('prevClose') if rt else None
            result[symbol] = calc_pct(
                [{'time': d['time'], 'price': d['close']} for d in data],
                prev_close
            )

    set_cache(cache_key, result)
    return jsonify({
        'ok': True,
        'data': result,
        'realtime': rt,
        'updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    })


@app.route('/api/realtime')
def api_realtime():
    cached = get_cache('realtime', CACHE_TTL['realtime'])
    if cached:
        return jsonify({'ok': True, 'data': cached})
    data = fetch_realtime(list(INDICES.keys()))
    if data:
        set_cache('realtime', data)
    return jsonify({'ok': True, 'data': data})


@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'time': datetime.now().isoformat()})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8888, debug=False)
