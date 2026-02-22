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
            populateTable();
        })
        .catch(err => {
            console.error('Failed to load data:', err);
            document.querySelector('#history-table tbody').innerHTML = '<tr><td colspan="8" style="text-align:center;">Failed to load data</td></tr>';
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

    // Populate Table
    const populateTable = () => {
        const tbody = document.querySelector('#history-table tbody');
        tbody.innerHTML = '';

        liquidityData.forEach(row => {
            const tr = document.createElement('tr');

            const yoy = formatPercent(row.YoY);
            const mom = formatPercent(row.MoM);
            const wow = formatPercent(row.WoW);

            // Set cell classes based on user requirement (Red back for negative, White back for positive/zero)
            const getPctClass = (valObj) => {
                if (valObj.text === '-') return '';
                return valObj.isNeg ? 'cell-negative' : 'cell-positive';
            };

            tr.innerHTML = `
                <td style="text-align:center">${row.Date}</td>
                <td>${formatNumber(row.WALCL)}</td>
                <td>${formatNumber(row.WDTGAL)}</td>
                <td>${formatNumber(row.RRPONTSYD)}</td>
                <td style="font-weight: bold; color: #60a5fa">${formatNumber(row.NetLiquidity)}</td>
                <td class="${getPctClass(wow)}" style="text-align:center">${wow.text}</td>
                <td class="${getPctClass(mom)}" style="text-align:center">${mom.text}</td>
                <td class="${getPctClass(yoy)}" style="text-align:center">${yoy.text}</td>
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
            }
        });
    };
});
