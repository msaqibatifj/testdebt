# Gulsher: remaining non-code items

## r4: secrets, requirements, .env.example  (checked 2026-11-06)
- `git log -p | grep -iE "api[_-]?key|csk-|secret"`: only hits are the redaction regexes, test fixtures with fake keys (`csk-thisisnotarealkey99`) and `.env.example`'s `CEREBRAS_API_KEY=your_key_here`. No real key in history. `.env` is in `.gitignore`.
- `.env.example` exists. `requirements.txt` is unpinned (`requests>=2.31`, `pytest>=8.0`, `matplotlib>=3.7`). Versions on this machine: `requests==2.34.2`, `pytest==9.1.1`, `matplotlib==3.11.2`, Python 3.12.3. **Pin these** (the plan asks for pinned versions); not changed here because it edits the main tree.

## r5: `data/splits/README.md` (missing). Text to paste
Splits were built once (commit `0e1f7da`) with `python3 -m testdebt.data.splits --seed 1` (dev seed 1, test seed 2), stratified by project x single/multi smell. Files hold test IDs: `dev.jsonl` 80, `test.jsonl` 150, `rest.jsonl` 254. Never tune prompts or thresholds on test. The plan names `dev_ids.txt` / `test_ids.txt`; ours are `.jsonl`, say so. Add SHA-256 checksums (`sha256sum data/splits/*.jsonl`).

## e2: UTRefactor on the same split
- `b0replay` = their published outputs, our verifier -> label **reproduced (measurement)**.
- `b0` = their prompt and KB, our model -> label **reproduced (prompt)**.
- Numbers from the paper itself -> label **paper-reported** and set `source: paper-reported`. Needs the paper's tables; I have not read them.
- Known: b0replay differs strongly from the paper on Gson and Jsoup (`docs/results_phase1.md`); explain it in Evaluation Methodology.
- The plan mentions `E2_base_paper.yaml`; this repo uses `team/gulsher/experiments/E2.json` / `experiments/run_all.py`. Add a `source` field to the output rather than a new file.

## failure_mode names (handoff to Hasan)
The `final` trace step carries Hasan's categories from `team/hasan/failures.py`: infrastructure error, budget exhausted, malformed reply, assertion dropped or empty test, compile (API not in project / missing symbol / other), fixture clobbered by extracted setup, semantic change: test now fails, weakened test: kill-set loss, smell not removed / new smell. The plan's examples map: `compile_error` -> compile:*, `assertion_changed` -> assertion dropped / semantic change, `llm_format_error` -> malformed reply, `timeout` -> infrastructure error.

## p1: Phase 1 supervisor comments
Not in the repo. One line each: `comment -> what changed -> commit`. Candidates from the history: PIT baseline measured the refactored code (fixed `5cf24e3`); splits frozen (`0e1f7da`); per-test error capture (`888b2eb`).
