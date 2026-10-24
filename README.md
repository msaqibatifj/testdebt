# VeriRefactor: Agentic Test-Debt Management (AI4015 Semester Project, G2)

Group: M Saqib Atif (23I-0769), Gulsher Khan (23I-0066), Hasan Altaf (23I-0698). Supervisor: Meemon Khan.

Goal: refactor test smells in Java/JUnit projects. A refactoring is accepted only when tools show it is safe: it
compiles, it passes, the targeted smells are gone (tsDetect, plus JNose later), and the test still kills every
mutant the original killed (PIT). Base paper: UTRefactor (FSE 2025) [1].

## Systems (selected with `--system`, same model, KB, tools, caps and tests)

| Flag | System | Status |
|---|---|---|
| `b0replay` | UTRefactor's **published** refactorings run through our verifier. No LLM calls. | working |
| `b0` | UTRefactor reproduction: KB prompt (smell definition, DSL rule, checkpoints), 1 pass, accepted if it compiles and passes | working |
| `b1` | Fixed pipeline: KB prompt, then verify. One fixed retry prompt carries the error text, up to 2 retries, then reject | working |
| `single` | Plain prompt with no KB (the "direct LLM" reference in [1]) | working |
| `s3` | Multi-agent system: Detection, Planner, Refactor and Verifier agents under a Supervisor (accept, retry, switch strategy, escalate; memory of failed proposals) | Phase 1 skeleton (`agents.py`), tested with a fake LLM |
| `b2` | Single tool-using agent | Phase 2 (raises `NotImplementedError`) |

## Status (Phase 1)

| Component | State |
|---|---|
| LLM client: logged, cached, rate-limited, `.env`; Cerebras `gpt-oss-120b` | working, smoke-tested |
| Contracts (`TestRef`, `DebtFinding`, `RefactorProposal`, `VerificationReport`, `RunState`) | done |
| Dataset: UTRefactor inputs, projects pinned to matching commits (98-99% verbatim) | done, 484 tests |
| tsDetect wrapper, method-level | working; reproduces 100% of the paper's labels |
| Maven runner (compile and run one class, per-project `JAVA_HOME`) | working in WSL |
| Fast runner (Maven once per module, then javac + JUnit launcher per test) | working in WSL (about 4 s per test) |
| PIT kill-set (full mutation matrix; union over split tests) | written and unit-tested; not yet run on a real project (Phase 2) |
| Verifier: patch, checks, smells, compile, run, kill-set, always restore | done, tested with real `javac` |
| Pipelines `b0replay`, `b0`, `b1`, `single`; resumable runs; metrics and decision report | done |
| First results | `docs/results_phase1.md`: b0replay on Commons-cli, b0 LLM pilot, Gson error analysis |
| S3 Supervisor loop (`agents.py`), decisions logged per step in `RunState.trace` | skeleton working (mock end-to-end tests) |
| JNose, JaCoCo, B2, LLM-based planning in S3 | Phase 2 |

## Quick start (WSL / Ubuntu)

```bash
bash scripts/install_env.sh                 # JDK 17 + Maven 3.9.9 (one time; asks for sudo)
export PATH=$HOME/apache-maven-3.9.9/bin:$PATH
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .
cp .env.example .env                        # then put your Cerebras key in .env
python3 -m pytest -q                        # 34 tests (2-3 optional ones skip without Java), no network needed
bash scripts/setup_projects.sh              # clones UTRefactor + 3 projects, pins commits, builds data/eval_set*.jsonl
bash scripts/check_builds.sh                # week-1 gate: each pinned project builds and a test class passes
python3 scripts/smoke_test.py               # one LLM call
bash scripts/phase1_pilots.sh               # PIT pilot + b0replay/single/b0/b1/s3 on 10 Commons-cli tests -> results/phase1/
```

### Runs

```bash
# no LLM: measure UTRefactor's own outputs (add --pit for kill-sets; slow)
python3 -m testdebt.eval.run_baseline --system b0replay --eval data/eval_set.jsonl --project commons-cli
# pilot: tokens per test, no Maven
python3 -m testdebt.eval.run_baseline --system b0 --eval data/eval_set.jsonl --limit 10 --skip-verify
# full baselines on the 150-test stratified subset, 3 seeds
for s in 1 2 3; do python3 -m testdebt.eval.run_baseline --system b1 --eval data/eval_subset150.jsonl --seed $s; done
# multi-agent system (S3)
python3 -m testdebt.eval.run_baseline --system s3 --eval data/eval_set.jsonl --project commons-cli --limit 10
# recompute metrics for a run
python3 -m testdebt.eval.run_baseline --report runs/<run_id>
```

Speed: by default (`--runner fast`) Maven runs once per module to compile and record the classpath. After that,
each refactored test is compiled alone with `javac` and its class is run with the JUnit launcher, which takes a few
seconds instead of the 20-60 s of a full `mvn test`. If the original class does not pass on the fast path but does
pass under Maven, that class falls back to Maven automatically. Use `--runner maven` to force Maven for everything.

Each run writes these files to `runs/<run_id>/`:

- `config.json`
- `state.jsonl`: one record per test, with every attempt, its error and the verdict
- `decisions.json`
- `report.json`
- `report.md`

Re-running with the same `--run-id` resumes the run. `runs/` is not committed; the runs quoted in the docs are
copied to `results/phase1/<run_id>/` (report, decisions, config).

With `--skip-verify` nothing is compiled or run. The report then shows `accepted_rate` as `-` and counts
`accepted_unverified` instead, so a static-only run is never mistaken for an acceptance rate.

## Initial results (Phase 1)

| Run | Tests | Accepted | Compiles | Passes | Smell reduction (tsDetect) | Tokens/test |
|---|---|---|---|---|---|---|
| b0replay, Commons-cli (UTRefactor's published outputs) | 77 | 84.4% | 87.0% | 84.4% | 86.4% (paper: 86%) | 0 |
| b0replay, all 3 projects, static only (`results/phase1/b0replay_all_skipverify`) | 483 | - | - | - | 59.9% | 0 |
| b0, Commons-cli pilot (gpt-oss-120b) | 10 | 90% | 100% | 90% | 100% | 2,462 |

Details, Gson analysis and caveats: `docs/results_phase1.md`.

## Layout

```
src/testdebt/
  contracts.py        TestRef, DebtFinding, RefactorProposal, VerificationReport, RunState
  llm_client.py       logged/cached/rate-limited chat client (.env aware)
  java_utils.py       mask comments/strings, find/replace JUnit test methods, find module pom
  smells.py           fast rules detector (approximation, JUnit 4 + 5); final numbers come from tsDetect
  prompts.py          UTRefactor KB lookup + its prompt template, plain prompt, fixed retry prompt
  tools/maven.py      compile + run one test class
  tools/tsdetect.py   method-level tsDetect (jar from the UTRefactor package)
  tools/pit.py        PIT via pom.pit.xml copy, full kill matrix, kill-set comparison
  verify.py           patch -> checks -> smells -> compile/run -> kill-set -> restore
  pipeline.py         control flow of b0replay / b0 / b1 / single (b2 in Phase 2)
  agents.py           S3: Detection, Planner, Refactor, Verifier agents + Supervisor
  eval/utr_dataset.py read UTRefactor reports, pin commits
  eval/build_eval_set.py  eval_set.jsonl + stratified seeded subset
  eval/metrics.py     rates, smell reduction by project and smell, kill-set loss with 95% CI, paper delta
  eval/run_baseline.py    CLI
configs/default.json  model, caps, retries, temperature, paths
data/pins.json        pinned commits + JAVA_HOME per project
data/eval_set*.jsonl  built by setup_projects.sh (not committed: contains UTRefactor's published code)
data/samples/demo/    tiny Maven project used by the tests
docs/architecture.png methodology diagram (python3 scripts/make_diagram.py)
docs/results_phase1.md
results/phase1/       committed reports of the runs quoted in the docs
scripts/phase1_pilots.sh  PIT pilot + LLM pilots, copies reports to results/phase1/
```

## Known limitations / to verify

- PIT has not run on a real project yet: `bash scripts/phase1_pilots.sh pit` runs it on 5 Commons-cli tests and fails loudly if no kill-sets come back. Check the plugin version in `tools/pit.py` and confirm that
  `fullMutationMatrix` fills `killingTests` in the pilot (proposal section 9.12).
- The pinned Gson build requires JDK 11 to 17, and old Jsoup needs JDK 19 or lower (`-source 1.7`). `data/pins.json`
  points all three projects at JDK 17.
- The B0-replay reduction differs strongly from the paper on Gson and Jsoup (see `docs/results_phase1.md`).
  Check UTRefactor's own counting before claiming anything.
- The UTRefactor package shows no licence. We clone it and read its KB at runtime; we do not copy it into this repo.
- Never commit `.env`. Rotate any key that has been pasted into a chat.
