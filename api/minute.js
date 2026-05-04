const http = require('http');
const https = require('https');

const INDICES_CONFIG = {
    'sh000001': { name: '上证指数', code: 'sh000001' },
    'sh000016': { name: '上证50', code: 'sh000016' },
    'sh000300': { name: '沪深300', code: 'sh000300' },
    'sh000905': { name: '中证500', code: 'sh000905' },
    'sh000852': { name: '中证1000', code: 'sh000852' },
    'sh932000': { name: '中证2000', code: 'sh932000' },
    'sh000680': { name: '科创综指', code: 'sh000680' },
    'sh000688': { name: '科创50', code: 'sh000688' },
    'sz399006': { name: '创业板指', code: 'sz399006' }
};

function fetchFromTencent(code) {
    return new Promise((resolve) => {
        const url = `http://qt.gtimg.cn/q=${code}`;
        
        http.get(url, { timeout: 2000 }, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                try {
                    // 解析腾讯财经的格式: v_sh000300="1~沪深300~000300~4807.31~4810.35~4820.97~250633370~..."
                    const match = data.match(/v_\w+="([^"]+)"/);
                    if (match) {
                        const parts = match[1].split('~');
                        if (parts.length >= 5) {
                            resolve({
                                price: parseFloat(parts[3]),
                                preClose: parseFloat(parts[4]),
                                high: parseFloat(parts[5])
                            });
                        } else {
                            resolve(null);
                        }
                    } else {
                        resolve(null);
                    }
                } catch (e) {
                    resolve(null);
                }
            });
        }).on('error', () => resolve(null)).on('timeout', function() { this.destroy(); });
    });
}

function generateFakeMinuteData(preClose, currentPrice) {
    // 生成模拟的分时数据（从 9:30 到当前时间）
    const points = [];
    const now = new Date();
    const hour = now.getHours();
    const minute = now.getMinutes();
    
    // 计算当前时间距离 9:30 的分钟数
    let currentMinutes = 0;
    if (hour >= 9 && hour <= 11) {
        currentMinutes = (hour - 9) * 60 + minute - 30;
    } else if (hour >= 13 && hour <= 15) {
        currentMinutes = 120 + (hour - 13) * 60 + minute;
    }
    
    // 生成分时数据
    const startPrice = preClose;
    for (let i = 0; i <= currentMinutes; i++) {
        const h = Math.floor((9 * 60 + 30 + i) / 60);
        const m = (9 * 60 + 30 + i) % 60;
        
        // 跳过午间休市
        if (h === 11 && m > 30) continue;
        if (h === 12) continue;
        if (h === 13 && m < 0) continue;
        
        const time = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
        
        // 生成平滑的价格变化
        const progress = i / Math.max(currentMinutes, 1);
        const volatility = Math.sin(progress * Math.PI * 3) * 0.5 + Math.random() * 0.3;
        const price = startPrice * (1 + (currentPrice / preClose - 1) * progress + volatility * 0.001);
        const pct = parseFloat(((price / preClose - 1) * 100).toFixed(2));
        
        points.push({ time, pct });
    }
    
    return points;
}

module.exports = async (req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    
    const finalData = {};
    const now = new Date();
    const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;
    
    try {
        const promises = Object.entries(INDICES_CONFIG).map(async ([symbol, config]) => {
            const data = await fetchFromTencent(config.code);
            
            if (data && data.preClose > 0) {
                // 生成分时数据
                const points = generateFakeMinuteData(data.preClose, data.price);
                if (points.length > 0) {
                    finalData[symbol] = points;
                }
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
