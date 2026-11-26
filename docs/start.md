# Getting started

## Installation

`conda-subchannel` is a `conda` subcommand plugin with no extra dependencies. As such you need to install it in your `base` environment:

```shell
$ conda install -n base -c conda-forge conda-subchannel
```

Once the installation has succeeded, this command should run without errors:

```shell
$ conda subchannel --help
```

## Your first subchannel

We call _subchannel_ to a subset of an already existing conda channel.

Let's say we start with conda-forge but we are not interested in keeping EOL'd versions of Python around. We could fetch the `repodata.json` files and remove any `python` record with version `3.7` and below.

The resulting `repodata.json` will not have these records present and as a result the solver will never see them or load them! All we have to do is put our new `repodata.json` in a location that looks like a conda channel and point our conda client there!

This works wonderfully for _dry-run_ solves, but downloads won't work yet. The problem is that conda clients always assumed that the downloadable artifacts (e.g. `python-3.9.3-h123abc_0.conda`) were available next to the `repodata.json`. In your new location, these files won't be found unless you also copy them over... and that's expensive to store and serve!

Fortunately, CEP-15 introduced a new metadata field in the `repodata.json` file, `base_url` that tells the conda client to find artifacts in that location instead of using the `repodata.json` location. So now you just need to set `base_url` to the conda-forge location and you are done!

You can do all those steps manually, but `conda subchannel` is here to help! To summarize, this is what we will do for you:

1. Fetch the remote channel and create a local copy.
2. Edit the `repodata.json` file(s) and choose which records will be kept in the new subchannel according to your provided filter conditions.
3. Add `base_url` pointing to the original remote location.
4. Publish the `repodata.json` file(s) in a channel-like directory structure.

### Create your local channel

Let's say we want to make sure that our team only uses `python=3.10` on `linux-64`. We can create a subchannel that removes any versions that don't match that specification. If we start with conda-forge:

```
$ conda subchannel -c conda-forge --subdir linux-64 --keep-tree python=3.10
```

You should see this output:

```
Syncing source channel: done
 - conda-forge linux-64
 - conda-forge noarch
Filtering package records: done
 - Reduced from 669094 to 1100 records
Writing output to subchannel: done
```

The files will be available under `./subchannel`:

```
$ tree -sh ./subchannel
./subchannel
├── [ 169]  index.md
├── [ 192]  linux-64
│   ├── [ 736]  index.md
│   ├── [591K]  repodata.json
│   ├── [ 81K]  repodata.json.bz2
│   └── [ 82K]  repodata.json.zst
└── [ 192]  noarch
    ├── [ 731]  index.md
    ├── [ 10K]  repodata.json
    ├── [2.2K]  repodata.json.bz2
    └── [1.9K]  repodata.json.zst
```

### Use it with `conda`

You can now use it locally to make sure you can _only_ install `python=3.10`.

This works:

```
$ conda create -dnx --override-channel -c ./subchannel python=3.10 --platform=linux-64
Channels:
 - ./subchannel
Platform: linux-64
Collecting package metadata (repodata.json): done
Solving environment: done

## Package Plan ##

  environment location: ...

  added / updated specs:
    - python=3.10


The following packages will be downloaded:

    package                    |            build
    ---------------------------|-----------------
    _libgcc_mutex-0.1          |      conda_forge           3 KB  ./subchannel
    _openmp_mutex-4.5          |            2_gnu          23 KB  ./subchannel
    bzip2-1.0.8                |       hd590300_5         248 KB  ./subchannel
    ca-certificates-2024.2.2   |       hbcca054_0         152 KB  ./subchannel
    ld_impl_linux-64-2.40      |       hf3520f5_1         691 KB  ./subchannel
    libffi-3.4.2               |       h7f98852_5          57 KB  ./subchannel
    libgcc-ng-13.2.0           |       h77fa898_7         758 KB  ./subchannel
    libgomp-13.2.0             |       h77fa898_7         412 KB  ./subchannel
    libnsl-2.0.1               |       hd590300_0          33 KB  ./subchannel
    libsqlite-3.45.3           |       h2797004_0         840 KB  ./subchannel
    libuuid-2.38.1             |       h0b41bf4_0          33 KB  ./subchannel
    libxcrypt-4.4.36           |       hd590300_1          98 KB  ./subchannel
    libzlib-1.2.13             |       h4ab18f5_6          60 KB  ./subchannel
    ncurses-6.5                |       h59595ed_0         867 KB  ./subchannel
    openssl-3.3.0              |       h4ab18f5_3         2.8 MB  ./subchannel
    python-3.10.14             |hd12c33a_0_cpython        24.3 MB  ./subchannel
    readline-8.2               |       h8228510_1         275 KB  ./subchannel
    tk-8.6.13                  |noxft_h4845f30_101         3.2 MB  ./subchannel
    tzdata-2024a               |       h0c530f3_0         117 KB  ./subchannel
    xz-5.2.6                   |       h166bdaf_0         409 KB  ./subchannel
    ------------------------------------------------------------
                                           Total:        35.2 MB

The following NEW packages will be INSTALLED:

  _libgcc_mutex      subchannel/linux-64::_libgcc_mutex-0.1-conda_forge
  _openmp_mutex      subchannel/linux-64::_openmp_mutex-4.5-2_gnu
  bzip2              subchannel/linux-64::bzip2-1.0.8-hd590300_5
  ca-certificates    subchannel/linux-64::ca-certificates-2024.2.2-hbcca054_0
  ld_impl_linux-64   subchannel/linux-64::ld_impl_linux-64-2.40-hf3520f5_1
  libffi             subchannel/linux-64::libffi-3.4.2-h7f98852_5
  libgcc-ng          subchannel/linux-64::libgcc-ng-13.2.0-h77fa898_7
  libgomp            subchannel/linux-64::libgomp-13.2.0-h77fa898_7
  libnsl             subchannel/linux-64::libnsl-2.0.1-hd590300_0
  libsqlite          subchannel/linux-64::libsqlite-3.45.3-h2797004_0
  libuuid            subchannel/linux-64::libuuid-2.38.1-h0b41bf4_0
  libxcrypt          subchannel/linux-64::libxcrypt-4.4.36-hd590300_1
  libzlib            subchannel/linux-64::libzlib-1.2.13-h4ab18f5_6
  ncurses            subchannel/linux-64::ncurses-6.5-h59595ed_0
  openssl            subchannel/linux-64::openssl-3.3.0-h4ab18f5_3
  python             subchannel/linux-64::python-3.10.14-hd12c33a_0_cpython
  readline           subchannel/linux-64::readline-8.2-h8228510_1
  tk                 subchannel/linux-64::tk-8.6.13-noxft_h4845f30_101
  tzdata             subchannel/noarch::tzdata-2024a-h0c530f3_0
  xz                 subchannel/linux-64::xz-5.2.6-h166bdaf_0



DryRunExit: Dry run. Exiting.
```

These do not, as expected. `python=3.9` is not available because we filtered it out:

```
$ conda create -dnx --override-channel -c ./subchannel python=3.9 --platform=linux-64
Channels:
 - ./subchannel
Platform: linux-64
Collecting package metadata (repodata.json): done
Solving environment: failed

PackagesNotFoundError: The following packages are not available from current channels:

  - python=3.9*

Current channels:

  - ./subchannel

To search for alternate channels that may provide the conda package you're
looking for, navigate to

    https://anaconda.org
```

`python=3.10` is not available on `osx-64`, only `linux-64`:

```
$ conda create -dnx --override-channel -c ./subchannel python=3.10 --platform=osx-64
Channels:
 - ./subchannel
Platform: osx-64
Collecting package metadata (repodata.json): done
Solving environment: failed

PackagesNotFoundError: The following packages are not available from current channels:

  - python=3.10*

Current channels:

  - ./subchannel

To search for alternate channels that may provide the conda package you're
looking for, navigate to

    https://anaconda.org

and use the search bar at the top of the page.
```

Check how to work with the other filters in {doc}`usage`.

### Publish it

You can push this directory structure to any location online, including:

- Static website providers like Github Pages, Netlify or Vercel
- Any HTTP(S) or FTP servers you control
- Network locations that can be mounted on your filesystem
- S3 buckets

Just remember to to maintain the directory tree intact, namely:

1. Make sure your channel is served under a directory, not the root of the server. In other words, you want them available at `https://my-channels.org/my-channel/noarch/repodata.json`, and not `https://my-channels.org/noarch/repodata.json`. Otherwise conda clients might fail to assign a name to the channel.
2. You always need `noarch/repodata.json` even if empty.
3. In practice, a platform specific subdir will also need to be there (e.g. `linux-64/repodata.json`).


```{tip}
We also provide a {doc}`Github Actions action <action>` you can use to both _run_ `conda subchannel` and then _publish_ it to the Github Pages deployment in the repository
```
