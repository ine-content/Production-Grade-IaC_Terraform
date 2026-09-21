terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ===========================================================================
# PROVIDED - DO NOT MODIFY
# ===========================================================================
#
# Meridian Retail is hosting this branch network in AWS - so this course
# points the real, official hashicorp/aws provider at LocalStack (a local
# AWS emulator) instead of real AWS. "test"/"test" aren't real credentials;
# LocalStack doesn't check them at all, but the aws provider still requires
# something be present in those fields. The 3 skip_* flags stop the
# provider from trying to make real AWS calls (account ID lookup, EC2
# instance metadata) that LocalStack doesn't need and would otherwise slow
# every plan/apply down while they time out.
#
# Every resource you create below this point is genuinely created,
# read, and destroyed against LocalStack over this connection - not
# simulated in any way.
provider "aws" {
  region                      = "us-east-1"
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  endpoints {
    ec2 = "http://localhost:4566"
  }
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
    condition     = alltrue([
      for zone_role in local.disabled_zones_flat : contains(local.valid_zone_roles, zone_role)
    ])
    error_message = "A disabled zone role isn't defined in the service intent."
  }
}

# ---------------------------------------------------------------------------
# TODO 04 - already solved in this folder.
# ---------------------------------------------------------------------------
locals {
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
}

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

# ---------------------------------------------------------------------------
# STUDENT WORK AREA - TODO 05
# ---------------------------------------------------------------------------
# TODO 02, 03, and 04's locals blocks, all above, are already solved and
# marked "do not modify" - leave them alone. Terraform allows more than
# one locals block in the same file (they all merge into the same
# local.* namespace), so write a fourth, separate locals block here
# instead of editing theirs:
#
#   locals {
#
#   }
#
# Inside it, define exactly these 4 locals. See TASK.md for the exact
# shape and a worked example. Nothing here creates any real
# infrastructure - these are plain values, not resources, so this TODO
# never touches LocalStack.
#
#   vpc_cidrs             - a plain map, site_id => that site's VPC CIDR
#                           block. See TASK.md's Technical Requirements
#                           table for the exact 3 values.
#
#   zone_subnet_octets    - a plain map, zone role => the /24 subnet
#                           number that role always gets within any
#                           site's VPC. See TASK.md's Technical
#                           Requirements table for the exact 5 values.
#
#   site_subnets          - a flat map keyed by "<site_id>-<zone_role>"
#                           (e.g. "rdu01-corp"), one entry per site per
#                           zone in that site's own local.site_zones -
#                           the exact zones TODO 04 already resolved.
#                           Each value is { site_id, zone_role,
#                           cidr_block }, where cidr_block comes from
#                           cidrsubnet(local.vpc_cidrs[site_id], 8,
#                           local.zone_subnet_octets[zone_role]).
#
#   branch_gateway_devices - a flat map keyed by device_id (e.g.
#                           "rdu01-gw-primary"), one entry per firewall
#                           device in EVERY site's own firewalls list -
#                           not just firewalls[0]. RDU01 and AUS02 each
#                           have 2 (an HA pair), SEA03 has 1. Each value
#                           is { site_id, role }.
#
# TODO 06 (the next lab in this course) turns these two maps into real
# AWS resources - VPCs, subnets, a route table, a security group, and an
# EC2 instance per firewall device - against LocalStack.



# ---------------------------------------------------------------------------
# END STUDENT WORK AREA - TODO 05
# ---------------------------------------------------------------------------

# ===========================================================================
# PROVIDED - DO NOT MODIFY
# ===========================================================================
#
# Wraps your two locals in output blocks, the same way "resolved_zones"
# did for TODO 04's local.site_zones:
#
#   terraform output -json site_subnets
#   terraform output -json branch_gateway_devices
#
# The grader reads these exact same outputs to check TODO 05's work -
# never by reading main.tf's source as text.
output "site_subnets" {
  value = local.site_subnets
}

output "branch_gateway_devices" {
  value = local.branch_gateway_devices
}
