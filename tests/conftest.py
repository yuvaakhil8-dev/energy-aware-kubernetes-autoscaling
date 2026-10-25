"""Shared pytest fixtures for the Energy-Aware Autoscaling project."""
import os
import sys

import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Prevent the background workload thread from starting during tests.
os.environ.setdefault('ENERGY_AWARE_NO_BG', '1')


@pytest.fixture(scope='session')
def flask_app():
    import app as app_module
    app_module.app.config.update(TESTING=True)
    return app_module.app


@pytest.fixture(scope='session')
def client(flask_app):
    return flask_app.test_client()


@pytest.fixture(scope='session')
def app_module():
    import app as app_module
    return app_module
