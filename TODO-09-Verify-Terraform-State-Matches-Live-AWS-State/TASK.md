# TODO 09 — Verify Terraform State Matches Live AWS State

## Topics Covered

```
✓ data sources - reading live information from the provider, independent of anything Terraform manages
✓ Why a data source is queried fresh every single plan and apply, never cached
✓ Extending check blocks to assert against a live, independently fetched read
```

## Recap

TODO 01 through TODO 08 are already solved in this folder. TODO 06 gave
you real infrastructure; TODO 07 verifies its shape; TODO 08 proved
applying it again is safe. Open `main.tf` and find `STUDENT WORK AREA -
TODO 09`, right after TODO 08's own `branch_gateway_tags` output.

## Scenario

Every resource this lab has created so far - the VPCs, subnets, security
groups, branch gateways, even TODO 08's compliance tag - is something
Terraform itself owns. Terraform tracks each one in its own state, and
everything you've checked about them so far has come from that state:
`aws_instance.branch_gateway`'s own attributes, refreshed on every plan,
but still fundamentally Terraform's own record of what it believes is
true.

Network Engineering wants a stronger guarantee than that: proof that
what's actually running in AWS matches expectations, read in a way that
doesn't depend on Terraform's own bookkeeping being correct. That's what
a **data source** is for. Unlike a `resource` block, a `data` block never
creates or manages anything - it only reads, fresh, from the provider, on
every single plan and apply, and it never appears in a `terraform
destroy` because Terraform never owned it in the first place. Looking up
each branch gateway's live instance with a data source, independently of
`aws_instance.branch_gateway`'s own state, is what turns "Terraform
believes this is true" into "this was just confirmed, live, from AWS
itself."

## Before You Start: Check LocalStack Is Running

This TODO still needs LocalStack running in the background, the same as
TODO 06 through TODO 08 did:

```
curl http://localhost:4566/_localstack/health
```

You should get back JSON with "ec2": "available". If instead you get a
connection error, start it from this folder:

```
docker compose up -d
```

## Worked Example

For `rdu01-gw-primary`, `aws_instance.branch_gateway["rdu01-gw-primary"]`
already exists, with its own `id`. A data source looks that same
instance up again, independently:

```
data.aws_instance.branch_gateway_live["rdu01-gw-primary"]
    instance_id = aws_instance.branch_gateway["rdu01-gw-primary"].id
    -> queries AWS (LocalStack) directly for that instance_id
    -> returns that instance's own live attributes: instance_state,
       tags, and more - read fresh, this plan, not from Terraform's
       cached state
```

`check "live_state_matches_expected"` then confirms something about
every one of those live reads at once - specifically, that each live
lookup's own `tags["DeviceRole"]` still comes back `"branch-gateway"`:

```
data.aws_instance.branch_gateway_live["rdu01-gw-primary"].tags["DeviceRole"]   -> "branch-gateway"
data.aws_instance.branch_gateway_live["rdu01-gw-secondary"].tags["DeviceRole"] -> "branch-gateway"
data.aws_instance.branch_gateway_live["aus02-gw-primary"].tags["DeviceRole"]   -> "branch-gateway"
data.aws_instance.branch_gateway_live["aus02-gw-secondary"].tags["DeviceRole"] -> "branch-gateway"
data.aws_instance.branch_gateway_live["sea03-gw-primary"].tags["DeviceRole"]   -> "branch-gateway"

alltrue([...]) over all 5 -> true, so the check reports "pass"
```

## Notation Used Below

Every step below shows a skeleton with two kinds of blanks - the same
two, used the same way, all the way through this file:

```
""   - you're writing your own text here, not just plugging in an
       existing value. Sometimes that's a plain literal; sometimes
       it's a literal combined with a reference, using ${...}
       interpolation.

...  - you're plugging in an existing value directly, with nothing of
       your own added around it: a reference on its own, a lookup
       into a local, a for expression, or a reference to another
       resource's own attribute. This holds even when that value
       already happens to be a string, or a number.
```

## Steps

```
1. Open main.tf and find STUDENT WORK AREA - TODO 09, right after TODO
   08's own branch_gateway_tags output. Everything you need already
   exists - aws_instance.branch_gateway and local.branch_gateway_devices
   were both created by earlier TODOs.

2. Define these 2 blocks, in this order - top-level blocks, not nested
   inside anything else. Every name below is exactly what the grader
   looks for - do not rename them.

     data "aws_instance" "branch_gateway_live" { ... }
     check "live_state_matches_expected" { ... }

3. Define data "aws_instance" "branch_gateway_live", one per firewall
   device, so for_each = local.branch_gateway_devices - the exact same
   set aws_instance.branch_gateway itself already uses.

     instance_id: that same entry's own aws_instance.branch_gateway
                  instance's id - this is what tells the data source
                  which live instance to look up

   Complete the skeleton below to meet the requirements given above:

     data "aws_instance" "branch_gateway_live" {
       for_each    = local.branch_gateway_devices
       instance_id = ...
     }

4. Define check "live_state_matches_expected".

     condition:     true only when every single one of the live
                    lookups' own DeviceRole tag reads exactly
                    "branch-gateway" - a for expression over
                    data.aws_instance.branch_gateway_live, combined
                    with alltrue(), the same pattern TODO 07's own
                    check blocks already used

     error_message: any string describing what a failure here means -
                    Terraform requires the argument to be present, but
                    its exact wording is up to you

   Complete the skeleton below to meet the requirements given above:

     check "live_state_matches_expected" {
       assert {
         condition = alltrue([
           for k, d in data.aws_instance.branch_gateway_live : ...
         ])
         error_message = ""
       }
     }

5. Save, then run: python grading.py
```

## Grading Check

```
python grading.py
```

The grader applies your file for real against LocalStack (TODO 06
through TODO 08's resources included), then reads back
`branch_gateway_live_state` to confirm every firewall device's live
lookup found a real instance_state and the same tags TODO 06 already
set - all read back through your data source, not through
`aws_instance.branch_gateway`'s own state.

It also reads `check "live_state_matches_expected"`'s own status, the
same way TODO 07's checks are read - via `terraform show -json`'s checks
array - and confirms it reports `"pass"`.

Every `apply` above is followed by `terraform destroy`, so LocalStack is
never left holding resources between grading runs.

Before you complete this TODO:

```
TODO 09 - Verify Terraform State Matches Live AWS State
────────────────────────────────────────────────────────────────────────────────

[9] Verifying Terraform state matches live AWS state...

✗ TODO 09 Not Complete

The pipeline cannot continue because live AWS state has not been independently
verified yet.

Proceeding to detailed feedback...
```

After you complete it correctly:

```
TODO 09 - Verify Terraform State Matches Live AWS State
────────────────────────────────────────────────────────────────────────────────

[9] Verifying Terraform state matches live AWS state...
rdu01-gw-primary -> live state confirmed independently
rdu01-gw-secondary -> live state confirmed independently
aus02-gw-primary -> live state confirmed independently
aus02-gw-secondary -> live state confirmed independently
sea03-gw-primary -> live state confirmed independently
live_state_matches_expected -> pass

✓ TODO 09 Complete
data.aws_instance.branch_gateway_live independently confirms every branch
gateway's live AWS state, and live_state_matches_expected reports "pass".
```

---
