#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
zip -r ../Phase2_G2-10_23I-0769_Source.zip main.tex refs.bib architecture.png sections
