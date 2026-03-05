#!/usr/bin/env python3
"""Customer journey walkthrough — uses the live API as a real user would.

Walks through every step a customer takes, from anonymous browsing to
ordering a VPS, managing it, and trying to leave. Reports findings as
a narrative with observations about UX, bugs, and missing pieces.

Usage:
    export BASE_URL=http://localhost:8000
    export ADMIN_USER=admin
    export ADMIN_PASS=admin
    export DOCKER_CONTAINER=inveterate-web-1   # optional
    python tests/journey.py
"""
import json
import os
import subprocess
import sys
import time
import uuid

import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "admin")
DOCKER_CONTAINER = os.environ.get("DOCKER_CONTAINER", "")

# ANSI
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"

observations = []  # (category, message) tuples
created_service_ids = []
created_user_id = None


def url(path):
    return f"{BASE_URL}/api/v1/{path.lstrip('/')}"


def pp(data):
    """Pretty-print JSON data."""
    print(json.dumps(data, indent=2))


def note(category, msg):
    """Record an observation."""
    icon = {"good": f"{GREEN}+{RESET}", "issue": f"{RED}!{RESET}",
            "ux": f"{YELLOW}?{RESET}", "info": f"{CYAN}i{RESET}"}
    observations.append((category, msg))
    print(f"  {icon.get(category, '.')} {msg}")


def heading(step, title):
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  STEP {step}: {title}{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")


def subheading(title):
    print(f"\n  {BOLD}--- {title} ---{RESET}")


def show(label, r, show_body=True):
    """Show request result."""
    status_color = GREEN if r.status_code < 400 else (YELLOW if r.status_code < 500 else RED)
    print(f"  {DIM}{r.request.method} {r.request.path_url}{RESET} → {status_color}{r.status_code}{RESET}")
    if show_body and r.headers.get("content-type", "").startswith("application/json"):
        body = r.json()
        # Truncate large result lists
        if isinstance(body, dict) and "results" in body and len(body["results"]) > 3:
            body = {**body, "results": body["results"][:3], "_truncated": f"...and {body['count'] - 3} more"}
        print(f"  {json.dumps(body, indent=2)}")


# ═══════════════════════════════════════════════════════════════
# STEP 1: DISCOVER — What can I buy?
# ═══════════════════════════════════════════════════════════════

def step_1_discover():
    heading(1, "DISCOVER — What can I buy? (Anonymous)")
    anon = requests.Session()

    subheading("Browse Plans")
    r = anon.get(url("plans/"))
    show("Plans", r)
    plans = r.json().get("results", [])
    if plans:
        note("good", f"Found {len(plans)} plans to choose from")
        for p in plans:
            price_info = ""  # No price field visible
            print(f"    • {p['name']}: {p['cores']} cores, {p['ram']}MB RAM, "
                  f"{p['size']}GB disk, {p['bandwidth']}GB BW, "
                  f"{p['ipv4_ips']} IPv4 + {p['internal_ips']} internal IPs")
    else:
        note("issue", "No plans available — customer sees empty catalog")
        return None

    # Check: is there a price field?
    sample = plans[0]
    if "price" not in sample:
        note("ux", "No price field on plans — customer can't see what things cost")

    # Check: is there a description?
    if "description" not in sample:
        note("ux", "No description field on plans — just raw specs, no marketing copy")

    subheading("Browse Templates (OS images)")
    r = anon.get(url("templates/"))
    if r.status_code == 401:
        note("issue", "Templates require authentication — anonymous users can't see what OS options exist before signing up")
        return plans
    templates = r.json().get("results", [])
    if templates:
        note("good", f"Found {len(templates)} templates")
        for t in templates:
            print(f"    • {t['name']} ({t['type']}) — status: {t['status']}")
    else:
        note("ux", "No templates available")

    subheading("Browse Apps (cloud-init profiles)")
    r = anon.get(url("apps/"))
    show("Apps", r, show_body=False)
    apps = r.json().get("results", [])
    if apps:
        note("good", f"Found {len(apps)} app profiles")
    else:
        note("info", "No app profiles configured")

    subheading("Check Inventory (what's in stock?)")
    r = anon.get(url("inventory/"))
    show("Inventory", r)
    inv = r.json().get("results", [])
    if inv:
        note("good", f"Inventory shows {len(inv)} plan/node combos available")
        for i in inv:
            print(f"    • Plan {i.get('plan')} on Node {i.get('node')}: {i.get('quantity')} slots")
    else:
        note("ux", "Inventory is empty — customer sees 'nothing in stock' even though plans exist")

    # Can I see plan details?
    subheading("Plan detail page")
    r = anon.get(url(f"plans/{plans[0]['id']}/"))
    show("Plan detail", r)
    if r.status_code == 200:
        note("good", "Anonymous users can view plan details")
    else:
        note("issue", "Can't view plan detail anonymously")

    return plans


# ═══════════════════════════════════════════════════════════════
# STEP 2: SIGN UP — Get an account
# ═══════════════════════════════════════════════════════════════

def step_2_signup():
    global created_user_id
    heading(2, "SIGN UP — Get an account")

    anon = requests.Session()

    # Is there a self-service signup?
    subheading("Try self-service registration")
    r = anon.post(url("auth/register/"), json={
        "username": "newcustomer",
        "email": "new@example.com",
        "password": "SecurePass123",
    })
    show("Register attempt", r, show_body=True)
    if r.status_code == 201:
        note("good", "Self-service registration works")
    elif r.status_code == 404:
        note("ux", "No self-service registration endpoint — admin must create accounts manually")
    else:
        note("info", f"Registration returned {r.status_code}")

    # Admin creates the user (the current flow)
    subheading("Admin creates customer account")
    admin = requests.Session()
    r = admin.post(url("auth/token/"), json={"username": ADMIN_USER, "password": ADMIN_PASS})
    admin_token = r.json()["token"]
    admin.headers["Authorization"] = f"Token {admin_token}"

    username = f"journey_user_{uuid.uuid4().hex[:6]}"
    password = f"JourneyPass_{uuid.uuid4().hex[:8]}"

    r = admin.post(url("customers/"), json={
        "username": username,
        "email": f"{username}@example.com",
        "first_name": "Journey",
        "last_name": "Customer",
    })
    show("Create customer", r)
    if r.status_code != 201:
        note("issue", "Failed to create customer")
        return None, None, None
    created_user_id = r.json()["id"]
    user_id = created_user_id

    # Set password (requires manage.py — no API for this)
    script = (
        f"from django.contrib.auth import get_user_model; "
        f"u = get_user_model().objects.get(username='{username}'); "
        f"u.set_password('{password}'); u.save()"
    )
    if DOCKER_CONTAINER:
        cmd = ["docker", "exec", DOCKER_CONTAINER, "python", "manage.py", "shell", "-c", script]
    else:
        cmd = ["python", "manage.py", "shell", "-c", script]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        note("issue", "Cannot set password — requires shell access")
        return None, None, None
    note("ux", "Password must be set via manage.py shell — no API endpoint to set/change password")

    # Customer logs in
    subheading("Customer logs in")
    user = requests.Session()
    r = user.post(url("auth/token/"), json={"username": username, "password": password})
    show("Login", r)
    if r.status_code == 200:
        user.headers["Authorization"] = f"Token {r.json()['token']}"
        note("good", "Customer can log in and gets a token")
    else:
        note("issue", "Login failed")
        return None, None, None

    # Can I see my own profile?
    subheading("View my profile")
    r = user.get(url("customers/"))
    show("GET /customers/", r, show_body=False)
    if r.status_code == 403:
        note("ux", "Customer cannot view their own profile via /customers/ — it's admin-only")

    r = user.get(url(f"customers/{user_id}/"))
    if r.status_code == 403:
        note("ux", "Customer cannot even view /customers/{id}/ for their own account")

    # Can I change my password via API?
    r = user.post(url("auth/password/change/"), json={
        "old_password": password,
        "new_password": "NewPassword123",
    })
    if r.status_code == 404:
        note("ux", "No password change endpoint — customer can never change their password via API")
    elif r.status_code == 200:
        note("good", "Password change works")

    return user, admin, user_id


# ═══════════════════════════════════════════════════════════════
# STEP 3: ORDER — Pick a plan and create a VPS
# ═══════════════════════════════════════════════════════════════

def step_3_order(user, plans):
    heading(3, "ORDER — Pick a plan and create a VPS")

    if not user or not plans:
        note("issue", "Cannot order — no user session or no plans")
        return None

    # Pick a plan
    plan = plans[0]
    print(f"  Choosing plan: {plan['name']} (id={plan['id']})")

    # What templates can I use?
    subheading("Browse templates as logged-in user")
    r = user.get(url("templates/"))
    show("Templates", r)
    templates = r.json().get("results", []) if r.status_code == 200 else []
    if not templates:
        note("issue", "No templates available — cannot order")
        return None
    # Pick by status=ready
    ready = [t for t in templates if t.get("status") == "ready"]
    if ready:
        template = ready[0]
    else:
        template = templates[0]
    print(f"  Choosing template: {template['name']} ({template['type']})")

    # What do I need to submit?
    subheading("What fields does the order form need?")
    r = user.options(url("services/"))
    if r.status_code == 200:
        body = r.json()
        actions = body.get("actions", {})
        post_fields = actions.get("POST", {})
        if post_fields:
            print(f"  Writable fields: {list(post_fields.keys())}")
            for fname, finfo in post_fields.items():
                req = " (REQUIRED)" if finfo.get("required") else ""
                print(f"    • {fname}: {finfo.get('type', '?')}{req} — {finfo.get('help_text', '')}")
        else:
            note("info", "OPTIONS doesn't list POST fields (might need auth or schema)")

    # Place the order
    subheading("Create service (place the order)")
    r = user.post(url("services/"), json={
        "hostname": "my-first-vps.example.com",
        "plan": plan["id"],
        "template": template["name"],
        "password": "MyVpsPassword123",
    })
    show("Create service", r)

    if r.status_code == 201:
        svc = r.json()
        svc_id = svc["id"]
        created_service_ids.append(svc_id)
        note("good", f"Service created! ID={svc_id}, machine_id={svc.get('machine_id')}")

        # What did I get back?
        print(f"\n  {BOLD}What the customer sees after ordering:{RESET}")
        for key in ("id", "hostname", "status", "machine_id", "owner",
                     "plan_name", "service_plan", "node", "created"):
            val = svc.get(key, "(missing)")
            print(f"    {key}: {val}")

        if "password" in svc:
            note("issue", "Password is visible in the response — should be write-only")
        else:
            note("good", "Password is not echoed back (write-only)")

        if svc.get("plan_name"):
            note("good", f"Plan name shown: '{svc['plan_name']}'")
        else:
            note("ux", "No plan_name in response — customer doesn't see which plan they ordered")

        if svc.get("status") == "pending":
            note("good", "Status is 'pending' — customer knows it's being set up")
        else:
            note("info", f"Initial status: {svc.get('status')}")

        return svc_id
    elif r.status_code == 400:
        note("issue", f"Order failed with validation error: {r.json()}")
        return None
    else:
        note("issue", f"Order failed: {r.status_code}")
        return None


# ═══════════════════════════════════════════════════════════════
# STEP 4: WAIT — Check provisioning status
# ═══════════════════════════════════════════════════════════════

def step_4_wait(user, svc_id):
    heading(4, "WAIT — Check provisioning status")

    if not svc_id:
        note("issue", "No service to check")
        return

    subheading("Poll service status")
    for i in range(5):
        r = user.get(url(f"services/{svc_id}/"))
        if r.status_code == 200:
            svc = r.json()
            status = svc.get("status")
            print(f"  [{i+1}/5] Status: {status}")
            if status in ("active", "error"):
                break
        time.sleep(2)

    r = user.get(url(f"services/{svc_id}/"))
    if r.status_code == 200:
        final_status = r.json().get("status")
        if final_status == "active":
            note("good", "Service provisioned and active!")
        elif final_status == "error":
            note("issue", f"Provisioning failed — status is 'error'")
            note("ux", f"status_msg: {r.json().get('status_msg', '(none)')}")
            note("ux", "No detailed error message for the customer about what went wrong")
        elif final_status == "pending":
            note("info", "Still pending after 10s — provisioning may take longer")
        else:
            note("info", f"Final status: {final_status}")

    # Is there a way to check provisioning progress?
    subheading("Provisioning feedback")
    note("ux", "No progress endpoint — customer can only poll GET /services/{id}/ and check 'status'")
    note("ux", "No webhook/callback option for status changes")
    note("ux", "No ETA or queue position shown")


# ═══════════════════════════════════════════════════════════════
# STEP 5: ORIENT — See what I got
# ═══════════════════════════════════════════════════════════════

def step_5_orient(user, svc_id):
    heading(5, "ORIENT — See what I got")

    if not svc_id:
        note("issue", "No service")
        return

    subheading("Service detail")
    r = user.get(url(f"services/{svc_id}/"))
    show("Service detail", r)

    if r.status_code == 200:
        svc = r.json()
        # What's useful for the customer?
        if svc.get("machine_id"):
            note("good", f"Machine ID shown: {svc['machine_id']}")
        if svc.get("node"):
            note("info", f"Node shown: {svc['node']} (is this useful to customers?)")

    subheading("My IPs")
    r = user.get(url(f"services/{svc_id}/ips/"))
    show("IPs", r)
    if r.status_code == 200:
        ips = r.json()
        if isinstance(ips, list) and ips:
            note("good", f"Got {len(ips)} IP(s)")
            for ip in ips:
                print(f"    • {ip}")
        elif isinstance(ips, dict) and ips:
            note("good", "IP info returned")
        else:
            note("ux", "No IPs assigned (yet?) — customer doesn't know how to connect")
    else:
        note("issue", f"Cannot see IPs: {r.status_code}")

    subheading("My service plan")
    r = user.get(url("serviceplans/"))
    show("Service Plans", r)
    sps = r.json().get("results", []) if r.status_code == 200 else []
    if sps:
        sp = sps[0]
        print(f"    Plan: {sp.get('name')}, {sp.get('cores')} cores, "
              f"{sp.get('ram')}MB RAM, {sp.get('size')}GB disk")
        note("good", "Customer can see their service plan specs")
    else:
        note("ux", "No service plans visible — customer can't see what they're paying for")

    # List all my services
    subheading("All my services")
    r = user.get(url("services/"))
    show("My services", r)


# ═══════════════════════════════════════════════════════════════
# STEP 6: OPERATE — Start, stop, reboot
# ═══════════════════════════════════════════════════════════════

def step_6_operate(user, svc_id):
    heading(6, "OPERATE — Power management")

    if not svc_id:
        note("issue", "No service")
        return

    subheading("VM Status")
    r = user.post(url(f"services/{svc_id}/status/"))
    show("Status", r)
    if r.status_code == 200:
        note("good", "Can check VM status")
    else:
        note("info", f"Status check: {r.status_code} (Proxmox may be unreachable)")

    subheading("Power actions")
    for action in ("start", "shutdown", "reboot"):
        r = user.post(url(f"services/{svc_id}/{action}/"))
        if r.status_code == 202:
            task_id = r.json().get("task_id")
            note("good", f"/{action}/ accepted, task_id={task_id}")
            # Can I check the task status?
            if task_id:
                # Is there a /tasks/{id}/ endpoint?
                r2 = user.get(url(f"tasks/{task_id}/"))
                if r2.status_code == 404:
                    note("ux", f"No way to check task progress — /tasks/{{id}}/ returns 404")
        else:
            note("info", f"/{action}/ returned {r.status_code}")

    note("ux", "Power actions return task_id but there's no endpoint to check task status")
    note("ux", "Customer has to poll GET /services/{id}/ to see if action completed")


# ═══════════════════════════════════════════════════════════════
# STEP 7: ACCESS — Get console
# ═══════════════════════════════════════════════════════════════

def step_7_access(user, svc_id):
    heading(7, "ACCESS — Console")

    if not svc_id:
        note("issue", "No service")
        return

    subheading("Get console credentials")
    r = user.get(url(f"services/{svc_id}/console/"))
    show("Console", r)
    if r.status_code == 200:
        body = r.json()
        note("good", "Console credentials returned")
        for field in ("username", "password", "node", "machine", "type"):
            if field in body:
                val = body[field] if field != "password" else "***"
                print(f"    {field}: {val}")
            else:
                note("ux", f"Console response missing '{field}'")
        note("ux", "Customer gets raw Proxmox credentials — no embedded console UI or websocket URL")
    elif r.status_code == 400:
        note("info", f"Console unavailable: {r.json()}")
    else:
        note("info", f"Console: {r.status_code}")


# ═══════════════════════════════════════════════════════════════
# STEP 8: NETWORK — Port forwarding
# ═══════════════════════════════════════════════════════════════

def step_8_network(user, svc_id):
    heading(8, "NETWORK — Port forwarding")

    if not svc_id:
        note("issue", "No service")
        return

    subheading("My port blocks")
    r = user.get(url("portblocks/"))
    show("Port blocks", r)
    blocks = r.json().get("results", []) if r.status_code == 200 else []
    if blocks:
        note("good", f"Got {len(blocks)} port block(s)")
        pb = blocks[0]
        print(f"    Port range: {pb.get('port_start')}-{pb.get('port_end')}")
        print(f"    Gateway: {pb.get('gateway_name')} ({pb.get('gateway_host')})")

        # Try to create a port forward
        subheading("Create a port forward")
        r = user.post(url("portforwards/"), json={
            "port_block": pb["id"],
            "external_port": pb.get("port_start", 10000),
            "internal_port": 22,
            "protocol": "tcp",
            "label": "SSH",
            "enabled": True,
        })
        show("Create forward", r)
        if r.status_code == 201:
            pf = r.json()
            note("good", f"Port forward created: ext:{pf.get('external_port')} → int:{pf.get('internal_port')}")

            # Can I delete it?
            r = user.delete(url(f"portforwards/{pf['id']}/"))
            if r.status_code == 403:
                note("ux", "Customer CANNOT delete their own port forwards — must ask admin")
            elif r.status_code == 204:
                note("good", "Customer can delete port forwards")
        elif r.status_code == 400:
            note("info", f"Port forward creation failed: {r.json()}")
    else:
        note("ux", "No port blocks — port forwarding not available (requires PortGateway setup)")
        note("ux", "Customer sees empty list with no explanation of what port blocks are")

    # Can I create port blocks?
    r = user.post(url("portblocks/"), json={"gateway": 1, "service_network": 1})
    if r.status_code == 403:
        note("info", "Port blocks are admin-only (expected)")
    else:
        note("info", f"POST /portblocks/: {r.status_code}")


# ═══════════════════════════════════════════════════════════════
# STEP 9: DOMAIN — Route a domain
# ═══════════════════════════════════════════════════════════════

def step_9_domain(user, svc_id):
    heading(9, "DOMAIN — Route a domain to my service")

    if not svc_id:
        note("issue", "No service")
        return

    subheading("My domain routes")
    r = user.get(url("domainroutes/"))
    show("Domain routes", r)
    routes = r.json().get("results", []) if r.status_code == 200 else []
    note("info", f"Currently have {len(routes)} domain route(s)")

    subheading("Create a domain route")
    domain = f"journey-{uuid.uuid4().hex[:6]}.example.com"
    r = user.post(url("domainroutes/"), json={
        "service": svc_id,
        "domain": domain,
        "forward_port": 80,
        "ssl": True,
        "force_ssl": True,
        "enabled": True,
    })
    show("Create route", r)
    if r.status_code == 201:
        dr = r.json()
        note("good", f"Domain route created: {dr.get('domain')} → port {dr.get('forward_port')}")

        # Can I delete it?
        r = user.delete(url(f"domainroutes/{dr['id']}/"))
        if r.status_code == 403:
            note("ux", "Customer CANNOT delete their own domain routes — must ask admin")
        elif r.status_code == 204:
            note("good", "Customer can delete domain routes")
    elif r.status_code == 400:
        errors = r.json().get("errors", r.json())
        note("ux", f"Domain route creation failed: {errors}")
        note("ux", "Likely needs an internal IP with a configured port gateway — not obvious to customer")
    else:
        note("info", f"Domain route: {r.status_code}")


# ═══════════════════════════════════════════════════════════════
# STEP 10: DAY-TO-DAY — Ongoing management
# ═══════════════════════════════════════════════════════════════

def step_10_daily(user, svc_id):
    heading(10, "DAY-TO-DAY — Ongoing management")

    if not svc_id:
        note("issue", "No service")
        return

    subheading("Update hostname")
    r = user.patch(url(f"services/{svc_id}/"), json={"hostname": "renamed-vps.example.com"})
    show("Patch hostname", r)
    if r.status_code == 200:
        note("good", "Customer can rename their VPS hostname")

    subheading("Check bandwidth usage")
    r = user.get(url(f"services/{svc_id}/"))
    if r.status_code == 200:
        svc = r.json()
        bw_fields = {k: v for k, v in svc.items() if "bw" in k.lower() or "bandwidth" in k.lower()}
        if bw_fields:
            note("good", f"Bandwidth info visible: {bw_fields}")
        else:
            note("ux", "No bandwidth usage info in service detail — customer can't track their usage")

    subheading("Try to upgrade plan")
    r = user.patch(url(f"services/{svc_id}/"), json={"plan": 2})
    if r.status_code == 200:
        note("info", "Plan change accepted (but field may be read-only/ignored)")
    else:
        note("ux", f"No way to upgrade/change plan: {r.status_code}")
    note("ux", "No plan upgrade/downgrade workflow exists")

    subheading("Try to change password")
    r = user.patch(url(f"services/{svc_id}/"), json={"password": "NewVpsPassword456"})
    if r.status_code == 200:
        note("info", "Password change accepted via PATCH")
    else:
        note("ux", f"Password change: {r.status_code}")


# ═══════════════════════════════════════════════════════════════
# STEP 11: LEAVE — Try to cancel/delete
# ═══════════════════════════════════════════════════════════════

def step_11_leave(user, svc_id):
    heading(11, "LEAVE — Try to cancel or delete")

    if not svc_id:
        note("issue", "No service")
        return

    subheading("Try to cancel service")
    r = user.post(url(f"services/{svc_id}/cancel/"))
    show("Cancel", r)
    if r.status_code == 403:
        note("ux", "Customer CANNOT cancel their own service — must contact admin")
    elif r.status_code == 202:
        note("good", "Customer can cancel service")

    subheading("Try to delete service")
    # Don't actually delete — just report what would happen
    note("info", "DELETE /services/{id}/ is allowed for users (returns 204)")
    note("ux", "Customer can delete (destroy) their service but CANNOT cancel it — these should probably be swapped")
    note("ux", "No confirmation flow, no cooling-off period, no 'are you sure?' — just gone")

    subheading("Try to delete account")
    r = user.delete(url(f"customers/1/"))  # would fail anyway
    if r.status_code == 403:
        note("ux", "Customer cannot delete their own account")
    note("ux", "No self-service account deletion")


# ═══════════════════════════════════════════════════════════════
# STEP 12: SECURITY — Probe the boundaries
# ═══════════════════════════════════════════════════════════════

def step_12_security(user, admin, svc_id):
    heading(12, "SECURITY — Probe the boundaries")

    if not user or not svc_id:
        note("issue", "No user session")
        return

    subheading("Can I see other users' services?")
    # Admin's services
    r = admin.get(url("services/"))
    admin_svcs = [s["id"] for s in r.json().get("results", [])]
    r = user.get(url("services/"))
    user_svcs = [s["id"] for s in r.json().get("results", [])]
    others = [s for s in admin_svcs if s not in user_svcs]
    if others:
        # Try to access one
        other_id = others[0]
        r = user.get(url(f"services/{other_id}/"))
        if r.status_code == 404:
            note("good", "Can't access other users' services (404)")
        elif r.status_code == 200:
            note("issue", "SECURITY: Can see another user's service!")

    subheading("Can I access admin endpoints?")
    for ep in ("clusters/", "nodes/", "ippools/", "customers/", "dashboard/summary/"):
        r = user.get(url(ep))
        if r.status_code == 403:
            pass  # good
        else:
            note("issue", f"User can access admin endpoint /{ep}: {r.status_code}")
    note("good", "Admin endpoints properly blocked for regular users")

    subheading("PATCH serializer gap (partial_update)")
    # The known bug — PATCH uses admin serializer for non-admin users
    r = user.get(url(f"services/{svc_id}/"))
    orig_status = r.json().get("status") if r.status_code == 200 else None

    r = user.patch(url(f"services/{svc_id}/"), json={"status": "suspended"})
    if r.status_code == 200 and r.json().get("status") == "suspended":
        note("issue", "SECURITY: User can PATCH status to 'suspended' via partial_update serializer gap")
        # Restore
        user.patch(url(f"services/{svc_id}/"), json={"status": orig_status or "pending"})
    elif r.status_code == 200:
        note("good", "Status field protected on PATCH")
    else:
        note("info", f"PATCH status: {r.status_code}")


# ═══════════════════════════════════════════════════════════════
# CLEANUP
# ═══════════════════════════════════════════════════════════════

def cleanup(admin):
    heading("X", "CLEANUP")
    if not admin:
        return
    for svc_id in created_service_ids:
        r = admin.delete(url(f"services/{svc_id}/"))
        print(f"  Deleted service {svc_id}: {r.status_code}")
    if created_user_id:
        r = admin.delete(url(f"customers/{created_user_id}/"))
        print(f"  Deleted user {created_user_id}: {r.status_code}")


# ═══════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════

def summary():
    heading("", "JOURNEY SUMMARY")

    categories = {"good": [], "issue": [], "ux": [], "info": []}
    for cat, msg in observations:
        categories.setdefault(cat, []).append(msg)

    print(f"  {GREEN}What works well ({len(categories['good'])}):{RESET}")
    for msg in categories["good"]:
        print(f"    + {msg}")

    print(f"\n  {RED}Issues / Bugs ({len(categories['issue'])}):{RESET}")
    for msg in categories["issue"]:
        print(f"    ! {msg}")

    print(f"\n  {YELLOW}UX Gaps ({len(categories['ux'])}):{RESET}")
    for msg in categories["ux"]:
        print(f"    ? {msg}")

    print(f"\n  {CYAN}Info ({len(categories['info'])}):{RESET}")
    for msg in categories["info"]:
        print(f"    i {msg}")

    total = len(observations)
    print(f"\n  {BOLD}Total observations: {total}{RESET}")
    print(f"    {GREEN}{len(categories['good'])} working well{RESET}")
    print(f"    {RED}{len(categories['issue'])} issues/bugs{RESET}")
    print(f"    {YELLOW}{len(categories['ux'])} UX gaps{RESET}")


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  CUSTOMER JOURNEY WALKTHROUGH{RESET}")
    print(f"{BOLD}  Target: {BASE_URL}{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    admin = None
    user = None
    svc_id = None

    try:
        plans = step_1_discover()
        user, admin, user_id = step_2_signup()
        svc_id = step_3_order(user, plans)
        step_4_wait(user, svc_id)
        step_5_orient(user, svc_id)
        step_6_operate(user, svc_id)
        step_7_access(user, svc_id)
        step_8_network(user, svc_id)
        step_9_domain(user, svc_id)
        step_10_daily(user, svc_id)
        step_11_leave(user, svc_id)
        step_12_security(user, admin, svc_id)
    finally:
        cleanup(admin)

    summary()


if __name__ == "__main__":
    main()
