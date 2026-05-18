.PHONY: install lint type test ci run
install:
	python -m pip install -e ".[dev]"
lint:
	ruff check src tests
type:
	mypy
test:
	pytest -q
ci: lint type test
run:
	python -m travel_assistant
