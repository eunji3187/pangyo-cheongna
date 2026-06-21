import './style.css'
import { initMaps } from './map.js'
import { initCharts } from './charts.js'
import { renderPanel } from './panel.js'

async function loadStats() {
  const resp = await fetch('./data/stats.json')
  if (!resp.ok) throw new Error('stats.json 로드 실패')
  return resp.json()
}

async function boot() {
  let stats
  try {
    stats = await loadStats()
  } catch (e) {
    document.getElementById('data-meta').textContent = '데이터 로드 오류: ' + e.message
    return
  }

  // 메타 배지
  const meta = stats.meta
  const cutoff = meta.network_cutoff ?? '-'
  const pop_yr = meta.pop_year ?? '-'
  document.getElementById('data-meta').textContent =
    `지하철 네트워크 기준일 ${cutoff} | 인구 ${pop_yr} | 토지이용 인천 ${meta.landuse_date_incheon ?? '-'}`

  // 데이터 출처 footer
  const sourceEl = document.getElementById('source-note')
  sourceEl.textContent =
    `출처: SGIS 집계구(${meta.sgis_boundary}) · AL_D154 토지이용계획정보 · ${meta.building_source} · ` +
    `OSM · 국토교통부 버스정류장 | 보행속도 ${meta.walk_speed_m_per_s} m/s, 최대반경 ${meta.walk_cap_m}m | ` +
    `면적 배분: ${meta.areal_method}`

  // 탭 전환
  document.querySelectorAll('.tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'))
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'))
      btn.classList.add('active')
      document.getElementById(btn.dataset.tab).classList.add('active')
    })
  })

  // 각 모듈 초기화
  initMaps(stats)
  renderPanel(stats)
  initCharts(stats)
}

boot()
