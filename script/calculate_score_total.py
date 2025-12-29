import json
from typing import Any, Dict, List, Tuple, Optional,Union
from global_config import Global_Config

def _canonical_pair(a: str, b: str) -> Tuple[str, str]:
    """把触点对规范化为有序二元组，用于忽略顺序匹配。"""
    return (a, b) if a <= b else (b, a)


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_answer_map(answer_json_path: str) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """
    从参考答案（长动.json）建立映射：
    key: (node1, node2) 的规范化二元组
    value: { "score": int/float, "id": 可选, "nodes": [..] }
    若存在重复 key，默认保留 score 更高的一条。
    """
    data = _load_json(answer_json_path)

    # 长动.json通常是 list[ {id, nodes:[a,b], score} ]；也兼容 dict 包裹的情况
    items: List[Dict[str, Any]]
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        # 尝试常见字段承载
        if isinstance(data.get("data"), list):
            items = data["data"]
        elif isinstance(data.get("items"), list):
            items = data["items"]
        else:
            raise ValueError(f"无法识别参考答案JSON结构：{answer_json_path}")
    else:
        raise ValueError(f"参考答案JSON必须为list或dict：{answer_json_path}")

    answer_map: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for item in items:
        nodes = item.get("nodes")
        if not isinstance(nodes, list) or len(nodes) != 2:
            continue

        a, b = str(nodes[0]), str(nodes[1])
        key = _canonical_pair(a, b)

        score = item.get("score", 0)
        try:
            score_val = float(score)
        except Exception:
            score_val = 0.0

        if key not in answer_map or score_val > float(answer_map[key].get("score", 0) or 0):
            answer_map[key] = {
                "score": score_val,
                "id": item.get("id"),
                "nodes": [a, b],
            }

    return answer_map


def evaluate_pairs(
    output_json_path: str,
    answer_json_path: str,
    print_console: bool = True
) -> Dict[str, Any]:
    """
    以 answer_json_path 为参考答案，对比 output_json_path 中的 pairs。
    - 忽略顺序：a-b 与 b-a 视为同一对
    - 匹配到则获得对应 score 分数
    返回：
    {
      "total_score": float,
      "matched": [ {"pair":[a,b], "score": float, "answer_id":..., "answer_nodes":[...]} ],
      "unmatched": [ {"pair":[a,b]} ],
      "pairs_count": int,
      "matched_count": int
    }
    """
    answer_map = _build_answer_map(answer_json_path)
    out = _load_json(output_json_path)

    if not isinstance(out, dict) or "pairs" not in out:
        raise ValueError(f"output.json 结构必须为包含 'pairs' 的对象：{output_json_path}")

    pairs = out.get("pairs")
    if not isinstance(pairs, list):
        raise ValueError(f"'pairs' 必须为list：{output_json_path}")

    total_score: float = 0.0
    matched: List[Dict[str, Any]] = []
    unmatched: List[Dict[str, Any]] = []

    for p in pairs:
        if not isinstance(p, list) or len(p) != 2:
            # 非法pair直接跳过，也可以改为 raise
            continue

        a, b = str(p[0]), str(p[1])
        key = _canonical_pair(a, b)

        if key in answer_map:
            info = answer_map[key]
            score_val = float(info.get("score", 0.0) or 0.0)
            total_score += score_val
            matched.append({
                "pair": [a, b],
                "score": score_val,
                "answer_id": info.get("id"),
                "answer_nodes": info.get("nodes"),
            })
        else:
            unmatched.append({"pair": [a, b]})

    result = {
        "total_score": total_score,
        "matched": matched,
        "unmatched": unmatched,
        "pairs_count": len(pairs),
        "matched_count": len(matched),
    }

    if print_console:
        print("======== Pairs评分结果 ========")
        print(f"参考答案: {answer_json_path}")
        print(f"待评估:   {output_json_path}")
        print(f"pairs总数: {result['pairs_count']}，匹配数: {result['matched_count']}，总分: {result['total_score']}")
        print("\n-- 匹配到的pairs（pair -> score）--")
        for m in matched:
            # 展示pair本身 + 对应参考nodes/id，便于排查
            print(f"{m['pair']} -> +{m['score']}  (answer_nodes={m['answer_nodes']}, answer_id={m['answer_id']})")
        print("\n-- 未匹配的pairs --")
        for u in unmatched:
            print(f"{u['pair']}")
        print("================================")

    return result


def score_pairs_to_list(
    pairs_input: Union[List[Any], Tuple[Any, ...]],
    answer_json_path: str,
    answer_map: Optional[Dict[Tuple[str, str], Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    返回 list[dict]：
    - 输入可以是单个触点对：["a","b"] 或 ("a","b")
    - 也可以是多个触点对：[[ "a","b" ],[ "c","d" ]] 或 [("a","b"),("c","d")]
    - 也支持空列表/空元组：[] / ()，直接返回 []

    返回示例：
    [
      {"pair": ["a","b"], "score": 10.0},
      {"pair": ["c","d"], "score": 0.0},
    ]
    """
    if not isinstance(pairs_input, (list, tuple)):
        raise ValueError("pairs_input 必须为 list 或 tuple")

    # 关键修复：空输入直接返回空结果
    if len(pairs_input) == 0:
        return []

    # 统一整理为“触点对列表”
    is_multi = (
        isinstance(pairs_input[0], (list, tuple))
        and len(pairs_input[0]) == 2
    )

    if is_multi:
        pairs_list = list(pairs_input)
    else:
        if len(pairs_input) != 2:
            raise ValueError("单个触点对输入必须长度为2，例如 ['A','B']")
        pairs_list = [pairs_input]

    # 构建/复用标准答案映射
    if answer_map is None:
        answer_map = _build_answer_map(answer_json_path)

    results: List[Dict[str, Any]] = []

    for p in pairs_list:
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise ValueError(f"发现非法触点对（必须长度为2）：{p}")

        a, b = str(p[0]), str(p[1])
        key = _canonical_pair(a, b)

        if key in answer_map:
            score_val = float(answer_map[key].get("score", 0.0) or 0.0)
            results.append({"pair": [a, b], "score": score_val})
        else:
            results.append({"pair": [a, b], "score": 0.0})

    return results

# 示例（如需在本文件直接运行测试，可取消注释）
if __name__ == "__main__":
     evaluate_pairs(Global_Config.new_result_json, Global_Config.test_rule)
