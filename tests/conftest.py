"""
Pytest configuration for conda-subchannel tests
"""
import os
import pytest


@pytest.fixture(scope="session", autouse=True)
def configure_conda_cache(tmp_path_factory):
    """
    Configure conda to use a persistent cache directory for test sessions.
    This significantly speeds up tests by avoiding repeated downloads of repodata.
    """
    # Create a persistent cache directory for the entire test session
    cache_dir = tmp_path_factory.mktemp("conda_cache", numbered=False)
    
    # Set environment variables for conda caching
    # These tell conda where to cache downloaded repodata
    os.environ["CONDA_PKGS_DIRS"] = str(cache_dir / "pkgs")
    os.environ["CONDA_REPODATA_CACHE_DIR"] = str(cache_dir / "repodata_cache")
    
    # Enable aggressive local repodata caching for faster test runs
    os.environ["CONDA_LOCAL_REPODATA_TTL"] = "604800"  # 7 days
    os.environ["CONDA_REPODATA_USE_CACHE"] = "true"  # Always use cache when available
    
    return cache_dir

