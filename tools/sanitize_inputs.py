"""One-time mechanical privacy minimization of copied numeric inputs."""
import json
from pathlib import Path
root = Path(__file__).resolve().parents[1]
for name in ("cost_groups", "token_groups"):
    p = root / "data" / (name + ".json")
    rows = json.loads(p.read_text())
    for r in rows:
        r.pop("contributor_index", None)
        r.pop("group_index", None)
    p.write_text(json.dumps(rows, separators=(",", ":")) + "\n")
reference = json.loads((root / "reference/cost_percentiles.json").read_text())
(root / "data/prices.json").write_text(json.dumps(reference["price_table"], indent=2) + "\n")
