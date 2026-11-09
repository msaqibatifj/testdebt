# VeriRefactor: one entry point. `make help` lists the targets.
# Long targets (dev, all) are resumable: running the same target again continues where it stopped.
SHELL := /bin/bash
VENV  := source .venv/bin/activate && export PATH=$$HOME/apache-maven-3.9.9/bin:$$PATH &&

.PHONY: help setup test smoke demo dev reproduce all zip

help:        ## list targets
	@grep -E '^[a-z-]+:.*## ' Makefile | awk -F':.*## ' '{printf "  make %-11s %s\n", $$1, $$2}'

setup:       ## one time: JDK+Maven, venv, deps, Java projects, JNose (asks for sudo; then put your key in .env)
	bash scripts/install_env.sh
	python3 -m venv .venv
	$(VENV) pip install -r requirements.txt && pip install -e .
	[ -f .env ] || cp .env.example .env
	$(VENV) bash scripts/setup_projects.sh && bash src/testdebt/team/hasan/get_jnose.sh

test:        ## unit + integration tests, no network
	$(VENV) python3 -m pytest -q

smoke:       ## one LLM call: the key in .env works
	$(VENV) python3 scripts/smoke_test.py

demo:        ## full system (s3, PIT gate) on 3 dev tests; then: testdebt trace runs/<id> '<test>'
	$(VENV) testdebt --system s3 --split dev --limit 3 --seed 1 --pit

dev:         ## E1-E5 on 2 dev tests each -> results/dev/ (about 30-60 min)
	$(VENV) SPLIT=dev LIMIT=2 bash experiments/run_all.sh

reproduce:   ## no LLM: unpack logs/ into runs/, rebuild results/, README gap table, paper tables and figures
	for l in logs/*/; do id=$$(basename $$l); [ -e runs/$$id/report.json ] && continue; mkdir -p runs/$$id; \
	  cp $$l/*.json* runs/$$id/; [ -f $$l/trajectories.tar.gz ] && tar xzf $$l/trajectories.tar.gz -C runs/$$id; done
	$(VENV) RUN=0 bash experiments/run_all.sh
	git checkout -- 'logs/*/trajectories.tar.gz'   # summarize re-compresses them; content is unchanged

all:         ## every reported run on the test split, frozen (days, ~20M tokens; needs a clean tree)
	$(VENV) bash experiments/run_all.sh

zip:         ## LaTeX source zip for the submission
	bash paper/make_zip.sh
