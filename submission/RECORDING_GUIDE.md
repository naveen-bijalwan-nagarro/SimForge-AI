# CodexForge four minute demo cue sheet

## One goal

Show one complete CloudRescue round trip: introduce the need, start SimForge AI, upload one synthetic incident brief, show the privacy check, generate a Codex draft, review and publish it, then follow one learner through a starting check, investigation, response and learning report. Use the same screen order for the recording and live presentation.

One scenario, one learner run and one report make the product clear.

**Primary short Codex packet:** paste `samples/sample2/admin_prompt.txt` and upload only `samples/sample2/CloudRescue_Incident_Brief.docx`. The brief contains a fictional contact, reserved-domain email and test-network IP for the privacy-screening demonstration. Follow `docs/SAMPLE2_LEARNER_ROUTE.md` for the scored Inspect → diagnosis → Repair sequence. The simulator generates generic records and actions, so the exact figures in the uploaded brief may differ from learner UI records. **FactoryPulse** in `samples/sample1` is an optional richer manufacturing example with Word/PDF references. Neither packet guarantees a fast Codex response.

## Rehearse before recording

1. Run `.\setup.cmd` and let the React build finish. Stop the app. Display `submission/CodexForge/Opening_Slide.png` full screen for about 12 seconds, then run `.\start.cmd` in PowerShell and show the printed localhost address and loaded Overview. The startup banner masks passwords; keep terminal history and any real credentials out of frame.
2. Use separate Admin and Learner browser profiles; tabs in one profile share the same login cookie. Hide desktop notifications and keep text readable at 1080p. Check Codex CLI sign-in before recording.
3. Keep the short Sample 2 prompt open in a text editor and its single DOCX ready in File Explorer. In **Admin / Trainer → Scenario Lab**, use **Upload scenario documents** to select the DOCX. Paste the prompt into **Admin prompt**. Wait for the current upload preview, inspect the redacted types, and open **Preview privacy checks** and **Security review** to show type/count receipts without matched values. Screening covers extracted text and is not a guarantee that all PII was found.
4. Click **Generate draft with Codex**. Inspect the returned job and check source **codex**, visual style **service_app**, the five connected systems, hidden deployment cause, complete learner Mission/Success text, passing validation and available Inspect/Repair actions. Use **Edit and revalidate** if needed. Publish only a reviewed draft with **Publish & notify learners**. Keep a labelled, validated, unpublished Codex draft as the live-presentation fallback.
5. Rehearse the learner route in `docs/SAMPLE2_LEARNER_ROUTE.md` with a separate synthetic run. In the recorded run, use the newly published scenario. Choose 60 work items, seed 2026 and 35 simulated minutes if those controls remain available. Wait for the new notification and mission to load in place; **Refresh notifications** and **Refresh view** fetch immediately. Answer all three starting questions before playback. After the incident starts at simulated minute 5, pause, compare evidence, commit **Investigate source signals**, submit the **deployment** diagnosis, and commit **Repair the source** with at least four simulated minutes left. Read the generated cause options instead of assuming an option position.
6. Complete the run only after diagnosis and repair have been recorded. **Complete run** advances to the horizon; the completion warning explains that missing diagnosis or decisions cannot be added to that run afterward. Answer all three post-check questions and show the actual earned practice score. Opening Evidence without committing Inspect does not earn investigation credit.
7. Record real interactions in sequence. Show Codex **generating**, then cut only genuine waiting time and return to that **same job** when ready. Say that waiting was shortened. A rehearsed draft must be identified as earlier work, never as the result of the current job.

## Spoken script and clicks

Target **3:45–3:55**. The time marks are editing targets; practise the exact clicks with a stopwatch. Speak normally and pause on visible proof instead of reading every field.

| Time | Show and click | Say |
| --- | --- | --- |
| 0:00-0:12 | Display **CodexForge/Opening_Slide.png** full screen. Point across the four-step path. | "Teams need realistic digital-tool practice without touching live systems. SimForge lets trainers review Codex-created exercises, then learners investigate, act and see what they learned." |
| 0:12-0:25 | PowerShell: .\start.cmd > localhost Overview. | "I am starting SimForge AI locally. One command serves the React interface and Python API." |
| 0:25-0:35 | Overview, then Admin / Trainer > Scenario Lab. | "Our original idea documents this client need. No pilot result is measured yet; we will track preparation time, diagnosis and knowledge change." |
| 0:35-1:30 | **Upload scenario documents** > choose the one CloudRescue DOCX > inspect the redacted preview and type/count receipt > paste `admin_prompt.txt` into **Admin prompt** > **Generate draft with Codex**. Show the real running status, then the same ready job, source and validation. Click **Publish & notify learners**. | "This brief is synthetic. Local screening removes recognized fictional identifiers from extracted text and records types and counts. The signed-in Codex CLI turns the selected brief into a structured draft. I review its learner goal and checks, then publish it." |
| 1:30-2:10 | Switch to Learner profile > new CloudRescue notification > generate linked records > enter simulation > answer all three starting questions. Wait for each current view to load in place. | "The learner opens that publication and generates a repeatable synthetic workload. Before the clock starts, the three-question check records their starting knowledge." |
| 2:10-2:55 | Operations > **Application**; play to simulated minute 5 and pause. Evidence > compare release, API and database records. Diagnose & act > **Investigate source signals** > submit deployment diagnosis > **Repair the source**. | "Requests queue after a bad deployment setting. I inspect before responding, commit the diagnosis and choose a simulated repair. Playback runs on the local CPU without a learner-side model call." |
| 2:55-3:26 | After diagnosis and repair, **Complete run** > debrief/no-action comparison > Learning review > answer all three post-check questions > practice report. | "The debrief reveals the cause and compares the same workload without intervention. The report separates before-and-after knowledge from the 100-point practice score. These are training signals, not measured customer savings or certification." |
| 3:26-3:55 | Admin / Trainer > Assignments & results > read-only learner result. End on Overview or one Scenario Library card. | "The trainer can observe but cannot change the learner's run. Role checks, synthetic data, screening receipts and human publication support responsible use. This is a single-host pilot; identity, retention and domain validation remain. The same path can be reused for other approved scenarios." |

## Live presentation using the same route

Use the same screen order and spoken lines. A fresh Codex job can exceed the planned Admin segment. Show **Generate** and its real running state. If it is still running, open the labelled unpublished rehearsal draft and say: "This draft was generated earlier by Codex from the same local brief. I am reviewing and publishing that saved draft so you can see the full learner journey." The recording may edit out real waiting from one completed job; never imply an earlier draft was generated during the cut.

If the CLI is unavailable and the draft source reads **openai_api** or **manual**, name that source accurately. Do not describe it as a Codex-generated draft. Codex remains the primary authoring path and the API is an explicit Admin-selected backup.

## Final submission check

- Record and export a **separate finished MP4 no longer than four minutes**. Verify readable text, audible speech, application startup, the actual reviewed and published draft, starting check, recorded Inspect/diagnosis/Repair, debrief and report. The existing `recordings/recording1.mp4` is an approximately 11-second clip, not the mandatory final demo.
- Refresh `submission/CodexForge/SimForge-AI-code.zip` after the last code or document change. Confirm its contents and SHA-256 match `TECHNICAL_REFERENCE.txt`. The source ZIP excludes local environments, runtime data, secrets and the submission folder.
- Put the finished MP4, code ZIP, opening image, Word overview and technical reference into the `CodexForge` folder. Add screenshots if useful. Zip that folder as `CodexForge.zip`, open the outer ZIP to check the MP4 and code ZIP, upload it to Google Drive with required viewer access, and submit its shareable link by **11:00 AM Saturday, 10 October 2026**. The final MP4 and outer ZIP have not yet been created in this workspace.

If you obtain an interview or pilot fact, replace the "no measured pilot yet" sentence only with a sourced, dated statement. Keep synthetic business effects labelled illustrative.
