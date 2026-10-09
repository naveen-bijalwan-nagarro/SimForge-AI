# Four-minute FactoryPulse demonstration

This route shows one complete Admin / Trainer to Learner cycle. Use one newly generated FactoryPulse scenario and one learner run. The detailed spoken cue sheet for the team is in submission/RECORDING_GUIDE.md in the working repository.

## Prepare once

- Install dependencies with .\setup.cmd, then stop the app. Open the recording with submission/CodexForge/Opening_Slide.png for 12 seconds. Then start the application with .\start.cmd and show the printed localhost address and loaded Overview.
- Use separate Admin and Learner browser profiles. Hide terminal demo credentials, API keys and desktop notifications.
- Check that the Codex CLI is signed in and ready. Scenario Lab's **Load FactoryPulse demo packet** button loads the short prompt, synthetic operations brief and chart PDF from samples/sample1. It creates references only; it does not generate or publish.
- Rehearse generation and keep one validated, unpublished Codex draft as a clearly labelled live-demo fallback. Before publication, check source **codex**, visual style **service_app**, the six connected nodes, a hidden cause, passing checks and brief, complete learner Mission and Success fields. Edit and revalidate any overlong wording.
- Do not use an old FactoryPulse run for the final demonstration: old runs retain their original 785-character mission and cut-off 500-character success text. Create a new publication and new learner environment from the revised packet.

## Timed route

| Time | Screen proof |
| --- | --- |
| 0:00-0:12 | Show the single opening image: safe practice, four-step path and planned pilot measures. |
| 0:12-0:25 | PowerShell .\start.cmd, localhost Overview. |
| 0:25-0:36 | Client need: safe practice without live systems; no measured pilot yet. |
| 0:36-1:18 | Admin Scenario Lab: load packet, preview local screening, click **Generate draft with Codex**, show the real running job and its returned source/checks, then **Publish & notify learners**. |
| 1:18-2:01 | Learner Notification: prepare linked records, enter simulation, complete the three-question starting check before playback. |
| 2:01-2:48 | Operations Application: play to the incident, pause, compare Evidence, commit **Investigate source signals**, submit diagnosis, then commit **Repair the source**. |
| 2:48-3:22 | Complete run, show same-workload no-action comparison, take the three-question post-check and show the practice report. |
| 3:22-3:55 | Admin Assignments & results observation, security receipts, pilot boundaries and reuse. |

The simulator uses synthetic data and no learner-side model call. Knowledge change is the difference between starting and post-check percentages. The separate 100-point practice score includes post-check answers (50), correct diagnosis (25), timely investigation (15) and targeted repair (10). Merely opening Evidence does not earn investigation credit; commit the inspect action after incident onset and before a response.

## Record and present honestly

Codex generation has a 120-second timeout and can exceed the timed Admin segment. In the recording, show the running job, then cut genuine waiting and return to that same job when it finishes. In a strict four-minute live presentation, if the fresh job is still running, open the labelled unpublished rehearsal draft and say when it was created. Do not describe an API or manual draft as Codex output.

The original idea documents the client need, but no measured customer pilot is supplied. Synthetic delays and savings are illustrative. Local pattern screening reports recognized types and counts without matched values, but cannot guarantee complete PII detection. The single-host pilot still needs enterprise identity, retention, monitoring, backup/restore drills, load testing and domain validation before rollout.
