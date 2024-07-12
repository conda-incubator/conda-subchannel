# Usage

## CLI

```
$ conda subchannel --help
usage: conda subchannel -c CHANNEL [--repodata-fn REPODATA_FN] [--base-url BASE_URL] [--output PATH] [--subdir PLATFORM] [--after TIME] [--before TIME] [--keep-tree SPEC] [--keep SPEC] [--remove SPEC] [-h]

Create subsets of conda channels thanks to CEP-15 metadata

options:
  -c CHANNEL, --channel CHANNEL
                        Source conda channel.
  --repodata-fn REPODATA_FN
                        Source repodata file to process from channel.
  --base-url BASE_URL   URL where the packages will be available. Defaults to the base URL for
                        '--channel'. Only needed if the user wants to mirror the required packages
                        separately.
  --output PATH         Directory where the subchannel repodata.json artifacts will be written to.
  --subdir PLATFORM, --platform PLATFORM
                        Process records for this platform. Defaults to osx-arm64. noarch is always included. Can be used several times.
  --after TIME          Timestamp as ts:<float> or date as YYYY-[MM[-DD[-HH[-MM[-SS]]]]]
  --before TIME         Timestamp as ts:<float> or date as YYYY-[MM[-DD[-HH[-MM[-SS]]]]]
  --keep-tree SPEC      Keep packages matching this spec and their dependencies. Can be used
                        several times.
  --keep SPEC           Keep packages matching this spec only. Can be used several times.
  --prune SPEC          Remove the distributions of this package name that do not match the
                        given constraints.
  --remove SPEC         Remove packages matching this spec. Can be used several times.
  -h, --help            Show this help message and exit.
  ```


## Filtering algorithm

The filtering algorithm operates in two phases: selection

In the first phase, we _select_ which records are going to be kept. Everything else is removed.

1. A selection list is built. Records in this list are added if:
  - They match specs in `--keep-tree`, or any of the dependencies in their tree (assessed recursively).
  - They match any of the specs in `--keep`.
  - Their timestamp is within the limits marked by `--before` and `--after`, when applicable. 
2. At this point, records that didn't make it to the selection list are removed.
3. The specs defined `--prune` are processed. Records that have the same name but don't match the spec are removed. Everything else is ignored.
4. Records matching any of the specs in `--remove` are filtered out.
