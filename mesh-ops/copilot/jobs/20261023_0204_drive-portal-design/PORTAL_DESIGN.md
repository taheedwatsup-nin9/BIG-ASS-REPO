# CR8MOR Knowledge Portal — Design Proposal

## Who it serves

- **Taheed:** A phone-friendly front door to find project files, skills, saved videos, and archived material. Keep labels plain and make common searches possible with a few taps or voice dictation.
- **Claude, MUZI, and Copilot:** A consistent, current list of Drive links and folder context they can search or use as a starting point. The sheet points to source files; it is not a replacement for them.

## Tabs and views

- **Keep Start Here** as the landing page: explain what the portal covers, how to search on a phone, and when it was last refreshed.
- **Keep Index** as the complete source list. Retain PARA location, folder, file name, type, size, and link; freeze the header and enable filters. Add a short “notes / useful for” field only when it can be maintained reliably.
- **Keep Skill Batches**, but group it for quick scanning and retain the saved-video entries. Link each item back to its Drive location.
- **Keep Archives** as a compact count-by-folder view, not a second file list. It helps show where older material lives without crowding the main Index.
- **Add a few saved views on Index** for Projects, Skills & learning, and Root files. These are filtered ways to see the same list, not extra copies to maintain.
- **Cut duplicate lists and decorative dashboards.** Every file should have one authoritative Index row so links and labels do not drift.

## Keeping it fresh

Refresh the Drive listing **once each night**, and show the refresh date prominently on Start Here. A scheduled refresh is a sensible default; if automatic access is not available, use a short, repeatable Google Sheets menu action instead of a command-line workflow. Keep the existing portal available if a refresh fails and show the last successful refresh date.

Rebuild the full listing when the Drive folder structure changes, when files are moved or renamed in bulk, or when the Index columns or inclusion rules change. Ordinary additions and edits should be picked up by the nightly refresh. Do not recreate Taheed’s folder structure as part of refreshing.

## Three quick wins (each under an hour)

1. **Make Start Here phone-ready:** Put the search tip, key links, and last-refreshed date at the top; hide unused columns and freeze the header.
2. **Add saved Index views:** Set up Projects, Skills & learning, and Root files filters; test each with a few existing rows.
3. **Make links and coverage easy to check:** Add a visible “missing link” check and a simple refresh-date label, then review the exceptions before sharing.

## Questions for Taheed

1. Should agents be able to access the whole Drive, or only files already shared with them?
2. Is a nightly update frequent enough, or do important changes need to appear sooner?
3. Which folders or file types should stay out of the portal?

---
## Verification (Claude, 02:06): PASS with 1 addition
Sound and fits Taheed's phone/voice use. Addition: the portal builder (build_portal.py) lived only in Claude's temporary scratchpad; now saved to mesh-ops/portal/ so a nightly refresh has something to run. Next: Taheed approves (or edits) before any build; his 3 questions stand.
