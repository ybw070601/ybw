// ==================== 全局变量 & 颜色映射 ====================
let latestData = null, historyData = null, compareData = null, charts = {};
let baiduOriginalOrder = [];

let xunyiHistoryData = null, xunyiChart = null, xunyiLatestData = [];
let xunyiOriginalOrder = [];

let baiduIndexData = [];
let baiduIndexOriginalOrder = [];
let yangBaiduHistoryData = [];
let yangBaiduChart = null;

let globalLastUpdateTimeStr = '';

const colorMap = {
    "张桂源": "#F9E511",
    "张函瑞": "#779649",
    "王橹杰": "#4ab7cc",
    "左奇函": "#10319f",
    "左齐函": "#10319f",
    "陈奕恒": "#9b59b6",
    "杨博文": "#F4A9AA",
    "陈浚铭": "#E60012"
};
function getColorForName(n) { return colorMap[n] || `hsl(${Math.abs(n.length * 37) % 360}, 70%, 55%)`; }
function getLightBgColor(n) {
    let h = getColorForName(n);
    if (h.startsWith('#')) {
        let r = parseInt(h.slice(1,3), 16);
        let g = parseInt(h.slice(3,5), 16);
        let b = parseInt(h.slice(5,7), 16);
        return `rgba(${r}, ${g}, ${b}, 0.4)`;
    }
    return h + '66';
}

// 水印
(function() {
    let wt = "YBW-裱你咋滴";
    let c = document.createElement('canvas');
    c.width = 300;
    c.height = 180;
    let ctx = c.getContext('2d');
    ctx.font = "bold 28px 'Segoe UI', 'Microsoft YaHei'";
    ctx.fillStyle = "rgba(100,100,100,0.5)";
    ctx.translate(40, 120);
    ctx.rotate(-Math.PI / 9);
    ctx.fillText(wt, 0, 0);
    let wd = document.getElementById('watermark');
    wd.style.backgroundImage = `url(${c.toDataURL()})`;
    wd.style.backgroundRepeat = 'repeat';
    wd.style.backgroundSize = '320px 200px';
})();

function getNextUpdateTimeFromLast(lastTimeStr) {
    let lastDate = new Date(lastTimeStr.replace(' ', 'T') + '+08:00');
    let minutes = lastDate.getMinutes();
    let remainder = minutes % 10;
    let nextMinutes = minutes + (10 - remainder);
    let next = new Date(lastDate);
    next.setMinutes(nextMinutes, 0, 0);
    return next.toLocaleString('zh-CN', { hour12: false, timeZone: 'Asia/Shanghai' });
}
function updateGlobalTimeDisplay() {
    if (globalLastUpdateTimeStr) {
        document.getElementById('updateTime').innerHTML = `📅 最后更新: ${globalLastUpdateTimeStr}`;
        document.getElementById('nextUpdate').innerHTML = `⏰ 预计下次更新: ${getNextUpdateTimeFromLast(globalLastUpdateTimeStr)}`;
    } else {
        document.getElementById('updateTime').innerHTML = `📅 最后更新: 等待数据...`;
        document.getElementById('nextUpdate').innerHTML = `⏰ 预计下次更新: 计算中...`;
    }
}

// ==================== 自定义排序顺序 ====================
const CUSTOM_ORDER = ["张桂源", "张函瑞", "王橹杰", "左奇函", "陈奕恒", "杨博文", "陈浚铭"];
function sortByCustomOrder(arr, nameKey = 'name') {
    return arr.sort((a, b) => {
        let idxA = CUSTOM_ORDER.indexOf(a[nameKey]);
        let idxB = CUSTOM_ORDER.indexOf(b[nameKey]);
        if (idxA === -1) idxA = CUSTOM_ORDER.length;
        if (idxB === -1) idxB = CUSTOM_ORDER.length;
        return idxA - idxB;
    });
}

// ==================== 百度送花模块 ====================
async function loadCompare() {
    try {
        let r = await fetch('compare_yangbowen.json?_=' + Date.now());
        if (!r.ok) throw new Error();
        compareData = await r.json();
        renderCompareTable();
    } catch(e) {
        document.getElementById('compareTable').innerHTML = '<p style="color:red;">暂无对比数据</p>';
    }
}
function renderCompareTable() {
    if (!compareData) return;
    let t = compareData.today, y = compareData.yesterday;
    let dg = t.today_gift - y.today_gift;
    let du = t.today_users - y.today_users;
    let da = t.avg - y.avg;
    document.getElementById('compareTable').innerHTML = `
        <table class="compare-table">
            <thead><tr><th>指标</th><th>今日(${compareData.update_time})</th><th>昨日(${y.timestamp})</th><th>差值</th></tr></thead>
            <tbody>
                <tr><td style="font-weight:bold">今日送花(朵)</td><td>${t.today_gift}</td><td>${y.today_gift}</td><td style="color:${dg>=0?'green':'red'}">${dg}</td></tr>
                <tr><td style="font-weight:bold">今日人数(人)</td><td>${t.today_users}</td><td>${y.today_users}</td><td style="color:${du>=0?'green':'red'}">${du}</td></tr>
                <tr><td style="font-weight:bold">人均(朵/人)</td><td>${t.avg.toFixed(2)}</td><td>${y.avg.toFixed(2)}</td><td style="color:${da>=0?'green':'red'}">${da.toFixed(2)}</td></tr>
            </tbody>
        </table>
    `;
}
async function loadHistory() {
    try {
        let r = await fetch('history.json?_=' + Date.now());
        if (!r.ok) throw new Error();
        historyData = await r.json();
    } catch(e) {
        historyData = { timestamps: [], series: {} };
    }
    renderAllCards();
}
function getChartDateFromTimestamps(timestamps) {
    if (!timestamps || timestamps.length === 0) return '';
    let lastTs = timestamps[timestamps.length-1];
    let datePart = lastTs.split(' ')[0];
    let parts = datePart.split('-');
    if (parts.length === 3) return `${parts[0]}年${parseInt(parts[1])}月${parseInt(parts[2])}日`;
    return datePart;
}
function createTooltipWithDiff(unit, isFloat = false) {
    return {
        mode: 'index',
        intersect: false,
        itemSort: (a, b) => b.parsed.y - a.parsed.y,
        callbacks: {
            label: function(context) {
                let dataset = context.dataset;
                let dataIndex = context.dataIndex;
                let value = context.parsed.y;
                let label = dataset.label || '';
                let diffText = '';
                if (dataIndex > 0) {
                    let prevValue = dataset.data[dataIndex-1];
                    let diff = value - prevValue;
                    let sign = diff >= 0 ? '+' : '';
                    let diffFormatted = isFloat ? diff.toFixed(2) : Math.round(diff);
                    diffText = ` (${sign}${diffFormatted} ${unit})`;
                }
                let valueFormatted = isFloat ? value.toFixed(2) : value;
                return `${label}: ${valueFormatted} ${unit}${diffText}`;
            }
        }
    };
}
function renderAllCards() {
    if (!historyData || !historyData.timestamps || historyData.timestamps.length === 0) {
        document.getElementById('cardsContainer').innerHTML = '<p>暂无历史数据</p>';
        return;
    }
    let ts = historyData.timestamps;
    let series = historyData.series;
    let names = Object.keys(series);
    let dateStr = getChartDateFromTimestamps(ts);
    let metrics = [
        { key: 'today_gift', title: '🏆 今日送花', unit: '朵', dataKey: 'today_gift', isFloat: false },
        { key: 'today_users', title: '👥 今日人数', unit: '人', dataKey: 'today_users', isFloat: false },
        { key: 'avg', title: '📊 人均送花', unit: '朵/人', dataKey: 'avg', isFloat: true },
        { key: 'total_gift', title: '🏆 累计送花', unit: '朵', dataKey: 'total_gift', isFloat: false }
    ];
    let container = document.getElementById('cardsContainer');
    container.innerHTML = '';
    metrics.forEach(metric => {
        let sorted = latestData ? [...latestData].sort((a,b) => b[metric.dataKey] - a[metric.dataKey]) : [];
        let datasets = [];
        names.forEach(name => {
            let points = series[name]?.[metric.key] || [];
            if (points.length) {
                datasets.push({
                    label: name,
                    data: points,
                    borderColor: getColorForName(name),
                    backgroundColor: 'transparent',
                    borderWidth: 2.5,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    tension: 0.2,
                    fill: false
                });
            }
        });
        let card = document.createElement('div');
        card.className = 'rank-card';
        card.innerHTML = `
            <div class="rank-left">
                <h3>${metric.title} 排名</h3>
                <ul class="rank-list" id="rank-list-${metric.key}"></ul>
            </div>
            <div class="rank-right">
                <div class="chart-header">📅 ${dateStr}</div>
                <div class="chart-container"><canvas id="chart-${metric.key}"></canvas></div>
            </div>
        `;
        container.appendChild(card);
        let rankUl = document.getElementById(`rank-list-${metric.key}`);
        if (rankUl && sorted.length) {
            rankUl.innerHTML = '';
            sorted.forEach((item, idx) => {
                let prev = idx > 0 ? sorted[idx-1][metric.dataKey] : null;
                let gap = idx === 0 ? '—' : `-${(prev - item[metric.dataKey]).toFixed(metric.isFloat ? 2 : 0)} ${metric.unit}`;
                let li = document.createElement('li');
                li.innerHTML = `
                    <div class="rank-number">${idx+1}</div>
                    <div class="rank-color" style="background-color:${getColorForName(item.name)}" title="${item.name}"></div>
                    <div class="rank-value">${item[metric.dataKey]} ${metric.unit}</div>
                    <div class="rank-gap">${gap}</div>
                `;
                rankUl.appendChild(li);
            });
        }
        let ctx = document.getElementById(`chart-${metric.key}`).getContext('2d');
        if (charts[metric.key]) charts[metric.key].destroy();
        charts[metric.key] = new Chart(ctx, {
            type: 'line',
            data: { labels: ts, datasets: datasets },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: { display: false },
                    tooltip: createTooltipWithDiff(metric.unit, metric.isFloat)
                },
                scales: {
                    y: { beginAtZero: true, title: { display: true, text: metric.unit } },
                    x: {
                        ticks: {
                            callback: function(val, index) {
                                let label = this.getLabelForValue(val);
                                if (!label) return '';
                                let parts = label.split(' ');
                                if (parts.length < 2) return '';
                                let time = parts[1];
                                let [hour, minute] = time.split(':');
                                if (minute === '00' && [0,4,8,12,16,20].includes(parseInt(hour))) {
                                    return `${hour}:00`;
                                }
                                return '';
                            },
                            autoSkip: true,
                            maxRotation: 45
                        },
                        title: { display: true, text: '时间' }
                    }
                }
            }
        });
    });
}
async function loadLatest() {
    try {
        let r = await fetch('data.json?_=' + Date.now());
        if (!r.ok) throw new Error();
        latestData = await r.json();
        // 按自定义顺序排序
        latestData = sortByCustomOrder(latestData, 'name');
        baiduOriginalOrder = latestData.map(item => item.name);
        let historyResp = await fetch('history.json?_=' + Date.now());
        if (historyResp.ok) {
            let hist = await historyResp.json();
            if (hist.timestamps && hist.timestamps.length) {
                globalLastUpdateTimeStr = hist.timestamps[hist.timestamps.length-1];
            } else {
                globalLastUpdateTimeStr = new Date().toLocaleString();
            }
        } else {
            globalLastUpdateTimeStr = new Date().toLocaleString();
        }
        updateGlobalTimeDisplay();
        updateBaiduTable();
        updateAllRankLists();
    } catch(e) {
        console.error(e);
        document.getElementById('baiduTableBody').innerHTML = '<tr><td colspan="5">暂无数据</td></tr>';
    }
}
function updateBaiduTable() {
    if (!latestData) return;
    let tb = document.getElementById('baiduTableBody');
    tb.innerHTML = '';
    latestData.forEach(item => {
        let bg = getLightBgColor(item.name), c = getColorForName(item.name);
        tb.innerHTML += `
            <tr style="background-color:${bg}">
                <td><div class="color-dot" style="background-color:${c}" title="${item.name}"></div></td>
                <td>${item.today_gift}</td>
                <td>${item.today_users}</td>
                <td>${item.avg.toFixed(2)}</td>
                <td>${item.total_gift}</td>
            </tr>
        `;
    });
}
function updateAllRankLists() {
    if (!latestData) return;
    let metrics = [
        { key: 'today_gift', dataKey: 'today_gift', unit: '朵', isFloat: false },
        { key: 'today_users', dataKey: 'today_users', unit: '人', isFloat: false },
        { key: 'avg', dataKey: 'avg', unit: '朵/人', isFloat: true },
        { key: 'total_gift', dataKey: 'total_gift', unit: '朵', isFloat: false }
    ];
    metrics.forEach(metric => {
        let sorted = [...latestData].sort((a,b) => b[metric.dataKey] - a[metric.dataKey]);
        let rankUl = document.getElementById(`rank-list-${metric.key}`);
        if (rankUl) {
            rankUl.innerHTML = '';
            sorted.forEach((item, idx) => {
                let prev = idx > 0 ? sorted[idx-1][metric.dataKey] : null;
                let gap = idx === 0 ? '—' : `-${(prev - item[metric.dataKey]).toFixed(metric.isFloat ? 2 : 0)} ${metric.unit}`;
                let li = document.createElement('li');
                li.innerHTML = `
                    <div class="rank-number">${idx+1}</div>
                    <div class="rank-color" style="background-color:${getColorForName(item.name)}" title="${item.name}"></div>
                    <div class="rank-value">${item[metric.dataKey]} ${metric.unit}</div>
                    <div class="rank-gap">${gap}</div>
                `;
                rankUl.appendChild(li);
            });
        }
    });
}
function setupBaiduTableSort() {
    let ths = document.querySelectorAll('#baiduDataTable th');
    ths.forEach(th => {
        th.addEventListener('click', () => {
            let key = th.getAttribute('data-sort');
            if (!key || !latestData) return;
            let sorted;
            if (key === 'name') {
                sorted = baiduOriginalOrder.map(name => latestData.find(item => item.name === name));
            } else {
                sorted = [...latestData].sort((a,b) => b[key] - a[key]);
            }
            let tb = document.getElementById('baiduTableBody');
            tb.innerHTML = '';
            sorted.forEach(item => {
                let bg = getLightBgColor(item.name), c = getColorForName(item.name);
                tb.innerHTML += `
                    <tr style="background-color:${bg}">
                        <td><div class="color-dot" style="background-color:${c}" title="${item.name}"></div></td>
                        <td>${item.today_gift}</td>
                        <td>${item.today_users}</td>
                        <td>${item.avg.toFixed(2)}</td>
                        <td>${item.total_gift}</td>
                    </tr>
                `;
            });
        });
    });
}

// ==================== 寻艺模块 ====================
async function loadXunyiHistory() {
    try {
        let r = await fetch('xunyi_history.json?_=' + Date.now());
        if (!r.ok) throw new Error();
        xunyiHistoryData = await r.json();
        renderXunyiChart();
        updateXunyiRankAndTable();
    } catch(e) {
        console.warn('寻艺历史加载失败', e);
        xunyiHistoryData = { timestamps: [], series: {} };
    }
}
function renderXunyiChart() {
    if (!xunyiHistoryData || !xunyiHistoryData.timestamps || xunyiHistoryData.timestamps.length === 0) return;
    let timestamps = xunyiHistoryData.timestamps;
    let series = xunyiHistoryData.series;
    let names = Object.keys(series);
    let datasets = [];
    names.forEach(name => {
        let points = series[name]?.total_points || [];
        if (points.length) {
            datasets.push({
                label: name,
                data: points,
                borderColor: getColorForName(name),
                backgroundColor: 'transparent',
                borderWidth: 2.5,
                pointRadius: 0,
                pointHoverRadius: 4,
                tension: 0.2,
                fill: false
            });
        }
    });
    let dateStr = getChartDateFromTimestamps(timestamps);
    let headerDiv = document.getElementById('xunyiChartDate');
    if (headerDiv) headerDiv.innerHTML = `📅 ${dateStr}`;
    let ctx = document.getElementById('xunyiTrendChart').getContext('2d');
    if (xunyiChart) xunyiChart.destroy();
    xunyiChart = new Chart(ctx, {
        type: 'line',
        data: { labels: timestamps, datasets: datasets },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { display: false },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    itemSort: (a,b) => b.parsed.y - a.parsed.y,
                    callbacks: {
                        label: function(context) {
                            let value = context.parsed.y;
                            let label = context.dataset.label || '';
                            let diffText = '';
                            let dataIndex = context.dataIndex;
                            if (dataIndex > 0) {
                                let prevValue = context.dataset.data[dataIndex-1];
                                let diff = value - prevValue;
                                let sign = diff >=0 ? '+' : '';
                                diffText = ` (${sign}${Math.round(diff)} 赞)`;
                            }
                            return `${label}: ${value} 赞${diffText}`;
                        }
                    }
                }
            },
            scales: {
                y: { beginAtZero: true, title: { display: true, text: '今日获赞总数' } },
                x: {
                    ticks: {
                        callback: function(val, index) {
                            let label = this.getLabelForValue(val);
                            if (!label) return '';
                            let parts = label.split(' ');
                            if (parts.length < 2) return '';
                            let time = parts[1];
                            let [hour, minute] = time.split(':');
                            if (minute === '00' && [0,4,8,12,16,20].includes(parseInt(hour))) {
                                return `${hour}:00`;
                            }
                            return '';
                        },
                        autoSkip: true,
                        maxRotation: 45
                    },
                    title: { display: true, text: '时间' }
                }
            }
        }
    });
}
async function loadXunyiLatest() {
    try {
        let r = await fetch('xunyi_history.json?_=' + Date.now());
        if (!r.ok) throw new Error();
        let full = await r.json();
        if (full.timestamps && full.timestamps.length) {
            let latestIdx = full.timestamps.length - 1;
            let series = full.series;
            let current = [];
            for (let name of Object.keys(series)) {
                let pt = series[name].total_points?.[latestIdx];
                let c1 = series[name].check1?.[latestIdx];
                let c2 = series[name].check2?.[latestIdx];
                let c3 = series[name].check3?.[latestIdx];
                if (pt !== undefined && c1 !== undefined && c2 !== undefined && c3 !== undefined) {
                    current.push({ name, total_points: pt, check1: c1, check2: c2, check3: c3 });
                }
            }
            // 按自定义顺序排序
            current = sortByCustomOrder(current, 'name');
            xunyiLatestData = current;
            xunyiOriginalOrder = current.map(item => item.name);
            updateXunyiRankAndTable();
            let yang = current.find(i => i.name === '杨博文');
            if (yang && full.timestamps.length > 1) {
                let yesterday = new Date();
                yesterday.setDate(yesterday.getDate() - 1);
                let yesterdayStr = yesterday.toISOString().slice(0,10);
                let yesterdayIdx = -1;
                for (let i=0; i<full.timestamps.length; i++) {
                    if (full.timestamps[i].startsWith(yesterdayStr)) {
                        yesterdayIdx = i;
                        break;
                    }
                }
                if (yesterdayIdx !== -1) {
                    let yesterdayTotal = full.series['杨博文']?.total_points?.[yesterdayIdx] || 0;
                    let diff = yang.total_points - yesterdayTotal;
                    let todayTime = full.timestamps[latestIdx];
                    let yesterdayTime = full.timestamps[yesterdayIdx];
                    document.getElementById('xunyiCompareTable').innerHTML = `
                        <table class="compare-table">
                            <thead><tr><th>指标</th><th>今日(${todayTime})</th><th>昨日(${yesterdayTime})</th><th>差值</th></tr></thead>
                            <tbody><tr><td style="font-weight:bold">获赞总数</td><td>${yang.total_points}</td><td>${yesterdayTotal}</td><td style="color:${diff>=0?'green':'red'}">${diff}</td></tr></tbody>
                        </table>
                    `;
                } else {
                    document.getElementById('xunyiCompareTable').innerHTML = '<p>暂无昨日同时段数据</p>';
                }
            } else {
                document.getElementById('xunyiCompareTable').innerHTML = '<p>暂无对比数据</p>';
            }
        }
    } catch(e) { console.error(e); }
}
function updateXunyiRankAndTable() {
    if (!xunyiLatestData.length) return;
    let sorted = [...xunyiLatestData].sort((a,b) => b.total_points - a.total_points);
    let rankList = document.getElementById('xunyiRankList');
    rankList.innerHTML = '';
    sorted.forEach((item, idx) => {
        let li = document.createElement('li');
        li.innerHTML = `<div class="rank-number">${idx+1}</div><div class="rank-color" style="background-color:${getColorForName(item.name)}" title="${item.name}"></div><div class="rank-value">${item.total_points} 赞</div>`;
        rankList.appendChild(li);
    });
    renderXunyiTable(xunyiLatestData);
}
function renderXunyiTable(data) {
    let tableBody = document.getElementById('xunyiTableBody');
    tableBody.innerHTML = '';
    data.forEach(item => {
        let bgColor = getLightBgColor(item.name);
        let colorCircle = getColorForName(item.name);
        let row = tableBody.insertRow();
        row.style.backgroundColor = bgColor;
        let cell0 = row.insertCell(0);
        cell0.innerHTML = `<div class="color-dot" style="background-color:${colorCircle}" title="${item.name}"></div>`;
        let cell1 = row.insertCell(1);
        cell1.textContent = item.total_points;
        let cell2 = row.insertCell(2);
        cell2.textContent = item.check3;
        let cell3 = row.insertCell(3);
        cell3.textContent = item.check2;
        let cell4 = row.insertCell(4);
        cell4.textContent = item.check1;
    });
}
function attachXunyiSortEvents() {
    let headers = document.querySelectorAll('#xunyiTableHeader th');
    headers.forEach(th => {
        th.removeEventListener('click', xunyiSortHandler);
        th.addEventListener('click', xunyiSortHandler);
    });
}
function xunyiSortHandler(e) {
    let th = e.target.closest('th');
    if (!th) return;
    let field = th.getAttribute('data-sort');
    if (!field) return;
    let sorted;
    if (field === '标识') {
        sorted = xunyiOriginalOrder.map(name => xunyiLatestData.find(item => item.name === name));
    } else {
        sorted = [...xunyiLatestData].sort((a,b) => b[field] - a[field]);
    }
    renderXunyiTable(sorted);
}

// ==================== 百度指数模块 ====================
async function loadBaiduIndex() {
    try {
        let resp = await fetch('baidu_index_today.json?_=' + Date.now());
        if (!resp.ok) throw new Error();
        let todayData = await resp.json();
        // 按自定义顺序排序
        todayData = sortByCustomOrder(todayData, 'name');
        baiduIndexData = todayData.map(item => ({ name: item.name, score: item.score }));
        baiduIndexOriginalOrder = baiduIndexData.map(item => item.name);
        renderBaiduIndexTable(baiduIndexData);
        let histResp = await fetch('baidu_index_yang_history.json?_=' + Date.now());
        if (histResp.ok) {
            yangBaiduHistoryData = await histResp.json();
            renderYangBaiduHistoryTable(yangBaiduHistoryData);
            renderYangBaiduChart(yangBaiduHistoryData);
        } else {
            console.warn('杨博文百度指数历史数据加载失败');
        }
    } catch(e) {
        console.error(e);
        document.getElementById('baiduIndexTableBody').innerHTML = '<tr><td colspan="2">暂无数据</td><tr>';
    }
}
function renderBaiduIndexTable(data) {
    let tbody = document.getElementById('baiduIndexTableBody');
    tbody.innerHTML = '';
    data.forEach(item => {
        let bgColor = getLightBgColor(item.name);
        let colorCircle = getColorForName(item.name);
        let row = tbody.insertRow();
        row.style.backgroundColor = bgColor;
        let cell0 = row.insertCell(0);
        cell0.innerHTML = `<div class="color-dot" style="background-color:${colorCircle}" title="${item.name}"></div>`;
        let cell1 = row.insertCell(1);
        cell1.textContent = item.score.toLocaleString();
    });
    attachBaiduIndexSortEvents();
}
function attachBaiduIndexSortEvents() {
    let headers = document.querySelectorAll('#baiduIndexTable th');
    headers.forEach(th => {
        th.removeEventListener('click', baiduIndexSortHandler);
        th.addEventListener('click', baiduIndexSortHandler);
    });
}
function baiduIndexSortHandler(e) {
    let th = e.target.closest('th');
    if (!th) return;
    let field = th.getAttribute('data-sort');
    if (!field) return;
    let sorted;
    if (field === '标识') {
        sorted = baiduIndexOriginalOrder.map(name => baiduIndexData.find(item => item.name === name));
    } else if (field === 'score') {
        sorted = [...baiduIndexData].sort((a,b) => b.score - a.score);
    } else {
        return;
    }
    renderBaiduIndexTable(sorted);
}
function renderYangBaiduHistoryTable(data) {
    let tbody = document.getElementById('yangBaiduHistoryBody');
    tbody.innerHTML = '';
    data.forEach(item => {
        let row = `<tr><td>${item.date}</td><td>${item.score.toLocaleString()}</td></tr>`;
        tbody.innerHTML += row;
    });
}
function renderYangBaiduChart(data) {
    if (!data || data.length === 0) return;
    let dates = data.map(item => item.date);
    let scores = data.map(item => item.score);
    let ctx = document.getElementById('yangBaiduIndexChart').getContext('2d');
    if (yangBaiduChart) yangBaiduChart.destroy();
    yangBaiduChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: dates,
            datasets: [{
                label: '百度指数',
                data: scores,
                borderColor: getColorForName('杨博文'),
                backgroundColor: 'transparent',
                borderWidth: 2.5,
                pointRadius: 0,
                pointHoverRadius: 4,
                tension: 0.2,
                fill: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false } },
            scales: {
                y: { beginAtZero: true, title: { display: true, text: '指数值' } },
                x: { ticks: { maxRotation: 45, autoSkip: true, maxTicksLimit: 15 } }
            }
        }
    });
}

// ==================== 选项卡切换 ====================
function initTabs() {
    document.querySelectorAll('.tab').forEach(t => {
        t.addEventListener('click', () => {
            let target = t.getAttribute('data-tab');
            document.querySelectorAll('.tab').forEach(tt => tt.classList.remove('active'));
            t.classList.add('active');
            document.getElementById('baidu-tab').classList.remove('active');
            document.getElementById('xunyi-tab').classList.remove('active');
            document.getElementById('baiduindex-tab').classList.remove('active');
            if (target === 'baidu') {
                document.getElementById('baidu-tab').classList.add('active');
                if (!latestData) loadLatest();
                if (!historyData) loadHistory();
            } else if (target === 'xunyi') {
                document.getElementById('xunyi-tab').classList.add('active');
                if (!xunyiHistoryData) loadXunyiHistory();
                else { updateXunyiRankAndTable(); }
                loadXunyiLatest();
            } else if (target === 'baiduindex') {
                document.getElementById('baiduindex-tab').classList.add('active');
                loadBaiduIndex();
            }
        });
    });
}

// ==================== 页面初始化 ====================
window.onload = async () => {
    await loadHistory();
    await loadLatest();
    await loadCompare();
    setupBaiduTableSort();
    setInterval(loadLatest, 60000);
    setInterval(loadCompare, 60000);
    setInterval(async () => { await loadHistory(); }, 600000);
    initTabs();
    await loadXunyiHistory();
    await loadXunyiLatest();
    attachXunyiSortEvents();
    loadBaiduIndex();
    setInterval(() => {
        if (document.getElementById('xunyi-tab').classList.contains('active')) {
            loadXunyiLatest();
        }
        if (document.getElementById('baiduindex-tab').classList.contains('active')) {
            loadBaiduIndex();
        }
    }, 60000);
};
