<!-- SECONDARY INPUT: preserved, never groomed. The EPIC (../proposal.md) is the shaped truth. -->

# Seed: message bus (split from aggregate-events, 2026-11-13)

## Seed text

Developer, 2026-11-06 (in `aggregate-events/inputs/seed.md`): "whatever is best, i would not mind
to have an event bus like redis/rabbitmq, but we need also the necessary plumbing for event driven
app in the code, no?"

Developer, 2026-11-13, answering "confirm the events need": "in general we want to support event
driven applications with design patetrns and archietcture described in teh cosmis python book. so
most likely yes, we need support for best pratices of event driven (adopt popular libraries/frameworks
if necessary)"

## Why a separate change

The Cosmic Python book (Percival and Gregory, *Architecture Patterns with Python*) builds the
event-driven architecture in two layers:

- In process (chapters 8 to 10, 12, 13): domain events, a message bus, commands and handlers, the
  unit of work collecting events, CQRS read side, dependency injection in a bootstrap script.
- Across processes (chapter 11): external events through a broker (Redis pub/sub in the book), and
  the outbox the book recommends for reliability.

`aggregate-events` held both. Together they outgrow one LARGE appetite, and the in-process layer is
useful (and testable) without a broker. The lead split it: `message-bus` (this change) is the
in-process layer; `aggregate-events` keeps the outbox, the relay, the broker and server-sent events,
and depends on this one.

## Leader's choices (2026-11-13; the developer may overrule)

- **Hand-rolled bus, as in the book.** The book's message bus is about 60 lines; its semantics
  (a command has one handler and its error propagates, an event has any number and their errors are
  logged) are the point. Checked alternatives: `blinker` (synchronous signals, no command
  semantics), `pyventus` (event emitter, no unit of work), `dependency-injector` (not needed: the
  book injects with `functools.partial` in a bootstrap). The developer's "adopt popular libraries if
  necessary" is applied where it pays: the broker in `aggregate-events` (FastStream).
- **Messages are LinkML classes.** Abstract `Event` and `Command` in the toolkit's schema; the
  toolkit's own change events (added, replaced, removed); consumers declare theirs `is_a` one of them.
- **Async.** The toolkit is asyncio throughout; handlers are coroutines.

## Re-shape: PROV-O (2026-11-13, same session)

Developer, on modelling: "we must model also actions/events side by side with the model, i mean
model events/actions as data structures, as kids of events not thir actual implementation, just the
link ml, andthen this must be a rule ... better to model more "static" domain structures, and then
more dynamic model structures (events/processes/states) in a separate sibling linkml module?"

Developer: "well in fact here the messages and prov-o might be tightly linked, please find a way to
integrate them natively, even adopt prov-o concepts if appropriate, then i smeel a weak link to
usecases? or can we mainly say that there is a standard set of operations/events on an aggregate
(CRUD-Like), and then leave out connection with the use cases complelty?"

Lead's proposal: commands are `prov:Activity` subclasses; the events are the PROV instantaneous
events `prov:Generation` and `prov:Invalidation`; the use case lives on the activity, not on events.

Developer: "so if i underatnd well, the events will be standard more or less, and the shall we then
have like standard commands, and then a set of "extensions" commands that are use case related (if
at all)?"

Lead: three layers (aggregate, toolkit features, consumer extensions); extensions specialise a
standard command or are bare `Activity` subclasses; dispatch follows the class hierarchy; the
generic routes record activities without going through the bus.

Developer: "and yes, 1. events fixed prov set, 2, one per commit rather than aggregate, sure then i
agree with what you said above, go ahead"

The modelling rule was recorded as repository rule P-0001 (`docs/rules/`).

## Test scenarios the EPIC must prove

- A command reaches exactly one handler; a command with no handler or two is refused at bus start.
- An event reaches all its handlers; one handler's error is logged and the others still run.
- A committed unit of work hands its events to the bus after the commit; a refused commit hands none.
- Every committed add, replace and remove yields one toolkit change event naming root, class,
  version and committer.
- An event raised by a handler is handled in the same `handle` call, after the current message.
- Handlers receive their dependencies through the bootstrap, and tests swap them for fakes.
