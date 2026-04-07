"""Minimal URL router — maps (method, path_pattern) to handler functions."""

from __future__ import annotations

import re
from typing import Any, Callable

# Handler signature: (params: dict[str, str], body: Any | None) -> (status, data)
Handler = Callable[..., tuple[int, Any]]


class Router:
    """Simple regex-based HTTP router with path parameter extraction."""

    def __init__(self) -> None:
        self._routes: list[tuple[str, re.Pattern[str], Handler]] = []

    def route(self, method: str, pattern: str) -> Callable[[Handler], Handler]:
        """Decorator to register a route.

        Pattern uses {name} for path parameters, e.g. '/api/features/{feature}/runs'.
        """
        regex = self._compile(pattern)

        def decorator(fn: Handler) -> Handler:
            self._routes.append((method, regex, fn))
            return fn

        return decorator

    def get(self, pattern: str) -> Callable[[Handler], Handler]:
        return self.route("GET", pattern)

    def post(self, pattern: str) -> Callable[[Handler], Handler]:
        return self.route("POST", pattern)

    def put(self, pattern: str) -> Callable[[Handler], Handler]:
        return self.route("PUT", pattern)

    def delete(self, pattern: str) -> Callable[[Handler], Handler]:
        return self.route("DELETE", pattern)

    def dispatch(self, method: str, path: str) -> tuple[Handler, dict[str, str]] | None:
        """Find a matching route. Returns (handler, params) or None."""
        for route_method, regex, handler in self._routes:
            if method != route_method:
                continue
            m = regex.fullmatch(path)
            if m:
                return handler, m.groupdict()
        return None

    @staticmethod
    def _compile(pattern: str) -> re.Pattern[str]:
        """Convert '/api/features/{feature}' to a compiled regex."""
        parts = re.split(r"\{(\w+)\}", pattern)
        regex_parts: list[str] = []
        for i, part in enumerate(parts):
            if i % 2 == 0:
                regex_parts.append(re.escape(part))
            else:
                regex_parts.append(f"(?P<{part}>[^/]+)")
        return re.compile("".join(regex_parts))
