#!/usr/bin/env python3
"""
A股指数分时数据收集器
每 20 秒获取一次分时数据，保存到 JSON 文件
"""

import json
import time
import requests
from datetime import datetime
import os

# 指数配置
INDICES = {
    'sh000001': {'name': '上证指数', 'code': '000001'},
    'sh000016': {'name': '上证50', 'code': '000016'},
    'sh000300': {'name': '沪深300', 'code': '000300'},
    'sh000905': {'name': '中证500', 'code': '000905'},
    'sh000852': {'name': '中证1000', 'code': '000852'},
    'sh932000': {'name': '中证2000', 'code': '932000'},
    'sh000680': {'name': '科创综指', 'code': '000680'},
    'sh000688': {'name': '科创50', 'code': '000688'},
    'sz399006': {'name': '创业板指', 'code': '399006'}
}

# 输出文件路径
OUTPUT_FILE = 'minute_data.json'
DAILY_FILE = 'daily_data.json'

def is_market_open():
    """检查股市是否开盘"""
    now = datetime.now()
    hour = now.hour
    minute = now.minute
    weekday = now.weekday()
    
    # 周末不开盘
    if weekday >= 5:
        return False
    
    # 上午 9:30-11:30
    if hour == 9 and minute >= 30:
        return True
    if hour == 10:
        return True
    if hour == 11 and minute <= 30:
        return True
    
    # 下午 13:00-15:00
    if hour >= 13 and hour < 15:
        return True
    if hour == 15 and minute == 0:
        return True
    
    return False

def fetch_minute_data(code):
    """从东方财富获取分时数据"""
    try:
        # 确定 secid
        if code.startswith('9'):
            secid = f"1.{code}"
        elif code.startswith('3'):
            secid = f"0.{code}"
        else:
            secid = f"1.{code}"
        
        url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&ut=fa44cfb3f7e6c18e&fltt=2&fields=f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65,f66,f67,f68,f69,f70,f71,f72"
        
        response = requests.get(url, timeout=3)
        data = response.json()
        
        if data.get('data'):
            stock_data = data['data']
            pre_close = float(stock_data.get('f60', 0))
            
            if pre_close > 0 and stock_data.get('f161'):
                # 解析分时数据
                points = []
                items = stock_data['f161'].split(';')
                
                for item in items:
                    parts = item.split(',')
                    if len(parts) >= 2:
                        time_str = parts[0]
                        price = float(parts[1])
                        pct = round((price / pre_close - 1) * 100, 2)
                        points.append({'time': time_str, 'pct': pct})
                
                return points if points else None
    except Exception as e:
        print(f"Error fetching {code}: {e}")
    
    return None

def fetch_daily_data(code):
    """从东方财富获取日线数据"""
    try:
        # 确定 secid
        if code.startswith('9'):
            secid = f"1.{code}"
        elif code.startswith('3'):
            secid = f"0.{code}"
        else:
            secid = f"1.{code}"
        
        url = f"https://push2.eastmoney.com/api/qt/stock/klines/get?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&beg=0&end=20&lmt=0&fqt=0&ut=fa44cfb3f7e6c18e"
        
        response = requests.get(url, timeout=3)
        data = response.json()
        
        if data.get('data') and data['data'].get('klines'):
            pre_close = float(data['data'].get('preClose', 0))
            
            if pre_close > 0:
                points = []
                for kline in data['data']['klines']:
                    parts = kline.split(',')
                    if len(parts) >= 4:
                        date = parts[0]
                        close = float(parts[3])
                        pct = round((close / pre_close - 1) * 100, 2)
                        points.append({'date': date, 'pct': pct})
                
                return points if points else None
    except Exception as e:
        print(f"Error fetching daily {code}: {e}")
    
    return None

def save_data():
    """获取所有指数数据并保存"""
    minute_data = {}
    daily_data = {}
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 正在获取数据...")
    
    for symbol, config in INDICES.items():
        code = config['code']
        
        # 获取分时数据
        minute = fetch_minute_data(code)
        if minute:
            minute_data[symbol] = minute
            print(f"  ✓ {config['name']} 分时数据: {len(minute)} 条")
        
        # 获取日线数据
        daily = fetch_daily_data(code)
        if daily:
            daily_data[symbol] = daily
            print(f"  ✓ {config['name']} 日线数据: {len(daily)} 条")
        
        time.sleep(0.5)  # 避免请求过快
    
    # 保存分时数据
    if minute_data:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'ok': True,
                'data': minute_data,
                'updated': datetime.now().strftime('%H:%M:%S'),
                'count': len(minute_data)
            }, f, ensure_ascii=False, indent=2)
        print(f"\n✓ 分时数据已保存到 {OUTPUT_FILE}")
    
    # 保存日线数据
    if daily_data:
        with open(DAILY_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'ok': True,
                'data': daily_data,
                'updated': datetime.now().strftime('%H:%M:%S'),
                'count': len(daily_data)
            }, f, ensure_ascii=False, indent=2)
        print(f"✓ 日线数据已保存到 {DAILY_FILE}")

def main():
    """主程序"""
    print("=" * 50)
    print("A股指数分时数据收集器")
    print("=" * 50)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"输出文件: {OUTPUT_FILE}, {DAILY_FILE}")
    print("=" * 50)
    print()
    
    try:
        while True:
            if is_market_open():
                save_data()
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 市场未开盘，等待...")
            
            # 等待 20 秒
            time.sleep(20)
    
    except KeyboardInterrupt:
        print("\n\n程序已停止")

if __name__ == '__main__':
    main()
