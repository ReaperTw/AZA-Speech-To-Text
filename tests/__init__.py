import os
import sys

# Make src importable for root `python -m unittest` discovery (non-installed app)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))