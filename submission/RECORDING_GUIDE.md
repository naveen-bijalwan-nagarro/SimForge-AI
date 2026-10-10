# CodexForge four minute demo cue sheet

## One goal

Show one real round trip: open with the 12-second SimForge image, start the application, use Codex to draft a FactoryPulse exercise from synthetic references, review and publish it, then follow one learner from a starting check through investigation, response and a learning report. Use the same screen order for the recording and live presentation.

You do not need to show every tab. One scenario, one learner run and one report make the product clear.

**Optional shorter Codex packet:** `samples/sample2/admin_prompt.txt` plus the single `samples/sample2/CloudRescue_Incident_Brief.docx` gives a checkout deployment incident. Show its redacted fictional contact/email/test-IP preview and type/count security receipt, then generate. It reduces reference material but cannot guarantee model response time. If you use it, say **CloudRescue** instead of FactoryPulse throughout this script and follow `docs/SAMPLE2_LEARNER_ROUTE.md` for the scored Inspect → diagnosis → Repair sequence. The simulator generates generic records and actions, so do not promise the exact figures in the uploaded brief will appear in the learner UI.

## Rehearse before recording

1. Run .\setup.cmd and let the React build finish before you record. Stop the app. Display **CodexForge/Opening_Slide.png** full screen for 12 seconds, then run .\start.cmd in PowerShell and show the printed localhost address and loaded Overview. The startup banner masks passwords; keep prior terminal history and any real credentials out of frame.
2. Use separate Admin and Learner browser profiles; tabs in one profile share the same login cookie. Hide desktop notifications and any keys. Keep zoom and font size readable at 1080p.
3. Before recording, keep `samples/sample1` open in File Explorer and `admin_prompt.txt` open in a text editor. In Admin / Trainer > Scenario Lab, use **Upload scenario documents** to select `FactoryPulse_Operations_Brief.docx` and `FactoryPulse_Sensor_Charts.pdf` together through the Windows file picker. Paste the text from `admin_prompt.txt` into **Admin prompt**. Show the selected references, their extracted previews and **Preview privacy checks**. The optional privacy-example DOCX is unnecessary for this timed route.
4. Check Codex CLI sign-in first. Generate and inspect a rehearsal draft. Its source must be **codex**, visual style **service_app**, and learner Mission/Success short complete sentences. Check the six-node workflow, hidden cause, passing validation and source-targeted inspect/repair actions. If necessary, use **Edit and revalidate** before the recording. Keep a labelled, validated, unpublished draft as a live-presentation fallback.
5. Rehearse the Learner path with a different synthetic run. In the recorded run use the newly published scenario, 60 work items, seed 2026 and 35 simulated minutes if those controls remain available. Wait for the learner notification and mission to load in place; use the in-page Refresh control if you need an immediate fetch. Submit all three starting questions **before** starting playback. After the incident appears, pause, inspect evidence, commit **Investigate source signals**, submit the diagnosis, commit **Repair the source**, then complete the run. Merely opening Evidence does not earn investigation credit.
6. Record real interactions in sequence. Show Codex **generating**, then cut only genuine waiting time and return to that **same job** when ready. Say that waiting was shortened. If the generated draft differs from the rehearsal draft, inspect and correct it; never publish an unchecked result.

## Spoken script and clicks

Target **3:45-3:55**. The time marks are editing targets; practise the exact clicks once with a stopwatch. Speak normally and pause on visible proof instead of reading every field.

| Time | Show and click | Say |
| --- | --- | --- |
| 0:00-0:12 | Display **CodexForge/Opening_Slide.png** full screen. Point across the four-step path. | "Teams need realistic digital-tool practice without touching live systems. SimForge lets trainers review Codex-created exercises, then learners investigate, act and see what they learned." |
| 0:12-0:25 | PowerShell: .\start.cmd > localhost Overview. | "I am starting SimForge AI locally. One command serves the React interface and Python API." |
| 0:25-0:35 | Overview, then Admin / Trainer > Scenario Lab. | "Our original idea documents this client need. No pilot result is measured yet; we will track preparation time, diagnosis and knowledge change." |
| 0:35-1:30 | **Upload scenario documents** > choose the local FactoryPulse DOCX and PDF together > inspect selected previews > paste `admin_prompt.txt` into **Admin prompt** > **Preview privacy checks** > **Generate draft with Codex**. Show the real running status, then the same ready job, source, short Mission/Success and checks. Click **Publish & notify learners**. | "I select two synthetic source files through the file picker and paste the administrator brief. Local screening records recognized types and counts without logging matched values. The signed-in Codex CLI turns them into a structured draft. I review its learner goal and checks, then publish it for learners." |
| 1:30-2:10 | Switch to Learner profile > Notifications > new FactoryPulse mission > generate linked records > enter simulation > answer all three starting questions. | "The learner opens that publication and generates a repeatable synthetic workload. Before the clock starts, the three-question check records their starting knowledge." |
| 2:10-2:55 | Operations > **Application**; start playback, reach incident, pause. Evidence > compare sensor, independent condition and quality records. Diagnose & act > **Investigate source signals** > diagnosis > **Repair the source**. | "The work queue changes with the exercise clock. The dashboard signal looks calm while independent evidence worsens. I investigate first, diagnose the failing source and choose a repair. The CPU simulator applies illustrative time and cost consequences; learner playback makes no model call." |
| 2:55-3:26 | **Complete run** > debrief/no-action comparison > Learning review > answer all three post-check questions > practice report. | "The debrief reveals the cause and compares the same workload without intervention. The report separates before-and-after knowledge from the 100-point practice score. These are training signals, not measured customer savings or certification." |
| 3:26-3:55 | Admin / Trainer > Assignments & results > read-only learner result. End on Overview or one Scenario Library card. | "The trainer can observe but cannot change the learner's run. Role checks, synthetic data, screening receipts and human publication support responsible use. This is a single-host pilot; identity, retention and domain validation remain. The same path can be reused for other approved scenarios." |

## Live presentation using the same route

Use the same screen order and spoken lines. A live Codex job can take up to two minutes, so a strict four-minute live run cannot guarantee fresh generation finishes in time. Show **Generate** and its real running state. If it is still running after the planned Admin segment, open the labelled unpublished rehearsal draft and say: "This draft was generated earlier by Codex from the same local source files. I am reviewing and publishing that saved draft so you can see the full learner journey." The recording may edit out real waiting from one completed job; never imply an earlier draft was generated during the cut.

If the CLI is unavailable and the draft source reads **openai_api** or **manual**, name that source accurately. Do not describe it as a Codex-generated draft. Codex remains the primary authoring path and the API is an explicit Admin-selected backup.

## Final submission check

- Export an MP4 shorter than **4:00**. Verify readable text, audible speech and that startup, the actual generated/published scenario, baseline, decision and report are visible.
- Confirm the source ZIP in submission/CodexForge contains the final source and its SHA-256 matches TECHNICAL_REFERENCE.txt. If code or sample documents change, refresh that ZIP and checksum.
- Put SimForge_Demo.mp4 into submission/CodexForge beside the opening image, code ZIP, Word overview and technical reference. Zip that **CodexForge** folder as CodexForge.zip. Open the outer ZIP and check both MP4 and code ZIP, then upload it to Google Drive with the required viewer access and submit the link by **11:00 AM Saturday, 10 October 2026**.

If you obtain an interview or pilot fact, replace the "no measured pilot yet" sentence only with a sourced, dated statement. Keep synthetic business effects labelled illustrative.
