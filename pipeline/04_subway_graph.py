"""
04_subway_graph.py — 지하철 네트워크 그래프 구축

nodes.tsv / links.tsv (UTF-8) 로드
cutoff 2026-05-04 기준 활성 노드·링크 필터
scipy CSR 행렬 → dijkstra 최단시간(초)
검증: 활성 노드 817 / 링크 999

출력: data_raw/subway_network/graph_dist.npz  (노드 인덱스, 거리행렬 sparse)
      data_raw/subway_network/active_nodes.csv
"""
import sys
import json
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import cfg

C = cfg()
CUTOFF = pd.Timestamp(C.NETWORK_CUTOFF)

def load_network():
    if not C.SUBWAY_NODES.exists() or not C.SUBWAY_LINKS.exists():
        print("  nodes.tsv / links.tsv 없음 → 건너뜀")
        return None, None

    nodes = pd.read_csv(C.SUBWAY_NODES, sep="\t", encoding="utf-8")
    links = pd.read_csv(C.SUBWAY_LINKS, sep="\t", encoding="utf-8")

    # cutoff 필터
    def parse_dt(col):
        return pd.to_datetime(col, errors="coerce")

    nodes["_eff"] = parse_dt(nodes.get("effective_begin", nodes.get("begin", pd.NaT)))
    nodes["_beg"] = parse_dt(nodes.get("begin", pd.NaT))
    eff = nodes["_eff"].fillna(nodes["_beg"])
    active_nodes = nodes[eff <= CUTOFF].copy()
    print(f"  활성 노드: {len(active_nodes)} (검증값 817)")

    active_ids = set(active_nodes["id"])
    links["_beg"] = parse_dt(links.get("begin", pd.NaT))
    active_links = links[
        (links["_beg"] <= CUTOFF) &
        links["fromNode"].isin(active_ids) &
        links["toNode"].isin(active_ids)
    ].copy()
    print(f"  활성 링크: {len(active_links)} (검증값 999)")

    return active_nodes, active_links

def build_graph(active_nodes: pd.DataFrame, active_links: pd.DataFrame):
    idx_map = {nid: i for i, nid in enumerate(active_nodes["id"])}
    n = len(active_nodes)

    rows, cols, data = [], [], []
    for _, lnk in active_links.iterrows():
        fi = idx_map.get(lnk["fromNode"])
        ti = idx_map.get(lnk["toNode"])
        if fi is None or ti is None:
            continue
        tft = float(lnk.get("timeFT", 0))
        ttf = float(lnk.get("timeTF", tft))
        rows.append(fi); cols.append(ti); data.append(tft)
        rows.append(ti); cols.append(fi); data.append(ttf)

    mat = csr_matrix((data, (rows, cols)), shape=(n, n))
    return mat, idx_map, active_nodes

def find_core_stations(active_nodes: pd.DataFrame, idx_map: dict) -> dict:
    """핵심역 노드 인덱스 반환"""
    result = {}
    # 판교역
    pg = active_nodes[active_nodes["statnm"] == "판교"]
    if len(pg):
        result["pangyo"] = [idx_map[i] for i in pg["id"] if i in idx_map]
        print(f"  판교역 노드: {list(pg['id'])} → idx {result['pangyo']}")
    # 청라국제도시역
    cr = active_nodes[active_nodes["statnm"] == C.CHEONGNA_STATION_NAME]
    if len(cr):
        result["cheongna"] = [idx_map[i] for i in cr["id"] if i in idx_map]
        print(f"  청라국제도시역 노드: {list(cr['id'])} → idx {result['cheongna']}")
    return result

def run_dijkstra(mat: csr_matrix, source_indices: list) -> np.ndarray:
    """멀티소스 다익스트라: 각 소스에서 실행 후 최솟값"""
    n = mat.shape[0]
    dist = np.full(n, np.inf)
    for src in source_indices:
        d = dijkstra(mat, directed=True, indices=src)
        dist = np.minimum(dist, d)
    return dist

if __name__ == "__main__":
    active_nodes, active_links = load_network()
    if active_nodes is None:
        print("네트워크 데이터 없음. 05_isochrone.py에서 null 처리됩니다.")
        sys.exit(0)

    mat, idx_map, nodes = build_graph(active_nodes, active_links)
    core = find_core_stations(nodes, idx_map)

    out_dir = C.SUBWAY_NODES.parent
    # 노드 좌표 + 거리 저장
    results = {}
    for region, src_idx in core.items():
        dist = run_dijkstra(mat, src_idx)
        results[region] = dist.tolist()

    nodes_out = active_nodes[["id", "statnm", "linenm", "x_5179", "y_5179", "lng", "lat"]].copy()
    nodes_out["idx"] = nodes_out["id"].map(idx_map)

    for region, dist_list in results.items():
        nodes_out[f"dist_s_{region}"] = nodes_out["idx"].apply(
            lambda i: dist_list[int(i)] if pd.notna(i) else None
        )

    nodes_out.to_csv(out_dir / "active_nodes.csv", index=False)
    print(f"\n→ active_nodes.csv 저장 ({len(nodes_out)} 노드)")
    print("OK 04_subway_graph.py done")
