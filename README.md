# 판교 vs 청라 — 스마트시티 공간 비교분석

> 가천대학교 스마트시티학과 · 스마트시티 이론과 실제 기말과제 2026  
> GitHub Pages 정적 배포 (서버·DB 없음)

## 분석 개요

| 구분 | 한국테크노밸리(제1판교) | 인천 청라 국제업무단지 |
|------|------------------------|----------------------|
| 성격 | 성공 사례 | 저조 사례 |
| 핵심역 | 판교 (경강선·신분당선) | 청라국제도시 (공항철도) |
| 데이터 기준 | 아래 메타 참조 | 아래 메타 참조 |

## 데이터 기준일 및 출처

| 항목 | 기준일 | 출처 |
|------|--------|------|
| 지하철 네트워크 | 2026-05-04 | 제공 (nodes.tsv / links.tsv) |
| 토지이용 — 인천(청라) | 2026-04-12 | AL_D154_28 토지이용계획정보 |
| 토지이용 — 경기(판교) | 2026-04-12 | AL_D154_41 토지이용계획정보 |
| 지구단위계획구역(판교 경계) | 2026-05-01 | UPIS_005_20260501_41000 |
| 인구·가구 | 2024년 | SGIS 집계구 통계 |
| 사업체·종사자 | 2023년 | SGIS 집계구 통계 |
| 건축물 표제부 | API 수집 | 건축HUB (공공데이터포털) |
| 도로망 | 2026-06-17 | south-korea-260617.osm.pbf |
| 버스정류장 | 2025-10-31 | 국토교통부 |

## 방법론 주요 사항

- **등시간권 egress 보정**: 지하철 네트워크에서 각 역까지 최단시간 계산 후  
  잔여시간 × 보행속도(1.333 m/s) 반경(최대 1,600 m) 버퍼 → union  
  → 보고서 수치와 동일 소스(stats.json) 사용
- **면적비례 배분**: 대상 폴리곤 P, 집계구 c → w = area(P∩c)/area(c)  
  배분값 = Σ w·value_c (구역 통계, 등시간권 통계 모두 동일 함수)
- **판교 구역경계 방법**: AL_D154_41 존재 시 업무·상업 용도 필지 dissolve (우선),  
  없을 시 수동 GeoJSON → UPIS_C_UQ161 bbox clip 순으로 fallback  
  (실제 사용 방법은 stats.json meta.pangyo_boundary_method 참조)
- **좌표계**: 면적·거리 계산 EPSG:5179, 웹 출력 EPSG:4326  
  AL_D154 원본 EPSG:5186, UPIS_C_UQ161 원본 EPSG:5174 → 모두 5179로 통일 후 계산

## 전처리 재현

```bash
# 의존 패키지 설치
pip install geopandas pandas shapely scipy pyproj pyogrio requests

# 단계별 실행 (data_raw/ 에 원본 배치 후)
python pipeline/01_boundary.py   # 구역경계 GeoJSON
python pipeline/02_landuse.py    # 토지이용 GeoJSON
python pipeline/03_buildings.py  # 건축물대장 API 수집
python pipeline/04_subway_graph.py  # 지하철 그래프
python pipeline/05_isochrone.py     # 등시간권
python pipeline/06_sgis_join.py     # 인구·사업체 배분
python pipeline/07_osm_roads.py     # 도로 밀도
python pipeline/07b_bus.py          # 버스 밀도
python pipeline/08_build_stats.py   # stats.json 통합
```

## 웹 로컬 실행

```bash
cd web
cp .env.example .env          # VITE_VWORLD_KEY 설정
npm install
npm run dev
```

## GitHub Pages 배포

1. Repository → Settings → Secrets → `VITE_VWORLD_KEY` 추가
2. main 브랜치 push → Actions 자동 빌드 → gh-pages 배포

## API 키 보안

- V-World WMTS 키: `.env` (로컬) / GitHub Secret (CI)  
- 건축HUB 키: `pipeline/` 스크립트 전용, 웹 코드에 포함 금지  
- `data_raw/` 전체 gitignore
