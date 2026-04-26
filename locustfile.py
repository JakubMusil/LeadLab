"""
Locust load-testing scenario for LeadLab.

Simulates realistic multi-tenant CRM usage patterns.  The scenario covers the
most frequently hit API paths: authentication, lead listing, customer listing,
dashboard stats, and lead creation.

Usage:
  locust -f locustfile.py --host http://localhost:8000 \
         --users 50 --spawn-rate 5 --run-time 60s --headless

Target: API p95 response time < 200 ms at 50 concurrent users.

Environment variables:
  LOCUST_EMAIL     — user email to authenticate with (default: locust@leadlab.test)
  LOCUST_PASSWORD  — user password                   (default: LocustPassword123!)
  LOCUST_FIRM_ID   — X-Firm-ID header value; derived from login response if blank
"""
import json
import os
import time

from locust import HttpUser, SequentialTaskSet, between, events, task


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _headers(firm_id: str) -> dict:
    return {"X-Firm-ID": firm_id, "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Task sets
# ---------------------------------------------------------------------------

class CRMTasks(SequentialTaskSet):
    """
    Simulates a sales rep's session:
      1. Hit the health endpoint (cheap probe).
      2. Fetch leads list (most common read).
      3. Fetch customers list.
      4. Fetch dashboard stats.
      5. Create a lead (write operation).
      6. Fetch the activity feed.
    """

    firm_id: str = ""

    def on_start(self):
        self.firm_id = self.user.firm_id  # type: ignore[attr-defined]

    @task
    def health_check(self):
        with self.client.get("/api/v1/health/", name="/health/", catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Health check failed: {resp.status_code}")

    @task
    def list_leads(self):
        with self.client.get(
            "/api/v1/crm/leads",
            headers=_headers(self.firm_id),
            name="/crm/leads (list)",
            catch_response=True,
        ) as resp:
            if resp.status_code not in (200, 401):
                resp.failure(f"Leads list failed: {resp.status_code}")

    @task
    def list_customers(self):
        with self.client.get(
            "/api/v1/crm/customers",
            headers=_headers(self.firm_id),
            name="/crm/customers (list)",
            catch_response=True,
        ) as resp:
            if resp.status_code not in (200, 401):
                resp.failure(f"Customers list failed: {resp.status_code}")

    @task
    def dashboard_stats(self):
        with self.client.get(
            "/api/v1/crm/dashboard-stats",
            headers=_headers(self.firm_id),
            name="/crm/dashboard-stats",
            catch_response=True,
        ) as resp:
            if resp.status_code not in (200, 401):
                resp.failure(f"Dashboard stats failed: {resp.status_code}")

    @task
    def create_lead(self):
        payload = json.dumps(
            {
                "title": f"Locust Lead {time.time_ns()}",
                "status": "new",
                "source": "web",
            }
        )
        with self.client.post(
            "/api/v1/crm/leads",
            data=payload,
            headers=_headers(self.firm_id),
            name="/crm/leads (create)",
            catch_response=True,
        ) as resp:
            if resp.status_code not in (200, 201, 401):
                resp.failure(f"Lead creation failed: {resp.status_code}")

    @task
    def activity_feed(self):
        with self.client.get(
            "/api/v1/crm/activity-feed",
            headers=_headers(self.firm_id),
            name="/crm/activity-feed",
            catch_response=True,
        ) as resp:
            if resp.status_code not in (200, 401):
                resp.failure(f"Activity feed failed: {resp.status_code}")


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class LeadLabUser(HttpUser):
    """
    Represents a single concurrent user of the LeadLab API.

    Authenticates on start and stores the firm_id for subsequent requests.
    """

    tasks = [CRMTasks]
    wait_time = between(0.5, 2.0)
    firm_id: str = ""

    _email: str = os.environ.get("LOCUST_EMAIL", "locust@leadlab.test")
    _password: str = os.environ.get("LOCUST_PASSWORD", "LocustPassword123!")
    _firm_id_override: str = os.environ.get("LOCUST_FIRM_ID", "")

    def on_start(self):
        """Log in and resolve the active firm ID."""
        if self._firm_id_override:
            self.firm_id = self._firm_id_override
            return

        resp = self.client.post(
            "/api/v1/users/login",
            json={"email": self._email, "password": self._password},
        )
        if resp.status_code == 200:
            data = resp.json()
            # The login endpoint returns the user; fetch firms separately.
            firms_resp = self.client.get("/api/v1/firms/")
            if firms_resp.status_code == 200:
                firms = firms_resp.json()
                if firms:
                    self.firm_id = str(firms[0].get("id", ""))
        else:
            # Register a new user on-the-fly so the scenario can self-bootstrap.
            import uuid

            new_email = f"locust-{uuid.uuid4().hex[:8]}@leadlab.test"
            reg_resp = self.client.post(
                "/api/v1/users/register",
                json={
                    "email": new_email,
                    "password": self._password,
                    "first_name": "Locust",
                    "last_name": "User",
                },
            )
            if reg_resp.status_code in (200, 201):
                # Create a firm for this user.
                firm_resp = self.client.post(
                    "/api/v1/firms/",
                    json={"name": f"Locust Firm {uuid.uuid4().hex[:6]}"},
                )
                if firm_resp.status_code in (200, 201):
                    self.firm_id = str(firm_resp.json().get("id", ""))


# ---------------------------------------------------------------------------
# Custom event hooks
# ---------------------------------------------------------------------------

@events.quitting.add_listener
def assert_p95(environment, **kwargs):
    """
    Fail the Locust run if the overall p95 response time exceeds 200 ms.

    This hook is called when Locust exits (--headless mode).
    """
    stats = environment.stats.total
    p95 = stats.get_response_time_percentile(0.95)
    threshold_ms = 200
    if p95 and p95 > threshold_ms:
        print(
            f"\n[FAIL] p95 response time {p95:.0f} ms exceeds threshold of {threshold_ms} ms."
        )
        environment.process_exit_code = 1
    elif p95:
        print(f"\n[PASS] p95 response time {p95:.0f} ms is within the {threshold_ms} ms threshold.")
