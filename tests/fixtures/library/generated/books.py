from __future__ import annotations

import re
import sys
from datetime import (
    date,
    datetime,
    time
)
from decimal import Decimal
from enum import Enum
from typing import (
    Any,
    ClassVar,
    Literal,
    Optional,
    Union
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer
)
from rdf_persistence import (
    AggregateRoot,
    Described,
    MembershipRule,
    Principal,
    ReferenceCollection,
    Tracked
)


metamodel_version = "1.12.0"
version = "None"


from rdf_persistence.domain.base import RpModel as ConfiguredBaseModel



class LinkMLMeta(RootModel):
    root: dict[str, Any] = {}
    model_config = ConfigDict(frozen=True)

    def __getattr__(self, key:str):
        return getattr(self.root, key)

    def __getitem__(self, key:str):
        return self.root[key]

    def __setitem__(self, key:str, value):
        self.root[key] = value

    def __contains__(self, key:str) -> bool:
        return key in self.root


linkml_meta = None

class Genre(str, Enum):
    "The literary genres a book can belong to."
    FICTION = "fiction"
    "Invented narrative."
    NONFICTION = "nonfiction"
    "Factual writing."
    POETRY = "poetry"
    "Verse."



class Book(Tracked, Described, AggregateRoot):
    "A book held by a library; an aggregate root that owns its chapters."
    isbn: Optional[str] = Field(default=None, title="ISBN", description="The International Standard Book Number of the book.")
    authors: Optional[list[str]] = Field(default=None, title="Authors", description="The names of the book\u0027s authors.")
    published: Optional[date] = Field(default=None, title="Publication date", description="The date the book was published.")
    genre: Optional[Genre] = Field(default=None, title="Genre", description="The literary genre of the book.")
    chapters: Optional[list[Chapter]] = Field(default=None, title="Chapters", description="The chapters of the book; they live in the book\u0027s graph.")
    shelf: Optional[str] = Field(default=None, title="Shelf", description="The shelf the book stands on, another aggregate, stored as its IRI.")
    sequel_of: Optional[str] = Field(default=None, title="Sequel of", description="The book this one follows, another aggregate, stored as its IRI.")
    id: str = Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    label: str = Field(default=..., title="Label", description="The preferred label of the object.")
    description: Optional[str] = Field(default=None, title="Description", description="A free-text description of the object.")
    created: Optional[datetime ] = Field(default=None, title="Created", description="The time the graph was first committed.")
    modified: Optional[datetime ] = Field(default=None, title="Modified", description="The time the graph was last committed.")
    creator: Optional[str] = Field(default=None, title="Creator", description="The principal that first committed the graph.")
    contributor: Optional[list[str]] = Field(default=None, title="Contributor", description="A principal that committed a later version of the graph.")


class Shelf(ReferenceCollection, Tracked, Described, AggregateRoot):
    "A shelf of the library; an aggregate root that books are placed on, and a collection of the books it names."
    id: str = Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    label: str = Field(default=..., title="Label", description="The preferred label of the object.")
    description: Optional[str] = Field(default=None, title="Description", description="A free-text description of the object.")
    created: Optional[datetime ] = Field(default=None, title="Created", description="The time the graph was first committed.")
    modified: Optional[datetime ] = Field(default=None, title="Modified", description="The time the graph was last committed.")
    creator: Optional[str] = Field(default=None, title="Creator", description="The principal that first committed the graph.")
    contributor: Optional[list[str]] = Field(default=None, title="Contributor", description="A principal that committed a later version of the graph.")
    member_class: str = Field(default=..., title="Member class", description="The schema name of the class of the aggregates the collection collects.")
    had_member: Optional[list[str]] = Field(default=None, title="Had member", description="The IRIs of the aggregates the collection names as its members.")
    membership_rule: Optional[MembershipRule] = Field(default=None, title="Membership rule", description="The rule that says which aggregates of the member class belong to the collection.")


class Chapter(Described):
    "A chapter of a book, known by its number rather than a label; part of the book\u0027s aggregate. It owns its notes."
    number: Optional[int] = Field(default=None, title="Chapter number", description="The position of a chapter in its book.")
    notes: Optional[list[Note]] = Field(default=None, title="Notes", description="The notes on a chapter; they live in the book\u0027s graph.")
    id: str = Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    label: Optional[str] = Field(default=None, title="Label", description="The preferred label of the object.")  # type: ignore[assignment]
    description: Optional[str] = Field(default=None, title="Description", description="A free-text description of the object.")


class Note(Described):
    "A short note on a chapter, with a label of its own."
    text: Optional[str] = Field(default=None, title="Text", description="The text of a note.")
    about: Optional[str] = Field(default=None, title="About", description="The book a note is about, another aggregate, stored as its IRI.")
    shade: Optional[str] = Field(default=None, title="Shade", description="The colour of the note\u0027s paper.")
    id: str = Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    label: str = Field(default=..., title="Label", description="The preferred label of the object.")
    description: Optional[str] = Field(default=None, title="Description", description="A free-text description of the object.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
Book.model_rebuild()
Shelf.model_rebuild()
Chapter.model_rebuild()
Note.model_rebuild()
