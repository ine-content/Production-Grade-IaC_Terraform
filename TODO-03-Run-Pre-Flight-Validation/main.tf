terraform {
  required_version = ">= 1.5.0"
}

# ---------------------------------------------------------------------------
# TODO 02 - already solved in this folder.
# ---------------------------------------------------------------------------
locals {
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
}

# ===========================================================================
# PROVIDED - DO NOT MODIFY
# ===========================================================================
#
# An `output` block is how a value computed inside this Terraform
# configuration becomes visible outside of it. Without this block,
# local.service_intent, local.environments, and local.sites would only
# exist internally - neither you nor the grader could ever see them.
# This wraps all 3 of TODO 02's locals into one output named
# "loaded_inputs" so you can inspect what TODO 02 loaded yourself with:
#
#   terraform output -json loaded_inputs
#
# The grader reads this exact same output to check TODO 02's work -
# never by reading main.tf's source as text.
output "loaded_inputs" {
  value = {
    service_intent = local.service_intent
    environments   = local.environments
    sites          = local.sites
  }
}

# ---------------------------------------------------------------------------
# STUDENT WORK AREA - TODO 03
# ---------------------------------------------------------------------------
# Write a locals block with exactly these 2 locals, then an output block
# with exactly this 1 precondition. See TASK.md for the exact shape.
#
#   valid_zone_roles    - a plain list of every zone role defined in the
#                         service intent (e.g. ["corp", "voice", "pos",
#                         "guest", "quarantine"])
#   disabled_zones_flat - every environment's disabled_zones, flattened
#                         into one plain list
#
#   output "preflight_ok" - value can just be true. Its precondition
#                         must fail (condition = false) if anything in
#                         disabled_zones_flat is NOT in valid_zone_roles.





# ---------------------------------------------------------------------------
# END STUDENT WORK AREA - TODO 03
# ---------------------------------------------------------------------------
