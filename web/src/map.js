import Map from 'ol/Map'
import View from 'ol/View'
import TileLayer from 'ol/layer/Tile'
import VectorLayer from 'ol/layer/Vector'
import VectorSource from 'ol/source/Vector'
import OSM from 'ol/source/OSM'
import WMTS from 'ol/source/WMTS'
import WMTSTileGrid from 'ol/tilegrid/WMTS'
import GeoJSON from 'ol/format/GeoJSON'
import { fromLonLat } from 'ol/proj'
import { Style, Fill, Stroke } from 'ol/style'
import { getTopLeft, getWidth } from 'ol/extent'
import { get as getProjection } from 'ol/proj'
import { isochrone } from './isochrone.js'

const VWORLD_KEY = typeof __VWORLD_KEY__ !== 'undefined' ? __VWORLD_KEY__ : ''

// ── 색상 팔레트 ──────────────────────────────────────────────────
const LANDUSE_COLORS = {
  '업무':     '#3b82f6',
  '상업':     '#f59e0b',
  '주거':     '#10b981',
  '공업':     '#8b5cf6',
  '지구단위': '#06b6d4',
  '비지':     '#22c55e',
  '기타':     '#94a3b8',
}

const BUILDING_COLORS = {
  '업무시설': '#1d4ed8',
  '근린생활시설': '#d97706',
  '주거':     '#059669',
  '판매시설': '#7c3aed',
  '기타':     '#94a3b8',
}

// ── V-World WMTS 타일 소스 ────────────────────────────────────────
function vworldTileSource() {
  const projection = getProjection('EPSG:3857')
  const extent = projection.getExtent()
  const size = getWidth(extent) / 256
  const resolutions = []
  const matrixIds = []
  for (let z = 0; z < 21; z++) {
    resolutions[z] = size / Math.pow(2, z)
    matrixIds[z] = String(z)
  }
  const tileGrid = new WMTSTileGrid({
    origin: getTopLeft(extent),
    resolutions,
    matrixIds,
  })

  const baseUrl = VWORLD_KEY
    ? `https://api.vworld.kr/req/wmts/1.0.0/${VWORLD_KEY}/Base/{TileMatrix}/{TileRow}/{TileCol}.png`
    : `https://tile.openstreetmap.org/{z}/{y}/{x}.png`

  if (!VWORLD_KEY) {
    // fallback OSM
    return null
  }
  return new WMTS({
    url: `https://api.vworld.kr/req/wmts/1.0.0/${VWORLD_KEY}/Base/{TileMatrix}/{TileRow}/{TileCol}.png`,
    layer: 'Base',
    matrixSet: 'GoogleMapsCompatible',
    format: 'image/png',
    projection: 'EPSG:3857',
    tileGrid,
    style: 'default',
    crossOrigin: 'anonymous',
  })
}

function makeBaseLayer() {
  const src = vworldTileSource()
  if (src) return new TileLayer({ source: src })
  return new TileLayer({ source: new OSM() })
}

// ── GeoJSON 벡터 레이어 ────────────────────────────────────────────
function colorStyle(color, opacity = 0.55) {
  return new Style({
    fill: new Fill({ color: hexToRgba(color, opacity) }),
    stroke: new Stroke({ color: color, width: 1 }),
  })
}

function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

function landuseStyle(feature) {
  const cat = feature.get('category') || '기타'
  const color = LANDUSE_COLORS[cat] || LANDUSE_COLORS['기타']
  return colorStyle(color)
}

function buildingStyle(feature) {
  const use = feature.get('main_use') || ''
  const color = Object.entries(BUILDING_COLORS).find(([k]) => use.includes(k))?.[1] || BUILDING_COLORS['기타']
  return colorStyle(color, 0.65)
}

// ── 경계선 스타일 ─────────────────────────────────────────────────
function boundaryStyle() {
  return new Style({
    fill: new Fill({ color: 'rgba(0,0,0,0)' }),
    stroke: new Stroke({ color: '#1e293b', width: 2.5, lineDash: [6, 3] }),
  })
}

// ── 지도 초기화 ────────────────────────────────────────────────────
const CENTERS = {
  pangyo:   fromLonLat([127.1085, 37.3996]),
  cheongna: fromLonLat([126.6500, 37.5370]),
}

let maps = {}
let layerGroups = { pangyo: {}, cheongna: {} }
let currentLayer = 'landuse'
let isoMinutes = 30

export function initMaps(stats) {
  for (const region of ['pangyo', 'cheongna']) {
    const view = new View({
      center: CENTERS[region],
      zoom: 14,
      minZoom: 11,
      maxZoom: 19,
    })

    const baseLayer = makeBaseLayer()
    const map = new Map({
      target: `map-${region}`,
      layers: [baseLayer],
      view,
    })
    maps[region] = map

    // 경계
    loadBoundaryLayer(region, map)
    // 토지이용 레이어 (기본)
    loadLanduseLayer(region, map)
    // 건축물 레이어 (숨김)
    loadBuildingsLayer(region, map)
    // 등시간권 (숨김)
    isochrone.init(region, map, stats)

    // 클릭 인터랙션
    map.on('singleclick', evt => onMapClick(evt, map, region))
    map.on('pointermove', evt => onPointerMove(evt, map, region))
  }

  // 레이어 셀렉터
  document.getElementById('layer-select').addEventListener('change', e => {
    currentLayer = e.target.value
    const isoCtrl = document.getElementById('iso-controls')
    isoCtrl.classList.toggle('hidden', currentLayer !== 'isochrone')
    updateVisibility()
    updateLegend()
  })

  // 등시간권 슬라이더
  document.getElementById('iso-slider').addEventListener('input', e => {
    isoMinutes = parseInt(e.target.value)
    document.getElementById('iso-label').textContent = isoMinutes + '분'
    for (const region of ['pangyo', 'cheongna']) {
      isochrone.setTime(region, isoMinutes)
    }
  })

  updateLegend()
}

function loadBoundaryLayer(region, map) {
  fetch(`./data/boundary_${region}.geojson`)
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      if (!data) return
      const src = new VectorSource({ features: new GeoJSON().readFeatures(data, { featureProjection: 'EPSG:3857' }) })
      const layer = new VectorLayer({ source: src, style: boundaryStyle(), zIndex: 50 })
      map.addLayer(layer)
      layerGroups[region].boundary = layer
    })
    .catch(() => {})
}

function loadLanduseLayer(region, map) {
  fetch(`./data/landuse_${region}.geojson`)
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      if (!data) return
      const src = new VectorSource({ features: new GeoJSON().readFeatures(data, { featureProjection: 'EPSG:3857' }) })
      const layer = new VectorLayer({ source: src, style: landuseStyle, zIndex: 10 })
      map.addLayer(layer)
      layerGroups[region].landuse = layer
    })
    .catch(() => {})
}

function loadBuildingsLayer(region, map) {
  fetch(`./data/buildings_${region}.geojson`)
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      if (!data) return
      const src = new VectorSource({ features: new GeoJSON().readFeatures(data, { featureProjection: 'EPSG:3857' }) })
      const layer = new VectorLayer({ source: src, style: buildingStyle, zIndex: 10, visible: false })
      map.addLayer(layer)
      layerGroups[region].buildings = layer
    })
    .catch(() => {})
}

function updateVisibility() {
  for (const region of ['pangyo', 'cheongna']) {
    const g = layerGroups[region]
    if (g.landuse)   g.landuse.setVisible(currentLayer === 'landuse')
    if (g.buildings) g.buildings.setVisible(currentLayer === 'buildings')
    // isochrone은 자체 모듈(state)에서 관리
    if (currentLayer === 'isochrone') {
      isochrone.setTime(region, isoMinutes)
    } else {
      isochrone.hide(region)
    }
  }
}

function onMapClick(evt, map, region) {
  const features = map.getFeaturesAtPixel(evt.pixel)
  const el = document.getElementById(`info-${region}`)
  if (!features || features.length === 0) {
    el.classList.remove('visible')
    return
  }
  const f = features[0]
  const props = f.getProperties()
  let html = ''
  if (currentLayer === 'landuse') {
    html = `<b>${props.zone_name || '-'}</b><br>
            지번: ${props.jibun || '-'}<br>
            면적: ${props.area_m2 ? props.area_m2.toLocaleString() + ' m²' : '-'}`
  } else if (currentLayer === 'buildings') {
    html = `<b>${props.main_use || '-'}</b><br>
            연면적: ${props.total_area ? Math.round(props.total_area).toLocaleString() + ' m²' : '-'}<br>
            용적률: ${props.mean_far ?? '-'}%`
  }
  if (html) {
    el.innerHTML = html
    el.classList.add('visible')
  }
}

function onPointerMove(evt, map, region) {
  if (evt.dragging) return
  const hit = map.hasFeatureAtPixel(evt.pixel)
  map.getTargetElement().style.cursor = hit ? 'pointer' : ''
}

// ── 범례 ──────────────────────────────────────────────────────────
function updateLegend() {
  const el = document.getElementById('map-legend')
  const palette = currentLayer === 'buildings' ? BUILDING_COLORS : LANDUSE_COLORS
  el.innerHTML = Object.entries(palette)
    .map(([k, v]) => `<div class="legend-item"><div class="legend-swatch" style="background:${v}"></div><span>${k}</span></div>`)
    .join('')
}
