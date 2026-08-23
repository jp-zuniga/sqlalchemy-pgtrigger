set dotenv-load
set quiet

########################################################################################

prek_toml := justfile_directory() + "/.prek.toml"

########################################################################################

[private]
default:
    @just --list --list-heading "" --list-prefix ""

########################################################################################

[private]
check-dep cmd pretty="":
    #!/usr/bin/env bash
    set -euo pipefail

    PRETTY="{{ pretty }}"

    if [ -z "$PRETTY" ]; then
      PRETTY="{{ cmd }}"
    fi

    if ! command -v {{ cmd }} > /dev/null 2>&1; then
      echo "\`$PRETTY\` debe estar instalado." >&2
      exit 1
    fi

[private]
check-uv:
    @just check-dep uv

[private]
pre-commit: full-check full-fix test

[private]
run-frozen *cmd: check-uv
    uv run --frozen {{ cmd }}

########################################################################################

[group("uv")]
check *args="":
    @just run-frozen ty check --no-progress {{ args }}

[group("uv")]
full-check: check lint

[group("uv")]
full-fix: (check "--fix") (lint "--fix") fmt

[group("uv")]
fix *args="":
    @just lint --fix {{ args }}

[group("uv")]
fmt *args="": (check-dep "prettier")
    @just run-frozen ruff format {{ args }}
    @just run-frozen tombi format
    prettier --write .

[group("uv")]
init:
    @just sync
    @just prek install

[group("uv")]
lint *args="":
    @just run-frozen ruff check --unsafe-fixes {{ args }}
    @just run-frozen tombi lint

[group("uv")]
prek *args:
    @just run-frozen prek -c {{ prek_toml }} {{ args }}

[group("uv")]
repl *args="":
    @just run-frozen python {{ args }}

[group("uv")]
sync: check-uv
    uv sync --frozen

[group("uv")]
test *args="":
    @just run-frozen pytest {{ args }}

[group("uv")]
zen:
    @just run-frozen zensical serve
