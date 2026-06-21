"""
05_isochrone.py — 등시간권 폴리곤 생성

active_nodes.csv의 dist_s_{region} 컬럼 (초) 이용
t분 등시간권 = 각 활성 노드 i에 대해
  egress_radius_i = min(t*60 - dist_i, 0) * walk_speed → 버퍼
  전체 union·dissolve

단, 네트워크 데이터가 없으면 null GeoJSON 출력

출력: iso_pangyo.geojson, iso_cheongna.geojson (4326)
      피처 속성: {"t": 30, "pop": null, "workers": null}
"""
import sys
import json
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from shapely.ops import unary_union
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import cfg

C = cfg()

WALK_SPEED = C.WALK_SPEED_M_S   # 1.333 m/s
WALK_CAP   = C.WALK_CAP_M       # 1600 m
MINUTES    = C.ISO_MINUTES

def make_isochrone_for_region(region: str, nodes_csv: Path) -> list:
    """
    region: "pangyo" | "cheongna"
    반환: [{t, geometry(5179)}, ...]  시간순
    """
    if not nodes_csv.exists():
        print(f"  [{region}] active_nodes.csv 없음 → null")
        return []

    df = pd.read_csv(nodes_csv)
    dist_col = f"dist_s_{region}"
    if dist_col not in df.columns:
        print(f"  [{region}] 컬럼 {dist_col} 없음 → null")
        return []

    df = df.dropna(subset=["x_5179", "y_5179", dist_col])
    df[dist_col] = pd.to_numeric(df[dist_col], errors="coerce")
    df = df[df[dist_col] < np.inf].copy()
    print(f"  [{region}] 유효 노드 {len(df)}")

    features = []
    for t in MINUTES:
        budget_s = t * 60
        subset = df[df[dist_col] <= budget_s].copy()
        if len(subset) == 0:
            continue
        subset["egress_s"] = budget_s - subset[dist_col]
        subset["radius_m"] = (subset["egress_s"] * WALK_SPEED).clip(upper=WALK_CAP)

        buffers = []
        for _, row in subset.iterrows():
            if row["radius_m"] > 0:
                pt = Point(row["x_5179"], row["y_5179"])
                buffers.append(pt.buffer(row["radius_m"]))
        if not buffers:
            continue
        poly = unary_union(buffers)
        features.append({"t": t, "geometry": poly})
        print(f"    {t}분권: {poly.area/1e6:.2f} km²")

    return features

def save_isochrone(region: str, features: list, core_station: dict):
    out_path = C.DATA_OUT / f"iso_{region}.geojson"

    if not features:
        # null 출력
        fc = {
            "type": "FeatureCollection",
            "features": [],
            "_null": True,
            "_reason": "subway network data not available",
        }
        with open(out_path, "w") as f:
            json.dump(fc, f)
        print(f"  [{region}] null GeoJSON 저장")
        return

    gdf = gpd.GeoDataFrame(
        [{"t": f["t"], "pop": None, "workers": None} for f in features],
        geometry=[f["geometry"] for f in features],
        crs=C.CRS_CALC,
    )

    # 60분 ⊇ 30분 포함관계 검증
    t30 = gdf[gdf["t"] == 30]
    t60 = gdf[gdf["t"] == 60]
    if len(t30) and len(t60):
        ok = t60.geometry.iloc[0].contains(t30.geometry.iloc[0])
        print(f"  [{region}] 30min<=60min containment: {'OK' if ok else 'WARN'}")

    gdf = gdf.to_crs(C.CRS_WEB)
    gdf.to_file(out_path, driver="GeoJSON")

    size_mb = out_path.stat().st_size / 1_048_576
    print(f"  [{region}] {out_path.name}  {size_mb:.1f} MB")

if __name__ == "__main__":
    C.ensure_out()
    print("=== 05_isochrone.py ===")

    nodes_csv = C.SUBWAY_NODES.parent / "active_nodes.csv"

    for region in ["pangyo", "cheongna"]:
        print(f"\n--- {region} ---")
        features = make_isochrone_for_region(region, nodes_csv)
        save_isochrone(region, features, {})

    print("\n✓ 05_isochrone.py 완료")
