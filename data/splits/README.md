# Fixed splits

Test IDs only, built once (commit `0e1f7da`) with `python3 -m testdebt.data.splits --seed 1`
(dev seed 1, test seed 2), stratified by project x single/multi smell. Files are `.jsonl`, not `dev_ids.txt`/`test_ids.txt`.

| File | Tests | Commons-cli / Gson / Jsoup | Use |
|---|---|---|---|
| `dev.jsonl` | 80 | 13 / 39 / 28 | tuning and debugging |
| `test.jsonl` | 150 | 24 / 74 / 52 | reported LLM runs (`--frozen`); never tune on it |
| `rest.jsonl` | 254 | 40 / 125 / 89 | no-LLM runs only |

Never regenerate. Check integrity with `sha256sum -c data/splits/SHA256SUMS` (run from the repo root).
