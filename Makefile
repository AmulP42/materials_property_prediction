#################################################################################
# GLOBALS                                                                       #
#################################################################################
include .env
export

PROJECT_NAME = materials_property_prediction
PYTHON_INTERPRETER = uv run python

#################################################################################
# COMMANDS                                                                      #
#################################################################################


## Install Python dependencies

.PHONY: setup
setup:
	@command -v uv >/dev/null 2>&1 || curl -LsSf https://astral.sh/uv/install.sh | sh
	@PATH="$$HOME/.local/bin:$$PATH" uv sync --group dev	

.PHONY: init_db
init_db:
	psql -h $(DB_HOST) -U $(DB_USER) -d $(DB_NAME) -f property_prediction/db/schema.sql

.PHONY: clear_db
clear_db:
	psql -h $(DB_HOST) -U $(DB_USER) -d $(DB_NAME) -f property_prediction/db/clear.sql

## Delete all compiled Python files
.PHONY: clean
clean:
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -delete

.PHONY: mlflow
mlflow:
	$(PYTHON_INTERPRETER) -m mlflow ui --port 5000

## Lint using ruff (use `make format` to do formatting)
.PHONY: lint
lint:
	ruff format --check
	ruff check

## Format source code with ruff
.PHONY: format
format:
	ruff check --fix
	ruff format



## Download Data from storage system
.PHONY: sync_data_down
sync_data_down:
	aws s3 sync s3://$(S3_BUCKET_NAME)/data/ \
		data/ 
	

## Upload Data to storage system
.PHONY: sync_data_up
sync_data_up:
	aws s3 sync data/ \
		s3://$(S3_BUCKET_NAME)/data 
	


#################################################################################
# PROJECT RULES                                                                 #
#################################################################################


## Make dataset
.PHONY: data
data: setup
	$(PYTHON_INTERPRETER) property_prediction/dataset.py


#################################################################################
# Self Documenting Commands                                                     #
#################################################################################

.DEFAULT_GOAL := help

define PRINT_HELP_PYSCRIPT
import re, sys; \
lines = '\n'.join([line for line in sys.stdin]); \
matches = re.findall(r'\n## (.*)\n[\s\S]+?\n([a-zA-Z_-]+):', lines); \
print('Available rules:\n'); \
print('\n'.join(['{:25}{}'.format(*reversed(match)) for match in matches]))
endef
export PRINT_HELP_PYSCRIPT

help:
	@$(PYTHON_INTERPRETER) -c "${PRINT_HELP_PYSCRIPT}" < $(MAKEFILE_LIST)
