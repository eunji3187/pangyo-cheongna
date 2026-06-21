import Chart from 'chart.js/auto'

const PALETTE = ['#3b82f6','#f59e0b','#10b981','#8b5cf6','#06b6d4','#22c55e','#ef4444','#94a3b8']

function nullSafe(v) {
  return (v === null || v === undefined) ? 0 : +v
}

function pctObject(obj) {
  if (!obj || Object.keys(obj).length === 0) return { labels: ['데이터 없음'], data: [1] }
  const entries = Object.entries(obj).filter(([, v]) => v !== null && v > 0)
  if (entries.length === 0) return { labels: ['데이터 없음'], data: [1] }
  return { labels: entries.map(([k]) => k), data: entries.map(([, v]) => +v) }
}

function donutChart(canvasId, title, obj) {
  const el = document.getElementById(canvasId)
  if (!el) return
  const { labels, data } = pctObject(obj)
  new Chart(el, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{ data, backgroundColor: PALETTE.slice(0, labels.length), borderWidth: 1 }],
    },
    options: {
      plugins: {
        legend: { position: 'bottom', labels: { font: { size: 11 }, boxWidth: 12 } },
        tooltip: {
          callbacks: {
            label: ctx => `${ctx.label}: ${ctx.parsed.toFixed(1)}%`,
          },
        },
      },
    },
  })
}

function isochroneLineChart(canvasId, pg_iso, cr_iso) {
  const el = document.getElementById(canvasId)
  if (!el) return
  const minutes = [10, 20, 30, 40, 50, 60]
  const pgData = minutes.map(t => nullSafe(pg_iso?.[String(t)]?.workers))
  const crData = minutes.map(t => nullSafe(cr_iso?.[String(t)]?.workers))
  new Chart(el, {
    type: 'line',
    data: {
      labels: minutes.map(t => t + '분'),
      datasets: [
        {
          label: '판교',
          data: pgData,
          borderColor: '#2563eb',
          backgroundColor: 'rgba(37,99,235,.1)',
          fill: true,
          tension: 0.3,
          pointRadius: 4,
        },
        {
          label: '청라',
          data: crData,
          borderColor: '#dc2626',
          backgroundColor: 'rgba(220,38,38,.08)',
          fill: true,
          tension: 0.3,
          pointRadius: 4,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { position: 'top' },
        tooltip: {
          callbacks: {
            label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y.toLocaleString('ko-KR')} 명`,
          },
        },
      },
      scales: {
        y: {
          beginAtZero: true,
          title: { display: true, text: '종사자 수 (명)' },
          ticks: { callback: v => v === 0 && '준비 중' || v.toLocaleString('ko-KR') },
        },
        x: { title: { display: true, text: '등시간권' } },
      },
    },
  })
}

export function initCharts(stats) {
  const pg = stats.regions.pangyo
  const cr = stats.regions.cheongna

  // 용도지역 도넛
  donutChart('chart-landuse-pangyo',  '판교 용도지역', pg.landuse_zone_pct)
  donutChart('chart-landuse-cheongna', '청라 용도지역', cr.landuse_zone_pct)

  // 등시간권 누적 접근성 곡선
  isochroneLineChart('chart-isochrone', pg.isochrone, cr.isochrone)

  // 산업별 종사자 (사업체 주용도 기반)
  donutChart('chart-industry-pangyo',  '판교 산업', pg.industry_mix_pct)
  donutChart('chart-industry-cheongna', '청라 산업', cr.industry_mix_pct)
}
