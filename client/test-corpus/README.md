# Pinned Markdown corpus

This directory contains **24 unmodified real Markdown files**: eight each from
NVIDIA/CUTLASS, Dao-AILab/flash-attention, and microsoft/vscode-docs. The manifest
records repository, exact commit, original path, source URL and SHA-256 for each
file and its repository license. Copyright and licensing remain with the source
projects. CUTLASS and FlashAttention use BSD-3-Clause; vscode-docs documents use
CC BY 3.0 US (its code examples use MIT). See the included upstream license files.

Files were selected at the recorded commit from Markdown files with size
101–65536 bytes, sorted by SHA-256 of the original path, taking the first eight.
The tests validate file hashes and require no network. This is a small fixed
regression corpus, **not** a reproduction of Issue #13's unpinned 1,010-file survey.
Chinese and boundary cases are authored in `src/roundtrip.test.jsx`; no
noncommercial-only upstream corpus is redistributed.

Run `npm run roundtrip` from `client/`. It uses the actual Milkdown parser and
serializer with the same source-preservation plugin as the UI, then runs real
ProseMirror text insertions in every block with a source-locatable text node.
Each insertion is compared against the exact expected source bytes and reopened.
UI tests separately cover composition, table and raw edits, history, and cleanup.
The JSON report is written to `client/.local/markdown-roundtrip.json` and uploaded
by CI. No-op roundtrip alone is not the edit-preservation assertion.

Whole-document fallback means opening the entire file as a textarea. Local raw
source blocks remain in the block editor and are counted separately, so the raw
block ratio is visible. Empty/whitespace-only files are roundtripped but have no
text-insertion probe. The insertion probes do not establish arbitrary rich
formatting or structural transformations as universally byte-stable.
