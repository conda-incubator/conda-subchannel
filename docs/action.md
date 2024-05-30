# Github Actions action

We also provide a convenience Actions wrapper you can use in your CI/CD workflows. See this example:

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
      - uses: jaimergp/conda-subchannel@main  # pin to a version once it works
        with:
          channel: conda-forge
          keep-trees: python=3.9
```

```{note}
By default, this action will also publish the resulting files to GH Pages. If you don't want that, make sure to set `gh-pages-branch` to an empty string.
```

All options are documented in the [`action.yml` file](https://github.com/jaimergp/conda-subchannel/blob/main/action.yml).
