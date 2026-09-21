# TODO 04 — Build Environment- and Site-Aware Locals

## Topics Covered

```
✓ Building a lookup map once instead of searching a list repeatedly
✓ Resolving a per-site result from data spread across 3 independent sources
```

## Recap

TODO 01, 02, and 03 are already solved in this folder. Open `main.tf` and find `STUDENT WORK AREA - TODO 04`, right after the `preflight_ok` output.

## Scenario

TODO 03 proved every disabled zone role is at least real. It never asked the next question: for one specific site, which zones does that leave actually turned on?

That answer depends on all 3 of the sources this pipeline has loaded so far, at once: the intent says which zones are approved at all (`quarantine` never is), each site's environment says which of the approved zones are additionally held back there (staging disables `pos`), and each site's own `zone_ids` says what numeric ID that zone actually has on that specific appliance. TODO 05 is going to plan one subnet and one firewall rule per zone per site - it needs this TODO to have already worked out exactly which zones that is, for every site, before it can plan anything.

## Worked Example

Business requirements (from TODO 01): zones `corp`, `voice`, `pos`, `guest` are `enabled: true`; `quarantine` is `enabled: false`.

Environments (from TODO 02): `prod` disables nothing extra. `staging` disables `pos`.

Sites (from TODO 02): `rdu01` and `aus02` are `prod`. `sea03` is `staging`.

So the final result should resolve to:

```
site_zones = {
  rdu01 = [
    { role = "corp",  name = "RTL-CORP-FW",  id = 110 },
    { role = "voice", name = "RTL-VOICE-FW", id = 120 },
    { role = "pos",   name = "RTL-POS-FW",   id = 130 },
    { role = "guest", name = "RTL-GUEST-FW", id = 140 },
  ]
  aus02 = [
    { role = "corp",  name = "RTL-CORP-FW",  id = 210 },
    { role = "voice", name = "RTL-VOICE-FW", id = 220 },
    { role = "pos",   name = "RTL-POS-FW",   id = 230 },
    { role = "guest", name = "RTL-GUEST-FW", id = 240 },
  ]
  sea03 = [
    { role = "corp",  name = "RTL-CORP-FW",  id = 310 },
    { role = "voice", name = "RTL-VOICE-FW", id = 320 },
    { role = "guest", name = "RTL-GUEST-FW", id = 340 },
  ]
}
```

Notice `sea03` has no `pos` entry at all - not a `pos` entry with `enabled: false` on it, no entry. Notice also `quarantine` never appears anywhere, for any site - it was never in `enabled_zone_roles` to begin with, so there was never anything to remove it from later.

## Steps

```
1. Open main.tf and find STUDENT WORK AREA - TODO 04. TODO 02's and
   TODO 03's locals blocks, both above it, are already solved and
   marked "do not modify" - leave them alone. Terraform allows more
   than one locals block in the same file (they all merge into the
   same local.* namespace), so write a third, separate locals block
   inside STUDENT WORK AREA - TODO 04 instead of editing theirs.

   Unlike TODO 02, there's no empty locals { } already sitting there
   for you - the area is blank, so you write the whole block yourself,
   opening brace and all:

     locals {

     }

   The "resolved_zones" output right after this block already exists
   and isn't yours to write.

2. Inside that locals block, define exactly these 4 locals, in this
   order, each one built from the one before it:

     zone_names_by_role - { for z in local.service_intent.zones :
                            z.role => z.name }

     enabled_zone_roles - [ for z in local.service_intent.zones :
                            z.role if z.enabled ]

     site_zone_roles    - a map keyed by site_id. For each site, filter
                          enabled_zone_roles down to the roles NOT in
                          that site's own environment's disabled_zones.
                          local.environments[site.environment] gets you
                          from a site to its environment.

     site_zones         - a map keyed by site_id. For each site, turn
                          site_zone_roles[site_id] into a list of
                          objects: { role = role, name =
                          zone_names_by_role[role], id =
                          site.zone_ids[role] }

3. Save, then run: python grading.py
```

## Grading Check

```
python grading.py
```

The grader runs `terraform apply` and reads back the `resolved_zones` output with `terraform output -json` - never by reading your `main.tf` source as text. It checks the exact result in the Worked Example above, independently computed from `intent/`, `environments/`, and `sites/` - not by comparing to any specific way of writing the locals that produce it.

Before you complete this TODO:

```
TODO 04 - Build Environment- and Site-Aware Locals
────────────────────────────────────────────────────────────────────────────────

[4] Building environment- and site-aware locals...

✗ TODO 04 Not Complete

The pipeline cannot continue because the per-site resolved zones have not been
built correctly yet.

Proceeding to detailed feedback...
```

After you complete it correctly:

```
TODO 04 - Build Environment- and Site-Aware Locals
────────────────────────────────────────────────────────────────────────────────

[4] Building environment- and site-aware locals...
rdu01 -> corp, voice, pos, guest
aus02 -> corp, voice, pos, guest
sea03 -> corp, voice, guest

✓ TODO 04 Complete
Every site resolves to the correct zones, with each environment's overrides
correctly applied.
```

---
