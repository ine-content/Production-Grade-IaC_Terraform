---
# TODO 01 — Author the Declarative Network Intent
---

<details>
<summary><strong>Overview</strong></summary>

This course combines the major concepts of production-grade Infrastructure as Code, built entirely with Terraform:

```
✓ Declarative Authoring
✓ Pre-Flight Validation
✓ Environment-Aware Policy Overrides
✓ Plan-Verified, Idempotent Provisioning
✓ Independent Live-State Verification
✓ Drift Detection and Reconciliation
✓ Remote State with Locking
✓ Guarded Teardown
✓ Structured Logging
```

The goal is not to write a large Terraform configuration. The goal is to engineer a provisioning pipeline that is safe to run in production, repeatedly, without supervision — starting from nothing but a business requirement.

There is no Ansible anywhere in this course. There is no hand-written Python pipeline either. Everything is pure Terraform.

</details>

---

<details>
<summary><strong>Business Scenario</strong></summary>

```
- Meridian Retail hosts each branch's network in AWS - one VPC per site, with a
  subnet per firewall zone and a security group carrying that site's policy.
  That policy has always been clicked in by hand, directly in the AWS Console.
  During a routine change, someone fat-fingered a security group rule at a live
  site and accidentally opened POS traffic to the guest network. Nobody caught
  it until the PCI audit did.

- Leadership has mandated a production-grade replacement:

  • No console clicking - every change goes through code
  • No hand-waved requirements - the intent must be written down
  • No unverified plan - every apply is checked against what was expected first
  • No silent rewrites of unchanged infrastructure
  • Every run must prove its own correctness, before AND after apply
  • No untracked drift - an out-of-band change must be caught, not ignored
  • No local-only state file a single laptop could lose or corrupt
  • No destroying a production site by accident

- The policy must be provisioned - and, for staging, actually applied to live
  AWS infrastructure - across 3 branch sites:
  • RDU01  (Raleigh   - prod)
  • AUS02  (Austin    - prod)
  • SEA03  (Seattle   - staging, newly onboarding)

- There is no real AWS account required for this course. LocalStack, a local AWS
  emulator, stands in for it starting TODO 06 - from Terraform's point of view,
  using the real, official hashicorp/aws provider, it is indistinguishable from
  real AWS. terraform plan, apply, state, and destroy all behave exactly as they
  would against a real account.

- You are provided:
  • Environment policy files (prod and staging - which zones each environment
    is allowed to enable, and whether auto-apply is permitted)
  • Three site files (per-site zone IDs, and each site's planned gateway
    device inventory)
  • A milestone-based grader

- You are NOT provided the declarative network intent. You write it yourself, from
  the requirements below, before anything else can run.
```

</details>

---

<details>
<summary><strong>Final Pipeline</strong></summary>

```
Author Declarative Network Intent
        ↓
Load & Parse Structured Inputs
        ↓
Run Pre-Flight Validation
        ↓
Build Environment- and Site-Aware Locals
        ↓
Define AWS Network & Firewall Resources
        ↓
Run terraform plan and Verify Against Expected Changes
        ↓
Apply Idempotently
        ↓
Verify Terraform State Matches Live AWS State
        ↓
Detect and Reconcile Drift
        ↓
Configure Remote State Backend & Locking
        ↓
Safe, Guarded Teardown for Decommissioned Sites
        ↓
Emit a Structured Audit Log
```

Each stage becomes one lesson (TODO 02 through TODO 12), always written as native Terraform - `variable`, `locals`, `resource`, `terraform plan`, `terraform apply`, `terraform state` - never a hand-rolled Python or Ansible equivalent of what Terraform already does for you.

</details>

---

<details>
<summary><strong>Lab Files</strong></summary>

Run all commands from this lab's own directory.

```
TODO-01-Author-the-Declarative-Network-Intent/
├── intent/
│   └── (empty — you create branch_firewall_service.json here, TODO 01)
├── grading.py
├── TASK.md
```

You will create:

```
intent/branch_firewall_service.json
```

Do not modify:

```
grading.py
```

</details>

---

<details>
<summary><strong>How This Lab Works</strong></summary>

There is no Terraform configuration to run yet — this TODO has no code, only a file to author by hand. Later TODOs (2 through 12) introduce Terraform configuration one stage at a time; the grader runs each stage for you.

</details>

---

<details>
<summary><strong>Run the grader</strong></summary>

```
python grading.py
```

Note: TODO 01 is checked directly by reading the JSON file you create — the grader does not need anything else running to check it, because there is nothing to run until the intent file exists.

</details>

---

# TODO 01 — Author the Declarative Network Intent

## Topics Covered

```
✓ Declarative Authoring
✓ Structured Data Modeling in JSON
```

## Business Requirements

```
- Store Operations and Network Engineering have agreed on the following requirements for the standard branch firewall service:
  - Tenant:              Meridian Retail

  - Service identifier:  branch-firewall-standard

  - A dedicated firewall zone for corporate user devices.
        role: corp        name: RTL-CORP-FW        enabled: true

  - A dedicated firewall zone for VoIP handsets.
        role: voice       name: RTL-VOICE-FW       enabled: true

  - A dedicated firewall zone for point-of-sale devices. This is the
    zone the PCI audit finding was about - it must exist and be
    isolated from every other zone.
        role: pos         name: RTL-POS-FW         enabled: true

  - A dedicated firewall zone for guest wifi. Approved at the intent
    level - individual environments may still restrict it locally.
        role: guest       name: RTL-GUEST-FW       enabled: true

  - A placeholder zone reserved for quarantining unrecognized devices.
    Not yet approved.
        role: quarantine  name: RTL-QUARANTINE-FW  enabled: false
```

## Scenario

This is the very first step in the whole pipeline. Nothing has been loaded, checked, planned, or applied yet, because nothing has even been written down yet.

Store Operations and Network Engineering have said: "We've agreed on the firewall zones we need, but right now that agreement only exists in a meeting and a Slack thread — nothing a computer can actually read. Before any automation touches a single piece of AWS infrastructure, we want that agreement written down as a real file the system can load and trust."

## Steps

```
1. Create the file: intent/branch_firewall_service.json
   There is no code for this TODO - this is the only file you write.

2. Shape it exactly like this:
     {
       "tenant": "<string>",
       "service": "<string>",
       "zones": [
         { "role": "<string>", "name": "<string>", "enabled": true }
       ]
     }

3. Add one zones entry per zone in the Business Requirements above, in
   any order, using the exact role, name, and enabled values given
   there. zones is a list.

4. Save, then run: python grading.py
```

## Grading Check

Run the grader. The grader reads this file directly — it does not need to run anything to check it.

Before you complete this TODO, running the grader shows:

```
TODO 01 - Author the Declarative Network Intent
────────────────────────────────────────────────────────────────────────────────

[1] Authoring the declarative network intent...

✗ TODO 01 Not Complete

The pipeline cannot continue because the declarative network intent has not been
authored correctly yet.

Proceeding to detailed feedback...
```

After you complete it correctly, the grader shows:

```
TODO 01 - Author the Declarative Network Intent
────────────────────────────────────────────────────────────────────────────────

[1] Authoring the declarative network intent...
intent/branch_firewall_service.json matches the required business requirements.

✓ TODO 01 Complete
intent/branch_firewall_service.json captures the business requirements correctly.
```

---
