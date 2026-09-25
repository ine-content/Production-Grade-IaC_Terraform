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
# TODO 05 - already solved in this folder.
# ---------------------------------------------------------------------------
locals {
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
}

# ===========================================================================
# PROVIDED - DO NOT MODIFY
# ===========================================================================
#
# Wraps TODO 05's two locals in output blocks, the same way "resolved_zones"
# did for TODO 04's local.site_zones:
#
#   terraform output -json site_subnets
#   terraform output -json branch_gateway_devices
#
# The grader reads these exact same outputs to re-check TODO 05's work -
# never by reading main.tf's source as text.
output "site_subnets" {
  value = local.site_subnets
}

output "branch_gateway_devices" {
  value = local.branch_gateway_devices
}

# ---------------------------------------------------------------------------
# TODO 06 - already solved in this folder.
# ---------------------------------------------------------------------------
resource "aws_vpc" "site" {
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
}

# ===========================================================================
# PROVIDED - DO NOT MODIFY
# ===========================================================================
#
# 6 outputs, one per resource type above, so you (and the grader) can
# inspect exactly what got created in LocalStack, the same way
# "resolved_zones" let you inspect TODO 04's locals:
#
#   terraform output -json vpcs
#   terraform output -json subnets
#   terraform output -json route_tables
#   terraform output -json route_table_associations
#   terraform output -json security_groups
#   terraform output -json branch_gateways
#
# The grader reads these exact same outputs to check TODO 06's work -
# never by reading main.tf's source as text, and never by calling AWS
# (LocalStack) APIs directly itself.
output "vpcs" {
  value = { for k, v in aws_vpc.site : k => { id = v.id, cidr_block = v.cidr_block } }
}

output "subnets" {
  value = { for k, s in aws_subnet.zone : k => { id = s.id, vpc_id = s.vpc_id, cidr_block = s.cidr_block } }
}

output "route_tables" {
  value = { for k, rt in aws_route_table.site : k => { id = rt.id, vpc_id = rt.vpc_id } }
}

output "route_table_associations" {
  value = { for k, a in aws_route_table_association.zone : k => { subnet_id = a.subnet_id, route_table_id = a.route_table_id } }
}

output "security_groups" {
  value = {
    for k, sg in aws_security_group.site : k => {
      id      = sg.id
      vpc_id  = sg.vpc_id
      ingress = [for r in sg.ingress : { protocol = r.protocol, cidr_blocks = r.cidr_blocks }]
    }
  }
}

output "branch_gateways" {
  value = {
    for k, i in aws_instance.branch_gateway : k => {
      subnet_id               = i.subnet_id
      vpc_security_group_ids  = i.vpc_security_group_ids
      tags                    = i.tags
    }
  }
}

# ---------------------------------------------------------------------------
# TODO 07 - already solved in this folder.
# ---------------------------------------------------------------------------
check "subnet_counts_match_expected" {
  assert {
    condition = alltrue([
      length([for k in keys(aws_subnet.zone) : true if startswith(k, "rdu01-")]) == 4,
      length([for k in keys(aws_subnet.zone) : true if startswith(k, "aus02-")]) == 4,
      length([for k in keys(aws_subnet.zone) : true if startswith(k, "sea03-")]) == 3,
    ])
    error_message = "One or more sites do not have the expected number of subnets."
  }
}

check "gateway_counts_match_expected" {
  assert {
    condition = alltrue([
      length([for k in keys(aws_instance.branch_gateway) : true if startswith(k, "rdu01-")]) == 2,
      length([for k in keys(aws_instance.branch_gateway) : true if startswith(k, "aus02-")]) == 2,
      length([for k in keys(aws_instance.branch_gateway) : true if startswith(k, "sea03-")]) == 1,
    ])
    error_message = "One or more sites do not have the expected number of branch gateway devices."
  }
}

# ---------------------------------------------------------------------------
# TODO 08 - already solved in this folder.
# ---------------------------------------------------------------------------
resource "aws_ec2_tag" "branch_gateway_last_verified" {
  for_each    = local.branch_gateway_devices
  resource_id = aws_instance.branch_gateway[each.key].id
  key         = "LastVerified"
  value       = timestamp()

  lifecycle {
    ignore_changes = [value]
  }
}

# ===========================================================================
# PROVIDED - DO NOT MODIFY
# ===========================================================================
#
# Wraps aws_ec2_tag.branch_gateway_last_verified in an output, the same way
# "branch_gateways" did for aws_instance.branch_gateway itself:
#
#   terraform output -json branch_gateway_tags
#
# The grader reads this exact same output to check TODO 08's work - never
# by reading your main.tf source as text.
output "branch_gateway_tags" {
  value = {
    for k, t in aws_ec2_tag.branch_gateway_last_verified : k => {
      key   = t.key
      value = t.value
    }
  }
}

# ---------------------------------------------------------------------------
# STUDENT WORK AREA - TODO 09
# ---------------------------------------------------------------------------
# Every resource above is something Terraform itself manages - it created
# each one, and it remembers what it created in its own state. This TODO
# introduces a different kind of block entirely: a `data` source, which
# never creates or manages anything - it only reads. A data source is
# queried fresh from the provider on every single plan and apply, and it
# never appears in a `terraform destroy`, because Terraform never owned it
# in the first place.
#
# Network Engineering wants proof that what aws_instance.branch_gateway
# claims about itself is what's actually running in AWS - queried
# completely independently, not by re-reading Terraform's own state.
#
# Define exactly these 2 blocks - top-level, not nested inside anything
# else. Every name below is exactly what the grader looks for - do not
# rename them.
#
#   data "aws_instance" "branch_gateway_live"   - one per firewall
#     device, for_each = local.branch_gateway_devices (the same set
#     aws_instance.branch_gateway itself already uses). Looks up that
#     same entry's own EC2 instance, live, by its instance_id.
#
#   check "live_state_matches_expected"   - one assert confirming every
#     one of those live lookups' own DeviceRole tag still reads
#     "branch-gateway" - proof this isn't just re-reading what Terraform
#     already believes, but an independently fetched confirmation of it.
#
# See TASK.md for the exact attributes these need.



# ---------------------------------------------------------------------------
# END STUDENT WORK AREA - TODO 09
# ---------------------------------------------------------------------------

# ===========================================================================
# PROVIDED - DO NOT MODIFY
# ===========================================================================
#
# Wraps data.aws_instance.branch_gateway_live in an output, the same way
# "branch_gateway_tags" did for aws_ec2_tag.branch_gateway_last_verified:
#
#   terraform output -json branch_gateway_live_state
#
# The grader reads this exact same output to check TODO 09's work - never
# by reading your main.tf source as text.
output "branch_gateway_live_state" {
  value = {
    for k, d in data.aws_instance.branch_gateway_live : k => {
      instance_state = d.instance_state
      tags           = d.tags
    }
  }
}
