"""
live_test.py - End-to-end live test of the Adaptive GRE Prep API
Run: python live_test.py
"""
import urllib.request
import json

BASE = "http://localhost:8000"


def call(method, path, body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


print("=" * 60)
print("  ADAPTIVE GRE PREP API — LIVE END-TO-END TEST")
print("=" * 60)

# 1. Health check
health = call("GET", "/health")
print(f"\n[1] GET /health           -> {health}")

# 2. Create session
session = call("POST", "/sessions")
sid = session["session_id"]
print(f"\n[2] POST /sessions")
print(f"    session_id  : {sid}")
print(f"    init_theta  : {session['initial_theta']}")

# 3-10. Answer 4 questions, alternating correct / wrong
ANSWERS = [0, 1, 0, 1]  # option indices (0=first, 1=second)
prev_theta = session["initial_theta"]

for i, opt_idx in enumerate(ANSWERS):
    # Get next question
    q_resp = call("GET", f"/next-question/{sid}")
    q = q_resp["question"]
    chosen = q["options"][opt_idx]

    # Submit answer
    ans = call("POST", "/submit-answer", {
        "session_id": sid,
        "question_id": q["id"],
        "selected_answer": chosen,
    })

    direction = "UP" if ans["updated_theta"] > ans["previous_theta"] else "DOWN"
    print(
        f"\n[Q{i+1}] Topic={q['topic']:<22} diff={q['difficulty']:.2f} | "
        f"correct={str(ans['correct']):<5} | "
        f"theta {ans['previous_theta']:.4f} {direction} {ans['updated_theta']:.4f}"
    )

# 11. Session status
status = call("GET", f"/sessions/{sid}/status")
print(f"\n[11] GET /sessions/status")
print(f"     questions_answered : {status['questions_answered']}")
print(f"     current_theta      : {status['current_ability_theta']}")
print(f"     completed          : {status['completed']}")

# 12. Generate study plan
plan = call("POST", "/generate-plan", {"session_id": sid})
print(f"\n[12] POST /generate-plan")
print(f"     final_theta        : {plan['final_theta']}")
print(f"     performance_summary: {plan['performance_summary']}")
print(f"     study steps ({len(plan['steps'])}):")
for step in plan["steps"]:
    print(f"       Step {step['step']}: [{step['focus']}] {step['action'][:80]}...")

print("\n" + "=" * 60)
print("  ALL ENDPOINTS TESTED SUCCESSFULLY")
print("=" * 60)
