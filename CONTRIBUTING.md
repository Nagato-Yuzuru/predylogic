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
Please note this documentation assumes you already have **`uv`**, **`just`**, and **`Git`** installed and ready to go.

1. Fork the `predylogic` repo on GitHub.

2. Clone your fork locally:

```bash
cd <directory_in_which_repo_should_be_created>
git clone git@github.com:YOUR_NAME/predylogic.git
```

3. Navigate into the directory:

```bash
cd predylogic
```

4. Install the environment and hooks.
   This command will use `uv` to create a virtual environment and install `pre-commit` hooks (including commit-message
   linting):

```bash
just py-install
```

5. Create a branch for local development:

```bash
git checkout -b name-of-your-bugfix-or-feature
```

Now you can make your changes locally.

6. Don't forget to add test cases for your added functionality to the `tests` directory.
7. When you're done making changes, run the code quality suite.
   This runs dependency checks (`tach`, `deptry`), type checking (`ty`), and linters:

```bash
just py-check
```

8. Validate that all unit tests are passing:

```bash
just py-test
```

9. (Optional) If you modified the documentation, you can preview it locally:

For example, when modifying Python documentation:

```bash
just py-docs
```

10. Commit your changes and push your branch to GitHub.
    **Note:** We follow **Conventional Commits**. Your commit message will be verified by the `commit-msg` hook
    installed in step 4.

```bash
git add .
git commit -m "feat: add support for new predicate types"
# or "fix: resolve issue with registry lookup"
git push origin name-of-your-bugfix-or-feature
```

11. Submit a pull request through the GitHub website.

# Pull Request Guidelines

Before you submit a pull request, check that it meets these guidelines:

1. The pull request should include tests.
2. The pull request must pass all CI/CD checks (linting, testing, type checking).
3. If the pull request adds functionality, the docs should be updated.
   Put your new functionality into a function with a docstring, and add the feature to the list in `README.md`.
