# TODO 10 — Detect and Reconcile Drift

## Topics Covered

```
✓ Drift - what it means for live infrastructure to stop matching Terraform's own configuration
✓ Why a check block reading a MANAGED RESOURCE's own attribute sees its planned value, not live drift
✓ Using a data source to see AWS's own current reality, unfiltered by any pending Terraform change
✓ terraform plan detecting a real, out-of-band change automatically, with no extra code
✓ terraform apply reconciling drift back to the declared configuration
```

## Recap

TODO 01 through TODO 09 are already solved in this folder. TODO 09 gave
you a `data` source that independently confirms live AWS state matches
what Terraform expects. Open `main.tf` and find `STUDENT WORK AREA - TODO
10`, right after TODO 09's own `branch_gateway_live_state` output.

## Scenario

Meridian Retail's branch network team has one explicit requirement before
this pipeline goes into production: **prove that drift detection and
reconciliation work against real infrastructure, not just in theory.**
Every check built so far has confirmed that Terraform's configuration,
Terraform's own state, and live AWS state all agree - but only ever at
one moment in time, right after an apply. None of them have tested what
happens *afterward*, and in the real world that's exactly when things go
wrong: an engineer opens the AWS console (or calls the API directly)
during an incident, adds a rule to unblock something quickly, and never
gets around to removing it. That's **drift** - live infrastructure
quietly diverging from what Terraform's configuration declares, with
nothing in Terraform's own history recording that it ever happened.

The test Meridian Retail wants is specific and literal: someone changes a
security group by hand, directly through the AWS API, completely
bypassing Terraform - and the very next `plan` has to notice, and the
very next `apply` has to fix it. A real API call against a real security
group, caught by a real plan, reverted by a real apply - nothing about
this gets simulated after the fact.

Drift can take any shape - a widened CIDR, an extra rule, a changed port
- and Terraform's own resource diffing already catches all of it, no
matter the shape, the moment the next `plan` runs, simply because
`aws_security_group`'s `ingress` list is the *complete, authoritative*
set. This TODO adds one more layer on top of that, aimed at the single
most dangerous shape drift can take here: ingress opened to `0.0.0.0/0`.
Every legitimate ingress rule this course has ever created is scoped to a
single zone's own subnet CIDR, never the entire internet, so a rule like
that can only mean something was added outside Terraform - and it's
exactly the kind of change Network Engineering wants flagged loudly, not
just quietly reverted on the next apply.

Here's a subtlety worth knowing before you write this check: you might
expect `aws_security_group.site["rdu01"].ingress` - the resource TODO 06
already created - to work directly inside a `check` block, the same way
TODO 07's checks read resources directly. It won't, for a specific
reason. Terraform evaluates a *managed resource's* own attribute as its
**planned** value - what that resource will look like once Terraform
finishes reconciling it back to your config - never the live, still-
drifted value sitting in AWS the moment before that reconciliation
happens. A `data` source has no such thing as a "planned value"; it just
reports whatever AWS says is true, right now. So genuinely observing
drift *before* it's fixed requires a real data source - not the resource
itself. The obvious candidate, `aws_security_group` (singular), turns out
not to expose `ingress`/`egress` at all. Its plural sibling,
`aws_security_groups`, can still answer the one question this check
actually needs - "does any of my own security groups currently have a
0.0.0.0/0 rule?" - by asking AWS's own API directly through a filter,
without ever needing to reconstruct the full rule list yourself.

## Before You Start: Check LocalStack Is Running

This TODO still needs LocalStack running in the background, the same as
TODO 06 through TODO 09 did:

```
curl http://localhost:4566/_localstack/health
```

You should get back JSON with "ec2": "available". If instead you get a
connection error, start it from this folder:

```
docker compose up -d
```

## Worked Example

`data "aws_security_groups" "rogue_ingress"` doesn't look up one security
group by id, the way TODO 09's data source did - it asks AWS's own
`DescribeSecurityGroups` API a yes/no question directly, using two
filters together (an AND, not an OR): *of these specific group ids, which
ones currently have an ingress rule allowing this specific CIDR?*

```
data.aws_security_groups.rogue_ingress
    filter "group-id"           = [rdu01's id, aus02's id, sea03's id]
    filter "ip-permission.cidr" = ["0.0.0.0/0"]
    -> asks AWS (LocalStack) directly, right now: of these 3 groups,
       which ones have a rule allowing 0.0.0.0/0?
    -> .ids = [] when the answer is "none of them"
```

`check "no_unauthorized_ingress_drift"` then just confirms that list came
back empty:

```
data.aws_security_groups.rogue_ingress.ids -> []
length(...) == 0 -> true, so the check reports "pass"
```

Now suppose someone adds a rule directly through the AWS API, allowing
`0.0.0.0/0` on port 9999 into `rdu01`'s security group - completely
bypassing Terraform. The very next `terraform plan` asks that same
question fresh, and that single plan now surfaces the drift twice, in two
independent ways:

```
terraform plan
    -> data.aws_security_groups.rogue_ingress.ids -> ["sg-...rdu01's id"]
    -> no_unauthorized_ingress_drift -> fail (your check block itself
       caught it, straight from AWS's own API)
    -> aws_security_group.site["rdu01"] has changed outside of Terraform
       (Terraform's own resource diffing caught it too, independently)

terraform apply
    -> the rogue rule is removed for real, reconciling rdu01's security
       group back to exactly what main.tf declares
    -> data.aws_security_groups.rogue_ingress.ids -> [] again
    -> no_unauthorized_ingress_drift -> pass again
```

Terraform never needed to be told a rule *might* appear - declaring
`ingress` as the complete list is what makes any addition to it, from any
source, show up as a change the very next time you plan. And because your
`data` source asks AWS directly every single time, it catches the same
drift on its own, in parallel with Terraform's built-in resource diffing
- not as a replacement for it.

## Steps

```
1. Open main.tf and find STUDENT WORK AREA - TODO 10, right after TODO
   09's own branch_gateway_live_state output. Everything you need already
   exists - aws_security_group.site was created by TODO 06.

2. Define these 2 blocks, in this order - top-level blocks, not nested
   inside anything else. Every name below is exactly what the grader
   looks for - do not rename them.

     data "aws_security_groups" "rogue_ingress" { ... }
     check "no_unauthorized_ingress_drift" { ... }

3. Define data "aws_security_groups" "rogue_ingress", with 2 filter
   blocks.

     filter "group-id":         values should be every one of
                                 aws_security_group.site's own ids, so
                                 this data source only ever looks at
                                 groups this course actually manages

     filter "ip-permission.cidr": values is already filled in below -
                                 ["0.0.0.0/0"], the one CIDR that should
                                 never legitimately appear

   Complete the skeleton below to meet the requirements given above:

     data "aws_security_groups" "rogue_ingress" {
       filter {
         name   = "group-id"
         values = ...
       }
       filter {
         name   = "ip-permission.cidr"
         values = ["0.0.0.0/0"]
       }
     }

4. Define check "no_unauthorized_ingress_drift".

     condition:     true only when that filtered lookup found nothing -
                    length() of data.aws_security_groups.rogue_ingress's
                    own ids, compared against 0

     error_message: any string describing what a failure here means -
                    Terraform requires the argument to be present, but
                    its exact wording is up to you

   Complete the skeleton below to meet the requirements given above:

     check "no_unauthorized_ingress_drift" {
       assert {
         condition     = ...
         error_message = ""
       }
     }

5. Save, then run: python grading.py
```

## Grading Check

```
python grading.py
```

The grader first applies your file for real against LocalStack (TODO 06
through TODO 09's resources included) - just enough to have a real
security group id to act on. It then immediately uses `boto3` to call the
AWS API directly and add a rogue `0.0.0.0/0` ingress rule to rdu01's
security group - entirely bypassing Terraform, exactly like someone
editing it by hand. From this point on, real drift exists, before your
code has had any chance to notice it yet.

It plans once and reads that one plan twice: `check
"no_unauthorized_ingress_drift"` should report `"fail"` (proof
data.aws_security_groups.rogue_ingress is actually asking AWS's own API
in real time, not hardcoded to always pass), and `aws_security_group.site
["rdu01"]` should independently show a pending change too.

It then runs `terraform apply` again to reconcile that drift for real,
and only now - against the freshly-reconciled state - reads back
`site_security_group_live_ingress` to confirm every site's ingress
matches the same CIDRs TODO 06 already created, with none of them
`0.0.0.0/0`, and confirms `no_unauthorized_ingress_drift` reports
`"pass"` again. Finally, it calls the AWS API directly one more time to
confirm, independently of anything Terraform reports, that the rogue rule
is actually gone.

Every apply above is followed by `terraform destroy`, so LocalStack is
never left holding resources between grading runs.

Before you complete this TODO:

```
TODO 10 - Detect and Reconcile Drift
────────────────────────────────────────────────────────────────────────────────

[10] Detecting and reconciling drift...

✗ TODO 10 Not Complete

The pipeline cannot continue because infrastructure drift has not been correctly
detected and reconciled yet.

Proceeding to detailed feedback...
```

After you complete it correctly:

```
TODO 10 - Detect and Reconcile Drift
────────────────────────────────────────────────────────────────────────────────

[10] Detecting and reconciling drift...
  Someone added a rogue 0.0.0.0/0 ingress rule to rdu01's security group
  directly through the AWS API, bypassing Terraform entirely.

  Detecting drift:
    terraform plan -> no_unauthorized_ingress_drift -> fail
    terraform plan -> aws_security_group.site["rdu01"] has a pending change

  Reconciling drift:
    terraform apply -> rogue rule reconciled

  Confirmed after reconciling:
    rdu01 -> live ingress confirmed independently, no unauthorized rules
    aus02 -> live ingress confirmed independently, no unauthorized rules
    sea03 -> live ingress confirmed independently, no unauthorized rules
    no_unauthorized_ingress_drift -> pass
    describe_security_groups -> confirms 0.0.0.0/0 is gone, verified independently

✓ TODO 10 Complete
A real, out-of-band change to rdu01's security group was correctly detected by
terraform plan and correctly reconciled by the next apply - verified
independently via the AWS API, not just Terraform's own state.
```

---
