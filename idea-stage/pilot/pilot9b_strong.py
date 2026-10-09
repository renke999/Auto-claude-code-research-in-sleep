"""Pilot 9b: pre-registered G2 remedy - re-measure the contradicted fire rate with a stronger COMMIT judge (Sonnet).
Same 100 prompts; variants ideal / plain / numpert / numsub; v3 prompt with grounding + recheck."""
from __future__ import annotations

import json
import random
import statistics as st
from pathlib import Path

import judges as J
from pilot8_twostage import perturb_sub

HERE = Path(__file__).parent


def main(n=100):
    import pilot1_stance as P
    rows = P.build_variants(n)
    rng = random.Random(7)
    jobs, keys = [], []
    for i, (ex, v) in enumerate(rows):
        vv = {"ideal": v["ideal"], "plain": v["plain"], "numpert": v["numpert"], "numsub": perturb_sub(v["plain"], rng)}
        for name, resp in vv.items():
            if resp:
                jobs.append((ex, resp, "")); keys.append((i, name))
    labs = J.commit3_many(jobs, workers=8, model="claude-sonnet-5-5")
    out = [{"i": i, "variant": nm, "commit3": l} for (i, nm), l in zip(keys, labs)]
    (HERE / "pilot9b_results.jsonl").write_text("\n".join(json.dumps(r) for r in out) + "\n")
    for nm in ("ideal", "plain", "numpert", "numsub"):
        x = [any(l == "contradicted" for l in r["commit3"]) for r in out if r["variant"] == nm]
        print(f"Sonnet COMMIT judge: contradicted fire rate {nm:8s} {st.mean(x):.2f} (n={len(x)})")
    pi = {r["i"] for r in out if r["variant"] == "numpert"}
    for nm in ("numpert", "numsub"):
        a = {r["i"]: any(l == "contradicted" for l in r["commit3"]) for r in out if r["variant"] == nm}
        b = {r["i"]: any(l == "contradicted" for l in r["commit3"]) for r in out if r["variant"] == "plain"}
        ks = [k for k in a if k in b]
        print(f"  paired: {nm} fires & plain doesn't {st.mean(a[k] and not b[k] for k in ks):.2f}; plain fires & {nm} doesn't {st.mean(b[k] and not a[k] for k in ks):.2f}")


if __name__ == "__main__":
    main()
