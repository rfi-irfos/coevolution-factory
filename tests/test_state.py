"""Task 0 smoke test: prove state save/load round-trips against FT_STATE_DIR.

conftest.py freezes FT_STATE_DIR to a temp dir before any import, so this
never touches the real state.json on the Fly volume.
"""


def test_state_roundtrip(state_dir):
    import os, sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'factory'))
    import importlib, factory_spawn_agent as F
    F.save_state({'x': 1})
    assert F.load_state().get('x') == 1
