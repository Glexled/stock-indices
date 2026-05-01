const https = require('https');

// 东方财富 API 指数代码映射
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

function fetchIndexData(symbol, config) {
    return new Promise((resolve) => {
        try {
            const secid = config.secid;
            const url = `https://push2.eastmoney.com/api/qt/stock/trends2/get?secid=${secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58&ut=fa44cfb3f7e6c18e`;
            
            const req = https.get(url, { timeout: 2000 }, (res) => {
                let data = '';
                res.on('data', chunk => data += chunk);
                res.on('end', () => {
                    try {
                        const json = JSON.parse(data);
                        if (json.data && json.data.trends && json.data.trends.length > 0) {
                            const trends = json.data.trends;
                            const preClose = parseFloat(json.data.preClose || 0);
                            
                            if (preClose > 0) {
                                const points = [];
                                for (const trendItem of trends) {
                                    try {
                                        const parts = trendItem.split(',');
                                        if (parts.length >= 3) {
                                            let timeStr = parts[0];
                                            if (timeStr.includes(' ')) {
                                                timeStr = timeStr.split(' ')[1].substring(0, 5);
                                            } else {
                                                timeStr = timeStr.substring(0, 5);
                                            }
                                            
                                            const price = parseFloat(parts[2]);
                                            const pct = parseFloat(((price / preClose - 1) * 100).toFixed(2));
                                            
                                            points.push({ time: timeStr, pct });
                                        }
                                    } catch (e) {
                                        // Skip invalid entries
                                    }
                                }
                                
                                if (points.length > 0) {
                                    resolve([symbol, points]);
                                    return;
                                }
                            }
                        }
                        resolve([symbol, []]);
                    } catch (e) {
                        console.error(`Error parsing ${symbol}:`, e.message);
                        resolve([symbol, []]);
                    }
                });
            });
            
            req.on('error', (e) => {
                console.error(`Error fetching ${symbol}:`, e.message);
                resolve([symbol, []]);
            });
            
            req.on('timeout', () => {
                req.destroy();
                resolve([symbol, []]);
            });
        } catch (e) {
            console.error(`Error in fetchIndexData ${symbol}:`, e.message);
            resolve([symbol, []]);
        }
    });
}

module.exports = async (req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
    
    if (req.method === 'OPTIONS') {
        res.status(200).end();
        return;
    }
    
    try {
        const finalData = {};
        const updatedTime = new Date().toLocaleTimeString('zh-CN', { 
            hour: '2-digit', 
            minute: '2-digit', 
            second: '2-digit' 
        });
        
        // 并发获取所有指数数据
        const promises = Object.entries(INDICES_CONFIG).map(([symbol, config]) => 
            fetchIndexData(symbol, config)
        );
        
        const results = await Promise.race([
            Promise.all(promises),
            new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout')), 5000))
        ]);
        
        for (const [symbol, points] of results) {
            if (points.length > 0) {
                finalData[symbol] = points;
            }
        }
        
        res.status(200).json({
            ok: true,
            data: finalData,
            updated: updatedTime,
            count: Object.keys(finalData).length
        });
    } catch (error) {
        console.error('API Error:', error.message);
        res.status(200).json({
            ok: true,
            data: {},
            updated: new Date().toLocaleTimeString('zh-CN'),
            count: 0,
            error: error.message
        });
    }
};
