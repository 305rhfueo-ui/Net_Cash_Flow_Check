document.addEventListener('DOMContentLoaded', () => {
    const btnHistory = document.getElementById('btn-history');
    const btnGraph = document.getElementById('btn-graph');
    const backBtns = document.querySelectorAll('.back-btn');

    const menuView = document.getElementById('menu-view');
    const historyView = document.getElementById('view-history');
    const graphView = document.getElementById('view-graph');

    let liquidityData = [];
    let chartInstance = null;

    // Load data
    fetch('data.json')
        .then(res => res.json())
        .then(data => {
            liquidityData = data.reverse(); // Newest first
            renderSignalPanel();
            populateTable();
        })
        .catch(err => {
            console.error('Failed to load data:', err);
            document.querySelector('#history-table tbody').innerHTML = '<tr><td colspan="9" style="text-align:center;">Failed to load data</td></tr>';
        });

    // Navigation logic
    btnHistory.addEventListener('click', () => {
        menuView.classList.add('hidden');
        historyView.classList.remove('hidden');
    });

    btnGraph.addEventListener('click', () => {
        menuView.classList.add('hidden');
        graphView.classList.remove('hidden');
        renderChart();
    });

    backBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            historyView.classList.add('hidden');
            graphView.classList.add('hidden');
            menuView.classList.remove('hidden');
        });
    });

    // Format numbers
    const formatNumber = (num) => {
        if (num === null || num === undefined) return '-';
        return Math.round(num).toLocaleString('en-US');
    };

    const formatPercent = (percent) => {
        if (percent === null || percent === undefined) return { text: '-', isNeg: false };
        const value = percent * 100;
        return {
            text: value.toFixed(1) + '%',
            isNeg: value < 0
        };
    };

    const toBillion = (num) => {
        if (num === null || num === undefined) return '-';
        const b = num / 1e9;
        return (b >= 0 ? '+' : '') + b.toFixed(0) + 'B';
    };

    const REGIME_LABEL = {
        'CONTRACTION': '유동성 축소',
        'NEUTRAL': '중립',
        'EXPANSION': '유동성 확장'
    };
    const REGIME_CLASS = {
        'CONTRACTION': 'regime-contraction',
        'NEUTRAL': 'regime-neutral',
        'EXPANSION': 'regime-expansion'
    };
    const REGIME_SHORT = {
        'CONTRACTION': { text: '축소', cls: 'rc-c' },
        'NEUTRAL': { text: '중립', cls: 'rc-n' },
        'EXPANSION': { text: '확장', cls: 'rc-e' }
    };

    // ── Signal Panel: 유동성 추세 판정 요약 ──────────────────
    const renderSignalPanel = () => {
        const panel = document.getElementById('signal-panel');
        if (!panel || liquidityData.length === 0) return;

        const latest = liquidityData[0]; // newest first
        if (!latest.Regime) return;

        const chg4w = latest.Chg4W !== null ? (latest.Chg4W * 100).toFixed(2) + '%' : '-';
        const chg4wCls = latest.Chg4W < 0 ? 'val-neg' : (latest.Chg4W > 0 ? 'val-pos' : 'val-flat');

        const z = latest.Chg4W_z !== null && latest.Chg4W_z !== undefined ? latest.Chg4W_z.toFixed(2) : '-';
        const zCls = latest.Chg4W_z < -1 ? 'val-neg' : (latest.Chg4W_z > 1 ? 'val-pos' : 'val-flat');

        const slopeB = latest.MA20Slope !== null ? toBillion(latest.MA20Slope) : '-';
        const slopeCls = latest.MA20Slope < 0 ? 'val-neg' : (latest.MA20Slope > 0 ? 'val-pos' : 'val-flat');

        const streak = latest.DownStreakW !== null && latest.DownStreakW !== undefined ? latest.DownStreakW : 0;
        const streakHtml = streak >= 1
            ? `주간 기준 <strong>${streak}주 연속 감소</strong>${streak >= 3 ? ' — 추세 하락 지속' : ''}`
            : '이번 주 감소 없음';

        const noiseHtml = latest.NoiseFlag
            ? `<div class="noise-note">⚠ 세금·분기말 구간 — 단기 변동 해석 주의</div>`
            : '';

        panel.innerHTML = `
            <div class="signal-top">
                <div class="regime-badge ${REGIME_CLASS[latest.Regime]}">${REGIME_LABEL[latest.Regime]}</div>
                <div class="signal-streak">${streakHtml}</div>
                ${noiseHtml}
            </div>
            <div class="signal-metrics">
                <div class="metric">
                    <div class="label">4주 변화율</div>
                    <div class="value ${chg4wCls}">${chg4w}</div>
                </div>
                <div class="metric">
                    <div class="label">MA20 기울기 (1개월)</div>
                    <div class="value ${slopeCls}">${slopeB}</div>
                </div>
                <div class="metric">
                    <div class="label">4주 변화 z-score (1년)</div>
                    <div class="value ${zCls}">${z}</div>
                </div>
            </div>
            <div class="decomp-line">
                최근 1주 변화 요인:
                <span>연준자산 ${toBillion(latest.D5_Fed)}</span>
                <span>TGA ${toBillion(latest.D5_TGA)}</span>
                <span>역레포 ${toBillion(latest.D5_RRP)}</span>
            </div>
        `;
        panel.classList.remove('hidden');
    };

    // Populate Table
    const populateTable = () => {
        const tbody = document.querySelector('#history-table tbody');
        tbody.innerHTML = '';

        liquidityData.forEach(row => {
            const tr = document.createElement('tr');

            const yoy = formatPercent(row.YoY);
            const chg4w = formatPercent(row.Chg4W !== undefined ? row.Chg4W : row.MoM);
            const wow = formatPercent(row.WoW);

            // Set cell classes based on user requirement (Red back for negative, White back for positive/zero)
            const getPctClass = (valObj) => {
                if (valObj.text === '-') return '';
                return valObj.isNeg ? 'cell-negative' : 'cell-positive';
            };

            const regime = row.Regime ? REGIME_SHORT[row.Regime] : null;
            const noiseMark = row.NoiseFlag ? ' <span title="세금·분기말 구간">*</span>' : '';

            tr.innerHTML = `
                <td style="text-align:center">${row.Date}</td>
                <td>${formatNumber(row.WALCL)}</td>
                <td>${formatNumber(row.WDTGAL)}</td>
                <td>${formatNumber(row.RRPONTSYD)}</td>
                <td style="font-weight: bold; color: #60a5fa">${formatNumber(row.NetLiquidity)}</td>
                <td class="${getPctClass(wow)}" style="text-align:center">${wow.text}${noiseMark}</td>
                <td class="${getPctClass(chg4w)}" style="text-align:center">${chg4w.text}</td>
                <td class="${getPctClass(yoy)}" style="text-align:center">${yoy.text}</td>
                <td class="regime-cell ${regime ? regime.cls : ''}">${regime ? regime.text : '-'}</td>
            `;
            tbody.appendChild(tr);
        });
    };

    // Render Chart
    const renderChart = () => {
        if (chartInstance) {
            chartInstance.destroy(); // Destroy previous instance if returning to view
        }

        // Get past 1 year of data for graph (250 business days approx)
        // Data is reversed (newest first), so we slice and then reverse back for chronological order
        const graphData = liquidityData.slice(0, 250).reverse();

        const dates = graphData.map(d => d.Date.substring(5)); // Show MM-DD
        const daily = graphData.map(d => d.NetLiquidity);
        const ma5 = graphData.map(d => d.MA5);
        const ma20 = graphData.map(d => d.MA20);
        const ma60 = graphData.map(d => d.MA60);

        // 축소 레짐 구간을 배경으로 표시
        const regimeBg = {
            id: 'regimeBg',
            beforeDraw(chart) {
                const { ctx, chartArea, scales } = chart;
                if (!chartArea) return;
                ctx.save();
                ctx.fillStyle = 'rgba(239, 68, 68, 0.07)';
                let start = null;
                graphData.forEach((d, i) => {
                    const isC = d.Regime === 'CONTRACTION';
                    if (isC && start === null) start = i;
                    if ((!isC || i === graphData.length - 1) && start !== null) {
                        const endIdx = isC ? i : i - 1;
                        const x1 = scales.x.getPixelForValue(start);
                        const x2 = scales.x.getPixelForValue(endIdx);
                        ctx.fillRect(x1, chartArea.top, x2 - x1, chartArea.bottom - chartArea.top);
                        start = null;
                    }
                });
                ctx.restore();
            }
        };

        const ctx = document.getElementById('liquidityChart').getContext('2d');

        Chart.defaults.color = '#cbd5e1';
        Chart.defaults.font.family = "'Inter', sans-serif";

        chartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: dates,
                datasets: [
                    {
                        label: '순유동성',
                        data: daily,
                        borderColor: '#ffffff', // White
                        borderWidth: 2,
                        pointRadius: 0,
                        tension: 0.1
                    },
                    {
                        label: '5일 이평',
                        data: ma5,
                        borderColor: '#fbbf24', // Amber
                        borderWidth: 2,
                        pointRadius: 0,
                        tension: 0.4
                    },
                    {
                        label: '20일 이평',
                        data: ma20,
                        borderColor: '#ef4444', // Red
                        borderWidth: 2,
                        pointRadius: 0,
                        tension: 0.4
                    },
                    {
                        label: '60일 이평',
                        data: ma60,
                        borderColor: '#3b82f6', // Blue
                        borderWidth: 2,
                        pointRadius: 0,
                        tension: 0.4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            usePointStyle: true,
                            padding: 20,
                            font: {
                                size: 14
                            }
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.9)',
                        titleFont: { size: 14 },
                        bodyFont: { size: 13 },
                        padding: 12,
                        cornerRadius: 8,
                        displayColors: true
                    }
                },
                scales: {
                    x: {
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)'
                        },
                        ticks: {
                            maxTicksLimit: 12
                        }
                    },
                    y: {
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)'
                        },
                        ticks: {
                            callback: function (value) {
                                return (value / 1000000000).toFixed(0) + 'B'; // formatting as billions roughly for scale
                            }
                        }
                    }
                }
            },
            plugins: [regimeBg]
        });
    };
});
