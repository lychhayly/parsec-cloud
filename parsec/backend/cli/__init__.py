# Parsec Cloud (https://parsec.cloud) Copyright (c) AGPLv3 2019 Scille SAS

import click

from parsec.backend.cli.init import init_cmd
from parsec.backend.cli.run import run_cmd
from parsec.backend.cli.migration import make_migration


__all__ = ("backend_cmd",)


@click.group()
def backend_cmd():
    pass


backend_cmd.add_command(run_cmd, "run")
backend_cmd.add_command(init_cmd, "init")
backend_cmd.add_command(make_migration, "make_migration")
