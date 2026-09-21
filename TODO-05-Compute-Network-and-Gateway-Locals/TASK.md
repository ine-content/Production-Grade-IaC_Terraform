# TODO 05 — Compute Network & Gateway Locals

## Topics Covered

```
✓ merge() - flattening a list of small maps into one big one
✓ Nested for expressions - a for loop inside another for loop's map value
✓ cidrsubnet() - carving a big CIDR block into smaller, non-overlapping ones
```

## Recap

TODO 01 through TODO 04 are already solved in this folder. Open `main.tf`
and find `STUDENT WORK AREA - TODO 05`, right after the `resolved_zones`
output.

## Scenario

TODO 01 through TODO 04 built Meridian Retail's firewall policy without
needing to touch AWS at all: a declarative intent, loaded and
cross-validated structured inputs, and - as of TODO 04 - the exact,
resolved set of zones for every site. This TODO is where that policy
starts turning into an AWS network plan: every site's subnet CIDRs, and
every firewall device's gateway entry, computed as plain data - no AWS
resources yet, that's the next lab (TODO 06).

Each site's `firewalls` list, loaded back in TODO 02, is that site's
planned gateway device inventory - `device_id` and `role`. It's not going
anywhere: `device_id` is what TODO 06 tags each new EC2 gateway with, so
the device Store Operations and Network Engineering already agreed on
stays traceable all the way through to what's actually running.

This TODO is pure data - no `resource` blocks, and nothing here ever
touches LocalStack.

## Technical Requirements

VPC CIDR block, by site:

```
rdu01 = 10.0.0.0/16
aus02 = 10.1.0.0/16
sea03 = 10.2.0.0/16
```

Each zone's subnet is a /24 carved out of its site's own /16 VPC, using
`cidrsubnet(prefix, newbits, netnum)`:

```
cidrsubnet(<that site's VPC CIDR>, 8, <that zone's number below>)
```

`newbits` is always `8` - that's what turns a /16 into /24s (16 + 8 = 24).
`netnum` is what actually picks which /24, and it's the one thing that
varies, by zone role - the same 5 numbers at every site, regardless of
which zones that site's environment actually leaves enabled:

```
corp       = 0
voice      = 1
pos        = 2
guest      = 3
quarantine = 4
```

So, for example, `rdu01`'s `voice` subnet is
`cidrsubnet("10.0.0.0/16", 8, 1)` = `10.0.1.0/24`.

## Worked Example

For `rdu01` (prod: no extra disabled zones), TODO 04 already resolved
`corp, voice, pos, guest` (no `quarantine` - never enabled at all). So
`local.site_subnets` gets these 4 entries for `rdu01`:

```
site_subnets["rdu01-corp"]  = { site_id = "rdu01", zone_role = "corp",  cidr_block = "10.0.0.0/24" }
site_subnets["rdu01-voice"] = { site_id = "rdu01", zone_role = "voice", cidr_block = "10.0.1.0/24" }
site_subnets["rdu01-pos"]   = { site_id = "rdu01", zone_role = "pos",   cidr_block = "10.0.2.0/24" }
site_subnets["rdu01-guest"] = { site_id = "rdu01", zone_role = "guest", cidr_block = "10.0.3.0/24" }
```

`sea03` (staging: `pos` disabled) only gets 3 entries - `corp, voice,
guest` - no `sea03-pos` entry exists at all, same as TODO 04 never
included `pos` in `sea03`'s resolved zones.

`sites/rdu01.json`'s `firewalls` list is an HA pair - `rdu01-gw-primary`
and `rdu01-gw-secondary` - so `local.branch_gateway_devices` gets 2
entries for `rdu01`:

```
branch_gateway_devices["rdu01-gw-primary"]   = { site_id = "rdu01", role = "primary" }
branch_gateway_devices["rdu01-gw-secondary"] = { site_id = "rdu01", role = "secondary" }
```

`sea03`'s own `firewalls` list has only 1 entry, so it only contributes 1
entry to `local.branch_gateway_devices`.

## Steps

```
1. Open main.tf and find STUDENT WORK AREA - TODO 05. Write a fourth,
   separate locals block (TODO 02/03/04's are already solved above -
   don't touch them), opening brace and all:

     locals {

     }

2. Inside it, define vpc_cidrs and zone_subnet_octets - plain maps,
   values straight from the Technical Requirements table above:

     vpc_cidrs = {
       rdu01 = "X.X.X.X"
       aus02 = "X.X.X.X"
       sea03 = "X.X.X.X"
     }

     zone_subnet_octets = {
       corp       = X
       voice      = X
       pos        = X
       guest      = X
       quarantine = X
     }

3. Still inside that locals block, define site_subnets: a flat map
   keyed by "<site_id>-<zone_role>" (e.g. "rdu01-corp"), one entry per
   site per zone in that site's own local.site_zones (TODO 04's
   resolved output).

   You're starting from a map of sites, each holding a list of zones -
   you need one flat map with one entry per site-zone pair. Use
   merge() to combine a list of small maps into one big one - the
   standard way to flatten that shape in Terraform, spreading the list
   out with "..." as merge()'s arguments.

   Inside merge()'s list, write a for loop over local.site_zones - one
   small map per site. Inside THAT map, write a second, nested for
   loop over that site's own zones - one "<site_id>-<zone_role>" =>
   {...} entry per zone, where cidr_block comes from cidrsubnet(),
   using that site's own vpc_cidrs entry and that zone's own
   zone_subnet_octets entry:

     site_subnets = merge([
       for site_id, zones in local.site_zones : {
         for zone in zones :
         "<site_id>-<zone_role>" => {
           site_id    = ...
           zone_role  = ...
           cidr_block = ...
         }
       }
     ]...)

4. Still inside that locals block, define branch_gateway_devices: the
   same flat-map idea as site_subnets, but keyed by device_id, and
   built from each site's own firewalls list (local.sites, loaded back
   in TODO 02) instead of local.site_zones. This has to include every
   device at every site - RDU01 and AUS02 each contribute 2 entries
   (their HA pair), SEA03 contributes 1 - not just each site's primary
   device.

   Use merge() the same way as site_subnets. Inside merge()'s list,
   write a for loop over local.sites - one small map per site. Inside
   THAT map, write a second, nested for loop over that site's own
   firewalls list - one "<device_id>" => {...} entry per device:

     branch_gateway_devices = merge([
       for site_id, site in local.sites : {
         for fw in site.firewalls :
         "<device_id>" => {
           site_id = ...
           role    = ...
         }
       }
     ]...)

5. Save, then run: python grading.py
```

## Grading Check

```
python grading.py
```

The grader runs `terraform apply` (no resources exist yet, so this is
instant and makes no external calls), reads back `site_subnets` and
`branch_gateway_devices` with `terraform output -json` - never by
reading your `main.tf` source as text - and independently recomputes the
correct subnet CIDR and gateway device entry for every site, straight
from `sites/*.json` and the Technical Requirements above.

Before you complete this TODO:

```
TODO 05 - Compute Network & Gateway Locals
────────────────────────────────────────────────────────────────────────────────

[5] Computing network and gateway locals...

✗ TODO 05 Not Complete

The pipeline cannot continue because the network and gateway locals have
not been computed correctly yet.

Proceeding to detailed feedback...
```

After you complete it correctly:

```
TODO 05 - Compute Network & Gateway Locals
────────────────────────────────────────────────────────────────────────────────

[5] Computing network and gateway locals...
rdu01 -> 4 subnet(s) planned in 10.0.0.0/16, 2 gateway device(s) planned
aus02 -> 4 subnet(s) planned in 10.1.0.0/16, 2 gateway device(s) planned
sea03 -> 3 subnet(s) planned in 10.2.0.0/16, 1 gateway device(s) planned

✓ TODO 05 Complete
Every site's subnet CIDRs and every firewall device's gateway entry are
computed correctly.
```

---
