from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass
from sqlalchemy import MetaData


class Base(DeclarativeBase):
    metadata = MetaData(schema="core")
