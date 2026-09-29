"""Shared, dependency-free helpers for the StandardLens MVP data pipeline.

Keeping this logic in one place lets the CSV/XLSX importer, the incremental
crawler, the search-index builder, the unit tests and (via search.js) the
browser agree on one definition of tokenization, standard-number families and
field provenance.
"""
from __future__ import annotations

__all__ = ["families", "indexing", "provenance", "tokenizer"]
__version__ = "0.2.0"
