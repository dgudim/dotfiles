#!/usr/bin/env bash

path="$1"
cd $path

if [ -f ./.envrc ]; then
	. .envrc
fi

if [ -d ./.venv ]; then
  source ./.venv/bin/activate
elif [ -d ./venv ]; then
  source ./venv/bin/activate
elif [ -f ./pyproject.toml ]; then
  $(poetry env activate)
fi

# exec basedpyright-langserver --stdio https://akselmo.dev/posts/kate-and-basedpyright/ || https://akselmo.dev/posts/kate-python-lsp/
exec pylsp --check-parent-process
