PYTHON ?= python

.PHONY: install test eval demo

install:
	$(PYTHON) -m pip install -r requirements.txt -r requirements-dev.txt

test:
	$(PYTHON) -m pytest -q --cov=src --cov=evals --cov=examples --cov-report=term-missing --cov-report=json:evals/results/coverage.json --cov-fail-under=80

eval:
	$(PYTHON) -m evals.generate_dataset
	$(PYTHON) -m evals.run_eval --mode stub
	$(PYTHON) -m evals.fairness_check --mode stub

demo:
	$(PYTHON) main.py
