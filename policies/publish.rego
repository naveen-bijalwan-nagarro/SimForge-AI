package simforge.publish

# Deterministic publication gate for SOP-generated scenarios.
# Evaluate with: opa eval --stdin-input -d policies/publish.rego data.simforge.publish
# SimForge falls back to an identical built-in evaluator when `opa` is not installed.

import rego.v1

default allow := false

allow if {
	input.tests_passed
	input.redteam_failures == 0
	input.pii_found == 0
	input.prohibited_tools == 0
	input.trainer_approved
}

deny contains "Mandatory scenario tests have not all passed" if not input.tests_passed

deny contains msg if {
	input.redteam_failures > 0
	msg := sprintf("%d red-team check(s) failing", [input.redteam_failures])
}

deny contains "Personal data found in generated content" if input.pii_found > 0

deny contains "Destructive or prohibited actions present" if input.prohibited_tools > 0

deny contains "Trainer approval is required" if not input.trainer_approved
