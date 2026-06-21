"""
08_build_stats.py — 모든 지표 통합 → stats.json

각 단계 산출 JSON을 읽어 단일 stats.json으로 병합.
미보유 데이터 → null (깨지지 않게).
stats.json이 웹의 유일한 수치 출처이므로 여기서만 계산.
"""
import sys
import json
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import cfg

C = cfg()

def load_json(path: Path) -> dict:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}

def load_boundary_area(region: str) -> float | None:
    p = C.DATA_OUT / f"boundary_{region}.geojson"
    if not p.exists():
        return None
    d = load_json(p)
    # FeatureCollection 또는 Feature
    if d.get("type") == "FeatureCollection":
        feats = d.get("features", [])
        if feats:
            return feats[0].get("properties", {}).get("area_ha")
    return d.get("properties", {}).get("area_ha")

def iso_stats_for_region(sgis: dict, region: str) -> dict:
    reg = sgis.get(region, {})
    iso = reg.get("isochrone", {})
    result = {}
    for t in ["10", "20", "30", "40", "50", "60"]:
        result[t] = iso.get(t, {"pop": None, "workers": None})
    return result

def build():
    landuse  = load_json(C.DATA_OUT / "landuse_stats.json")
    buildings = load_json(C.DATA_OUT / "buildings_stats.json")
    sgis     = load_json(C.DATA_OUT / "sgis_stats.json")
    roads    = load_json(C.DATA_OUT / "roads_stats.json")
    bus      = load_json(C.DATA_OUT / "bus_stats.json")

    # 건축물 fetch 날짜
    building_fetch_date = date.today().strftime("%Y-%m")

    # 경기 AL_D154 있는지 여부
    gyeonggi_date = "2026-04-12" if C.AL_D154_41.exists() else None

    meta = {
        "network_cutoff": C.NETWORK_CUTOFF,
        "pop_year": "2024",
        "household_year": "2024",
        "business_year": "2023",
        "sgis_boundary": "2025_2Q",
        "building_source": "건축HUB 표제부",
        "building_fetch_date": building_fetch_date,
        "landuse_source": "AL_D154 토지이용계획정보",
        "landuse_date_incheon": "2026-04-12",
        "landuse_date_gyeonggi": gyeonggi_date,
        "walk_speed_m_per_s": C.WALK_SPEED_M_S,
        "walk_cap_m": C.WALK_CAP_M,
        "areal_method": "area-weighted apportionment",
        "pangyo_boundary_method": load_boundary_method("pangyo"),
        "cheongna_boundary_method": load_boundary_method("cheongna"),
    }

    def reg(region: str, name: str, core_station: str) -> dict:
        lu = landuse.get(region, {})
        bld = buildings.get(region, {})
        sg = sgis.get(region, {})
        rd = roads.get(region, {})
        bs = bus.get(region, {})

        return {
            "name": name,
            "core_station": core_station,
            "area_ha": load_boundary_area(region),
            "landuse_zone_pct": lu.get("landuse_zone_pct", {}),
            "building_use_pct": bld.get("building_use_pct", {}),
            "lum_entropy": lu.get("lum_entropy"),
            "mean_far": bld.get("mean_far"),
            "mean_bcr": bld.get("mean_bcr"),
            "vacant_parcel_pct": bld.get("vacant_parcel_pct"),
            "population": sg.get("population"),
            "households": sg.get("households"),
            "workers": sg.get("workers"),
            "businesses": sg.get("businesses"),
            "industry_mix_pct": sg.get("industry_mix_pct", {}),
            "jobs_housing_ratio": compute_jhr(sg),
            "road_density_km_per_km2": rd.get("road_density_km_per_km2"),
            "bus_density_per_km2": bs.get("bus_density_per_km2"),
            "station_catchment_pct": sg.get("station_catchment_pct", {"500m": None, "1km": None}),
            "isochrone": iso_stats_for_region(sgis, region),
        }

    stats = {
        "meta": meta,
        "regions": {
            "pangyo":  reg("pangyo",  "한국테크노밸리(제1판교)", "판교"),
            "cheongna": reg("cheongna", "인천 청라 국제업무단지", "청라국제도시"),
        },
    }

    out = C.DATA_OUT / "stats.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"✓ stats.json 저장: {out}")
    return stats

def load_boundary_method(region: str) -> str | None:
    p = C.DATA_OUT / f"boundary_{region}.geojson"
    if not p.exists():
        return None
    d = load_json(p)
    if d.get("type") == "FeatureCollection":
        feats = d.get("features", [])
        return feats[0].get("properties", {}).get("method") if feats else None
    return d.get("properties", {}).get("method")

def compute_jhr(sg: dict) -> float | None:
    workers = sg.get("workers")
    pop = sg.get("population")
    if workers and pop and pop > 0:
        return round(workers / pop, 4)
    return None

if __name__ == "__main__":
    C.ensure_out()
    print("=== 08_build_stats.py ===")
    build()
    print("✓ 08_build_stats.py 완료")
