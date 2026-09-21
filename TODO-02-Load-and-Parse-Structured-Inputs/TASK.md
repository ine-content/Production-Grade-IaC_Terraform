# TODO 02 — Load & Parse Structured Inputs

## Topics Covered

```
✓ Reading structured data into Terraform with jsondecode() and file()
```

## Recap

TODO 01 is already solved in this folder — `intent/branch_firewall_service.json` exists and is correct. Open `main.tf` and find `STUDENT WORK AREA - TODO 02`.

## Provided

```
environments/
  prod.json      (disabled_zones, auto_apply)
  staging.json   (disabled_zones, auto_apply)
sites/
  rdu01.json     (site_id, region, environment, zone_ids, firewalls)
  aus02.json
  sea03.json
```

Each site's `firewalls` is a list of that site's planned gateway devices — the same zone/firewall policy applies to the whole site, which is what makes a site's list an HA pair rather than two unrelated devices. RDU01 and AUS02 (prod, already live) each plan for a primary + secondary device. SEA03 (staging, still onboarding) plans for a single device for now — nothing about this TODO's code should assume every site has exactly one entry here, or exactly two.

Do not modify anything under `environments/` or `sites/`.

## Scenario

The intent file says *what* the firewall policy should be everywhere. It says nothing about *where* — which sites exist, which environment each one belongs to, or which environments are allowed to relax that policy (staging, newly onboarding, hasn't cut over its POS traffic yet).

That information already exists as files on disk — Store Operations keeps `sites/` current, and Network Engineering keeps `environments/` current — but nothing has loaded them into the pipeline yet. This TODO is that first load: turn the intent file, the environment files, and the site files into data Terraform can actually work with, before any validation or provisioning logic touches any of it.

There are exactly 2 environments and exactly 3 sites in this course, and that isn't going to change - so this TODO loads each one by name, directly. (A later TODO can revisit loading every file in a directory automatically, if you ever want a course with a variable number of sites - not needed here.)

## Steps

```
1. Open main.tf and find STUDENT WORK AREA - TODO 02. There's already
   an empty locals block there:

     locals {

     }

   Everything you write goes inside those braces. Don't add a second
   locals block, and don't touch anything outside STUDENT WORK AREA -
   the output block right after it already exists and isn't yours to
   write.

2. Inside that locals block, define exactly these 3 locals:

     service_intent - jsondecode the contents of
                       intent/branch_firewall_service.json

     environments    - a map with 2 keys, "prod" and "staging", each
                       value the jsondecode'd contents of
                       environments/prod.json and
                       environments/staging.json respectively.

     sites           - a map with 3 keys, "rdu01", "aus02", and "sea03",
                       each value the jsondecode'd contents of the
                       matching file in sites/.

   Each value is just jsondecode(file("${path.module}/<path>")) - the
   same pattern used 5 times over, once per file.

3. Save, then run: python grading.py
```

## Grading Check

```
python grading.py
```

The grader runs `terraform init` and `terraform apply` (there are no resources yet, so this is instant and makes no external calls), then reads the `loaded_inputs` output back with `terraform output -json` — never by reading your `main.tf` source as text. A locals block that produces the right values in a different shape, or in a different order, passes just as well as the one in the solution.

Before you complete this TODO:

```
TODO 02 - Load & Parse Structured Inputs
────────────────────────────────────────────────────────────────────────────────

[2] Loading and parsing structured inputs...

✗ TODO 02 Not Complete

The pipeline cannot continue because the structured inputs have not been loaded
and parsed correctly yet.

Proceeding to detailed feedback...
```

After you complete it correctly:

```
TODO 02 - Load & Parse Structured Inputs
────────────────────────────────────────────────────────────────────────────────

[2] Loading and parsing structured inputs...
service_intent, environments, and sites all loaded and match the source files.

✓ TODO 02 Complete
main.tf loads the service intent, both environments, and all 3 sites correctly.
```

---
