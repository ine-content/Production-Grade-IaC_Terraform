# TODO 12 — Emit a Structured Audit Log

## Topics Covered

```
✓ Why Terraform's own state is not an audit trail - it only ever tracks the current shape
✓ for_each over a growing set as the way to add records without disturbing old ones
✓ Why aws_s3_object treats bucket + key as identity, and what changing key actually does
✓ jsonencode() - building a structured, machine-readable record from plain Terraform values
✓ Proving "additive, not overwritten" directly from a plan's own resource_changes
```

## Recap

TODO 01 through TODO 11 are already solved in this folder. Open `main.tf`
and find `STUDENT WORK AREA - TODO 12`, right after TODO 10's own
`site_security_group_live_ingress` output. TODO 11 doesn't add anything
here - its own work lives inside the `terraform {}` block at the very top
of the file, untouched by this TODO.

## Scenario

Terraform's state is very good at answering one question: what does this
infrastructure look like *right now*. It is not built to answer a
different one Meridian Retail's compliance team actually cares about -
*what happened, and when*. State gets overwritten on every apply by
design; an audit trail is supposed to do the opposite. So this TODO adds
something new to this pipeline: a durable, append-only record, written to
the same S3 bucket TODO 11 already set up, that never gets overwritten,
no matter how many times this pipeline runs.

`audit/apply_log.json` already exists in this folder, with one timestamp
in it - proof this pipeline has already been applied once before you ever
touched it. Every time it gets applied again, one more timestamp gets
appended to that file (the grader does this for you, between two applies,
to represent time actually passing between real runs of this pipeline).
Your job is to make sure every timestamp that has *ever* appeared in that
file ends up with its own permanent, independent record in S3.

Here's the part worth understanding before you write a single line:
`aws_s3_object` treats `bucket` and `key` together as that object's
entire identity - AWS itself has no concept of "renaming" an object, so
the moment `key`'s value changes, Terraform has no choice but to delete
the old object and create a brand new one under the new key. That's a
real, permanent fact about this resource type, not a guess - confirmed
directly against the AWS provider's own source before this TODO was
written. It means a *single* `aws_s3_object` whose `key` embeds something
that changes on every apply (`timestamp()`, evaluated fresh every time,
for instance) would delete its own previous record on every single
apply - the exact opposite of an audit trail.

`for_each` is what avoids this. Once a `for_each` instance exists, its own
key (in Terraform's sense) never changes on its own - so the `key`
argument you build from `each.value` never changes for it either, and
Terraform leaves it completely alone. Only a genuinely *new* entry in the
`for_each` set ever produces a genuinely new object. A list that only ever
grows, turned into a `for_each` set, is what makes this an actual
append-only trail rather than a rotating single file.

## Before You Start: Check LocalStack Is Running

This TODO still needs LocalStack running in the background, the same as
TODO 06 through TODO 11 did:

```
curl http://localhost:4566/_localstack/health
```

You should get back JSON with `"s3": "available"`. If instead you get a
connection error, start it from this folder:

```
docker compose up -d
```

## Worked Example

Say `audit/apply_log.json` currently holds one timestamp:

```
["2026-01-05T09:00:00Z"]
```

`local.audit_entries` turns that into a set, and `for_each` creates one
`aws_s3_object` instance per entry in it:

```
local.audit_entries -> toset(["2026-01-05T09:00:00Z"])

aws_s3_object.apply_audit_log["2026-01-05T09:00:00Z"]
    key     -> "audit-log/2026-01-05T09:00:00Z.json"
    content -> {"applied_at": "2026-01-05T09:00:00Z", "site_count": 3,
                "gateway_count": 5, "sites": ["aus02", "rdu01", "sea03"]}
```

Now suppose this pipeline gets applied again, and by the time it does,
one more timestamp has been appended to `audit/apply_log.json`:

```
["2026-01-05T09:00:00Z", "2026-03-12T14:30:00Z"]
```

`local.audit_entries` is now a set with 2 members instead of 1 - and
`for_each` reacts to that exactly the way it's supposed to:

```
terraform plan
    -> aws_s3_object.apply_audit_log["2026-01-05T09:00:00Z"] -> no-op
       (this instance's own for_each key didn't change, so neither did
       its key argument - nothing about it is even touched)
    -> aws_s3_object.apply_audit_log["2026-03-12T14:30:00Z"] -> create
       (a genuinely new for_each key, so a genuinely new object)

terraform apply
    -> the January record is still sitting in S3, completely undisturbed
    -> a brand new March record now exists right alongside it
```

Nothing about the first record's own key, content, or existence in S3 was
ever affected by the second apply - that's the entire point.

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
1. Open main.tf and find STUDENT WORK AREA - TODO 12, right after TODO
   10's own site_security_group_live_ingress output. Everything you need
   already exists - local.sites and local.branch_gateway_devices were
   built by TODO 02 and TODO 05.

2. Define these 2 things, in this order - top-level, not nested inside
   anything else. Every name below is exactly what the grader looks for -
   do not rename them.

     locals {
       audit_entries = ...
     }

     resource "aws_s3_object" "apply_audit_log" { ... }

3. Define local.audit_entries: every timestamp currently in
   audit/apply_log.json, as a SET, not a list - for_each requires a set
   or a map, never a plain list.

     locals {
       audit_entries = toset(jsondecode(file("${path.module}/audit/apply_log.json")))
     }

4. Define resource "aws_s3_object" "apply_audit_log", for_each over
   local.audit_entries.

     bucket:       "meridian-retail-tfstate" - the same bucket TODO 11's
                   backend already uses, under a different key prefix

     key:          "audit-log/${each.value}.json" - each.value here is
                   the timestamp itself, since audit_entries is a set of
                   plain strings

     content:      jsonencode({...}) - a JSON object recording at least
                   applied_at (each.value), site_count
                   (length(local.sites)), gateway_count
                   (length(local.branch_gateway_devices)), and sites
                   (keys(local.sites))

   Complete the skeleton below to meet the requirements given above:

     resource "aws_s3_object" "apply_audit_log" {
       for_each     = ...
       bucket       = "meridian-retail-tfstate"
       key          = ...
       content_type = "application/json"

       content = jsonencode({
         applied_at    = ...
         site_count    = ...
         gateway_count = ...
         sites         = ...
       })
     }

5. Save, then run: python grading.py
```

## Grading Check

```
python grading.py
```

The grader applies your file for real, in a scratch copy, against
whatever is currently in that copy's own `audit/apply_log.json` (one
seed timestamp). It reads back `terraform output -json
apply_audit_log_keys` and confirms exactly one `audit-log/<timestamp>.json`
key exists per timestamp in that file - then independently, via the AWS
API directly (never `terraform show`, never a Terraform output), confirms
that object genuinely exists in S3 with the right `site_count`,
`gateway_count`, and `sites`.

It then appends one brand new timestamp directly to that same scratch
copy's `audit/apply_log.json` - simulating this pipeline being applied
again later - and plans again against the exact same state, with no
destroy in between. It reads that plan's own `resource_changes` and
confirms every instance keyed by an *already-existing* timestamp plans as
`"no-op"`, while only the instance keyed by the brand new timestamp plans
as `"create"`. That's the actual proof this is additive, not a rotating
single file - a check hardcoded to always create fresh objects, or one
that accidentally rebuilds everything from `key = timestamp()` directly,
would get caught right here.

Finally, it applies that second plan for real and independently
reconfirms, via the AWS API, that every object - the original and the new
one alike - genuinely exists in S3.

Every apply above is followed by `terraform destroy`, so LocalStack is
never left holding resources between grading runs. This folder's own
`audit/apply_log.json` is never touched by any of this - only a scratch
copy's.

Before you complete this TODO:

```
TODO 12 - Emit a Structured Audit Log
────────────────────────────────────────────────────────────────────────────────

[12] Emitting a structured audit log...

✗ TODO 12 Not Complete

The pipeline cannot continue because a structured, append-only audit log has not
been correctly emitted yet.

Proceeding to detailed feedback...
```

After you complete it correctly:

```
TODO 12 - Emit a Structured Audit Log
────────────────────────────────────────────────────────────────────────────────

[12] Emitting a structured audit log...
  terraform apply -> 1 audit record written for the existing timestamp
  audit/apply_log.json -> 1 new timestamp appended, simulating time passing
  terraform plan  -> every earlier audit record -> no-op
  terraform plan  -> the new timestamp's own record -> create
  terraform apply -> reconciled, no earlier record touched or replaced
  s3://meridian-retail-tfstate/audit-log/*.json -> every record confirmed
  independently via the AWS API

✓ TODO 12 Complete
aws_s3_object.apply_audit_log writes one independent, permanent record per apply
into S3 - verified by applying twice and confirming every earlier record
survived untouched while exactly one new record appeared.
```

---
