# Maintenance and verification

## Environment

Create a fresh `.venv` and install `requirements.txt` there; see README. Updating
the file does not repair an existing environment with both OpenCV distributions.
The project's isolated environment should pass `python -m pip check`. Shared
Anaconda may still report unrelated package conflicts; do not uninstall those
packages as part of this project's maintenance.

## Thirty-day retention

First run `python -m pipeline.purge --days 30 --dry-run` from the repository.
Review the counts and file paths, then omit `--dry-run` to apply deletion.
Only generated MP4/CSV files beneath this repository's `output/` are eligible.
Database age uses event timestamps; file age uses last modification time.
`--database-only` retains the earlier database-only behavior.

No scheduled task has been installed. To schedule daily on this Windows machine,
create a Task Scheduler task with these settings:

- Trigger: daily, at a time when video processing is not running.
- Program: `D:\python\GITHUB\Smart City Traffic ANPR System\.venv\Scripts\python.exe`
- Arguments: `-m pipeline.purge --days 30`
- Start in: `D:\python\GITHUB\Smart City Traffic ANPR System`
- Prevent overlapping task instances; enable task history and inspect failures.

For a Linux deployment, use a daily cron entry with the deployment's actual
absolute paths, for example:

```cron
0 3 * * * cd /srv/anpr && /srv/anpr/.venv/bin/python -m pipeline.purge --days 30 >> /srv/anpr/retention.log 2>&1
```

This is an example, not an installed job. Schedule on the host that owns the
files and SQLite database. A GitHub Actions runner cannot purge files on your
computer or a separate Streamlit deployment. Sleeping/offline hosts do not run
ordinary jobs; configure catch-up/retries where supported. Monitor success.

Deletion is irreversible without a backup. It is not secure erasure: filesystem
snapshots, backups, and SQLite free pages can retain old content. Those require
a separate storage/backup policy. Raw source footage and custom output locations
outside `output/` are intentionally not deleted. Do not store source footage in
`output/`. Stop processing before a manual purge if files are being replaced.

## Warnings

Streamlit calls use `width="stretch"` rather than the deprecated
`use_container_width` parameter. The two known EasyOCR/Torch CPU notices have
narrow message/module filters only during OCR initialization/execution (D-028).
Other warnings remain visible. Quantization and the OCR threshold are unchanged.
This avoids cosmetic notices without editing installed libraries; it does not
fix EasyOCR's upstream implementation. Revisit when upgrading EasyOCR/Torch.

## OCR accuracy

Successful tests prove code paths, not recognition accuracy. To validate accuracy:

1. Collect representative, authorized footage with readable plates and a separate
   human-labeled ground-truth plate for each crossing. Keep it outside Git.
2. Include difficult lighting, angles, motion blur, and unreadable/absent plates.
3. Compare normalized full-plate text against labels, recording exact-match rate,
   missed reads, and high-confidence incorrect reads separately. OCR confidence
   is not an accuracy score.
4. Keep a held-out set; do not tune thresholds solely to the existing sample.
5. Agree on acceptance thresholds before deploying results for consequential use.

No labeled dataset or accuracy target has been supplied for this change. D-022's
limitations therefore remain; no recognition-quality improvement is claimed.

Sensitive artifacts, model weights, database files (including WAL/SHM sidecars),
and generated test outputs remain ignored by Git. That is intentional protection,
not a defect to remove.
