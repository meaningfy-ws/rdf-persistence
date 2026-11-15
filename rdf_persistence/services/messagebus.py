"""An in-process message bus in the Cosmic Python style (message-bus PD-13).

A command (an ``Activity`` subclass) goes to the handler of its nearest class; after a commit the
completed activity goes to the observers of its class and of every ancestor. A handler or observer gets
a ``Work``: the session, the collaboration, a unit of work, and ``send`` to queue a command. Delivery
is in process and at most once. This module sits above the collaboration layers, which never import it.
"""

import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextvars import ContextVar
from typing import Any

from rdf_persistence.domain.exceptions import InvalidBody, MessageLimitExceeded
from rdf_persistence.domain.generated.rp_provenance import Activity
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.collaboration import Collaboration
from rdf_persistence.services.mapper import Mapper, UnitOfWork
from rdf_persistence.services.provenance import Served, new_activity_id
from rdf_persistence.services.session import Session

log = logging.getLogger(__name__)

Handler = Callable[[Activity, "Work"], Awaitable[object]]
Observer = Callable[[Activity, "Work"], Awaitable[None]]


class _Run:
    """One running ``handle``: its collaboration, the commands it started and the queue it still owes."""

    def __init__(self, collaboration: Collaboration) -> None:
        self.collaboration = collaboration
        self.started = 0
        self.queue: list[Activity] = []


_run: ContextVar[_Run | None] = ContextVar("message_bus_run", default=None)
_depth: ContextVar[int] = ContextVar("message_bus_publish_depth", default=0)


class Work:
    """What a handler or an observer works with. A handler's ``served`` is its command's ``Served``."""

    def __init__(
        self,
        session: Session,
        collaboration: Collaboration | None,
        *,
        served: Served | None = None,
        mapper: Mapper | None = None,
        run: _Run | None = None,
    ) -> None:
        self.session = session
        self.collaboration = collaboration  # None for a commit made outside ``handle``
        self.served = served
        self._mapper = mapper
        self._run = run

    def unit_of_work(self) -> UnitOfWork:
        """A unit of work on the session, with the bus's mapper (``RuntimeError`` if it has none)."""
        if self._mapper is None:
            raise RuntimeError("the bus has no mapper: build it with MessageBus(..., mapper=...)")
        return UnitOfWork(self.session, self._mapper)  # 3.3: UnitOfWork(served=)

    async def send(self, command: Activity) -> None:
        """Queue ``command``; ``handle`` runs it after the current one. ``RuntimeError`` outside ``handle``."""
        if self._run is None:
            raise RuntimeError(
                "send needs a running handle: there is no collaboration to run it with"
            )
        self._run.queue.append(command)


def command[A: Activity](cls: type[A], **slots: Any) -> A:
    """A command of ``cls`` with a fresh ``urn:uuid:`` id."""
    return cls(id=new_activity_id(), **slots)


def _refuse_filled(command: Activity) -> None:
    for slot in sorted(v.TOOLKIT_FILLED):
        if getattr(command, slot, None) not in (None, []):
            raise InvalidBody(f"{slot} is filled by the toolkit: a command does not set it")


def _name(observer: Callable[..., object]) -> str:
    return getattr(observer, "__qualname__", repr(observer))


class MessageBus:
    """Dispatches commands to handlers (``handle``) and committed activities to observers (``publish``)."""

    def __init__(
        self,
        commands: Mapping[type[Activity], Handler],
        observers: Mapping[type[Activity], Sequence[Observer]],
        *,
        limit: int = 100,
        mapper: Mapper | None = None,
    ) -> None:
        for key in (*commands, *observers):
            if not (isinstance(key, type) and issubclass(key, Activity)):
                raise ValueError(f"{key!r} is not an Activity subclass")
        if limit < 1:
            raise ValueError(f"limit must be at least 1, got {limit}")
        self._commands = dict(commands)
        self._observers = {cls: list(each) for cls, each in observers.items()}
        self._limit = limit
        self._mapper = mapper

    async def handle(self, command: Activity, collaboration: Collaboration) -> object:
        """Run ``command``'s handler, then the commands it queued; return the handler's result.

        A call made while another runs in the same context joins its count and its queue.
        """
        run = _run.get()
        if run is not None:
            return await self._start(run, command, collaboration)
        run = _Run(collaboration)
        token = _run.set(run)
        try:
            result = await self._start(run, command, collaboration)
            while run.queue:
                queued = run.queue.pop(0)
                try:
                    await self._start(run, queued, collaboration)
                except MessageLimitExceeded:
                    raise
                except Exception:
                    log.exception("%s %s failed in the queue", type(queued).__name__, queued.id)
            return result
        finally:
            _run.reset(token)

    async def _start(self, run: _Run, command: Activity, collaboration: Collaboration) -> object:
        run.started += 1
        if run.started > self._limit:
            raise MessageLimitExceeded(self._limit)
        _refuse_filled(command)
        handler = next(
            (self._commands[cls] for cls in type(command).__mro__ if cls in self._commands), None
        )
        if handler is None:
            raise LookupError(f"no handler for {type(command).__name__}")
        served = self._mapper.served(command) if self._mapper is not None else None
        work = Work(
            collaboration.session,  # type: ignore[attr-defined]  # 3.3 adds Collaboration.session
            collaboration,
            served=served,
            mapper=self._mapper,
            run=run,
        )
        return await handler(command, work)

    async def publish(self, activity: Activity, session: Session) -> None:
        """Call the observers of the activity's classes, nearest first (the session's ``on_commit``).

        An observer's error is logged and the rest run; ``MessageLimitExceeded`` is not swallowed.
        """
        run = _run.get()
        depth = _depth.get()
        if run is None and depth >= self._limit:
            raise MessageLimitExceeded(self._limit)
        work = Work(
            session,
            run.collaboration if run else None,
            mapper=self._mapper,
            run=run,
        )
        token = _depth.set(depth + 1)
        try:
            for cls in type(activity).__mro__:
                for observer in self._observers.get(cls, ()):
                    try:
                        await observer(activity, work)
                    except MessageLimitExceeded:
                        raise
                    except Exception:
                        log.exception("%s failed on %s", _name(observer), activity.id)
        finally:
            _depth.reset(token)
