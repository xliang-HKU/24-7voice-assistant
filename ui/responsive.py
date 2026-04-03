from __future__ import annotations


def compute_breakpoint(width: int) -> str:
    if width < 860:
        return "sm"
    if width < 1140:
        return "md"
    return "lg"

