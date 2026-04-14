"""Shared pytest configuration for suite2_translation tests."""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-llm", action="store_true", default=False,
        help="Run tests that require LLM (Azure) calls",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "llm: test requires LLM calls")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-llm"):
        skip_llm = pytest.mark.skip(reason="needs --run-llm to run")
        for item in items:
            if "llm" in item.keywords:
                item.add_marker(skip_llm)
