"""
07_osm_roads.py — OSM 도로 밀도

south-korea-260617.osm.pbf → osmium extract (bbox) → highway way
구역경계로 clip → 도로연장km / 면적km² = 도로망 밀도

의존: osmium-tool (CLI), pyosmium 또는 osmium python binding
없을 경우 subprocess로 osmium extract 후 geopandas 처리

출력: roads_stats.json (road_density_km_per_km2)
"""
import sys
import json
import subprocess
import tempfile
import geopandas as gpd
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import cfg

C = cfg()

BBOX = {
    "pangyo":  "127.085,37.380,127.135,37.425",
    "cheongna": "126.610,37.510,126.690,37.570",
}

def osmium_extract(pbf: Path, bbox: str, out_pbf: Path):
    cmd = [
        "osmium", "extract",
        "--bbox", bbox,
        "--output", str(out_pbf),
        "--overwrite",
        str(pbf),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"osmium extract 실패: {result.stderr}")

def pbf_to_roads_gdf(pbf: Path) -> gpd.GeoDataFrame:
    """pyosmium 없으면 osmium export로 GeoJSON 변환 후 로드"""
    out_geojson = pbf.with_suffix(".geojson")
    cmd = [
        "osmium", "export",
        "--geometry-types=linestring",
        "--output-format=geojson",
        "--output", str(out_geojson),
        "--overwrite",
        str(pbf),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"osmium export 실패: {result.stderr}")

    gdf = gpd.read_file(out_geojson)
    # highway 필터
    if "highway" in gdf.columns:
        gdf = gdf[gdf["highway"].notna()]
    return gdf

def compute_road_density(region: str) -> float | None:
    bnd_path = C.DATA_OUT / f"boundary_{region}.geojson"
    if not bnd_path.exists():
        print(f"  [{region}] 경계 없음")
        return None

    if not C.OSM_PBF.exists():
        print(f"  OSM PBF 없음: {C.OSM_PBF}")
        return None

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_pbf = Path(tmpdir) / f"{region}.pbf"
            osmium_extract(C.OSM_PBF, BBOX[region], tmp_pbf)
            roads_gdf = pbf_to_roads_gdf(tmp_pbf)
            if len(roads_gdf) == 0:
                return None

            bnd = gpd.read_file(bnd_path).to_crs(C.CRS_CALC)
            roads_gdf = roads_gdf.to_crs(C.CRS_CALC)
            bnd_poly = bnd.geometry.iloc[0]

            clipped = roads_gdf.clip(bnd_poly)
            road_km = clipped.geometry.length.sum() / 1000
            area_km2 = bnd_poly.area / 1_000_000
            density = round(road_km / area_km2, 3) if area_km2 > 0 else None
            print(f"  [{region}] 도로 {road_km:.1f} km / {area_km2:.2f} km² = {density} km/km²")
            return density
    except Exception as e:
        print(f"  [{region}] osmium 오류: {e}")
        return None

if __name__ == "__main__":
    C.ensure_out()
    print("=== 07_osm_roads.py ===")

    result = {}
    for region in ["pangyo", "cheongna"]:
        result[region] = {"road_density_km_per_km2": compute_road_density(region)}

    out = C.DATA_OUT / "roads_stats.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n→ {out.name}")
    print("✓ 07_osm_roads.py 완료")
