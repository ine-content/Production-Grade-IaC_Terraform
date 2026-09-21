#!/usr/bin/env python3

"""
Production-Grade IaC with Terraform - Coaching-Style Grader (Rich terminal UI)

This grader validates the course one TODO at a time, always starting from
TODO 01, and stops at the first incomplete one - even though TODO 01-07
are already solved for you in this folder, it re-checks them live every
run, so you always see real, current proof that nothing earlier broke, not
a cached checkmark.

TODO 05 (already solved here) computed local.site_subnets and
local.branch_gateway_devices - pure data, no resources. TODO 06 (also
already solved) created real resources - VPCs, subnets, a route table, a
security group, and an EC2 instance, per site - against LocalStack (a
local AWS emulator), using the real, official hashicorp/aws provider.
TODO 07 (also already solved) added check blocks that verify what TODO 06
created actually matches a fixed, expected shape. TODO 08 doesn't create
any new infrastructure either - it adds one small compliance tag (via
aws_ec2_tag, a standalone resource) and, in doing so, proves the single
most important guarantee Terraform makes: applying the exact same
configuration a second time, with nothing meaningfully changed, produces
zero further changes. Every check below still runs against a disposable
scratch copy of this lab (see _scoped_workdir()), exactly like TODO 02-07
- the student's real terraform.tfstate in this directory is never touched
by grading. Every check that applies the full file runs `terraform
destroy` in that same scratch copy before finishing - pass or fail - so
LocalStack is never left holding orphaned VPCs/subnets/instances between
grading runs (see apply_read_and_destroy() and
apply_and_check_idempotent()).

Requires the `terraform` CLI (>= 1.5) on PATH, and LocalStack running at
http://localhost:4566 (see TASK.md's "Before You Start" section).
"""

import ipaddress
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
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

LOCALSTACK_HEALTH_URL = "http://localhost:4566/_localstack/health"

SITE_RDU01_FILE = SITES_DIR / "rdu01.json"

# Cutting main.tf at one of these markers, when grading an earlier TODO,
# drops everything from that later TODO onward - see _scoped_workdir().
# These point at the real banner comments already in THIS folder's
# main.tf, not an invented marker - see TODO 04's grading.py for why.
TODO_03_MARKER = "# TODO 03 - already solved in this folder."
TODO_04_MARKER = "# TODO 04 - already solved in this folder."
TODO_05_MARKER = "# TODO 05 - already solved in this folder."
TODO_06_MARKER = "# TODO 06 - already solved in this folder."
TODO_07_MARKER = "# TODO 07 - already solved in this folder."
TODO_08_MARKER = "# STUDENT WORK AREA - TODO 08"

# The aws_ec2_tag resource after TODO 08's own work area references
# aws_instance.branch_gateway - a resource that already exists (TODO 06 is
# solved), so referencing it is never the problem. But a resource block
# with a syntax mistake, or none written at all, is a completely normal,
# expected state before TODO 08 is solved - not a syntax error - so
# ensure_valid() validates only up through here. See ensure_valid() for
# why this matters (same fix as TODO 04's grading.py, now applied
# proactively here for the same reason).
CURRENT_TODO_END_MARKER = "# END STUDENT WORK AREA - TODO 08"

console = Console(markup=False, highlight=False)

BOLD = "bold "
DIM = "dim"
RED = "red"
GREEN = "green"
YELLOW = "yellow"
CYAN = "cyan"

INTERACTIVE_MODE = os.environ.get("CAPSTONE_INTERACTIVE", "1") != "0"

COURSE_TOTAL_TODOS = 12
TOTAL_TODOS = 8

VPC_CIDRS = {
    "rdu01": "10.0.0.0/16",
    "aus02": "10.1.0.0/16",
    "sea03": "10.2.0.0/16",
}

ZONE_SUBNET_OCTETS = {
    "corp": 0,
    "voice": 1,
    "pos": 2,
    "guest": 3,
    "quarantine": 4,
}

# The fixed, expected per-site counts TODO 07's own check blocks assert
# against - not derived from local.site_subnets/local.branch_gateway_devices
# (those are what's being verified), and not derived here from
# sites/*.json either, so this grader's expectation and the student's own
# check block condition are two genuinely independent sources of truth.
EXPECTED_SUBNET_COUNTS = {"rdu01": 4, "aus02": 4, "sea03": 3}
EXPECTED_GATEWAY_COUNTS = {"rdu01": 2, "aus02": 2, "sea03": 1}

TODO_NAMES = {
    1: "Author the Declarative Network Intent",
    2: "Load & Parse Structured Inputs",
    3: "Run Pre-Flight Validation",
    4: "Build Environment- and Site-Aware Locals",
    5: "Compute Network & Gateway Locals",
    6: "Define AWS Network & Firewall Resources",
    7: "Run terraform plan and Verify Against Expected Changes",
    8: "Apply Idempotently",
}

SUCCESS_MESSAGES = {
    1: "intent/branch_firewall_service.json captures the business requirements correctly.",
    2: "main.tf loads the service intent, both environments, and all 3 sites correctly.",
    3: "Pre-flight validation is running and correctly catches a bad cross-file reference.",
    4: "Every site resolves to the correct zones, with each environment's overrides correctly applied.",
    5: "Every site's subnet CIDRs and every firewall device's gateway entry are computed correctly.",
    6: "Every site's VPC, subnets, route table, security group, and branch gateway instance(s) - one per firewall device, HA pairs included - are correctly defined and provisioned in LocalStack.",
    7: "Both check blocks are defined correctly and correctly flag a real fault when one is injected.",
    8: "aws_ec2_tag.branch_gateway_last_verified is defined correctly, and a second apply - with nothing meaningfully changed - produces zero further changes.",
}

FAIL_MESSAGES = {
    1: "The pipeline cannot continue because the declarative network intent has not been authored correctly yet.",
    2: "The pipeline cannot continue because the structured inputs have not been loaded and parsed correctly yet.",
    3: "The pipeline cannot continue because pre-flight validation is not actually being executed.",
    4: "The pipeline cannot continue because the per-site resolved zones have not been built correctly yet.",
    5: "The pipeline cannot continue because the network and gateway locals have not been computed correctly yet.",
    6: "The pipeline cannot continue because the AWS network and firewall resources have not been defined correctly yet.",
    7: "The pipeline cannot continue because the verification check blocks have not been defined correctly yet.",
    8: "The pipeline cannot continue because applying the same configuration twice does not yet produce zero changes.",
}

HINTS = {
    1: "Create intent/branch_firewall_service.json by hand. Match the shape in TASK.md (tenant, service, zones: [{role, name, enabled}]) using the business requirements table exactly - JSON, not YAML.",
    2: "Use jsondecode(file(\"${path.module}/<path>\")) once per file - one call for the intent file, one for each of the 2 environment files, one for each of the 3 site files. Same pattern, 6 times over.",
    3: "First build valid_zone_roles with [for z in local.service_intent.zones : z.role]. Then build disabled_zones_flat with flatten([for env in local.environments : env.disabled_zones]). Then write one output block whose precondition condition is alltrue([for zone_role in local.disabled_zones_flat : contains(local.valid_zone_roles, zone_role)]) - true only when every disabled zone really exists.",
    4: "Build zone_names_by_role and enabled_zone_roles straight from local.service_intent.zones first. Then site_zone_roles: for each site, filter enabled_zone_roles to roles NOT in local.environments[site.environment].disabled_zones. Then site_zones: for each site, map site_zone_roles[site_id] to { role, name = zone_names_by_role[role], id = site.zone_ids[role] } objects.",
    5: "Build vpc_cidrs and zone_subnet_octets as plain maps straight from TASK.md's Technical Requirements table. Build site_subnets with merge([for site_id, zones in local.site_zones : { for zone in zones : \"${site_id}-${zone.role}\" => {...} }]...) - flattening a map of small maps into one big one. Build branch_gateway_devices the same way, but from each site's own firewalls list (not just firewalls[0]) - RDU01/AUS02 have 2 entries, SEA03 has 1.",
    6: "TODO 05 already gave you local.vpc_cidrs, local.site_subnets, and local.branch_gateway_devices - use them directly. 6 resource blocks, for_each over local.sites, local.site_subnets, or local.branch_gateway_devices as TASK.md describes, referencing each other's attributes (aws_vpc.site[each.key].id, etc.) to wire them together.",
    7: "Define exactly 2 top-level check blocks, named \"subnet_counts_match_expected\" and \"gateway_counts_match_expected\" - do not rename them. Each has one assert whose condition groups aws_subnet.zone's (or aws_instance.branch_gateway's) own keys by site, using startswith(key, \"<site_id>-\"), and compares each site's count against the fixed numbers in TASK.md's Technical Requirements table - never against local.site_subnets or local.branch_gateway_devices, since those are exactly what's being verified.",
    8: "for_each = local.branch_gateway_devices, resource_id should reference aws_instance.branch_gateway[each.key].id. key and value are already filled in below - value uses timestamp(), which returns a different string on every single plan. Add a lifecycle block with ignore_changes = [value] so Terraform stops trying to update that tag after it's first created - without it, every later apply will show this one resource changing, forever.",
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
    5: '''locals {
  vpc_cidrs = {
    rdu01 = "10.0.0.0/16"
    aus02 = "10.1.0.0/16"
    sea03 = "10.2.0.0/16"
  }

  zone_subnet_octets = {
    corp       = 0
    voice      = 1
    pos        = 2
    guest      = 3
    quarantine = 4
  }

  site_subnets = merge([
    for site_id, zones in local.site_zones : {
      for zone in zones :
      "${site_id}-${zone.role}" => {
        site_id    = site_id
        zone_role  = zone.role
        cidr_block = cidrsubnet(local.vpc_cidrs[site_id], 8, local.zone_subnet_octets[zone.role])
      }
    }
  ]...)

  branch_gateway_devices = merge([
    for site_id, site in local.sites : {
      for fw in site.firewalls :
      fw.device_id => { site_id = site_id, role = fw.role }
    }
  ]...)
}''',
    6: '''resource "aws_vpc" "site" {
  for_each   = local.sites
  cidr_block = local.vpc_cidrs[each.key]

  tags = {
    Name        = "meridian-${each.key}"
    Site        = each.key
    Environment = each.value.environment
  }
}

resource "aws_subnet" "zone" {
  for_each   = local.site_subnets
  vpc_id     = aws_vpc.site[each.value.site_id].id
  cidr_block = each.value.cidr_block

  tags = {
    Name = "${each.value.site_id}-${each.value.zone_role}"
    Zone = each.value.zone_role
  }
}

resource "aws_route_table" "site" {
  for_each = local.sites
  vpc_id   = aws_vpc.site[each.key].id

  tags = {
    Name = "meridian-${each.key}-rt"
  }
}

resource "aws_route_table_association" "zone" {
  for_each       = local.site_subnets
  subnet_id      = aws_subnet.zone[each.key].id
  route_table_id = aws_route_table.site[each.value.site_id].id
}

resource "aws_security_group" "site" {
  for_each    = local.sites
  name        = "meridian-${each.key}-fw"
  description = "Firewall policy for ${each.key}, resolved from local.site_zones"
  vpc_id      = aws_vpc.site[each.key].id

  dynamic "ingress" {
    for_each = { for zone in local.site_zones[each.key] : zone.role => zone }
    content {
      description = "${ingress.value.name} zone"
      from_port   = 0
      to_port     = 65535
      protocol    = "tcp"
      cidr_blocks = [local.site_subnets["${each.key}-${ingress.key}"].cidr_block]
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "meridian-${each.key}-fw"
  }
}

resource "aws_instance" "branch_gateway" {
  for_each                = local.branch_gateway_devices
  ami                     = "ami-00000000"
  instance_type           = "t3.micro"
  subnet_id               = aws_subnet.zone["${each.value.site_id}-corp"].id
  vpc_security_group_ids  = [aws_security_group.site[each.value.site_id].id]

  tags = {
    Name       = each.key
    Site       = each.value.site_id
    DeviceRole = "branch-gateway"
  }
}''',
    7: '''check "subnet_counts_match_expected" {
  assert {
    condition = alltrue([
      length([for k, s in aws_subnet.zone : s if startswith(k, "rdu01-")]) == 4,
      length([for k, s in aws_subnet.zone : s if startswith(k, "aus02-")]) == 4,
      length([for k, s in aws_subnet.zone : s if startswith(k, "sea03-")]) == 3,
    ])
    error_message = "One or more sites do not have the expected number of subnets."
  }
}

check "gateway_counts_match_expected" {
  assert {
    condition = alltrue([
      length([for k, i in aws_instance.branch_gateway : i if startswith(k, "rdu01-")]) == 2,
      length([for k, i in aws_instance.branch_gateway : i if startswith(k, "aus02-")]) == 2,
      length([for k, i in aws_instance.branch_gateway : i if startswith(k, "sea03-")]) == 1,
    ])
    error_message = "One or more sites do not have the expected number of branch gateway devices."
  }
}''',
    8: '''resource "aws_ec2_tag" "branch_gateway_last_verified" {
  for_each    = local.branch_gateway_devices
  resource_id = aws_instance.branch_gateway[each.key].id
  key         = "LastVerified"
  value       = timestamp()

  lifecycle {
    ignore_changes = [value]
  }
}''',
}

EXPECTED = {
    1: "intent/branch_firewall_service.json should exist with tenant: \"Meridian Retail\", service: \"branch-firewall-standard\", and exactly the 5 zone definitions specified in TASK.md.",
    2: "terraform output -json loaded_inputs should return service_intent matching intent/branch_firewall_service.json, environments with both \"prod\" and \"staging\" keys matching environments/*.json, and sites with \"rdu01\", \"aus02\", and \"sea03\" keys matching sites/*.json.",
    3: "With an unknown zone role temporarily injected into environments/staging.json's disabled_zones, terraform apply should fail. With the file restored, terraform apply should succeed.",
    4: "terraform output -json resolved_zones should return, for each site, the intent's enabled zones minus that site's own environment's disabled_zones, each with the right name and the right site-specific id - see TASK.md's Worked Example for the exact expected values.",
    5: "terraform output -json site_subnets should return one entry per site per resolved zone, keyed \"<site_id>-<zone_role>\", each with the right cidr_block. terraform output -json branch_gateway_devices should return one entry per firewall device in every site's firewalls list (RDU01/AUS02: 2, SEA03: 1), keyed by device_id, each with the right site_id and role.",
    6: "For each site: one VPC with the right CIDR, one /24 subnet per resolved zone with the right CIDR and the right VPC, one route table with every one of that site's subnets associated to it, one security group with one ingress rule per zone sourced from that zone's own subnet, and one EC2 instance per firewall device in that site's firewalls list (RDU01/AUS02: 2, SEA03: 1) in that site's corp subnet, using that site's security group, tagged with its own device_id.",
    7: "Both check blocks - \"subnet_counts_match_expected\" and \"gateway_counts_match_expected\" - should report status \"pass\" (via terraform show -json's checks array) against the real, correct data. With one of rdu01's two branch gateway devices temporarily removed from sites/rdu01.json, \"gateway_counts_match_expected\" should report status \"fail\" - proof the check is actually evaluating live data, not hardcoded to always pass. Either way, terraform apply itself should still exit 0 - a failing check is a warning, never a blocking error.",
    8: "terraform output -json branch_gateway_tags should return one entry per firewall device (RDU01/AUS02: 2, SEA03: 1), each with key \"LastVerified\" and a non-empty value. Immediately after a real apply, planning again should show every aws_ec2_tag.branch_gateway_last_verified instance as \"no-op\" - proof the lifecycle block is correctly ignoring the ever-changing timestamp() value after creation.",
}

PROBLEMS = {
    1: "The declarative network intent file is missing, malformed, or does not match the required business requirements.",
    2: "main.tf's locals block is missing, fails to evaluate, or does not load service_intent, environments, and sites correctly from disk.",
    3: "Pre-flight validation did not catch an intentionally broken cross-file reference, or it fails even when every disabled zone is valid.",
    4: "resolved_zones is missing, fails to evaluate, or does not match the correct per-site zone list for at least one site.",
    5: "site_subnets or branch_gateway_devices is missing, fails to evaluate, or does not match the correct flattened map for at least one site.",
    6: "One or more of the 6 AWS resource types is missing, fails to apply, or doesn't match the correct per-site shape - wrong CIDR, a subnet in the wrong VPC, a missing route table association, a wrong or missing security group ingress rule, a missing branch gateway instance for a site's secondary device, or a branch gateway in the wrong subnet or with the wrong tags.",
    7: "One or both check blocks are missing, misnamed, fail to evaluate, always report \"pass\" regardless of the underlying data, or don't match the fixed expected per-site counts in TASK.md.",
    8: "aws_ec2_tag.branch_gateway_last_verified is missing, references the wrong resource, is missing for one or more devices, or is missing (or has the wrong) lifecycle.ignore_changes - causing a second apply, right after the first, to still show a pending change.",
}


# -----------------------------------------------------------------------------
# Terraform / LocalStack helpers
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
            timeout=180,
            env=_offline_cli_config_env(),
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return 127, "", "terraform CLI not found on PATH. Install Terraform >= 1.5 to run this grader."
    except subprocess.TimeoutExpired:
        return 124, "", "terraform command timed out."


def localstack_reachable():
    """A quick, cheap check that LocalStack is actually up before we ever
    try a real terraform init/apply against it - a much clearer failure
    than letting `terraform apply` time out slowly, once per check, and
    print a generic connection-refused error with no explanation."""
    try:
        with urllib.request.urlopen(LOCALSTACK_HEALTH_URL, timeout=3) as resp:
            return resp.status == 200
    except OSError:
        return False


_SKIP_COPY = {".terraform", "terraform.tfstate", "terraform.tfstate.backup", "__pycache__", ".terraform.lock.hcl"}


def _scoped_workdir(truncate_before=None):
    """Copy this lab's files into a fresh temp directory, optionally
    cutting main.tf short right before a marker string. See TODO 04's
    grading.py for why this (rather than -target) is how this course
    isolates one TODO's check from another's."""
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
        assert idx != -1, f"grading.py bug: truncation marker {truncate_before!r} not found in main.tf"
        main_tf.write_text(text[:idx], encoding="utf-8")

    return tmp


def apply_and_read_output(name, truncate_before=None):
    """Run init + apply in a scoped scratch copy of this lab, then read
    one output back. Used for TODO 01-05's own checks (all truncated
    well before TODO 06's resource blocks), so nothing real ever gets
    created in LocalStack here - no destroy step needed. Returns the
    parsed output value, or None if init/apply/output failed for any
    reason."""
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
    (returncode, stdout, stderr). Used by check_todo_3, truncated well
    before TODO 05 and TODO 06 - never touches LocalStack."""
    workdir = _scoped_workdir(truncate_before=truncate_before)
    try:
        rc, out, err = run_terraform(workdir, "init", "-input=false", "-no-color")
        if rc != 0:
            return rc, out, err
        return run_terraform(workdir, "apply", "-auto-approve", "-input=false", "-no-color")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _read_check_statuses(workdir):
    """Reads back every top-level `check` block's status from the
    current state, via `terraform show -json` - the only reliable way to
    see whether a check passed, since a PASSING check emits no line at
    all in `apply -json`'s streamed log (only failures do - verified
    against Terraform's own source, not just its docs). Returns
    {check_name: status} for every top-level check block found (status
    is one of "pass"/"fail"/"error"/"unknown"), or None if
    `terraform show -json` itself failed or returned something
    unreadable. An address only counts here when its own "kind" is
    "check" - that's what a standalone, top-level check block (as
    opposed to a resource or output precondition) looks like in this
    JSON."""
    rc, stdout, _ = run_terraform(workdir, "show", "-json")
    if rc != 0:
        return None
    try:
        state = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    statuses = {}
    for check in state.get("checks", []):
        address = check.get("address", {})
        if address.get("kind") != "check":
            continue
        name = address.get("name")
        if name:
            statuses[name] = check.get("status")
    return statuses


def apply_read_and_destroy(names, truncate_before=None):
    """Like apply_and_read_output, but for TODO 06 and TODO 07, where a
    (possibly truncated) apply creates REAL mock resources in
    LocalStack - something no earlier TODO in this course ever did.
    Every apply here is followed by `terraform destroy`, before the
    scratch copy itself is deleted, so LocalStack never accumulates
    orphaned VPCs, subnets, or instances across repeated grading runs -
    this check leaves LocalStack exactly as it found it, pass or fail.

    Returns a dict {name: parsed_output_or_None} for every name in
    `names`, plus "_apply_ok" (bool) so callers can tell "apply failed"
    apart from "apply succeeded but this output happened to be null",
    and "_checks" (see _read_check_statuses()) - populated whenever
    apply succeeds, regardless of whether the caller is TODO 06 (which
    ignores it - no check blocks exist yet in its truncated copy) or
    TODO 07 (which reads it directly)."""
    workdir = _scoped_workdir(truncate_before=truncate_before)
    results = {name: None for name in names}
    results["_apply_ok"] = False
    results["_checks"] = None
    try:
        rc, _, _ = run_terraform(workdir, "init", "-input=false", "-no-color")
        if rc != 0:
            return results
        rc, _, _ = run_terraform(workdir, "apply", "-auto-approve", "-input=false", "-no-color")
        if rc != 0:
            return results
        results["_apply_ok"] = True
        for name in names:
            rc, stdout, _ = run_terraform(workdir, "output", "-json", name)
            if rc == 0:
                try:
                    results[name] = json.loads(stdout)
                except json.JSONDecodeError:
                    results[name] = None
        results["_checks"] = _read_check_statuses(workdir)
        return results
    finally:
        run_terraform(workdir, "destroy", "-auto-approve", "-input=false", "-no-color")
        shutil.rmtree(workdir, ignore_errors=True)


def _read_plan_resource_actions(workdir, resource_prefix):
    """Plans again (against the state already on disk in `workdir`, no
    destroy or re-apply involved), saves that plan to a file, and reads
    back only the planned actions for resource instances whose own
    address starts with `resource_prefix` (e.g.
    'aws_ec2_tag.branch_gateway_last_verified["rdu01-gw-primary"]'),
    straight from `terraform show -json <planfile>`'s own
    resource_changes array. Returns {address: [actions]} for just those
    instances, or None if the plan or the JSON read itself failed.

    Deliberately reads ONE resource's own planned actions rather than
    trusting the plan's overall exit code (`-detailed-exitcode`): this
    course runs against LocalStack, a mocked AWS - and a mock EC2 API can
    return slightly different attribute values on refresh than what's in
    state, for reasons that have nothing to do with anything a student
    wrote. Scoping this check to exactly the resource this TODO is about
    means that kind of unrelated, LocalStack-only drift elsewhere in the
    plan can never fail this check - only whether THIS resource's own
    lifecycle.ignore_changes is doing its job is graded."""
    plan_file = workdir / "tfplan.out"
    rc, _, _ = run_terraform(workdir, "plan", f"-out={plan_file}", "-input=false", "-no-color")
    if rc != 0:
        return None
    rc, stdout, _ = run_terraform(workdir, "show", "-json", str(plan_file))
    if rc != 0:
        return None
    try:
        plan = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    actions = {}
    for change in plan.get("resource_changes", []):
        address = change.get("address", "")
        if address.startswith(resource_prefix):
            actions[address] = change.get("change", {}).get("actions", [])
    return actions


def apply_and_check_idempotent(names, resource_prefix, truncate_before=None):
    """Like apply_read_and_destroy, but for TODO 08: applies for real
    once, then - against that exact same state, with NO destroy in
    between - reads back the planned actions for just the resource
    instances matching `resource_prefix` (see
    _read_plan_resource_actions()). Idempotent means every one of those
    instances plans as ["no-op"] - nothing to add, change, or destroy.
    Always destroys before returning, pass or fail, so LocalStack is
    never left holding resources.

    Returns a dict {name: parsed_output_or_None} for every name in
    `names`, plus "_apply_ok" (bool) and "_actions" -
    {address: [actions]} for every matching resource instance, or None
    if the second plan itself couldn't be read at all (not the same as
    finding real changes)."""
    workdir = _scoped_workdir(truncate_before=truncate_before)
    results = {name: None for name in names}
    results["_apply_ok"] = False
    results["_actions"] = None
    try:
        rc, _, _ = run_terraform(workdir, "init", "-input=false", "-no-color")
        if rc != 0:
            return results
        rc, _, _ = run_terraform(workdir, "apply", "-auto-approve", "-input=false", "-no-color")
        if rc != 0:
            return results
        results["_apply_ok"] = True
        for name in names:
            rc, stdout, _ = run_terraform(workdir, "output", "-json", name)
            if rc == 0:
                try:
                    results[name] = json.loads(stdout)
                except json.JSONDecodeError:
                    results[name] = None
        results["_actions"] = _read_plan_resource_actions(workdir, resource_prefix)
        return results
    finally:
        run_terraform(workdir, "destroy", "-auto-approve", "-input=false", "-no-color")
        shutil.rmtree(workdir, ignore_errors=True)


_validate_checked = False
_validate_result = (True, "")


def ensure_valid():
    """`terraform validate` checks that main.tf is structurally sound
    HCL, WITHOUT evaluating whether any precondition's condition is
    actually true, and WITHOUT creating anything in LocalStack (validate
    never applies). That makes it the right tool to catch a genuine
    syntax mistake before ever attributing a failure to a specific TODO.

    This validates a scoped copy truncated right after TODO 06's own
    END marker - NOT the raw ROOT directory - because the real ROOT
    file's trailing outputs (vpcs, subnets, ...) reference aws_vpc.site,
    aws_subnet.zone, etc., which don't exist until TODO 06 is actually
    solved. Validating the full file would call that completely normal
    starting state "main.tf is not valid Terraform configuration", which
    is wrong and confusing - it isn't invalid, TODO 06 just isn't done
    yet. Any syntax mistake actually made while writing TODO 06 is still
    inside the truncated copy (that code comes before the END marker),
    so this still catches real syntax errors just fine. See TODO 04's
    grading.py, which hit this exact bug first.

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
    """Only called once TODO 01 and TODO 02 are already confirmed
    correct - see compute_statuses(). Temporarily breaks the REAL
    environments/staging.json on disk, always restores it in a finally
    block even if something raises. Truncated at TODO_04_MARKER so a
    broken TODO 04, TODO 05, or TODO 06 can't affect this result - and,
    since that truncation drops every resource block, this never
    touches LocalStack."""
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
    """Runs against a copy truncated right before TODO 05's own marker -
    dropping TODO 05's locals and TODO 06's resource blocks entirely, so
    a broken TODO 05 or TODO 06 can't affect this result, and this never
    touches LocalStack either."""
    resolved = apply_and_read_output("resolved_zones", truncate_before=TODO_05_MARKER)
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


def _cidrsubnet(prefix, newbits, netnum):
    """Python equivalent of Terraform's cidrsubnet(prefix, newbits,
    netnum) for the simple case this course needs (splitting a /16 into
    /24s) - independently recomputes the correct subnet CIDR straight
    from Technical Requirements' numbers, never by trusting whatever the
    student's own locals produced."""
    network = ipaddress.ip_network(prefix)
    subnets = list(network.subnets(new_prefix=network.prefixlen + newbits))
    return str(subnets[netnum])


def _compute_expected_site_subnets(site_zones):
    """site_id -> { zone_role -> expected subnet CIDR }, straight from
    VPC_CIDRS/ZONE_SUBNET_OCTETS and TODO 04's already-independently-
    computed site_zones - never from main.tf."""
    result = {}
    for site_id, zones in site_zones.items():
        result[site_id] = {
            zone["role"]: _cidrsubnet(VPC_CIDRS[site_id], 8, ZONE_SUBNET_OCTETS[zone["role"]])
            for zone in zones
        }
    return result


def _compute_expected_flat_site_subnets(site_zones):
    """The same expected values as _compute_expected_site_subnets(), but
    reshaped into the flat "<site_id>-<zone_role>" => {...} map that
    TODO 05's own local.site_subnets (and its "site_subnets" output) is
    actually shaped like."""
    nested = _compute_expected_site_subnets(site_zones)
    return {
        f"{site_id}-{role}": {"site_id": site_id, "zone_role": role, "cidr_block": cidr}
        for site_id, roles in nested.items()
        for role, cidr in roles.items()
    }


def _compute_expected_branch_gateway_devices():
    """device_id -> { site_id, role }, straight from every site's own
    sites/*.json firewalls list - never from main.tf."""
    result = {}
    for site_id in ("rdu01", "aus02", "sea03"):
        site_data = _load_source_json(SITES_DIR, f"{site_id}.json")
        if not site_data or not site_data.get("firewalls"):
            return None
        for fw in site_data["firewalls"]:
            device_id = fw.get("device_id")
            role = fw.get("role")
            if not device_id or not role:
                return None
            result[device_id] = {"site_id": site_id, "role": role}
    return result


def check_todo_5():
    """Re-checks TODO 05's already-solved locals every run, the same as
    TODO 01-04's own checks - runs in a scoped copy truncated right
    before TODO 06's own resource blocks (TODO_06_MARKER), so this only
    ever evaluates local values, never creates anything, and never
    touches LocalStack."""
    site_subnets = apply_and_read_output("site_subnets", truncate_before=TODO_06_MARKER)
    if not isinstance(site_subnets, dict):
        return False

    expected_site_zones = _compute_expected_site_zones()
    if expected_site_zones is None:
        return False
    if site_subnets != _compute_expected_flat_site_subnets(expected_site_zones):
        return False

    branch_gateway_devices = apply_and_read_output("branch_gateway_devices", truncate_before=TODO_06_MARKER)
    if not isinstance(branch_gateway_devices, dict):
        return False

    expected_devices = _compute_expected_branch_gateway_devices()
    if expected_devices is None:
        return False
    if branch_gateway_devices != expected_devices:
        return False

    return True


def check_todo_6():
    """Runs against a copy truncated right before TODO 07's own check
    blocks (TODO_07_MARKER) - a broken, or not-yet-written, TODO 07
    can't affect this result, consistent with every earlier check's
    "truncate before the next TODO's start" pattern. This is the first
    check in this course that creates real resources in LocalStack (see
    apply_read_and_destroy()), and the first that requires LocalStack to
    be reachable at all (see main())."""
    names = ["vpcs", "subnets", "route_tables", "route_table_associations", "security_groups", "branch_gateways"]
    results = apply_read_and_destroy(names, truncate_before=TODO_07_MARKER)
    if not results["_apply_ok"]:
        return False

    vpcs = results["vpcs"]
    subnets = results["subnets"]
    route_tables = results["route_tables"]
    route_table_associations = results["route_table_associations"]
    security_groups = results["security_groups"]
    branch_gateways = results["branch_gateways"]

    if not all(isinstance(x, dict) for x in (vpcs, subnets, route_tables, route_table_associations, security_groups, branch_gateways)):
        return False

    expected_site_zones = _compute_expected_site_zones()
    if expected_site_zones is None:
        return False
    expected_subnets = _compute_expected_site_subnets(expected_site_zones)

    site_ids = ("rdu01", "aus02", "sea03")

    if set(vpcs.keys()) != set(site_ids):
        return False
    for site_id in site_ids:
        vpc = vpcs.get(site_id)
        if not isinstance(vpc, dict) or vpc.get("cidr_block") != VPC_CIDRS[site_id] or not vpc.get("id"):
            return False

    expected_subnet_keys = {
        f"{site_id}-{role}" for site_id, roles in expected_subnets.items() for role in roles
    }
    if set(subnets.keys()) != expected_subnet_keys:
        return False
    for site_id, roles in expected_subnets.items():
        for role, expected_cidr in roles.items():
            key = f"{site_id}-{role}"
            subnet = subnets.get(key)
            if not isinstance(subnet, dict):
                return False
            if subnet.get("cidr_block") != expected_cidr:
                return False
            if subnet.get("vpc_id") != vpcs[site_id]["id"]:
                return False
            if not subnet.get("id"):
                return False

    if set(route_tables.keys()) != set(site_ids):
        return False
    for site_id in site_ids:
        rt = route_tables.get(site_id)
        if not isinstance(rt, dict) or rt.get("vpc_id") != vpcs[site_id]["id"] or not rt.get("id"):
            return False

    if set(route_table_associations.keys()) != expected_subnet_keys:
        return False
    for site_id, roles in expected_subnets.items():
        for role in roles:
            key = f"{site_id}-{role}"
            assoc = route_table_associations.get(key)
            if not isinstance(assoc, dict):
                return False
            if assoc.get("subnet_id") != subnets[key]["id"]:
                return False
            if assoc.get("route_table_id") != route_tables[site_id]["id"]:
                return False

    if set(security_groups.keys()) != set(site_ids):
        return False
    for site_id in site_ids:
        sg = security_groups.get(site_id)
        if not isinstance(sg, dict) or sg.get("vpc_id") != vpcs[site_id]["id"] or not sg.get("id"):
            return False
        ingress = sg.get("ingress")
        if not isinstance(ingress, list):
            return False
        expected_ingress = sorted(
            ("tcp", expected_subnets[site_id][role])
            for role in expected_subnets[site_id]
        )
        actual_ingress = []
        for rule in ingress:
            if not isinstance(rule, dict):
                return False
            cidrs = rule.get("cidr_blocks") or []
            if len(cidrs) != 1:
                return False
            actual_ingress.append((rule.get("protocol"), cidrs[0]))
        if sorted(actual_ingress) != expected_ingress:
            return False

    # One branch gateway instance per firewall DEVICE, not per site - a
    # site with an HA pair (RDU01, AUS02) needs 2, matching its own
    # firewalls list from sites/*.json; SEA03 (1 device) needs 1.
    expected_device_ids = set()
    for site_id in site_ids:
        site_data = _load_source_json(SITES_DIR, f"{site_id}.json")
        if not site_data or not site_data.get("firewalls"):
            return False
        corp_key = f"{site_id}-corp"
        for fw in site_data["firewalls"]:
            device_id = fw.get("device_id")
            if not device_id:
                return False
            expected_device_ids.add(device_id)
            gw = branch_gateways.get(device_id)
            if not isinstance(gw, dict):
                return False
            if gw.get("subnet_id") != subnets.get(corp_key, {}).get("id"):
                return False
            if gw.get("vpc_security_group_ids") != [security_groups[site_id]["id"]]:
                return False
            tags = gw.get("tags") or {}
            if tags.get("Name") != device_id or tags.get("Site") != site_id or tags.get("DeviceRole") != "branch-gateway":
                return False
    if set(branch_gateways.keys()) != expected_device_ids:
        return False

    return True


def check_todo_7():
    """Checks that both check blocks exist, are named exactly right, and
    correctly flag a REAL fault - not just that they're present and
    always say "pass". Runs against a copy truncated right before TODO
    08's own resource (TODO_08_MARKER) - a broken, or not-yet-written,
    TODO 08 can't affect this result, consistent with every earlier
    check's "truncate before the next TODO's start" pattern. Applies
    that truncated copy twice against LocalStack, in a fresh scratch
    copy each time (same real-apply approach as check_todo_6): once
    against a version of sites/rdu01.json with one of its 2 firewalls
    entries temporarily removed (rdu01 should then only get 1 branch
    gateway instance instead of 2), confirming
    "gateway_counts_match_expected" reports status "fail"; once against
    the real, unmodified file, confirming both checks report status
    "pass". Always restores sites/rdu01.json in a finally block, even if
    something raises.

    Since a failing check block is only ever a WARNING, never a blocking
    error (Terraform's own documented behavior), `terraform apply`
    exits 0 either way - the apply return code alone can never tell
    "passed" apart from "failed" here. Only `terraform show -json`'s
    checks array (read via _read_check_statuses(), inside
    apply_read_and_destroy()) can.

    Self-healing: writes sites/rdu01.json's real, original content to a
    backup file before ever touching it, and only deletes that backup
    once the real file is safely restored. If a previous grading run was
    killed or interrupted while the file was still broken (e.g. Ctrl+C
    or a closed terminal during the real terraform apply below), that
    backup is left behind - the next run detects it, restores the real
    file from it before doing anything else, and only then proceeds.
    Without this, an interrupted run would permanently leave
    sites/rdu01.json missing a real firewall device, and every TODO from
    here on would keep failing for a reason that has nothing to do with
    anything the student wrote."""
    names = ["vpcs", "subnets", "route_tables", "route_table_associations", "security_groups", "branch_gateways"]
    expected_checks = {"subnet_counts_match_expected", "gateway_counts_match_expected"}

    if not SITE_RDU01_FILE.exists():
        return False

    backup_file = SITE_RDU01_FILE.with_suffix(".json.grading-backup")
    if backup_file.exists():
        SITE_RDU01_FILE.write_text(backup_file.read_text(encoding="utf-8"), encoding="utf-8")
        backup_file.unlink()

    original = SITE_RDU01_FILE.read_text(encoding="utf-8")
    try:
        data = json.loads(original)
        firewalls = data.get("firewalls")
        if not isinstance(firewalls, list) or len(firewalls) < 2:
            return False

        backup_file.write_text(original, encoding="utf-8")

        broken = dict(data)
        broken["firewalls"] = firewalls[:1]
        SITE_RDU01_FILE.write_text(json.dumps(broken, indent=2) + "\n", encoding="utf-8")

        broken_results = apply_read_and_destroy(names, truncate_before=TODO_08_MARKER)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    finally:
        SITE_RDU01_FILE.write_text(original, encoding="utf-8")
        if backup_file.exists():
            backup_file.unlink()

    if not broken_results["_apply_ok"]:
        return False
    broken_checks = broken_results["_checks"]
    if not isinstance(broken_checks, dict) or not expected_checks.issubset(broken_checks.keys()):
        return False
    if broken_checks.get("gateway_counts_match_expected") != "fail":
        return False

    clean_results = apply_read_and_destroy(names, truncate_before=TODO_08_MARKER)
    if not clean_results["_apply_ok"]:
        return False
    clean_checks = clean_results["_checks"]
    if not isinstance(clean_checks, dict) or not expected_checks.issubset(clean_checks.keys()):
        return False
    if clean_checks.get("subnet_counts_match_expected") != "pass":
        return False
    if clean_checks.get("gateway_counts_match_expected") != "pass":
        return False

    return True


def check_todo_8():
    """Checks that aws_ec2_tag.branch_gateway_last_verified exists, one
    per firewall device, tagged "LastVerified" - and, critically, that a
    second `terraform plan` run immediately after a real apply (same
    state, no destroy in between - see apply_and_check_idempotent())
    plans every one of those aws_ec2_tag instances as "no-op". value
    uses timestamp(), which returns a different string on every single
    plan - so this second plan can only come back "no-op" for this
    resource if lifecycle.ignore_changes is correctly telling Terraform
    to stop tracking that one attribute after creation. Deliberately
    checks only this one resource's own planned actions (see
    _read_plan_resource_actions()), not the plan's overall exit code -
    LocalStack's EC2 mock can show unrelated drift elsewhere that has
    nothing to do with this TODO, and that should never fail this
    check. This is the same real-apply approach as check_todo_6 and
    check_todo_7 - runs against the full, untruncated file, since TODO
    08 is the last TODO in this folder."""
    names = ["branch_gateway_tags"]
    resource_prefix = "aws_ec2_tag.branch_gateway_last_verified["
    results = apply_and_check_idempotent(names, resource_prefix)
    if not results["_apply_ok"]:
        return False

    tags = results["branch_gateway_tags"]
    if not isinstance(tags, dict):
        return False

    expected_devices = _compute_expected_branch_gateway_devices()
    if expected_devices is None:
        return False
    if set(tags.keys()) != set(expected_devices.keys()):
        return False
    for device_id, tag in tags.items():
        if not isinstance(tag, dict):
            return False
        if tag.get("key") != "LastVerified":
            return False
        if not tag.get("value"):
            return False

    actions = results["_actions"]
    if not isinstance(actions, dict) or not actions:
        return False
    expected_addresses = {
        f'{resource_prefix}"{device_id}"]' for device_id in expected_devices
    }
    if set(actions.keys()) != expected_addresses:
        return False
    for address, planned_actions in actions.items():
        if planned_actions != ["no-op"]:
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
    statuses[5] = check_todo_5() if (statuses[1] and statuses[2] and statuses[3] and statuses[4]) else False
    statuses[6] = check_todo_6() if all(statuses[n] for n in range(1, 6)) else False
    statuses[7] = check_todo_7() if all(statuses[n] for n in range(1, 7)) else False
    statuses[8] = check_todo_8() if all(statuses[n] for n in range(1, 8)) else False
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
    elif number == 5:
        console.print("[5] Computing network and gateway locals...")
        if statuses[number]:
            expected_site_zones = _compute_expected_site_zones() or {}
            for site_id in ("rdu01", "aus02", "sea03"):
                zone_count = len(expected_site_zones.get(site_id, []))
                site_data = _load_source_json(SITES_DIR, f"{site_id}.json") or {}
                device_count = len(site_data.get("firewalls") or [])
                console.print(
                    f"  {site_id} -> {zone_count} subnet(s) planned in {VPC_CIDRS[site_id]}, "
                    f"{device_count} gateway device(s) planned"
                )
    elif number == 6:
        console.print("[6] Defining AWS network and firewall resources...")
        if statuses[number]:
            expected_site_zones = _compute_expected_site_zones() or {}
            for site_id in ("rdu01", "aus02", "sea03"):
                zone_count = len(expected_site_zones.get(site_id, []))
                site_data = _load_source_json(SITES_DIR, f"{site_id}.json") or {}
                gateway_names = ", ".join(
                    fw.get("device_id", "?") for fw in (site_data.get("firewalls") or [])
                )
                console.print(
                    f"  {site_id} -> VPC {VPC_CIDRS[site_id]}, {zone_count} subnets, "
                    f"{zone_count} firewall rules, gateways: {gateway_names}"
                )
    elif number == 7:
        console.print("[7] Running terraform plan and verifying against expected changes...")
        if statuses[number]:
            for site_id in ("rdu01", "aus02", "sea03"):
                console.print(
                    f"  {site_id} -> {EXPECTED_SUBNET_COUNTS[site_id]} subnets (expected "
                    f"{EXPECTED_SUBNET_COUNTS[site_id]}), {EXPECTED_GATEWAY_COUNTS[site_id]} "
                    f"gateways (expected {EXPECTED_GATEWAY_COUNTS[site_id]})"
                )
            console.print("  subnet_counts_match_expected  -> pass")
            console.print("  gateway_counts_match_expected -> pass")
    elif number == 8:
        console.print("[8] Applying idempotently...")
        if statuses[number]:
            expected_devices = _compute_expected_branch_gateway_devices() or {}
            for device_id in sorted(expected_devices):
                console.print(f"  {device_id} -> LastVerified tag present")
            console.print("  terraform apply    -> 5 added, 0 changed, 0 destroyed")
            console.print("  terraform plan     -> No changes. Your infrastructure matches the configuration.")


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


def print_localstack_unreachable():
    banner("LocalStack is not reachable", YELLOW)
    console.print(c(
        f"Couldn't reach {LOCALSTACK_HEALTH_URL} - TODO 06, TODO 07, and TODO 08 all "
        "need LocalStack running before they can create or verify anything. See "
        "TASK.md's \"Before You Start\" section.",
        YELLOW,
    ))
    console.print()
    console.print("  docker run --rm -d -p 4566:4566 --name localstack localstack/localstack")
    console.print()


def main():
    banner("Production-Grade IaC with Terraform")

    if shutil.which("terraform") is None:
        console.print(c("terraform CLI not found on PATH.", f"{BOLD}{RED}"))
        console.print(c("Install Terraform >= 1.5 (https://developer.hashicorp.com/terraform/install) and try again.", YELLOW))
        console.print()
        sys.exit(127)

    if not localstack_reachable():
        print_localstack_unreachable()
        sys.exit(1)

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
