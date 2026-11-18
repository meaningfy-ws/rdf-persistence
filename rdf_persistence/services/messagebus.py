"""An in-process message bus in the Cosmic Python style (message-bus PD-13).

A command (an ``Activity`` subclass) goes to the handler of its nearest class; after a commit the
completed activity goes to the observers of its class and of every ancestor. A handler or observer gets
a ``Work``: the session, the collaboration, a unit of work, and ``send`` to queue a command. Delivery
is in process and at most once. This module sits above the collaboration layers, which never import it.
"""

import functools
import inspect
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextvars import ContextVar
from typing import Any

from rdf_persistence.core.domain.exceptions import InvalidBody, MessageLimitExceeded
from rdf_persistence.core.domain.generated.rp_discussion import PostComment, PostReply
from rdf_persistence.core.domain.generated.rp_provenance import Activity
from rdf_persistence.core.domain.generated.rp_workflow import Transition
from rdf_persistence.core.services.generated.rp_core_services import LogContext
from rdf_persistence.core.services.telemetry import log_extra, traced
from rdf_persistence.provenance.services.provenance import Served, new_activity_id
from rdf_persistence.schema.services import vocabulary as v
from rdf_persistence.services.collaboration import Collaboration
from rdf_persistence.services.generated.settings.rp_settings import LimitSettings
from rdf_persistence.services.mapper import Mapper, UnitOfWork
from rdf_persistence.services.session import Session

log = logging.getLogger(__name__)

Handler = Callable[[Activity, "Work"], Awaitable[object]]
Observer = Callable[[Activity, "Work"], Awaitable[None]]


class _Run:
    """One running ``handle``: the collaborations it serves, the commands it started and the queue it
    still owes, each command with the collaboration it was sent under. ``closed`` once it returned."""

    def __init__(self) -> None:
        self.collaborations: list[Collaboration] = []
        self.started = 0
        self.queue: list[tuple[Activity, Collaboration]] = []
        self.closed = False

    def of_session(self, session: Session) -> Collaboration | None:
        """The collaboration of this run that writes through ``session``, if any."""
        return next((c for c in self.collaborations if c.session is session), None)


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
        return UnitOfWork(self.session, self._mapper, served=self.served)

    async def send(self, command: Activity) -> None:
        """Queue ``command``; ``handle`` runs it after the current one. ``RuntimeError`` outside ``handle``."""
        if self._run is None or self.collaboration is None:
            raise RuntimeError(
                "send needs a running handle: there is no collaboration to run it with"
            )
        if self._run.closed:
            raise RuntimeError("the handle that gave this work has finished: send queues nothing")
        self._run.queue.append((command, self.collaboration))


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
    """Dispatches commands to handlers (``handle``) and committed activities to observers (``publish``).

    ``limits.max_messages`` bounds one run (a fresh ``LimitSettings`` unless given).
    """

    def __init__(
        self,
        commands: Mapping[type[Activity], Handler],
        observers: Mapping[type[Activity], Sequence[Observer]],
        *,
        limits: LimitSettings | None = None,
        mapper: Mapper | None = None,
    ) -> None:
        for key in (*commands, *observers):
            if not (isinstance(key, type) and issubclass(key, Activity)):
                raise ValueError(f"{key!r} is not an Activity subclass")
        self._commands = dict(commands)
        self._observers = {cls: list(each) for cls, each in observers.items()}
        self._limit = (limits or LimitSettings()).max_messages
        self._mapper = mapper

    async def handle(self, command: Activity, collaboration: Collaboration) -> object:
        """Run ``command``'s handler, then the commands it queued; return the handler's result.

        A call made while another runs in the same context joins its count and its queue.
        """
        run = _run.get()
        if run is not None and not run.closed:
            return await self._start(run, command, collaboration)
        run = _Run()
        token = _run.set(run)
        try:
            result = await self._start(run, command, collaboration)
            while run.queue:
                queued, under = run.queue.pop(0)
                try:
                    await self._start(run, queued, under)
                except MessageLimitExceeded:
                    raise
                except Exception:
                    log.exception(
                        "a queued command failed",
                        extra=log_extra(
                            LogContext(
                                step="bus-queued-failed",
                                activity_class=type(queued).__name__,
                                activity_id=queued.id,
                            )
                        ),
                    )
            return result
        finally:
            run.closed = True
            _run.reset(token)

    async def _start(self, run: _Run, command: Activity, collaboration: Collaboration) -> object:
        run.started += 1
        if run.started > self._limit:
            raise MessageLimitExceeded(self._limit, f"{type(command).__name__} {command.id}")
        if not any(c is collaboration for c in run.collaborations):
            run.collaborations.append(collaboration)
        _refuse_filled(command)
        handler = next(
            (self._commands[cls] for cls in type(command).__mro__ if cls in self._commands), None
        )
        if handler is None:
            raise LookupError(f"no handler for {type(command).__name__}")
        served = self._mapper.served(command) if self._mapper is not None else None
        work = Work(
            collaboration.session,
            collaboration,
            served=served,
            mapper=self._mapper,
            run=run,
        )
        context = LogContext(
            step="bus-handle", activity_class=type(command).__name__, activity_id=command.id
        )
        with traced("rp.bus.handle", context):
            return await handler(command, work)

    async def publish(self, activity: Activity, session: Session) -> None:
        """Call the observers of the activity's classes, nearest first (the session's ``on_commit``).

        An observer's error is logged and the rest run; ``MessageLimitExceeded`` is not swallowed.
        """
        run = _run.get()
        if run is not None and run.closed:
            run = None
        depth = _depth.get()
        if depth >= self._limit:
            raise MessageLimitExceeded(self._limit)
        work = Work(
            session,
            run.of_session(session) if run else None,
            mapper=self._mapper,
            run=run,
        )
        token = _depth.set(depth + 1)
        try:
            for cls in type(activity).__mro__:
                for observer in self._observers.get(cls, ()):
                    try:
                        context = LogContext(
                            step="bus-observe",
                            observer_name=_name(observer),
                            activity_class=type(activity).__name__,
                            activity_id=activity.id,
                        )
                        with traced("rp.bus.observe", context):
                            await observer(activity.model_copy(deep=True), work)
                    except MessageLimitExceeded:
                        raise
                    except Exception:
                        log.exception(
                            "an observer failed",
                            extra=log_extra(
                                LogContext(
                                    step="bus-observer-failed",
                                    observer_name=_name(observer),
                                    activity_class=type(activity).__name__,
                                    activity_id=activity.id,
                                )
                            ),
                        )
        finally:
            _depth.reset(token)


async def _transition(cmd: Activity, work: Work) -> str:
    """The toolkit's handler of ``Transition`` and of every command class that extends it (PD-15).

    Raises:
        InvalidBody: The command names no state or no version.
    """
    assert isinstance(cmd, Transition), "registered for Transition only"
    assert work.collaboration is not None, "a handler always has the caller's collaboration"
    if cmd.to_state is None or cmd.expected_version is None:
        raise InvalidBody("a transition command names to_state and expected_version")
    return await work.collaboration.transition(
        cmd.used_resource,
        cmd.to_state,
        if_version=cmd.expected_version,
        comment=cmd.body_value,
        command=cmd,
    )


async def _comment(cmd: Activity, work: Work) -> str:
    """The toolkit's handler of ``PostComment`` and ``PostReply`` (PD-15): the IRI of the comment."""
    assert isinstance(cmd, PostComment), "registered for PostComment and PostReply only"
    assert work.collaboration is not None, "a handler always has the caller's collaboration"
    return await work.collaboration.comment(
        cmd.used_resource,
        cmd.body_value or "",
        audience=cmd.comment_audience or (),
        references=cmd.comment_references or (),
        reply_to=cmd.replies_to if isinstance(cmd, PostReply) else None,
        command=cmd,
    )


def _bind(
    function: Callable[..., Any], dependencies: Mapping[str, Any], used: set[str]
) -> Callable[..., Any]:
    """``function`` with the dependencies its parameters name, after the first two, bound by name.

    Only a positional-or-keyword or keyword-only parameter takes one (``*args`` cannot be called by name).

    Raises:
        ValueError: A parameter after the first two has no default and no dependency.
    """
    named = list(inspect.signature(function).parameters.values())[2:]
    takers = [p for p in named if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)]
    for p in takers:
        if p.name not in dependencies and p.default is p.empty:
            raise ValueError(
                f"{_name(function)} needs {p.name}, which no dependency provides and has no default"
            )
    names = [p.name for p in takers if p.name in dependencies]
    if not names:
        return function
    used.update(names)
    bound = functools.partial(function, **{n: dependencies[n] for n in names})
    bound.__qualname__ = _name(function)  # type: ignore[attr-defined]  # a partial takes attributes
    return bound


def bootstrap(
    *,
    commands: Mapping[type[Activity], Callable[..., Awaitable[object]]] | None = None,
    observers: Mapping[type[Activity], Sequence[Callable[..., Awaitable[None]]]] | None = None,
    limits: LimitSettings | None = None,
    mapper: Mapper | None = None,
    **dependencies: Any,
) -> MessageBus:
    """A bus with the toolkit's ``Transition``, ``PostComment`` and ``PostReply`` handlers (each unless
    ``commands`` names its class; there is none for ``DeleteFile``) and the handlers
    and observers given, each with the ``dependencies`` its parameters name bound (PD-14).

    Raises:
        ValueError: A dependency that no handler or observer names, or what ``MessageBus`` refuses.
    """
    used: set[str] = set()
    handlers: dict[type[Activity], Callable[..., Awaitable[object]]] = {
        Transition: _transition,
        PostComment: _comment,
        PostReply: _comment,
        **(commands or {}),
    }
    bound_commands = {cls: _bind(h, dependencies, used) for cls, h in handlers.items()}
    bound_observers = {
        cls: [_bind(o, dependencies, used) for o in each] for cls, each in (observers or {}).items()
    }
    if unused := sorted(set(dependencies) - used):
        raise ValueError(f"no handler or observer names the dependency {', '.join(unused)}")
    return MessageBus(bound_commands, bound_observers, limits=limits, mapper=mapper)
