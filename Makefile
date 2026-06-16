.PHONY: install download audit test clean help

# Default target
all: help

help:
	@echo "ViMedCSS Evaluation Pipeline - Commands:"
	@echo "  make install   - Install required Python dependencies inside virtual environment"
	@echo "  make download  - Download dataset metadata from Hugging Face"
	@echo "  make audit     - Run metadata schema checks and statistics audit"
	@echo "  make test      - Run all pytest unit tests"
	@echo "  make clean     - Clean python caches, logs, and outputs"

install:
	.venv/bin/pip install -r requirements.txt

download:
	PYTHONPATH=. .venv/bin/python src/cli.py download-metadata

audit:
	PYTHONPATH=. .venv/bin/python src/cli.py audit-metadata

test:
	PYTHONPATH=. .venv/bin/pytest

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	rm -rf .pytest_cache
	rm -rf logs/
	rm -rf outputs/audit/*
	touch outputs/audit/.gitkeep
