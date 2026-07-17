"""Pytest scaffold for the CoEvolution autonomous-firm test suite (Task 0).

Two things MUST happen before any project module is imported:
  1. ``factory/`` is placed on sys.path so ``import factory_spawn_agent`` works.
  2. ``FT_STATE_DIR`` is frozen to a throwaway temp dir. Project modules read
     this env var at IMPORT time (e.g. factory_spawn_agent.STATE_DIR), so it
     must be set here, at collection time, before the first import — never
     against the real Fly-volume state.json.
"""
import os
import sys
import tempfile

# 1. Put factory/ on the import path.
_FACTORY = os.path.join(os.path.dirname(__file__), "..", "factory")
if _FACTORY not in sys.path:
    sys.path.insert(0, _FACTORY)

# 2. Freeze FT_STATE_DIR to a temp dir BEFORE any project module import.
_STATE_DIR = tempfile.mkdtemp(prefix="ft_state_")
os.environ["FT_STATE_DIR"] = _STATE_DIR

import pytest


@pytest.fixture
def state_dir():
    """Absolute path to the frozen temp state dir used for this test run.

    Project modules capture FT_STATE_DIR at import time, so this fixture just
    exposes the same directory for tests that want to inspect files directly.
    """
    return _STATE_DIR
