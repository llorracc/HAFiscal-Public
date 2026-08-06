# `ksweep/` — two unrelated sweep families, kept apart on purpose

Both families were written by `fa970b31` ("K-sweep on the ergodic metric") and
originally sat side by side in this directory. Their labels collided only in
case (`K3.json` vs `k3.json`, `K6.json` vs `k6.json`), which is unrepresentable
on a case-insensitive filesystem (macOS APFS default): only one file of each
pair could exist, so the other family's numbers silently took its place. The
decay family was moved into `pf_decay/` to make the collision impossible.

| location | family | keys |
|---|---|---|
| `K1.json` … `K6.json` | K-sweep arms — grid provisioning (`tm_acount`) | `label`, `axtra_count`, `tm_acount`, `groups` (per-education `distance`/`beta`/`nabla` + wealth moments) |
| `pf_decay/*.json` | power-law decay extrapolation arms (`HAFISCAL_PF_DECAY_*`) | `label`, `beta_mode`, `DiscFac`, `aXtraMax`, `env`, `n_powerlaw_slices` |

These are archival run artifacts: nothing in the repo reads them. **Do not add
new files here whose names differ from an existing one only by case.**
