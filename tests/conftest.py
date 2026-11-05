import shutil
import pytest
from core.config import PROJECTS_DIR

@pytest.fixture(autouse=True)
def auto_cleanup_test_projects():
    """Ensure any project directory created during test execution is deleted when done testing."""
    existing_dirs = set(d.name for d in PROJECTS_DIR.iterdir()) if PROJECTS_DIR.exists() else set()
    yield
    if PROJECTS_DIR.exists():
        for d in list(PROJECTS_DIR.iterdir()):
            if d.is_dir() and d.name not in existing_dirs:
                if d.name.lower().startswith("test") or "cleanup" in d.name.lower():
                    shutil.rmtree(d, ignore_errors=True)


def pytest_sessionfinish(session, exitstatus):
    """Safety net: clean up all lingering test projects from PROJECTS_DIR when test session ends."""
    if PROJECTS_DIR.exists():
        for d in list(PROJECTS_DIR.iterdir()):
            if d.is_dir() and (d.name.lower().startswith("test_") or d.name.startswith("Test ") or "cleanup" in d.name.lower()):
                shutil.rmtree(d, ignore_errors=True)
