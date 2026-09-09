"""Main module entry point for python -m factground."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
