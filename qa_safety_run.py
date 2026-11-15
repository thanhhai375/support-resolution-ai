"""QA Safety Test Suite runner from repository root."""

import sys
from pathlib import Path

# Add backend directory to sys.path
ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from qa_safety_run import run_all_qa_safety_tests

if __name__ == "__main__":
    success = run_all_qa_safety_tests()
    sys.exit(0 if success else 1)
