"""
07b_bus.py — 버스정류장 밀도

국토교통부_전국 버스정류장 위치정보_20251031.csv (cp949)
WGS84 포인트 → 구역 내 정류장 수 / 면적km²

출력: bus_stats.json (bus_density_per_km2)
      stations.geojson (버스+지하철 정류장 합산, 웹 마커용)
"""
import sys
import json
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import cfg

C = cfg()

def load_bus_csv() -> gpd.GeoDataFrame:
    if not C.BUS_CSV.exists():
        print(f"  버스 CSV 없음: {C.BUS_CSV}")
        return None
    print(f"  버스 CSV 로드: {C.BUS_CSV.name}")
    try:
        df = pd.read_csv(C.BUS_CSV, encoding="cp949", low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(C.BUS_CSV, encoding="utf-8", low_memory=False)

    # 컬럼 탐색 (위도/경도)
    lat_col = next((c for c in df.columns if "위도" in c or "lat" in c.lower()), None)
    lng_col = next((c for c in df.columns if "경도" in c or "lon" in c.lower() or "lng" in c.lower()), None)
    name_col = next((c for c in df.columns if "정류장명" in c or "명칭" in c), None)

    if lat_col is None or lng_col is None:
        print(f"  위도/경도 컬럼 못 찾음. 컬럼: {list(df.columns[:10])}")
        return None

    df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce")
    df[lng_col] = pd.to_numeric(df[lng_col], errors="coerce")
    df = df.dropna(subset=[lat_col, lng_col])

    gdf = gpd.GeoDataFrame(
        df,
        geometry=[Point(row[lng_col], row[lat_col]) for _, row in df.iterrows()],
        crs="EPSG:4326",
    )
    print(f"  전국 버스정류장: {len(gdf):,}")
    return gdf

def compute_bus_density(region: str, bus_gdf: gpd.GeoDataFrame) -> float | None:
    bnd_path = C.DATA_OUT / f"boundary_{region}.geojson"
    if not bnd_path.exists() or bus_gdf is None:
        return None

    bnd = gpd.read_file(bnd_path).to_crs(C.CRS_CALC)
    bnd_poly = bnd.geometry.iloc[0]
    area_km2 = bnd_poly.area / 1_000_000

    bus_5179 = bus_gdf.to_crs(C.CRS_CALC)
    within = bus_5179[bus_5179.geometry.within(bnd_poly)]
    count = len(within)
    density = round(count / area_km2, 3) if area_km2 > 0 else None
    print(f"  [{region}] 버스정류장 {count}개 / {area_km2:.2f} km² = {density} /km²")
    return density

def make_stations_geojson(bus_gdf: gpd.GeoDataFrame):
    """웹 마커용 정류장 GeoJSON (두 지역 주변 합산)"""
    if bus_gdf is None:
        return

    features = []
    regions_bbox = {
        "pangyo":   (127.085, 37.380, 127.135, 37.425),
        "cheongna": (126.610, 37.510, 126.690, 37.570),
    }
    for region, (x0, y0, x1, y1) in regions_bbox.items():
        subset = bus_gdf.cx[x0:x1, y0:y1]
        name_col = next((c for c in bus_gdf.columns if "정류장명" in c or "명칭" in c), None)
        for _, row in subset.iterrows():
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [row.geometry.x, row.geometry.y],
                },
                "properties": {
                    "type": "bus",
                    "region": region,
                    "name": str(row[name_col]) if name_col else "",
                },
            })

    out = C.DATA_OUT / "stations.geojson"
    fc = {"type": "FeatureCollection", "features": features}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False)
    print(f"  → stations.geojson ({len(features)} 정류장)")

if __name__ == "__main__":
    C.ensure_out()
    print("=== 07b_bus.py ===")

    bus_gdf = load_bus_csv()
    result = {}
    for region in ["pangyo", "cheongna"]:
        result[region] = {"bus_density_per_km2": compute_bus_density(region, bus_gdf)}

    make_stations_geojson(bus_gdf)

    out = C.DATA_OUT / "bus_stats.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n→ {out.name}")
    print("✓ 07b_bus.py 완료")
