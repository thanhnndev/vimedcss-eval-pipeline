"""Report generation module for Vietnamese Medical Code-Switching (ViMedCSS) evaluation pipeline.

This module provides facilities to generate comprehensive Vietnamese markdown reports
aggregating artifacts from Phase 0-4 of the evaluation pipeline.

Classes:
    ReportGenerator: Main report generator that assembles section-based reports
    DataSourceRegistry: Registry of data sources with provenance tracking
    LimitationWriter: Writer for report limitations and caveats

Exports:
    ReportGenerator: Primary report generation class
    DataSourceRegistry: Data source registry class
    LimitationWriter: Limitations document writer
"""

from src.reports.report_generator import ReportGenerator
from src.reports.report_data_sources import DataSourceRegistry
from src.reports.report_limitations import LimitationWriter

__all__ = [
    "ReportGenerator",
    "DataSourceRegistry",
    "LimitationWriter",
]
