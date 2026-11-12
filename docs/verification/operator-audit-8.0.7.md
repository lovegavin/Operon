# Operator Library Audit 8.0.7

Library 8.0.7 is a patch release on top of 8.0.6. It inherits the 8.0.6 L1-L5 evidence and adds targeted fixes for the 4.1.6 environment reports.

## Delta evidence

| Layer | Check | Result |
| --- | --- | --- |
| L1 | registry descriptors | 1063 operators / 108 readers / 79 routes / 0 errors; bundle sha `d18803b7e9a9daf0f69f9c80030c9bce3dac59907860095333cdeacfbe5294d9` |
| L1 | environment manifest | `openmm81` includes `venv_shared`, `setuptools<81`, PDBFixer pinned URL |
| L2 | `tests/test_environments.py` | manifest/import/probe assertions pass |
| L2 | `tests/test_extension249.py` | 1MEL golden: 46 residues, 4 columns, A/L ΔSASA at 1e-6 |
| L4 | clean Windows 4.1.7 install | `openmm81` ready; 157,355,136 B / 3,823 files; all probes OK; bundle `d18803b7…` |
| L4 | PDBFixer smoke | 8,148 atoms / 554 residues on `vhh_1mel.pdb` |
| L4 | install evidence | `verification/operator-audit-8.0.7/application-4.1.7-openmm81.json` |
| L4 | Windows bundle | sha `19092668279873c3561be2c0e5a308acae944cf88538c9db1b0ed63a57da31ea` |

## Application compatibility

The 8.0.7 release is built against the 4.0.8 application line with forward-minimum metadata (`minimum_application: 4.1.0`). The 4.1.7 runtime was used for the environment install proof. The 4.1.0 runtime acceptance remains a post-release gate; a stock 4.0.8 application cannot import the embedded environment manifest.

## Not changed

- No operator algorithm was changed in this release.
- Remote environment provisioning and UI progress remain application work.
- The 4.0.8 interface numbers are historical and are not asserted as a golden baseline.