const fs = require('fs');
const path = require('path');

module.exports = async (req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    
    try {
        // 尝试读取本地的 minute_data.json 文件
        const dataPath = path.join(process.cwd(), 'minute_data.json');
        
        if (fs.existsSync(dataPath)) {
            const data = fs.readFileSync(dataPath, 'utf-8');
            const json = JSON.parse(data);
            res.status(200).json(json);
        } else {
            // 文件不存在，返回空数据
            res.status(200).json({
                ok: true,
                data: {},
                updated: new Date().toTimeString().slice(0, 8),
                count: 0,
                message: 'No data file found. Please run data_collector.py'
            });
        }
    } catch (error) {
        console.error('Error reading data:', error);
        res.status(200).json({
            ok: false,
            data: {},
            error: error.message
        });
    }
};
