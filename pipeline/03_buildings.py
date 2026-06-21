"""
03_buildings.py — 건축물대장 API 수집 (건축HUB 표제부)

필지 SHP A1 컬럼에서 (sigunguCd, bjdongCd) 쌍을 자동 추출하여 수집.
출력: buildings_pangyo.geojson, buildings_cheongna.geojson (4326)
건축HUB 키는 이 스크립트에서만 사용, 웹 코드에 절대 포함 금지
"""
import sys
import time
import json
import traceback
import requests
import geopandas as gpd
import pandas as pd
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import cfg

C = cfg()
API_BASE = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"


def _dong_pairs_from_shp(shp_path: Path, boundary_geojson: str) -> list:
    """경계와 교차하는 필지 A1 컬럼에서 (sigunguCd, bjdongCd) 쌍 추출"""
    gdf = gpd.read_file(shp_path, encoding="cp949").to_crs(C.CRS_CALC)
    bnd = gpd.read_file(C.DATA_OUT / boundary_geojson).to_crs(C.CRS_CALC)
    bnd_poly = bnd.geometry.iloc[0]
    sub = gdf[gdf.geometry.intersects(bnd_poly)]
    a1_vals = (
        sub["A1"].fillna("").astype(str)
        .str.replace(r"\.0+$", "", regex=True)
        .str.zfill(10)
        .unique()
    )
    pairs = [(v[:5], v[5:]) for v in a1_vals if len(v) == 10 and v.isdigit()]
    return sorted(set(pairs))


def _fetch_one_dong(sigungu_cd: str, bjdong_cd: str, max_pages=9999) -> list:
    """단일 (sigunguCd, bjdongCd) 건물 전량 수집"""
    records = []
    page = 1
    while page <= max_pages:
        params = {
            "serviceKey": C.BUILDING_HUB_KEY,
            "sigunguCd": sigungu_cd,
            "bjdongCd": bjdong_cd,
            "numOfRows": 100,
            "pageNo": page,
            "_type": "json",
        }
        try:
            resp = requests.get(API_BASE, params=params, timeout=30)
            data = resp.json()
            body = data.get("response", {}).get("body", {})
            items = body.get("items", {})
            if not items:
                break
            item_list = items.get("item", [])
            if isinstance(item_list, dict):
                item_list = [item_list]
            if not item_list:
                break
            records.extend(item_list)
            total_count = int(body.get("totalCount", 0))
            if page == 1:
                print(f"    {sigungu_cd}+{bjdong_cd}: {total_count}건")
            if len(records) >= total_count:
                break
            page += 1
            time.sleep(0.1)
        except Exception as e:
            traceback.print_exc()
            print(f"    {sigungu_cd}+{bjdong_cd} p{page} error: {e}")
            time.sleep(1)
            break
    return records


def fetch_buildings(shp_path: Path, boundary_geojson: str, region: str) -> pd.DataFrame:
    """필지 SHP 경계 내 동 목록을 자동 추출해 건축물 표제부 전량 수집"""
    pairs = _dong_pairs_from_shp(shp_path, boundary_geojson)
    print(f"  [{region}] 수집 대상 동: {pairs}")
    all_records = []
    for sigungu_cd, bjdong_cd in pairs:
        recs = _fetch_one_dong(sigungu_cd, bjdong_cd)
        all_records.extend(recs)
    print(f"  [{region}] 총 {len(all_records)}건 수집 완료")
    return pd.DataFrame(all_records)


def join_to_parcels(df_bld: pd.DataFrame, shp_path: Path, boundary_geojson: str, region: str):
    """건축물 속성을 필지 GeoDataFrame에 조인"""
    if not shp_path.exists():
        print(f"  [{region}] SHP 없음 -> 스킵")
        return None, {}

    bnd_path = C.DATA_OUT / boundary_geojson
    if not bnd_path.exists():
        print(f"  [{region}] 경계 파일 없음 -> 01_boundary.py 먼저 실행")
        return None, {}

    gdf = gpd.read_file(shp_path, encoding="cp949").to_crs(C.CRS_CALC)
    bnd = gpd.read_file(bnd_path).to_crs(C.CRS_CALC)
    bnd_poly = bnd.geometry.iloc[0]

    gdf = gdf[gdf.geometry.intersects(bnd_poly)].copy()
    gdf["geometry"] = gdf.geometry.intersection(bnd_poly)
    gdf = gdf[~gdf.geometry.is_empty].copy()

    # PNU 15자리: 법정동코드(10) + 산구분(1) + 본번(4)
    # 부번(ji)은 필지 SHP에 항상 0000이므로 조인 키에서 제외
    gdf["pnu"] = (
        gdf["A1"].fillna("").astype(str)
            .str.replace(r"\.0+$", "", regex=True).str.zfill(10) +
        "0" +
        gdf["A5"].fillna("").astype(str)
            .str.extract(r"^(\d+)", expand=False).fillna("0").str.zfill(4)
    )

    if len(df_bld) == 0:
        print(f"  [{region}] 건축물 데이터 없음")
        gdf_out = gdf[["geometry", "pnu"]].copy()
        gdf_out = gdf_out.to_crs(C.CRS_WEB)
        out = C.DATA_OUT / f"buildings_{region}.geojson"
        gdf_out.to_file(out, driver="GeoJSON")
        return gdf_out, {}

    # 건축물 PNU 15자리: sigunguCd(5)+bjdongCd(5)+산구분(1)+본번(4)
    df_bld = df_bld.copy()
    df_bld["pnu"] = (
        df_bld["sigunguCd"].fillna("").astype(str).str.zfill(5) +
        df_bld["bjdongCd"].fillna("").astype(str).str.zfill(5) +
        df_bld.get("platGbCd", pd.Series("0", index=df_bld.index)).fillna("0").astype(str) +
        df_bld.get("bun", pd.Series("0", index=df_bld.index)).fillna("0").astype(str).str.zfill(4)
    )

    numeric_cols = ["totArea", "vlRat", "bcRat", "platArea", "vlRatEstmTotArea"]
    for col in numeric_cols:
        if col in df_bld.columns:
            df_bld[col] = pd.to_numeric(df_bld[col], errors="coerce")

    agg = df_bld.groupby("pnu").agg(
        total_area=("totArea", "sum"),
        mean_far=("vlRat", "mean"),
        mean_bcr=("bcRat", "mean"),
        main_use=("mainPurpsCdNm", lambda x: x.mode().iloc[0] if len(x) else None),
    ).reset_index()

    matched = gdf["pnu"].isin(agg["pnu"]).sum()
    print(f"  [{region}] PNU join: parcel {len(gdf)}필지 중 {matched}개 매칭")

    gdf = gdf.merge(agg, on="pnu", how="left")

    has_bld = gdf["total_area"].notna() & (gdf["total_area"] > 0)
    vacant_pct = round((~has_bld).sum() / len(gdf) * 100, 2) if len(gdf) > 0 else 0

    use_pct = {}
    if "main_use" in gdf.columns:
        use_cnts = gdf[has_bld]["main_use"].value_counts(normalize=True)
        use_pct = {str(k): round(v * 100, 2) for k, v in use_cnts.head(10).items()}

    mean_far = round(gdf[has_bld]["mean_far"].mean(), 3) if has_bld.sum() > 0 else None
    mean_bcr = round(gdf[has_bld]["mean_bcr"].mean(), 3) if has_bld.sum() > 0 else None

    stats = {
        "building_use_pct": use_pct,
        "mean_far": mean_far,
        "mean_bcr": mean_bcr,
        "vacant_parcel_pct": vacant_pct,
    }

    cols_keep = ["geometry", "pnu", "total_area", "mean_far", "mean_bcr", "main_use"]
    cols_keep = [c for c in cols_keep if c in gdf.columns]
    gdf_out = gdf[cols_keep].copy()
    gdf_out["geometry"] = gdf_out.geometry.simplify(C.SIMPLIFY_TOL_M)
    gdf_out = gdf_out.to_crs(C.CRS_WEB)
    out = C.DATA_OUT / f"buildings_{region}.geojson"
    gdf_out.to_file(out, driver="GeoJSON")
    print(f"  [{region}] {out.name} saved (vacant {vacant_pct}%, mean FAR {mean_far})")

    return gdf_out, stats


if __name__ == "__main__":
    C.ensure_out()
    print("=== 03_buildings.py ===")

    print("\n[pangyo] fetch buildings from AL_D154_41 boundary")
    df_pg = fetch_buildings(C.AL_D154_41, "boundary_pangyo.geojson", "pangyo")
    _, stats_pg = join_to_parcels(df_pg, C.AL_D154_41, "boundary_pangyo.geojson", "pangyo")

    print("\n[cheongna] fetch buildings from AL_D154_28 boundary")
    df_cr = fetch_buildings(C.AL_D154_28, "boundary_cheongna.geojson", "cheongna")
    _, stats_cr = join_to_parcels(df_cr, C.AL_D154_28, "boundary_cheongna.geojson", "cheongna")

    summary = {"pangyo": stats_pg or {}, "cheongna": stats_cr or {}}
    out = C.DATA_OUT / "buildings_stats.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n-> {out.name} saved")
    print("OK 03_buildings.py done")
