# Prototype 1 Release Artifacts

Release identity: **Prototype 1 RC1 (`0.1.0-rc1`)**.

| Artifact | Classification | SHA-256 / source |
|---|---|---|
| `data/tokenizer_v2.json` | Required external/local artifact | `D6C21CD45CEDB1D78AC476C0B3635A26C2A7C147C033E85E5151016C9D4E21DE` |
| `checkpoints/v2/reasoning_model_v1.pt` | Required external/local artifact; not tracked in Git | `E32AC5BE88E249C19E74355A8A3C352B62BF57CB03C0E6860BCA8C6198F4EFA3` |
| `data/wikitext_v2.txt` | Configured tracked knowledge artifact | `E543F070C75D1D636CE3936F69094A785A53E794024A876D108E40161958D01B` |
| `data/knowledge_extra_v1.txt` | Configured tracked knowledge artifact | `C61FCFF405EE84EAE9A818993787EF04FBA9ED537901EDC63D1995367B7A49CA` |
| `data/runtime_uploads/` | Generated runtime persistence | Created by ingestion; not a release input |
| `logs/` | Generated validation output | Optional, ignored/generated |

Validated environment: Windows, Python 3.11, Torch 2.7.1+cu128, CUDA 12.8,
NVIDIA GeForce RTX 3050 Laptop GPU (6 GB). Configuration may override model,
tokenizer, data, and upload locations through the documented environment
variables.

`requirements.txt` was installed to completion in a disposable Python 3.11
environment. The pinned `tokenizers==0.23.1` is resolvable and compatible
with the validated runtime; the earlier failed attempt used Python 3.9.
