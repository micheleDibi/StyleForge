"""
Provider per la ricerca accademica su database esterni.
Ogni provider espone una funzione `search` async che ritorna UnifiedPaper[].
"""

from .base import BaseProvider, ProviderError, RateLimitError, UnifiedPaper
from .openalex import OpenAlexProvider
from .semantic_scholar import SemanticScholarProvider
from .crossref import CrossrefProvider

__all__ = [
    "BaseProvider",
    "ProviderError",
    "RateLimitError",
    "UnifiedPaper",
    "OpenAlexProvider",
    "SemanticScholarProvider",
    "CrossrefProvider",
]
