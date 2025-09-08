all: format lint test

format:
	poetry run ruff format .

lint:
	poetry run ruff check --fix .

test:
	poetry run pytest test_golden.py -v

test-update-golden:
	poetry run pytest test_golden.py::test_update_golden -v -s

test-coverage:
	poetry run pytest test_golden.py -v --cov=. --cov-report=html --cov-report=term

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf .mypy_cache

install:
	poetry install
