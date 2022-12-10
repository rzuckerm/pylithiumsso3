PACKAGE := pylithiumsso3
TESTS := test
CONFIG_FILE = pyproject.toml
ALL = $(PACKAGE) $(TESTS)

SHELL := bash
ifeq ($(OS),Windows_NT)
ifneq ($(GITHUB_PATH),)
POETRY := $(HOME)/.local/bin/poetry
else
POETRY := poetry
endif
else
POETRY := poetry
endif

RUN = $(POETRY) run
META = .meta
META_INSTALL = $(META)/.install

PYTEST_ARGS ?= -vvl \
	--color=yes \
	--cov=$(PACKAGE) \
	--cov-branch \
	--cov-report term-missing \
	--cov-report=html:$(META)/html_cov/ \
	--cov-report=xml:$(META)/coverage.xml

help:
	@echo "clean       - Delete output files"
	@echo "doc         - Create documentation with sphinx"
	@echo "format      - Format code with black"
	@echo "lint        - Lint code with black, pylint, and mypy"
	@echo "lint-black  - Lint code with black"
	@echo "lint-mypy   - Lint code with mypy"
	@echo "lint-pylint - Lint code with pylint"
	@echo "test        - Run unit tests with pytest."
	@echo "              Use PYTEST_ARGS to override options"

$(META):
	mkdir -p $@

$(META_INSTALL): $(CONFIG_FILE) | $(META)
	$(POETRY) install
	touch $@

.PHONY: clean
clean:
	rm -rf $(PACKAGE)/__pycache__/ \
		$(TESTS)/__pycache__/ \
		$(META)/ \
		.pytest_cache/ \
		.mypy_cache/ \
		dist
	rm -f .coverage .coverage.*

.PHONY: doc
doc: $(META_INSTALL)
	@echo "*** Building docs ***"
	$(RUN) sphinx-build -b html docs $(META)/docs
	@echo ""

.PHONY: format
format: $(META_INSTALL)
	$(RUN) black $(ALL)

.PHONY: lint
lint: lint-black lint-pylint lint-mypy

.PHONY: lint-black
lint-black: $(META_INSTALL)
	@echo "*** Linting with black ***"
	$(RUN) black --check $(ALL)
	@echo ""

.PHONY: lint-pylint
lint-pylint: $(META_INSTALL)
	@echo "*** Linting with pylint ***"
	$(RUN) pylint --rcfile $(CONFIG_FILE) $(PACKAGE)
	$(RUN) pylint --rcfile $(TESTS)/$(CONFIG_FILE) $(TESTS)
	@echo ""

.PHONY: lint-mypy
lint-mypy: $(META_INSTALL)
	@echo "*** Linting with mypy ***"
	$(RUN) mypy $(ALL)
	@echo ""

.PHONY: test
test: $(META_INSTALL)
	@echo "*** Running tests ***"
	$(RUN) pytest $(PYTEST_ARGS)
	@echo ""
