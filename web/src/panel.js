/**
 * panel.js — 통계 패널 테이블 렌더링
 * stats.json의 수치만 사용. null → "데이터 준비 중"
 */

const NULL_TEXT = '<span class="null-val">준비 중</span>'

function fmt(v, unit = '', digits = 1) {
  if (v === null || v === undefined) return NULL_TEXT
  const n = typeof v === 'number' ? v.toLocaleString('ko-KR', { maximumFractionDigits: digits }) : v
  return `<b>${n}</b>${unit ? ' ' + unit : ''}`
}

function pctBar(v) {
  if (v === null || v === undefined) return NULL_TEXT
  const p = Math.min(Math.max(+v, 0), 100)
  return `<span style="display:inline-flex;align-items:center;gap:6px">
    <span style="display:inline-block;width:${p.toFixed(0)}px;max-width:100px;height:8px;background:var(--c-pangyo);border-radius:2px;min-width:2px"></span>
    <b>${p.toFixed(1)}%</b>
  </span>`
}

function highlight(pg, cr, higherIsBetter = true) {
  if (pg === null || cr === null || pg === undefined || cr === undefined) return ['', '']
  const pgBetter = higherIsBetter ? pg >= cr : pg <= cr
  return pgBetter ? ['better', ''] : ['', 'better']
}

function row(label, pgVal, crVal, unit = '', digits = 1, higherIsBetter = true) {
  const [pgCls, crCls] = highlight(pgVal, crVal, higherIsBetter)
  return `<tr>
    <td>${label}</td>
    <td class="${pgCls}">${fmt(pgVal, unit, digits)}</td>
    <td class="${crCls}">${fmt(crVal, unit, digits)}</td>
  </tr>`
}

export function renderPanel(stats) {
  const pg = stats.regions.pangyo
  const cr = stats.regions.cheongna

  // ── 토지이용 탭 ─────────────────────────────────────────────────
  const luRows = [
    row('구역 면적', pg.area_ha, cr.area_ha, 'ha', 1),
    row('업무 용도 비율', pg.landuse_zone_pct?.['업무'], cr.landuse_zone_pct?.['업무'], '%', 1),
    row('상업 용도 비율', pg.landuse_zone_pct?.['상업'], cr.landuse_zone_pct?.['상업'], '%', 1),
    row('주거 용도 비율', pg.landuse_zone_pct?.['주거'], cr.landuse_zone_pct?.['주거'], '%', 1, false),
    row('토지이용 혼합도 (LUM)', pg.lum_entropy, cr.lum_entropy, '', 4),
    row('평균 용적률', pg.mean_far, cr.mean_far, '%', 1),
    row('평균 건폐율', pg.mean_bcr, cr.mean_bcr, '%', 1),
    row('공필지율', pg.vacant_parcel_pct, cr.vacant_parcel_pct, '%', 1, false),
  ]
  document.querySelector('#landuse-table tbody').innerHTML = luRows.join('')

  // ── 교통망 탭 ───────────────────────────────────────────────────
  const trRows = [
    row('도로망 밀도', pg.road_density_km_per_km2, cr.road_density_km_per_km2, 'km/km²', 2),
    row('버스정류장 밀도', pg.bus_density_per_km2, cr.bus_density_per_km2, '/km²', 2),
    row('도보 500m 역세권 인구 비율', pg.station_catchment_pct?.['500m'], cr.station_catchment_pct?.['500m'], '%', 1),
    row('도보 1km 역세권 인구 비율', pg.station_catchment_pct?.['1km'], cr.station_catchment_pct?.['1km'], '%', 1),
    row('30분권 유입 종사자', pg.isochrone?.['30']?.workers, cr.isochrone?.['30']?.workers, '명', 0),
    row('60분권 유입 종사자', pg.isochrone?.['60']?.workers, cr.isochrone?.['60']?.workers, '명', 0),
    row('30분권 유입 인구', pg.isochrone?.['30']?.pop, cr.isochrone?.['30']?.pop, '명', 0),
  ]
  document.querySelector('#transport-table tbody').innerHTML = trRows.join('')

  // ── 인구·사업체 탭 ───────────────────────────────────────────────
  const popRows = [
    row('구역 내 인구', pg.population, cr.population, '명', 0),
    row('구역 내 가구', pg.households, cr.households, '세대', 0),
    row('구역 내 종사자', pg.workers, cr.workers, '명', 0),
    row('구역 내 사업체', pg.businesses, cr.businesses, '개', 0),
    row('직주비 (종사자/인구)', pg.jobs_housing_ratio, cr.jobs_housing_ratio, '', 3),
  ]
  document.querySelector('#population-table tbody').innerHTML = popRows.join('')
}
