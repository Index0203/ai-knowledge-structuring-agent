"""Re-run the pipeline for an already uploaded document and report the outcome.

Usage (inside the compose network):

    docker compose run --rm --no-deps -v "<repo>/scripts:/scripts:ro" backend \
        sh -c "python /scripts/reprocess_document.py <document-id> [question]"
"""

import sys
import time
import json
import urllib.request

API_BASE_URL = "http://backend:8000"
POLL_INTERVAL_SECONDS = 3.0
MAX_POLLS = 200


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.loads(response.read().decode())


def post_json(url: str, payload: dict | None = None) -> dict:
    request = urllib.request.Request(url, method="POST", data=json.dumps(payload or {}).encode("utf-8"))
    request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode())


def wait_for(label: str, url: str, is_done) -> dict:
    for _ in range(MAX_POLLS):
        payload = get_json(url)
        state = is_done(payload)
        if state == "done":
            return payload
        if state == "failed":
            raise SystemExit(f"{label} failed: {payload}")
        time.sleep(POLL_INTERVAL_SECONDS)
    raise SystemExit(f"{label} timed out")


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit("usage: reprocess_document.py <document-id> [question] [--tree-only]")
    document_id = sys.argv[1]
    tree_only = "--tree-only" in sys.argv
    arguments = [argument for argument in sys.argv[2:] if not argument.startswith("--")]
    question = arguments[0] if arguments else "这份文档的主要内容是什么？"

    print(f"document {document_id}")
    if not tree_only:
        print("queued processing:", post_json(f"{API_BASE_URL}/api/v1/documents/{document_id}/processing"))
        started = time.perf_counter()
        status = wait_for(
            "indexing",
            f"{API_BASE_URL}/api/v1/documents/{document_id}",
            lambda payload: "done"
            if payload["status"] == "indexed"
            else "failed"
            if payload["status"] == "failed"
            else "pending",
        )
        print(
            f"indexed in {time.perf_counter() - started:.1f}s: chunks={status['chunk_count']} "
            f"ocr_pages={status['ocr_page_count']} pages={status['page_count']}"
        )

    print("queued knowledge tree:", post_json(f"{API_BASE_URL}/api/v1/documents/{document_id}/knowledge-tree"))
    tree = wait_for(
        "knowledge tree",
        f"{API_BASE_URL}/api/v1/documents/{document_id}/knowledge-tree",
        lambda payload: "done"
        if payload["status"] == "ready"
        else "failed"
        if payload["status"] == "failed"
        else "pending",
    )
    node = tree["tree"]["children"][0]
    print(f"tree ready in mode '{tree['mode']}': root='{tree['tree']['title']}' first node='{node['title']}'")
    print("outline:")
    for chapter in tree["tree"]["children"][:8]:
        print(f"  - {chapter['title']}")
        print(f"      摘要: {chapter['summary'][:80]}")
        print(f"      关键词: {', '.join(chapter['keywords']) or '（无）'}")
        for section in chapter["children"][:5]:
            print(f"      · {section['title']}")
            print(f"          摘要: {section['summary'][:80]}")
            print(f"          关键词: {', '.join(section['keywords']) or '（无）'}")

    submission = post_json(
        f"{API_BASE_URL}/api/v1/knowledge-nodes/{node['id']}/questions",
        {"question": question},
    )
    print("submitted question:", submission["question_id"])
    answer = wait_for(
        "question",
        f"{API_BASE_URL}/api/v1/questions/{submission['question_id']}",
        lambda payload: "done" if payload["status"] in {"answered", "insufficient_evidence", "failed"} else "pending",
    )
    print(f"status={answer['status']} mode={answer['answer_mode']} citations={len(answer['citations'])}")
    print("answer:", (answer["answer"] or answer["error_message"] or "")[:300])
    for citation in answer["citations"][:3]:
        location = f"p.{citation['page_number']}" if citation["page_number"] else citation["section_title"]
        print(f"  citation: {location} · {citation['quote'][:100]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
