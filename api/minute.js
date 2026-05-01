const https = require('https');
const http = require('http');

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

function fetchFromEastmoney(secid) {
    return new Promise((resolve) => {
        const url = `https://push2.eastmoney.com/api/qt/stock/trends2/get?secid=${secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58`;
        
        https.get(url, { timeout: 3000 }, (res) => {
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

module.exports = async (req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    
    const finalData = {};
    const updatedTime = new Date().toLocaleTimeString('zh-CN');
    
    try {
        // 并发获取所有指数
        const promises = Object.entries(INDICES_CONFIG).map(async ([symbol, config]) => {
            const resp = await fetchFromEastmoney(config.secid);
            
            if (resp && resp.data && resp.data.trends && resp.data.trends.length > 0) {
                const preClose = parseFloat(resp.data.preClose || 0);
                if (preClose > 0) {
                    const points = [];
                    for (const trend of resp.data.trends) {
                        try {
                            const parts = trend.split(',');
                            if (parts.length >= 3) {
                                const timeStr = parts[0].includes(' ') ? parts[0].split(' ')[1].substring(0, 5) : parts[0].substring(0, 5);
                                const price = parseFloat(parts[2]);
                                const pct = parseFloat(((price / preClose - 1) * 100).toFixed(2));
                                points.push({ time: timeStr, pct });
                            }
                        } catch (e) {}
                    }
                    if (points.length > 0) {
                        finalData[symbol] = points;
                    }
                }
            }
        });
        
        await Promise.race([
            Promise.all(promises),
            new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout')), 5000))
        ]);
    } catch (e) {
        console.error('Error:', e.message);
    }
    
    res.status(200).json({
        ok: true,
        data: finalData,
        updated: updatedTime,
        count: Object.keys(finalData).length
    });
};
