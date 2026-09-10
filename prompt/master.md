# Read the files at provided links in exact order following these instructions:

- File fetch instructions:
  * ONE batched call with all URL aliases (raw.githubusercontent + cdn.jsdelivr.net/gh + raw.githack.com + statically.io);
  * never sequential retries of one URL family;
  * never blob/ HTML pages (renderer truncates);
  * repo mirrors (GitHub + GitLab) are preferred redundancy;
  * verify EOF sentinel before treating content as authoritative;
  * single user-paste fallback, then stop.
  * consume via raw endpoints only (`raw.githubusercontent.com/<owner>/<repo>/<sha-or-branch>/<path>`);
  * `blob/` pages — branch or permalink-SHA alike — are render-truncated and banned for reading;
  * permalinks (blob @ SHA) are for citations only.

- Files to fetch:

https://raw.githubusercontent.com/alksbrs/ipu6/refs/heads/main/prompt/instructions.md
https://raw.githubusercontent.com/alksbrs/ipu6/refs/heads/main/transcript/transcript.md
