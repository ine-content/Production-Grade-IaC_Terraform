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
# STUDENT WORK AREA - TODO 08
# ---------------------------------------------------------------------------
# TODO 06 and TODO 07, just above, already created and verified every real
# resource this lab needs. This TODO adds one more, small resource - a
# compliance tag Network Engineering wants stamped on every branch gateway
# instance, recording when it was last verified - and, in doing so, teaches
# the single most important guarantee Terraform makes: applying the same
# configuration twice, with nothing meaningfully changed in between, should
# never show a third round of changes. That guarantee is called
# idempotency, and it's why `terraform apply` is safe to run again and
# again in a pipeline, on a schedule, or by hand, without ever worrying it
# will do something different the second time.
#
# Define exactly this 1 resource - a top-level block, not nested inside
# anything else. The resource name below (aws_ec2_tag.branch_gateway_last_verified)
# is exactly what the grader looks for - do not rename it.
#
#   resource "aws_ec2_tag" "branch_gateway_last_verified"   - one per
#     firewall device, for_each = local.branch_gateway_devices (the same
#     set aws_instance.branch_gateway itself already uses). Unlike a
#     tag written directly into a resource's own tags block, aws_ec2_tag
#     attaches one tag to an already-existing resource, by its id, as a
#     completely independent resource of its own - see TASK.md for why
#     that separation matters here.
#
# See TASK.md for the exact attributes this resource needs, and why a
# naive version of it would NOT be idempotent - it would show a change on
# every single apply, forever, unless you tell Terraform to ignore that
# one attribute after creation.


# ---------------------------------------------------------------------------
# END STUDENT WORK AREA - TODO 08
# ---------------------------------------------------------------------------

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
