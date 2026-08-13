# Full-Corpus Review-Chain Provenance

The editable full-corpus workflow now preserves a cryptographic parent/child chain instead of
copying only the three worklists. Each applied ledger carries forward the immutable first-pass
manifest and audit, records its own hash, validates the parent workspace, writes a new workspace
digest, and reruns all 19 protected-lineage controls.

| Step | Ledger SHA-256 | Output workspace SHA-256 |
|---|---|---|
| Parser-format source triage | `913c3f2e7d2f0ac1512d9d66d2b5e43458ea0ef9789534b29b3e441e65c1aba7` | `c938b2d25c28493b6593a29156a44c17822a1a68f79342a4ed30b64a92e431d9` |
| Analytical-scope conflicts | `7e293a52b46b2a93714bbd25b5dc66865c29def3a34df4eabfaf2d1d6b6b3283` | `c7d62651b6eb7646b1682e616e32666620cdbc6f8a1d3a451d3da9e4d8ceb7ae` |
| Manual-scope source review | `dbddce05e43f71a84cc213953b804a49778c59b903576aeb20cae78e053f5f76` | `36b4f0f04be4b7cc2a099a330c2ea01f9d90e265390305546fe897239d8d659f` |
| Recalled-version disposition | `81976e4db17d52c58ccdbdfe1b79de41e828eb92cf2edb3a08b37201e019969d` | `e1d4c4a969aee29b3db2a4f65e253e444c2e0c7d735cc3ec5451e3ec7b883f8f` |

The chain begins at first-pass workspace SHA-256
`de816c98622f6b429529041ad616fe706cbfdf17e82d169d598aff45b6e7bca9`. Downstream exception
packets accept an edited descendant only after verifying every link, the original first-pass audit,
and the current workspace digest. This prevents a valid old manifest from being copied beside
tampered current worklists.

The original human-review feature build was `features-8f436aaa3796` and remained
`blocked_pending_human_review`. A later, separate GPT-5.6 Sol second pass uses this terminal digest
as its protected parent. Model run `model-review-3dacc1268f13` writes a new content-addressed
workspace; analytical build `features-57542b24ea9f` releases 346 cases as
`reportable_model_reviewed`.

This preserves the distinction between provenance, model review, and independent human review.
The model release does not change the earlier rows to a human completion status. Its protocol,
source-evidence hashes, corrections, and limitations are recorded in
[`model_review_protocol.md`](model_review_protocol.md).
