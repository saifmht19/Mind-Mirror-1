import os

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "real: needs real models / ffmpeg / network (set VOICE_TEST_REAL=input,output,...)")


def real_enabled(kind: str) -> bool:
    return kind in os.getenv("VOICE_TEST_REAL", "").replace(" ", "").split(",")


@pytest.fixture
def tmp(tmp_path):
    return tmp_path
