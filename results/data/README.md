## Research dataset

The dataset collected during the 30-day basil deployment, from 15 April to
15 May 2026, is available as a compressed JSON export:

[Download the dataset](docs/data/dtwin-data-2026-05-15T11-25-11-175Z.json.gz)

The archive contains the complete JSON export used to derive the results
reported in the accompanying paper. Its top-level sections are `metadata`,
`plant`, `readings`, `health`, `forecasts`, `recommendations`, `actions`,
and `alerts`.

Decompress the archive with:

```bash
gzip -dk docs/data/dtwin-data-2026-05-15T11-25-11-175Z.json.gz
