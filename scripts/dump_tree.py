"""Print the persisted knowledge tree with summaries.

Usage (inside the compose network):

    docker compose run --rm --no-deps -v "<repo>/scripts:/scripts:ro" backend \
        python /scripts/dump_tree.py <document-id> [max-depth]
"""

import json
import sys
import urllib.request

API_BASE_URL = "http://backend:8000/api/v1"


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit("usage: dump_tree.py <document-id> [max-depth]")
    document_id = sys.argv[1]
    max_depth = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    with urllib.request.urlopen(f"{API_BASE_URL}/documents/{document_id}/knowledge-tree", timeout=60) as response:
        payload = json.loads(response.read().decode())
    if payload.get("tree") is None:
        print(f"tree status: {payload.get('status')} error: {payload.get('error_message')}")
        return 1

    def walk(node: dict, depth: int) -> None:
        summary = " ".join(node["summary"].split())[:56]
        keywords = "、".join(node["keywords"][:4])
        print(f"{'  ' * depth}- {node['title']}")
        print(f"{'  ' * depth}    摘要: {summary}")
        print(f"{'  ' * depth}    关键词: {keywords or '（无）'}")
        if depth < max_depth:
            for child in node["children"]:
                walk(child, depth + 1)

    print(f"mode: {payload['mode']}")
    walk(payload["tree"], 0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
