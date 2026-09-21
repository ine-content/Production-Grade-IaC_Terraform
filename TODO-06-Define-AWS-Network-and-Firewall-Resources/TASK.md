# TODO 06 — Define AWS Network & Firewall Resources

## Topics Covered

```
✓ Turning resolved data into real Terraform resources with for_each
✓ Referencing one resource's attributes from another (aws_vpc.site[...].id)
✓ dynamic blocks - generating a variable number of nested blocks (ingress rules)
```

## Recap

TODO 01 through TODO 05 are already solved in this folder. TODO 05 gave
you `local.site_subnets` (every site's subnet CIDRs, already carved out
of its VPC) and `local.branch_gateway_devices` (every firewall device
across every site). Open `main.tf` and find `STUDENT WORK AREA - TODO 06`,
right after TODO 05's own `branch_gateway_devices` output.

## Scenario

TODO 05 finished the planning: every subnet's CIDR and every gateway
device's placement are already computed, sitting in `local.site_subnets`
and `local.branch_gateway_devices`. This TODO is where that plan actually
becomes AWS infrastructure.

Each site's `firewalls` list, loaded back in TODO 02, is that site's
planned gateway device inventory - `device_id` and `role`. It's not going
anywhere: `device_id` becomes the Name tag on that site's new EC2 gateway
below, so the device Store Operations and Network Engineering already
agreed on stays traceable all the way through to what's actually running.
Concretely, per site:

```
- One VPC, sized /16
- One subnet per resolved zone (from local.site_subnets), sized /24
- One route table, with every one of that site's subnets associated to it
- One security group carrying that site's firewall policy - one ingress
  rule per resolved zone, sourced from that zone's own subnet
- One EC2 instance per device in that site's own firewalls list, each
  tagged with its own device_id so it's traceable end to end - RDU01 and
  AUS02 each get 2 (their HA pair), SEA03 gets 1
```

This TODO defines all 6 resource types. It provisions them against
**LocalStack** (a local AWS emulator) using the real, official
`hashicorp/aws` provider - so every `plan`, `apply`, and `destroy` from
here on is genuine Terraform behavior against a genuine AWS provider, not
simulated.

## Before You Start: Check LocalStack Is Running

This TODO (and every one after it) needs LocalStack running in the
background. It's set up (see docker-compose.yml in this folder) to start
automatically with Docker, so just check it's actually up:

```
curl http://localhost:4566/_localstack/health
```

You should get back JSON with "ec2": "available".

If instead you get a connection error, start it from this folder:

```
docker compose up -d
```

## Worked Example

For `rdu01` (prod: no extra disabled zones), TODO 04 already resolved
`corp, voice, pos, guest` (no `quarantine` - never enabled at all), and
TODO 05 already computed their CIDRs. So `rdu01` gets:

```
aws_vpc.site["rdu01"]            10.0.0.0/16

aws_subnet.zone["rdu01-corp"]    10.0.0.0/24
aws_subnet.zone["rdu01-voice"]   10.0.1.0/24
aws_subnet.zone["rdu01-pos"]     10.0.2.0/24
aws_subnet.zone["rdu01-guest"]   10.0.3.0/24

aws_route_table.site["rdu01"]    (all 4 subnets above associated to it)

aws_security_group.site["rdu01"] 4 ingress rules - one per zone above,
                                  each sourced from that zone's own subnet

aws_instance.branch_gateway["rdu01-gw-primary"]
    subnet    = aws_subnet.zone["rdu01-corp"]
    sg        = aws_security_group.site["rdu01"]
    tags.Name = "rdu01-gw-primary"

aws_instance.branch_gateway["rdu01-gw-secondary"]
    subnet    = aws_subnet.zone["rdu01-corp"]
    sg        = aws_security_group.site["rdu01"]
    tags.Name = "rdu01-gw-secondary"
```

Both of `rdu01`'s gateway instances come from `sites/rdu01.json`'s
`firewalls` list (an HA pair - `rdu01-gw-primary` and
`rdu01-gw-secondary`), both in the same `corp` subnet, both using the
same security group - one EC2 instance per entry in that list, not one
per site.

`sea03` (staging: `pos` disabled) gets only 3 subnets/ingress rules -
`corp, voice, guest` - no `sea03-pos` subnet exists at all, same as TODO 04
never included `pos` in `sea03`'s resolved zones. `sea03`'s own
`firewalls` list has only 1 entry, so it gets only 1 gateway instance,
`aws_instance.branch_gateway["sea03-gw-primary"]`.

## Steps

```
1. Open main.tf and find STUDENT WORK AREA - TODO 06, right after TODO
   05's own branch_gateway_devices output. Everything you need is
   already computed: local.sites, local.vpc_cidrs, local.site_subnets,
   and local.branch_gateway_devices. This TODO is only about defining
   resources - no locals block of your own this time.

2. Define these 6 resources, in any order (Terraform figures out the
   dependency order itself from the references between them). Every
   resource name below (aws_vpc.site, aws_subnet.zone, etc.) is exactly
   what the grader looks for - do not rename them.

     resource "aws_vpc" "site" { ... }
     resource "aws_subnet" "zone" { ... }
     resource "aws_route_table" "site" { ... }
     resource "aws_route_table_association" "zone" { ... }
     resource "aws_security_group" "site" { ... }
     resource "aws_instance" "branch_gateway" { ... }

3. Define aws_vpc.site, one per site, so for_each = local.sites. Its
   cidr_block should come from that site's own entry in
   local.vpc_cidrs. Tags should be:

     Name:        starts with "meridian-", followed by the site's own id
     Site:        the site's own id
     Environment: that site's own environment field

   Complete the skeleton below to meet the requirements given above:

     resource "aws_vpc" "site" {
       for_each   = local.sites
       cidr_block = ...

       tags = {
         Name        = ""
         Site        = ...
         Environment = ...
       }
     }

4. Define aws_subnet.zone, one per site-zone pair, so for_each =
   local.site_subnets. Its vpc_id should reference the aws_vpc.site
   instance for that entry's own site_id, and its cidr_block is already
   sitting in each entry of local.site_subnets (no computation needed
   here, TODO 05 already did it). Tags should be:

     Name: the entry's own site_id, followed by a dash, then its own zone_role
     Zone: that entry's own zone_role

   Complete the skeleton below to meet the requirements given above:

     resource "aws_subnet" "zone" {
       for_each   = local.site_subnets
       vpc_id     = ...
       cidr_block = ...

       tags = {
         Name = ""
         Zone = ...
       }
     }

5. Define aws_route_table.site, one per site, so for_each = local.sites
   again. Its vpc_id should reference that same site's own aws_vpc.site
   instance. Its Name tag should be:

     Name: starts with "meridian-", followed by the site's own id, then "-rt"

   Complete the skeleton below to meet the requirements given above:

     resource "aws_route_table" "site" {
       for_each = local.sites
       vpc_id   = ...

       tags = {
         Name = ""
       }
     }

6. Define aws_route_table_association.zone, one per site-zone pair, so
   for_each = local.site_subnets again. Its subnet_id should reference
   the aws_subnet.zone instance for that same entry; its
   route_table_id should reference the aws_route_table.site instance
   for that entry's own site_id. This resource has no tags of its own.

   Complete the skeleton below to meet the requirements given above:

     resource "aws_route_table_association" "zone" {
       for_each       = local.site_subnets
       subnet_id      = ...
       route_table_id = ...
     }

7. Define aws_security_group.site, one per site, so for_each =
   local.sites again. Its vpc_id should reference that same site's own
   aws_vpc.site instance. It needs one dynamic "ingress" block per zone
   in that site's own local.site_zones (TODO 04's output) - the
   dynamic block's own for_each should build a map of that site's
   zones keyed by zone role, and each ingress rule's cidr_blocks should
   be a single-element list sourced from that zone's own subnet in
   local.site_subnets. Each ingress rule's from_port, to_port, and
   protocol are already filled in below - every rule opens the same
   full port range over tcp. Add a single egress rule allowing all
   outbound traffic (also already filled in below).

   name and description are free-form - Terraform requires name to be
   set, but neither one is checked precisely. They should be:

     name:        starts with "meridian-", followed by the site's own id, then "-fw"
     description: starts with "Firewall policy for ", followed by the
                  site's own id, then ", resolved from local.site_zones"

   Each ingress rule's own description is free-form too - it should
   be that zone's own name (from local.site_zones), followed by
   " zone".

   Tags should be:

     Name: starts with "meridian-", followed by the site's own id, then "-fw"

   Complete the skeleton below to meet the requirements given above:

     resource "aws_security_group" "site" {
       for_each    = local.sites
       name        = ""
       description = ""
       vpc_id      = ...

       dynamic "ingress" {
         for_each = ...
         content {
           description = ""
           from_port   = 0
           to_port     = 65535
           protocol    = "tcp"
           cidr_blocks = [...]
         }
       }

       egress {
         from_port   = 0
         to_port     = 0
         protocol    = "-1"
         cidr_blocks = ["0.0.0.0/0"]
       }

       tags = {
         Name = ""
       }
     }

8. Define aws_instance.branch_gateway, one per firewall device rather
   than one per site, so for_each = local.branch_gateway_devices. Set
   ami to "ami-00000000" and instance_type to "t3.micro" - LocalStack
   doesn't validate that the AMI is real, and this course doesn't need
   a real one. Its subnet_id should reference that entry's own site's
   "corp" subnet specifically, from aws_subnet.zone, and its
   vpc_security_group_ids should be a single-element list referencing
   that entry's own site's aws_security_group.site instance. Unlike
   every other resource above, this one's tags matter - they're checked
   exactly, not free-form labels:

     Name:       that entry's own key, precisely
     Site:       that entry's own site_id, precisely
     DeviceRole: "branch-gateway" - this literal string, exactly

   Complete the skeleton below to meet the requirements given above:

     resource "aws_instance" "branch_gateway" {
       for_each                = local.branch_gateway_devices
       ami                     = "ami-00000000"
       instance_type           = "t3.micro"
       subnet_id               = ...
       vpc_security_group_ids  = [...]

       tags = {
         Name       = ...
         Site       = ...
         DeviceRole = ""
       }
     }

9. Save, then run: python grading.py
```

## Grading Check

```
python grading.py
```

The grader runs `terraform apply` for real against LocalStack, reads back
all 6 outputs with `terraform output -json` - never by reading your
`main.tf` source as text - and independently recomputes the correct VPC
CIDR, subnet CIDR, route table association, security group ingress rules,
and branch gateway tags for every site, straight from `sites/*.json`. It
then runs `terraform destroy` before finishing, pass or fail, so
LocalStack is never left holding resources between runs.

Before you complete this TODO:

```
TODO 06 - Define AWS Network & Firewall Resources
────────────────────────────────────────────────────────────────────────────────

[6] Defining AWS network and firewall resources...

✗ TODO 06 Not Complete

The pipeline cannot continue because the AWS network and firewall resources
have not been defined correctly yet.

Proceeding to detailed feedback...
```

After you complete it correctly:

```
TODO 06 - Define AWS Network & Firewall Resources
────────────────────────────────────────────────────────────────────────────────

[6] Defining AWS network and firewall resources...
rdu01 -> VPC 10.0.0.0/16, 4 subnets, 4 firewall rules, gateways: rdu01-gw-primary, rdu01-gw-secondary
aus02 -> VPC 10.1.0.0/16, 4 subnets, 4 firewall rules, gateways: aus02-gw-primary, aus02-gw-secondary
sea03 -> VPC 10.2.0.0/16, 3 subnets, 3 firewall rules, gateways: sea03-gw-primary

✓ TODO 06 Complete
Every site's VPC, subnets, route table, security group, and branch gateway
instance are correctly defined and provisioned in LocalStack.
```

---
