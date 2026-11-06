# Agent trajectories and run logs

`experiments/run_all.sh` copies every reported run here when it summarizes an experiment
(`team/gulsher/experiments.py:_copy`), because `runs/` is not committed:

- `<run_id>/config.json`: model, temperature, seed, git commit, prompt hash, flags
- `<run_id>/state.jsonl`: one record per test (decision, proposals, verification reports, tokens)
- `<run_id>/report.json`: metrics of the run
- `<run_id>/trajectories.tar.gz`: one JSON event per agent step (LLM calls with prompt, reply and token counts;
  tool calls with input and output; supervisor decisions; the closing `final` event with `failure_mode`)

Read one trajectory: `tar xzf logs/<run_id>/trajectories.tar.gz -C /tmp && python3 -m testdebt.trace /tmp '<test_id>'`
(or extract into `runs/<run_id>/` and use `python3 -m testdebt.trace runs/<run_id> '<test_id>'`).

Representative samples from development (dev split, not reported results):
`smoke_E3_s3_s1` (s3, 1 test, accepted), `dev_wired_s3_s1` (s3, 3 tests), `dev_B2_b2_s1` (b2 single agent, 5 tests),
`smoke_g1off` (s3 with the kill-set gate off: PIT measured, never rejects).
