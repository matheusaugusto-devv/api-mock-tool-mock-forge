import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List


class LogEventManager:
    def __init__(self, max_history: int = 50):
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        self._history: Dict[str, List[dict]] = {}
        self.max_history = max_history

    def get_history(self, project_slug: str) -> List[dict]:
        return list(self._history.get(project_slug, []))

    def subscribe(self, project_slug: str) -> asyncio.Queue:
        if project_slug not in self._subscribers:
            self._subscribers[project_slug] = []
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[project_slug].append(queue)
        return queue

    def unsubscribe(self, project_slug: str, queue: asyncio.Queue) -> None:
        if project_slug in self._subscribers:
            if queue in self._subscribers[project_slug]:
                self._subscribers[project_slug].remove(queue)
            if not self._subscribers[project_slug]:
                del self._subscribers[project_slug]

    async def broadcast(self, project_slug: str, event: dict) -> None:
        if project_slug != "__all__":
            if project_slug not in self._history:
                self._history[project_slug] = []
            self._history[project_slug].insert(0, event)
            if len(self._history[project_slug]) > self.max_history:
                self._history[project_slug].pop()

        queues = self._subscribers.get(project_slug, [])
        for q in list(queues):
            await q.put(event)


log_manager = LogEventManager()
