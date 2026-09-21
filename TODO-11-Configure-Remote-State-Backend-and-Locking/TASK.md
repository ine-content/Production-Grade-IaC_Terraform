# TODO 11 — Configure Remote State Backend & Locking

## Topics Covered

```
✓ Why a local terraform.tfstate file doesn't survive contact with a real team
✓ Remote state - storing state in a shared backend (S3) instead of on disk
✓ State locking - a DynamoDB table preventing two applies from racing each other
✓ Why a backend block can only ever hold literal values, never expressions
✓ The bootstrap problem - why Terraform can never create the backend it depends on
```

## Recap

TODO 01 through TODO 10 are already solved in this folder. This TODO is
different from every one before it: there's nothing to add after TODO
10's own `site_security_group_live_ingress` output. Instead, open
`main.tf` and scroll all the way back to the very top - the
`terraform {}` block. Find `STUDENT WORK AREA - TODO 11` inside it,
right after `required_providers`.

## Scenario

Every apply so far in this course has written its state to one file,
`terraform.tfstate`, sitting on disk right next to `main.tf`. That's
worked fine because it's been just one person (you) running one grader,
one apply at a time. Meridian Retail's platform team has pointed out that
none of that will survive contact with a real team, and they're right,
for 3 specific reasons:

**Nobody else can see it.** State isn't a cache - it's Terraform's only
record of what it created and what it's responsible for. If that file
only exists on your laptop, nobody else on the team can safely run
`terraform apply` against this same infrastructure; Terraform has no way
to know what already exists.

**Two applies can corrupt it.** Nothing today stops two people (or two CI
jobs) from running `terraform apply` against the same local file at the
same moment. Terraform reads state, computes a plan, and writes state
back - if two applies interleave those steps, the file can end up
reflecting neither apply correctly.

**Losing the file loses everything.** If this laptop's disk dies, every
VPC, subnet, security group, and instance this course has created still
exists in AWS - but Terraform's own memory of managing them is gone.
Terraform would see brand-new infrastructure it's never heard of and try
to create it all over again, duplicating everything already running.

**Remote state** fixes the first and third problem: instead of a file on
one disk, Terraform stores state in a shared location - here, an S3
bucket - that every team member and every CI job reads from and writes to
the same way. **Locking** fixes the second: a separate DynamoDB table
holds a lock for the duration of every `plan` and `apply`, so a second
apply that starts while one is already running has to wait its turn
instead of racing it.

There's one wrinkle worth knowing before you touch this: Terraform can
never create the very bucket and table its own backend block depends on.
Backend initialization happens before Terraform ever looks at a single
resource in `main.tf` - so no `aws_s3_bucket` or `aws_dynamodb_table`
resource you could write here would ever get a chance to run first. This
course's grader handles that for you (it creates both directly, the same
way it already stands up LocalStack's other resources), so you don't need
to provision anything yourself - just point the backend block at the
names it expects.

## Before You Start: Check LocalStack Is Running

This TODO still needs LocalStack running in the background, the same as
TODO 06 through TODO 10 did:

```
curl http://localhost:4566/_localstack/health
```

You should get back JSON with `"s3": "available"` and `"dynamodb":
"available"` alongside `"ec2"`. If instead you get a connection error,
start it from this folder:

```
docker compose up -d
```

## Worked Example

A `backend` block is declared *inside* the same `terraform {}` block that
already holds `required_version` and `required_providers` - never as a
block of its own. Terraform only allows one `terraform {}` block per
configuration:

```
terraform {
  required_version = ...
  required_providers { ... }

  backend "s3" {
    bucket         = "meridian-retail-tfstate"
    key            = "branch-network/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "meridian-retail-tf-locks"
    access_key     = "test"
    secret_key     = "test"
    ...
  }
}
```

Every one of those values has to be a literal string - `"..."` - never a
variable, a `local.`, or any kind of expression. That's not a style
choice; Terraform's backend configuration is read before any of the rest
of your configuration (including `locals`) is even parsed, so nothing
dynamic is available to it yet.

A backend block also authenticates completely separately from the `aws`
provider block further down this same file - the provider's own
`access_key = "test"` doesn't carry over to the backend. Without its own
`access_key`/`secret_key`, Terraform tries to find real AWS credentials
(environment variables, an EC2 instance role, `~/.aws/credentials`...)
and fails with "No valid credential sources found" before it ever gets
far enough to talk to LocalStack.

Once this is correct, `terraform init` resolves it and writes a small
pointer file, `.terraform/terraform.tfstate`, recording which backend is
in use - that pointer file is how this TODO's grading actually confirms
your work, not by reading `main.tf`'s own text. From there:

```
terraform init
    -> reads your backend "s3" block
    -> confirms the bucket and table exist (already true - the grader
       creates them before you ever run this)
    -> writes .terraform/terraform.tfstate: {"backend": {"type": "s3",
       "config": {"bucket": "meridian-retail-tfstate", ...}}}

terraform apply
    -> acquires a lock in the DynamoDB table before touching anything
    -> writes the real state to s3://meridian-retail-tfstate/
       branch-network/terraform.tfstate - never to a local
       terraform.tfstate file
    -> releases the lock when the apply finishes
```

If a second `apply` tried to start against this same key while the first
one was still running, it would have to wait for that same DynamoDB lock
- the exact race a local file has no protection against at all.

## Steps

```
1. Open main.tf and scroll to the very top - the terraform {} block.
   Find STUDENT WORK AREA - TODO 11, right after required_providers.

2. Add exactly one block - backend "s3" - inside this SAME terraform {}
   block, not as a separate block anywhere else in the file. Every
   value below is a literal this course requires exactly as written;
   none of it is derived or computed.

     backend "s3" {
       bucket         = "meridian-retail-tfstate"
       key            = "branch-network/terraform.tfstate"
       region         = "us-east-1"
       dynamodb_table = "meridian-retail-tf-locks"

       access_key                   = "test"
       secret_key                   = "test"
       skip_credentials_validation = true
       skip_metadata_api_check     = true
       skip_requesting_account_id  = true
       use_path_style              = true

       endpoints = {
         s3       = "http://localhost:4566"
         dynamodb = "http://localhost:4566"
       }
     }

   The first 4 lines are the backend itself - bucket, key (the path
   state is written to inside that bucket), region, and the DynamoDB
   table used for locking. Everything after that authenticates and
   redirects the backend at LocalStack - and it has to be repeated here
   even though the aws provider block just below already has its own
   access_key/secret_key, because a backend authenticates completely
   separately from any provider. use_path_style is the same path-style S3
   addressing LocalStack needs everywhere else.

3. Save, then run: python grading.py
```

## Grading Check

```
python grading.py
```

Before checking anything else, the grader creates the S3 bucket and
DynamoDB table your backend block needs, directly via `boto3` - the same
chicken-and-egg problem described above, solved outside of Terraform
entirely, so you never need to provision this infrastructure by hand.

It then applies your file in a fresh scratch copy and reads back
`.terraform/terraform.tfstate` - the pointer file `terraform init` itself
writes once a real backend is configured - to independently confirm
Terraform resolved a backend of type `"s3"`, pointed at exactly the
bucket, key, and DynamoDB table this course requires. None of this is
read from `main.tf`'s own source text.

It then runs a real `terraform apply` against that backend. If the
`dynamodb_table` name were wrong, this is where it would fail -
LocalStack has no table by that name to lock against. Once the apply
succeeds, the grader confirms no local `terraform.tfstate` file exists in
the working directory (state genuinely didn't fall back to disk), and
calls the AWS API directly, via `boto3`, to confirm the state object
really exists in the S3 bucket at the expected key - never trusting
Terraform's own account of where it put things.

Every apply above is followed by `terraform destroy`, so LocalStack is
never left holding resources between grading runs.

Before you complete this TODO:

```
TODO 11 - Configure Remote State Backend & Locking
────────────────────────────────────────────────────────────────────────────────

[11] Configuring the remote state backend and locking...

✗ TODO 11 Not Complete

The pipeline cannot continue because a remote state backend with locking has
not been correctly configured yet.

Proceeding to detailed feedback...
```

After you complete it correctly:

```
TODO 11 - Configure Remote State Backend & Locking
────────────────────────────────────────────────────────────────────────────────

[11] Configuring the remote state backend and locking...
  terraform init -> backend "s3" resolved (bucket=meridian-retail-tfstate)
    key            -> branch-network/terraform.tfstate
    dynamodb_table -> meridian-retail-tf-locks
  terraform apply -> succeeded against the real S3 + DynamoDB backend
  local terraform.tfstate -> absent, state is not sitting on local disk
  s3://meridian-retail-tfstate/branch-network/terraform.tfstate -> confirmed
  independently via the AWS API

✓ TODO 11 Complete
main.tf's terraform {} block now configures a real S3 backend with DynamoDB
locking - Terraform itself resolved the exact bucket, key, region, and lock
table this course requires, and state is confirmed living in S3, not on local
disk.
```

---
