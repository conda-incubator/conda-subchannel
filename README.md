# conda-subchannel

Create subsets of conda channels thanks to CEP-15 metadata

## conda plugin

```bash
$ conda install -n base conda-subchannel
$ conda subchannel --channel=conda-forge --keep-tree python=3.9
$ python -m http.serve --directory subchannel/
```

## Github Actions action

```yaml
name: Create conda subchannel

on:
  push:
    branches:
      - main
  pull_request:

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: write  # to deploy to GH Pages automatically
    concurrency:
      group: ${{ github.workflow }}-${{ github.ref }}
    steps:
      - uses: conda-incubator/conda-subchannel@main
        with:
          channel: conda-forge
          keep-trees: python=3.9
```
