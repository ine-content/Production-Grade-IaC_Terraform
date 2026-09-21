# Production-Grade IaC with Terraform

A progressive, TODO-based Terraform course, in the same family as *Production-Grade Python Engineering* and *Production-Grade IaC with Ansible*.

## Business Scenario

Meridian Retail's branch network team wants their **firewall and network-segmentation policy** managed the same disciplined way the last two courses managed rendering and config push: written down as intent, validated before anything runs, provisioned idempotently, independently verified against the live state, and permanently audited. Every branch is hosted **in AWS** - one VPC per site, one subnet per resolved zone, a security group carrying that site's firewall policy, and an EC2 instance acting as that branch's gateway.

TODO 01 through TODO 04 build that policy first, entirely independent of AWS: a declarative network intent, loaded and cross-validated structured inputs, and a resolved, environment- and site-aware set of zones per branch. Only once that policy is fully resolved does TODO 05 turn it into a network plan - every site's subnet CIDRs and every firewall device's gateway entry, computed as plain data. TODO 06 then turns that plan into real infrastructure - one VPC per site, one subnet per zone, a security group carrying the same firewall policy TODO 04 already resolved, and an EC2 instance as that branch's gateway, tagged with that site's own planned device ID so it's traceable end to end.

Starting with TODO 06, this course provisions actual **AWS VPC, subnet, route table, security group, and EC2 resources** with Terraform, against LocalStack (a local AWS emulator) standing in for real AWS — using the real, official `hashicorp/aws` provider, just pointed at a local endpoint instead of `amazonaws.com`. So every `plan`, `apply`, `state`, and `destroy` from here on is genuine Terraform behavior against a genuine AWS provider, not simulated.

## Pipeline

```
Author Declarative Network Intent
        ↓
Load & Parse Structured Inputs
        ↓
Run Pre-Flight Validation
        ↓
Build Environment- and Site-Aware Locals
        ↓
Compute Network & Gateway Locals
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
Emit a Structured Audit Log
```

## Branches

Same three branches as the Ansible/Python courses, each hosted as its own AWS VPC. Each site plans for more than one gateway instance - RDU01 and AUS02 (prod, already live) each an HA pair; SEA03 (staging, still onboarding) a single instance for now. Each site's primary device becomes that VPC's EC2 gateway instance, starting TODO 06:

```
RDU01  (Raleigh  - prod)     - rdu01-gw-primary, rdu01-gw-secondary  ->  VPC 10.0.0.0/16
AUS02  (Austin   - prod)     - aus02-gw-primary, aus02-gw-secondary  ->  VPC 10.1.0.0/16
SEA03  (Seattle  - staging)  - sea03-gw-primary                      ->  VPC 10.2.0.0/16
```

## TODOs

```
TODO 01  Author the Declarative Network Intent
TODO 02  Load & Parse Structured Inputs
TODO 03  Run Pre-Flight Validation
TODO 04  Build Environment- and Site-Aware Locals
TODO 05  Compute Network & Gateway Locals
TODO 06  Define AWS Network & Firewall Resources
TODO 07  Run terraform plan and Verify Against Expected Changes
TODO 08  Apply Idempotently
TODO 09  Verify Terraform State Matches Live AWS State
TODO 10  Detect and Reconcile Drift
TODO 11  Configure Remote State Backend & Locking
TODO 12  Emit a Structured Audit Log
```

## Status

TODO 01 through TODO 12 are built. The course is complete.

## Running Offline

This course can run with zero internet access on the student machine - see
[OFFLINE_SETUP.md](OFFLINE_SETUP.md) for the one-time setup step (done
once, by the instructor, with internet).
