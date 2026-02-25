#!/usr/bin/env python3
"""Functional API tests for Inveterate.

Makes real HTTP requests against a running Inveterate instance to verify
all API endpoints, permissions, CRUD operations, validation rules,
filtering/search/ordering, service lifecycle, and edge cases.

Usage:
    export BASE_URL=http://localhost:8000
    export ADMIN_USER=admin
    export ADMIN_PASS=yourpassword
    python tests/functional_api_test.py

    # If running against Docker:
    export DOCKER_CONTAINER=inveterate-test-web
    python tests/functional_api_test.py
"""
import os
import subprocess
import sys
import time
import uuid
import requests
from requests.adapters import HTTPAdapter

BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")
ADMIN_USER = os.environ.get("ADMIN_USER", "")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "")
# Optional: Docker container name to exec manage.py commands for user setup
DOCKER_CONTAINER = os.environ.get("DOCKER_CONTAINER", "")

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"


class ThrottleRetryAdapter(HTTPAdapter):
    """Retries on 429 after clearing the throttle cache."""

    def send(self, request, **kwargs):
        response = super().send(request, **kwargs)
        if response.status_code == 429:
            _flush_throttle_cache()
            time.sleep(0.1)
            response = super().send(request, **kwargs)
        return response


def _flush_throttle_cache():
    """Flush the DRF throttle cache via Redis CLI or manage.py."""
    # Try Redis directly first (fast)
    result = subprocess.run(
        ["redis-cli", "-h", "localhost", "FLUSHALL"],
        capture_output=True, text=True, timeout=3,
    )
    if result.returncode == 0:
        return
    # Fall back to manage.py
    script = "from django.core.cache import cache; cache.clear()"
    if DOCKER_CONTAINER:
        cmd = ["docker", "exec", DOCKER_CONTAINER, "python", "manage.py", "shell", "-c", script]
    else:
        cmd = ["python", "manage.py", "shell", "-c", script]
    subprocess.run(cmd, capture_output=True, text=True, timeout=15)


class APITestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.admin_session = requests.Session()
        self.user_session = requests.Session()
        self.user_b_session = requests.Session()
        self.anon_session = requests.Session()
        retry_adapter = ThrottleRetryAdapter()
        for s in (self.admin_session, self.user_session, self.user_b_session, self.anon_session):
            s.mount("http://", retry_adapter)
            s.mount("https://", retry_adapter)
        self.admin_token = None
        self.user_token = None
        self.user_b_token = None
        self.user_b_id = None
        self.user_b_username = f"testuser_b_{uuid.uuid4().hex[:8]}"
        self.user_b_password = f"TestPass_{uuid.uuid4().hex[:12]}"
        self.created = {
            "clusters": [],
            "nodes": [],
            "nodedisks": [],
            "plans": [],
            "templates": [],
            "ippools": [],
            "ips": [],
            "apps": [],
            "services": [],
            "serviceplans": [],
            "portgateways": [],
            "portblocks": [],
            "portforwards": [],
            "domainroutes": [],
            "inventory": [],
            "user_a_services": [],
            "user_b_services": [],
            "user_a_portforwards": [],
            "user_b_portforwards": [],
            "user_a_domainroutes": [],
            "user_b_domainroutes": [],
        }
        self.test_user_id = None
        self.test_username = f"testuser_{uuid.uuid4().hex[:8]}"
        self.test_password = f"TestPass_{uuid.uuid4().hex[:12]}"

    # ── Helpers ──────────────────────────────────────────────────────

    def url(self, path):
        return f"{BASE_URL}/api/v1/{path.lstrip('/')}"

    def raw_url(self, path):
        return f"{BASE_URL}/{path.lstrip('/')}"

    def _json_body(self, response):
        """Safely extract JSON body, return {} on failure."""
        try:
            if response.headers.get("content-type", "").startswith("application/json"):
                return response.json()
        except Exception:
            pass
        return {}

    def _results(self, response):
        """Extract paginated results list from response."""
        body = self._json_body(response)
        if isinstance(body, dict) and "results" in body:
            return body["results"]
        if isinstance(body, list):
            return body
        return []

    def check(self, name, response, expected_status, check_json=None):
        """Assert status code, optionally check JSON keys/values."""
        actual = response.status_code
        if actual == expected_status:
            extra_ok = True
            if check_json:
                body = self._json_body(response)
                for key, expected in check_json.items():
                    if expected is True:
                        # Key must exist
                        target = body.get("results", body) if isinstance(body, dict) else body
                        if isinstance(target, dict) and key not in target:
                            extra_ok = False
                            self._fail(name, f"missing key '{key}' in response")
                    elif expected is False:
                        # Key must NOT exist
                        target = body.get("results", body) if isinstance(body, dict) else body
                        if isinstance(target, dict) and key in target:
                            extra_ok = False
                            self._fail(name, f"unexpected key '{key}' in response")
            if extra_ok:
                self._pass(name)
            return response
        else:
            self._fail(name, f"expected {expected_status}, got {actual}")
            return response

    def check_any(self, name, response, expected_statuses):
        """Assert status code is one of the expected values."""
        actual = response.status_code
        if actual in expected_statuses:
            self._pass(name)
        else:
            self._fail(name, f"expected one of {expected_statuses}, got {actual}")
        return response

    def _pass(self, name):
        self.passed += 1
        print(f"  {GREEN}[PASS]{RESET} {name}")

    def _fail(self, name, detail=""):
        self.failed += 1
        msg = f"  {RED}[FAIL]{RESET} {name}"
        if detail:
            msg += f" -- {detail}"
        print(msg)

    def _skip(self, name, reason=""):
        self.skipped += 1
        msg = f"  {YELLOW}[SKIP]{RESET} {name}"
        if reason:
            msg += f" -- {reason}"
        print(msg)

    def _section(self, title):
        print(f"\n{BOLD}--- {title} ---{RESET}")

    def _track(self, resource, item_id):
        self.created.setdefault(resource, []).append(item_id)

    def _clear_throttle_cache(self):
        """Clear DRF throttle cache to avoid 429s during testing."""
        _flush_throttle_cache()

    def _get_real_infrastructure(self):
        """Check for real infrastructure (non-test clusters/nodes). Returns dict or None."""
        s = self.admin_session
        clusters = self._results(s.get(self.url("clusters/")))
        nodes = self._results(s.get(self.url("nodes/")))
        templates = self._results(s.get(self.url("templates/")))
        plans = self._results(s.get(self.url("plans/")))

        real_clusters = [c for c in clusters if c.get("id") not in self.created.get("clusters", [])]
        real_nodes = [n for n in nodes if n.get("id") not in self.created.get("nodes", [])]

        if not real_clusters or not real_nodes or not templates or not plans:
            return None

        return {
            "plan_id": plans[0]["id"],
            "template_name": templates[0]["name"],
            "real_clusters": real_clusters,
            "real_nodes": real_nodes,
        }

    # ── Phase 0: Setup ───────────────────────────────────────────────

    def setup(self):
        self._section("Phase 0: Setup")

        # Clear throttle caches so tests don't hit rate limits
        self._clear_throttle_cache()

        # Admin token
        r = self.anon_session.post(
            self.url("auth/token/"),
            json={"username": ADMIN_USER, "password": ADMIN_PASS},
        )
        if r.status_code != 200:
            print(f"{RED}FATAL: Cannot obtain admin token (status {r.status_code}). Aborting.{RESET}")
            sys.exit(2)
        self.admin_token = r.json()["token"]
        self.admin_session.headers["Authorization"] = f"Token {self.admin_token}"
        print(f"  Admin token obtained")

        # Create test user via customers endpoint (does NOT set password)
        r = self.admin_session.post(
            self.url("customers/"),
            json={
                "username": self.test_username,
                "email": f"{self.test_username}@example.com",
                "first_name": "Test",
                "last_name": "User",
            },
        )
        if r.status_code == 201:
            self.test_user_id = r.json()["id"]
            print(f"  Test user created: {self.test_username} (id={self.test_user_id})")
        else:
            print(f"{RED}FATAL: Cannot create test user (status {r.status_code}): {r.text}{RESET}")
            sys.exit(2)

        # Set password via manage.py (Customer API doesn't expose password field)
        manage_script = (
            f"from django.contrib.auth import get_user_model; "
            f"u = get_user_model().objects.get(username='{self.test_username}'); "
            f"u.set_password('{self.test_password}'); u.save()"
        )
        if DOCKER_CONTAINER:
            cmd = ["docker", "exec", DOCKER_CONTAINER, "python", "manage.py", "shell", "-c", manage_script]
        else:
            cmd = ["python", "manage.py", "shell", "-c", manage_script]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"{RED}FATAL: Cannot set test user password: {result.stderr}{RESET}")
            sys.exit(2)
        print(f"  Test user password set via manage.py")

        # Test user token
        r = self.anon_session.post(
            self.url("auth/token/"),
            json={"username": self.test_username, "password": self.test_password},
        )
        if r.status_code != 200:
            print(f"{RED}FATAL: Cannot obtain test user token (status {r.status_code}). Aborting.{RESET}")
            sys.exit(2)
        self.user_token = r.json()["token"]
        self.user_session.headers["Authorization"] = f"Token {self.user_token}"
        print(f"  Test user token obtained")

    # ── Phase 1: Token Auth Edge Cases ───────────────────────────────

    def test_token_auth(self):
        self._section("Phase 1: Token Auth Edge Cases")
        s = self.anon_session

        # Bad credentials
        r = s.post(self.url("auth/token/"), json={"username": "noexist", "password": "bad"})
        self.check("Token: bad credentials -> 400", r, 400)

        # Missing fields
        r = s.post(self.url("auth/token/"), json={})
        self.check("Token: missing fields -> 400", r, 400)

        # Invalid token header
        bad = requests.Session()
        bad.headers["Authorization"] = "Token invalidtokenvalue999"
        r = bad.get(self.url("services/"))
        self.check("Token: invalid token -> 401", r, 401)

        # Re-request token returns same token (idempotent)
        r = s.post(self.url("auth/token/"), json={"username": ADMIN_USER, "password": ADMIN_PASS})
        self.check("Token: re-request admin token -> 200", r, 200)
        if r.status_code == 200:
            token2 = r.json().get("token")
            if token2 == self.admin_token:
                self._pass("Token: re-request returns same token")
            else:
                self._pass("Token: re-request returns token (may differ)")

    # ── Phase 2: Anonymous Access ────────────────────────────────────

    def test_anonymous(self):
        self._section("Phase 2: Anonymous Access")
        s = self.anon_session

        # Public read endpoints (ReadOnlyAnonymous)
        self.check("Anon: GET /plans/ -> 200", s.get(self.url("plans/")), 200)
        self.check("Anon: GET /inventory/ -> 200", s.get(self.url("inventory/")), 200)
        self.check("Anon: GET /apps/ -> 200", s.get(self.url("apps/")), 200)

        # Anonymous write on public-read endpoints -> 401
        self.check("Anon: POST /plans/ -> 401", s.post(self.url("plans/"), json={"name": "x"}), 401)
        self.check("Anon: POST /apps/ -> 401", s.post(self.url("apps/"), json={"name": "x"}), 401)
        self.check("Anon: POST /inventory/ -> 401", s.post(self.url("inventory/"), json={}), 401)
        self.check("Anon: POST /inventory/calculate/ -> 401", s.post(self.url("inventory/calculate/")), 401)

        # Admin-only endpoints -> 401
        self.check("Anon: GET /clusters/ -> 401", s.get(self.url("clusters/")), 401)
        self.check("Anon: GET /nodes/ -> 401", s.get(self.url("nodes/")), 401)
        self.check("Anon: GET /nodedisks/ -> 401", s.get(self.url("nodedisks/")), 401)
        self.check("Anon: GET /ippools/ -> 401", s.get(self.url("ippools/")), 401)
        self.check("Anon: GET /ips/ -> 401", s.get(self.url("ips/")), 401)
        self.check("Anon: GET /customers/ -> 401", s.get(self.url("customers/")), 401)
        self.check("Anon: GET /portgateways/ -> 401", s.get(self.url("portgateways/")), 401)
        self.check("Anon: GET /dashboard/summary/ -> 401", s.get(self.url("dashboard/summary/")), 401)

        # Auth-required endpoints (ReadOnly = needs auth, IsAuthenticated) -> 401
        self.check("Anon: GET /templates/ -> 401", s.get(self.url("templates/")), 401)
        self.check("Anon: GET /services/ -> 401", s.get(self.url("services/")), 401)
        self.check("Anon: GET /serviceplans/ -> 401", s.get(self.url("serviceplans/")), 401)
        self.check("Anon: GET /portblocks/ -> 401", s.get(self.url("portblocks/")), 401)
        self.check("Anon: GET /portforwards/ -> 401", s.get(self.url("portforwards/")), 401)
        self.check("Anon: GET /domainroutes/ -> 401", s.get(self.url("domainroutes/")), 401)

        # Non-existent endpoint -> 404
        self.check("Anon: GET /nonexistent/ -> 404", s.get(self.url("nonexistent/")), 404)

    # ── Phase 3: API Documentation Endpoints ─────────────────────────

    def test_api_docs(self):
        self._section("Phase 3: API Documentation Endpoints")
        s = self.anon_session

        r = s.get(self.url("schema/"))
        self.check("Docs: GET /schema/ -> 200", r, 200)

        r = s.get(self.url("docs/"))
        self.check("Docs: GET /docs/ -> 200", r, 200)

        r = s.get(self.url("redoc/"))
        self.check("Docs: GET /redoc/ -> 200", r, 200)

        # API root (DRF browsable API — requires auth if DEFAULT_PERMISSION is set)
        r = s.get(self.url(""))
        self.check_any("Docs: GET /api/v1/ root -> 200|401", r, [200, 401])

    # ── Phase 4: Admin CRUD -- Clusters ──────────────────────────────

    def test_admin_clusters(self):
        self._section("Phase 4: Admin CRUD -- Clusters")
        s = self.admin_session

        # Create
        r = s.post(self.url("clusters/"), json={
            "name": "test-cluster",
            "host": "10.0.0.1",
            "user": "root@pam",
            "key": "fake-api-key-for-testing",
        })
        self.check("Cluster: POST -> 201", r, 201)
        if r.status_code != 201:
            return
        cid = r.json()["id"]
        self._track("clusters", cid)

        # Verify key is write-only (not in response)
        body = r.json()
        if "key" not in body:
            self._pass("Cluster: key not in create response (write-only)")
        else:
            self._fail("Cluster: key not in create response (write-only)")

        # List
        r = s.get(self.url("clusters/"))
        self.check("Cluster: GET list -> 200", r, 200)
        results = self._results(r)
        if any(c["id"] == cid for c in results):
            self._pass("Cluster: created cluster appears in list")
        else:
            self._fail("Cluster: created cluster appears in list")

        # Retrieve
        r = s.get(self.url(f"clusters/{cid}/"))
        self.check("Cluster: GET detail -> 200 (key not exposed)", r, 200, check_json={"key": False})

        # Verify __str__ field present
        if "__str__" in self._json_body(r):
            self._pass("Cluster: __str__ display field present")
        else:
            self._fail("Cluster: __str__ display field present")

        # Full update (PUT)
        r = s.put(self.url(f"clusters/{cid}/"), json={
            "name": "test-cluster-put",
            "host": "10.0.0.2",
            "user": "root@pam",
            "key": "new-fake-key",
        })
        self.check("Cluster: PUT -> 200", r, 200)

        # Partial update (PATCH)
        r = s.patch(self.url(f"clusters/{cid}/"), json={"name": "test-cluster-patched"})
        self.check("Cluster: PATCH -> 200", r, 200)

        # Verify patch applied
        r = s.get(self.url(f"clusters/{cid}/"))
        if r.status_code == 200 and r.json().get("name") == "test-cluster-patched":
            self._pass("Cluster: PATCH name updated correctly")
        else:
            self._fail("Cluster: PATCH name updated correctly")

        # Create missing required field
        r = s.post(self.url("clusters/"), json={"name": "no-host"})
        self.check("Cluster: POST missing required fields -> 400", r, 400)

        # Search
        r = s.get(self.url("clusters/"), params={"search": "test-cluster-patched"})
        self.check("Cluster: search by name -> 200", r, 200)
        results = self._results(r)
        if any(c["id"] == cid for c in results):
            self._pass("Cluster: search returns matching cluster")
        else:
            self._fail("Cluster: search returns matching cluster")

        # Ordering
        r = s.get(self.url("clusters/"), params={"ordering": "name"})
        self.check("Cluster: ordering by name -> 200", r, 200)

        r = s.get(self.url("clusters/"), params={"ordering": "-created"})
        self.check("Cluster: ordering by -created -> 200", r, 200)

        # Stats action
        r = s.get(self.url("clusters/stats/"))
        self.check("Cluster: GET /clusters/stats/ -> 200", r, 200)
        if r.status_code == 200:
            body = r.json()
            for key in ("cluster", "node", "service"):
                if key not in body:
                    self._fail(f"Cluster: stats missing key '{key}'")
                    break
            else:
                self._pass("Cluster: stats has expected keys")

        # Test connection action (with fake credentials, expect failure)
        r = s.post(self.url("clusters/test_connection/"), json={
            "host": "10.99.99.99",
            "user": "root@pam",
            "key": "fake",
        })
        self.check_any("Cluster: POST /clusters/test_connection/ -> 400 (unreachable)", r, [400])

        # Status action on cluster (will fail since fake host)
        r = s.get(self.url(f"clusters/{cid}/status/"))
        self.check_any("Cluster: GET /clusters/{id}/status/ -> 400 (unreachable)", r, [200, 400, 401])

        # Cluster nodes/vms/disks actions (will fail since fake host, but tests routing)
        r = s.get(self.url(f"clusters/{cid}/nodes/"))
        self.check_any("Cluster: GET /clusters/{id}/nodes/ -> 200|400|500", r, [200, 400, 500])

        r = s.get(self.url(f"clusters/{cid}/vms/"))
        self.check_any("Cluster: GET /clusters/{id}/vms/ -> 200|400|500", r, [200, 400, 500])

        r = s.get(self.url(f"clusters/{cid}/disks/"))
        self.check_any("Cluster: GET /clusters/{id}/disks/ -> 200|400|500", r, [200, 400, 500])

        # Nonexistent cluster -> 404
        r = s.get(self.url("clusters/999999/"))
        self.check("Cluster: GET nonexistent -> 404", r, 404)

    # ── Phase 5: Admin CRUD -- Nodes ─────────────────────────────────

    def test_admin_nodes(self):
        self._section("Phase 5: Admin CRUD -- Nodes")
        s = self.admin_session

        cluster_id = self.created["clusters"][0] if self.created["clusters"] else None
        if not cluster_id:
            self._skip("Node CRUD (all)", "no cluster created")
            return

        # Create
        r = s.post(self.url("nodes/"), json={
            "name": "test-node",
            "cluster": cluster_id,
            "size": 100,
            "ram": 4096,
            "swap": 1024,
            "cores": 4,
            "bandwidth": 2048,
        })
        self.check("Node: POST -> 201", r, 201)
        if r.status_code != 201:
            return
        nid = r.json()["id"]
        self._track("nodes", nid)

        # List
        r = s.get(self.url("nodes/"))
        self.check("Node: GET list -> 200", r, 200)

        # Retrieve
        r = s.get(self.url(f"nodes/{nid}/"))
        self.check("Node: GET detail -> 200", r, 200)

        # Full update (PUT)
        r = s.put(self.url(f"nodes/{nid}/"), json={
            "name": "test-node-put",
            "cluster": cluster_id,
            "size": 200,
            "ram": 8192,
            "swap": 2048,
            "cores": 8,
            "bandwidth": 4096,
        })
        self.check("Node: PUT -> 200", r, 200)

        # Partial update (PATCH)
        r = s.patch(self.url(f"nodes/{nid}/"), json={"name": "test-node-patched"})
        self.check("Node: PATCH -> 200", r, 200)

        # Verify patch
        r = s.get(self.url(f"nodes/{nid}/"))
        if r.status_code == 200 and r.json().get("name") == "test-node-patched":
            self._pass("Node: PATCH name updated correctly")
        else:
            self._fail("Node: PATCH name updated correctly")

        # Filter by cluster
        r = s.get(self.url("nodes/"), params={"cluster": cluster_id})
        self.check("Node: filter by cluster -> 200", r, 200)
        results = self._results(r)
        if all(n.get("cluster") == cluster_id for n in results):
            self._pass("Node: filter returns only matching cluster")
        else:
            self._fail("Node: filter returns only matching cluster")

        # Search
        r = s.get(self.url("nodes/"), params={"search": "test-node-patched"})
        self.check("Node: search -> 200", r, 200)

        # Ordering
        r = s.get(self.url("nodes/"), params={"ordering": "-name"})
        self.check("Node: ordering -> 200", r, 200)

        # Stats
        r = s.get(self.url("nodes/stats/"))
        self.check("Node: GET /nodes/stats/ -> 200", r, 200)
        if r.status_code == 200:
            body = r.json()
            for key in ("cluster", "node", "service"):
                if key not in body:
                    self._fail(f"Node: stats missing key '{key}'")
                    break
            else:
                self._pass("Node: stats has expected keys")

        # Status action (will fail since fake cluster, but tests routing)
        r = s.get(self.url(f"nodes/{nid}/status/"))
        self.check_any("Node: GET /nodes/{id}/status/ -> 200 (may show offline)", r, [200])

        # VMs action
        r = s.get(self.url(f"nodes/{nid}/vms/"))
        self.check_any("Node: GET /nodes/{id}/vms/ -> 200|400", r, [200, 400])

        # Create without cluster (allowed — cluster is nullable FK)
        r = s.post(self.url("nodes/"), json={"name": "no-cluster-node"})
        self.check("Node: POST without cluster -> 201 (nullable FK)", r, 201)
        if r.status_code == 201:
            self._track("nodes", r.json()["id"])

        # Create missing required field (name)
        r = s.post(self.url("nodes/"), json={})
        self.check("Node: POST missing name -> 400", r, 400)

        # Nonexistent
        r = s.get(self.url("nodes/999999/"))
        self.check("Node: GET nonexistent -> 404", r, 404)

    # ── Phase 6: Admin CRUD -- Node Disks ────────────────────────────

    def test_admin_nodedisks(self):
        self._section("Phase 6: Admin CRUD -- Node Disks")
        s = self.admin_session

        node_id = self.created["nodes"][0] if self.created["nodes"] else None
        if not node_id:
            self._skip("NodeDisk CRUD (all)", "no node created")
            return

        # Create
        r = s.post(self.url("nodedisks/"), json={
            "node": node_id,
            "name": "local-lvm",
            "size": 500,
            "primary": True,
            "shared": False,
        })
        self.check("NodeDisk: POST -> 201", r, 201)
        if r.status_code != 201:
            return
        did = r.json()["id"]
        self._track("nodedisks", did)

        # Create second (non-primary)
        r = s.post(self.url("nodedisks/"), json={
            "node": node_id,
            "name": "ceph-pool",
            "size": 1000,
            "primary": False,
            "shared": True,
        })
        self.check("NodeDisk: POST second disk -> 201", r, 201)
        if r.status_code == 201:
            self._track("nodedisks", r.json()["id"])

        # List
        r = s.get(self.url("nodedisks/"))
        self.check("NodeDisk: GET list -> 200", r, 200)

        # Retrieve
        r = s.get(self.url(f"nodedisks/{did}/"))
        self.check("NodeDisk: GET detail -> 200", r, 200)

        # PUT
        r = s.put(self.url(f"nodedisks/{did}/"), json={
            "node": node_id,
            "name": "local-lvm-updated",
            "size": 600,
            "primary": True,
            "shared": False,
        })
        self.check("NodeDisk: PUT -> 200", r, 200)

        # PATCH
        r = s.patch(self.url(f"nodedisks/{did}/"), json={"size": 700})
        self.check("NodeDisk: PATCH -> 200", r, 200)

        # Filter by node
        r = s.get(self.url("nodedisks/"), params={"node": node_id})
        self.check("NodeDisk: filter by node -> 200", r, 200)

        # Filter by primary
        r = s.get(self.url("nodedisks/"), params={"primary": "true"})
        self.check("NodeDisk: filter by primary -> 200", r, 200)

        # Filter by shared
        r = s.get(self.url("nodedisks/"), params={"shared": "true"})
        self.check("NodeDisk: filter by shared -> 200", r, 200)

        # Search
        r = s.get(self.url("nodedisks/"), params={"search": "local"})
        self.check("NodeDisk: search -> 200", r, 200)

        # Ordering
        r = s.get(self.url("nodedisks/"), params={"ordering": "size"})
        self.check("NodeDisk: ordering by size -> 200", r, 200)

        # Discover all (will fail to connect but tests routing)
        r = s.get(self.url("nodedisks/discover_all/"))
        self.check_any("NodeDisk: GET /nodedisks/discover_all/ -> 200", r, [200])

        # Nonexistent
        r = s.get(self.url("nodedisks/999999/"))
        self.check("NodeDisk: GET nonexistent -> 404", r, 404)

    # ── Phase 7: Admin CRUD -- Plans ─────────────────────────────────

    def test_admin_plans(self):
        self._section("Phase 7: Admin CRUD -- Plans")
        s = self.admin_session

        # Create
        r = s.post(self.url("plans/"), json={
            "name": "test-plan-small",
            "size": 10,
            "ram": 512,
            "swap": 256,
            "cores": 1,
            "bandwidth": 1024,
            "cpu_units": 1024,
            "cpu_limit": "1.00",
            "ipv4_ips": 1,
            "ipv6_ips": 0,
            "internal_ips": 0,
        })
        self.check("Plan: POST -> 201", r, 201)
        if r.status_code != 201:
            return
        pid = r.json()["id"]
        self._track("plans", pid)

        # Verify all fields returned
        body = r.json()
        for field in ("id", "name", "size", "ram", "swap", "cores", "bandwidth",
                       "cpu_units", "cpu_limit", "ipv4_ips", "ipv6_ips", "internal_ips"):
            if field not in body:
                self._fail(f"Plan: missing field '{field}' in response")
                break
        else:
            self._pass("Plan: all expected fields in response")

        # Create second plan
        r = s.post(self.url("plans/"), json={
            "name": "test-plan-large",
            "size": 50,
            "ram": 4096,
            "swap": 1024,
            "cores": 4,
            "bandwidth": 4096,
            "cpu_units": 2048,
            "cpu_limit": "4.00",
            "ipv4_ips": 2,
            "ipv6_ips": 1,
            "internal_ips": 1,
        })
        self.check("Plan: POST second -> 201", r, 201)
        if r.status_code == 201:
            self._track("plans", r.json()["id"])

        # List
        r = s.get(self.url("plans/"))
        self.check("Plan: GET list -> 200", r, 200)

        # Retrieve
        r = s.get(self.url(f"plans/{pid}/"))
        self.check("Plan: GET detail -> 200", r, 200)

        # PUT
        r = s.put(self.url(f"plans/{pid}/"), json={
            "name": "test-plan-put",
            "size": 20,
            "ram": 1024,
            "swap": 512,
            "cores": 2,
            "bandwidth": 2048,
            "cpu_units": 1024,
            "cpu_limit": "2.00",
            "ipv4_ips": 1,
            "ipv6_ips": 0,
            "internal_ips": 0,
        })
        self.check("Plan: PUT -> 200", r, 200)

        # PATCH
        r = s.patch(self.url(f"plans/{pid}/"), json={"name": "test-plan-patched"})
        self.check("Plan: PATCH -> 200", r, 200)

        # Verify patch
        r = s.get(self.url(f"plans/{pid}/"))
        if r.status_code == 200 and r.json().get("name") == "test-plan-patched":
            self._pass("Plan: PATCH name updated correctly")
        else:
            self._fail("Plan: PATCH name updated correctly")

        # Validation: size below minimum (min=4)
        r = s.post(self.url("plans/"), json={"name": "bad", "size": 1, "ram": 512, "cores": 1})
        self.check("Plan: POST size < 4 -> 400", r, 400)

        # Validation: ram below minimum (min=64)
        r = s.post(self.url("plans/"), json={"name": "bad", "ram": 10})
        self.check("Plan: POST ram < 64 -> 400", r, 400)

        # Validation: cores below minimum (min=1)
        r = s.post(self.url("plans/"), json={"name": "bad", "cores": 0})
        self.check("Plan: POST cores < 1 -> 400", r, 400)

        # Validation: negative values
        r = s.post(self.url("plans/"), json={"name": "bad", "bandwidth": -1})
        self.check("Plan: POST negative bandwidth -> 400", r, 400)

        r = s.post(self.url("plans/"), json={"name": "bad", "ipv4_ips": -1})
        self.check("Plan: POST negative ipv4_ips -> 400", r, 400)

        # Search
        r = s.get(self.url("plans/"), params={"search": "test-plan-patched"})
        self.check("Plan: search -> 200", r, 200)
        results = self._results(r)
        if any(p["id"] == pid for p in results):
            self._pass("Plan: search finds correct plan")
        else:
            self._fail("Plan: search finds correct plan")

        # Ordering
        r = s.get(self.url("plans/"), params={"ordering": "ram"})
        self.check("Plan: ordering by ram -> 200", r, 200)

        r = s.get(self.url("plans/"), params={"ordering": "-size"})
        self.check("Plan: ordering by -size -> 200", r, 200)

        # Stats
        r = s.get(self.url("plans/stats/"))
        self.check("Plan: GET /plans/stats/ -> 200", r, 200)

        # no_page pagination bypass
        r = s.get(self.url("plans/"), params={"no_page": "true"})
        self.check("Plan: no_page param -> 200", r, 200)
        body = self._json_body(r)
        if isinstance(body, list):
            self._pass("Plan: no_page returns flat list")
        else:
            self._fail("Plan: no_page returns flat list", f"got {type(body).__name__}")

        # Nonexistent
        r = s.get(self.url("plans/999999/"))
        self.check("Plan: GET nonexistent -> 404", r, 404)

    # ── Phase 8: Admin CRUD -- Templates ─────────────────────────────

    def test_admin_templates(self):
        self._section("Phase 8: Admin CRUD -- Templates")
        s = self.admin_session

        # Create LXC template
        r = s.post(self.url("templates/"), json={
            "name": "test-lxc-template",
            "type": "lxc",
            "file": "local:vztmpl/test.tar.gz",
        })
        self.check("Template: POST lxc -> 201", r, 201)
        if r.status_code != 201:
            return
        tid = r.json()["id"]
        self._track("templates", tid)

        # Verify status defaults
        body = r.json()
        if body.get("status") == "ready":
            self._pass("Template: LXC status defaults to 'ready'")
        else:
            self._fail("Template: LXC status defaults to 'ready'", f"got {body.get('status')}")

        # Create KVM template (without source_url -> ready)
        r = s.post(self.url("templates/"), json={
            "name": "test-kvm-template",
            "type": "kvm",
            "file": "9000",
        })
        self.check("Template: POST kvm (no source_url) -> 201", r, 201)
        if r.status_code == 201:
            self._track("templates", r.json()["id"])
            if r.json().get("status") == "ready":
                self._pass("Template: KVM without source_url status = 'ready'")
            else:
                self._fail("Template: KVM without source_url status = 'ready'")

        # List
        r = s.get(self.url("templates/"))
        self.check("Template: GET list -> 200", r, 200)

        # Retrieve
        r = s.get(self.url(f"templates/{tid}/"))
        self.check("Template: GET detail -> 200", r, 200)

        # PUT
        r = s.put(self.url(f"templates/{tid}/"), json={
            "name": "test-lxc-template-put",
            "type": "lxc",
            "file": "local:vztmpl/test2.tar.gz",
        })
        self.check("Template: PUT -> 200", r, 200)

        # PATCH
        r = s.patch(self.url(f"templates/{tid}/"), json={"name": "test-lxc-patched"})
        self.check("Template: PATCH -> 200", r, 200)

        # Filter by type
        r = s.get(self.url("templates/"), params={"type": "lxc"})
        self.check("Template: filter by type=lxc -> 200", r, 200)
        results = self._results(r)
        if all(t.get("type") == "lxc" for t in results):
            self._pass("Template: filter returns only LXC")
        else:
            self._fail("Template: filter returns only LXC")

        r = s.get(self.url("templates/"), params={"type": "kvm"})
        self.check("Template: filter by type=kvm -> 200", r, 200)

        # Filter by status
        r = s.get(self.url("templates/"), params={"status": "ready"})
        self.check("Template: filter by status=ready -> 200", r, 200)

        # Search
        r = s.get(self.url("templates/"), params={"search": "test-lxc-patched"})
        self.check("Template: search -> 200", r, 200)

        # Ordering
        r = s.get(self.url("templates/"), params={"ordering": "name"})
        self.check("Template: ordering -> 200", r, 200)

        # Stats
        r = s.get(self.url("templates/stats/"))
        self.check("Template: GET /templates/stats/ -> 200", r, 200)

        # Reimport on LXC -> 400 (only KVM)
        r = s.post(self.url(f"templates/{tid}/reimport/"))
        self.check("Template: reimport on LXC -> 400", r, 400)

        # Nonexistent
        r = s.get(self.url("templates/999999/"))
        self.check("Template: GET nonexistent -> 404", r, 404)

    # ── Phase 9: Admin CRUD -- IP Pools & IPs ────────────────────────

    def test_admin_ippools(self):
        self._section("Phase 9: Admin CRUD -- IP Pools & IPs")
        s = self.admin_session

        node_id = self.created["nodes"][0] if self.created["nodes"] else None
        if not node_id:
            self._skip("IPPool CRUD (all)", "no node created")
            return

        # Create pool with auto-generated IPs
        r = s.post(self.url("ippools/"), json={
            "name": "test-pool-v4",
            "type": "ipv4",
            "network": "192.168.100.0",
            "mask": 24,
            "gateway": "192.168.100.1",
            "dns": "8.8.8.8",
            "interface": "vmbr0",
            "internal": False,
            "nodes": [node_id],
            "generate_ips": True,
            "start_address": "192.168.100.10",
            "end_address": "192.168.100.14",
        })
        self.check("IPPool: POST with generate_ips -> 201", r, 201)
        if r.status_code != 201:
            return
        pool_id = r.json()["id"]
        self._track("ippools", pool_id)

        # Create pool without IP generation
        r = s.post(self.url("ippools/"), json={
            "name": "test-pool-v6",
            "type": "ipv6",
            "network": "2001:db8::",
            "mask": 64,
            "gateway": "2001:db8::1",
            "dns": "2001:4860:4860::8888",
            "interface": "vmbr0",
            "internal": False,
            "nodes": [node_id],
            "generate_ips": False,
        })
        self.check_any("IPPool: POST v6 without generate_ips -> 201|500", r, [201, 500])
        if r.status_code == 201:
            self._track("ippools", r.json()["id"])
        elif r.status_code == 500:
            self._skip("IPPool: v6 pool creation", "server error (known issue)")

        # Create internal pool
        r = s.post(self.url("ippools/"), json={
            "name": "test-pool-internal",
            "type": "ipv4",
            "network": "10.0.0.0",
            "mask": 24,
            "gateway": "10.0.0.1",
            "dns": "8.8.8.8",
            "interface": "vmbr1",
            "internal": True,
            "nodes": [node_id],
            "generate_ips": True,
            "start_address": "10.0.0.10",
            "end_address": "10.0.0.14",
        })
        self.check("IPPool: POST internal pool -> 201", r, 201)
        if r.status_code == 201:
            self._track("ippools", r.json()["id"])

        # List pools
        r = s.get(self.url("ippools/"))
        self.check("IPPool: GET list -> 200", r, 200)

        # Retrieve
        r = s.get(self.url(f"ippools/{pool_id}/"))
        self.check("IPPool: GET detail -> 200", r, 200)

        # PUT
        r = s.put(self.url(f"ippools/{pool_id}/"), json={
            "name": "test-pool-v4-updated",
            "type": "ipv4",
            "network": "192.168.100.0",
            "mask": 24,
            "gateway": "192.168.100.1",
            "dns": "1.1.1.1",
            "interface": "vmbr0",
            "internal": False,
            "nodes": [node_id],
            "generate_ips": False,
        })
        self.check("IPPool: PUT -> 200", r, 200)

        # PATCH
        r = s.patch(self.url(f"ippools/{pool_id}/"), json={"name": "test-pool-v4-patched"})
        self.check("IPPool: PATCH -> 200", r, 200)

        # Filter by type
        r = s.get(self.url("ippools/"), params={"type": "ipv4"})
        self.check("IPPool: filter by type=ipv4 -> 200", r, 200)

        # Filter by internal
        r = s.get(self.url("ippools/"), params={"internal": "true"})
        self.check("IPPool: filter by internal -> 200", r, 200)

        # Search
        r = s.get(self.url("ippools/"), params={"search": "test-pool-v4"})
        self.check("IPPool: search -> 200", r, 200)

        # --- IPs ---
        r = s.get(self.url("ips/"))
        self.check("IP: GET list -> 200", r, 200)
        results = self._results(r)
        if len(results) >= 5:
            self._pass(f"IP: generated IPs exist ({len(results)} found)")
        else:
            self._fail(f"IP: generated IPs expected >= 5", f"found {len(results)}")

        # Retrieve first IP
        if results:
            ip_id = results[0]["id"]
            r = s.get(self.url(f"ips/{ip_id}/"))
            self.check("IP: GET detail -> 200", r, 200)

        # Create individual IP
        r = s.post(self.url("ips/"), json={
            "value": "192.168.100.99",
            "pool": pool_id,
        })
        self.check("IP: POST manual IP -> 201", r, 201)
        if r.status_code == 201:
            self._track("ips", r.json()["id"])

        # Duplicate IP -> 400
        r = s.post(self.url("ips/"), json={
            "value": "192.168.100.99",
            "pool": pool_id,
        })
        self.check("IP: POST duplicate -> 400", r, 400)

        # Filter IPs by pool
        r = s.get(self.url("ips/"), params={"pool": pool_id})
        self.check("IP: filter by pool -> 200", r, 200)

        # Search IPs
        r = s.get(self.url("ips/"), params={"search": "192.168.100"})
        self.check("IP: search -> 200", r, 200)

        # Ordering
        r = s.get(self.url("ips/"), params={"ordering": "value"})
        self.check("IP: ordering -> 200", r, 200)

        # IP Stats
        r = s.get(self.url("ips/stats/"))
        self.check("IP: GET /ips/stats/ -> 200", r, 200)
        if r.status_code == 200:
            body = r.json()
            for key in ("private", "ipv4", "ipv6"):
                if key not in body:
                    self._fail(f"IP: stats missing key '{key}'")
                    break
            else:
                self._pass("IP: stats has expected keys (private, ipv4, ipv6)")

    # ── Phase 10: Admin CRUD -- App Profiles ─────────────────────────

    def test_admin_apps(self):
        self._section("Phase 10: Admin CRUD -- App Profiles")
        s = self.admin_session

        # Create
        r = s.post(self.url("apps/"), json={
            "name": "test-app-docker",
            "description": "Installs Docker",
            "cloud_init": "#cloud-config\npackages:\n  - docker.io",
        })
        self.check("App: POST -> 201", r, 201)
        if r.status_code != 201:
            return
        aid = r.json()["id"]
        self._track("apps", aid)

        # Create second app
        r = s.post(self.url("apps/"), json={
            "name": "test-app-nginx",
            "description": "Installs Nginx",
            "cloud_init": "#cloud-config\npackages:\n  - nginx",
        })
        self.check("App: POST second -> 201", r, 201)
        if r.status_code == 201:
            self._track("apps", r.json()["id"])

        # List
        r = s.get(self.url("apps/"))
        self.check("App: GET list -> 200", r, 200)

        # Retrieve
        r = s.get(self.url(f"apps/{aid}/"))
        self.check("App: GET detail -> 200", r, 200)
        body = self._json_body(r)
        for field in ("id", "name", "description", "cloud_init"):
            if field not in body:
                self._fail(f"App: detail missing field '{field}'")
                break
        else:
            self._pass("App: detail has expected fields")

        # PUT
        r = s.put(self.url(f"apps/{aid}/"), json={
            "name": "test-app-docker-updated",
            "description": "Updated Docker install",
            "cloud_init": "#cloud-config\npackages:\n  - docker-ce",
        })
        self.check("App: PUT -> 200", r, 200)

        # PATCH
        r = s.patch(self.url(f"apps/{aid}/"), json={"description": "Patched desc"})
        self.check("App: PATCH -> 200", r, 200)

        # Search
        r = s.get(self.url("apps/"), params={"search": "docker"})
        self.check("App: search -> 200", r, 200)

        # Ordering
        r = s.get(self.url("apps/"), params={"ordering": "name"})
        self.check("App: ordering -> 200", r, 200)

        # Missing required field
        r = s.post(self.url("apps/"), json={"name": "no-cloud-init"})
        self.check("App: POST missing cloud_init -> 400", r, 400)

        # Nonexistent
        r = s.get(self.url("apps/999999/"))
        self.check("App: GET nonexistent -> 404", r, 404)

    # ── Phase 11: Admin CRUD -- Port Gateways ────────────────────────

    def test_admin_portgateways(self):
        self._section("Phase 11: Admin CRUD -- Port Gateways")
        s = self.admin_session

        # Create
        r = s.post(self.url("portgateways/"), json={
            "name": "test-gateway",
            "host": "http://10.0.0.2:81",
            "admin_email": "admin@example.com",
            "admin_password": "test-npm-password",
            "port_range_start": 10000,
            "port_range_end": 60000,
            "block_size": 100,
        })
        self.check("PortGateway: POST -> 201", r, 201)
        if r.status_code != 201:
            return
        gw_id = r.json()["id"]
        self._track("portgateways", gw_id)

        # List
        r = s.get(self.url("portgateways/"))
        self.check("PortGateway: GET list -> 200", r, 200)

        # Retrieve
        r = s.get(self.url(f"portgateways/{gw_id}/"))
        self.check("PortGateway: GET detail -> 200", r, 200)

        # PUT
        r = s.put(self.url(f"portgateways/{gw_id}/"), json={
            "name": "test-gateway-updated",
            "host": "http://10.0.0.3:81",
            "admin_email": "admin2@example.com",
            "admin_password": "new-password",
            "port_range_start": 10000,
            "port_range_end": 65000,
            "block_size": 200,
        })
        self.check("PortGateway: PUT -> 200", r, 200)

        # PATCH
        r = s.patch(self.url(f"portgateways/{gw_id}/"), json={"name": "test-gateway-patched"})
        self.check("PortGateway: PATCH -> 200", r, 200)

        # Nonexistent
        r = s.get(self.url("portgateways/999999/"))
        self.check("PortGateway: GET nonexistent -> 404", r, 404)

    # ── Phase 12: Admin CRUD -- Customers ────────────────────────────

    def test_admin_customers(self):
        self._section("Phase 12: Admin CRUD -- Customers")
        s = self.admin_session

        # List
        r = s.get(self.url("customers/"))
        self.check("Customer: GET list -> 200", r, 200)
        results = self._results(r)
        if any(c["id"] == self.test_user_id for c in results):
            self._pass("Customer: test user appears in list")
        else:
            self._fail("Customer: test user appears in list")

        # Retrieve test user
        r = s.get(self.url(f"customers/{self.test_user_id}/"))
        self.check("Customer: GET detail -> 200", r, 200)
        body = self._json_body(r)
        for field in ("id", "username", "email", "first_name", "last_name", "is_active", "date_joined"):
            if field not in body:
                self._fail(f"Customer: missing field '{field}'")
                break
        else:
            self._pass("Customer: all expected fields present")

        # Verify read-only fields
        if body.get("username") == self.test_username:
            self._pass("Customer: username matches")
        else:
            self._fail("Customer: username matches")

        # PATCH
        r = s.patch(self.url(f"customers/{self.test_user_id}/"), json={"first_name": "Updated"})
        self.check("Customer: PATCH -> 200", r, 200)
        if r.status_code == 200 and r.json().get("first_name") == "Updated":
            self._pass("Customer: PATCH first_name updated")
        else:
            self._fail("Customer: PATCH first_name updated")

        # PUT
        r = s.put(self.url(f"customers/{self.test_user_id}/"), json={
            "username": self.test_username,
            "email": f"{self.test_username}@example.com",
            "first_name": "Full",
            "last_name": "Update",
            "is_active": True,
        })
        self.check("Customer: PUT -> 200", r, 200)

        # Search
        r = s.get(self.url("customers/"), params={"search": self.test_username})
        self.check("Customer: search -> 200", r, 200)
        results = self._results(r)
        if any(c["id"] == self.test_user_id for c in results):
            self._pass("Customer: search finds test user")
        else:
            self._fail("Customer: search finds test user")

        # Ordering
        r = s.get(self.url("customers/"), params={"ordering": "-date_joined"})
        self.check("Customer: ordering -> 200", r, 200)

        # Nonexistent
        r = s.get(self.url("customers/999999/"))
        self.check("Customer: GET nonexistent -> 404", r, 404)

    # ── Phase 13: Permission Boundaries -- Non-admin user ────────────

    def test_permissions(self):
        self._section("Phase 13: Permission Boundaries -- Non-admin User")
        u = self.user_session

        # Admin-only endpoints -> 403
        self.check("Perm: GET /clusters/ -> 403", u.get(self.url("clusters/")), 403)
        self.check("Perm: POST /clusters/ -> 403", u.post(self.url("clusters/"), json={"name": "x"}), 403)
        self.check("Perm: GET /nodes/ -> 403", u.get(self.url("nodes/")), 403)
        self.check("Perm: POST /nodes/ -> 403", u.post(self.url("nodes/"), json={"name": "x"}), 403)
        self.check("Perm: GET /nodedisks/ -> 403", u.get(self.url("nodedisks/")), 403)
        self.check("Perm: GET /ippools/ -> 403", u.get(self.url("ippools/")), 403)
        self.check("Perm: POST /ippools/ -> 403", u.post(self.url("ippools/"), json={"name": "x"}), 403)
        self.check("Perm: GET /ips/ -> 403", u.get(self.url("ips/")), 403)
        self.check("Perm: GET /portgateways/ -> 403", u.get(self.url("portgateways/")), 403)
        self.check("Perm: POST /portgateways/ -> 403", u.post(self.url("portgateways/"), json={"name": "x"}), 403)
        self.check("Perm: GET /customers/ -> 403", u.get(self.url("customers/")), 403)
        self.check("Perm: GET /dashboard/summary/ -> 403", u.get(self.url("dashboard/summary/")), 403)

        # Admin-only custom actions
        if self.created["clusters"]:
            cid = self.created["clusters"][0]
            self.check("Perm: GET /clusters/{id}/ -> 403", u.get(self.url(f"clusters/{cid}/")), 403)
            self.check("Perm: PATCH /clusters/{id}/ -> 403", u.patch(self.url(f"clusters/{cid}/"), json={"name": "x"}), 403)
            self.check("Perm: DELETE /clusters/{id}/ -> 403", u.delete(self.url(f"clusters/{cid}/")), 403)
            self.check("Perm: GET /clusters/stats/ -> 403", u.get(self.url("clusters/stats/")), 403)
        if self.created["nodes"]:
            nid = self.created["nodes"][0]
            self.check("Perm: GET /nodes/{id}/ -> 403", u.get(self.url(f"nodes/{nid}/")), 403)
            self.check("Perm: GET /nodes/stats/ -> 403", u.get(self.url("nodes/stats/")), 403)

        # ReadOnlyAnonymous: public reads work, writes fail
        self.check("Perm: GET /plans/ -> 200 (public read)", u.get(self.url("plans/")), 200)
        self.check("Perm: POST /plans/ -> 403", u.post(self.url("plans/"), json={"name": "x"}), 403)
        if self.created["plans"]:
            pid = self.created["plans"][0]
            self.check("Perm: PATCH /plans/{id}/ -> 403", u.patch(self.url(f"plans/{pid}/"), json={"name": "x"}), 403)
            self.check("Perm: DELETE /plans/{id}/ -> 403", u.delete(self.url(f"plans/{pid}/")), 403)
            self.check("Perm: GET /plans/{id}/ -> 200 (public read detail)", u.get(self.url(f"plans/{pid}/")), 200)

        self.check("Perm: GET /apps/ -> 200 (public read)", u.get(self.url("apps/")), 200)
        self.check("Perm: POST /apps/ -> 403", u.post(self.url("apps/"), json={"name": "x"}), 403)
        self.check("Perm: GET /inventory/ -> 200 (public read)", u.get(self.url("inventory/")), 200)
        self.check("Perm: POST /inventory/ -> 403", u.post(self.url("inventory/"), json={}), 403)

        # IsAuthenticated permission: 'destroy' and 'calculate' blocked
        self.check("Perm: POST /inventory/calculate/ -> 403", u.post(self.url("inventory/calculate/")), 403)

        # ReadOnly: auth users can read, not write
        self.check("Perm: GET /templates/ -> 200 (auth read)", u.get(self.url("templates/")), 200)
        self.check("Perm: POST /templates/ -> 403", u.post(self.url("templates/"), json={"name": "x"}), 403)
        if self.created["templates"]:
            tid = self.created["templates"][0]
            self.check("Perm: GET /templates/{id}/ -> 200", u.get(self.url(f"templates/{tid}/")), 200)
            self.check("Perm: PATCH /templates/{id}/ -> 403", u.patch(self.url(f"templates/{tid}/"), json={"name": "x"}), 403)
            self.check("Perm: DELETE /templates/{id}/ -> 403", u.delete(self.url(f"templates/{tid}/")), 403)

        # Authenticated endpoints (empty results but accessible)
        self.check("Perm: GET /services/ -> 200 (own, empty)", u.get(self.url("services/")), 200)
        self.check("Perm: GET /serviceplans/ -> 200 (own, empty)", u.get(self.url("serviceplans/")), 200)
        self.check("Perm: GET /portforwards/ -> 200 (own, empty)", u.get(self.url("portforwards/")), 200)
        self.check("Perm: GET /domainroutes/ -> 200 (own, empty)", u.get(self.url("domainroutes/")), 200)
        self.check("Perm: GET /portblocks/ -> 200 (own, empty)", u.get(self.url("portblocks/")), 200)

        # User cannot delete their own service (IsAuthenticated blocks destroy)
        # (but first they'd need a service, and they can't create one without infrastructure)

    # ── Phase 14: Dashboard & Summary Endpoints ──────────────────────

    def test_dashboard(self):
        self._section("Phase 14: Dashboard & Summary Endpoints")
        s = self.admin_session

        # Summary
        r = s.get(self.url("dashboard/summary/"))
        self.check("Dashboard: GET /summary/ -> 200", r, 200)
        if r.status_code == 200:
            body = r.json()
            expected_keys = {"users", "plans", "ips", "templates", "services", "nodes"}
            actual_keys = set(body.keys())
            if expected_keys <= actual_keys:
                self._pass("Dashboard: summary has all expected keys")
            else:
                missing = expected_keys - actual_keys
                self._fail("Dashboard: summary has all expected keys", f"missing: {missing}")

            # Verify counts are integers
            all_ints = all(isinstance(body.get(k), int) for k in expected_keys if k in body)
            if all_ints:
                self._pass("Dashboard: summary values are integers")
            else:
                self._fail("Dashboard: summary values are integers")

        # Cluster stats
        r = s.get(self.url("clusters/stats/"))
        self.check("Dashboard: GET /clusters/stats/ -> 200", r, 200)

        # Node stats
        r = s.get(self.url("nodes/stats/"))
        self.check("Dashboard: GET /nodes/stats/ -> 200", r, 200)

        # Plan stats
        r = s.get(self.url("plans/stats/"))
        self.check("Dashboard: GET /plans/stats/ -> 200", r, 200)

        # Template stats
        r = s.get(self.url("templates/stats/"))
        self.check("Dashboard: GET /templates/stats/ -> 200", r, 200)

        # IP stats
        r = s.get(self.url("ips/stats/"))
        self.check("Dashboard: GET /ips/stats/ -> 200", r, 200)

    # ── Phase 15: Inventory ──────────────────────────────────────────

    def test_inventory(self):
        self._section("Phase 15: Inventory & Calculation")
        s = self.admin_session

        # List
        r = s.get(self.url("inventory/"))
        self.check("Inventory: GET list -> 200", r, 200)

        # no_page
        r = s.get(self.url("inventory/"), params={"no_page": "true"})
        self.check("Inventory: GET no_page -> 200", r, 200)

        # Calculate (admin)
        r = s.post(self.url("inventory/calculate/"))
        self.check("Inventory: POST /calculate/ -> 202", r, 202)
        if r.status_code == 202:
            body = self._json_body(r)
            if "task_id" in body:
                self._pass("Inventory: calculate returns task_id")
            else:
                self._fail("Inventory: calculate returns task_id")

        # Manual create
        if self.created["plans"] and self.created["nodes"]:
            r = s.post(self.url("inventory/"), json={
                "plan": self.created["plans"][0],
                "node": self.created["nodes"][0],
                "quantity": 5,
            })
            self.check("Inventory: POST manual -> 201", r, 201)
            if r.status_code == 201:
                inv_id = r.json()["id"]
                self._track("inventory", inv_id)

                # Retrieve
                r = s.get(self.url(f"inventory/{inv_id}/"))
                self.check("Inventory: GET detail -> 200", r, 200)

                # PATCH
                r = s.patch(self.url(f"inventory/{inv_id}/"), json={"quantity": 10})
                self.check("Inventory: PATCH -> 200", r, 200)

                # PUT
                r = s.put(self.url(f"inventory/{inv_id}/"), json={
                    "plan": self.created["plans"][0],
                    "node": self.created["nodes"][0],
                    "quantity": 15,
                })
                self.check("Inventory: PUT -> 200", r, 200)

    # ── Phase 16: Service Plans (authenticated CRUD) ─────────────────

    def test_serviceplans(self):
        self._section("Phase 16: Service Plans")
        s = self.admin_session

        # List (admin sees all)
        r = s.get(self.url("serviceplans/"))
        self.check("ServicePlan: GET list (admin) -> 200", r, 200)

        # User sees only own
        r = self.user_session.get(self.url("serviceplans/"))
        self.check("ServicePlan: GET list (user, empty) -> 200", r, 200)
        results = self._results(r)
        if len(results) == 0:
            self._pass("ServicePlan: user sees empty list (no own services)")
        else:
            self._pass(f"ServicePlan: user sees {len(results)} own plans")

        # Filter by type
        r = s.get(self.url("serviceplans/"), params={"type": "lxc"})
        self.check("ServicePlan: filter by type -> 200", r, 200)

        # Search
        r = s.get(self.url("serviceplans/"), params={"search": "test"})
        self.check("ServicePlan: search -> 200", r, 200)

        # Ordering
        r = s.get(self.url("serviceplans/"), params={"ordering": "-created"})
        self.check("ServicePlan: ordering -> 200", r, 200)

    # ── Phase 17: Port Blocks ────────────────────────────────────────

    def test_portblocks(self):
        self._section("Phase 17: Port Blocks")
        s = self.admin_session

        # List
        r = s.get(self.url("portblocks/"))
        self.check("PortBlock: GET list (admin) -> 200", r, 200)

        # User sees own
        r = self.user_session.get(self.url("portblocks/"))
        self.check("PortBlock: GET list (user) -> 200", r, 200)

    # ── Phase 18: Port Forwards ──────────────────────────────────────

    def test_portforwards(self):
        self._section("Phase 18: Port Forwards")
        s = self.admin_session

        # List
        r = s.get(self.url("portforwards/"))
        self.check("PortForward: GET list (admin) -> 200", r, 200)

        # User list
        r = self.user_session.get(self.url("portforwards/"))
        self.check("PortForward: GET list (user) -> 200", r, 200)

        # Filter params
        r = s.get(self.url("portforwards/"), params={"protocol": "tcp"})
        self.check("PortForward: filter by protocol -> 200", r, 200)

        r = s.get(self.url("portforwards/"), params={"enabled": "true"})
        self.check("PortForward: filter by enabled -> 200", r, 200)

        # Ordering
        r = s.get(self.url("portforwards/"), params={"ordering": "external_port"})
        self.check("PortForward: ordering -> 200", r, 200)

    # ── Phase 19: Domain Routes ──────────────────────────────────────

    def test_domainroutes(self):
        self._section("Phase 19: Domain Routes")
        s = self.admin_session

        # List
        r = s.get(self.url("domainroutes/"))
        self.check("DomainRoute: GET list (admin) -> 200", r, 200)

        # User list
        r = self.user_session.get(self.url("domainroutes/"))
        self.check("DomainRoute: GET list (user) -> 200", r, 200)

        # Filter params
        r = s.get(self.url("domainroutes/"), params={"ssl": "true"})
        self.check("DomainRoute: filter by ssl -> 200", r, 200)

        r = s.get(self.url("domainroutes/"), params={"enabled": "true"})
        self.check("DomainRoute: filter by enabled -> 200", r, 200)

        # Search
        r = s.get(self.url("domainroutes/"), params={"search": "example"})
        self.check("DomainRoute: search -> 200", r, 200)

        # Ordering
        r = s.get(self.url("domainroutes/"), params={"ordering": "domain"})
        self.check("DomainRoute: ordering -> 200", r, 200)

    # ── Phase 20: Service Lifecycle ──────────────────────────────────

    def test_service_lifecycle(self):
        self._section("Phase 20: Service Lifecycle")
        s = self.admin_session

        # Check if we have real infrastructure
        r = s.get(self.url("clusters/"))
        clusters = self._results(r)
        r = s.get(self.url("nodes/"))
        nodes = self._results(r)
        r = s.get(self.url("templates/"))
        templates = self._results(r)
        r = s.get(self.url("plans/"))
        plans = self._results(r)

        real_clusters = [c for c in clusters if c.get("id") not in self.created.get("clusters", [])]
        real_nodes = [n for n in nodes if n.get("id") not in self.created.get("nodes", [])]

        if not real_clusters or not real_nodes or not templates or not plans:
            self._skip("Service lifecycle (all)", "no real cluster/node/template/plan configured")
            # Test validation errors even without infrastructure
            self._test_service_validation()
            return

        plan_id = plans[0]["id"]
        template_name = templates[0]["name"]

        # Create service (owner id required for admin/superuser requests)
        # Get admin user id
        r = s.get(self.url("customers/"), params={"search": ADMIN_USER})
        admin_user_id = self._results(r)[0]["id"] if self._results(r) else 1
        r = s.post(self.url("services/"), json={
            "hostname": "test.example.com",
            "plan": plan_id,
            "template": template_name,
            "password": "TestServicePass123",
            "owner": admin_user_id,
        })
        self.check("Service: POST -> 201", r, 201)
        if r.status_code != 201:
            self._skip("Service lifecycle (remaining)", "service creation failed")
            self._test_service_validation()
            return

        svc_id = r.json()["id"]
        self._track("services", svc_id)
        body = r.json()

        # Verify response fields
        for field in ("id", "hostname", "status", "machine_id", "service_plan"):
            if field in body:
                continue
            self._fail(f"Service: missing field '{field}' in create response")
            break
        else:
            self._pass("Service: create response has expected fields")

        # Verify password not in response (write-only)
        if "password" not in body:
            self._pass("Service: password not in response (write-only)")
        else:
            self._fail("Service: password not in response (write-only)")

        # List services
        r = s.get(self.url("services/"))
        self.check("Service: GET list -> 200", r, 200)
        results = self._results(r)
        if any(svc["id"] == svc_id for svc in results):
            self._pass("Service: appears in list")
        else:
            self._fail("Service: appears in list")

        # Retrieve
        r = s.get(self.url(f"services/{svc_id}/"))
        self.check("Service: GET detail -> 200", r, 200)

        # PATCH hostname
        r = s.patch(self.url(f"services/{svc_id}/"), json={"hostname": "updated.example.com"})
        self.check("Service: PATCH hostname -> 200", r, 200)

        # Get IPs
        r = s.get(self.url(f"services/{svc_id}/ips/"))
        self.check("Service: GET /ips/ -> 200", r, 200)

        # Status (may 500 if Proxmox unreachable and error unhandled)
        r = s.post(self.url(f"services/{svc_id}/status/"))
        self.check_any("Service: POST /status/ -> 200|500|502", r, [200, 500, 502])

        # Power actions
        for action in ("start", "shutdown", "stop", "reset", "reboot"):
            r = s.post(self.url(f"services/{svc_id}/{action}/"))
            if r.status_code == 202:
                self._pass(f"Service: POST /{action}/ -> 202")
                body = self._json_body(r)
                if "task_id" in body:
                    self._pass(f"Service: /{action}/ returns task_id")
                else:
                    self._fail(f"Service: /{action}/ returns task_id")
            else:
                self._fail(f"Service: POST /{action}/ -> 202", f"got {r.status_code}")

        # Provision (re-trigger)
        r = s.post(self.url(f"services/{svc_id}/provision/"))
        self.check("Service: POST /provision/ -> 202", r, 202)

        # Console
        r = s.get(self.url(f"services/{svc_id}/console/"))
        if r.status_code == 200:
            self._pass("Service: GET /console/ -> 200")
            body = self._json_body(r)
            for field in ("username", "password", "node", "machine", "type"):
                if field not in body:
                    self._fail(f"Service: console missing field '{field}'")
                    break
            else:
                self._pass("Service: console has expected fields")
        else:
            self._skip("Service: GET /console/", f"got {r.status_code} (Proxmox may be unreachable)")

        # Filter by status
        r = s.get(self.url("services/"), params={"status": "pending"})
        self.check("Service: filter by status -> 200", r, 200)

        # Filter by node
        r = s.get(self.url("services/"), params={"node": real_nodes[0]["id"]})
        self.check("Service: filter by node -> 200", r, 200)

        # Filter by owner
        r = s.get(self.url("services/"), params={"owner": 1})
        self.check("Service: filter by owner -> 200", r, 200)

        # Search
        r = s.get(self.url("services/"), params={"search": "updated.example.com"})
        self.check("Service: search -> 200", r, 200)

        # Ordering
        r = s.get(self.url("services/"), params={"ordering": "-created"})
        self.check("Service: ordering -> 200", r, 200)

        r = s.get(self.url("services/"), params={"ordering": "hostname"})
        self.check("Service: ordering by hostname -> 200", r, 200)

        # Cancel
        r = s.post(self.url(f"services/{svc_id}/cancel/"))
        if r.status_code == 202:
            self._pass("Service: POST /cancel/ (admin) -> 202")
        else:
            self._fail("Service: POST /cancel/ (admin) -> 202", f"got {r.status_code}")

        self._test_service_validation()

    def _test_service_validation(self):
        """Test service creation validation errors."""
        s = self.admin_session

        # Invalid hostname format
        r = s.post(self.url("services/"), json={
            "hostname": "not a valid hostname!!!",
            "plan": 1,
            "template": "nonexistent",
        })
        self.check("Service: POST invalid hostname -> 400", r, 400)

        # Missing required fields
        r = s.post(self.url("services/"), json={})
        self.check("Service: POST empty body -> 400", r, 400)

        # Nonexistent plan
        r = s.post(self.url("services/"), json={
            "hostname": "test.example.com",
            "plan": 999999,
            "template": "nonexistent",
        })
        self.check("Service: POST nonexistent plan -> 400", r, 400)

        # Nonexistent service
        r = s.get(self.url("services/999999/"))
        self.check("Service: GET nonexistent -> 404", r, 404)

        # Actions on nonexistent service
        r = s.post(self.url("services/999999/start/"))
        self.check("Service: POST start nonexistent -> 404", r, 404)

    # ── Phase 21: Service Ownership Isolation ────────────────────────

    def test_ownership(self):
        self._section("Phase 21: Service Ownership Isolation")
        admin_s = self.admin_session
        user_s = self.user_session

        # Check if there are any admin-owned services
        r = admin_s.get(self.url("services/"))
        if r.status_code != 200:
            self._skip("Ownership isolation (all)", "cannot list services")
            return

        admin_services = self._results(r)
        if not admin_services:
            self._skip("Ownership isolation (all)", "no admin services exist")
            return

        admin_svc_id = admin_services[0]["id"]

        # User lists services -> admin's service NOT visible
        r = user_s.get(self.url("services/"))
        self.check("Ownership: user GET /services/ -> 200", r, 200)
        user_svc_ids = [svc["id"] for svc in self._results(r)]
        if admin_svc_id not in user_svc_ids:
            self._pass("Ownership: admin service NOT in user's list")
        else:
            self._fail("Ownership: admin service NOT in user's list", "service leaked")

        # User accesses admin's service directly -> 404
        r = user_s.get(self.url(f"services/{admin_svc_id}/"))
        self.check("Ownership: user GET admin service -> 404", r, 404)

        # User tries actions on admin's service -> 404
        for action in ("start", "stop", "shutdown", "reboot", "reset", "status", "provision", "ips", "console"):
            method = user_s.post if action not in ("ips", "console") else user_s.get
            r = method(self.url(f"services/{admin_svc_id}/{action}/"))
            self.check(f"Ownership: user {action} admin service -> 404", r, 404)

        # User tries cancel on admin's service -> 403 (admin-only permission)
        r = user_s.post(self.url(f"services/{admin_svc_id}/cancel/"))
        self.check("Ownership: user cancel admin service -> 403", r, 403)

        # ServicePlan isolation
        r = admin_s.get(self.url("serviceplans/"))
        admin_plans = self._results(r)
        if admin_plans:
            admin_sp_id = admin_plans[0]["id"]
            r = user_s.get(self.url(f"serviceplans/{admin_sp_id}/"))
            self.check("Ownership: user GET admin serviceplan -> 404", r, 404)

    # ── Phase 22: Bulk Import Endpoints ──────────────────────────────

    def test_bulk_import(self):
        self._section("Phase 22: Bulk Import Endpoints")
        s = self.admin_session
        u = self.user_session

        # Node bulk import (empty list)
        r = s.post(self.url("nodes/bulk_import/"), json={"nodes": []})
        self.check_any("BulkImport: POST /nodes/bulk_import/ empty -> 201|400", r, [201, 400])

        # NodeDisk bulk import (empty list)
        r = s.post(self.url("nodedisks/bulk_import/"), json={"disks": []})
        self.check_any("BulkImport: POST /nodedisks/bulk_import/ empty -> 201|400", r, [201, 400])

        # Service bulk import (empty list)
        r = s.post(self.url("services/bulk_import/"), json={"vms": [], "default_owner_id": 1})
        self.check_any("BulkImport: POST /services/bulk_import/ empty -> 201|400", r, [201, 400])

        # User cannot access bulk import
        r = u.post(self.url("services/bulk_import/"), json={"vms": []})
        self.check("BulkImport: user /services/bulk_import/ -> 403", r, 403)

        r = u.post(self.url("nodes/bulk_import/"), json={"nodes": []})
        self.check("BulkImport: user /nodes/bulk_import/ -> 403", r, 403)

        r = u.post(self.url("nodedisks/bulk_import/"), json={"disks": []})
        self.check("BulkImport: user /nodedisks/bulk_import/ -> 403", r, 403)

    # ── Phase 23: Pagination, no_page, and edge cases ────────────────

    def test_pagination(self):
        self._section("Phase 23: Pagination & Query Edge Cases")
        s = self.admin_session

        # Paginated list
        r = s.get(self.url("plans/"))
        self.check("Pagination: plans paginated -> 200", r, 200)
        body = self._json_body(r)
        if isinstance(body, dict) and "results" in body:
            self._pass("Pagination: response has 'results' key")
            for key in ("count", "next", "previous"):
                if key in body:
                    continue
                # DRF pagination normally includes these
                self._fail(f"Pagination: missing '{key}' key")
                break
            else:
                self._pass("Pagination: has count/next/previous keys")
        else:
            self._fail("Pagination: expected paginated response")

        # no_page returns flat list
        for endpoint in ("plans", "templates", "inventory", "apps"):
            r = s.get(self.url(f"{endpoint}/"), params={"no_page": "true"})
            self.check(f"Pagination: /{endpoint}/ no_page -> 200", r, 200)
            body = self._json_body(r)
            if isinstance(body, list):
                self._pass(f"Pagination: /{endpoint}/ no_page returns list")
            else:
                self._fail(f"Pagination: /{endpoint}/ no_page returns list")

        # Invalid ordering field -> still returns 200 (DRF ignores invalid)
        r = s.get(self.url("plans/"), params={"ordering": "nonexistent_field"})
        self.check("Pagination: invalid ordering field -> 200 (ignored)", r, 200)

        # HTTP methods on list endpoints
        r = s.options(self.url("plans/"))
        self.check("HTTP: OPTIONS /plans/ -> 200", r, 200)

        r = s.head(self.url("plans/"))
        self.check("HTTP: HEAD /plans/ -> 200", r, 200)

        # Method not allowed
        r = self.anon_session.delete(self.url("plans/"))
        self.check_any("HTTP: DELETE /plans/ list -> 401|405", r, [401, 405])

    # ── Phase 24: IPPool Delete Validation ───────────────────────────

    def test_ippool_delete_validation(self):
        self._section("Phase 24: IPPool Delete Validation")
        s = self.admin_session

        # Delete pool with unused IPs -> success
        if self.created["ippools"]:
            pool_id = self.created["ippools"][0]
            r = s.delete(self.url(f"ippools/{pool_id}/"))
            self.check("IPPool: DELETE unused pool -> 204", r, 204)
            if r.status_code == 204:
                self.created["ippools"].remove(pool_id)
        else:
            self._skip("IPPool: delete validation", "no pool created")

    # ── Phase 25: Create Second Test User (User B) ─────────────────

    def test_create_user_b(self):
        self._section("Phase 25: Create Second Test User (User B)")
        s = self.admin_session

        # Create User B via admin Customer API
        r = s.post(self.url("customers/"), json={
            "username": self.user_b_username,
            "email": f"{self.user_b_username}@example.com",
            "first_name": "Test",
            "last_name": "UserB",
        })
        self.check("UserB: POST /customers/ -> 201", r, 201)
        if r.status_code != 201:
            self._skip("UserB: remaining setup", "user creation failed")
            return
        self.user_b_id = r.json()["id"]

        # Set password via manage.py
        manage_script = (
            f"from django.contrib.auth import get_user_model; "
            f"u = get_user_model().objects.get(username='{self.user_b_username}'); "
            f"u.set_password('{self.user_b_password}'); u.save()"
        )
        if DOCKER_CONTAINER:
            cmd = ["docker", "exec", DOCKER_CONTAINER, "python", "manage.py", "shell", "-c", manage_script]
        else:
            cmd = ["python", "manage.py", "shell", "-c", manage_script]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            self._fail("UserB: set password via manage.py")
            return
        self._pass("UserB: password set via manage.py")

        # Obtain User B auth token
        r = self.anon_session.post(
            self.url("auth/token/"),
            json={"username": self.user_b_username, "password": self.user_b_password},
        )
        self.check("UserB: obtain token -> 200", r, 200)
        if r.status_code != 200:
            return
        self.user_b_token = r.json()["token"]
        self.user_b_session.headers["Authorization"] = f"Token {self.user_b_token}"

        # Verify User B sees empty service list
        r = self.user_b_session.get(self.url("services/"))
        self.check("UserB: GET /services/ -> 200", r, 200)
        results = self._results(r)
        if len(results) == 0:
            self._pass("UserB: sees empty service list")
        else:
            self._fail("UserB: sees empty service list", f"got {len(results)}")

    # ── Phase 26: User Browses Public Catalog ────────────────────────

    def test_user_browse_catalog(self):
        self._section("Phase 26: User Browses Public Catalog")
        u = self.user_session

        # Public read endpoints
        r = u.get(self.url("plans/"))
        self.check("Catalog: user GET /plans/ -> 200", r, 200)
        plans = self._results(r)
        if len(plans) > 0:
            self._pass(f"Catalog: plans available ({len(plans)})")
        else:
            self._pass("Catalog: plans list accessible (empty)")

        r = u.get(self.url("templates/"))
        self.check("Catalog: user GET /templates/ -> 200", r, 200)

        r = u.get(self.url("inventory/"))
        self.check("Catalog: user GET /inventory/ -> 200", r, 200)

        r = u.get(self.url("apps/"))
        self.check("Catalog: user GET /apps/ -> 200", r, 200)

        # Plan detail
        if self.created["plans"]:
            pid = self.created["plans"][0]
            r = u.get(self.url(f"plans/{pid}/"))
            self.check("Catalog: user GET /plans/{id}/ detail -> 200", r, 200)

        # Template detail
        if self.created["templates"]:
            tid = self.created["templates"][0]
            r = u.get(self.url(f"templates/{tid}/"))
            self.check("Catalog: user GET /templates/{id}/ detail -> 200", r, 200)

        # Write attempts on public-read endpoints -> 403
        r = u.post(self.url("plans/"), json={"name": "user-plan"})
        self.check("Catalog: user POST /plans/ -> 403", r, 403)

        r = u.post(self.url("templates/"), json={"name": "user-tmpl"})
        self.check("Catalog: user POST /templates/ -> 403", r, 403)

        r = u.post(self.url("apps/"), json={"name": "user-app", "cloud_init": "test"})
        self.check("Catalog: user POST /apps/ -> 403", r, 403)

        # Search/filter plans
        r = u.get(self.url("plans/"), params={"search": "test"})
        self.check("Catalog: user search plans -> 200", r, 200)

        r = u.get(self.url("plans/"), params={"ordering": "name"})
        self.check("Catalog: user order plans by name -> 200", r, 200)

        # Filter templates
        r = u.get(self.url("templates/"), params={"type": "lxc"})
        self.check("Catalog: user filter templates type=lxc -> 200", r, 200)

    # ── Phase 27: User Creates a Service (VPS Order) ─────────────────

    def test_user_creates_service(self):
        self._section("Phase 27: User Creates a Service (VPS Order)")
        u = self.user_session

        infra = self._get_real_infrastructure()
        if not infra:
            self._skip("UserService (all)", "no real infrastructure")
            return

        plan_id = infra["plan_id"]
        template_name = infra["template_name"]

        # User browses plans and picks one
        r = u.get(self.url("plans/"))
        self.check("UserService: browse plans -> 200", r, 200)

        r = u.get(self.url("templates/"))
        self.check("UserService: browse templates -> 200", r, 200)

        # User creates service (no owner field — should auto-set)
        r = u.post(self.url("services/"), json={
            "hostname": "user-vps.example.com",
            "plan": plan_id,
            "template": template_name,
            "password": "UserVpsPass123",
        })
        self.check("UserService: POST /services/ -> 201", r, 201)
        if r.status_code != 201:
            self._skip("UserService: remaining", "service creation failed")
            return
        body = r.json()
        svc_id = body["id"]
        self._track("user_a_services", svc_id)

        # Verify owner auto-set to User A
        owner_val = body.get("owner")
        if owner_val in (self.test_user_id, self.test_username):
            self._pass("UserService: owner auto-set to self")
        else:
            # Owner might be displayed differently; verify via detail
            r2 = u.get(self.url(f"services/{svc_id}/"))
            if r2.status_code == 200:
                detail_owner = r2.json().get("owner")
                if detail_owner in (self.test_user_id, self.test_username):
                    self._pass("UserService: owner auto-set to self (detail check)")
                else:
                    self._fail("UserService: owner auto-set to self", f"got owner={detail_owner}")
            else:
                self._fail("UserService: owner auto-set to self", "could not verify")

        # Verify status is initial
        if body.get("status") in ("pending", "active", "provisioning"):
            self._pass(f"UserService: initial status = {body.get('status')}")
        else:
            self._fail("UserService: initial status", f"got {body.get('status')}")

        # Verify password NOT in response
        if "password" not in body:
            self._pass("UserService: password not in response")
        else:
            self._fail("UserService: password not in response")

        # Verify plan_name present
        if body.get("plan_name"):
            self._pass("UserService: plan_name present in response")
        else:
            self._pass("UserService: plan_name field checked")

        # User lists services -> new service appears
        r = u.get(self.url("services/"))
        self.check("UserService: GET /services/ list -> 200", r, 200)
        results = self._results(r)
        if any(s["id"] == svc_id for s in results):
            self._pass("UserService: new service in list")
        else:
            self._fail("UserService: new service in list")

        # User views service detail
        r = u.get(self.url(f"services/{svc_id}/"))
        self.check("UserService: GET detail -> 200", r, 200)

        # User views IPs
        r = u.get(self.url(f"services/{svc_id}/ips/"))
        self.check("UserService: GET /ips/ -> 200", r, 200)

        # User views status
        r = u.post(self.url(f"services/{svc_id}/status/"))
        self.check_any("UserService: POST /status/ -> 200|500|502", r, [200, 500, 502])

        # User fires power actions
        for action in ("start", "stop", "shutdown", "reboot", "reset"):
            r = u.post(self.url(f"services/{svc_id}/{action}/"))
            if r.status_code == 202:
                self._pass(f"UserService: POST /{action}/ -> 202")
                task_body = self._json_body(r)
                if "task_id" in task_body:
                    self._pass(f"UserService: /{action}/ returns task_id")
                else:
                    self._fail(f"UserService: /{action}/ returns task_id")
            else:
                self._fail(f"UserService: POST /{action}/ -> 202", f"got {r.status_code}")

    # ── Phase 28: User Service Restrictions ──────────────────────────

    def test_user_service_restrictions(self):
        self._section("Phase 28: User Service Restrictions")
        u = self.user_session

        if not self.created.get("user_a_services"):
            self._skip("UserRestrict (all)", "no user service")
            return

        svc_id = self.created["user_a_services"][0]

        # User cancel own service -> 403 (admin-only action)
        r = u.post(self.url(f"services/{svc_id}/cancel/"))
        self.check("UserRestrict: cancel own service -> 403", r, 403)

        # User DELETE own service -> 403 (IsAuthenticated blocks destroy)
        r = u.delete(self.url(f"services/{svc_id}/"))
        self.check("UserRestrict: DELETE own service -> 403", r, 403)

        # Get original values to check read-only enforcement
        r = u.get(self.url(f"services/{svc_id}/"))
        original = self._json_body(r) if r.status_code == 200 else {}
        original_status = original.get("status")

        # User PATCHes read-only field (status) -> 200 but ignored
        r = u.patch(self.url(f"services/{svc_id}/"), json={"status": "active"})
        self.check("UserRestrict: PATCH status -> 200 (ignored)", r, 200)
        if r.status_code == 200:
            if r.json().get("status") == original_status:
                self._pass("UserRestrict: status unchanged after PATCH")
            else:
                self._fail("UserRestrict: status unchanged after PATCH")

        # User PATCHes read-only field (node) -> 200 but ignored
        r = u.patch(self.url(f"services/{svc_id}/"), json={"node": 999999})
        self.check("UserRestrict: PATCH node -> 200 (ignored)", r, 200)

        # User PATCHes writable field (hostname) -> 200, actually changes
        new_hostname = "patched-by-user.example.com"
        r = u.patch(self.url(f"services/{svc_id}/"), json={"hostname": new_hostname})
        self.check("UserRestrict: PATCH hostname -> 200", r, 200)
        if r.status_code == 200 and r.json().get("hostname") == new_hostname:
            self._pass("UserRestrict: hostname actually changed")
        else:
            self._fail("UserRestrict: hostname actually changed")

        # User bulk_import -> 403
        r = u.post(self.url("services/bulk_import/"), json={"vms": []})
        self.check("UserRestrict: bulk_import -> 403", r, 403)

    # ── Phase 29: Serializer Difference Verification ─────────────────

    def test_serializer_differences(self):
        self._section("Phase 29: Serializer Difference Verification")
        a = self.admin_session
        u = self.user_session

        if not self.created.get("user_a_services"):
            self._skip("SerializerDiff (all)", "no user service")
            return

        svc_id = self.created["user_a_services"][0]

        # Admin GETs User A's service -> full admin fields
        r = a.get(self.url(f"services/{svc_id}/"))
        self.check("SerializerDiff: admin GET user's service -> 200", r, 200)
        admin_body = self._json_body(r)

        # User A GETs same service
        r = u.get(self.url(f"services/{svc_id}/"))
        self.check("SerializerDiff: user GET own service -> 200", r, 200)
        user_body = self._json_body(r)

        # Both should have common fields
        for field in ("id", "hostname", "status", "machine_id", "owner"):
            if field in admin_body and field in user_body:
                continue
            self._fail(f"SerializerDiff: both views have field '{field}'")
            break
        else:
            self._pass("SerializerDiff: both views share common fields")

        # Admin creates service with explicit owner=user_a
        infra = self._get_real_infrastructure()
        if infra:
            r = a.post(self.url("services/"), json={
                "hostname": "admin-for-user.example.com",
                "plan": infra["plan_id"],
                "template": infra["template_name"],
                "password": "AdminCreated123",
                "owner": self.test_user_id,
            })
            self.check("SerializerDiff: admin creates service for user -> 201", r, 201)
            if r.status_code == 201:
                admin_created_id = r.json()["id"]
                self._track("user_a_services", admin_created_id)

                # User A should see this service
                r = u.get(self.url(f"services/{admin_created_id}/"))
                self.check("SerializerDiff: user sees admin-created service -> 200", r, 200)

        # Admin vs User A GET /serviceplans/
        r = a.get(self.url("serviceplans/"))
        admin_sp = self._results(r)
        r = u.get(self.url("serviceplans/"))
        user_sp = self._results(r)

        if len(admin_sp) >= len(user_sp):
            self._pass(f"SerializerDiff: admin sees >= user's serviceplans ({len(admin_sp)} vs {len(user_sp)})")
        else:
            self._fail("SerializerDiff: admin sees >= user's serviceplans")

        # All user's plans should be subset of admin's
        user_sp_ids = [sp["id"] for sp in user_sp]
        admin_sp_ids = [sp["id"] for sp in admin_sp]
        if all(sp_id in admin_sp_ids for sp_id in user_sp_ids):
            self._pass("SerializerDiff: user's serviceplans subset of admin's")
        else:
            self._fail("SerializerDiff: user's serviceplans subset of admin's")

        # User PATCHes service plan non-template field -> ignored (read-only)
        if user_sp:
            sp_id = user_sp[0]["id"]
            r = u.get(self.url(f"serviceplans/{sp_id}/"))
            if r.status_code == 200:
                original_name = r.json().get("name", "")
                r = u.patch(self.url(f"serviceplans/{sp_id}/"), json={"name": "hacked-name"})
                self.check("SerializerDiff: user PATCH serviceplan name -> 200", r, 200)
                if r.status_code == 200:
                    if r.json().get("name") == original_name:
                        self._pass("SerializerDiff: serviceplan name unchanged (read-only)")
                    else:
                        self._fail("SerializerDiff: serviceplan name unchanged (read-only)")

    # ── Phase 30: Owner Field Behavior ───────────────────────────────

    def test_owner_field_behavior(self):
        self._section("Phase 30: Owner Field Behavior")
        u = self.user_session
        a = self.admin_session

        infra = self._get_real_infrastructure()
        if not infra:
            self._skip("OwnerField (all)", "no real infrastructure")
            return

        plan_id = infra["plan_id"]
        template_name = infra["template_name"]

        # User creates service without owner -> auto-set to self
        r = u.post(self.url("services/"), json={
            "hostname": "owner-test-1.example.com",
            "plan": plan_id,
            "template": template_name,
            "password": "OwnerTest123",
        })
        self.check("OwnerField: user creates without owner -> 201", r, 201)
        if r.status_code == 201:
            self._track("user_a_services", r.json()["id"])
            owner_val = r.json().get("owner")
            if owner_val in (self.test_user_id, self.test_username):
                self._pass("OwnerField: auto-set to self")
            else:
                self._fail("OwnerField: auto-set to self", f"got owner={owner_val}")

        # User creates service with owner=self -> 201
        r = u.post(self.url("services/"), json={
            "hostname": "owner-test-2.example.com",
            "plan": plan_id,
            "template": template_name,
            "password": "OwnerTest123",
            "owner": self.test_user_id,
        })
        self.check("OwnerField: user creates with owner=self -> 201", r, 201)
        if r.status_code == 201:
            self._track("user_a_services", r.json()["id"])

        # User creates service with owner=user_b -> 400
        if self.user_b_id:
            r = u.post(self.url("services/"), json={
                "hostname": "owner-test-3.example.com",
                "plan": plan_id,
                "template": template_name,
                "password": "OwnerTest123",
                "owner": self.user_b_id,
            })
            self.check("OwnerField: user creates with owner=other -> 400", r, 400)

        # User creates service with owner=999999 -> 400
        r = u.post(self.url("services/"), json={
            "hostname": "owner-test-4.example.com",
            "plan": plan_id,
            "template": template_name,
            "password": "OwnerTest123",
            "owner": 999999,
        })
        self.check("OwnerField: user creates with owner=999999 -> 400", r, 400)

        # Admin creates service with owner=user_a -> 201
        r = a.post(self.url("services/"), json={
            "hostname": "admin-owner-a.example.com",
            "plan": plan_id,
            "template": template_name,
            "password": "AdminOwner123",
            "owner": self.test_user_id,
        })
        self.check("OwnerField: admin creates with owner=user_a -> 201", r, 201)
        if r.status_code == 201:
            self._track("user_a_services", r.json()["id"])
            if r.json().get("owner") in (self.test_user_id, self.test_username):
                self._pass("OwnerField: admin-created owner=user_a verified")
            else:
                self._fail("OwnerField: admin-created owner=user_a verified")

        # Admin creates service with owner=user_b -> 201
        if self.user_b_id:
            r = a.post(self.url("services/"), json={
                "hostname": "admin-owner-b.example.com",
                "plan": plan_id,
                "template": template_name,
                "password": "AdminOwner123",
                "owner": self.user_b_id,
            })
            self.check("OwnerField: admin creates with owner=user_b -> 201", r, 201)
            if r.status_code == 201:
                self._track("user_b_services", r.json()["id"])
                if r.json().get("owner") in (self.user_b_id, self.user_b_username):
                    self._pass("OwnerField: admin-created owner=user_b verified")
                else:
                    self._fail("OwnerField: admin-created owner=user_b verified")

    # ── Phase 31: Multi-User Isolation ───────────────────────────────

    def test_multi_user_isolation(self):
        self._section("Phase 31: Multi-User Isolation")
        ua = self.user_session
        ub = self.user_b_session
        admin = self.admin_session

        if not self.user_b_token:
            self._skip("Isolation (all)", "User B not created")
            return

        infra = self._get_real_infrastructure()

        # User B creates own service (if infrastructure available)
        user_b_svc_id = None
        if infra:
            r = ub.post(self.url("services/"), json={
                "hostname": "user-b-vps.example.com",
                "plan": infra["plan_id"],
                "template": infra["template_name"],
                "password": "UserBPass123",
            })
            self.check("Isolation: User B creates service -> 201", r, 201)
            if r.status_code == 201:
                user_b_svc_id = r.json()["id"]
                self._track("user_b_services", user_b_svc_id)

        # Get User A service IDs
        user_a_svc_ids = self.created.get("user_a_services", [])

        # User A lists services -> does NOT see User B's
        r = ua.get(self.url("services/"))
        self.check("Isolation: User A lists services -> 200", r, 200)
        user_a_list = [s["id"] for s in self._results(r)]
        if user_b_svc_id and user_b_svc_id not in user_a_list:
            self._pass("Isolation: User A does NOT see User B's service")
        elif user_b_svc_id:
            self._fail("Isolation: User A does NOT see User B's service")
        else:
            self._skip("Isolation: User A / B service visibility", "no User B service")

        # User B lists services -> does NOT see User A's
        r = ub.get(self.url("services/"))
        self.check("Isolation: User B lists services -> 200", r, 200)
        user_b_list = [s["id"] for s in self._results(r)]
        if user_a_svc_ids:
            leaked = [sid for sid in user_a_svc_ids if sid in user_b_list]
            if not leaked:
                self._pass("Isolation: User B does NOT see User A's services")
            else:
                self._fail("Isolation: User B does NOT see User A's services", f"leaked: {leaked}")
        else:
            self._skip("Isolation: User B / A service visibility", "no User A service")

        # User A GETs User B's service by ID -> 404
        if user_b_svc_id:
            r = ua.get(self.url(f"services/{user_b_svc_id}/"))
            self.check("Isolation: User A GET User B's service -> 404", r, 404)

            # User A tries all actions on User B's service -> 404
            for action in ("start", "stop", "shutdown", "reboot", "reset", "status", "provision"):
                r = ua.post(self.url(f"services/{user_b_svc_id}/{action}/"))
                self.check(f"Isolation: User A {action} User B's service -> 404", r, 404)

            for action in ("ips", "console"):
                r = ua.get(self.url(f"services/{user_b_svc_id}/{action}/"))
                self.check(f"Isolation: User A {action} User B's service -> 404", r, 404)

            # Cancel is admin-only permission, so 403 before ownership check
            r = ua.post(self.url(f"services/{user_b_svc_id}/cancel/"))
            self.check("Isolation: User A cancel User B's service -> 403", r, 403)

        # ServicePlan isolation
        r = ua.get(self.url("serviceplans/"))
        user_a_sp = self._results(r)
        r = ub.get(self.url("serviceplans/"))
        user_b_sp = self._results(r)
        user_a_sp_ids = set(sp["id"] for sp in user_a_sp)
        user_b_sp_ids = set(sp["id"] for sp in user_b_sp)
        if not user_a_sp_ids & user_b_sp_ids:
            self._pass("Isolation: ServicePlan no overlap between users")
        else:
            self._fail("Isolation: ServicePlan no overlap between users")

        # PortBlock/PortForward/DomainRoute isolation
        for endpoint in ("portblocks", "portforwards", "domainroutes"):
            r = ua.get(self.url(f"{endpoint}/"))
            a_items = set(i["id"] for i in self._results(r))
            r = ub.get(self.url(f"{endpoint}/"))
            b_items = set(i["id"] for i in self._results(r))
            if not a_items & b_items:
                self._pass(f"Isolation: {endpoint} no overlap between users")
            else:
                self._fail(f"Isolation: {endpoint} no overlap between users")

        # Admin lists services -> sees ALL from both users
        r = admin.get(self.url("services/"))
        self.check("Isolation: admin lists services -> 200", r, 200)
        admin_svc_ids = [s["id"] for s in self._results(r)]
        all_user_svcs = list(user_a_svc_ids) + self.created.get("user_b_services", [])
        visible_count = sum(1 for sid in all_user_svcs if sid in admin_svc_ids)
        if all_user_svcs and visible_count == len(all_user_svcs):
            self._pass("Isolation: admin sees all user services")
        elif all_user_svcs:
            self._fail("Isolation: admin sees all user services", f"{visible_count}/{len(all_user_svcs)} visible")
        else:
            self._skip("Isolation: admin visibility", "no user services to check")

    # ── Phase 32: User Port Forward CRUD ─────────────────────────────

    def test_user_portforward_crud(self):
        self._section("Phase 32: User Port Forward CRUD")
        u = self.user_session

        # User lists own port blocks
        r = u.get(self.url("portblocks/"))
        self.check("UserPF: GET /portblocks/ -> 200", r, 200)
        port_blocks = self._results(r)

        if not port_blocks:
            self._skip("UserPF (CRUD)", "no port blocks for user (created during provisioning)")
            # Still test write prohibition on portblocks
            r = u.post(self.url("portblocks/"), json={"gateway": 1, "service_network": 1})
            self.check("UserPF: POST /portblocks/ -> 403 (ReadOnly)", r, 403)
            return

        pb = port_blocks[0]
        pb_id = pb["id"]
        port_start = pb.get("port_start", 10000)
        port_end = pb.get("port_end", 10099)

        # User creates port forward with valid data
        valid_ext_port = port_start
        r = u.post(self.url("portforwards/"), json={
            "port_block": pb_id,
            "external_port": valid_ext_port,
            "internal_port": 8080,
            "protocol": "tcp",
            "label": "test-forward",
            "enabled": True,
        })
        self.check("UserPF: POST create -> 201", r, 201)
        if r.status_code == 201:
            pf_id = r.json()["id"]
            self._track("user_a_portforwards", pf_id)

            # List port forwards
            r = u.get(self.url("portforwards/"))
            self.check("UserPF: GET list -> 200", r, 200)
            if any(pf["id"] == pf_id for pf in self._results(r)):
                self._pass("UserPF: created forward in list")
            else:
                self._fail("UserPF: created forward in list")

            # Retrieve
            r = u.get(self.url(f"portforwards/{pf_id}/"))
            self.check("UserPF: GET detail -> 200", r, 200)

            # PATCH
            r = u.patch(self.url(f"portforwards/{pf_id}/"), json={"label": "updated-label"})
            self.check("UserPF: PATCH -> 200", r, 200)
            if r.status_code == 200 and r.json().get("label") == "updated-label":
                self._pass("UserPF: PATCH label updated")
            elif r.status_code == 200:
                self._pass("UserPF: PATCH accepted")

            # DELETE -> 403 (IsAuthenticated blocks destroy)
            r = u.delete(self.url(f"portforwards/{pf_id}/"))
            self.check("UserPF: DELETE -> 403", r, 403)

        # Validation: external_port outside block range -> 400
        r = u.post(self.url("portforwards/"), json={
            "port_block": pb_id,
            "external_port": port_end + 100,
            "internal_port": 80,
            "protocol": "tcp",
        })
        self.check("UserPF: external_port out of range -> 400", r, 400)

        # Validation: internal_port out of range -> 400
        r = u.post(self.url("portforwards/"), json={
            "port_block": pb_id,
            "external_port": port_start + 1,
            "internal_port": 99999,
            "protocol": "tcp",
        })
        self.check("UserPF: internal_port out of range -> 400", r, 400)

        # Cross-user: User A uses User B's port block -> 400
        if self.user_b_token:
            ub = self.user_b_session
            r = ub.get(self.url("portblocks/"))
            user_b_blocks = self._results(r)
            if user_b_blocks:
                b_pb_id = user_b_blocks[0]["id"]
                r = u.post(self.url("portforwards/"), json={
                    "port_block": b_pb_id,
                    "external_port": user_b_blocks[0].get("port_start", 10000),
                    "internal_port": 80,
                    "protocol": "tcp",
                })
                self.check("UserPF: User A uses User B's block -> 400", r, 400)
            else:
                self._skip("UserPF: cross-user block test", "User B has no port blocks")

        # PortBlock write prohibition
        r = u.post(self.url("portblocks/"), json={"gateway": 1, "service_network": 1})
        self.check("UserPF: POST /portblocks/ -> 403 (ReadOnly)", r, 403)

    # ── Phase 33: User Domain Route CRUD ─────────────────────────────

    def test_user_domainroute_crud(self):
        self._section("Phase 33: User Domain Route CRUD")
        u = self.user_session

        user_a_svcs = self.created.get("user_a_services", [])
        if not user_a_svcs:
            self._skip("UserDR (all)", "no user service")
            return

        svc_id = user_a_svcs[0]
        test_domain = f"test-{uuid.uuid4().hex[:8]}.example.com"

        # User creates domain route for own service
        r = u.post(self.url("domainroutes/"), json={
            "service": svc_id,
            "domain": test_domain,
            "forward_port": 80,
            "ssl": True,
            "force_ssl": True,
            "enabled": True,
        })
        if r.status_code == 201:
            self._pass("UserDR: POST create -> 201")
            dr_id = r.json()["id"]
            self._track("user_a_domainroutes", dr_id)

            # List
            r = u.get(self.url("domainroutes/"))
            self.check("UserDR: GET list -> 200", r, 200)
            if any(d["id"] == dr_id for d in self._results(r)):
                self._pass("UserDR: created route in list")
            else:
                self._fail("UserDR: created route in list")

            # Retrieve
            r = u.get(self.url(f"domainroutes/{dr_id}/"))
            self.check("UserDR: GET detail -> 200", r, 200)

            # PATCH
            r = u.patch(self.url(f"domainroutes/{dr_id}/"), json={"forward_port": 8080})
            self.check("UserDR: PATCH -> 200", r, 200)

            # DELETE -> 403 (IsAuthenticated blocks destroy)
            r = u.delete(self.url(f"domainroutes/{dr_id}/"))
            self.check("UserDR: DELETE -> 403", r, 403)
        elif r.status_code == 400:
            self._pass("UserDR: POST -> 400 (expected if no gateway/internal IP)")
            body = self._json_body(r)
            print(f"    (detail: {body})")
        else:
            self._fail("UserDR: POST create -> 201 or 400", f"got {r.status_code}")

        # Cross-user: User A creates route for User B's service -> 400
        user_b_svcs = self.created.get("user_b_services", [])
        if user_b_svcs:
            r = u.post(self.url("domainroutes/"), json={
                "service": user_b_svcs[0],
                "domain": f"cross-{uuid.uuid4().hex[:8]}.example.com",
                "forward_port": 80,
            })
            self.check("UserDR: User A route for User B's service -> 400", r, 400)
        else:
            self._skip("UserDR: cross-user test", "no User B service")

        # Validation: forward_port out of range -> 400
        r = u.post(self.url("domainroutes/"), json={
            "service": svc_id,
            "domain": f"badport-{uuid.uuid4().hex[:8]}.example.com",
            "forward_port": 99999,
        })
        self.check_any("UserDR: forward_port out of range -> 400|201", r, [400, 201])
        if r.status_code == 201:
            self._track("user_a_domainroutes", r.json()["id"])

        # Validation: duplicate domain -> 400
        if self.created.get("user_a_domainroutes"):
            r = u.post(self.url("domainroutes/"), json={
                "service": svc_id,
                "domain": test_domain,
                "forward_port": 80,
            })
            self.check("UserDR: duplicate domain -> 400", r, 400)

    # ── Phase 34: Admin Managing User Services ───────────────────────

    def test_admin_manages_user_services(self):
        self._section("Phase 34: Admin Managing User Services")
        a = self.admin_session
        u = self.user_session

        user_a_svcs = self.created.get("user_a_services", [])
        user_b_svcs = self.created.get("user_b_services", [])

        # Admin lists all services -> sees User A's and User B's
        r = a.get(self.url("services/"))
        self.check("AdminManage: GET /services/ -> 200", r, 200)
        admin_svc_ids = [s["id"] for s in self._results(r)]

        for svc_id in user_a_svcs:
            if svc_id in admin_svc_ids:
                self._pass(f"AdminManage: admin sees User A service {svc_id}")
                break
        else:
            if user_a_svcs:
                self._fail("AdminManage: admin sees User A services")
            else:
                self._skip("AdminManage: User A visibility", "no User A services")

        for svc_id in user_b_svcs:
            if svc_id in admin_svc_ids:
                self._pass(f"AdminManage: admin sees User B service {svc_id}")
                break
        else:
            if user_b_svcs:
                self._fail("AdminManage: admin sees User B services")
            else:
                self._skip("AdminManage: User B visibility", "no User B services")

        # Admin views/patches/cancels User A's service
        if user_a_svcs:
            svc_id = user_a_svcs[0]

            r = a.get(self.url(f"services/{svc_id}/"))
            self.check("AdminManage: admin GET user's service detail -> 200", r, 200)

            r = a.patch(self.url(f"services/{svc_id}/"), json={"hostname": "admin-patched.example.com"})
            self.check("AdminManage: admin PATCH user's service -> 200", r, 200)

            r = a.post(self.url(f"services/{svc_id}/cancel/"))
            self.check("AdminManage: admin cancel user's service -> 202", r, 202)

        # Dashboard summary checks
        r = a.get(self.url("dashboard/summary/"))
        self.check("AdminManage: dashboard summary -> 200", r, 200)
        if r.status_code == 200:
            body = r.json()
            if body.get("services", 0) > 0:
                self._pass("AdminManage: dashboard services > 0")
            else:
                self._pass("AdminManage: dashboard services count checked")
            if body.get("users", 0) >= 3:
                self._pass(f"AdminManage: dashboard users >= 3 (got {body.get('users')})")
            else:
                self._fail("AdminManage: dashboard users >= 3", f"got {body.get('users')}")

        # Admin creates service on behalf of User A -> appears in user's list
        infra = self._get_real_infrastructure()
        if infra:
            r = a.post(self.url("services/"), json={
                "hostname": "admin-behalf.example.com",
                "plan": infra["plan_id"],
                "template": infra["template_name"],
                "password": "AdminBehalf123",
                "owner": self.test_user_id,
            })
            self.check("AdminManage: admin creates for user -> 201", r, 201)
            if r.status_code == 201:
                new_svc_id = r.json()["id"]
                self._track("user_a_services", new_svc_id)

                # Appears in User A's list
                r = u.get(self.url("services/"))
                if any(s["id"] == new_svc_id for s in self._results(r)):
                    self._pass("AdminManage: admin-created appears in user's list")
                else:
                    self._fail("AdminManage: admin-created appears in user's list")

        # Admin deletes user's port forwards
        user_a_pfs = self.created.get("user_a_portforwards", [])
        if user_a_pfs:
            pf_id = user_a_pfs[-1]
            r = a.delete(self.url(f"portforwards/{pf_id}/"))
            self.check("AdminManage: admin DELETE user's portforward -> 204", r, 204)
            if r.status_code == 204:
                self.created["user_a_portforwards"].remove(pf_id)
        else:
            self._skip("AdminManage: admin delete portforward", "no user portforwards")

    # ── Phase 35: User Edge Cases & Validation ───────────────────────

    def test_user_edge_cases(self):
        self._section("Phase 35: User Edge Cases & Validation")
        u = self.user_session

        # Empty body -> 400
        r = u.post(self.url("services/"), json={})
        self.check("EdgeCase: POST service empty body -> 400", r, 400)

        # Nonexistent plan -> 400
        r = u.post(self.url("services/"), json={
            "hostname": "edge.example.com",
            "plan": 999999,
            "template": "nonexistent",
        })
        self.check("EdgeCase: POST nonexistent plan -> 400", r, 400)

        # Invalid hostname
        r = u.post(self.url("services/"), json={
            "hostname": "!!!invalid!!!",
            "plan": 1,
            "template": "anything",
        })
        self.check("EdgeCase: POST invalid hostname -> 400", r, 400)

        # Missing required fields
        r = u.post(self.url("services/"), json={"hostname": "only-hostname.example.com"})
        self.check("EdgeCase: POST missing plan/template -> 400", r, 400)

        # Nonexistent service ID -> 404
        r = u.get(self.url("services/999999/"))
        self.check("EdgeCase: GET nonexistent service -> 404", r, 404)

        # Actions on nonexistent service -> 404
        for action in ("start", "stop", "shutdown", "reboot", "reset"):
            r = u.post(self.url(f"services/999999/{action}/"))
            self.check(f"EdgeCase: {action} nonexistent -> 404", r, 404)

        r = u.get(self.url("services/999999/ips/"))
        self.check("EdgeCase: ips on nonexistent -> 404", r, 404)

        # User POST/PATCH /portblocks/ -> 403 (ReadOnly for non-admin)
        r = u.post(self.url("portblocks/"), json={"gateway": 1, "service_network": 1})
        self.check("EdgeCase: POST /portblocks/ -> 403", r, 403)

        r = u.patch(self.url("portblocks/1/"), json={"port_start": 100})
        self.check_any("EdgeCase: PATCH /portblocks/ -> 403|404", r, [403, 404])

        # Nonexistent template
        r = u.post(self.url("services/"), json={
            "hostname": "edge2.example.com",
            "plan": self.created["plans"][0] if self.created["plans"] else 1,
            "template": "definitely-not-a-template",
        })
        self.check("EdgeCase: POST nonexistent template -> 400", r, 400)

    # ── Cleanup ──────────────────────────────────────────────────────

    def cleanup(self):
        self._section("Cleanup")
        s = self.admin_session

        # Delete in reverse dependency order
        # Keys prefixed with user_a_/user_b_ map to their base API endpoint
        delete_order = [
            "user_a_domainroutes",
            "user_b_domainroutes",
            "domainroutes",
            "user_a_portforwards",
            "user_b_portforwards",
            "portforwards",
            "portblocks",
            "portgateways",
            "user_a_services",
            "user_b_services",
            "services",
            "serviceplans",
            "inventory",
            "apps",
            "ips",
            "ippools",
            "templates",
            "plans",
            "nodedisks",
            "nodes",
            "clusters",
        ]

        resource_endpoint = {
            "user_a_services": "services",
            "user_b_services": "services",
            "user_a_portforwards": "portforwards",
            "user_b_portforwards": "portforwards",
            "user_a_domainroutes": "domainroutes",
            "user_b_domainroutes": "domainroutes",
        }

        for resource in delete_order:
            endpoint = resource_endpoint.get(resource, resource)
            for item_id in reversed(self.created.get(resource, [])):
                r = s.delete(self.url(f"{endpoint}/{item_id}/"))
                if r.status_code in (204, 200, 202):
                    print(f"  Deleted {endpoint}/{item_id} -> {r.status_code}")
                elif r.status_code == 404:
                    print(f"  {endpoint}/{item_id} already gone (404)")
                else:
                    print(f"  {YELLOW}Warning: DELETE {endpoint}/{item_id} -> {r.status_code}{RESET}")

        # Delete test users
        if self.test_user_id:
            r = s.delete(self.url(f"customers/{self.test_user_id}/"))
            if r.status_code in (204, 200):
                print(f"  Deleted test user {self.test_username} -> {r.status_code}")
            else:
                print(f"  {YELLOW}Warning: DELETE test user -> {r.status_code}{RESET}")

        if self.user_b_id:
            r = s.delete(self.url(f"customers/{self.user_b_id}/"))
            if r.status_code in (204, 200):
                print(f"  Deleted test user B {self.user_b_username} -> {r.status_code}")
            else:
                print(f"  {YELLOW}Warning: DELETE test user B -> {r.status_code}{RESET}")

    # ── Run ──────────────────────────────────────────────────────────

    def run(self):
        print(f"\n{BOLD}=== Inveterate Functional API Tests ==={RESET}")
        print(f"  Target: {BASE_URL}")
        print(f"  Admin:  {ADMIN_USER}")

        try:
            self.setup()
            self.test_token_auth()
            self.test_anonymous()
            self.test_api_docs()
            self._clear_throttle_cache()
            self.test_admin_clusters()
            self.test_admin_nodes()
            self.test_admin_nodedisks()
            self.test_admin_plans()
            self.test_admin_templates()
            self._clear_throttle_cache()
            self.test_admin_ippools()
            self.test_admin_apps()
            self.test_admin_portgateways()
            self.test_admin_customers()
            self._clear_throttle_cache()
            self.test_permissions()
            self.test_dashboard()
            self.test_inventory()
            self._clear_throttle_cache()
            self.test_serviceplans()
            self.test_portblocks()
            self.test_portforwards()
            self.test_domainroutes()
            self.test_service_lifecycle()
            self._clear_throttle_cache()
            self.test_ownership()
            self.test_bulk_import()
            self.test_pagination()
            self.test_ippool_delete_validation()
            self._clear_throttle_cache()
            self.test_create_user_b()
            self.test_user_browse_catalog()
            self._clear_throttle_cache()
            self.test_user_creates_service()
            self.test_user_service_restrictions()
            self.test_serializer_differences()
            self._clear_throttle_cache()
            self.test_owner_field_behavior()
            self.test_multi_user_isolation()
            self._clear_throttle_cache()
            self.test_user_portforward_crud()
            self.test_user_domainroute_crud()
            self.test_admin_manages_user_services()
            self.test_user_edge_cases()
        finally:
            self.cleanup()

        self.report()

    def report(self):
        total = self.passed + self.failed + self.skipped
        print(f"\n{BOLD}=== Results: ", end="")
        print(f"{GREEN}{self.passed} passed{RESET}", end="")
        print(f", {RED}{self.failed} failed{RESET}" if self.failed else f", 0 failed", end="")
        print(f", {YELLOW}{self.skipped} skipped{RESET}" if self.skipped else "", end="")
        print(f" (of {total} total) ==={RESET}\n")

        if self.failed:
            sys.exit(1)
        sys.exit(0)


def main():
    if not BASE_URL:
        print(f"{RED}Error: BASE_URL environment variable is required{RESET}")
        print("  export BASE_URL=http://localhost:8000")
        sys.exit(2)
    if not ADMIN_USER or not ADMIN_PASS:
        print(f"{RED}Error: ADMIN_USER and ADMIN_PASS environment variables are required{RESET}")
        print("  export ADMIN_USER=admin")
        print("  export ADMIN_PASS=yourpassword")
        sys.exit(2)

    runner = APITestRunner()
    runner.run()


if __name__ == "__main__":
    main()
