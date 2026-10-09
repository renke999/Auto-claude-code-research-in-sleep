"""Pilot 9c: physician BoN-4 non-inferiority for the v3 judge (re-registration of P8 B1/B2 after v2 was superseded).
Pools: load_pools(1000, seed=5) as in P8; processed in batches of 100 and appended incrementally."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import judges as J
from metaeval import load_pools

HERE = Path(__file__).parent


def main(n=1000, batch=100):
    pools = load_pools(n, seed=5, min_spread=0.0)
    path = HERE / "pilot9c_results.jsonl"
    done = {json.loads(l)["pool"] for l in path.open()} if path.exists() else set()
    for s in range(0, len(pools), batch):
        idx = [pi for pi in range(s, min(s + batch, len(pools))) if pi not in done]
        if not idx:
            continue
        jobs, keys = [], []
        for pi in idx:
            for cid, txt in pools[pi]["completions"].items():
                jobs.append((pools[pi]["ex"], txt, "")); keys.append((pi, cid))
        pres = J.judge_many(jobs, "presence", workers=10)
        com = J.commit3_many(jobs, workers=10)
        with path.open("a") as f:
            for (pi, cid), (ex, _, _), p, c in zip(keys, jobs, pres, com):
                f.write(json.dumps({"pool": pi, "prompt_id": ex["prompt_id"], "cid": cid, "gold": pools[pi]["gold"][cid],
                                    "clusters": pools[pi]["clusters"], "presence": p, "commit3": c,
                                    "points": [r["points"] for r in ex["rubrics"]]}) + "\n")
        print(f"batch {s // batch} done", flush=True)


if __name__ == "__main__":
    main(*(int(a) for a in sys.argv[1:]))
