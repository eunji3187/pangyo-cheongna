"""
프로젝트 공통 설정: 경로, API 키, 좌표계, 파라미터
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data_raw"
DATA_OUT = ROOT / "web" / "public" / "data"

# ── 원본 데이터 경로 ─────────────────────────────────────────────
SUBWAY_NODES = DATA_RAW / "subway_network" / "network" / "nodes.tsv"
SUBWAY_LINKS = DATA_RAW / "subway_network" / "network" / "links.tsv"

AL_D154_28  = DATA_RAW / "AL_D154_28_20260412.shp"   # 인천 토지이용 EPSG:5186 cp949
AL_D154_41  = DATA_RAW / "AL_D154_41_20260412.shp"   # 경기 토지이용 EPSG:5186 cp949
UPIS_UQ161  = DATA_RAW / "UPIS_C_UQ161.shp"          # 경기 지구단위계획구역 EPSG:5174 cp949
PANGYO_MANUAL = DATA_RAW / "boundary" / "pangyo_manual.geojson"

BUS_CSV = ROOT / "국토교통부_전국 버스정류장 위치정보_20251031.csv"
OSM_PBF = ROOT / "south-korea-260617.osm.pbf"

SGIS_DIR      = DATA_RAW / "sgis"
SGIS_BOUNDARY = DATA_RAW / "sgis" / "bnd_oa_31_2025_2Q.shp"   # 경기도 집계구 경계 EPSG:5179
SGIS_POP_CSV  = DATA_RAW / "sgis" / "31_2024년_인구총괄(총인구).csv"
SGIS_HH_CSV   = DATA_RAW / "sgis" / "31_2024년_가구총괄.csv"
SGIS_WK_CSV   = DATA_RAW / "sgis" / "31_2023년_산업분류별(10차_대분류)_총괄종사자수.csv"
SGIS_BIZ_CSV  = DATA_RAW / "sgis" / "31_2023년_산업분류별(10차_대분류)_총괄사업체수.csv"
# 인천 서구 CSV (청라 추정용 — 집계구 경계 SHP 미확보 시 단순 면적비례 추정)
SGIS_POP23_CSV  = DATA_RAW / "sgis" / "23080_2024년_인구총괄(총인구).csv"
SGIS_HH23_CSV   = DATA_RAW / "sgis" / "23080_2024년_가구총괄.csv"
SGIS_WK23_CSV   = DATA_RAW / "sgis" / "23080_2023년_산업분류별(10차_대분류)_총괄종사자수.csv"
SGIS_BIZ23_CSV  = DATA_RAW / "sgis" / "23080_2023년_산업분류별(10차_대분류)_총괄사업체수.csv"
SEOGU_AREA_HA   = 15918.0   # 인천 서구 행정면적(ha) — 청라 면적비례 추정 기준

# ── API 키 ───────────────────────────────────────────────────────
# V-World: 웹에서 사용 (.env / GitHub Secret) — 여기서는 읽지 않음
BUILDING_HUB_KEY = os.getenv(
    "BUILDING_HUB_KEY",
    "51b085b7cc7cd32e1d3bdaeb0901ac8f820e1cbc00f65854764dcda593d5a8c9",
)

# ── 좌표계 ───────────────────────────────────────────────────────
CRS_IN  = "EPSG:5186"   # AL_D154 원본
CRS_5174 = "EPSG:5174"  # UPIS UQ161 원본
CRS_CALC = "EPSG:5179"  # 면적·거리 계산
CRS_WEB  = "EPSG:4326"  # 웹 출력

# ── 분석 파라미터 ────────────────────────────────────────────────
NETWORK_CUTOFF = "2026-05-04"
WALK_SPEED_M_S = 1.333          # 보행속도 m/s
WALK_CAP_M     = 1600           # 보행 최대반경 m
ISO_MINUTES    = [10, 20, 30, 40, 50, 60]

# 판교역 중심 좌표 (WGS84)
PANGYO_STATION_LNG = 127.1112
PANGYO_STATION_LAT = 37.3947
PANGYO_1ST_LNG     = 127.1058
PANGYO_1ST_LAT     = 37.4045

# 청라국제도시역 (공항철도)
CHEONGNA_STATION_NAME = "청라국제도시"

# 지역 시군구코드
PANGYO_SIGUNGU_CD  = "41135"   # 성남 분당구
CHEONGNA_SIGUNGU_CD = "28260"  # 인천 서구

# ── 출력 경량화 ──────────────────────────────────────────────────
SIMPLIFY_TOL_M = 1    # simplify tolerance (m, 5179 기준)
MAX_GEOJSON_MB = 8    # 단일 GeoJSON 상한

def ensure_out():
    DATA_OUT.mkdir(parents=True, exist_ok=True)
