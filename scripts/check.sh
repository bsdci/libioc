#!/bin/sh
# Run all static checks: flake8, mypy and bandit.
# Tool configuration lives in setup.cfg; bandit options are given below.
set -e
cd "$(dirname "$0")/.."

flake8 --version
mypy --version
bandit --version 2>&1 | head -n 1

flake8
mypy libioc/ setup.py
bandit --quiet --skip B404,B110 \
    -x ./tests,./docs,./stubs,./tools,./scripts,./.venv,./.git,./.eggs \
    -r .
