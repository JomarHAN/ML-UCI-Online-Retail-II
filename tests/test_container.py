"""Container integration tests for the UCI Online Retail API.

These test are FUNDAMENTALLY DIFFERENT from `tests/test_api.py`:
    tests/test_api.py uses FastAPI's TestClient - calls the app in-process,
    bypassing HTTP, ports, networking, and the container runtime entirely.
    Fast (<1s startup) but catches only application-logic bugs.
    
    tests/test_container.py (this file) starts the actual Docker container,
    hits it over real HTTP at a real port, and validates behavior at the 
    container boundary. Slow (1-3 min startup) but catches a different class
    of bugs that TestClient cannot see:
    
        - Port mapping / networking issues
        - Permission errors from the non-root user
        - Missing system libraries (libgomp, etc.)
        - Volume mount permission/path issues
        - Slow startup that exceeds healthcheck windows
        - Environment variable propagation
        - Graceful shutdown via SIGTERM
        - HTTP correctness through a real network stack (headers, encoding)
        - Concurrent request handling
        - Docker HEALTHCHECK correctness
        
If Docker is not available, all tests in this file SKIP rather than fail.
Run from the repo root:
    uv run pytest tests/test_container.py -v
"""
from __future__ import annotations

import json
import shutil
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx2
import pytest

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
IMAGE_NAME = "uci-retail-api"
TAG = "test"
CONTAINER_NAME = "uci-retail-test"
TEST_PORT = 8002    # avoid colliding with dev server (8000) or smoke test (8001)
STARTUP_TIMEOUT_S = 120     # how long we'll wait for /health to return 200
PROJECT_ROOT = Path(__file__).resolve().parents[1]


# -----------------------------------------------------------------------------
# Helpers -wrap docker CLI via subprocess. We use subprocess (not docker-py)
# so these tests run on any machine with `docker` installed, no extra Python
# dependencies required.
# -----------------------------------------------------------------------------
def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command, capturing stdout/stderr. Helpful in test output on failure."""
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def docker_available() -> bool:
    """Is Docker installed AND the daemon running?"""
    if shutil.which("docker") is None:
        return False
    result = run(["docker", "info"])
    return result.returncode == 0


def is_port_free(port: int) -> bool:
    """True if `port` on localhost is not already bound."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0
    

def image_exists(image: str) -> bool:
    """Has the image been built locally?"""
    result = run(["docker", "image", "inspect", image])
    return result.returncode == 0


def remove_container(name: str) -> None:
    """Force-remove a container if it exists. Idempotent."""
    run(["docker", "rm", "-f", name])   # ignore errors
    
    
def container_logs(name: str, lines: int = 100) -> str:
    """Capture container logs for diagnostics on failure."""
    result = run(["docker", "logs", "--tail", str(lines), name])
    return (result.stdout or "") + (result.stderr or "")


def container_inspect(name: str) -> dict:
    """Return docker inspect JSON as a Python dict."""
    result = run(["docker", "inspect", name])
    if result.returncode != 0:
        return {}
    return json.loads(result.stdout)[0]


def wait_for_healthy(url: str, timeout_s: int) -> bool:
    """Poll /health until 200 OK, with a timeout. Returns True on success."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            r = httpx2.get(url, timeout=2.0)
            if r.status_code == 200:
                return True
        except (httpx2.RequestError, httpx2.HTTPError):
            pass
        time.sleep(2)
    return False

# -----------------------------------------------------------------------------
# Skip everything in this file if Docker isn't available - graceful degradation
# rather than failing on reviewer/CI machines without Docker.
# -----------------------------------------------------------------------------
pytestmark = pytest.mark.skipif(
    not docker_available(),
    reason="Docker not installed or daemon not running."
)


# -----------------------------------------------------------------------------
# Session-scoped fixture: build image (once), run container, tear down after
# -----------------------------------------------------------------------------
@pytest.fixture(scope="session")
def container():
    """Boot the API container for the entire test session.
    
    Steps:
        1. Build the image if not already present
        2. Ensure port and container name are free
        3. Verify required artifacts (models/, data/processed/) exist on host
        4. Run the container with bind mounts and port mapping
        5. Wait for /health to return 200
        6. Yield the base URL to tests
        7. On teardown, stop and remove the container regardless of test outcome
    """
    # 1. Build the image (only if missing - saves time across runs)
    full_image = f"{IMAGE_NAME}:{TAG}"
    if not image_exists(full_image):
        print(f"\n[container] Building {full_image} (this takes 2-5 minutes...)")
        build_result = run(
            ["docker", "build", "-t", full_image, str(PROJECT_ROOT)]
        )
        if build_result.returncode != 0:
            pytest.fail(
                f"docker build failed:\nSTDOUT:\n{build_result.stdout}\nSTDERR:\n{build_result.stderr}"
            )
    else:
        print(f"\n[container] Reusing existing image {full_image}")
        
    # 2. Free up the port and container name (in case a prior run left them)
    remove_container(CONTAINER_NAME)
    if not is_port_free(TEST_PORT):
        pytest.fail(
            f"Port {TEST_PORT} is in use. Stop whatever is listening on it "
            f"(e.g., a previous test container) and re-run."
        )
    
    # 3. Verify host-side artifacts exist. The container mounts these read-only;
    # if they're missing, the API will start but fail to serve real customers.
    models_dir = PROJECT_ROOT / "models"
    processed_dir = PROJECT_ROOT / "data" / "processed"
    required = [
        models_dir / "clv_xgboost.joblib",
        models_dir / "churn_xgboost.joblib",
        processed_dir / "customer_segments.parquet",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        pytest.skip(
            "Required artifacts not found (run notebooks 01-08 first): "
            + ", ".join(missing)
        )
        
    # 4. Run the container, mounting the models and data read-only so the
    # container sees the same artifacts a real deployment would.
    run_cmd = [
        "docker", "run", "-d",
        "--name", CONTAINER_NAME,
        "-p", f"{TEST_PORT}:8000",
        "-v", f"{models_dir}:/app/models:ro",
        "-v", f"{processed_dir}:/app/data/processed:ro",
        "-e", "PYTHONUNBUFFERED=1",
        full_image
    ]
    print(f"[container] Starting: {' '.join(run_cmd)}")
    result = run(run_cmd)
    if result.returncode != 0:
        pytest.fail(f"docker run failed:\n{result.stderr}")
        
    base_url = f"http://localhost:{TEST_PORT}"
    
    # 5. Wait for the app to become healthy. Model loading takes 5-20s after
    # startup, so we poll /health for up to STARTUP_TIMEOUT_S seconds.
    print(f"[container] Waiting for {base_url}/health...")
    if not wait_for_healthy(f"{base_url}/health", STARTUP_TIMEOUT_S):
        logs = container_logs(CONTAINER_NAME, lines=200)
        remove_container(CONTAINER_NAME)
        pytest.fail(
            f"Container did not become healthy within {STARTUP_TIMEOUT_S}s.\n"
            f"Last 200 lines of logs:\n{logs}"
        )
    print(f"[container] Healthy at {base_url}")
    
    # 6. Hand control to tests.
    yield base_url
    
    # 7. Always tear down, even to test failure.
    print(f"\n[container] Stopping {CONTAINER_NAME}...")
    remove_container(CONTAINER_NAME)
    
    
@pytest.fixture(scope="session")
def client(container) -> httpx2.Client:
    """Pre-configured httpx2 client pointed at the running container."""
    with httpx2.Client(base_url=container, timeout=10.0) as c:
        yield c
        
        
@pytest.fixture(scope="session")
def known_customer_id(client) -> str:
    """A real CustomerID, fetched from the running API itself.
    
    Avoids hardcoding an ID that may not exist in the user's data, and tests
    the /customers/top endpoint along the way.
    """
    response = client.get("/customers/top", params={"n":1})
    assert response.status_code == 200, response.text
    return response.json()["customers"][0]["customer_id"]


# ============================================================================
# Tests
# ============================================================================

# -----------------------------------------------------------------------------
# Group 1: Container lifecycle and runtime properties
# -----------------------------------------------------------------------------
@pytest.mark.usefixtures("container")
class TestContainerRuntime:
    """Thngs that are only testable against a real running container."""
    
    def test_container_is_runnning(self):
        """`docker ps` should show our container in the 'running' state."""
        info = container_inspect(CONTAINER_NAME)
        assert info, "Container not found in `docker inspect`"
        assert info["State"]["Running"] is True, info["State"]
        
    def test_container_runs_as_not_root_user(self):
        """Security: the process inside shold be running as 'app', not root.
        
        This catches the regression where someone accidentally removes
        `USER app` from the Dockerfile.
        """
        result = run(["docker", "exec", CONTAINER_NAME, "whoami"])
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "app", (
            f"Container running as '{result.stdout.strip()}', expected 'app'. "
            f"Check the USER directive in the Dockerfile."
        )
        
    def test_container_has_required_system_libs(self):
        """libgomp1 is needed by XGBoost/LightGBM. Without it the app crashes
        on import. This test catches a missing apt-get install in the runtime stage.
        """
        # libgomp.so.1 should be findable. ldconfig -p lists what's available
        result = run(["docker", "exec", CONTAINER_NAME, "ldconfig", "-p"])
        assert result.returncode == 0
        assert "libgomp.so.1" in result.stdout, (
            "libgomp.so.1 not present in the container - XGBoost won't work. "
            "Check the apt-get install line in the runtime stage."
        )
        
    def test_container_python_version(self):
        """Pin: the container shold run the same Python version as declared in
        pyproject.toml. Catches accidental base-iamge changes."""
        result = run(["docker", "exec", CONTAINER_NAME, "python", "--version"])
        assert result.returncode == 0
        assert "Python 3.12" in result.stdout, result.stdout
        
    def test_container_has_healthcheck_configured(self):
        """Docker's HEALTHCHECK is what AWS ECS uses to route traffic.
        If it's missing, ECS doesn't know when the app is ready."""
        info = container_inspect(CONTAINER_NAME)
        healthcheck = info["Config"].get("Healthcheck")
        assert healthcheck is not None, "Container has no HEALTHCHECK"
        assert "CMD" in healthcheck["Test"][0] or healthcheck["Test"][0] == "CMD"
        
    def test_container_eventually_becomes_healthy(self):
        """Docker's healthycheck should mark the container as 'healthy' after
        a few interval cycles. We wait up to 90s for the state to settle."""
        deadline = time.time() + 90
        last_status = None
        while time.time() < deadline:
            info = container_inspect(CONTAINER_NAME)
            health = info.get("State", {}).get("Health", {})
            last_status = health.get("Status")
            if last_status == "healthy":
                return
            time.sleep(5)
        pytest.fail(
            f"Container healthcheck status is '{last_status}' (expected 'healthy')"
        )
        

# -----------------------------------------------------------------------------
# Group 2: HTTP correctness over a real socket
# -----------------------------------------------------------------------------
class TestHTTPCorrectness:
    """Things that only matter when going through a real HTTP stack - 
    headers, encoding, network errors. TestClient bypasses all of this."""
    
    def test_health_responds_quicky(self, client):
        """The /health endpoint should respondin well under a second.
        Slow /health = bad healthcheck = bad load balancer behavior."""
        start = time.perf_counter()
        r = client.get("/health")
        elapsed = time.perf_counter() - start
        assert r.status_code == 200
        assert elapsed < 1.0, f"/health took {elapsed:.2f}s - too slow"
        
    def test_content_type_is_json(self, client):
        """Production clients (Shopify webhooks, ect.) parse the response based
        on Content-Type. FastAPI sets it correctly but verify."""
        r = client.get("/health")
        assert r.headers["content-type"].startswith("application/json")
        
    def test_response_is_valid_json(self, client):
        """If the response body isn't parseable JSON, clients will fail.
        This catches accidental returns of strings/objects that aren't 
        JSON-serializable (the numpy.bool issue from Notebook 08)."""
        r = client.get("/customers/top", params={"n": 3})
        assert r.status_code == 200
        # Will raise if not valid JSON
        body = r.json()
        assert isinstance(body, dict)
        assert "customers" in body
        
    def test_validation_error_returns_422(self, client):
        """Pydantic validation errors should come back as 422 with a structured
        body explaining what went wrong."""
        r = client.get("/customers/top", params={"n": -1})
        assert r.status_code == 422
        assert "detail" in r.json()
        
    def test_unknown_customer_returns_404(self, client):
        """Real 404 over real HTTP - not a TestClient mock."""
        r = client.get("/customers/not-existing-customer/recommendation")
        assert r.status_code == 404
        
    def test_unknown_route_returns_404(self, client):
        """Routes that don't exist should 404, not 500 or hang."""
        r = client.get("/this/is/not/a/route")
        assert r.status_code == 404
        
        
# -----------------------------------------------------------------------------
# Group 3: End-to-end happy paths through the container
# -----------------------------------------------------------------------------
class TestEndpointsAgainstContainer:
    """Same logical tests as test_api.py, but going through real HTTP +
    the actual container. Validates that the deployment artifact works."""
    
    def test_health_payload(self, client):
        body = client.get("/health").json()
        assert body["status"] == "ok"
        assert body["n_customers"] > 0
        assert "clv_xgboost" in body["models_loaded"]
        assert "churn_xgboost" in body["models_loaded"]
        
    def test_top_customers(self, client):
        body = client.get("/customers/top", params={"n": 5}).json()
        assert body["n_returned"] == 5
        # Sorted descending by priority
        priorities = [c["priority_score"] for c in body["customers"]]
        assert priorities == sorted(priorities, reverse=True)
        
    def test_full_recommendation(self, client, known_customer_id):
        r = client.get(f"/customers/{known_customer_id}/recommendation")
        assert r.status_code == 200
        body = r.json()
        # Required fields per schema
        assert body["customer_id"] == known_customer_id
        assert "segment" in body
        assert "strategy_quadrant" in body
        assert 0 <= body["metrics"]["churn_risk"] <= 1
        assert body["metrics"]["predicted_clv_90d_gbp"] >= 0
        assert isinstance(body["churn_drivers"], list)
        
    def test_risk_endpoint_consistency(self, client, known_customer_id):
        """p_active + churn_risk must equal 1.0 (within float tolerance).
        Catches a polarity-flip bug."""
        body = client.get(f"/customers/{known_customer_id}/risk").json()
        total = body["p_active"] + body["churn_risk"]
        assert abs(total - 1.0) < 1e-6
        
# -----------------------------------------------------------------------------
# Group 4: Concurrency - does the app survice parallel load?
# -----------------------------------------------------------------------------
class TestConcurrency:
    """The TestClient runs requests serially. Real HTTP servers handle
    parallel client. This catches threading / state-sharing bugs."""
    
    def test_concurrent_health_requests(self, client, container):
        """50 parallel /health requests should all succeed.
        Sequential bugs (shared mutable state, missing locks) surface here."""
        url = f"{container}/health"
        
        def do_request():
            return httpx2.get(url, timeout=5.0).status_code
        
        with ThreadPoolExecutor(max_workers=20) as pool:
            results = list(pool.map(lambda _: do_request(), range(50)))
            
        failed = [r for r in results if r != 200]
        assert not failed, f"{len(failed)} of requests failed: {failed[:5]}"
        
    def test_concurrent_recommendation_requests(self, client, container, known_customer_id):
        """Parallel recommendation requests (more expensive - they run SHAP).
        Test that the SHAP explainer is safe to call from multiple threads."""
        url = f"{container}/customers/{known_customer_id}/recommendation"
        
        def do_request():
            r = httpx2.get(url, timeout=15.0)
            return r.status_code, r.elapsed.total_seconds()
        
        with ThreadPoolExecutor(max_workers=10) as pool:
            features = [pool.submit(do_request) for _ in range(20)]
            results = [f.result() for f in as_completed(features)]
            
        statuses = [s for s, _ in results]
        latencies = [t for _, t in results]
        assert all(s == 200 for s in statuses), f"Statuses: {statuses}"
        # Even under load, p95 latency should be reasonable
        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]
        assert p95 < 5.0, f"p95 latency {p95:.2f}s under concurrent load is too slow"
        

# -----------------------------------------------------------------------------
# Group 5: Graceful shutdown - SIGTERM handling
# -----------------------------------------------------------------------------
class TestGracefulShutdown:
    """ECS sends SIGTERM during deployments. The container should drain 
    in-flight requests and exit cleanly, NOT get killed mod-request.
    
    Note: these tests stop the container, so they run LAST (alphabetical
    ordering puts 'Z' last; we name the class with a leading underscore
    plus zzz prefix in test names to force ordering).
    """
    
    def test_zzz_container_handles_sigterm_gracefully(self):
        """`docker stop` sends SIGTERM, waits 10s, then SIGKILL.
        A well-behaved container exits on SIGTERM in well under 10s.
        If we hit SIGKILL, the exit code shows it (137 = 128 + SIGKILL=9)."""
        # Stop the container, capture timing and exit code
        start = time.time()
        result = run(["docker", "stop", "--time", "15", CONTAINER_NAME])
        elapsed = time.time() - start
        assert result.returncode == 0, f"docker stop failed: {result.stderr}"
        
        # Check exit code: 0 (clean exit) or 143 (128 + SIGTERM=15) is OK
        # 137 (128 + SIGKILL=9) means we had to force-kill it
        info = container_inspect(CONTAINER_NAME)
        exit_code = info["State"]["ExitCode"]
        assert exit_code in (0, 143), (
            f"Container exited with code {exit_code} after {elapsed:.1f}s. "
            f"Exit code 137 means SIGKILL was needed - graceful shutdown failed."
        )
        assert elapsed < 14, (
            f"Container took {elapsed:.1f}s to stop - shutdown is too slow."
        )
        
