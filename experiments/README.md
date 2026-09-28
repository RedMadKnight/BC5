# experiments/

One directory per experiment: `NNNN-short-name/` (four-digit number, next free one, kebab-case name), e.g. `0002-bc5-mount-gate/`.

Each directory contains:

- `README.md` — written from [`TEMPLATE.md`](TEMPLATE.md): **Question**, **Setup**, **Result**, **Verdict**.
- the scripts needed to rerun it;
- `raw/` — logs, captures, measurements. Files over 1 MB are not committed (see `.gitignore`); say in the README how to regenerate them.

Rules:

- One question per experiment. If the answer raises a new question, that is a new experiment.
- Once the Verdict is written, the directory is frozen. A rerun or correction is a new experiment that links to the old one.
- A phase gate in `docs/PHASES.md` is passed only when an experiment's Verdict says so, with evidence.
- Anything that submits to `amdgpu` must name the risk (machine reset) in Setup and run only with an explicit `--submit`.
- No Sony material in `raw/`: no game files, firmware or decrypted binaries. Command-buffer captures are fine; the shader or data blobs they reference are not committed.
