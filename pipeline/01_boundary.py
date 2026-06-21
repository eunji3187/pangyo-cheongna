"""
01_boundary.py — 구역경계 생성

청라: AL_D154_28에서 '청라' 포함 필지 dissolve → 전체 경계
     + A7/A8 업무·상업 용도 필지 dissolve → 업무지구 코어

판교: 우선순위
  (a) AL_D154_41 존재 시 — 판교역·제1판교 일대 용도(업무/상업) 필지 dissolve  [권장]
  (b) AL_D154_41 없을 시 — data_raw/boundary/pangyo_manual.geojson 사용
  (c) 최후: UPIS_C_UQ161에서 판교TV bbox로 clip

출력: boundary_pangyo.geojson, boundary_cheongna.geojson (EPSG:4326)
"""
import sys
import json
import geopandas as gpd
import pandas as pd
from shapely.geometry import box, Point
from shapely.ops import unary_union
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from config_loader import cfg

C = cfg()

# ── 업무/상업 용도코드 ────────────────────────────────────────────
# 실측: UQA코드 체계 — A7에 콤마 구분 중간에 삽입됨 (첫 코드는 항상 UBA100 등)
# UQA130=준주거, UQA210=?, UQA220=일반상업, UQA230=근린상업 (분당/판교 기준)
OFFICE_UQA_CODES = {
    "UQA130",  # 준주거지역
    "UQA210",  # 전용공업(일부 지역) 또는 중심상업
    "UQA220",  # 일반상업지역
    "UQA230",  # 근린상업지역
    "UQA240",  # 유통상업지역(있을 경우)
    "UQA310",  # (기타 상업)
}
OFFICE_NAMES_KW = ["일반상업", "중심상업", "근린상업", "유통상업",
                   "일반업무", "중심업무", "준주거", "준공업"]

def is_office(a7: str, a8: str) -> bool:
    """A7 콤마 목록 중 업무·상업 UQA 코드가 있거나, A8 명칭이 해당 키워드인지"""
    if pd.isna(a7) or pd.isna(a8):
        return False
    codes = set(c.strip() for c in str(a7).split(","))
    # UQA 코드 직접 비교 (신뢰도 높음)
    if codes & OFFICE_UQA_CODES:
        return True
    # A8 한글 키워드 fallback
    return any(kw in str(a8) for kw in OFFICE_NAMES_KW)

# ── 인코딩 안전 로더 ─────────────────────────────────────────────
def load_shp(path, enc="cp949"):
    try:
        return gpd.read_file(path, encoding=enc)
    except UnicodeDecodeError:
        return gpd.read_file(path, encoding="utf-8")

def save_boundary(gdf_5179, name: str, method: str):
    gdf_5179 = gdf_5179.copy()
    area_m2 = gdf_5179.geometry.iloc[0].area
    area_ha = round(area_m2 / 10_000, 2)
    gdf_5179 = gdf_5179.to_crs(C.CRS_WEB)

    fc = json.loads(gdf_5179.to_json())
    # properties는 FeatureCollection이 아닌 첫 번째 Feature에 기록
    if fc.get("type") == "FeatureCollection" and fc.get("features"):
        fc["features"][0]["properties"] = {
            "name": name,
            "area_ha": area_ha,
            "method": method,
        }
    out_path = C.DATA_OUT / f"boundary_{name.replace(' ','_').lower()}.geojson"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False)
    print(f"[{name}] 면적 {area_ha} ha  →  {out_path.name}")
    return area_ha

# ════════════════════════════════════════════════════════════════
# 청라
# ════════════════════════════════════════════════════════════════
def make_cheongna():
    print("=== 청라 경계 생성 ===")
    gdf = load_shp(C.AL_D154_28)
    print(f"  원본 CRS: {gdf.crs}  행수: {len(gdf):,}")

    # 5186 → 5179 변환
    gdf = gdf.to_crs(C.CRS_CALC)

    # A2 주소에 '청라' 포함 필지
    mask_cheongna = gdf["A2"].fillna("").str.contains("청라", na=False)
    gdf_cr = gdf[mask_cheongna].copy()
    print(f"  '청라' 필지 수: {len(gdf_cr):,}")
    if len(gdf_cr) == 0:
        raise ValueError("청라 필지를 찾을 수 없습니다. AL_D154_28 인코딩/경로 확인")

    # 전체 청라동 경계 (참고용)
    whole = unary_union(gdf_cr.geometry)
    gdf_whole = gpd.GeoDataFrame(geometry=[whole], crs=C.CRS_CALC)
    save_boundary(gdf_whole, "cheongna_all", "AL_D154_28 청라동 전체 필지 dissolve (참고용)")

    # 업무지구 코어 (A7/A8 업무·상업) → 이것이 분석 기본 경계
    mask_office = gdf_cr.apply(lambda r: is_office(r.get("A7",""), r.get("A8","")), axis=1)
    gdf_office = gdf_cr[mask_office]
    print(f"  업무·상업 필지 수: {len(gdf_office):,}")
    if len(gdf_office) > 0:
        core = unary_union(gdf_office.geometry)
        gdf_core = gpd.GeoDataFrame(geometry=[core], crs=C.CRS_CALC)
        # boundary_cheongna.geojson = 업무지구 코어 (분석 기본)
        save_boundary(gdf_core, "cheongna",
                      "AL_D154_28 청라 업무·상업 용도 필지 dissolve (청라 국제업무단지 분석 기본 경계)")

# ════════════════════════════════════════════════════════════════
# 판교
# ════════════════════════════════════════════════════════════════
def make_pangyo():
    print("=== 판교 경계 생성 ===")
    method = None

    # ── (a) AL_D154_41 경기도 토지이용 이용 ──────────────────────
    if C.AL_D154_41.exists():
        print("  (a) AL_D154_41 경기도 토지이용 사용")
        gdf = load_shp(C.AL_D154_41)
        gdf = gdf.to_crs(C.CRS_CALC)

        # 판교역 / 제1판교 일대 bounding box (5179 약 127.09~127.13 / 37.38~37.42)
        from pyproj import Transformer
        t = Transformer.from_crs("EPSG:4326", C.CRS_CALC, always_xy=True)
        x0, y0 = t.transform(127.085, 37.380)
        x1, y1 = t.transform(127.135, 37.425)
        bbox = box(x0, y0, x1, y1)
        gdf_area = gdf[gdf.geometry.intersects(bbox)].copy()
        print(f"  bbox 내 필지: {len(gdf_area):,}")

        mask_office = gdf_area.apply(lambda r: is_office(r.get("A7",""), r.get("A8","")), axis=1)
        gdf_office = gdf_area[mask_office]
        print(f"  업무·상업 필지: {len(gdf_office):,}")

        if len(gdf_office) > 50:
            poly = unary_union(gdf_office.geometry)
            gdf_pangyo = gpd.GeoDataFrame(geometry=[poly], crs=C.CRS_CALC)
            method = "AL_D154_41 판교 일대 업무·상업 용도 필지 dissolve (IFEZ 토지이용계획 준거)"
        else:
            print("  업무·상업 필지 부족 → (b) 수동 경계로 fallback")

    # ── (b) 수동 GeoJSON ──────────────────────────────────────────
    if method is None and C.PANGYO_MANUAL.exists():
        print(f"  (b) 수동 경계 사용: {C.PANGYO_MANUAL}")
        gdf_pangyo = gpd.read_file(C.PANGYO_MANUAL).to_crs(C.CRS_CALC)
        method = f"수동 디지타이징 GeoJSON ({C.PANGYO_MANUAL.name})"

    # ── (c) UPIS_C_UQ161 + bbox clip ─────────────────────────────
    if method is None:
        print("  (c) UPIS_C_UQ161 fallback")
        if not C.UPIS_UQ161.exists():
            raise FileNotFoundError(f"{C.UPIS_UQ161} 없음")
        gdf_uq = load_shp(C.UPIS_UQ161)
        gdf_uq = gdf_uq.to_crs(C.CRS_CALC)

        from pyproj import Transformer
        t = Transformer.from_crs("EPSG:4326", C.CRS_CALC, always_xy=True)
        x0, y0 = t.transform(127.090, 37.390)
        x1, y1 = t.transform(127.125, 37.420)
        bbox = box(x0, y0, x1, y1)
        gdf_clip = gdf_uq[gdf_uq.geometry.intersects(bbox)]

        # 판교TV 좌표 포함 폴리곤 우선
        pt1 = Point(*t.transform(C.PANGYO_STATION_LNG, C.PANGYO_STATION_LAT))
        pt2 = Point(*t.transform(C.PANGYO_1ST_LNG, C.PANGYO_1ST_LAT))
        hit = gdf_clip[gdf_clip.geometry.contains(pt1) | gdf_clip.geometry.contains(pt2)]
        target = hit if len(hit) > 0 else gdf_clip.iloc[[0]]
        poly = unary_union(target.geometry)
        gdf_pangyo = gpd.GeoDataFrame(geometry=[poly], crs=C.CRS_CALC)
        method = "UPIS_C_UQ161 지구단위계획구역 bbox clip (판교TV 포인트 포함 폴리곤)"

    save_boundary(gdf_pangyo, "pangyo", method)

# ════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    C.ensure_out()
    make_cheongna()
    make_pangyo()
    print("\n✓ 01_boundary.py 완료")
