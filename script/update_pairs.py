# json_pairs_diff.py
# -*- coding: utf-8 -*-

from __future__ import annotations
import shutil
import json
from pathlib import Path
from typing import Any, List, Sequence, Tuple, Union, Optional
from global_config import Global_Config
from calculate_score_total import score_pairs_to_list

Pair = Tuple[str, str]


def _load_json(path: Union[str, Path]) -> Any:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"找不到文件：{p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _extract_pairs(data: Any) -> Sequence[Sequence[Any]]:
    """
    兼容两种结构：
    1) 顶层直接有 pairs: {"pairs": [...], "connected": [...]}
    2) 旧结构可能包了一层 by_name: {"by_name": {"pairs": [...], "connected": [...]}}
    """
    if isinstance(data, dict) and "pairs" in data:
        return data["pairs"]
    if isinstance(data, dict) and "by_name" in data and isinstance(data["by_name"], dict) and "pairs" in data["by_name"]:
        return data["by_name"]["pairs"]
    raise ValueError("JSON 中未找到 pairs 字段（支持顶层 pairs 或 by_name.pairs）")


def _canon_pair(pair: Sequence[Any]) -> Pair:
    """
    规范化一条 pair：
    - 必须是长度为2
    - 元素转为字符串（触点名一般就是字符串）
    - 对内部做排序，保证 (A,B) 和 (B,A) 视为同一条
    """
    if not isinstance(pair, (list, tuple)) or len(pair) != 2:
        raise ValueError(f"非法 pair：{pair}（必须是长度为2的数组/元组）")
    a, b = str(pair[0]).strip(), str(pair[1]).strip()
    if not a or not b:
        raise ValueError(f"非法 pair：{pair}（触点名不能为空）")
    return tuple(sorted((a, b)))


def _pairs_to_set(pairs: Sequence[Sequence[Any]]) -> set[Pair]:
    """
    转为集合去重（如果原文件里有重复 pair，会自动去重）。
    """
    s: set[Pair] = set()
    for p in pairs:
        s.add(_canon_pair(p))
    return s


def diff_json_pairs(
    old_json_path: Union[str, Path],
    new_json_path: Union[str, Path],
) -> Tuple[List[List[str]], List[List[str]]]:
    """
    对比两个 JSON 文件的 pairs，返回：
    - add_pairs: 新增的接线对（在 new 中但不在 old 中）
    - undo_pairs: 撤去的接线对（在 old 中但不在 new 中）

    返回类型为 List[List[str]]，每个元素都是 [name1, name2]，且 name1 <= name2（稳定输出）。
    """
    old_data = _load_json(old_json_path)
    new_data = _load_json(new_json_path)

    old_pairs = _extract_pairs(old_data)
    new_pairs = _extract_pairs(new_data)

    old_set = _pairs_to_set(old_pairs)
    new_set = _pairs_to_set(new_pairs)

    add_set = new_set - old_set
    undo_set = old_set - new_set

    # 稳定排序输出，便于日志与测试
    add_pairs = [list(p) for p in sorted(add_set, key=lambda x: (x[0], x[1]))]
    undo_pairs = [list(p) for p in sorted(undo_set, key=lambda x: (x[0], x[1]))]

    Global_Config.add_pairs = score_pairs_to_list(add_pairs,Global_Config.test_rule)
    Global_Config.undo_pairs = score_pairs_to_list(undo_pairs,Global_Config.test_rule)

    shutil.copy(Global_Config.new_result_json, Global_Config.old_result_json)

    return add_pairs, undo_pairs

if __name__ == '__main__':
    add_pairs, undo_pairs = diff_json_pairs(
        old_json_path="D:/Project/videoProject/data/result/old/result.json",
        new_json_path="D:/Project/videoProject/data/result/new/result.json",
    )
    print("新增：", add_pairs)
    print("撤去：", undo_pairs)