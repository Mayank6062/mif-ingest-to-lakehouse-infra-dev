"""
Top-level app package shim.

This file makes `import app.*` resolve to `backend/app/*` during tests
when running from the repository root. It's a minimal compatibility shim
so tests that expect `app` as a top-level package can import modules
without changing their imports.

Do NOT use this file to change architecture or merge runtime behavior.
"""
import os

# Make `app` a namespace package that points at `backend/app`.
ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_APP = os.path.join(ROOT, 'backend', 'app')

if os.path.isdir(BACKEND_APP):
    # Replace package search path so subpackages (e.g., app.graph)
    # resolve to backend/app/graph, backend/app/services, etc.
    __path__[:] = [BACKEND_APP]

