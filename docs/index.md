# conda-subchannel

Welcome to the conda-subchannel documentation! The conda-subchannel project
allows you to republish a subset of existing channels under a static website
by leveraging [CEP-15][CEP-15].

This is mostly targeted at tasks like:

- Only enabling certain versions of known packages to group of users (e.g. team environments,
  plugin ecosystems, etc.).
- Snapshotting known states of a channel for checkpoints of reproducibility.
- Removing unwanted dependencies from a channel (e.g. incompatible with of a license).

## Learn

::::{grid} 2

:::{grid-item-card} 🏡 Getting started
:link: start
:link-type: doc
New to conda-subchannel? Start here to learn the essentials
:::

:::{grid-item-card} 🔧 Usage
:link: usage
:link-type: doc
Learn about all available configuration options

::::

## Development

::::{grid} 2

:::{grid-item-card} 📝 Changelog
:link: https://github.com/conda-incubator/conda-subchannel/blob/main/CHANGELOG.md
Recent changes and updates to the project
:::
:::{grid-item-card} 🐞 Found a bug?
:link: https://github.com/conda-incubator/conda-subchannel/issues/new/choose
File an issue in our tracker
:::
::::


```{toctree}
:hidden:

start
usage
action
```

[CEP-15]: https://github.com/conda/ceps/blob/a0807260bb5c303bbd99c690eb1ea993373f9fd9/cep-15.md
