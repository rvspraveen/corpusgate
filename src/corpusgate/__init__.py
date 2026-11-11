"""corpusgate: data contracts and CI gates for RAG corpora."""

__version__ = "0.2.0"

from corpusgate.contract import ContractError, load_contract
from corpusgate.runner import CheckOutcome, DataError, Report, read_corpus, run_contract

__all__ = [
    "CheckOutcome",
    "ContractError",
    "DataError",
    "Report",
    "__version__",
    "load_contract",
    "read_corpus",
    "run_contract",
]
