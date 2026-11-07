# Visiongraph model catalog

Each `.json` file here is one model catalog entry, registered as
`haybale-visiongraph:catalog:<file name without .json>`.

They are the curated models the estimator nodes run, from the
[visiongraph model repository](https://huggingface.co/cansik/visiongraph), pinned to commit
`0de7ab36c9cf7d0843a1a19fd8c83db34a19d8a3`. Digests and sizes were read from that commit, and
licences from its `MODEL_ATTRIBUTIONS.md`. `commercial` is true for the Apache-2.0 models; the
Ultralytics models stay false because AGPL-3.0 use comes with conditions.

Each entry needs a matching item in the node's `MODELS`.
