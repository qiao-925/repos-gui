"""Unit tests for CLI path argument normalization."""

from __future__ import annotations

from pathlib import Path

from clonex.cli import _normalize_output_path_arg


def test_normalize_output_path_arg_trims_trailing_dot():
    path = _normalize_output_path_arg("./test-clonex.")
    assert path.name == "test-clonex"
    assert str(path).endswith("test-clonex")


def test_normalize_output_path_arg_trims_trailing_spaces():
    path = _normalize_output_path_arg("./test-clonex   ")
    assert path.name == "test-clonex"


def test_normalize_output_path_arg_keeps_normal_names():
    path = _normalize_output_path_arg("./test-clonex")
    assert path.name == "test-clonex"


def test_normalize_output_path_arg_blank_falls_back():
    path = _normalize_output_path_arg("   ...   ")
    assert isinstance(path, Path)
    assert path.name == "clonex-repos"
