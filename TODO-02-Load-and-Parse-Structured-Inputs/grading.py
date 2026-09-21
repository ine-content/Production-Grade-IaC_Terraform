#!/usr/bin/env python3

"""
Production-Grade IaC with Terraform - Coaching-Style Grader (Rich terminal UI)

This grader validates the course one TODO at a time, always starting from
TODO 01, and stops at the first incomplete one - even in a later lab
folder where earlier TODOs are already solved for you, it re-checks them
every run, so you always see real, current proof that nothing earlier
broke, not a cached checkmark.

TODO 02 onward is graded by actually running `terraform init` and
`terraform apply` against your main.tf, then reading the results back
with `terraform output -json` - never by reading your main.tf source as
text. Requires the `terraform` CLI (>= 1.5) to be installed and on PATH.

Student experience:
- TODO progress (every TODO from 1 up to this lab's total, re-checked live)
- Detailed feedback on the first incomplete one
- Lab progress summary
- Solution hidden unless you type S
"""

import json
import os
import shutil
import subprocess
import sys
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

console = Console(markup=False, highlight=False)

BOLD = "bold "
DIM = "dim"
RED = "red"
GREEN = "green"
YELLOW = "yellow"
CYAN = "cyan"

INTERACTIVE_MODE = os.environ.get("CAPSTONE_INTERACTIVE", "1") != "0"

COURSE_TOTAL_TODOS = 12
TOTAL_TODOS = 2

TODO_NAMES = {
    1: "Author the Declarative Network Intent",
    2: "Load & Parse Structured Inputs",
}

SUCCESS_MESSAGES = {
    1: "intent/branch_firewall_service.json captures the business requirements correctly.",
    2: "main.tf loads the service intent, both environments, and all 3 sites correctly.",
}

FAIL_MESSAGES = {
    1: "The pipeline cannot continue because the declarative network intent has not been authored correctly yet.",
    2: "The pipeline cannot continue because the structured inputs have not been loaded and parsed correctly yet.",
}

HINTS = {
    1: "Create intent/branch_firewall_service.json by hand. Match the shape in TASK.md (tenant, service, zones: [{role, name, enabled}]) using the business requirements table exactly - JSON, not YAML.",
    2: "Use jsondecode(file(\"${path.module}/<path>\")) once per file - one call for the intent file, one for each of the 2 environment files, one for each of the 3 site files. Same pattern, 6 times over.",
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
}

EXPECTED = {
    1: "intent/branch_firewall_service.json should exist with tenant: \"Meridian Retail\", service: \"branch-firewall-standard\", and exactly the 5 zone definitions specified in TASK.md.",
    2: "terraform output -json loaded_inputs should return service_intent matching intent/branch_firewall_service.json, environments with both \"prod\" and \"staging\" keys matching environments/*.json, and sites with \"rdu01\", \"aus02\", and \"sea03\" keys matching sites/*.json.",
}

PROBLEMS = {
    1: "The declarative network intent file is missing, malformed, or does not match the required business requirements.",
    2: "main.tf's locals block is missing, fails to evaluate, or does not load service_intent, environments, and sites correctly from disk.",
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


def run_terraform(*args):
    """Run a terraform command in ROOT. Returns (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["terraform", *args],
            cwd=ROOT,
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


_apply_attempted = False
_apply_succeeded = False


def ensure_applied():
    """init + apply once per grading.py run, memoized so every check_todo_N
    that needs the current state doesn't re-run terraform from scratch."""
    global _apply_attempted, _apply_succeeded
    if _apply_attempted:
        return _apply_succeeded
    _apply_attempted = True

    rc, _, _ = run_terraform("init", "-input=false", "-no-color")
    if rc != 0:
        _apply_succeeded = False
        return False

    rc, _, _ = run_terraform("apply", "-auto-approve", "-input=false", "-no-color")
    _apply_succeeded = rc == 0
    return _apply_succeeded


def get_output(name):
    if not ensure_applied():
        return None
    rc, stdout, _ = run_terraform("output", "-json", name)
    if rc != 0:
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return None


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
    if not check_todo_1():
        return False

    loaded = get_output("loaded_inputs")
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


def compute_statuses():
    statuses = {1: check_todo_1()}
    statuses[2] = check_todo_2() if statuses[1] else False
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


def main():
    banner("Production-Grade IaC with Terraform")

    if shutil.which("terraform") is None:
        console.print(c("terraform CLI not found on PATH.", f"{BOLD}{RED}"))
        console.print(c("Install Terraform >= 1.5 (https://developer.hashicorp.com/terraform/install) and try again.", YELLOW))
        console.print()
        sys.exit(127)

    statuses = compute_statuses()
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
