"""
02_landuse.py — 토지이용 분석

AL_D154(5186, cp949) → 5179 변환 → 구역경계로 clip
A7 콤마 중 UQA 계열 코드로 주 용도지역 판별 (첫 코드는 UBA 등 규제지역)
A8 한글명으로 카테고리 분류 (주 UQA 코드 이름이 A8 중간에 있음)
출력: landuse_pangyo.geojson, landuse_cheongna.geojson (4326)
"""
import sys
import json
import math
import numpy as np
import geopandas as gpd
import pandas as pd
from shapely.ops import unary_union
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from config_loader import cfg

C = cfg()

# ── 용도지역 카테고리 매핑 ────────────────────────────────────────
LANDUSE_CAT = {
    "주거": ["전용주거", "일반주거", "준주거"],
    "상업": ["근린상업", "일반상업", "유통상업", "중심상업"],
    "업무": ["일반업무", "중심업무"],
    "공업": ["전용공업", "일반공업", "준공업"],
    "비지": ["자연녹지", "생산녹지", "보전녹지", "자연환경", "농림", "관리"],
    "기타": [],
}

def classify_landuse(a8: str) -> str:
    if pd.isna(a8):
        return "기타"
    a8 = str(a8)
    for cat, kws in LANDUSE_CAT.items():
        if any(kw in a8 for kw in kws):
            return cat
    if "지구단위" in a8 or "UQ" in a8:
        return "지구단위"
    return "기타"

def load_shp(path, enc="cp949"):
    try:
        gdf = gpd.read_file(path, encoding=enc)
    except UnicodeDecodeError:
        gdf = gpd.read_file(path, encoding="utf-8")
    return gdf

def lum_entropy(pct_dict: dict) -> float:
    """토지이용 혼합도 LUM Shannon entropy (정규화)"""
    vals = [v for v in pct_dict.values() if v > 0]
    n = len(vals)
    if n <= 1:
        return 0.0
    total = sum(vals)
    ent = -sum((v/total) * math.log(v/total) for v in vals)
    return round(ent / math.log(n), 4)

def process_region(shp_path, boundary_geojson, region_name: str):
    if not shp_path.exists():
        print(f"  [{region_name}] {shp_path.name} 없음 → null 처리")
        return None, {}

    bnd_path = C.DATA_OUT / boundary_geojson
    if not bnd_path.exists():
        print(f"  [{region_name}] 경계 파일 없음 ({bnd_path}) → 01_boundary.py 먼저 실행")
        return None, {}

    print(f"  [{region_name}] SHP 로드 중...")
    gdf = load_shp(shp_path)
    gdf = gdf.to_crs(C.CRS_CALC)

    bnd = gpd.read_file(bnd_path).to_crs(C.CRS_CALC)
    bnd_poly = bnd.geometry.iloc[0]

    # clip
    gdf = gdf[gdf.geometry.intersects(bnd_poly)].copy()
    gdf["geometry"] = gdf.geometry.intersection(bnd_poly)
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()].copy()
    print(f"    clip 후 필지 수: {len(gdf):,}")

    gdf["category"] = gdf["A8"].apply(classify_landuse)
    gdf["area_m2"] = gdf.geometry.area

    total_area = gdf["area_m2"].sum()
    zone_pct = {}
    for cat in LANDUSE_CAT:
        a = gdf[gdf["category"] == cat]["area_m2"].sum()
        zone_pct[cat] = round(a / total_area * 100, 2) if total_area > 0 else 0.0
    # 지구단위 포함
    a = gdf[gdf["category"] == "지구단위"]["area_m2"].sum()
    zone_pct["지구단위"] = round(a / total_area * 100, 2) if total_area > 0 else 0.0

    entropy = lum_entropy(zone_pct)

    # 웹용 GeoJSON (simplify + 4326)
    gdf_out = gdf[["geometry", "A5", "A8", "category", "area_m2"]].copy()
    gdf_out.columns = ["geometry", "jibun", "zone_name", "category", "area_m2"]
    gdf_out["area_m2"] = gdf_out["area_m2"].round(1)
    gdf_out["geometry"] = gdf_out.geometry.simplify(C.SIMPLIFY_TOL_M)
    gdf_out = gdf_out.to_crs(C.CRS_WEB)

    out_path = C.DATA_OUT / f"landuse_{region_name}.geojson"
    gdf_out.to_file(out_path, driver="GeoJSON")

    # 파일 크기 체크
    size_mb = out_path.stat().st_size / 1_048_576
    print(f"    {out_path.name}  {size_mb:.1f} MB  entropy={entropy}")

    stats = {
        "landuse_zone_pct": zone_pct,
        "lum_entropy": entropy,
    }
    return gdf, stats

if __name__ == "__main__":
    C.ensure_out()
    print("=== 02_landuse.py ===")

    _, stats_cr = process_region(C.AL_D154_28, "boundary_cheongna.geojson", "cheongna")
    _, stats_pg = process_region(C.AL_D154_41, "boundary_pangyo.geojson", "pangyo")

    summary = {
        "pangyo": stats_pg or {},
        "cheongna": stats_cr or {},
    }
    out = C.DATA_OUT / "landuse_stats.json"
    import json
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n→ {out.name} 저장 완료")
    print("✓ 02_landuse.py 완료")
