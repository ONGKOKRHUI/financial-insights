"""
Root-level pytest configuration for FinSight integration tests.

These tests make real HTTP calls to a live backend.  They are intentionally
separate from the unit tests in src/backend/tests/ (which use an in-memory
SQLite database and require no running server).

Usage
-----
Against the live Render deployment (default):
    pytest tests/test_phase3_api_integration.py -v

Against a local backend:
    FINSIGHT_BASE_URL=http://localhost:8000 pytest tests/test_phase3_api_integration.py -v
"""
