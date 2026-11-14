# Phase 2.1 changes

- Bundled original Phase 1 project and applied its population-gap patch.
- Wired the included current NISAR pair into Phase 1 config and doctor; proved both phases' inputs match the existing import receipt.
- Mounted a new local dashboard and Phase 2 routes on the original M5 app; retained the original JWT adapter and verified real decoder/owner isolation.
- Removed the Python 3.14-only multi-exception syntax. Tested on 3.12 and pinned the complete observed dependency set.
- Added immutable operator dataset import, listing, safe source pinning, optional independent labels, optional geography and explicit missing-source outcomes.
- Added uncentered spatial review candidates and their threshold stability alongside the unchanged conservative default. M3 honors the submitted mode.
- Generalized footprint equal-area calculation for imported non-Alaska regions; added explicit population/road/building data gaps.
- Added training-country-only threshold selection, spatial ML experiment, comparison output, deterministic source splits and held-out label leakage test. Poorer test results are preserved.
- Added deterministic before/after/candidate/priority PNG previews, downloadable generated report, job/event history and client-side download digest checking.
- Added supervised launcher, token generation/private state, integrated HTTP demonstration, updated Docker/CI configs and regression evidence.
- Preserved source/reference scientific limitations. No fabricated observations, labels, population estimates or provider certifications were introduced.
