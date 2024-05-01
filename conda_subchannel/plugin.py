from conda import plugins

from .cli import configure_parser, execute


@plugins.hookimpl
def conda_subcommands():
    yield plugins.CondaSubcommand(
        name="subchannel",
        summary="Create subsets of conda channels thanks to CEP-15 metadata",
        action=execute,
        configure_parser=configure_parser,
    )
