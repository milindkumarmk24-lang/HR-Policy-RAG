"""End-to-end check against a running server: asks one question, prints the
answer, the cited pages and, once scored, the RAGAS scores.

    python scripts/smoke_test.py                      # http://localhost:8000
    python scripts/smoke_test.py https://your-space.hf.space
"""
import json
import sys
import time
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


def main() -> None:
    health = call("GET", "/api/health")
    print("health:", json.dumps(health, indent=2))
    q = "How many sick days do I get, and when do I need a medical certificate?"
    res = call("POST", "/api/chat", {"question": q})
    print(f"\nQ: {q}\nroute: {res['plan']['route']}  mode: {res['mode']}\n\n{res['answer']}\n")
    for s in res["sources"]:
        mark = "cited" if s["cited"] else "     "
        print(f"  [{s['id']}] {mark} p.{s['page']:<3} {s['section']}  (faiss #{s['faiss_rank']} -> rerank #{s['rerank_rank']})")
    if res["eval"]["eval_status"] == "queued":
        print("\nWaiting for RAGAS", end="", flush=True)
        for _ in range(120):
            time.sleep(5)
            ev = call("GET", f"/api/evals/{res['query_id']}")
            if ev["eval_status"] not in ("queued", "running"):
                break
            print(".", end="", flush=True)
        print(f"\nRAGAS {ev['eval_status']}: {ev['scores']}")
        if ev.get("eval_error"):
            print("errors:", ev["eval_error"])


if __name__ == "__main__":
    main()
