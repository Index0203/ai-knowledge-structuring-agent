"""Run the four Node AI Assistant intents against a real document node.

Usage (inside the compose network):

    docker compose run --rm --no-deps -v "<repo>/scripts:/scripts:ro" backend \
        python /scripts/check_node_assistant.py <document-id> [node-index]
"""

import json
import sys
import time
import urllib.request

API_BASE_URL = "http://backend:8000/api/v1"
INTENTS = ("explain", "example", "deep_dive", "quiz")
POLL_INTERVAL_SECONDS = 2.0
MAX_POLLS = 90


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.loads(response.read().decode())


def post_json(url: str, payload: dict) -> dict:
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST")
    request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode())


def wait_for_answer(question_id: str) -> dict:
    for _ in range(MAX_POLLS):
        payload = get_json(f"{API_BASE_URL}/questions/{question_id}")
        if payload["status"] in {"answered", "insufficient_evidence", "failed"}:
            return payload
        time.sleep(POLL_INTERVAL_SECONDS)
    raise SystemExit("assistant timed out")


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit("usage: check_node_assistant.py <document-id> [node-index]")
    document_id = sys.argv[1]
    node_index = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    tree = get_json(f"{API_BASE_URL}/documents/{document_id}/knowledge-tree")["tree"]
    chapter = tree["children"][node_index]
    node = chapter["children"][0] if chapter["children"] else chapter
    print(f"node: {node['title']} (id={node['id']})")

    for intent in INTENTS:
        submitted = post_json(f"{API_BASE_URL}/knowledge-nodes/{node['id']}/questions", {"intent": intent})
        answer = wait_for_answer(submitted["question_id"])
        print(f"\n=== {intent} | status={answer['status']} mode={answer['answer_mode']} ===")
        print("answer:", (answer["answer"] or answer["error_message"] or "")[:400])
        for index, citation in enumerate(answer["citations"][:3], start=1):
            print(f"  [{index}] {citation['section_title']} · {citation['quote'][:70]}")
        for index, item in enumerate(answer["quiz_items"], start=1):
            print(f"  Q{index}: {item['question']}")
            print(f"     A: {item['answer'][:120]}")
            print(f"     出处: {len(item['citations'])} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
