const https = require('https');
const fs = require('fs');
const path = require('path');

const INDICES_CONFIG = {
    'sh000001': { name: '上证指数', secid: '1.000001' },
    'sh000016': { name: '上证50', secid: '1.000016' },
    'sh000300': { name: '沪深300', secid: '1.000300' },
    'sh000905': { name: '中证500', secid: '1.000905' },
    'sh000852': { name: '中证1000', secid: '1.000852' },
    'sh932000': { name: '中证2000', secid: '1.932000' },
    'sh000680': { name: '科创综指', secid: '1.000680' },
    'sh000688': { name: '科创50', secid: '1.000688' },
    'sz399006': { name: '创业板指', secid: '0.399006' }
};

// 使用内存缓存（在 Vercel 中，每个请求是独立的，所以这个缓存只在单个请求内有效）
let cachedData = null;
let cacheTime = 0;

function fetchFromEastmoney(secid) {
    return new Promise((resolve) => {
        const url = `https://push2.eastmoney.com/api/qt/stock/get?secid=${secid}&ut=fa44cfb3f7e6c18e&fltt=2&fields=f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65,f66,f67,f68,f69,f70,f71,f72`;
        
        https.get(url, { timeout: 2000 }, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                try {
                    const json = JSON.parse(data);
                    resolve(json);
                } catch (e) {
                    resolve(null);
                }
            });
        }).on('error', () => resolve(null)).on('timeout', function() { this.destroy(); });
    });
}

function parseMinuteData(json) {
    if (!json || !json.data) return null;
    
    const data = json.data;
    const preClose = parseFloat(data.f60 || 0);
    
    if (preClose <= 0 || !data.f161) return null;
    
    try {
        // f161 是分时数据，格式：时间,价格,成交量;时间,价格,成交量;...
        const points = [];
        const items = data.f161.split(';');
        
        for (const item of items) {
            const parts = item.split(',');
            if (parts.length >= 2) {
                const time = parts[0];
                const price = parseFloat(parts[1]);
                const pct = parseFloat(((price / preClose - 1) * 100).toFixed(2));
                points.push({ time, pct });
            }
        }
        
        return points.length > 0 ? points : null;
    } catch (e) {
        return null;
    }
}

module.exports = async (req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    
    const finalData = {};
    const now = new Date();
    const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;
    
    try {
        const promises = Object.entries(INDICES_CONFIG).map(async ([symbol, config]) => {
            const resp = await fetchFromEastmoney(config.secid);
            const points = parseMinuteData(resp);
            
            if (points && points.length > 0) {
                finalData[symbol] = points;
            }
        });
        
        await Promise.race([
            Promise.all(promises),
            new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout')), 4000))
        ]);
    } catch (e) {
        console.error('Error:', e.message);
    }
    
    res.status(200).json({
        ok: true,
        data: finalData,
        updated: timeStr,
        count: Object.keys(finalData).length
    });
};
