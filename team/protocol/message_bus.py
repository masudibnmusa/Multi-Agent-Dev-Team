from collections import defaultdict, deque
from typing import Callable

from team.protocol.messages import Message


class MessageBus:
    """In-process bus: per-agent inboxes, payload validation, and listeners for logging."""

    def __init__(self) -> None:
        self._inboxes: dict[str, deque[Message]] = defaultdict(deque)
        self._listeners: list[Callable[[Message], None]] = []
        self.history: list[Message] = []

    def subscribe(self, listener: Callable[[Message], None]) -> None:
        self._listeners.append(listener)

    def send(self, msg: Message) -> None:
        msg.parse()  # reject malformed payloads at the door
        self._inboxes[msg.recipient].append(msg)
        self.history.append(msg)
        for listener in self._listeners:
            listener(msg)

    def receive(self, recipient: str) -> Message | None:
        inbox = self._inboxes[recipient]
        return inbox.popleft() if inbox else None

    def drain(self, recipient: str) -> list[Message]:
        inbox = self._inboxes[recipient]
        items = list(inbox)
        inbox.clear()
        return items

    def pending(self, recipient: str) -> int:
        return len(self._inboxes[recipient])