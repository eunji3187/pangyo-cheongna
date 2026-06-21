import VectorLayer from 'ol/layer/Vector'
import VectorSource from 'ol/source/Vector'
import GeoJSON from 'ol/format/GeoJSON'
import { Style, Fill, Stroke } from 'ol/style'

const ISO_COLORS = ['#bfdbfe','#93c5fd','#60a5fa','#3b82f6','#2563eb','#1d4ed8']

function isoStyle(t) {
  const idx = Math.min(Math.floor((t - 10) / 10), ISO_COLORS.length - 1)
  const color = ISO_COLORS[idx]
  return new Style({
    fill: new Fill({ color: hexToRgba(color, 0.35) }),
    stroke: new Stroke({ color: color, width: 1.5 }),
  })
}

function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16)
  return `rgba(${r},${g},${b},${alpha})`
}

// keyed by region
const state = {}

export const isochrone = {
  init(region, map, stats) {
    fetch(`./data/iso_${region}.geojson`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!data || data._null || !data.features?.length) {
          state[region] = { layer: null, features: [] }
          return
        }
        const fmt = new GeoJSON()
        const allFeatures = fmt.readFeatures(data, { featureProjection: 'EPSG:3857' })
        const src = new VectorSource()
        const layer = new VectorLayer({ source: src, zIndex: 20, visible: false })
        map.addLayer(layer)
        state[region] = { layer, features: allFeatures }

        // 기본 30분 표시
        this.setTime(region, 30)
      })
      .catch(() => { state[region] = { layer: null, features: [] } })
  },

  setTime(region, minutes) {
    const s = state[region]
    if (!s?.layer) return
    const src = s.layer.getSource()
    src.clear()
    const feat = s.features.find(f => f.get('t') === minutes)
    if (feat) {
      feat.setStyle(isoStyle(minutes))
      src.addFeature(feat)
    }
    s.layer.setVisible(true)
  },

  hide(region) {
    state[region]?.layer?.setVisible(false)
  },

  show(region) {
    state[region]?.layer?.setVisible(true)
  },
}
