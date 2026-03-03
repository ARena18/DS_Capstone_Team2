# conftest.py — shared pytest configuration
# Ensures the project root is on sys.path so `import app` etc. work.

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
