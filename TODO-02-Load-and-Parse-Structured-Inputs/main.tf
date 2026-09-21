terraform {
  required_version = ">= 1.5.0"
}

# ---------------------------------------------------------------------------
# STUDENT WORK AREA - TODO 02
# ---------------------------------------------------------------------------
# Write one locals block here that loads:
#
#   service_intent - the declarative network intent you authored in TODO 01
#   environments    - a map keyed by environment name ("prod", "staging"),
#                     each value the parsed contents of environments/<name>.json
#   sites           - a map keyed by site_id ("rdu01", "aus02", "sea03"),
#                     each value the parsed contents of sites/<site_id>.json
#
# Load the intent file, both environment files, and all 3 site files, each
# with its own jsondecode(file(...)) call. See TASK.md for the exact shape.

locals {

}

# ---------------------------------------------------------------------------
# END STUDENT WORK AREA - TODO 02
# ---------------------------------------------------------------------------

# ===========================================================================
# PROVIDED - DO NOT MODIFY
# ===========================================================================
#
# An `output` block is how a value computed inside this Terraform
# configuration becomes visible outside of it. Without this block,
# local.service_intent, local.environments, and local.sites would only
# exist internally - neither you nor the grader could ever see them.
# This wraps all 3 of TODO 02's locals into one output named
# "loaded_inputs" so you can inspect what you loaded yourself with:
#
#   terraform output -json loaded_inputs
#
# The grader reads this exact same output to check your work - never by
# reading main.tf's source as text.
output "loaded_inputs" {
  value = {
    service_intent = local.service_intent
    environments   = local.environments
    sites          = local.sites
  }
}
