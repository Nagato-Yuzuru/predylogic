# Contributing to `predylogic`

Contributions are welcome, and they are greatly appreciated!
Every little bit helps, and credit will always be given.

You can contribute in many ways:

# Types of Contributions

## Report Bugs

Report bugs at https://github.com/Nagato-Yuzuru/predylogic/issues

If you are reporting a bug, please include:

- Your operating system name and version.
- Any details about your local setup that might be helpful in troubleshooting.
- Detailed steps to reproduce the bug.

## Fix Bugs

Look through the GitHub issues for bugs.
Anything tagged with "bug" and "help wanted" is open to whoever wants to implement a fix for it.

## Implement Features

Look through the GitHub issues for features.
Anything tagged with "enhancement" and "help wanted" is open to whoever wants to implement it.

## Write Documentation

predylogic could always use more documentation, whether as part of the official docs, in docstrings, or even on the
web in blog posts, articles, and such.

## Submit Feedback

The best way to send feedback is to file an issue at https://github.com/Nagato-Yuzuru/predylogic/issues.

If you are proposing a new feature:

- Explain in detail how it would work.
- Keep the scope as narrow as possible, to make it easier to implement.
- Remember that this is a volunteer-driven project, and that contributions
  are welcome :)

# Get Started!

Ready to contribute? Here's how to set up `predylogic` for local development.

This project uses **[`mise`](https://mise.jdx.dev)** to manage its toolchain (`uv`, `just`, `prek`, `git-cliff`).
The only prerequisites you need on your machine are **`mise`** and **`Git`** — everything else is pinned in `mise.toml`
and installed automatically.

1. Fork the `predylogic` repo on GitHub and clone your fork:

    ```bash
    git clone git@github.com:YOUR_NAME/predylogic.git
    cd predylogic
    ```

2. Trust and install the toolchain:

    ```bash
    mise trust
    mise install
    ```

    This reads `mise.toml` and installs `uv`, `just`, `prek`, and `git-cliff` at the versions declared there. Make sure
    mise shims are active in your shell (`mise activate`, see the mise docs).

3. Install Python dependencies and the git hooks:

    ```bash
    just install
    ```

    This runs `uv sync` and installs `prek` hooks for both `pre-commit` and `commit-msg`.

4. Create a branch for local development:

    ```bash
    git checkout -b name-of-your-bugfix-or-feature
    ```

5. Add tests for any new behavior under `sdks/python/tests/`.

6. Run the quality suite — this runs type checking (`ty`), linting (`ruff`), and dependency checks (`deptry`, `tach`):

    ```bash
    just py-check
    ```

7. Run the tests:

    ```bash
    just py-test
    ```

8. (Optional) Preview documentation changes:

    ```bash
    just docs-serve
    ```

9. Stage and commit your changes. **Stage specific files** rather than `git add .` to avoid pulling in local artifacts
   (profile output, coverage files, notes). We follow **Conventional Commits**; the `commit-msg` hook installed in
   step 3 will reject commits that don't conform:

    ```bash
    git add path/to/changed/files
    git commit -m "feat: add support for new predicate types"
    git push origin name-of-your-bugfix-or-feature
    ```

10. Open a pull request against `main` on GitHub.

# Pull Request Guidelines

Before you submit a pull request, check that it meets these guidelines:

1. The pull request includes tests for the new or changed behavior.
2. The pull request passes all CI checks (`prek`, `ty`, `ruff`, `deptry`, `tach`, pytest across the Python matrix).
3. Public API changes are reflected in Google-style docstrings on `src/`, and — if user-visible — in `docs/` and the
   `README.md` feature narrative.
