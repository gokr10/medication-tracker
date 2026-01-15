from __future__ import annotations

import inspect
from inspect import isclass
from typing import List, Type

from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql

from application import db, models


def get_tables():
    # type: () -> List[Type[db.Model]]
    """
    Get the defined models by inspecting models file
    """
    table_classes = []
    for name, table_class in inspect.getmembers(models):
        if isclass(table_class) and issubclass(table_class, db.Model):
            table_classes.append(table_class)
    return table_classes


def print_ddls():
    """
    Print out the DDL statements for the defined models
    """
    for table in get_tables():
        print(CreateTable(table.__table__).compile(dialect=postgresql.dialect()))
