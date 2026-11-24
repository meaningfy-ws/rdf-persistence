from __future__ import annotations

import re
import sys
from datetime import (
    date,
    datetime,
    time
)
from decimal import Decimal as _Decimal
from enum import Enum as _Enum
from typing import (
    Any as _Any,
    ClassVar as _ClassVar,
    Literal as _Literal,
    Optional as _Optional,
    Union as _Union
)

from pydantic import (
    BaseModel as _BaseModel,
    ConfigDict as _ConfigDict,
    Field as _Field,
    RootModel as _RootModel,
    SerializationInfo as _SerializationInfo,
    SerializerFunctionWrapHandler as _SerializerFunctionWrapHandler,
    field_validator,
    model_serializer
)
from rdf_persistence import (
    AggregateRoot,
    Described,
    MembershipRule,
    Principal,
    ReferenceCollection,
    Tracked,
    UnderWorkflow
)


metamodel_version = "1.12.0"
version = "None"


from rdf_persistence import RpModel as ConfiguredBaseModel

linkml_meta = None

class Genre(str, _Enum):
    "The literary genres a book can belong to."
    FICTION = "fiction"
    "Invented narrative."
    NONFICTION = "nonfiction"
    "Factual writing."
    POETRY = "poetry"
    "Verse."



class Book(UnderWorkflow, Tracked, Described, AggregateRoot):
    "A book held by a library; an aggregate root that owns its chapters."
    isbn: _Optional[str] = _Field(default=None, title="ISBN", description="The International Standard Book Number of the book.")
    authors: _Optional[list[str]] = _Field(default=None, title="Authors", description="The names of the book\u0027s authors.")
    published: _Optional[date] = _Field(default=None, title="Publication date", description="The date the book was published.")
    genre: _Optional[Genre] = _Field(default=None, title="Genre", description="The literary genre of the book.")
    chapters: _Optional[list[Chapter]] = _Field(default=None, title="Chapters", description="The chapters of the book; they live in the book\u0027s graph.")
    shelf: _Optional[str] = _Field(default=None, title="Shelf", description="The shelf the book stands on, another aggregate, stored as its IRI.")
    sequel_of: _Optional[str] = _Field(default=None, title="Sequel of", description="The book this one follows, another aggregate, stored as its IRI.")
    written_by: _Optional[str] = _Field(default=None, title="Written by", description="The author of the book, another aggregate, stored as its IRI.")
    id: str = _Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    label: str = _Field(default=..., title="Label", description="The preferred label of the object.")
    description: _Optional[str] = _Field(default=None, title="Description", description="A free-text description of the object.")
    created: _Optional[datetime ] = _Field(default=None, title="Created", description="The time the graph was first committed.")
    modified: _Optional[datetime ] = _Field(default=None, title="Modified", description="The time the graph was last committed.")
    creator: _Optional[str] = _Field(default=None, title="Creator", description="The principal that first committed the graph.")
    contributor: _Optional[list[str]] = _Field(default=None, title="Contributor", description="A principal that committed a later version of the graph.")
    workflow_status: _Optional[str] = _Field(default=None, title="Workflow status", description="The current state of the aggregate, the IRI of a state of its workflow.")


class Shelf(ReferenceCollection, Tracked, Described, AggregateRoot):
    "A shelf of the library; an aggregate root that books are placed on, and a collection of the books it names."
    id: str = _Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    label: str = _Field(default=..., title="Label", description="The preferred label of the object.")
    description: _Optional[str] = _Field(default=None, title="Description", description="A free-text description of the object.")
    created: _Optional[datetime ] = _Field(default=None, title="Created", description="The time the graph was first committed.")
    modified: _Optional[datetime ] = _Field(default=None, title="Modified", description="The time the graph was last committed.")
    creator: _Optional[str] = _Field(default=None, title="Creator", description="The principal that first committed the graph.")
    contributor: _Optional[list[str]] = _Field(default=None, title="Contributor", description="A principal that committed a later version of the graph.")
    member_class: str = _Field(default=..., title="Member class", description="The schema name of the class of the aggregates the collection collects.")
    has_part: _Optional[list[str]] = _Field(default=None, title="Has part", description="The IRIs of the aggregates the collection names as its members.")
    membership_rule: _Optional[MembershipRule] = _Field(default=None, title="Membership rule", description="The rule that says which aggregates of the member class belong to the collection.")
    nests: _Optional[bool] = _Field(default=None, title="Nests", description="Whether the collection may hold collections of its own class and member class as members, to any depth. Absent means false.")


class BookCollection(ReferenceCollection, Described, AggregateRoot):
    "A collection of books, whose member class is fixed to Book by a slot usage."
    id: str = _Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    label: str = _Field(default=..., title="Label", description="The preferred label of the object.")
    description: _Optional[str] = _Field(default=None, title="Description", description="A free-text description of the object.")
    member_class: _Literal["Book"] = _Field(default=..., title="Member class", description="The schema name of the class of the aggregates the collection collects.")
    has_part: _Optional[list[str]] = _Field(default=None, title="Has part", description="The IRIs of the aggregates the collection names as its members.")
    membership_rule: _Optional[MembershipRule] = _Field(default=None, title="Membership rule", description="The rule that says which aggregates of the member class belong to the collection.")
    nests: _Optional[bool] = _Field(default=None, title="Nests", description="Whether the collection may hold collections of its own class and member class as members, to any depth. Absent means false.")


class Display(Tracked, Described, AggregateRoot):
    "A display of the library, featuring several books through a slot that is single-valued where it is declared."
    features: list[str] = _Field(default=..., title="Features", description="A book a display features, another aggregate, stored as its IRI; single-valued where declared.")
    id: str = _Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    label: str = _Field(default=..., title="Label", description="The preferred label of the object.")
    description: _Optional[str] = _Field(default=None, title="Description", description="A free-text description of the object.")
    created: _Optional[datetime ] = _Field(default=None, title="Created", description="The time the graph was first committed.")
    modified: _Optional[datetime ] = _Field(default=None, title="Modified", description="The time the graph was last committed.")
    creator: _Optional[str] = _Field(default=None, title="Creator", description="The principal that first committed the graph.")
    contributor: _Optional[list[str]] = _Field(default=None, title="Contributor", description="A principal that committed a later version of the graph.")


class Author(Tracked, Described, AggregateRoot):
    "An author of the library; an aggregate root that books point at, and that cannot be deleted while a book still does."
    id: str = _Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    label: str = _Field(default=..., title="Label", description="The preferred label of the object.")
    description: _Optional[str] = _Field(default=None, title="Description", description="A free-text description of the object.")
    created: _Optional[datetime ] = _Field(default=None, title="Created", description="The time the graph was first committed.")
    modified: _Optional[datetime ] = _Field(default=None, title="Modified", description="The time the graph was last committed.")
    creator: _Optional[str] = _Field(default=None, title="Creator", description="The principal that first committed the graph.")
    contributor: _Optional[list[str]] = _Field(default=None, title="Contributor", description="A principal that committed a later version of the graph.")


class LendingItem(AggregateRoot):
    "Something the library lends; an abstract aggregate root, so a loan points at any of its kinds by IRI."
    id: str = _Field(default=..., title="Identifier", description="The IRI that identifies the object.")


class Magazine(LendingItem, Tracked, Described):
    "A magazine the library lends; a concrete kind of item."
    id: str = _Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    label: str = _Field(default=..., title="Label", description="The preferred label of the object.")
    description: _Optional[str] = _Field(default=None, title="Description", description="A free-text description of the object.")
    created: _Optional[datetime ] = _Field(default=None, title="Created", description="The time the graph was first committed.")
    modified: _Optional[datetime ] = _Field(default=None, title="Modified", description="The time the graph was last committed.")
    creator: _Optional[str] = _Field(default=None, title="Creator", description="The principal that first committed the graph.")
    contributor: _Optional[list[str]] = _Field(default=None, title="Contributor", description="A principal that committed a later version of the graph.")


class Pamphlet(LendingItem, Tracked, Described):
    "A pamphlet the library lends; a concrete kind of item."
    id: str = _Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    label: str = _Field(default=..., title="Label", description="The preferred label of the object.")
    description: _Optional[str] = _Field(default=None, title="Description", description="A free-text description of the object.")
    created: _Optional[datetime ] = _Field(default=None, title="Created", description="The time the graph was first committed.")
    modified: _Optional[datetime ] = _Field(default=None, title="Modified", description="The time the graph was last committed.")
    creator: _Optional[str] = _Field(default=None, title="Creator", description="The principal that first committed the graph.")
    contributor: _Optional[list[str]] = _Field(default=None, title="Contributor", description="A principal that committed a later version of the graph.")


class Loan(Tracked, Described, AggregateRoot):
    "A loan of an item; an aggregate root that points at the item, of whichever kind, by IRI."
    lends: str = _Field(default=..., title="Lends", description="The item the loan is of, another aggregate, abstract or concrete, stored as its IRI.")
    id: str = _Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    label: str = _Field(default=..., title="Label", description="The preferred label of the object.")
    description: _Optional[str] = _Field(default=None, title="Description", description="A free-text description of the object.")
    created: _Optional[datetime ] = _Field(default=None, title="Created", description="The time the graph was first committed.")
    modified: _Optional[datetime ] = _Field(default=None, title="Modified", description="The time the graph was last committed.")
    creator: _Optional[str] = _Field(default=None, title="Creator", description="The principal that first committed the graph.")
    contributor: _Optional[list[str]] = _Field(default=None, title="Contributor", description="A principal that committed a later version of the graph.")


class Chapter(Described):
    "A chapter of a book, known by its number rather than a label; part of the book\u0027s aggregate. It owns its notes."
    number: _Optional[int] = _Field(default=None, title="Chapter number", description="The position of a chapter in its book.")
    notes: _Optional[list[Note]] = _Field(default=None, title="Notes", description="The notes on a chapter; they live in the book\u0027s graph.")
    id: str = _Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    label: _Optional[str] = _Field(default=None, title="Label", description="The preferred label of the object.")  # type: ignore[assignment]
    description: _Optional[str] = _Field(default=None, title="Description", description="A free-text description of the object.")


class Note(Described):
    "A short note on a chapter, with a label of its own."
    text: _Optional[str] = _Field(default=None, title="Text", description="The text of a note.")
    about: _Optional[str] = _Field(default=None, title="About", description="The book a note is about, another aggregate, stored as its IRI.")
    shade: _Optional[str] = _Field(default=None, title="Shade", description="The colour of the note\u0027s paper.")
    id: str = _Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    label: str = _Field(default=..., title="Label", description="The preferred label of the object.")
    description: _Optional[str] = _Field(default=None, title="Description", description="A free-text description of the object.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
Book.model_rebuild()
Shelf.model_rebuild()
BookCollection.model_rebuild()
Display.model_rebuild()
Author.model_rebuild()
LendingItem.model_rebuild()
Magazine.model_rebuild()
Pamphlet.model_rebuild()
Loan.model_rebuild()
Chapter.model_rebuild()
Note.model_rebuild()
