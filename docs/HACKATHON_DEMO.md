# Four-minute CloudRescue demonstration

Show one complete Admin / Trainer to Learner cycle with the short CloudRescue sample2 packet. The aim is to demonstrate safe scenario creation and evidence of learner practice. Use the same sequence for the recorded video and live presentation. The spoken cue sheet is in [the recording guide](../submission/RECORDING_GUIDE.md).

## Prepare once

- Complete `setup.cmd` before recording, then stop the app. Open with `submission/CodexForge/Opening_Slide.png` for about 12 seconds; start the app with `start.cmd` and show its localhost address and loaded Overview.
- Use separate Admin and Learner browser profiles. The startup banner masks passwords; keep any prior terminal history, API keys and desktop notifications out of frame.
- Check Codex CLI sign-in before recording. In **Scenario Lab**, upload only `samples/sample2/CloudRescue_Incident_Brief.docx` and paste `samples/sample2/admin_prompt.txt` into **Admin prompt**. Inspect the extracted preview and **Preview privacy checks**. Its fictional contact, reserved-domain email and test-network IP demonstrate local text screening; confirm the visible redactions and type/count receipts.
- Rehearse generation and keep one validated, unpublished Codex draft clearly labelled as a live-presentation fallback. Before publication, check source **codex**, the five-node **service_app** workflow, hidden cause, passing checks and short, complete learner Mission and Success fields. Edit and revalidate where needed.
- Start a fresh learner run from that publication. Read the [CloudRescue learner route](SAMPLE2_LEARNER_ROUTE.md), including the Inspect, diagnosis and Repair steps before debrief. FactoryPulse in `samples/sample1` remains a richer two-document operations example for a longer demonstration.

## Timed route

| Time | Screen proof |
| --- | --- |
| 0:00-0:12 | Show the single opening image: safe practice, four-step path and planned pilot measures. |
| 0:12-0:25 | PowerShell .\start.cmd, localhost Overview. |
| 0:25-0:35 | Client need: safe practice without live systems; no measured pilot yet. |
| 0:35-1:30 | Admin Scenario Lab: upload the single CloudRescue DOCX, inspect its preview and PII type/count receipt, paste the short prompt, click **Generate draft with Codex**, show the real running job and returned source/checks, then **Publish & notify learners**. |
| 1:30-2:10 | The learner notification appears in place. Open the mission, generate linked synthetic records and answer the three-question starting check before playback. |
| 2:10-2:55 | Operations: play to the incident, pause, inspect Evidence, commit **Investigate source signals**, submit the deployment diagnosis and commit **Repair the source** with enough simulated time left for its effect. |
| 2:55-3:26 | Complete run, show same-workload no-action comparison, take the three-question post-check and show the practice report. |
| 3:26-3:55 | Admin Assignments & results observation, security receipts, pilot boundaries and reuse. |

Notifications poll automatically. The library, assignments and paused runs refresh while visible; **Refresh notifications**, **Refresh library**, **Refresh progress** and **Refresh view** fetch immediately in-page. Wait for each loading state to resolve before narrating the next screen. Merely opening Evidence does not earn investigation credit: commit the Inspect action after incident onset and before a response. **Complete run** warns about missing scored steps and lets you return to **Diagnose & act**.

The simulator uses synthetic data and makes no learner-side model call. Knowledge change is the difference between starting and post-check percentages. The separate 100-point practice score includes post-check answers (50), correct diagnosis (25), timely investigation (15) and targeted repair (10). The generated exercise uses generic simulator records and actions, so the exact figures in the uploaded brief should not be promised as learner UI records.

## Record and present honestly

Codex generation can exceed the timed Admin segment. In the recording, show the running job, then cut only genuine waiting and return to that same job when it finishes. In a strict four-minute live presentation, if the fresh job is still running, open the labelled unpublished rehearsal draft and say when it was created. Do not describe an API or manual draft as Codex output.

The original idea documents the client need, but no measured customer pilot is supplied. Synthetic delays and savings are illustrative. Local pattern screening reports recognized types and counts without matched values, but cannot guarantee complete PII detection. The single-host pilot still needs enterprise identity, retention, monitoring, backup/restore drills, load testing and domain validation before rollout.
