# wiring_exporter.py
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

import pandas as pd

Pair = Tuple[int, int]


def _file_looks_like_xlsx(path: Union[str, Path]) -> bool:
    """通过文件头判断是否为 xlsx（xlsx 本质是 zip，常见头为 PK\\x03\\x04）。"""
    p = Path(path)
    with p.open("rb") as f:
        sig = f.read(4)
    return sig == b"PK\x03\x04"


def load_labels(
    label_path: Union[str, Path],
    name_col: int = 0,
    start_index: int = 1,
) -> Dict[int, str]:
    """
    从标签文件读取：行号 -> 触点名

    约定：
    - 行号从 start_index 开始（默认 1，对应你说的“csv 行号”）
    - 默认读取第 1 列（name_col=0）作为触点名列
    - header=None（即不把第一行当表头）

    支持：
    - csv（自动尝试常见编码）
    - xlsx 或“xlsx 误命名为 csv”（通过文件头识别）
    """
    label_path = Path(label_path)

    if label_path.suffix.lower() in {".xlsx", ".xls", ".xlsm", ".xltx", ".xltm"} or _file_looks_like_xlsx(label_path):
        df = pd.read_excel(label_path, header=None, engine="openpyxl")
    else:
        last_err = None
        for enc in ("utf-8-sig", "gb18030", "gbk", "utf-16", "latin1"):
            try:
                df = pd.read_csv(label_path, header=None, encoding=enc)
                last_err = None
                break
            except Exception as e:
                last_err = e
        if last_err is not None:
            raise ValueError(f"无法读取标签文件：{label_path}，请确认格式/编码是否正确") from last_err

    if name_col not in df.columns:
        raise ValueError(f"标签文件列数不足：需要第 {name_col+1} 列作为触点名列")

    values: List[str] = []
    for v in df[name_col].tolist():
        if pd.isna(v):
            continue
        s = str(v).strip()
        if s:
            values.append(s)

    return {start_index + i: values[i] for i in range(len(values))}


def normalize_pairs(pairs: Iterable[Pair]) -> List[Pair]:
    """
    规范化接线对：
    - 转 int
    - 视为无向边：小号在前
    - 去重
    - 过滤自环 (a,a)
    """
    seen = set()
    out: List[Pair] = []
    for a, b in pairs:
        a, b = int(a), int(b)
        if a == b:
            continue
        x, y = (a, b) if a < b else (b, a)
        if (x, y) in seen:
            continue
        seen.add((x, y))
        out.append((x, y))
    return out


def _connected_components(adj: Dict[int, set]) -> List[set]:
    """无向图连通分量。"""
    visited = set()
    comps: List[set] = []
    for node in sorted(adj.keys()):
        if node in visited:
            continue
        q = deque([node])
        visited.add(node)
        comp = set()
        while q:
            v = q.popleft()
            comp.add(v)
            for nb in adj[v]:
                if nb not in visited:
                    visited.add(nb)
                    q.append(nb)
        comps.append(comp)
    return comps


def _order_component(comp: set, adj: Dict[int, set]) -> List[int]:
    """
    把一个连通分量输出为“可复现”的节点顺序：
    - 若该分量是简单路径/简单环（max degree <= 2），尽量按路径顺序输出
    - 否则使用 DFS 兜底（对分支结构也适用，但不是唯一链条，仅给出一个确定性顺序）
    """
    deg = {n: sum(1 for nb in adj[n] if nb in comp) for n in comp}
    maxdeg = max(deg.values()) if deg else 0
    endpoints = sorted([n for n, d in deg.items() if d == 1])

    # 简单路径/简单环
    if maxdeg <= 2 and len(comp) >= 2 and (len(endpoints) in (0, 2)):
        start = endpoints[0] if endpoints else min(comp)
        visited = {start}
        order = [start]
        prev = None
        curr = start

        while len(visited) < len(comp):
            candidates = sorted([x for x in adj[curr] if x in comp and x != prev])
            nxt = next((c for c in candidates if c not in visited), None)
            if nxt is None:
                break
            order.append(nxt)
            visited.add(nxt)
            prev, curr = curr, nxt

        if len(visited) == len(comp):
            return order

    # DFS 兜底：确定性（邻居升序，入栈 reverse）
    start = min(comp)
    order: List[int] = []
    stack = [start]
    visited = set()

    while stack:
        v = stack.pop()
        if v in visited:
            continue
        visited.add(v)
        order.append(v)
        nbs = sorted([x for x in adj[v] if x in comp and x not in visited], reverse=True)
        stack.extend(nbs)

    # 理论上不会遗漏；保险起见补齐
    for n in sorted(comp):
        if n not in visited:
            order.append(n)

    return order


def merge_pairs_to_connected_sequences(pairs: Sequence[Pair]) -> List[List[int]]:
    """
    功能1：验证并合并接线对之间的连接关系（连通分量）
    返回：每个连通分量一个序列，例如 [[1,2,3], [10,11]]
    """
    pairs_norm = normalize_pairs(pairs)
    adj: Dict[int, set] = defaultdict(set)

    for a, b in pairs_norm:
        adj[a].add(b)
        adj[b].add(a)

    comps = _connected_components(adj)
    return [_order_component(comp, adj) for comp in comps]


def generate_by_name_json(
    pairs: Sequence[Pair],
    label_path: Union[str, Path],
    out_path: Optional[Union[str, Path]] = None,
    name_col: int = 0,
    start_index: int = 1,
    print_console: bool = True,
) -> dict:
    """
    输出/返回结构（不含 by_name 上级结构）：
    {
      "pairs": [[nameA, nameB], ...],
      "connected": [[name1, name2, ...], ...]
    }
    """
    labels = load_labels(label_path, name_col=name_col, start_index=start_index)
    pairs_norm = normalize_pairs(pairs)
    connected = merge_pairs_to_connected_sequences(pairs_norm)

    def name_of(i: int) -> str:
        if i not in labels:
            raise ValueError(f"索引 {i} 超出标签文件范围（标签行数={len(labels)}，起始行号={start_index}）")
        return labels[i]

    pairs_name = [[name_of(a), name_of(b)] for a, b in pairs_norm]
    connected_name = [[name_of(i) for i in seq] for seq in connected]

    data = {
        "pairs": pairs_name,
        "connected": connected_name,
    }

    if print_console:
        print("========== pairs（触点名接线对） ==========")
        for a, b in pairs_name:
            print(f"({a}, {b})")
        print("\n========== connected（按连通合并） ==========")
        for seq in connected_name:
            print("(" + ", ".join(seq) + ")")
        print("==========================================")

    if out_path is not None:
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    return data

