#!/bin/bash
set -e
cd "$(dirname "$0")"
pip install -r requirements.txt
pytest -q
uvicorn app.main:app --reload
