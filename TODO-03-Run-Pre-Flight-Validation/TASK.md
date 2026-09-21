# TODO 03 — Run Pre-Flight Validation

## Topics Covered

```
✓ Cross-referencing two independently-maintained data sources
✓ Hard-failing terraform apply with a precondition, before any provisioning logic runs
```

## Recap

TODO 01 and TODO 02 are already solved in this folder. Open `main.tf` and find `STUDENT WORK AREA - TODO 03`, right after the `loaded_inputs` output.

## Scenario

Network Engineering keeps `environments/*.json` current. Store Operations keeps `intent/branch_firewall_service.json` current. Nobody who edits one of those files is required to check the other one first — and nothing has stopped someone from typing a zone role into an environment's `disabled_zones` list that doesn't actually exist in the intent. Today that's a silent no-op. In a bigger course it'd be the kind of typo that ships to production without anyone noticing until an audit.

This TODO catches that before anything gets provisioned: every zone role any environment tries to disable must be a real zone role, defined in the intent. If it isn't, the whole run stops right here — not partway through creating firewall resources later.

## Steps

```
1. Open main.tf and find STUDENT WORK AREA - TODO 03. TODO 02's locals
   block, right above it, is already solved and marked "do not modify" -
   leave it alone. Terraform allows more than one locals block in the
   same file (they all merge into the same local.* namespace), so write
   a second, separate locals block inside STUDENT WORK AREA - TODO 03
   instead of editing TODO 02's.

2. In that new locals block, define exactly these 2 locals:

     valid_zone_roles    - a plain list of every zone role in
                           local.service_intent.zones, e.g.
                           ["corp", "voice", "pos", "guest", "quarantine"]

     disabled_zones_flat - every environment's disabled_zones list,
                           flattened into one plain list. Use flatten()
                           over a for expression across
                           local.environments.

3. Write one output block:

     output "preflight_ok" {
       value = true

       precondition {
         condition     = <true only if every entry in
                          disabled_zones_flat is also in
                          valid_zone_roles>
         error_message = "<something that explains what went wrong>"
       }
     }

   Use alltrue() and contains() for the condition - true only when
   every disabled zone role genuinely exists.

4. Save, then run: python grading.py
```

## Grading Check

```
python grading.py
```

The grader doesn't just check that `terraform apply` succeeds on the files as they are today - a `condition = true` stub would pass that too, without validating anything. Instead it temporarily adds an unknown zone role ("gust") to `environments/staging.json`, runs `terraform apply`, and requires it to fail. Then it restores the file and requires a clean `terraform apply` to succeed. Only a precondition that's actually wired to the real data can pass both halves of that test.

Before you complete this TODO:

```
TODO 03 - Run Pre-Flight Validation
────────────────────────────────────────────────────────────────────────────────

[3] Running pre-flight validation...

✗ TODO 03 Not Complete

The pipeline cannot continue because pre-flight validation is not actually being
executed.

Proceeding to detailed feedback...
```

After you complete it correctly:

```
TODO 03 - Run Pre-Flight Validation
────────────────────────────────────────────────────────────────────────────────

[3] Running pre-flight validation...
Injected an unknown zone role ("gust") into environments/staging.json:
  terraform apply -> failed as expected
Restored environments/staging.json:
  terraform apply -> succeeded, pre-flight validation passed

✓ TODO 03 Complete
Pre-flight validation is running and correctly catches a bad cross-file reference.
```

---
