default:
    @just --list

# Install the virtual environment and install the pre-commit hooks
install:
    @echo "Creating virtual environment using uv"
    uv sync
    uv run pre-commit install && uv run pre-commit  install --hook-type commit-msg

# Run code quality tools.
check:
    @echo "Checking lock file consistency with 'pyproject.toml'"
    uv lock --locked
    @echo "Linting code: Running pre-commit"
    uv run pre-commit run -a
    @echo "Static type checking: Running ty"
    uv run ty check
    @echo "Checking for obsolete dependencies: Running deptry"
    uv run deptry src
    @echo "Checking for dependency: Running tach"
    uv run tach check

# Test the code with pytest
test:
    @echo "Testing code: Running pytest"
    uv run python -m pytest --cov --cov-config=pyproject.toml --cov-report=xml

# Build wheel file
build: clean-build
    @echo "Creating wheel file"
    uvx --from build pyproject-build --installer uv

# Clean build artifacts
clean-build:
    @echo "Removing build artifacts"
    uv run python -c "import shutil; import os; shutil.rmtree('dist') if os.path.exists('dist') else None"

# Test if documentation can be built without warnings or errors
docs-test:
    uv run mkdocs build -s

# Build and serve the documentation
docs:
    uv run mkdocs serve
