set shell := ["bash", "-euo", "pipefail", "-c"]

PY_SDK := "sdks/python"

[private]
default:
    @just --list

# Install dependencies and pre-commit hooks
install *groups="dev test":
    uv sync --all-packages {{ if groups == "all" { "--all-groups" } else { prepend("--group ", groups) } }}
    prek install --overwrite
    prek install --overwrite --hook-type commit-msg

# Run Python code quality checks
py-check:
    @echo "Checking lock file consistency with 'pyproject.toml'"
    uv lock --locked
    @echo "Static type checking: Running ty"
    uv run ty check
    @echo "Linting: Running ruff"
    uv run ruff check
    @echo "Checking for obsolete dependencies: Running deptry"
    uv run --directory {{ PY_SDK }} deptry src
    @echo "Checking for dependency architecture: Running tach"
    uv run --directory {{ PY_SDK }} tach check

# Test the Python code with pytest
py-test:
    @echo "Testing code: Running pytest"
    uv run --directory {{ PY_SDK }} pytest --cov --cov-config=pyproject.toml --cov-report=xml

test: py-test

# Build Python wheel file
py-build: py-clean-build
    @echo "Creating wheel file"
    uvx --from build pyproject-build --installer uv --outdir {{ PY_SDK }}/dist {{ PY_SDK }}

# Publish Python package
py-publish:
    uv publish --directory {{ PY_SDK }}

# Clean Python build artifacts
py-clean-build:
    @echo "Removing build artifacts"
    rm -rf {{ PY_SDK }}/dist

# Build and test documentation
docs-test:
    uv run mkdocs build -s

# Build documentation
docs-build:
    uv run mkdocs build --clean

# Build and serve documentation
docs-serve:
    uv run mkdocs serve

# CPU profiling with py-spy (requires sudo)
py-prof-cpu output="sdks/python/prof/cpu_prof.svg" depth="2000" iter="100" mode="current":
    sudo PYTHONPATH="{{ PY_SDK }}/src:$PYTHONPATH" \
    uv run --directory {{ PY_SDK }} --group prof py-spy record \
    -o {{ output }} \
    --format flamegraph \
    --rate 20 \
    -- \
    python -m prof.profile_predicate --depth={{ depth }} --iter={{ iter }} --mode={{ mode }}
    sudo chown "$(id -un):$(id -gn)" {{ output }}
    chmod u+rw {{ output }}

# Memory profiling with memray
py-prof-mem binoutput="sdks/python/prof/memory.bin" output="sdks/python/prof/mem_flamegraph.html" depth="2000" iter="100" mode="current":
    uv run --directory {{ PY_SDK }} --group prof memray run \
        --force \
        -o {{ binoutput }} \
        -m prof.profile_predicate --depth {{ depth }} --iter={{ iter }} --mode={{ mode }} \
    && uv run --directory {{ PY_SDK }} --group prof memray flamegraph \
        --force \
        -o {{ output }} \
        {{ binoutput }}
