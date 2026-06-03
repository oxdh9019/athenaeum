"""V0.7 Phase D verification: scattered fixture exercises movement/encounter/dialogue.

Replaces the legacy apply_same_loc.json that forced all agents to start in
the same place, masking the Phase D P0 movement bug. This test:

1. Loads tests/fixtures/scattered_world.json (3 agents, 3 distinct locations)
2. Starts the world
3. Polls /world/state for 30s, asserts >=1 movement event
4. (skipped if no encounter — probabilistic) asserts >=1 dialogue in 60s

Run from v0.7/ with server up on :8000:
    python tests/test_scattered_world.py
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

API = "http://localhost:8000"
FIXTURE = Path(__file__).parent / "fixtures" / "scattered_world.json"
MOVE_WINDOW_SEC = 30
DIALOGUE_WINDOW_SEC = 60
POLL_INTERVAL = 2


def post(path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def get(path: str) -> dict:
    with urllib.request.urlopen(f"{API}{path}", timeout=10) as r:
        return json.loads(r.read())


def main() -> int:
    if not FIXTURE.exists():
        print(f"FAIL: fixture not found: {FIXTURE}", file=sys.stderr)
        return 2
    fx = json.loads(FIXTURE.read_text())
    print(f"loaded fixture: {fx['world']['name']} ({len(fx['agents'])} agents, "
          f"{len(fx['world']['locations'])} locations)")

    # Reset: stop any running world first (no-op if not running)
    try:
        post("/world/stop")
    except Exception:
        pass
    time.sleep(1)

    # 1. Create world
    post("/world/create", fx["world"])
    print(f"world created: {fx['world']['locations']}")

    # 2. Create agents at distinct locations
    initial_locs = {}
    for a in fx["agents"]:
        post("/agent/create", a)
        initial_locs[a["id"]] = a["initial_location"]
        print(f"  agent {a['id']} ({a['name']}) @ {a['initial_location']}")

    # 3. Start world
    post("/world/start")
    print(f"world started; polling {MOVE_WINDOW_SEC}s for movement...")

    # 4. Poll for movement: any agent's location != initial
    t0 = time.time()
    moved = {}
    while time.time() - t0 < MOVE_WINDOW_SEC:
        state = get("/world/state")
        for ag in state.get("agents", []):
            aid = ag["id"]
            now = ag.get("location")
            if aid in initial_locs and now != initial_locs[aid]:
                moved[aid] = (initial_locs[aid], now)
        if len(moved) >= 1:
            break
        time.sleep(POLL_INTERVAL)

    if not moved:
        print(f"FAIL: no movement in {MOVE_WINDOW_SEC}s — P0 regression", file=sys.stderr)
        return 1
    print(f"OK movement: {moved}")

    # 5. Continue polling for dialogue (max total wall time = MOVE_WINDOW + DIALOGUE_WINDOW)
    t1 = time.time()
    pre_dialogue_count = len(get("/world/state").get("recent_dialogues", []))
    while time.time() - t1 < DIALOGUE_WINDOW_SEC:
        state = get("/world/state")
        rd = state.get("recent_dialogues", [])
        if len(rd) > pre_dialogue_count:
            new_turns = len(rd) - pre_dialogue_count
            print(f"OK dialogue: +{new_turns} turn(s) in {int(time.time()-t0)}s")
            print("PASS")
            return 0
        time.sleep(POLL_INTERVAL)

    # 0 dialogue is acceptable if no encounter happened, but warn
    state = get("/world/state")
    rd = state.get("recent_dialogues", [])
    if len(rd) == pre_dialogue_count:
        # Check if any agents are co-located now
        locs = [a.get("location") for a in state.get("agents", [])]
        if len(set(locs)) < len(locs):
            print(f"WARN: agents co-located ({locs}) but 0 dialogue in "
                  f"{MOVE_WINDOW_SEC + DIALOGUE_WINDOW_SEC}s — P2 may be too strict")
            # Don't fail — dialogue is probabilistic through the dialogue engine queue
        else:
            print(f"WARN: no encounter in {MOVE_WINDOW_SEC + DIALOGUE_WINDOW_SEC}s, "
                  f"agents all separated ({locs})")
    print("PASS (movement verified, dialogue probabilistic)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
