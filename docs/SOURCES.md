# Source and method references

- Supplied Phase 1 archive: SPECTRA-PHASE1-REAL-DATA-INTEGRATED.zip, plus SPECTRA-M3-POPULATION-FIX.zip. These are the user's existing project sources. Included source receipt hashes are retained.
- Supplied Phase 2 archive: SPECTRA-Phase2-Complete.zip. Baseline methods, exact NISAR extracts and geographic/benchmark snapshots were retained.
- NISAR GCOV product documentation: https://hyp3-docs.asf.alaska.edu/nisar-docs/gcov/ . Granule identity is inherited from user-provided metadata; original provider authentication was not independently established.
- Ritu Yadav, Modified Sen1Floods11 Dataset for Change Detection, Zenodo 7946594: https://doi.org/10.5281/zenodo.7946594 . CC BY 4.0 attribution as recorded in the supplied benchmark-source.json. Three supplied chips are preserved unchanged.
- U.S. Census TIGERweb and FEMA/ORNL USA Structures: exact source URLs and query metadata in data/geography/geography-source.json. No new source coverage is claimed.
- scikit-learn threshold-selection guidance: https://scikit-learn.org/stable/modules/classification_threshold.html . Training and threshold validation must be separate; the added comparisons use train-country out-of-fold predictions and reserve Spain labels for evaluation.
- scikit-learn leakage guidance: https://scikit-learn.org/stable/common_pitfalls.html . Test labels are not used for selecting the threshold. The spatial comparator test deliberately changes held-out labels and verifies that predictions and selected policy stay identical.

Only three external chips are included. Training-country validation did not translate into improved Spain performance for the added policies. All methods and poorer results are retained; no attempt was made to alter the held-out labels or present a weaker model as a successful upgrade.
