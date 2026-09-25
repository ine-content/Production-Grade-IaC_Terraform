# TODO 08 — Apply Idempotently

## Topics Covered

```
✓ Idempotency - why re-running apply should never show new changes
✓ aws_ec2_tag - tagging an existing resource as its own, independent resource
✓ timestamp() - a function that returns a different value every single plan
✓ lifecycle - ignore_changes, and why some attributes need to be excluded from diffing
```

## Recap

TODO 01 through TODO 07 are already solved in this folder. TODO 06 gave
you real infrastructure; TODO 07 gave you two check blocks that verify
it. Open `main.tf` and find `STUDENT WORK AREA - TODO 08`, right after
TODO 07's own `gateway_counts_match_expected` check block.

## Scenario

Meridian Retail's branch network team doesn't just want their
infrastructure provisioned correctly once - they want it independently
verified against the live state, every single time, without anyone
having to remember to check by hand. TODO 07 already built that
verification layer. What's still missing is the guarantee underneath all
of it: that running `terraform apply` again, with nothing meaningfully
changed, is always safe - it should never show a surprise change, never
touch something it doesn't need to, and never behave differently the
second time than the first. That guarantee is called **idempotency**,
and it's the whole reason a pipeline (or a person) can re-run `apply` on
a schedule, after a restart, or just to be sure, without worrying it
will do something different.

Network Engineering wants one more thing recorded on every branch
gateway: a `LastVerified` tag, so anyone looking at a gateway in the AWS
console can see it was provisioned and confirmed by this pipeline.
You'll add that tag as its own resource - `aws_ec2_tag` - rather than
folding it into `aws_instance.branch_gateway`'s own `tags` block (which
TODO 06 already owns). That separation matters here for
a second reason too: it's what makes the idempotency lesson concrete.
A tag stamped with the *current time* changes every single plan by
definition - so writing this resource naively would break the very
guarantee this TODO is about. Getting it right means telling Terraform,
explicitly, to stop caring about that one attribute once it's set.

## Before You Start: Check LocalStack Is Running

This TODO still needs LocalStack running in the background, the same as
TODO 06 and TODO 07 did:

```
curl http://localhost:4566/_localstack/health
```

You should get back JSON with "ec2": "available". If instead you get a
connection error, start it from this folder:

```
docker compose up -d
```

## Worked Example

`aws_ec2_tag` is a real resource in its own right - not an attribute
inside `aws_instance.branch_gateway`, but a separate thing that points
*at* an existing resource by its id and attaches one tag to it:

```
aws_ec2_tag.branch_gateway_last_verified["rdu01-gw-primary"]
    resource_id = aws_instance.branch_gateway["rdu01-gw-primary"].id
    key         = "LastVerified"
    value       = timestamp()   # e.g. "2026-09-16T14:03:22Z" this plan,
                                 # "2026-09-16T14:03:47Z" the next one -
                                 # a different string, every time
```

Without any further instruction, Terraform would see `value` come back
different on every plan and want to update it - forever. That's a
perpetual diff, not idempotency. Adding a `lifecycle` block fixes it:

```
  lifecycle {
    ignore_changes = [value]
  }
```

`ignore_changes = [value]` tells Terraform: once this resource is
created, stop comparing `value` against what's currently configured -
whatever got set at creation time stays, and no future plan will ever
propose changing it again. With that in place, a `terraform plan` run
immediately after `terraform apply` - same state, nothing changed -
reports:

```
No changes. Your infrastructure matches the configuration.
```

That's what a correctly idempotent apply looks like.

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
1. Open main.tf and find STUDENT WORK AREA - TODO 08, right after TODO
   07's own gateway_counts_match_expected check block. Everything you
   need already exists - aws_instance.branch_gateway and
   local.branch_gateway_devices were both created by earlier TODOs.

2. Define aws_ec2_tag.branch_gateway_last_verified, one per firewall
   device, so for_each = local.branch_gateway_devices - the exact same
   set aws_instance.branch_gateway itself already uses. resource_id
   should reference that same entry's own aws_instance.branch_gateway
   instance's id. key and value are already filled in
   below - key is the fixed, literal string "LastVerified"; value uses
   timestamp(), which is exactly what makes the lifecycle block below
   necessary.

   Add a lifecycle block whose ignore_changes tells Terraform to stop
   tracking this resource's own value attribute after it's first
   created - without it, every later apply will show this resource
   changing, forever, exactly as described in the Worked Example above.

   Complete the skeleton below to meet the requirements given above:

     resource "aws_ec2_tag" "branch_gateway_last_verified" {
       for_each    = local.branch_gateway_devices
       resource_id = ...
       key         = "LastVerified"
       value       = timestamp()

       lifecycle {
         ignore_changes = [...]
       }
     }

3. Save, then run: python grading.py
```

## Grading Check

```
python grading.py
```

The grader applies your file for real against LocalStack (TODO 06 and
TODO 07's resources included), then reads back `branch_gateway_tags` to
confirm every firewall device got tagged `LastVerified` with a real
value.

Then, immediately after that same apply - same state, nothing destroyed
or reapplied in between - it plans again and reads back the planned
action for each `aws_ec2_tag.branch_gateway_last_verified` instance
specifically (via `terraform show -json` on the saved plan). Every one
of them should plan as `"no-op"` - nothing to add, change, or destroy.
The grader deliberately checks only this one resource's own planned
action, not the plan's overall result: LocalStack's EC2 mock can show
unrelated drift elsewhere that has nothing to do with this TODO, and
that should never be held against you here - only whether your own
`lifecycle.ignore_changes` is doing its job is graded. Both the tags and
this "no-op" result have to be correct for this TODO to pass.

Every `apply` above is followed by `terraform destroy`, so LocalStack is
never left holding resources between grading runs.

Before you complete this TODO:

```
TODO 08 - Apply Idempotently
────────────────────────────────────────────────────────────────────────────────

[8] Applying idempotently...

✗ TODO 08 Not Complete

The pipeline cannot continue because applying the same configuration twice
does not yet produce zero changes.

Proceeding to detailed feedback...
```

After you complete it correctly:

```
TODO 08 - Apply Idempotently
────────────────────────────────────────────────────────────────────────────────

[8] Applying idempotently...
rdu01-gw-primary -> LastVerified tag present
rdu01-gw-secondary -> LastVerified tag present
aus02-gw-primary -> LastVerified tag present
aus02-gw-secondary -> LastVerified tag present
sea03-gw-primary -> LastVerified tag present
terraform apply    -> 5 added, 0 changed, 0 destroyed
terraform plan     -> No changes. Your infrastructure matches the configuration.

✓ TODO 08 Complete
aws_ec2_tag.branch_gateway_last_verified is defined correctly, and a second
apply - with nothing meaningfully changed - produces zero further changes.
```

---
