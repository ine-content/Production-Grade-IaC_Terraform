# TODO 07 — Run terraform plan and Verify Against Expected Changes

## Topics Covered

```
✓ check blocks - a native Terraform feature (>= 1.5) for post-apply/plan verification
✓ assert - a check block's own condition + error_message
✓ Why a failing check is a warning, never a blocking error
✓ startswith(), length(), and alltrue() - filtering and verifying for_each resources
```

## Recap

TODO 01 through TODO 06 are already solved in this folder. TODO 06 gave
you real infrastructure - every site's VPC, subnets, route table,
security group, and branch gateway instance(s) already exist in
LocalStack. Open `main.tf` and find `STUDENT WORK AREA - TODO 07`, right
after TODO 06's own `branch_gateways` output.

## Scenario

Meridian Retail's branch network team doesn't just want their
infrastructure provisioned correctly once - they want it independently
verified against the live state, every single time, without anyone
having to remember to check by hand. TODO 06 already created every VPC,
subnet, route table, security group, and branch gateway instance this
lab needs. What's still missing is a live, automatic answer to one
question: did it actually turn out the way the network plan said it
should?

That's what this TODO builds. Terraform's `check` block (>= 1.5) exists
exactly for this - a small, named block whose own `assert` runs after
everything else, on every `plan` and every `apply`, and reports pass or
fail without ever blocking the run itself. A failing check is
deliberately only a **warning**, never an error: it's meant to catch
drift or a bad edit and surface it loudly, not to hold up firewall
changes reaching a branch because a sanity check tripped.

You'll define 2 check blocks: one confirming every site ended up with
the right number of subnets, one confirming every site ended up with the
right number of branch gateway instances - each checked against a fixed,
independent number, never against anything this file already computed.

## Before You Start: Check LocalStack Is Running

This TODO still needs LocalStack running in the background, the same as
TODO 06 did:

```
curl http://localhost:4566/_localstack/health
```

You should get back JSON with "ec2": "available". If instead you get a
connection error, start it from this folder:

```
docker compose up -d
```

## Technical Requirements

Both check blocks compare against these fixed numbers - not against
`local.site_subnets` or `local.branch_gateway_devices`, and not against
anything else computed elsewhere in this file. The whole point of a
check block is to verify the *real*, already-created resources
(`aws_subnet.zone`, `aws_instance.branch_gateway`) against a number that
was decided independently, up front - not to recompute the same value
twice and compare it to itself, which would never be able to catch a
real mistake.

| Site  | Expected Subnets | Expected Gateway Devices |
|-------|-------------------|---------------------------|
| rdu01 | 4                 | 2                         |
| aus02 | 4                 | 2                         |
| sea03 | 3                 | 1                         |

Every `aws_subnet.zone` key looks like `"rdu01-corp"` - that site's own
id, a dash, then the zone role. Every `aws_instance.branch_gateway` key
looks like `"rdu01-gw-primary"` - that site's own id, a dash, then the
device's own name. `startswith(key, "rdu01-")` is how you test a key
belongs to a given site.

## Worked Example

Take `rdu01` through `subnet_counts_match_expected` first. Start from
every key `aws_subnet.zone` has, across all 3 sites - then keep only the
ones `startswith(key, "rdu01-")` is true for:

```
aws_subnet.zone's keys, filtered to startswith(key, "rdu01-"):

  rdu01-corp
  rdu01-voice
  rdu01-pos
  rdu01-guest

length(...) of that filtered list -> 4
rdu01's row in the table above    -> 4
4 == 4, so this comparison is true.
```

`aus02` and `sea03` each get their own filtered list, the same way,
compared against their own row in the table. `alltrue([...])` is what
combines all 3 sites' true/false results into the single true/false
`subnet_counts_match_expected` itself reports.

`gateway_counts_match_expected` works identically, just starting from
`aws_instance.branch_gateway`'s keys instead of `aws_subnet.zone`'s:

```
aws_instance.branch_gateway's keys, filtered to startswith(key, "rdu01-"):

  rdu01-gw-primary
  rdu01-gw-secondary

length(...) of that filtered list -> 2
rdu01's row in the table above    -> 2
2 == 2, so this comparison is true.
```

Only once every site's comparison is true, in both check blocks, do
both report "pass".

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
1. Open main.tf and find STUDENT WORK AREA - TODO 07, right after TODO
   06's own branch_gateways output. Everything you need already exists
   - aws_subnet.zone and aws_instance.branch_gateway were both created
   by TODO 06. This TODO is only about verifying them - no resources or
   locals of your own this time.

2. Define these 2 check blocks, in any order - top-level blocks, not
   nested inside anything else. Every check name below is exactly what
   the grader looks for - do not rename them.

     check "subnet_counts_match_expected" { ... }
     check "gateway_counts_match_expected" { ... }

3. Define check "subnet_counts_match_expected".

   Each of the 3 blanks below is its own separate count - one per
   site. Each one follows the same shape:

     for k in keys(aws_subnet.zone) : true if startswith(k, "<site>-")

   k is a name you choose yourself, the same as any for expression -
   bound to each key aws_subnet.zone has (e.g. "rdu01-corp").
   keys(aws_subnet.zone) gives you just those key strings, with no
   values attached - you don't need the subnet objects themselves
   here, only their keys, so there's nothing to bind a second loop
   variable to. The if clause keeps only the entries whose key belongs
   to one specific site; the : true just needs to produce something,
   anything, for each surviving entry - only the count matters here,
   never the content, since the whole thing gets wrapped in length()
   next to turn that filtered list into a plain number.

   Fill in the skeleton so that:

     each blank    - length() of a for expression like the one above,
                     one per site, using that site's own prefix
                     ("rdu01-", "aus02-", "sea03-")

     error_message - free-form text describing what a failure here
                     means - Terraform requires the argument to be
                     present, but its exact wording isn't checked

   The whole condition is true only when all 3 of those per-site
   counts match their own expected number from the Technical
   Requirements table above (already filled in below, as the numbers
   being compared against) - alltrue() is what combines the 3
   individual true/false comparisons into that single result.

   Complete the skeleton below to meet the requirements given above:

     check "subnet_counts_match_expected" {
       assert {
         condition = alltrue([
           ... == 4,   # rdu01
           ... == 4,   # aus02
           ... == 3,   # sea03
         ])
         error_message = ""
       }
     }

4. Define check "gateway_counts_match_expected". Same idea as step 3,
   just a different resource and a different expected table column:

     for k in keys(aws_instance.branch_gateway) : true if startswith(k, "<site>-")

   k is a name you choose yourself again - bound to each key
   aws_instance.branch_gateway has (e.g. "rdu01-gw-primary").

   Fill in the skeleton so that:

     each blank    - length() of a for expression like the one above,
                     one per site, using that site's own prefix
                     ("rdu01-", "aus02-", "sea03-")

     error_message - free-form text describing what a failure here
                     means - Terraform requires the argument to be
                     present, but its exact wording isn't checked

   Compared against each site's own expected gateway device count from
   the same Technical Requirements table (already filled in below),
   combined with alltrue() the same way as step 3.

   Complete the skeleton below to meet the requirements given above:

     check "gateway_counts_match_expected" {
       assert {
         condition = alltrue([
           ... == 2,   # rdu01
           ... == 2,   # aus02
           ... == 1,   # sea03
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

The grader applies your file for real against LocalStack (TODO 06's
resources included), then reads back both check blocks' own pass/fail
status with `terraform show -json` - never by reading your `main.tf`
source as text, and never by scraping `apply`'s own log output (a
passing check never prints anything there - only a failing one does).
Against the real, unmodified data, both checks should report "pass".

Then it proves your checks are actually evaluating something real, not
just hardcoded to always say "pass": it temporarily removes one of
`rdu01`'s two branch gateway devices from `sites/rdu01.json`, re-applies,
and confirms `gateway_counts_match_expected` correctly flips to "fail".
`sites/rdu01.json` is always restored afterward, whether this passes or
not.

Every `apply` above is followed by `terraform destroy`, so LocalStack is
never left holding resources between grading runs.

Before you complete this TODO:

```
TODO 07 - Run terraform plan and Verify Against Expected Changes
────────────────────────────────────────────────────────────────────────────────

[7] Running terraform plan and verifying against expected changes...

✗ TODO 07 Not Complete

The pipeline cannot continue because the verification check blocks have not
been defined correctly yet.

Proceeding to detailed feedback...
```

After you complete it correctly:

```
TODO 07 - Run terraform plan and Verify Against Expected Changes
────────────────────────────────────────────────────────────────────────────────

[7] Running terraform plan and verifying against expected changes...
rdu01 -> 4 subnets (expected 4), 2 gateways (expected 2)
aus02 -> 4 subnets (expected 4), 2 gateways (expected 2)
sea03 -> 3 subnets (expected 3), 1 gateways (expected 1)
subnet_counts_match_expected  -> pass
gateway_counts_match_expected -> pass

✓ TODO 07 Complete
Both check blocks are defined correctly and correctly flag a real fault when
one is injected.
```

---
