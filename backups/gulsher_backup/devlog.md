# Devlog (Gulsher's parts): date, failure seen, change, measured effect on dev
Entries come from git history. "Effect" must be filled from `results/dev` or `runs/` before it is cited; none are invented here.

| Date | Failure seen | Change | Effect on dev |
|---|---|---|---|
| 2026-10-24 | Phase 1 PIT pilot: the baseline kill matrix was computed after the patch was written, so it measured the refactored code | `5cf24e3` compute the original matrix first | TODO rerun pilot (`bash scripts/phase1_pilots.sh pit`) |
| 2026-10-25 | One exception stopped a whole run | `888b2eb` per-test error capture: decision `error`, run continues | TODO count of `error` decisions on dev |
| 2026-10-25 | No fixed evaluation split; tuning could leak into reporting | `0e1f7da` dev 80 / test 150 / rest 254, exact-size stratification; `764c7df` `--frozen` guard | n/a (design) |
| 2026-11-05 | Same refactored class re-ran PIT for every system/seed; secrets could reach traces; a crash could leave a checkout modified | `7610ce4` KillsetGate caches matrices by SHA-256 of the class source; `redact()` on all trace text; `RestoreCheck` after each test | TODO PIT time saved on a 5-test dev run |
| 2026-11-05 | Maven subprocess hangs | timeouts in `tools/` (Maven 900 s, PIT 3600 s, tsDetect 600 s); a timeout becomes decision `error`, resume retries it | TODO |
