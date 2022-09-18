PACKAGE := pylithiumsso3
TESTS := test
CONFIG_FILE = pyproject.toml
ALL = $(PACKAGE) $(TESTS)

ifeq ($(VENV),)
RUN = poetry run
else
RUN = $(VENV)/bin/poetry run
endif

META = .meta
PYTEST_ARGS ?= -vvl \
	--cov=$(PACKAGE) \
	--cov-branch \
	--cov-report term-missing \
	--cov-report=html:$(META)/html_cov/ \
	--cov-report=xml:$(META)/coverage.xml

help:
	@echo "clean       - Delete output files"
	@echo "doc         - Create documentation"
	@echo "format      - Format code with black"
	@echo "lint        - Lint code with black, pylint, and mypy"
	@echo "lint-black  - Lint code with black"
	@echo "lint-mypy   - Lint code with mypy"
	@echo "lint-pylint - Lint code with pylint"
	@echo "test        - Run unit tests with pytest."
	@echo "              Use PYTEST_ARGS to override options"

$(META):
	mkdir -p $@

ifneq ($(VENV),)
$(VENV):
	virtualenv $(VENV)
	$(VENV)/bin/pip install poetry
endif

.PHONY: clean
clean:
	rm -rf $(PACKAGE)/__pycache__/ \
		$(TESTS)/__pycache__/ \
		$(META)/ \
		.pytest_cache/ \
		.mypy_cache/
	rm -f .coverage .coverage.*

.PHONY: doc
doc: | $(META)
	sphinx-build -b html docs $(META)/docs

.PHONY: format
format: | $(VENV)
	$(RUN) black $(ALL)

.PHONY: lint
lint: lint-black lint-pylint lint-mypy

.PHONY: lint-black
lint-black: | $(VENV)
	@echo "*** Linting with black ***"
	$(RUN) black --check $(ALL)
	@echo ""

.PHONY: lint-pylint
lint-pylint: | $(VENV)
	@echo "*** Linting with pylint ***"
	$(RUN) pylint --rcfile $(CONFIG_FILE) $(PACKAGE)
	$(RUN) pylint --rcfile $(TESTS)/$(CONFIG_FILE) $(TESTS)
	@echo ""

.PHONY: lint-mypy
lint-mypy: | $(VENV)
	@echo "*** Linting with mypy ***"
	$(RUN) mypy $(ALL)
	@echo ""

.PHONY: test
test: | $(VENV) $(META)
	$(RUN) pytest $(PYTEST_ARGS)
