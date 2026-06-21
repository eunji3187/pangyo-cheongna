"""
06_sgis_join.py — SGIS 인구·사업체 통계 공간 배분

경기도 집계구 경계(EPSG:5179) + 인구(2024)/가구(2024)/종사자·사업체(2023) CSV
집계구코드 조인 → 면적비례 배분(areal weighting) → 판교 통계 산출

인천 서구 CSV (23080_*): 집계구 경계 SHP 미확보 → 서구 전체 합산 후 면적비례 추정

CSV 형식: 헤더 없음, 4열 = [year, census_cd, indicator, value]
SHP 조인키: TOT_OA_CD (14자리) ↔ CSV census_cd
"""
import sys
import json
import geopandas as gpd
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import cfg

C = cfg()

def load_csv(path: Path) -> pd.DataFrame:
    """SGIS CSV 로드 (헤더 없음, 4열)"""
    if not path.exists():
        return pd.DataFrame(columns=["year", "census_cd", "indicator", "value"])
    df = pd.read_csv(path, encoding="cp949", header=None)
    df.columns = ["year", "census_cd", "indicator", "value"]
    df["value"] = pd.to_numeric(df["value"], errors="coerce").fillna(0)
    df["census_cd"] = df["census_cd"].astype(str)
    return df

def areal_apportionment(target_poly, census_gdf: gpd.GeoDataFrame,
                        value_cols: list) -> dict:
    """
    면적 비례 배분:
      대상 폴리곤 P, 집계구 c → w = area(P∩c)/area(c)
      배분값 = Σ w * value_c
    """
    if census_gdf is None or len(census_gdf) == 0:
        return {col: None for col in value_cols}

    # 후보 집계구 한정 (bounding box로 1차 필터)
    candidates = census_gdf[census_gdf.intersects(target_poly.buffer(0))]
    result = {col: 0.0 for col in value_cols}
    any_overlap = False

    for _, row in candidates.iterrows():
        geom_c = row.geometry
        inter = target_poly.intersection(geom_c)
        area_c = geom_c.area
        if area_c <= 0 or inter.is_empty:
            continue
        w = inter.area / area_c
        if w <= 0:
            continue
        any_overlap = True
        for col in value_cols:
            v = row.get(col, 0)
            if pd.notna(v):
                result[col] += w * float(v)

    if not any_overlap:
        return {col: None for col in value_cols}
    return {col: round(v, 1) for col, v in result.items()}

def load_gyeonggi_census() -> gpd.GeoDataFrame | None:
    """경기도 집계구 경계 + 인구·가구·종사자·사업체 CSV 조인"""
    if not C.SGIS_BOUNDARY.exists():
        print("  경기도 집계구 경계 SHP 없음 → null 처리")
        return None

    gdf = gpd.read_file(C.SGIS_BOUNDARY)  # already EPSG:5179
    gdf["TOT_OA_CD"] = gdf["TOT_OA_CD"].astype(str)
    print(f"  경기도 집계구: {len(gdf):,} 개")

    # 인구 (to_in_001 = 총인구)
    pop = load_csv(C.SGIS_POP_CSV)
    pop = pop[pop["indicator"] == "to_in_001"][["census_cd", "value"]].rename(columns={"value": "pop_total"})

    # 가구 (to_ga_001 = 총가구)
    hh = load_csv(C.SGIS_HH_CSV)
    hh = hh[hh["indicator"] == "to_ga_001"][["census_cd", "value"]].rename(columns={"value": "hh_total"})

    # 종사자 (to_em_020 = 총종사자수)
    wk = load_csv(C.SGIS_WK_CSV)
    wk = wk[["census_cd", "value"]].rename(columns={"value": "workers"})

    # 사업체 (to_fa_010 = 총사업체수)
    biz = load_csv(C.SGIS_BIZ_CSV)
    biz = biz[["census_cd", "value"]].rename(columns={"value": "businesses"})

    for df in [pop, hh, wk, biz]:
        col = [c for c in df.columns if c != "census_cd"][0]
        gdf = gdf.merge(df, left_on="TOT_OA_CD", right_on="census_cd", how="left")
        gdf[col] = gdf[col].fillna(0)
        if "census_cd" in gdf.columns:
            gdf = gdf.drop(columns=["census_cd"])

    matched = (gdf["pop_total"] > 0).sum()
    print(f"  인구 매칭 집계구: {matched:,} / {len(gdf):,}")
    return gdf

def cheongna_area_estimate(boundary_ha: float) -> dict:
    """
    인천 서구 CSV 총합 × (청라 boundary_ha / 서구 면적 ha) 면적비례 추정
    서구 집계구 경계 SHP 미확보로 areal apportionment 불가.
    """
    frac = boundary_ha / C.SEOGU_AREA_HA
    sgis_dir = C.DATA_RAW / "sgis"

    def safe_total(path, indicator_filter=None):
        df = load_csv(path)
        if indicator_filter:
            df = df[df["indicator"] == indicator_filter]
        total = df["value"].sum()
        return round(total * frac, 1) if total > 0 else None

    return {
        "pop_total":  safe_total(C.SGIS_POP23_CSV, "to_in_001"),
        "hh_total":   safe_total(C.SGIS_HH23_CSV,  "to_ga_001"),
        "workers":    safe_total(C.SGIS_WK23_CSV),
        "businesses": safe_total(C.SGIS_BIZ23_CSV),
    }

def compute_region_stats(region: str, census_gdf) -> dict:
    bnd_path = C.DATA_OUT / f"boundary_{region}.geojson"
    iso_path = C.DATA_OUT / f"iso_{region}.geojson"

    if not bnd_path.exists():
        return {
            "population": None, "households": None,
            "workers": None, "businesses": None, "isochrone": {}
        }

    bnd = gpd.read_file(bnd_path).to_crs(C.CRS_CALC)
    bnd_poly = bnd.geometry.iloc[0]
    area_ha = bnd["properties"].iloc[0].get("area_ha") if "properties" in bnd.columns else None
    if area_ha is None:
        area_ha = bnd.iloc[0].geometry.area / 1e4  # 5179 → m² → ha

    value_cols = ["pop_total", "hh_total", "workers", "businesses"]

    if region == "cheongna":
        # 인천 서구 SHP 미확보 → 면적비례 추정
        print(f"  청라: 서구 CSV 면적비례 추정 (boundary {area_ha:.1f} ha / 서구 {C.SEOGU_AREA_HA:.0f} ha)")
        stats = cheongna_area_estimate(area_ha)
    else:
        stats = areal_apportionment(bnd_poly, census_gdf, value_cols) if census_gdf is not None else {c: None for c in value_cols}

    # 등시간권 통계
    iso_stats = {}
    if iso_path.exists():
        iso_gdf = gpd.read_file(iso_path).to_crs(C.CRS_CALC)
        for _, row in iso_gdf.iterrows():
            t = str(int(row.get("t", 0)))
            props = row.get("geometry")
            if row.geometry is None or row.geometry.is_empty:
                iso_stats[t] = {"pop": None, "workers": None}
                continue
            if region == "cheongna" or census_gdf is None:
                iso_stats[t] = {"pop": None, "workers": None}
            else:
                iso_val = areal_apportionment(row.geometry, census_gdf, value_cols)
                iso_stats[t] = {
                    "pop":     iso_val.get("pop_total"),
                    "workers": iso_val.get("workers"),
                }

    return {
        "population":  stats.get("pop_total"),
        "households":  stats.get("hh_total"),
        "workers":     stats.get("workers"),
        "businesses":  stats.get("businesses"),
        "isochrone":   iso_stats,
    }

if __name__ == "__main__":
    C.ensure_out()
    print("=== 06_sgis_join.py ===")

    census_gdf = load_gyeonggi_census()

    output = {}
    for region in ["pangyo", "cheongna"]:
        print(f"\n--- {region} ---")
        output[region] = compute_region_stats(region, census_gdf)
        pop = output[region].get("population")
        wk  = output[region].get("workers")
        biz = output[region].get("businesses")
        print(f"  인구={pop}, 종사자={wk}, 사업체={biz}")

    out_path = C.DATA_OUT / "sgis_stats.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n→ {out_path.name} 저장")
    print("✓ 06_sgis_join.py 완료")
