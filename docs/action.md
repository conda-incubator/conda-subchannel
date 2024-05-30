# Github Actions action

We also provide a convenience Actions wrapper you can use in your CI/CD workflows. All options are documented in the [`action.yml` file](https://github.com/jaimergp/conda-subchannel/blob/main/action.yml).

This will run `conda subchannel` for you and then upload the resulting files to GH Pages. A few `index.md` files are thrown in so Github Pages renders them in a nice way. They will summarize which subdirs are available and some details about the available repodata.json files. See the live demo below for more details.

## Live demo

A simple example (only `python=3.9` is kept) is available at [`jaimergp/conda-subchannel-demo`](https://github.com/jaimergp/conda-subchannel-demo). This repository publishes its subchannel at https://jaimergp.github.io/conda-subchannel-demo/, which can be used with conda clients like:

```
$ conda create --override-channels -c https://jaimergp.github.io/conda-subchannel-demo/ python=3.9
```
