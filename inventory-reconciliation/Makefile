.PHONY: test lint format typecheck run clean

test:
	pytest

lint:
	ruff check reconciliation/ reconcile.py tests/

format:
	ruff format reconciliation/ reconcile.py tests/

typecheck:
	mypy reconciliation/ reconcile.py

run:
	python reconcile.py --allow-errors

clean:
	rm -rf output/ .coverage .pytest_cache __pycache__ reconciliation/__pycache__ tests/__pycache__
