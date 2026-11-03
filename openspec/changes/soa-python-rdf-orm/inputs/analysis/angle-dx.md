# Angle: developer experience — what makes developers love a persistence library (DEC-12)

- Analyst: angle-dx, round 3 brief (BRIEF-round3.md) + round-4 "Purpose and origin" rule.
- Question: which API choices make mainstream ORMs/ODMs loved, and how do they translate to an
  RDF / LinkML / SPARQL persistence layer that keeps LinkML-generated Pydantic classes
  persistence-free (Data Mapper, cosmic-python)?
- Deep dives (clone + `gitnexus analyze` + docs), clones in `/home/lps/work/repos/`:

| Repo | Commit analysed | Python LOC | GitNexus index |
|---|---|---|---|
| sqlmodel | `6a939fb` (2026-11-02) | 21,492 | 4,321 nodes · 6,072 edges · 131 clusters · 50 flows |
| beanie | `de3e326` (2026-10-07) | 22,555 | 4,060 nodes · 8,319 edges · 95 clusters · 206 flows |
| odmantic | `26e4504` (2026-01-25) | 12,898 | 2,598 nodes · 5,545 edges · 78 clusters · 92 flows |
| piccolo | `fc1fc86` (2026-10-30) | 53,612 | 6,399 nodes · 16,396 edges · 270 clusters · 278 flows |

- neomodel: compared only, from `neomodel.md` (the existing DX 5/5 benchmark).
- Other benchmarks: desk scan + official docs and source files fetched with `curl` (error
  strings verified in source where cited). Code examples for non-cloned libraries are written
  from their official quick-starts; they are marked *(docs)* and were not executed.
- No candidate code was installed or run.

## Summary

1. Developers love **short, typed, unsurprising** persistence: plain (Pydantic) model classes,
   one session object, `select(Model).where(Model.f == v)` expressions, a context-managed
   transaction, and errors that name the model and the field. These are now *expected* by Python
   developers (SQLAlchemy 2.0, SQLModel, Beanie, ODMantic, Piccolo all converge on them).
2. The best Data Mapper DX (ODMantic, SQLAlchemy 2.0, Ecto, Prisma) is **as short as Active
   Record** (8–14 lines for CRUD + query). So persistence-free LinkML classes cost no DX if the
   session/engine API is right.
3. The one unsolved typing problem everywhere is **class-level field expressions on plain
   classes** (`Hero.age > 35` type-checks as `bool`). SQLModel ships `col()`, Beanie/ODMantic
   accept `bool` in their signatures, SQLAlchemy uses `Mapped[]` descriptors, JPA generates a
   metamodel (`Person_`). For generated LinkML classes the clean answer is a **generated typed
   field metamodel** (proposed D15).
4. RDF forces five real differences: open world (absent ≠ empty ≠ not loaded), multi-valued
   properties by default, IRIs as ids (known before save), language-tagged strings, named graphs.
   Each has a mainstream precedent to borrow (Ecto `NotLoaded`, Django `using()`, JSON-LD
   language maps, …).
5. Verdict for every benchmark: **borrow ideas** — none is an RDF dependency candidate.

## Purpose and origin

| Tool | Built for / by | Design angle | Where its *ideas* fit (L0–L6) |
|---|---|---|---|
| SQLAlchemy 2.0 | General SQL toolkit + ORM; Mike Bayer and community, since 2005 | Data Mapper, Unit of Work, expression language | L1 session/UoW, query expression design, L2 dialect/capability idea |
| SQLModel | Make SQL feel like FastAPI: one class is both Pydantic model and table; Sebastián Ramírez (FastAPI org) | API-first, Pydantic-first | L1 API surface, L4 FastAPI integration, docs style |
| Django ORM | Web framework ORM; Django Software Foundation | Active Record, convention, batteries (migrations, admin) | L1 query-set ergonomics, L0 migrations, L4 admin (U5) |
| Prisma | TS ORM with a schema language and generated client; Prisma Data Inc. | Schema-first, generated typed client | L0 generate-on-save, L1 nested writes / batch transactions, L5 typed client |
| Drizzle | TS "SQL-shaped" ORM; Drizzle Team | Code-first, SQL-transparent | L1 query transparency, test-with-embedded-engine (PGlite) |
| Beanie | Async MongoDB ODM on Pydantic; Roman Right, BeanieODM org | Active Record over Pydantic documents | L1 document mapping (closest to JSON-LD), revision locking, projections |
| ODMantic | Async/sync MongoDB ODM on Pydantic; Arthur Pastel | Data Mapper (engine) over Pydantic | L1 engine API shape — the closest analogue to what rdf-persistence must be |
| Tortoise ORM | Django-style async ORM | Active Record, async-only | L1 async lookups, `in_transaction()` |
| Piccolo | Async query builder + ORM + admin; Daniel Townsend | Query-builder-first, batteries | L1 awaitable queries + `run_sync`, L4 admin, test kit (`ModelBuilder`) |
| Pony | Pythonic generator-expression queries | Bytecode-decompiling query DSL, identity map, optimistic checks | L1 default optimistic concurrency; warning on "magic" |
| Ecto | Elixir data mapper; Plataformatec / Dashbit | Repo + changesets, explicit preload | L1 explicit loading, validation separation, test sandbox |
| ActiveRecord | Rails ORM; Rails core | Convention over configuration | L1 conventions, validations, `lock_version` |
| Spring Data | Repository abstraction over many stores; VMware/Broadcom | Repository interfaces + derived queries | L1 repositories, derived finders (Q8), "did you mean" errors |
| neomodel | Neo4j OGM (compare only) | Django-style Active Record | see `neomodel.md` |

None of them speaks RDF; their place is the **API shape and developer tooling** of
rdf-persistence (L1) and of the generated service (L4), not a dependency.

## Landscape table (desk scan, 2026-11-03)

Stars / last push via `gh api repos/<r>`; downloads = last month from pypistats.org / npm API.
DEC-5 = >200 stars AND commit within 12 months (it is recorded for completeness; these are
idea sources, not dependency candidates — they are not RDF libraries).

| Library | Repo | Stars | Last push | Licence | Lang | Downloads/month | DEC-5 | Layers (ideas) | Depth |
|---|---|---|---|---|---|---|---|---|---|
| SQLModel | fastapi/sqlmodel | 18,539 | 2026-11-02 | MIT | Python | 23.9 M | pass | L1, L4 | **deep** |
| SQLAlchemy 2.0 | sqlalchemy/sqlalchemy | 12,276 | 2026-11-02 | MIT | Python | 329.8 M | pass | L1, L2 | desk (via SQLModel) |
| Django ORM | django/django | 91,489 | 2026-11-02 | BSD-3 | Python | 41.1 M | pass | L0, L1, L4 | desk |
| Prisma | prisma/prisma (now `prisma/orm`) | 47,659 | 2026-11-02 | Apache-2.0 | TS | 73.6 M (`prisma`) | pass | L0, L1, L5 | desk |
| prisma-client-py | RobertCraigie/prisma-client-py | 2,091 | 2025-04-10, **archived** | Apache-2.0 | Python | — | **fail** (archived) | L1 | desk |
| Drizzle | drizzle-team/drizzle-orm | 36,205 | 2026-11-03 | Apache-2.0 | TS | 118.4 M | pass | L1 | desk |
| Beanie | BeanieODM/beanie | 2,709 | 2026-11-02 | Apache-2.0 | Python | 1.45 M | pass | L1 | **deep** |
| ODMantic | art049/odmantic | 1,177 | 2026-05-19 (last commit 2026-01-25) | ISC | Python | 62.8 k | pass (barely; single maintainer) | L1 | **deep** |
| MongoEngine | MongoEngine/mongoengine | 4,347 | 2026-09-06 | MIT | Python | 1.59 M | pass | L1 | desk (not Pydantic) |
| Tortoise ORM | tortoise/tortoise-orm | 5,640 | 2026-10-31 | Apache-2.0 | Python | 478 k | pass | L1 | desk |
| Piccolo | piccolo-orm/piccolo | 1,951 | 2026-10-30 | MIT | Python | 509 k | pass | L1, L4 | **deep** |
| Pony | ponyorm/pony | 3,820 | 2026-08-10 | Apache-2.0 | Python | 507 k | pass | L1 | desk |
| Ecto | elixir-ecto/ecto | 6,500 | 2026-11-01 | Apache-2.0 | Elixir | — | pass | L1 | desk |
| ActiveRecord | rails/rails | 58,846 | 2026-11-03 | MIT | Ruby | — | pass | L0, L1 | desk |
| Spring Data JPA / Commons | spring-projects/spring-data-jpa · -commons | 3,294 · 842 | 2026-10-29 | Apache-2.0 | Java | — | pass | L1 | desk |
| TypeORM | typeorm/typeorm | 36,661 | 2026-10-29 | MIT | TS | 19.3 M | pass | L1 | desk (no new ideas beyond the above) |
| MikroORM | mikro-orm/mikro-orm | 9,265 | 2026-11-03 | MIT | TS | — | pass | L1 | desk (UoW + identity map in TS) |
| neomodel | neo4j-contrib/neomodel | 1,092 | 2026-11-02 | MIT | Python | 112 k | pass | L1, L2 | compare (`neomodel.md`) |

## Benchmarks: the shortest complete example

"Complete" = model with one relationship, create, read, update, delete, one filtered query, in
a transaction or session. Lines exclude imports and blank lines.

### SQLModel (deep) — 15 lines

Assembled from `docs_src/tutorial/relationship_attributes/read_relationships/tutorial001_py310.py:4-19`
and `docs/tutorial/where.md`.

```python
class Team(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    heroes: list["Hero"] = Relationship(back_populates="team")
class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    team_id: int | None = Field(default=None, foreign_key="team.id")
    team: Team | None = Relationship(back_populates="heroes")
with Session(engine) as session:
    hero = Hero(name="Deadpond", team=Team(name="Z-Force")); session.add(hero); session.commit()
    hero = session.get(Hero, hero.id)
    hero.name = "Deadpool"; session.add(hero); session.commit()
    found = session.exec(select(Hero).where(Hero.name == "Deadpool")).all()
    session.delete(hero); session.commit()
```

- **Concepts (≈8):** `SQLModel`, `table=True`, `Field`, `Relationship`, `engine`, `Session`,
  `select`, `exec`. Plus the "multiple models" pattern (`HeroCreate`, `HeroPublic`) for APIs.
- **Typing/IDE:** classes are Pydantic, so instance completion works. Class-level `Hero.age` is
  typed as `int`, so `Hero.age > 35` is a `bool` to the type checker; `in_` needs a wrapper:
  `col()` (`sqlmodel/sql/expression.py:200-206`, documented in `docs/tutorial/where.md:719-741`:
  "We can tell the editor that this class attribute is actually a special SQLModel column").
  `select()` has 33 generated overloads for typed tuples (`sqlmodel/sql/_expression_select_gen.py`,
  from a Jinja template).
- **Query style:** expression objects (SQLAlchemy 2.0). `Session.exec()` returns model objects
  instead of `Row`s; the old `execute()` carries a deprecation docstring explaining why
  (`sqlmodel/orm/session.py:105-140`).
- **Transactions:** SQLAlchemy `Session` (UoW + identity map); `commit()` / `rollback()`,
  `session.begin()`. `AsyncSession.exec` mirrors the sync one (`sqlmodel/ext/asyncio/session.py:30-59`).
- **Migrations:** none built in; Alembic (documented externally).
- **Testing:** the docs teach it: `create_engine("sqlite://", poolclass=StaticPool)` + a pytest
  `session` fixture + FastAPI `app.dependency_overrides[get_session]`
  (`docs_src/tutorial/fastapi/app_testing/tutorial001_py310/test_main.py:9-27`).
- **Errors:** SQLAlchemy's `NoResultFound: No row was found when one was required` and
  `MultipleResultsFound: Multiple rows were found when exactly one was required`
  (`lib/sqlalchemy/engine/_result_cy.py:540, 599` upstream) — correct but model-agnostic.
- **Docs:** tutorial-first, progressive; **every example is a file and is tested**: 150 files in
  `docs_src/`, 119 test modules in `tests/test_tutorial/`.
- **Footguns:** `session.refresh()` dance after commit to get generated ids; `table=True` vs
  data models confuse newcomers; `col()` needed for typed operators.

### SQLAlchemy 2.0 (desk, docs) — 14 lines

```python
class User(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    addresses: Mapped[list["Address"]] = relationship(back_populates="user")
with Session(engine) as s, s.begin():
    s.add(User(name="ada", addresses=[Address(email="a@x")]))
with Session(engine) as s, s.begin():
    ada = s.scalars(select(User).where(User.name == "ada")).one()
    ada.name = "Ada"                               # dirty tracking, flushed on commit
    users = s.scalars(select(User).options(selectinload(User.addresses))).all()
    s.delete(ada)
```

- **Typing:** `Mapped[T]` descriptors: class access gives an expression, instance access gives
  `T` — no plugin needed in 2.0. This is the gold standard but requires the ORM to own the class.
- **Loading:** explicit strategies (`selectinload`, `joinedload`, `lazy="raise"` to forbid N+1).
- **Transactions:** "begin once" `with s.begin():`; `AsyncSession` mirrors `Session`.

### Django ORM (desk, docs) — 11 lines

```python
class Team(models.Model):
    name = models.CharField(max_length=100)
class Hero(models.Model):
    name = models.CharField(max_length=100)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="heroes")
with transaction.atomic():
    h = Hero.objects.create(name="Deadpond", team=Team.objects.create(name="Z"))
    h = Hero.objects.get(pk=h.pk); h.name = "Deadpool"; h.save()
    found = Hero.objects.filter(team__name__icontains="z").select_related("team")
    h.delete()
```

- **Concepts (≈8):** Model, Field, Manager (`objects`), QuerySet, lookups (`field__op`), `Q`/`F`,
  `transaction.atomic`, migrations.
- **Errors (verified, `django/db/models/query.py:751, 754`):**
  `"%s matching query does not exist." % object_name` → `Hero matching query does not exist.`;
  `"get() returned more than one %s -- it returned %s!"`. Per-model `Hero.DoesNotExist`.
- **Migrations:** `makemigrations` autodetects model diffs — the most-praised Django feature.
- **Testing:** `TestCase` wraps each test in a transaction; test DB created automatically.
- **Typing:** weak without `django-stubs`; kwargs lookups are strings.

### Prisma (desk, docs) — 12 lines (schema) + 8 lines (code)

```prisma
model User { id Int @id @default(autoincrement())  name String  posts Post[] }
model Post { id Int @id @default(autoincrement())  title String  author User @relation(fields: [authorId], references: [id])  authorId Int }
```
```ts
const u = await prisma.user.create({ data: { name: "Ada", posts: { create: [{ title: "Hi" }] } } })
const one = await prisma.user.findUnique({ where: { id: u.id }, include: { posts: true } })
await prisma.user.update({ where: { id: u.id }, data: { name: "Ada L." } })
const found = await prisma.user.findMany({ where: { name: { contains: "Ada" } } })
await prisma.$transaction([prisma.post.deleteMany({ where: { authorId: u.id } }),
                           prisma.user.delete({ where: { id: u.id } })])
```

- **Concepts (≈6):** schema file, `prisma generate`, client, model delegate, `where`/`include`/
  `select` objects, `$transaction`.
- **Typing:** the generated client types every `where`/`include`/`select` argument and narrows
  the return type to what was selected — completion is the documentation.
- **Transactions:** `$transaction([...])` = **atomic batch of operations sent together** (the
  exact analogue of a single SPARQL Update request, T1) and an interactive variant.
- **Nested writes:** a whole aggregate in one call (`posts: { create: [...] }`).
- **Errors (verified, `prisma-engines/libs/user-facing-errors/src/query_engine/mod.rs:244-245`):**
  coded and documented: `P2025: An operation failed because it depends on one or more records
  that were required but not found. {cause}`.
- **Testing:** no in-memory engine; the docs recommend mocking the client or a real DB — the
  weak spot.
- **Python port** (prisma-client-py) is archived — the generated-client approach needs a
  maintained generator.

### Drizzle (desk, docs) — 9 lines

```ts
export const users = pgTable("users", { id: serial("id").primaryKey(), name: text("name") })
export const posts = pgTable("posts", { id: serial("id").primaryKey(), authorId: integer("author_id").references(() => users.id) })
const [u] = await db.insert(users).values({ name: "Ada" }).returning()
await db.update(users).set({ name: "Ada L." }).where(eq(users.id, u.id))
const rows = await db.select().from(users).where(like(users.name, "%Ada%"))
const withPosts = await db.query.users.findMany({ with: { posts: true } })
await db.delete(users).where(eq(users.id, u.id))
```

- **Angle:** "if you know SQL, you know Drizzle" — the builder mirrors SQL clause by clause and
  every query has `.toSQL()`. Two APIs: SQL-like builder and a relational `db.query` API.
- **Typing:** inferred from the code-first table objects, no generation step.
- **Testing:** runs against PGlite (embedded Postgres) in-process.

### Beanie (deep) — 10 lines

From `README.md` and `docs/tutorial/relations.md`:

```python
class Door(Document):
    height: int = 2
class House(Document):
    name: str
    door: Link[Door]
await init_beanie(database=client.db, document_models=[Door, House])
house = House(name="A", door=Door()); await house.insert(link_rule=WriteRules.WRITE)
house = await House.find_one(House.name == "A", fetch_links=True)
await house.set({House.name: "B"})
await house.delete()
```

- **Concepts (≈9):** `Document`, `init_beanie`, `Link`/`BackLink`, `fetch_links` + `nesting_depth`,
  find/expressions, update operators, `Settings` inner class, state management, revision.
- **Typing/IDE:** documents are Pydantic. Class-level fields become `ExpressionField` at
  `init_beanie` time by `setattr(cls, k, ExpressionField(...))`
  (`beanie/odm/utils/init.py:387, 628`; `beanie/odm/fields.py:195`), i.e. **the library attaches
  query attributes to plain Pydantic classes at runtime** — feasible with Pydantic v2. To the type
  checker they are still `float`, so comparisons are `bool`. Typing is regression-tested with
  dedicated modules (`tests/typing/find.py`: `find().project(projection_model=...)` returns
  `list[ProjectionTest]`).
- **Optimistic concurrency:** opt-in `Settings.use_revision` (`beanie/odm/settings/document.py:14`);
  the save adds `revision_id` to the filter and raises `RevisionIdWasChanged`
  (`beanie/odm/documents.py:501-515`).
- **Change tracking:** `use_state_management` + `save_changes()` sends only the diff
  (`settings/document.py:10`).
- **Projections:** typed `project(projection_model=...)` — read models without new concepts.
- **Transactions:** a pymongo `session=` keyword on every method
  (`beanie/odm/documents.py:234, 451, 534`) — no context-managed scope; easy to forget.
- **Migrations:** iterative / free-fall data migrations with typed input/output document classes
  and forward/backward (`docs/tutorial/migrations.md`, `beanie/migrations/`).
- **Errors — counter-example:** exceptions carry no message (`beanie/exceptions.py:1-75`, every
  class is `pass`; `raise RevisionIdWasChanged` bare at `documents.py:515`), and query-building
  errors are generic: `TypeError("Wrong expression type")` (`beanie/odm/queries/update.py:62-85`),
  `TypeError("Wrong argument type")` (`queries/find.py:410`).
- **Testing:** needs a live MongoDB (`tests/conftest.py:3-24`).
- **Docs:** `docs/getting-started.md` spends its first screen on seven install extras before the
  first model — tutorial pages are good (`docs/tutorial/*.md`, 20 topics).
- **Footguns:** global registry via `init_beanie`; `Link` resolution rules (`WriteRules`,
  `fetch_links`) surprise; transactions by keyword.

### ODMantic (deep) — 9 lines (Data Mapper!)

From `README.md`:

```python
class Publisher(Model):
    name: str
    founded: int = Field(ge=1440)
class Book(Model):
    title: str
    publisher: Publisher = Reference()
engine = AIOEngine()
book = Book(title="X", publisher=Publisher(name="Lulu", founded=2002)); await engine.save(book)
found = await engine.find(Book, Book.title == "X")
book.title = "Y"; await engine.save(book)
await engine.delete(book)
```

- **Concepts (≈6):** `Model`, `Field`, `Reference`, engine, query expressions, session/transaction.
- **Pattern:** **engine = Data Mapper**: `engine.save / find / find_one / delete / count / session /
  transaction` (`odmantic/engine.py:295-715`); a `SyncEngine` mirrors the API (`:715-1085`).
  Models are Pydantic subclasses with no persistence methods.
- **Typing trick, stated in code:** `find(model, *queries: Union[QueryExpression, Dict, bool], ...)`
  with the comment `# bool: allow using binary operators with mypy` (`odmantic/engine.py:433-437`).
- **Change tracking:** `__fields_modified__` per instance → saves only modified fields
  (`odmantic/model.py:542-549, 710-711`).
- **Errors — good:** base exception carries the model; `DocumentNotFoundError`: `Document not
  found for : {Model}. Instance: {instance}`; `DuplicateKeyError` includes the instance and the
  driver error (`odmantic/exceptions.py:14-57`); validation errors are Pydantic custom errors with
  an `odmantic::` type prefix (`:60-65`).
- **Testing:** live MongoDB (`tests/integration/conftest.py:18`).
- **Health:** single maintainer, last commit 2026-01-25 — healthy design, fragile project.

### Piccolo (deep) — 9 lines

From `README.md`:

```python
class Manager(Table):
    name = Varchar()
class Band(Table):
    name = Varchar(); popularity = Integer(); manager = ForeignKey(references=Manager)
b = Band(name="C-Sharps", popularity=100); await b.save()
b = await Band.objects().get(Band.name == "Pythonistas")
b.popularity = 10000; await b.save()
rows = await Band.select(Band.name, Band.manager.name).where(Band.popularity > 100)
await b.remove()
```

- **Concepts (≈7):** `Table`, column types, `objects()` vs `select()`, `where`, `run_sync`, engine,
  transaction.
- **Async with sync escape:** every query is awaitable (`piccolo/query/base.py:140 __await__`) and
  has `.run_sync()` (`:201, :355, :453`) — one API, two call styles, no duplicate class tree.
- **Transactions:** `async with DB.transaction():` held in a ContextVar so nested calls join it
  (`piccolo/engine/postgres.py:203-226`); `atomic()` for building a batch.
- **Serialisation:** `create_pydantic_model(Band, nested=..., exclude_columns=...)`
  (`piccolo/utils/pydantic.py:111`) → FastAPI models from tables.
- **Testing kit:** `ModelBuilder.build(Band, persist=False, minimal=True)` fabricates valid rows
  (`docs/src/piccolo/testing/index.rst`); `piccolo tester run` sets up a test DB.
- **Batteries:** `piccolo/apps/` — migrations (auto), playground (in-memory demo data), shell,
  admin, project scaffolding (`asgi new`).
- **Errors:** few custom exception types (`piccolo/query/mixins.py:24 DistinctOnError` is one).

### Tortoise ORM (desk, docs) — 9 lines

```python
class Team(Model):
    name = fields.CharField(max_length=50)
class Hero(Model):
    name = fields.CharField(max_length=50); team = fields.ForeignKeyField("models.Team", related_name="heroes")
await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
async with in_transaction():
    h = await Hero.create(name="A", team=await Team.create(name="Z"))
    h.name = "B"; await h.save()
    found = await Hero.filter(team__name__icontains="z").prefetch_related("team")
    await h.delete()
```

- Django idioms, async-only; `register_tortoise(app, ...)` for FastAPI; `pydantic_model_creator`;
  Aerich for migrations. Global init registry by module path strings (typo-prone).

### Pony (desk, docs) — 8 lines

```python
class Team(db.Entity):
    name = Required(str); heroes = Set("Hero")
class Hero(db.Entity):
    name = Required(str); team = Optional(Team)
with db_session:
    h = Hero(name="A", team=Team(name="Z"))           # committed at block end
    h.name = "B"
    found = select(x for x in Hero if "Z" in x.team.name)[:]
    h.delete()
```

- The most "Pythonic" queries (generator expressions decompiled from bytecode) — loved, but the
  decompiler must follow every new CPython release (a recurring lag). Lesson: **no syntax magic
  that depends on interpreter internals.**
- `db_session` = identity map + UoW + **optimistic checks on by default** (columns read are
  checked at update time; `optimistic=False` to opt out).

### Ecto (desk, docs) — 10 lines

```elixir
schema "posts" do field :title, :string; has_many :comments, Comment end
def changeset(post, attrs), do: post |> cast(attrs, [:title]) |> validate_required([:title])
{:ok, post} = %Post{} |> Post.changeset(%{title: "Hi"}) |> Repo.insert()
post = Repo.get!(Post, post.id) |> Repo.preload(:comments)
{:ok, post} = post |> Post.changeset(%{title: "Hello"}) |> Repo.update()
posts = Repo.all(from p in Post, where: ilike(p.title, "%he%"))
Repo.transaction(fn -> Repo.delete!(post) end)
```

- **Repo = Data Mapper**; schemas are plain structs.
- **Changesets** separate "what changed + is it valid" from the schema; errors per field
  (`ecto/lib/ecto/changeset.ex:129`: `changeset.errors #=> [age: {"is invalid", []}, name:
  {"can't be blank", []}]`).
- **No lazy loading:** an unloaded association is `%Ecto.Association.NotLoaded{}` — accessing it
  never queries; `Repo.preload` is explicit. N+1 is impossible by construction.
- **SQL Sandbox:** each test runs in a transaction that is rolled back; tests run concurrently.

### ActiveRecord (desk, docs) — 8 lines

```ruby
class Team < ApplicationRecord; has_many :heroes; end
class Hero < ApplicationRecord; belongs_to :team; validates :name, presence: true; end
h = Hero.create!(name: "A", team: Team.create!(name: "Z"))
h = Hero.find(h.id); h.update!(name: "B")
found = Hero.joins(:team).where(teams: { name: "Z" }).order(:name).limit(10)
h.destroy
```

- Convention over configuration (table, keys, foreign keys derived from names).
- `lock_version` column → automatic optimistic locking (`ActiveRecord::StaleObjectError`).
- Errors: `ActiveRecord::RecordNotFound: Couldn't find Hero with 'id'=42`;
  `h.errors.full_messages # => ["Name can't be blank"]`.

### Spring Data (desk; error string verified) — 6 lines + entity

```java
interface PersonRepository extends CrudRepository<Person, Long> {
  List<Person> findByLastnameAndAgeGreaterThan(String lastname, int age);
}
repo.save(p); repo.findById(id); repo.delete(p);
@Transactional void transfer(...) { ... }
```

- Derived queries from method names, validated **at startup**. Error template verified at
  `spring-data-commons/src/main/java/org/springframework/data/core/PropertyReferenceException.java:43-44`:
  `"No property '%s' found for type '%s'"` + `"Did you mean %s"` — the best typo error in the set.
- `@Transactional` declarative boundary; JPA static metamodel (`Person_.lastname`) for typed
  Criteria queries — the typed-field-companion precedent for D15.

### neomodel (compare only, from `neomodel.md`)

~14 lines CRUD, ≈8 concepts, Django idioms on a graph; per-class `DoesNotExist`; relationship
managers with verbs; one transaction object in three styles; async-first with generated sync.
Footguns: no identity map, lazy N+1, global `db` singleton. DX 5/5.

## Comparison matrix (DX dimensions)

| Library | CRUD+rel+query lines | Concepts | Pattern | Typing / IDE | Query style | Transaction API | Migrations | Testing | Errors | Async |
|---|---|---|---|---|---|---|---|---|---|---|
| SQLModel | 15 | 8 | Data Mapper (Session) on Pydantic | Pydantic + `col()` workaround | expressions | Session / `begin()` | Alembic | sqlite memory + DI override | generic SA | `AsyncSession` mirror |
| SQLAlchemy 2.0 | 14 | 10+ | Data Mapper, UoW, identity map | `Mapped[]` descriptors | expressions | `with s.begin()` | Alembic | sqlite memory | generic | mirror |
| Django | 11 | 8 | Active Record | stubs needed | kwargs lookups + Q/F | `atomic` ctx/decorator | autodetect | tx per test | model-named | partial |
| Prisma | 20 (incl. schema) | 6 | generated client | generated, return narrowing | generated where-objects | batch + interactive | `migrate dev` | mock / real DB | coded P-errors | native |
| Drizzle | 9 | 6 | builder | inferred | SQL-like builder + relational | `db.transaction` | drizzle-kit | PGlite | driver errors | native |
| Beanie | 10 | 9 | Active Record on Pydantic | Pydantic; runtime-attached fields | expressions + Mongo operators | `session=` kwarg | data migrations | live Mongo | bare exceptions | async only |
| ODMantic | 9 | 6 | **Data Mapper (engine)** on Pydantic | Pydantic; `bool` in signature | expressions | `engine.transaction()` | none | live Mongo | model + instance | async + `SyncEngine` |
| Tortoise | 9 | 7 | Active Record | partial | kwargs lookups | `in_transaction()` | Aerich | sqlite memory | model-named | async only |
| Piccolo | 9 | 7 | Active Record + builder | columns typed | expressions | ContextVar `transaction()` | auto | ModelBuilder, tester | few | async + `run_sync` |
| Pony | 8 | 6 | identity map + UoW | weak | generator expressions | `db_session` | none | sqlite memory | ok | none |
| Ecto | 10 | 7 | **Repo (Data Mapper)** + changesets | n.a. (Elixir) | macro query DSL | `Repo.transaction` | Ecto migrations | SQL Sandbox | per-field | n.a. |
| ActiveRecord | 8 | 7 | Active Record | n.a. | hash + chained | `transaction do` | Rails migrations | transactional fixtures | readable | n.a. |
| Spring Data | 6+entity | 6 | Repository | Java types + metamodel | derived names / Criteria | `@Transactional` | Flyway/Liquibase | `@DataJpaTest` | "Did you mean" | reactive variant |
| neomodel | 14 | 8 | Active Record | v7 typed props | kwargs lookups + Q | ctx/decorator/manual | `install_labels` | live Neo4j | model-aware | generated sync |

## Conventions now EXPECTED by Python developers (2026)

1. **Pydantic models** as the entity type (SQLModel, Beanie, ODMantic; Piccolo/Tortoise generate
   Pydantic). FastAPI request/response models are the same or derived classes.
2. **`select(Model).where(Model.field == value)`** expression style (SQLAlchemy 2.0, SQLModel,
   Beanie, ODMantic, Piccolo). Kwargs lookups (`filter(name__icontains=)`) remain familiar from
   Django but are a second style, not the primary one in new libraries.
3. **`with Session(...) as s:` / `async with`** and `s.begin()` transaction blocks; decorator form
   for service functions (Django `atomic`, Spring `@Transactional`, neomodel).
4. **FastAPI dependency injection:** `session: Session = Depends(get_session)` and
   `app.dependency_overrides` in tests (SQLModel docs). No global singletons.
5. **Async parity:** an `AsyncSession` that mirrors the sync one, or awaitable queries with a sync
   escape (`run_sync`).
6. **`get` vs `get_or_none` / `one` vs `one_or_none` / `first`** naming; per-model `DoesNotExist`.
7. **An in-memory engine for tests** (sqlite `:memory:`, PGlite) plus a fixture recipe in the docs.
8. **Typed results**: `list[Model]`, narrowed projections (Beanie `projection_model`, Prisma
   `select`).
9. **`echo=True` / query logging** and a way to print the generated query.

## DX principles catalogue

Each principle: evidence → translation to RDF / LinkML / SPARQL → where RDF forces a difference.

| # | Principle | Evidence | Translation to rdf-persistence | RDF-forced difference |
|---|---|---|---|---|
| DX-P1 | **Plain models are the API** — the entity is an ordinary (Pydantic) class | SQLModel, Beanie, ODMantic are Pydantic; Ecto schemas are structs; Prisma types are plain | Use LinkML `gen-pydantic` classes unchanged; no required base class (sparqlmodel's `SPARQLModel` subclassing blocks reuse) | Mapping lives in `linkml_meta` (`class_uri`, `slot_uri`), not in the class body |
| DX-P2 | **Data Mapper can be as short as Active Record** | ODMantic 9 lines, Ecto 10, SQLAlchemy 14 vs Django 11, Beanie 10 | A `Session` (engine) does `add/get/delete/exec`; repositories are optional sugar | Same |
| DX-P3 | **Typed expression queries** `select(M).where(...)` | SQLAlchemy `Mapped[]`; SQLModel `col()` (`expression.py:200`); ODMantic `bool` in `find` signature (`engine.py:433-437`); Beanie runtime `ExpressionField` (`init.py:387`); JPA `Person_` metamodel | **Generated typed field metamodel** `Person_.name: Field[str]` next to the domain module (D15); compiled to a SPARQL AST (Q7), bound parameters (Q6) | Field operators include RDF ones: `.lang("en")`, `.any(...)` for multi-valued, `.iri` for references, `.exists()` / `.missing()` |
| DX-P4 | **One way for simple, one way for complex** | Django: kwargs + Q/F; Prisma: one `where` object; Beanie mixes expressions, dicts and Mongo operators (confusing) | `repo.find(name="Ada")` = equality only, typed by a generated `TypedDict` (D16); everything else via expressions | — |
| DX-P5 | **The query is transparent** | Drizzle `.toSQL()`; SQLAlchemy `echo=True`; Django `str(qs.query)`; Prisma `log: ['query']` | `q.to_sparql()` with bound values; logger `rdf_persistence.sparql` with timing (S14) (D14) | Show prefixes and the named graphs used |
| DX-P6 | **Transaction scope is one obvious block** | `with s.begin()`; Django `atomic`; Piccolo ContextVar (`postgres.py:203-226`); Prisma `$transaction([...])`; Beanie `session=` kwarg as counter-example | `async with session.begin():` commits **one SPARQL Update** (T1); decorator form `@transactional`; ContextVar so nested calls join | Atomicity is per request: say so in the API (`store.capabilities()`, T7); no fake rollback |
| DX-P7 | **Lost updates are prevented by default** | Pony optimistic checks default; Rails `lock_version`; Beanie `use_revision` (`documents.py:501-515`); JPA `@Version` | Version triple per aggregate in the `WHERE` guard (T2), **on by default**; `ConflictError` names IRI and versions | Version lives in the graph (or graph metadata) — foreign writers that ignore it are not protected; document it |
| DX-P8 | **Loading is explicit; unloaded ≠ empty** | Ecto `NotLoaded` + `preload`; SQLAlchemy `selectinload`, `lazy="raise"`; Prisma `include`; Beanie `fetch_links` + `nesting_depth` | References come back as IRIs (LinkML non-inlined slots already are `str`); `s.load(obj, Person_.member_of)` batches one query (Q9); `depth=` for inlined composition | **Open world:** three states — not loaded, loaded-and-absent, known-empty. A `NotLoaded` sentinel (D17) prevents saving a partial object as "delete everything I did not load" (pairs with P8 owned predicates) |
| DX-P9 | **Errors name the model, the field and the fix** | Django `Hero matching query does not exist.`; Spring `No property 'x' found for type 'Person'` + `Did you mean`; Prisma coded `P2025`; ODMantic model + instance; Beanie bare exceptions (counter) | Every error carries class CURIE, IRI, slot, graph, store response body (D11–D13); suggestions (D22); stable codes with a docs page (D23) | Include the SPARQL snippet and the endpoint; distinguish "no triples" from "no access" when the store says so |
| DX-P10 | **Validation is separate and structured** | Ecto changesets; Rails `errors.full_messages`; Pydantic `ValidationError`; Beanie `validate_on_save` | Pydantic on construction; optional SHACL report on commit, mapped to field paths (U6) | SHACL is closed/open by shape; validate the aggregate's graph, not the whole store |
| DX-P11 | **Test against a real in-process engine, not mocks** | SQLModel `sqlite://` + `StaticPool` + `dependency_overrides` (`test_main.py:9-27`); Ecto SQL Sandbox; Piccolo `ModelBuilder`; Drizzle PGlite; Beanie/ODMantic/Prisma need live DBs (counter) | `rdf_persistence.testing` pytest plugin: pyoxigraph in-memory `store` fixture, fresh per test; LinkML-driven fake builder; graph-isomorphism asserts (D18) | Advantage: the in-memory store runs **the same SPARQL** as production — better than sqlite-vs-Postgres |
| DX-P12 | **Framework integration through DI, no globals** | SQLModel `Depends(get_session)`; neomodel global `db` and Beanie `init_beanie` registry as footguns | `Session` is a FastAPI dependency; identity and graph scope are per-request arguments | Required for DEC-8: the end-user identity travels with the session (AZ4); no shared caches across users |
| DX-P13 | **Async without a second mental model** | SQLAlchemy `AsyncSession` mirror; Piccolo `run_sync`; neomodel unasync; ODMantic `SyncEngine` | Async-first, sync generated (D7) | rdflib/pyoxigraph are sync — the in-memory adapter runs inline; HTTP via httpx async |
| DX-P14 | **One schema source, regenerate on save** | Prisma `generate`; Drizzle inferred types; Django model = migration source | LinkML is the schema; one `make generate-models` emits Pydantic + field metamodel + TypedDicts + JSON-LD context + TS types (G1, G7, G16) | — |
| DX-P15 | **Schema changes have a story** | Django `makemigrations`; Prisma `migrate`; Beanie data migrations with typed in/out docs; neomodel `install_labels` | No DDL in RDF: "migrations" are versioned SPARQL Update scripts + SHACL shape install, applied once and recorded in a graph (D20) | Schema-less store: model evolution = data transformation, not table alteration |
| DX-P16 | **Tutorial first, every example tested** | SQLModel: 150 `docs_src` files, 119 `tests/test_tutorial` modules; Beanie install-extras wall (counter) | Docs examples run in CI against the in-memory store (D19); page one = complete CRUD + query + transaction | — |
| DX-P17 | **An escape hatch that returns models** | SQLAlchemy `text()`/`from_statement`; Django `raw()`; neomodel `resolve_objects`; Prisma `$queryRaw` | `s.sparql(query, bind=..., as_=Person)` (Q3) | Map by `?id` variable + CONSTRUCT of owned predicates |
| DX-P18 | **Typed projections for read paths** | Beanie `project(projection_model=)`; Prisma `select` narrowing; SQLModel `HeroPublic` | `select(Person).project(PersonCard)` returns `list[PersonCard]`, read-only (X10) | Projections must never be saved (would drop triples) — enforce by type |
| DX-P19 | **Conventions only where safe; explicit mapping wins** | Rails/Spring derive names; Pony magic lag; sparqlmodel metaclass `__getattr__` untyped | No name-derived predicates (LinkML is explicit); defaults only for IRI minting (`id_prefixes`) and CURIE expansion (D21) | IRIs are global — a convention that guesses predicates writes wrong data silently |
| DX-P20 | **Ids are known before save** | SQLModel needs `session.refresh()` to see the autoincrement id (footgun); ODMantic/Beanie mint ObjectIds client-side | IRIs minted client-side (`s.mint(Person)` from schema `id_prefixes`, UUID default); no refresh dance | IRIs are ids **and** links — CURIE in, CURIE-aware `repr` out (D21) |

### Where RDF forces a different API (summary)

| RDF trait | Mainstream default | rdf-persistence choice | Precedent borrowed |
|---|---|---|---|
| Open world | `None` = NULL | `None` = "no value in loaded data"; `NotLoaded` sentinel for unloaded slots; owned-predicate writes (P8) | Ecto `NotLoaded`, SQLAlchemy `lazy="raise"` |
| Multi-valued by default | scalar columns | LinkML `multivalued` → `list[T]` (as generated), **set semantics**, deterministic order on load (D24); collection operators `.add/.remove` (P10) | Prisma `push`/`set`, Mongo `$addToSet` (Beanie) |
| IRIs as ids | integer autoincrement | `id: str` IRI, minted client-side, CURIEs accepted everywhere | Mongo ObjectId minted client-side |
| Language tags | one string | `LangString` = `dict[lang, str]` (JSON-LD language map); `Person_.name.lang("en")` in queries (G6) | JSON-LD `@container: @language` |
| Named graphs | database / schema | `Session(store, graph=...)` and `s.using(graph=...)`; policy-driven placement (P12) when configured | Django `QuerySet.using("db")` |
| No schema DDL | migrations alter tables | data migrations + SHACL install (D20) | Beanie data migrations |
| Multi-typing | one class per row | load as the requested class; polymorphic query over subclasses (Q17) | SQLAlchemy polymorphic loading |

## API sketch for rdf-persistence (illustrative, 56 lines)

```python
# --- 1. generated by LinkML gen-pydantic: the domain, persistence-free (G1) ---
class Organization(BaseModel):
    id: str                                   # IRI; class_uri / slot_uri sit in linkml_meta
    name: LangString                          # {"en": "ACME", "fr": "ACMÉ"}
class Person(BaseModel):
    id: str
    name: str
    member_of: list[str] = []                 # non-inlined range → IRIs of Organization

# --- 2. generated next to it by rdf-persistence: typed field metamodel (D15) ---
from org_model.fields import Person_, Organization_    # Person_.name: Field[str]

# --- 3. wiring: one Store, sessions per request (FastAPI dependency) ---
from rdf_persistence import Store, Session, select, Repository, ConflictError
store = Store.connect("oxigraph:memory", schema="model/org.yaml")   # or an https SPARQL URL
store.capabilities()       # Capabilities(atomic_request=True, multi_request_tx=False, ...)

async def get_session(user: User = Depends(current_user)):
    async with Session(store, graph="ex:graph/hr", identity=user.token) as s:
        yield s                               # no globals: identity + graph per request

# --- 4. unit of work: one commit == one SPARQL Update, version-guarded (T1, T2) ---
async with Session(store) as s, s.begin():    # commit on exit, nothing sent on error
    acme = Organization(id="ex:org/acme", name={"en": "ACME", "fr": "ACMÉ"})
    ada = Person(id=s.mint(Person), name="Ada", member_of=[acme.id])
    s.add_all([acme, ada])
# ConflictError: Person <ex:person/7f3c> changed since it was loaded
#   (version 3, store has 4). Reload it with session.refresh(obj) and re-apply. [RP-409]

# --- 5. read and change ---
async with Session(store) as s, s.begin():
    ada = await s.get(Person, "ex:person/7f3c")         # raises Person.NotFound (D12)
    ada.name = "Ada L."                                  # dirty-tracked; owned predicates only
    orgs = await s.load(ada, Person_.member_of)          # explicit, one query (Q9)
    await s.delete(acme)                                 # cascade per LinkML composition

# --- 6. query: typed expressions → SPARQL AST → bound parameters (Q6, Q7) ---
q = (select(Person)
     .where(Person_.name.contains("Ada"),
            Person_.member_of.any(Organization_.name.lang("en") == "ACME"))
     .order_by(Person_.name)
     .limit(20))
people = await s.exec(q)                                 # list[Person]
page = await s.page(q, size=20)                          # page.items, page.total (Q15)
print(q.to_sparql())                                     # always inspectable (D14)
cards = await s.exec(q.project(PersonCard))              # read-only projection (X10)

# --- 7. repository per aggregate: optional sugar, generated or one line ---
class PersonRepo(Repository[Person]): ...
await PersonRepo(s).find(name="Ada")                     # kwargs typed by PersonFilter TypedDict (D16)

# --- 8. escape hatch that still returns models (Q3) ---
rows = await s.sparql("SELECT ?id WHERE { ?id org:memberOf ?o }", bind={"o": acme.id}, as_=Person)

# --- 9. sync twin, generated from the async source (D7) ---
from rdf_persistence.sync import Session as SyncSession  # same names, no await
```

**Concepts to learn: 9** — generated model, field metamodel (`Person_`), `Store`, `Session`,
`begin`, `select`, `Repository`, `LangString`, `load`. On par with neomodel (8) and SQLModel (8).

### Reasoning behind each choice

1. **Generated Pydantic stays untouched** (DX-P1, approach A/B, G1). sparqlmodel and Beanie need a
   base class; ODMantic and Ecto show a separate engine/repo costs no lines.
2. **`Person_` metamodel instead of `Person.name`** (DX-P3). Attaching expressions to the domain
   class at runtime (Beanie, `init.py:387`) works but (a) mutates the domain class globally,
   (b) the IDE still sees `str`, so `.lang()` / `.any()` are invisible (SQLModel's `col()` exists
   for exactly this). A generated companion module is fully typed, keeps the domain pure, and is
   free once there is a generator. Approach A (no generator) gets an untyped `F(Person).name`
   fallback built from `linkml_meta`.
3. **`Store.connect(url, schema=)` + capabilities** (DX-P6, T7). One config object; the store says
   honestly what a commit means. In-memory and remote by URL so tests and production differ by
   one string.
4. **`Session` per request via DI with `identity` and `graph`** (DX-P12, AZ4, DEC-8). Kills the
   global-singleton and shared-mirror footguns of neomodel and sparqlmodel.
5. **`async with s.begin()` commits one SPARQL Update with a version guard** (DX-P6, DX-P7, T1,
   T2). The block is the only transaction concept; the error explains the conflict and the fix.
   Prisma's batch `$transaction([...])` is the mainstream precedent for "one request = one
   transaction".
6. **`get` raises, `get_or_none` returns `None`; `Person.NotFound`** (D12, Django/SQLAlchemy
   naming). Generated per class, no metaclass needed on the domain class — the exception can live
   in the generated metamodel (`Person_.NotFound`) and subclass a common `NotFound`.
7. **References are IRIs; loading is explicit** (DX-P8). LinkML already types non-inlined ranges
   as `str`, so the default avoids N+1 and open-world confusion; `load()` batches.
8. **`select()` + `exec()` + `page()` + `to_sparql()`** (DX-P3/P5, SQLModel naming). Developers
   already know them; `page()` adds totals because every API needs them (Q15).
9. **Repository is optional sugar** (DX-P4, Spring Data). Cosmic-python wants a repository per
   aggregate; the session is enough for scripts. Kwargs = equality only, typed via TypedDict.
10. **Sync twin generated** (DX-P13, D7). FastAPI wants async; notebooks and CLIs want sync.

## Feature inventory (deep dives, DX-relevant ids)

| Id | SQLModel | Beanie | ODMantic | Piccolo | Evidence |
|---|---|---|---|---|---|
| D1 typing/IDE | present | present | present | present | `py.typed` in all four; Beanie `tests/typing/`; SQLModel `select` overloads |
| D2 async | present | present | present | present | `ext/asyncio/session.py:30`; Beanie all-async; `engine.py:295`; `query/base.py:140` |
| D3 framework integration | present (FastAPI docs) | partial (docs article) | present (`docs/usage_fastapi.md`) | present (`create_pydantic_model`, asgi templates) | paths cited above |
| D4 docs tutorial+ref | present (tested) | present | present | present | `docs_src/` + `tests/test_tutorial/`; `docs/tutorial/` |
| D5 testing support | partial (recipe) | absent (live Mongo) | absent | present (`ModelBuilder`, tester) | `test_main.py:9-27`; `conftest.py`; Piccolo testing docs |
| D6 lifecycle hooks | partial (SA events) | present (`actions.py`) | absent (grep `before_save` none) | absent | `beanie/odm/actions.py` |
| D7 single-source sync/async | absent (two classes) | absent | absent (`SyncEngine` duplicated) | present (`run_sync`) | `engine.py:715`; `query/base.py:201` |
| D12 per-model exceptions | absent | absent | absent | absent | none found (grep `DoesNotExist`) |
| D13 model-aware errors | partial | absent (bare) | present | partial | `beanie/exceptions.py`; `odmantic/exceptions.py:22-57` |
| P3 UoW/session | present (SA) | partial (state management) | partial (engine, modified fields) | absent | `settings/document.py:10`; `model.py:542` |
| P5 optimistic concurrency | partial (SA `version_id_col`, not in SQLModel docs) | present (opt-in) | absent | absent | `documents.py:501-515` |
| P9 change detection | present (SA) | present | present | absent (`save()` writes all) | `model.py:710-711` |
| Q2 expression builder | present | present | present | present | — |
| Q3 raw escape → models | present (SA) | partial (aggregate with `projection_model`) | partial (raw query usage doc) | present (`raw()`) | `docs/raw_query_usage.md` |
| Q9 eager loading | present (SA loaders) | present (`fetch_links`, `nesting_depth`) | present (references fetched) | present (`nested`, joins) | `documents.py:224-253` |
| X10 projections | present (multi-model pattern) | present (`projection_model`) | absent | present (`select` columns, `create_pydantic_model`) | `tests/typing/find.py` |

### Proposed new features

Continuing D* (DevEx). The leader may move D15/D16 to G*.

| Id | Feature | Evidence |
|---|---|---|
| **D14** | Inspectable compiled query: `to_sparql()` with bound values, plus query logging (refines S14 on the API side) | Drizzle `.toSQL()`, SQLAlchemy `echo`, Django `qs.query`, Prisma `log` |
| **D15** | Generated typed field metamodel for queries (`Person_.name: Field[str]`, RDF operators `.lang()`, `.any()`, `.missing()`), keeping domain classes persistence-free | JPA static metamodel; SQLModel `col()` workaround (`expression.py:200`); ODMantic `bool` in signature (`engine.py:433-437`) |
| **D16** | Generated typed filter / input types per class (`TypedDict`) for repository finders and partial updates | Prisma generated `where` / `data` input types |
| **D17** | Explicit-loading sentinel: not-loaded vs absent vs empty, never lazily queried, never saved as a deletion | Ecto `%Ecto.Association.NotLoaded{}`, SQLAlchemy `lazy="raise"` |
| **D18** | Test kit: pytest plugin with an in-memory store fixture per test, LinkML-driven fake instance builder, graph-isomorphism assertions (refines D5) | Piccolo `ModelBuilder`, Ecto SQL Sandbox, SQLModel test recipe |
| **D19** | Tested documentation: every docs example is a file executed in CI | SQLModel `docs_src/` (150) ↔ `tests/test_tutorial/` (119) |
| **D20** | Data migrations: versioned SPARQL Update scripts (forward/backward) with an applied-migrations record in the store, plus SHACL shape install | Beanie `migrations/`, Django, Prisma `migrate`, neomodel `install_labels` |
| **D21** | CURIE-everywhere: schema prefixes accepted in every id argument, CURIE-aware `repr` and error messages | ODMantic/Beanie readable ids; RDF-specific |
| **D22** | "Did you mean" suggestions for unknown slots, classes, prefixes | Spring `PropertyReferenceException.java:43-44` |
| **D23** | Stable error codes with one documentation page per code | Prisma `P2025` (`mod.rs:244-245`) |
| **D24** | Deterministic ordering of multi-valued properties on load (stable diffs, tests, UIs) | RDF-specific; set semantics vs `list[T]` |
| **D25** | Typing regression tests (`assert_type` modules checked in CI) | Beanie `tests/typing/` |

Also recommended as defaults (existing ids): **P5/T2 optimistic concurrency on by default**
(Pony, Rails `lock_version`), **D7** async-first with generated sync, **D12/D13** errors.

## Deep-dive scores

C5 and C7 are scored relative to their own ecosystem (reuse of mature drivers; portability across
their backends); they are not RDF candidates. DX = developer experience (0–5).

| Criterion | SQLModel | Beanie | ODMantic | Piccolo |
|---|---|---|---|---|
| C1 features | 4 — full ORM via SQLAlchemy (`orm/session.py`) | 4 — links, revision, state, views, migrations (`docs/tutorial/`) | 3 — CRUD, references, sessions; no hooks/migrations (`engine.py`) | 4 — ORM, builder, migrations, admin (`piccolo/apps/`) |
| C2 patterns | 4 — Data Mapper, UoW, identity map from SA | 3 — Active Record + optional state tracking | 5 — Data Mapper engine, change tracking (`engine.py:295`, `model.py:542`) | 3 — Active Record + query builder |
| C3 friendliness | 5 — tested tutorial, FastAPI-native | 4 — short; weak errors (`exceptions.py`) | 4 — short; good errors; small docs | 4 — `run_sync`, playground |
| C4 adoption | 5 — `pip install`, sqlite works | 3 — needs MongoDB + `init_beanie` | 3 — needs MongoDB | 4 — sqlite or Postgres |
| C5 reuse of foundations | 5 — SQLAlchemy + Pydantic | 5 — pymongo + Pydantic | 4 — pymongo + Pydantic | 3 — own builder over asyncpg/sqlite |
| C6 DDD fit | 3 — session separate, but classes carry table metadata | 2 — persistence methods on documents | 4 — models free of persistence methods | 2 — Active Record |
| C7 portability | 4 — any SA dialect | 1 — MongoDB only | 1 — MongoDB only | 3 — Postgres, SQLite, Cockroach |
| C8 health | 5 — 18.5k★, active, tested docs | 4 — 2.7k★, active | 2 — single maintainer, quiet since 2026-01 | 4 — active |
| C9 composability | 4 — SA ecosystem, Alembic, FastAPI | 3 — Pydantic, FastAPI | 3 — Pydantic, FastAPI | 3 — own ecosystem |
| C10 maintainability | 4 — thin layer, but tied to SA internals | 3 — large surface | 4 — small surface | 3 — large surface |
| **DX** | **5** | 4 | 4 | 4 |

**Reuse verdict (all benchmarks): borrow ideas.** Top ideas: SQLModel (docs and testing story,
`exec()` naming, async mirror), ODMantic (engine-as-Data-Mapper over Pydantic — the closest shape
to rdf-persistence), Beanie (revision locking, typed projections, data migrations, typing
tests), Piccolo (`run_sync`, ContextVar transactions, `ModelBuilder`), Prisma (batch transaction
= single request, generated input types, coded errors), Ecto (explicit loading, changesets,
sandbox), Spring (typo suggestions, metamodel).

**Anti-patterns to avoid** (seen here): bare exceptions (Beanie); `session=` keyword threaded
through every call (Beanie); global init registries (Beanie, Tortoise, neomodel); interpreter
magic (Pony); `refresh()` after commit to learn ids (SQLModel); install-extras wall before the
first example (Beanie docs); two duplicated class trees for sync/async (ODMantic).

## How this plugs into MWBv2 and an ACL-agnostic rdf-persistence

- **L0 (generation):** the generator that already emits LinkML Pydantic (G1) additionally emits
  `fields.py` (D15), `filters.py` TypedDicts (D16), per-class exceptions (D12) and the JSON-LD
  context (G7). Approach B gets all of it; approach A gets the untyped `F(Model)` fallback.
- **L1 (persistence):** `Store` / `Session` / `select` / `Repository` as sketched; the session is
  the unit of work (P3, T1, T2) and the only place that talks to the store port.
- **L2 (stores):** `Store.connect(url)` picks the adapter; `capabilities()` (T7) drives honest
  transaction semantics.
- **L3 (authorization, DEC-8):** the session carries `identity` and `graph` per request; the store
  adapter forwards identity (AZ4) or the PEP port injects graph scope. No shared mirror or
  cross-request cache, so DX choices do not leak data.
- **L4 (service):** FastAPI `Depends(get_session)`; projections (X10) feed response models;
  `ConflictError` → 412 (X19); error codes (D23) → problem+json.
- **L5 (JS client):** the same principles hold in TS (Prisma/Drizzle-style generated types, G16);
  the JS side consumes the service contract, not the persistence API.
- **L6 (events):** commit hooks (D6) after the single update for the outbox; not a DX
  differentiator.

## Variants enabled

| Variant / approach | Effect of this angle |
|---|---|
| V1 Portable Python core | **Enables** — the sketch is the V1 core API; in-memory Oxigraph for tests (D18) |
| V2 semantic.works-compatible | Supports — same API; `begin()` must report degraded atomicity behind the chunking proxy (T7, T11) |
| V3 Fluree | Supports — `identity=` forwards Fluree credentials; Fluree's conflict detection maps to `ConflictError` |
| V4 GraphDB | Supports — `capabilities().multi_request_tx=True` lets `begin()` span several requests |
| V5 Graph-direct reads | Neutral — the read side is LDkit/JS; the same DX principles apply there |
| Approach A runtime mapper | Supported with weaker typing (`F(Model).field`, untyped kwargs) |
| Approach B generated | **Best DX** — typed metamodel, TypedDicts, per-class exceptions are generated |
| Approach C generic service | Weakest DX for domain code (no typed classes); fine for RAD screens |

## Open questions

1. Accept a **generated `Person_` companion** (D15) as the query vocabulary, or attach expression
   attributes to the generated classes at runtime (Beanie style, `Person.name == ...`, shorter but
   untyped operators and a mutated domain class)?
2. **Optimistic concurrency on by default** for every aggregate (Pony/Rails style), or opt-in
   (Beanie)? Default-on costs one version triple per aggregate.
3. **Multi-valued as `list[T]`** (what LinkML generates today) with set semantics, or ask the
   generator for `set[T]` / a custom `RdfSet[T]`? `list` is more familiar and JSON-friendly.
4. **`LangString` as `dict[str, str]`** (JSON-LD language map) or a dedicated class with
   `.best(lang_prefs)`? Needs the G6 decision.
5. **Repository required or optional?** Cosmic-python says repository per aggregate; the DX
   benchmarks say the session alone is enough for scripts.
6. **Async-first with generated sync** (neomodel, D7) or `run_sync()` on awaitables (Piccolo)?
   The latter is less code to own.
7. Should the **test kit** (D18) ship in the core package (`rdf_persistence.testing`, pytest
   entry point) — SQLModel/Piccolo style — or as a separate package?

---
Not checked: SQLAlchemy, Django, Prisma, Drizzle, Tortoise, Pony, Ecto, ActiveRecord and Spring
examples were written from their official quick-starts and not executed; only the cited error
strings were verified in source. GitNexus indexes were built but the findings above come mainly
from reading source files directly. Line counts are approximate (imports and blank lines excluded).

## Round 5

### Id mapping note (raw report → taxonomy v4)

The round-3 proposals in this report were renumbered on merge: D14 → **D17**, D15 → **G35**,
D16 → **G36**, D17 → **D18**, D18 → **D19**, D19 → **D21**, D20 → **EV1** (+EV4), D21 → **D22**,
D22 → **D23**, D23 → **D24**, D24 → **D25**, D25 → **D26**. **Correction to this report:** the
identity-propagation feature cited above as "AZ4" is **AZ19** in v3/v4 (AZ4 is list-filter
integration). The polished page already uses AZ19.

### (a) v4 cross-check — SQLModel · Beanie · ODMantic · Piccolo

Paths are relative to each clone in `/home/lps/work/repos/<name>/`. "n.a." = the concept does not
exist outside RDF / a service layer (no graphs, no PDP, no UI, no LPG projection). Absences
confirmed by grep over the clone (`Did you mean`, `checksum`, `testcontainers`, `schemathesis`,
`opentelemetry`, `on_commit|after_commit`, `NotLoaded|sentinel`, `version_id_col` → 0 hits in
library code unless cited).

| Id | SQLModel | Beanie | ODMantic | Piccolo | Evidence |
|---|---|---|---|---|---|
| B1 aggregate declaration | partial | partial | partial | absent | SQLModel `Relationship(cascade_delete=)` (`docs_src/tutorial/relationship_attributes/cascade_delete_relationships/`); Beanie `Link` + `WriteRules`/`DeleteRules` (`beanie/odm/fields.py:344`); ODMantic `EmbeddedModel` vs `Reference()` (`docs/modeling.md:395`) — ownership by embedding, no root declaration |
| B2 boundary validation at generation | absent | absent | absent | absent | no generator in any |
| B3 whole-aggregate load | partial | partial | partial | partial | SA loader options; Beanie `fetch_links` + `nesting_depth` (`documents.py:224-253`); ODMantic references always fetched (`engine.py` pipeline lookups); Piccolo `nested=True` |
| B4 whole-aggregate save, diffed | partial | partial | partial | absent | SA cascade save-update + UoW diff; Beanie `link_rule=WriteRules.WRITE` + `save_changes()`; ODMantic `__fields_modified__` (`model.py:542`); Piccolo `save()` writes all columns |
| B5 typed cross-aggregate reference | absent (FK `int` + navigation) | **present** `Link[T]` holding a DBRef, resolved explicitly (`fields.py:378-381`) | absent (`Reference()` embeds the full object) | partial (`ForeignKey` value, joins navigate) | — |
| B6 aggregates-per-commit policy | absent | absent | absent | absent | none |
| B7 single conjunctive guarded op | n.a. | partial (revision in one update filter, one doc only, `documents.py:501-515`) | absent | absent | — |
| B8 inspectable change-set | partial (`session.dirty/new/deleted` from SA) | partial (`get_changes()`, `documents.py:1114`) | partial (`__fields_modified__`) | absent | values exist; none renders them backend-neutrally |
| B9 domain events via outbox | absent | absent | absent | absent | none |
| B10 aggregate storage strategy | n.a. | n.a. | n.a. | n.a. | collection/table per class only |
| B11 version kept by mapper, exposed as ETag | partial (SA `version_id_col` mapper-level; not documented in SQLModel, 0 hits) | partial (`revision_id` is a field on the document, `documents.py:170`, excluded from dumps) | absent | absent | no ETag anywhere |
| B12 after-commit hooks | partial (SA `after_commit` session event) | partial (`@after_event(Insert/Save)` per document, not per commit, `actions.py:186`) | absent | absent | grep `on_commit` 0 in library code |
| B13 boundary-aware delete | partial (`cascade_delete`) | partial (`DeleteRules.DELETE_LINKS`, `fields.py:344-346`) | absent | partial (`ForeignKey(on_delete=)`, DB-level) | none refuses inbound references at mapper level |
| B14 bounded-context partitioning | n.a. | n.a. | n.a. | partial (Piccolo "apps" each with own tables/migrations, `piccolo/apps/`) | — |
| B15 no-autoflush contract | absent (SA autoflush is on by default — the inverse) | n.a. | n.a. | n.a. | — |
| B16 saga support | absent | absent | absent | absent | none |
| PG1–PG4 | n.a. | n.a. | n.a. | n.a. | not graph libraries |
| EV1 migration runner + log | absent (Alembic, external) | **present** (`MigrationLog` document, `migrations/models.py:10-16`; runner `migrations/runner.py`) | absent | **present** (`Migration` table, `apps/migrations/tables.py:10`; `commands/forwards.py`) | — |
| EV2 checksum, lock, dry run | absent | absent | absent | partial (`migrations check` lists unapplied, `commands/check.py`; no checksum) | grep `checksum` 0 |
| EV3 schema diff → skeletons | absent (Alembic autogenerate external) | absent | absent | **present** (`apps/migrations/auto/schema_differ.py`, `schema_snapshot.py`) | — |
| EV4 down migrations | absent | **present** (`Forward`/`Backward` classes, `docs/tutorial/migrations.md:16-41`) | absent | **present** (`commands/backwards.py`) | — |
| EV5 object-level transformation | absent | **present** (iterative migrations with typed input/output documents, `migrations/controllers/iterative.py:55-63`) | absent | partial (raw/Python migration steps) | — |
| EV6 post-migration validation gate | absent | partial (documents validated on parse) | absent | absent | — |
| EV7 schema version check at startup | absent | absent | absent | partial (`check` command, not enforced at startup) | — |
| EV8 staged bulk load | absent | absent | absent | absent | — |
| EV9 migration rehearsal | absent | absent | absent | absent | — |
| AZ30–AZ36 | n.a. | n.a. | n.a. | n.a. | no authorization concept (Piccolo's `user` app is authentication only, `piccolo/apps/user`) |
| G28–G34 | n.a. | n.a. | n.a. | n.a. | no LinkML / OpenAPI / reasoner generation |
| G35 typed field metamodel | absent — workaround `col()` (`sql/expression.py:200`) | absent — runtime `ExpressionField` (`utils/init.py:387`) | absent — `bool` in signature (`engine.py:433-437`) | partial — columns are typed class attributes on the table (Active Record, not a separate metamodel) | the gap this angle identified |
| G36 typed filter / input TypedDicts | absent | absent | absent | absent | none |
| T12 read-tracked optimistic commit | n.a. | n.a. | n.a. | n.a. | — |
| T13 read-only mode guard | absent | absent | absent | absent | Piccolo `read_only_columns` is per column (`tests/columns/test_generated.py:198`), not a mode |
| T14 cross-store unit of work | partial (SA `Session(binds=...)`) | absent | absent | partial (engine per table via `Meta.db`) | — |
| S20–S23 | n.a. | n.a. | n.a. | n.a. | no graphs; no admin port |
| X23 strict JSON-LD | n.a. | n.a. | n.a. | n.a. | — |
| X24 MCP projection | n.a. | n.a. | n.a. | n.a. | — |
| E10 subscription options | n.a. | n.a. | n.a. | n.a. | — |
| I7 reversible IRI minting | n.a. | n.a. | n.a. | n.a. | — |
| I8 deferred id minting | present (autoincrement at flush — the footgun) | absent (`PydanticObjectId` minted client-side) | absent (`default_factory=ObjectId`, `model.py:477`) | present (id at insert) | for RDF client-side minting is preferred |
| P20 reference-aware flush ordering | **present** (SA UoW topological sort) | partial (`WriteRules.WRITE` writes links first) | partial (references saved first) | absent | — |
| U11–U13 | n.a. | n.a. | n.a. | n.a. (Piccolo Admin is a separate repo) | — |
| D14 stale-write warning | n.a. | n.a. | n.a. | n.a. | RDF-specific |
| D15 parameter redaction in logs | partial (SA `create_engine(hide_parameters=True)`, not in SQLModel docs) | absent | absent | absent (`log_queries`, `engine/postgres.py:362`, no redaction) | — |
| D16 formal HTTP contract model | n.a. | n.a. | n.a. | n.a. | — |
| D17 inspectable compiled query | present (`str(select(...))`, `echo=True`) | present (`get_filter_query()`, `queries/find.py:93`) | present (`QueryExpression` is a dict, `query.py:9`) | present (`__str__`, `query/base.py:341`; `log_queries`) | — |
| D18 explicit-loading sentinel | partial (SA `lazy="raise"`) | partial (unfetched value stays a `Link` object, `fields.py:378`) | absent | absent | none distinguishes absent from not loaded |
| D19 test kit | partial (docs recipe only) | absent | absent | **present** (`testing/model_builder.py:17`, `piccolo tester`) | — |
| D20 real-store testcontainers fixtures | absent | absent | absent | absent | grep `testcontainers` 0 |
| D21 tested documentation | **present** (`docs_src/` 150 ↔ `tests/test_tutorial/` 119) | absent | partial (`docs/examples_src`) | absent | — |
| D22 CURIEs everywhere | n.a. | n.a. | n.a. | n.a. | RDF-specific |
| D23 "did you mean" | absent | absent | absent | absent | grep 0 |
| D24 stable error codes | absent | absent | partial (`odmantic::<type>` Pydantic error types, `exceptions.py:60-65`) | absent | — |
| D25 deterministic multi-value order | n.a. | n.a. | n.a. | n.a. | arrays are ordered in SQL/Mongo |
| D26 typing regression tests | present (`tests/test_asyncio.py:33-46` `assert_type`) | **present** (`tests/typing/`) | partial (`tests/test_typing_utils.py`, utilities only) | partial (one `assert_type` file) | — |
| D27 fault-injection tests | absent | absent | absent | absent | grep `toxiproxy` 0 |
| D28 API contract fuzzing | absent | absent | absent | absent | grep `schemathesis` 0 |
| D29 OpenTelemetry spans | absent (only in `uv.lock`) | absent | absent | absent | — |

**Counts (77 v4 ids × 4 libraries = 308 cells; grouped n.a. rows counted per id):**
SQLModel 5 present / 11 partial / 24 absent / 37 n.a.;
Beanie 6 / 11 / 23 / 37;
ODMantic 1 / 8 / 31 / 37;
Piccolo 6 / 10 / 25 / 36.
Totals: **18 present, 40 partial, 103 absent, 147 n.a.** Headline: the mainstream benchmarks cover the DX ids and the
migration ids (Beanie, Piccolo); none covers the DDD-boundary ids (B6, B9, B16) or G35/G36 —
the typed-metamodel gap is real outside RDF too.

### (b) Page review — `angles/dx.adoc` and `design-implications.adoc` § Developer-facing API shape

| # | Page line (quoted) | Problem | Fix |
|---|---|---|---|
| 1 | dx.adoc:16 "ODMantic, SQLAlchemy 2.0, Ecto and Prisma need 8–14 lines for CRUD plus a query" | Overstatement: Prisma is 20 lines including its schema (the same page says so at :111); range is 9–14 | "ODMantic (9), Ecto (10) and SQLAlchemy 2.0 (14) need 9–14 lines …; Prisma needs 8 lines of code plus its schema." |
| 2 | dx.adoc:84 "`save_changes()` sends only the diff." | Missing caveat: only with `Settings.use_state_management = True` (off by default, `settings/document.py:10`) | append "(when `use_state_management` is on; off by default)" |
| 3 | dx.adoc:115 "accessing it never queries, so N+1 is impossible" | Overstatement: preloading in a loop is still N+1; lazy N+1 is impossible | "… so *lazy* N+1 is impossible" |
| 4 | dx.adoc:154 "P5 optimistic concurrency \| partial" (SQLModel) | Missing caveat | "partial (SQLAlchemy `version_id_col`; not documented in SQLModel)" |
| 5 | dx.adoc:219 "raw proposal ids from the report are dropped" and :296-311 "Not yet in the taxonomy" | Stale after v4 merge | Cite the v4 ids: metamodel G35, TypedDicts G36, `to_sparql` D17, sentinel D18, test kit D19, tested docs D21, migrations EV1/EV4, CURIEs D22, did-you-mean D23, codes D24, ordering D25, typing tests D26; retitle the section "Features contributed (v4 ids)"; add G35/D17/D18/G36 to sketch comments (lines 232, 256, 267, 272) |
| 6 | dx.adoc:325 "after-commit hooks (D6) drive the outbox" | Wrong id: D6 is per-object lifecycle hooks; after-commit is B12 (outbox: B9) | "after-commit hooks (B12) and the outbox (B9)" |
| 7 | dx.adoc:362 "Prisma: https://github.com/prisma/prisma" | Repo renamed (API returns `prisma/orm`) | `https://github.com/prisma/prisma` (redirects to `prisma/orm`) — note the rename |
| 8 | design-implications.adoc § API shape: "Field expressions on plain classes are unsolved everywhere." | Overstatement: SQLAlchemy 2.0 solves it with `Mapped[]` descriptors — when the ORM owns the class | "… are unsolved for classes the ORM does not own (SQLAlchemy solves it only by owning the class with `Mapped[]`)." |
| 9 | design-implications.adoc § API shape: "A Data Mapper costs no lines: ODMantic does CRUD plus a query in 9 lines, Django in 11." | Ambiguous: Django is the Active Record comparison point | "… ODMantic (Data Mapper) 9 lines vs Django (Active Record) 11." |
| 10 | design-implications.adoc § API shape: the `[RP-409]` error text | Reads as an existing message | prefix "illustrative (proposed):" |

Checked and confirmed (no change): Beanie accepting `bool` (`beanie/odm/interfaces/find.py:54`
`*args: Mapping[Any, Any] | bool`); Beanie backward migrations (`docs/tutorial/migrations.md:16-41`);
AZ19 for identity propagation; all quoted error strings; scores and stats.

### (c) Final verdict

**Ideas** — none of the benchmarks is an RDF dependency; they define the API shape and tooling
of rdf-persistence.

Three things a system architect must remember:
1. **Data Mapper over generated Pydantic costs no DX** (ODMantic 9 lines) — keep LinkML classes
   persistence-free and put all ergonomics in the session; do not adopt Active Record for brevity.
2. **Typed queries need a generated companion** (G35, JPA-metamodel style). Every Pydantic-based
   ORM fakes it (`col()`, `bool` signatures, runtime `setattr`); only owning the class (SQLAlchemy)
   or generating a metamodel gives real IDE help — commit to approach B for full DX.
3. **The loved defaults are safety defaults**: one obvious transaction block that maps to one
   SPARQL Update, optimistic concurrency on, explicit loading (not loaded ≠ absent), DI with no
   globals, an in-memory store running the same SPARQL in tests, and errors that name the model,
   IRI and fix. Each is cheap at design time and expensive to retrofit.

### (d) Purpose and origin + variant fit — deep-dived candidates

Purpose and origin: see `## Purpose and origin` near the top of this report (all benchmarks,
including SQLModel, Beanie, ODMantic, Piccolo). Summary for the four deep dives:

| Candidate | Built for / by / context | Design angle | Fit in L0–L6 |
|---|---|---|---|
| SQLModel | FastAPI users who want one class for API model and table; Sebastián Ramírez (FastAPI org), 2021, on SQLAlchemy + Pydantic | API-first, Pydantic-first | Ideas for L1 API surface and L4 FastAPI integration; docs/testing practice. Not a component (SQL only) |
| Beanie | Async MongoDB apps on Pydantic; Roman Right, BeanieODM org | Active Record over Pydantic documents | Ideas for L1 (revision locking, projections, links) and L0/L2 data migrations. Not a component (MongoDB only) |
| ODMantic | Type-safe MongoDB access with Pydantic, engine-based; Arthur Pastel (single maintainer) | Data Mapper (engine) | The closest *shape* for L1 `Session`; not a component |
| Piccolo | Async Postgres/SQLite apps with batteries (migrations, admin, scaffolding); Daniel Townsend | Query-builder-first, batteries | Ideas for L1 (`run_sync`, ContextVar transactions), test kit (D19), migrations (EV1/EV3/EV4), L4 admin idea (U5). Not a component |

Variant fit (they contribute ideas, never code, so "supports" means the idea strengthens that
variant):

| Candidate | V1 | V2 | V3 | V4 | V5 | A | B | C |
|---|---|---|---|---|---|---|---|---|
| SQLModel | supports (session API, DI, tested docs) | supports | supports | supports | neutral | supports (session API) | **enables** (generated typed models + FastAPI routes, its multi-model pattern) | neutral |
| Beanie | supports (revision → T2, data migrations → EV1/EV5) | supports | supports (revision ≈ Fluree conflicts) | supports | neutral | supports (runtime `ExpressionField` = A's untyped fallback) | supports (typed projections) | neutral |
| ODMantic | **enables** (engine-as-Data-Mapper is the V1 core shape) | supports | supports | supports | neutral | supports | supports | neutral |
| Piccolo | supports (`run_sync`, ContextVar tx, test kit) | supports | supports | supports | neutral | supports | supports (`create_pydantic_model` ≈ projections) | supports (admin from schema ≈ U5) |

No candidate blocks any variant.

### (e) New features

None. The round-3 proposals are merged (G35, G36, D17–D19, D21–D26, EV1/EV4) and the v4
cross-check found nothing important missing.
