# Usage

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
  --remove SPEC         Remove packages matching this spec. Can be used several times.
  -h, --help            Show this help message and exit.
  ```