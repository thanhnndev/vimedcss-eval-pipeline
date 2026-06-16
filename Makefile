.PHONY: install download audit terms classify classify-mock external external-mock asr report test clean pipeline help

# Default target
all: help

help:
	@echo "ViMedCSS Evaluation Pipeline"
	@echo ""
	@echo "Setup:"
	@echo "  make install         - Install required Python dependencies inside virtual environment"
	@echo ""
	@echo "Pipeline:"
	@echo "  make download        - Download dataset metadata from Hugging Face"
	@echo "  make audit           - Run metadata schema checks and statistics audit"
	@echo "  make terms           - Extract and normalize code-switching medical terms"
	@echo "  make classify        - Classify terms with LLM (requires OPENAI_API_KEY)"
	@echo "  make classify-mock   - Run LLM classification in mock mode (no API required)"
	@echo "  make external        - Match ViMedCSS terms against external medical reference lexicon"
	@echo "  make external-mock   - Run external matching in mock mode (no external inventory required)"
	@echo "  make asr             - Run ASR baseline evaluation (Phase 4 - coming soon)"
	@echo "  make report          - Generate Vietnamese final report (Phase 5 - coming soon)"
	@echo "  make pipeline        - Run full pipeline: download -> audit -> terms -> classify -> external"
	@echo ""
	@echo "Utilities:"
	@echo "  make test            - Run all pytest unit tests"
	@echo "  make clean           - Clean python caches, logs, and outputs"

install:
	.venv/bin/pip install -r requirements.txt

download:
	PYTHONPATH=. .venv/bin/python src/cli.py download-metadata

audit:
	PYTHONPATH=. .venv/bin/python src/cli.py audit-metadata

terms:
	PYTHONPATH=. .venv/bin/python src/cli.py extract-terms

classify:
	PYTHONPATH=. .venv/bin/python src/cli.py classify-terms

classify-mock:
	PYTHONPATH=. .venv/bin/python src/cli.py classify-terms --mock --limit 20

external:
	PYTHONPATH=. .venv/bin/python src/cli.py match-external

external-mock:
	PYTHONPATH=. .venv/bin/python src/cli.py match-external --mock --limit 50

asr:
	@echo "ASR evaluation module is under development (Phase 4)."
	@echo "Please run individual stages manually or check .planning/phases/04/ for progress."

report:
	@echo "Report generation module is under development (Phase 5)."
	@echo "Please run individual stages manually or check .planning/phases/05/ for progress."

pipeline: download audit terms classify external
	@echo "Full pipeline completed. Check outputs/ for results."

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
	rm -rf outputs/term_coverage/*
	rm -rf outputs/asr_eval/*
	rm -rf outputs/reports/*
	touch outputs/audit/.gitkeep
	touch outputs/term_coverage/.gitkeep
	touch outputs/asr_eval/.gitkeep
	touch outputs/reports/.gitkeep
