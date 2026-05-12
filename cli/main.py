"""Compatibility wrapper for `python -m cli.main`."""

from stocksage.cli import (
    AnalysisRunPrep,
    _prepare_analysis_row,
    cli,
)

__all__ = ["AnalysisRunPrep", "_prepare_analysis_row", "cli"]


if __name__ == "__main__":
    cli()
