const https = require('https');

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
        const url = `https://push2.eastmoney.com/api/qt/stock/klines/get?secid=${secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&beg=0&end=20&lmt=0&fqt=0&ut=fa44cfb3f7e6c18e`;
        
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
    
    try {
        const promises = Object.entries(INDICES_CONFIG).map(async ([symbol, config]) => {
            const resp = await fetchFromEastmoney(config.secid);
            
            if (resp && resp.data && resp.data.klines && resp.data.klines.length > 0) {
                const preClose = parseFloat(resp.data.preClose || 0);
                if (preClose > 0) {
                    const points = [];
                    for (const kline of resp.data.klines) {
                        try {
                            const parts = kline.split(',');
                            if (parts.length >= 3) {
                                const date = parts[0];
                                const close = parseFloat(parts[3]);
                                const pct = parseFloat(((close / preClose - 1) * 100).toFixed(2));
                                points.push({ date, pct });
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
        count: Object.keys(finalData).length
    });
};
