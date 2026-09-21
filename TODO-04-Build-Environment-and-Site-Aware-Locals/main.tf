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
# TODO 03 - already solved in this folder.
# ---------------------------------------------------------------------------
locals {
  valid_zone_roles = [for z in local.service_intent.zones : z.role]

  disabled_zones_flat = flatten([
    for env in local.environments : env.disabled_zones
  ])
}

output "preflight_ok" {
  value = true

  precondition {
    condition = alltrue([
      for zone_role in local.disabled_zones_flat : contains(local.valid_zone_roles, zone_role)
    ])
    error_message = "A disabled zone role isn't defined in the service intent."
  }
}

# ---------------------------------------------------------------------------
# STUDENT WORK AREA - TODO 04
# ---------------------------------------------------------------------------
# Write a locals block with exactly these 4 locals. See TASK.md for the
# exact shape and a worked example.
#
#   zone_names_by_role - a map from zone role to zone name, built once
#                        from local.service_intent.zones, so nothing
#                        later has to search a list to find a name.
#
#   enabled_zone_roles - a plain list of every zone role that is
#                        enabled: true at the intent level (quarantine
#                        is enabled: false, so it's never in this list).
#
#   site_zone_roles    - a map keyed by site_id. Each value is
#                        enabled_zone_roles with that site's own
#                        environment's disabled_zones removed - e.g.
#                        sea03 is staging, and staging disables "pos",
#                        so sea03's list has no "pos" in it even though
#                        "pos" is enabled_zone_roles.
#
#   site_zones         - a map keyed by site_id. Each value is a list of
#                        objects { role, name, id }, one per role in
#                        that site's site_zone_roles - name comes from
#                        zone_names_by_role, id comes from that site's
#                        own zone_ids.




# ---------------------------------------------------------------------------
# END STUDENT WORK AREA - TODO 04
# ---------------------------------------------------------------------------

# ===========================================================================
# PROVIDED - DO NOT MODIFY
# ===========================================================================
#
# This wraps local.site_zones - the one local your TODO 04 solution is
# actually graded on - in an output block, the same way "loaded_inputs"
# above did for TODO 02's locals. Without this, local.site_zones would
# only exist internally; neither you nor the grader could ever see it.
# Once you've written TODO 04, you can inspect what it resolved yourself
# with:
#
#   terraform output -json resolved_zones
#
# The grader reads this exact same output to check TODO 04's work -
# never by reading main.tf's source as text.
output "resolved_zones" {
  value = local.site_zones
}
