#!/usr/bin/env python3

"""
Production-Grade IaC with Terraform - Coaching-Style Grader (Rich terminal UI)

This grader validates the course one TODO at a time, always starting from
TODO 01, and stops at the first incomplete one - even though TODO 01, 02,
and 03 are already solved for you in this folder, it re-checks them live
every run, so you always see real, current proof that nothing earlier
broke, not a cached checkmark.

A single `terraform apply` evaluates every output in main.tf at once, so a
broken later TODO could otherwise fail the whole apply and make an earlier,
already-correct TODO look broken too. `-target` can't fix this - it only
addresses resources, data sources, and module calls, never locals or
outputs (this course has none of the former yet). Instead, every check
below runs against a disposable scratch copy of this lab, with everything
after that TODO's own marker physically cut out of main.tf first (see
_scoped_workdir()) - the student's real terraform.tfstate in this
directory is never touched by grading.

TODO 03 is additionally checked by temporarily breaking a real cross-file
reference (environments/staging.json disabling a zone role, "gust", that
was never defined in the service intent) and confirming terraform apply
fails, then restoring the file and confirming a clean apply succeeds.

Requires the `terraform` CLI (>= 1.5) to be installed and on PATH.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.align import Align
from rich.text import Text
from rich.rule import Rule
from rich.syntax import Syntax
from rich.bar import Bar

ROOT = Path(__file__).parent
INTENT_FILE = ROOT / "intent" / "branch_firewall_service.json"
ENVIRONMENTS_DIR = ROOT / "environments"
SITES_DIR = ROOT / "sites"
STAGING_FILE = ENVIRONMENTS_DIR / "staging.json"

# Cutting main.tf at one of these markers, when grading an earlier TODO,
# drops everything from that later TODO onward - see _scoped_workdir().
#
# These point at the real banner comments already in THIS folder's
# main.tf - not an invented marker. Each folder's grading.py is its own
# file, hand-written against that folder's own main.tf, so the marker
# just has to match what's actually there right now: TODO 03 is already
# solved in this folder, so its section starts with
# "# TODO 03 - already solved in this folder.", and TODO 04 is the
# current student work area, so its section starts with
# "# STUDENT WORK AREA - TODO 04". An earlier version of this grader
# reused TODO 03's marker text unchanged from TODO-03's own grading.py
# (where TODO 03 was still the student work area) - that string doesn't
# exist in this file, so truncation silently never happened. The
# _scoped_workdir() assert below now fails loudly if a marker like this
# is ever wrong again, instead of silently grading against the wrong
# scope.
TODO_03_MARKER = "# TODO 03 - already solved in this folder."
TODO_04_MARKER = "# STUDENT WORK AREA - TODO 04"

# The "provided" output block after TODO 04's own work area
# (output "resolved_zones") references local.site_zones, which doesn't
# exist until TODO 04 is actually solved. Before that, referencing it is
# a completely normal, expected state - not a syntax error - so
# ensure_valid() validates only up through here, never that trailing
# output. See ensure_valid() for why this matters.
CURRENT_TODO_END_MARKER = "# END STUDENT WORK AREA - TODO 04"

console = Console(markup=False, highlight=False)

BOLD = "bold "
DIM = "dim"
RED = "red"
GREEN = "green"
YELLOW = "yellow"
CYAN = "cyan"

INTERACTIVE_MODE = os.environ.get("CAPSTONE_INTERACTIVE", "1") != "0"

COURSE_TOTAL_TODOS = 12
TOTAL_TODOS = 4

TODO_NAMES = {
    1: "Author the Declarative Network Intent",
    2: "Load & Parse Structured Inputs",
    3: "Run Pre-Flight Validation",
    4: "Build Environment- and Site-Aware Locals",
}

SUCCESS_MESSAGES = {
    1: "intent/branch_firewall_service.json captures the business requirements correctly.",
    2: "main.tf loads the service intent, both environments, and all 3 sites correctly.",
    3: "Pre-flight validation is running and correctly catches a bad cross-file reference.",
    4: "Every site resolves to the correct zones, with each environment's overrides correctly applied.",
}

FAIL_MESSAGES = {
    1: "The pipeline cannot continue because the declarative network intent has not been authored correctly yet.",
    2: "The pipeline cannot continue because the structured inputs have not been loaded and parsed correctly yet.",
    3: "The pipeline cannot continue because pre-flight validation is not actually being executed.",
    4: "The pipeline cannot continue because the per-site resolved zones have not been built correctly yet.",
}

HINTS = {
    1: "Create intent/branch_firewall_service.json by hand. Match the shape in TASK.md (tenant, service, zones: [{role, name, enabled}]) using the business requirements table exactly - JSON, not YAML.",
    2: "Use jsondecode(file(\"${path.module}/<path>\")) once per file - one call for the intent file, one for each of the 2 environment files, one for each of the 3 site files. Same pattern, 6 times over.",
    3: "First build valid_zone_roles with [for z in local.service_intent.zones : z.role]. Then build disabled_zones_flat with flatten([for env in local.environments : env.disabled_zones]). Then write one output block whose precondition condition is alltrue([for zone_role in local.disabled_zones_flat : contains(local.valid_zone_roles, zone_role)]) - true only when every disabled zone really exists.",
    4: "Build zone_names_by_role and enabled_zone_roles straight from local.service_intent.zones first. Then site_zone_roles: for each site, filter enabled_zone_roles to roles NOT in local.environments[site.environment].disabled_zones. Then site_zones: for each site, map site_zone_roles[site_id] to { role, name = zone_names_by_role[role], id = site.zone_ids[role] } objects.",
}

SOLUTIONS = {
    1: '''{
  "tenant": "Meridian Retail",
  "service": "branch-firewall-standard",
  "zones": [
    { "role": "corp", "name": "RTL-CORP-FW", "enabled": true },
    { "role": "voice", "name": "RTL-VOICE-FW", "enabled": true },
    { "role": "pos", "name": "RTL-POS-FW", "enabled": true },
    { "role": "guest", "name": "RTL-GUEST-FW", "enabled": true },
    { "role": "quarantine", "name": "RTL-QUARANTINE-FW", "enabled": false }
  ]
}''',
    2: '''locals {
  service_intent = jsondecode(file("${path.module}/intent/branch_firewall_service.json"))

  environments = {
    prod    = jsondecode(file("${path.module}/environments/prod.json"))
    staging = jsondecode(file("${path.module}/environments/staging.json"))
  }

  sites = {
    rdu01 = jsondecode(file("${path.module}/sites/rdu01.json"))
    aus02 = jsondecode(file("${path.module}/sites/aus02.json"))
    sea03 = jsondecode(file("${path.module}/sites/sea03.json"))
  }
}''',
    3: '''locals {
  valid_zone_roles = [for z in local.service_intent.zones : z.role]

  disabled_zones_flat = flatten([
    for env in local.environments : env.disabled_zones
  ])
}

output "preflight_ok" {
  value = true

  precondition {
    condition     = alltrue([
      for zone_role in local.disabled_zones_flat : contains(local.valid_zone_roles, zone_role)
    ])
    error_message = "A disabled zone role isn't defined in the service intent."
  }
}''',
    4: '''locals {
  zone_names_by_role = {
    for z in local.service_intent.zones : z.role => z.name
  }

  enabled_zone_roles = [
    for z in local.service_intent.zones : z.role if z.enabled
  ]

  site_zone_roles = {
    for site_id, site in local.sites :
    site_id => [
      for role in local.enabled_zone_roles :
      role if !contains(local.environments[site.environment].disabled_zones, role)
    ]
  }

  site_zones = {
    for site_id, site in local.sites :
    site_id => [
      for role in local.site_zone_roles[site_id] : {
        role = role
        name = local.zone_names_by_role[role]
        id   = site.zone_ids[role]
      }
    ]
  }
}''',
}

EXPECTED = {
    1: "intent/branch_firewall_service.json should exist with tenant: \"Meridian Retail\", service: \"branch-firewall-standard\", and exactly the 5 zone definitions specified in TASK.md.",
    2: "terraform output -json loaded_inputs should return service_intent matching intent/branch_firewall_service.json, environments with both \"prod\" and \"staging\" keys matching environments/*.json, and sites with \"rdu01\", \"aus02\", and \"sea03\" keys matching sites/*.json.",
    3: "With an unknown zone role temporarily injected into environments/staging.json's disabled_zones, terraform apply should fail. With the file restored, terraform apply should succeed.",
    4: "terraform output -json resolved_zones should return, for each site, the intent's enabled zones minus that site's own environment's disabled_zones, each with the right name and the right site-specific id - see TASK.md's Worked Example for the exact expected values.",
}

PROBLEMS = {
    1: "The declarative network intent file is missing, malformed, or does not match the required business requirements.",
    2: "main.tf's locals block is missing, fails to evaluate, or does not load service_intent, environments, and sites correctly from disk.",
    3: "Pre-flight validation did not catch an intentionally broken cross-file reference, or it fails even when every disabled zone is valid.",
    4: "resolved_zones is missing, fails to evaluate, or does not match the correct per-site zone list for at least one site.",
}


# -----------------------------------------------------------------------------
# Terraform helpers
# -----------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Offline provider mirror support
# ---------------------------------------------------------------------------
#
# terraform init needs to resolve the hashicorp/aws provider before it can do
# anything at all - normally fetched from registry.terraform.io. In a
# classroom with no internet access, that single network dependency would
# block every TODO from TODO 02 onward, even ones that never touch AWS
# themselves. If a pre-populated local mirror exists at this course's own
# root (see PROVIDER_MIRROR_DIR - populated once, with real internet, via
# `terraform providers mirror`; see OFFLINE_SETUP.md at the course root),
# every terraform invocation below is transparently redirected to read the
# provider from that mirror instead of the network, via a small,
# dynamically-generated CLI config file. This is generated at runtime
# (never a static, committed file) because a filesystem_mirror path must be
# absolute, and this course folder can be copied to different machines at
# different absolute paths. If no mirror exists at that path, this silently
# changes nothing - terraform still resolves providers from the network
# exactly as it always has.
PROVIDER_MIRROR_DIR = ROOT.parent / ".terraform-providers-mirror"
_offline_cli_config_path = None


def _offline_cli_config_env():
    """Returns a copy of the current environment, with TF_CLI_CONFIG_FILE
    pointing at a freshly-written CLI config that restricts hashicorp/aws
    provider installation to PROVIDER_MIRROR_DIR - or the environment
    unchanged if that mirror directory doesn't exist. Memoized per process
    so the tiny config file is written at most once per grading run."""
    global _offline_cli_config_path
    env = dict(os.environ)
    if not PROVIDER_MIRROR_DIR.is_dir():
        return env
    if _offline_cli_config_path is None:
        config_path = PROVIDER_MIRROR_DIR.parent / ".offline-provider-mirror.tfrc"
        config_path.write_text(
            'provider_installation {\n'
            '  filesystem_mirror {\n'
            '    path    = "%s"\n'
            '    include = ["registry.terraform.io/hashicorp/aws"]\n'
            '  }\n'
            '  direct {\n'
            '    exclude = ["registry.terraform.io/hashicorp/aws"]\n'
            '  }\n'
            '}\n' % str(PROVIDER_MIRROR_DIR.resolve()),
            encoding="utf-8",
        )
        _offline_cli_config_path = config_path
    env["TF_CLI_CONFIG_FILE"] = str(_offline_cli_config_path)
    return env


def run_terraform(cwd, *args):
    """Run a terraform command in the given directory. Returns
    (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["terraform", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=120,
            env=_offline_cli_config_env(),
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return 127, "", "terraform CLI not found on PATH. Install Terraform >= 1.5 to run this grader."
    except subprocess.TimeoutExpired:
        return 124, "", "terraform command timed out."


_SKIP_COPY = {".terraform", "terraform.tfstate", "terraform.tfstate.backup", "__pycache__", ".terraform.lock.hcl"}


def _scoped_workdir(truncate_before=None):
    """Copy this lab's files into a fresh temp directory, optionally
    cutting main.tf short right before a marker string. See the module
    docstring for why this is necessary instead of -target."""
    tmp = Path(tempfile.mkdtemp(prefix="tf_grade_"))
    for item in ROOT.iterdir():
        if item.name in _SKIP_COPY:
            continue
        dest = tmp / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    if truncate_before:
        main_tf = tmp / "main.tf"
        text = main_tf.read_text(encoding="utf-8")
        idx = text.find(truncate_before)
        # If this ever fires, it's a grading.py bug (a marker that no
        # longer matches main.tf), not a student mistake - fail loudly
        # instead of silently skipping truncation and grading against
        # the wrong scope.
        assert idx != -1, f"grading.py bug: truncation marker {truncate_before!r} not found in main.tf"
        main_tf.write_text(text[:idx], encoding="utf-8")

    return tmp


def apply_and_read_output(name, truncate_before=None):
    """Run init + apply in a scoped scratch copy of this lab, then read
    one output back. Returns the parsed output value, or None if
    init/apply/output failed for any reason."""
    workdir = _scoped_workdir(truncate_before=truncate_before)
    try:
        rc, _, _ = run_terraform(workdir, "init", "-input=false", "-no-color")
        if rc != 0:
            return None
        rc, _, _ = run_terraform(workdir, "apply", "-auto-approve", "-input=false", "-no-color")
        if rc != 0:
            return None
        rc, stdout, _ = run_terraform(workdir, "output", "-json", name)
        if rc != 0:
            return None
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return None
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def apply_in_scoped_copy(truncate_before=None):
    """Copy the lab (with whatever is currently on disk, including any
    temporary edit a caller just made to a source .json file) into a
    scratch directory and run init + apply there. Returns
    (returncode, stdout, stderr). Used by check_todo_3, which needs to
    see the real, current apply result - not just one output value -
    without ever touching the student's real terraform.tfstate, and
    without a broken TODO 04 affecting the result."""
    workdir = _scoped_workdir(truncate_before=truncate_before)
    try:
        rc, out, err = run_terraform(workdir, "init", "-input=false", "-no-color")
        if rc != 0:
            return rc, out, err
        return run_terraform(workdir, "apply", "-auto-approve", "-input=false", "-no-color")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


_validate_checked = False
_validate_result = (True, "")


def ensure_valid():
    """`terraform validate` checks that main.tf is structurally sound
    HCL, WITHOUT evaluating whether any precondition's condition is
    actually true. That makes it the right tool to catch a genuine
    syntax mistake before ever attributing a failure to a specific TODO:
    a syntax error anywhere in the file stops every TODO from running at
    all, so it isn't any one TODO's fault.

    This validates a scoped copy truncated right after TODO 04's own
    END marker - NOT the raw ROOT directory - because the real ROOT
    file's last output ("resolved_zones") references local.site_zones,
    which the student hasn't written yet on a fresh, unsolved TODO 04.
    Validating the full file would call that completely normal starting
    state "main.tf is not valid Terraform configuration", which is
    wrong and confusing - it isn't invalid, TODO 04 just isn't done. Any
    syntax mistake the student actually makes while writing TODO 04 is
    still inside the truncated copy (their code comes before the END
    marker), so this still catches real syntax errors just fine.

    Memoized - the file doesn't change between calls within one
    grading.py run except inside check_todo_3's own temporary edits,
    which touch a .json data file, never main.tf."""
    global _validate_checked, _validate_result
    if _validate_checked:
        return _validate_result
    _validate_checked = True

    workdir = _scoped_workdir(truncate_before=CURRENT_TODO_END_MARKER)
    try:
        rc, init_out, init_err = run_terraform(workdir, "init", "-input=false", "-no-color")
        if rc != 0:
            _validate_result = (False, (init_err or init_out or "terraform init failed").strip())
            return _validate_result

        rc, stdout, stderr = run_terraform(workdir, "validate", "-no-color", "-json")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    if rc == 0:
        _validate_result = (True, "")
        return _validate_result

    try:
        diagnostics = json.loads(stdout).get("diagnostics", [])
        text = "\n".join(
            f"{d.get('summary', '')}: {d.get('detail', '')}".strip(": ")
            for d in diagnostics
        )
    except (json.JSONDecodeError, ValueError, AttributeError):
        text = stderr or stdout
    _validate_result = (False, text or "main.tf is not valid Terraform configuration.")
    return _validate_result


# -----------------------------------------------------------------------------
# Presentation helpers (Rich)
# -----------------------------------------------------------------------------

def c(text, style):
    return Text(str(text), style=style.strip())


def todo_label(number):
    return f"TODO {number:02d}"


def banner(title, color=CYAN):
    console.print()
    console.print(
        Panel(
            Align.center(Text(str(title), style=f"bold {color}")),
            border_style=color,
            padding=(0, 2),
        )
    )
    console.print()


def divider():
    console.print()
    console.print(Rule(style="grey50"))
    console.print()


def pause(message):
    if INTERACTIVE_MODE:
        try:
            input(f"\n{message}")
        except EOFError:
            pass


def section(title, value, color):
    body = Text()
    lines = str(value).splitlines()
    for i, line in enumerate(lines):
        body.append(line)
        if i < len(lines) - 1:
            body.append("\n")
    console.print(Panel(body, title=title, title_align="left", border_style=color, padding=(0, 1)))
    console.print()


def render_bar(completed, total):
    total = max(total, 1)
    return Bar(size=total, begin=0, end=completed, color="green3", bgcolor="grey27", width=40)


# -----------------------------------------------------------------------------
# TODO checks
# -----------------------------------------------------------------------------

def check_todo_1():
    if not INTENT_FILE.exists():
        return False

    try:
        data = json.loads(INTENT_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False

    if not isinstance(data, dict):
        return False
    if data.get("tenant") != "Meridian Retail":
        return False
    if data.get("service") != "branch-firewall-standard":
        return False

    zones = data.get("zones")
    if not isinstance(zones, list):
        return False

    expected = {
        "corp": ("RTL-CORP-FW", True),
        "voice": ("RTL-VOICE-FW", True),
        "pos": ("RTL-POS-FW", True),
        "guest": ("RTL-GUEST-FW", True),
        "quarantine": ("RTL-QUARANTINE-FW", False),
    }

    actual = {}
    for zone in zones:
        if not isinstance(zone, dict):
            return False
        actual[zone.get("role")] = (zone.get("name"), zone.get("enabled"))

    for role, expected_values in expected.items():
        if actual.get(role) != expected_values:
            return False

    return True


def _load_source_json(directory, filename):
    path = directory / filename
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def check_todo_2():
    """Runs in a scratch copy with everything from TODO 03 onward cut
    out of main.tf first, so this check's result depends only on TODO
    01 and TODO 02's own code."""
    loaded = apply_and_read_output("loaded_inputs", truncate_before=TODO_03_MARKER)
    if not isinstance(loaded, dict):
        return False

    expected_intent = json.loads(INTENT_FILE.read_text(encoding="utf-8"))
    if loaded.get("service_intent") != expected_intent:
        return False

    environments = loaded.get("environments")
    if not isinstance(environments, dict):
        return False
    for env_name in ("prod", "staging"):
        expected_env = _load_source_json(ENVIRONMENTS_DIR, f"{env_name}.json")
        if expected_env is None or environments.get(env_name) != expected_env:
            return False

    sites = loaded.get("sites")
    if not isinstance(sites, dict):
        return False
    for site_id in ("rdu01", "aus02", "sea03"):
        expected_site = _load_source_json(SITES_DIR, f"{site_id}.json")
        if expected_site is None or sites.get(site_id) != expected_site:
            return False

    return True


def check_todo_3():
    """Only called once TODO 01 and TODO 02 are already confirmed correct -
    see compute_statuses(). Temporarily breaks the REAL
    environments/staging.json on disk, always restores it in a finally
    block even if something raises. Truncated at TODO_04_MARKER so a
    broken TODO 04 can't affect this result either."""
    if not STAGING_FILE.exists():
        return False

    original = STAGING_FILE.read_text(encoding="utf-8")
    try:
        data = json.loads(original)
        broken = dict(data)
        broken["disabled_zones"] = list(data.get("disabled_zones", [])) + ["gust"]
        STAGING_FILE.write_text(json.dumps(broken, indent=2) + "\n", encoding="utf-8")

        broken_rc, _, _ = apply_in_scoped_copy(truncate_before=TODO_04_MARKER)
        broke_correctly = broken_rc != 0
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    finally:
        STAGING_FILE.write_text(original, encoding="utf-8")

    if not broke_correctly:
        return False

    clean_rc, _, _ = apply_in_scoped_copy(truncate_before=TODO_04_MARKER)
    return clean_rc == 0


def _compute_expected_site_zones():
    """Independently computes the correct answer straight from the
    source JSON files - never by reading main.tf's source, and never by
    trusting whatever the student's own locals produced."""
    intent = json.loads(INTENT_FILE.read_text(encoding="utf-8"))
    zone_names_by_role = {z["role"]: z["name"] for z in intent["zones"]}
    enabled_roles = [z["role"] for z in intent["zones"] if z["enabled"]]

    environments = {}
    for env_name in ("prod", "staging"):
        env = _load_source_json(ENVIRONMENTS_DIR, f"{env_name}.json")
        if env is None:
            return None
        environments[env_name] = env

    result = {}
    for site_id in ("rdu01", "aus02", "sea03"):
        site = _load_source_json(SITES_DIR, f"{site_id}.json")
        if site is None:
            return None
        disabled = set(environments[site["environment"]]["disabled_zones"])
        roles = [r for r in enabled_roles if r not in disabled]
        result[site_id] = [
            {"role": r, "name": zone_names_by_role[r], "id": site["zone_ids"][r]}
            for r in roles
        ]
    return result


def check_todo_4():
    """Runs against the full, untruncated file - TODO 04 is the last
    TODO in this folder, so there's nothing later to cut away."""
    resolved = apply_and_read_output("resolved_zones")
    if not isinstance(resolved, dict):
        return False

    expected = _compute_expected_site_zones()
    if expected is None:
        return False

    if set(resolved.keys()) != set(expected.keys()):
        return False

    def normalize(zone_list):
        if not isinstance(zone_list, list):
            return None
        try:
            return sorted((z.get("role"), z.get("name"), z.get("id")) for z in zone_list)
        except (AttributeError, TypeError):
            return None

    for site_id, expected_zones in expected.items():
        if normalize(resolved.get(site_id)) != normalize(expected_zones):
            return False

    return True


def compute_statuses():
    valid, _ = ensure_valid()
    if not valid:
        return None

    statuses = {1: check_todo_1()}
    statuses[2] = check_todo_2() if statuses[1] else False
    statuses[3] = check_todo_3() if (statuses[1] and statuses[2]) else False
    statuses[4] = check_todo_4() if (statuses[1] and statuses[2] and statuses[3]) else False
    return statuses


def first_failed_todo(statuses):
    for number in range(1, TOTAL_TODOS + 1):
        if not statuses[number]:
            return number
    return None


# -----------------------------------------------------------------------------
# TODO progress / feedback / summary
# -----------------------------------------------------------------------------

def print_todo_details(number, statuses):
    if number == 1:
        console.print("[1] Authoring the declarative network intent...")
        if statuses[number]:
            console.print("intent/branch_firewall_service.json matches the required business requirements.")
    elif number == 2:
        console.print("[2] Loading and parsing structured inputs...")
        if statuses[number]:
            console.print("service_intent, environments, and sites all loaded and match the source files.")
    elif number == 3:
        console.print("[3] Running pre-flight validation...")
        if statuses[number]:
            console.print("Injected an unknown zone role (\"gust\") into environments/staging.json:")
            console.print("  terraform apply -> failed as expected")
            console.print("Restored environments/staging.json:")
            console.print("  terraform apply -> succeeded, pre-flight validation passed")
    elif number == 4:
        console.print("[4] Building environment- and site-aware locals...")
        if statuses[number]:
            expected = _compute_expected_site_zones() or {}
            for site_id in ("rdu01", "aus02", "sea03"):
                roles = ", ".join(z["role"] for z in expected.get(site_id, []))
                console.print(f"  {site_id} -> {roles}")


def print_todo_progress(statuses):
    banner("TODO PROGRESS")

    for number in range(1, TOTAL_TODOS + 1):
        console.print(c(f"{todo_label(number)} - {TODO_NAMES[number]}", f"{BOLD}{CYAN}"))
        console.print(Rule(style=CYAN))
        console.print()

        print_todo_details(number, statuses)
        console.print()

        if statuses[number]:
            console.print(c(f"✓ {todo_label(number)} Complete", f"{BOLD}{GREEN}"))
            console.print(c(SUCCESS_MESSAGES[number], GREEN))
            if number < TOTAL_TODOS:
                console.print()
                console.print(c(f"Moving to {todo_label(number + 1)}...", DIM))
            divider()
            continue

        console.print(c(f"✗ {todo_label(number)} Not Complete", f"{BOLD}{YELLOW}"))
        console.print()
        console.print(c(FAIL_MESSAGES[number], YELLOW))
        console.print()
        console.print(c("Proceeding to detailed feedback...", DIM))
        divider()
        break


def feedback(failed):
    banner("FEEDBACK")

    if failed is None:
        for number in range(1, TOTAL_TODOS + 1):
            console.print(Text.assemble(("[PASS] ", "bold green"), (f"{todo_label(number)} - {TODO_NAMES[number]}", "bold")))
        return

    for number in range(1, failed):
        console.print(Text.assemble(("[PASS] ", "bold green"), (f"{todo_label(number)} - {TODO_NAMES[number]}", "bold")))

    console.print()
    console.print(Text.assemble(("[FAIL] ", "bold red"), (f"{todo_label(failed)} - {TODO_NAMES[failed]}", "bold")))
    console.print()

    section("Problem", PROBLEMS[failed], YELLOW)
    section("Expected", EXPECTED[failed], CYAN)
    section("Hint", HINTS[failed], GREEN)

    console.print("Type S and press Enter to reveal the solution, or press Enter to skip: ", end="")
    try:
        answer = input().strip().lower()
    except EOFError:
        answer = ""

    if answer == "s":
        console.print()
        lexer = "json" if failed == 1 else "hcl"
        syntax = Syntax(SOLUTIONS[failed], lexer, theme="ansi_dark", line_numbers=False, word_wrap=True)
        console.print(Panel(syntax, title="Solution", title_align="left", border_style=GREEN, padding=(0, 1)))
        console.print()


def lab_summary(statuses):
    completed = sum(1 for number in range(1, TOTAL_TODOS + 1) if statuses[number])
    failed = first_failed_todo(statuses)
    percent = int((completed / TOTAL_TODOS) * 100)

    if failed is None:
        banner(f"{todo_label(TOTAL_TODOS)} COMPLETE - LAB {TOTAL_TODOS} OF {COURSE_TOTAL_TODOS} DONE", GREEN)
        console.print(c("Progress", f"{BOLD}{CYAN}"))
        console.print(Rule(style=CYAN))
        console.print(render_bar(completed, TOTAL_TODOS))
        console.print(f"  {percent}% Complete ({completed} of {TOTAL_TODOS} TODOs in this lab)")
        console.print()
        console.print(f"  {todo_label(TOTAL_TODOS)} - {TODO_NAMES[TOTAL_TODOS]} - is complete.")
        console.print("  Move on to the next lab; everything done here will")
        console.print("  already be done for you there.")
        console.print()
        return

    banner("LAB NOT COMPLETE", YELLOW)
    console.print(c("Progress", f"{BOLD}{CYAN}"))
    console.print(Rule(style=CYAN))
    console.print(render_bar(completed, TOTAL_TODOS))
    console.print(f"  {percent}% Complete ({completed} of {TOTAL_TODOS} TODOs)")
    console.print()

    console.print(c("Completed", f"{BOLD}{GREEN}"))
    console.print(Rule(style=GREEN))
    if completed == 0:
        console.print("  No TODOs completed yet.")
    else:
        for number in range(1, failed):
            console.print(f"  ✓ {todo_label(number)} - {TODO_NAMES[number]}")
    console.print()

    console.print(c("Remaining", f"{BOLD}{YELLOW}"))
    console.print(Rule(style=YELLOW))
    for number in range(failed, TOTAL_TODOS + 1):
        console.print(f"  ✗ {todo_label(number)} - {TODO_NAMES[number]}")
    console.print()

    console.print(c("Next Step", f"{BOLD}{CYAN}"))
    console.print(Rule(style=CYAN))
    console.print(f"  Complete {todo_label(failed)} and run:")
    console.print()
    console.print("  python grading.py")
    console.print()


def print_invalid_config():
    _, detail = ensure_valid()
    banner("main.tf is not valid Terraform configuration", YELLOW)
    console.print(c(
        "terraform validate could not confirm main.tf is well-formed - this is a "
        "syntax or structural error somewhere in the file, not a specific TODO "
        "being incomplete. Fix this error, then run python grading.py again.",
        YELLOW,
    ))
    console.print()
    section("terraform validate's diagnostics", detail.strip() or "(no details returned)", RED)


def main():
    banner("Production-Grade IaC with Terraform")

    if shutil.which("terraform") is None:
        console.print(c("terraform CLI not found on PATH.", f"{BOLD}{RED}"))
        console.print(c("Install Terraform >= 1.5 (https://developer.hashicorp.com/terraform/install) and try again.", YELLOW))
        console.print()
        sys.exit(127)

    statuses = compute_statuses()
    if statuses is None:
        print_invalid_config()
        sys.exit(1)

    print_todo_progress(statuses)
    pause("Press ENTER to view detailed feedback...")

    failed = first_failed_todo(statuses)
    feedback(failed)
    pause("Press ENTER to view lab progress...")

    divider()
    lab_summary(statuses)
    pause("Press ENTER to exit...")

    sys.exit(0 if failed is None else 1)


if __name__ == "__main__":
    main()
