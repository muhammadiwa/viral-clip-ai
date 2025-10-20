from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

from ..domain.pagination import PaginationMeta, PaginationParams

T = TypeVar("T")


def paginate_sequence(
    items: Sequence[T],
    params: PaginationParams,
) -> tuple[list[T], PaginationMeta]:
    """Slice a sequence according to the provided pagination params."""

    total = len(items)
    start = params.offset
    end = start + params.limit
    page_items = list(items[start:end])
    next_offset = end if end < total else None
    meta = PaginationMeta(
        limit=params.limit,
        offset=params.offset,
        count=len(page_items),
        total=total,
        has_more=next_offset is not None,
        next_offset=next_offset,
    )
    return page_items, meta
