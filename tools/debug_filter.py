"""Debug: check remaining suspicious vault entries against the filter."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prompt_filter import is_real_prompt

tests = [
    "A directory \"src\" was created in the project path. A directory "
    "structure was created for a QA automation project including subdirs",
    "hey continue the task. The git push failed because there is no master "
    "branch - fix it",
    "Created a comprehensive logging module at src/logging/__init__.py "
    "containing 447 lines",
    "A tool call was made to create a browser automation module for an AI "
    "Super App",
]
for t in tests:
    print(f"real={is_real_prompt(t)} :: {t[:70]}")
