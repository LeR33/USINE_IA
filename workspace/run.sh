#!/bin/bash
pip install -r requirements.txt
pytest tests/test_all.py
uvicorn app.main:app --reload
