# Running This Course With No Internet Access

This course can run entirely offline, for a classroom or workshop machine
that has no internet access at all. One thing still needs real internet,
but only **once**, and only on **your** machine — not the students'.

## Why this is needed

`terraform init` normally resolves the `hashicorp/aws` provider from
`registry.terraform.io`. TODO 01 through TODO 04 never declare that
provider at all, so they need no internet. TODO 05 onward all declare
`required_providers { aws = { source = "hashicorp/aws" } }`, so from TODO
05 on, `terraform init` needs to resolve that provider from *somewhere* —
normally the public registry.

Terraform has a built-in way to point it at a local folder instead of the
registry: a **filesystem provider mirror**. This course's grading.py files
now do that automatically, with no student-visible change, whenever a
mirror folder exists at the course root.

## One-time setup (do this once, with internet, before handing the course out)

1. Pick any TODO folder that declares the `aws` provider (TODO 05 or
   later — TODO 12 works fine) and run:

   ```
   cd Production-Grade-IaC_Terraform/TODO-12-Emit-a-Structured-Audit-Log
   terraform providers mirror -platform=linux_amd64 -platform=darwin_arm64 ../.terraform-providers-mirror
   ```

   This is Terraform's own subcommand, built exactly for this. It reads
   `required_providers` from that folder's `main.tf` (`hashicorp/aws, ~>
   5.0`), downloads the matching provider version for **both** platforms
   from the real registry, and writes them into
   `Production-Grade-IaC_Terraform/.terraform-providers-mirror/` in the
   exact directory layout Terraform's filesystem mirror expects. No
   manual file placement needed — just run the command.

   Add more `-platform=` flags if any student machine isn't one of these
   two (e.g. `-platform=windows_amd64`, `-platform=linux_arm64`).

2. Confirm it worked:

   ```
   find ../.terraform-providers-mirror -type f
   ```

   You should see a `registry.terraform.io/hashicorp/aws/...` structure
   with a `.zip` per platform, a couple hundred MB total.

3. Ship the whole `Production-Grade-IaC_Terraform` folder to students,
   including the new `.terraform-providers-mirror/` folder sitting at its
   root, next to all the TODO-XX folders. It travels as part of the course
   — nothing else to configure.

## What happens automatically from there

Every `grading.py` (TODO 02 through TODO 12) checks, at the top of its
`run_terraform()` function, whether
`Production-Grade-IaC_Terraform/.terraform-providers-mirror/` exists next
to the TODO folders. If it does, grading.py writes a small, temporary CLI
config file (`.offline-provider-mirror.tfrc`, at the course root) telling
Terraform: "get `hashicorp/aws` only from this local folder, never from
the network," and points `terraform` at it via the `TF_CLI_CONFIG_FILE`
environment variable for that one command. Students never see this, never
configure anything, and never type a raw `terraform` command — everything
still goes through `python grading.py` exactly as before.

If the mirror folder is missing (e.g. you're still developing on your own
machine with internet), everything falls back to normal registry-based
resolution, unchanged. Nothing breaks either way.

LocalStack itself (the AWS emulator these TODOs provision against) still
needs to be reachable at `localhost:4566`, same as always — but that's a
local Docker container, not the internet.
