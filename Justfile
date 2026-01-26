set shell := ["bash", "-c"]

[private]
default:
    @just --list

PY_SDK_PATH := "./sdks/python"

# Install the python virtual environment and install the pre-commit hooks
@py-install all="false":
    echo "Creating python virtual environment using uv"
    just -d {{ PY_SDK_PATH }} -f {{ PY_SDK_PATH }}/Justfile install
    just pre-commit-install

@pre-commit-install:
    uv run pre-commit install && uv run pre-commit  install --hook-type commit-msg

# Run python code quality tools.
@py-check:
    just -d {{ PY_SDK_PATH }} -f {{ PY_SDK_PATH }}/Justfile check

# Test the python code with pytest
@py-test:
    just -d {{ PY_SDK_PATH }} -f {{ PY_SDK_PATH }}/Justfile test

@test: py-test

# Build python wheel file
@py-build:
    just -d {{ PY_SDK_PATH }} -f {{ PY_SDK_PATH }}/Justfile build

# Test if documentation of python can be built without warnings or errors
py-docs-test:
    uv run --project={{PY_SDK_PATH}} mkdocs build -s

# Build and serve the documentation of python
py-docs:
    uv run  --project={{PY_SDK_PATH}} mkdocs serve
