"""Progress display for terminal output.

Shows live status of the research pipeline with source-by-source progress.
"""

import sys
import threading
import time
from typing import Dict, List, Optional

BOLD = "\033[1m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"
DIM = "\033[2m"
NC = "\033[0m"


class ProgressDisplay:
    """Live progress display for the research pipeline."""

    def __init__(self, topic: str, show: bool = True):
        self.topic = topic
        self.show = show and sys.stderr.isatty()
        self._lock = threading.Lock()
        self._sources: Dict[str, str] = {}  # source -> status
        self._start_time = time.time()
        self._line_count = 0

    def _write(self, text: str) -> None:
        """Write to stderr."""
        if self.show:
            sys.stderr.write(text)
            sys.stderr.flush()

    def _clear_lines(self, n: int) -> None:
        """Clear n lines above cursor."""
        if self.show and n > 0:
            for _ in range(n):
                sys.stderr.write("\033[1A\033[2K")

    def start(self) -> None:
        """Start the progress display."""
        if not self.show:
            return
        self._write(f"\n{BOLD}Researching: {self.topic}{NC}\n")
        self._write(f"{DIM}Starting pipeline...{NC}\n")
        self._line_count = 2

    def update_source(self, source: str, status: str) -> None:
        """Update status for a specific source."""
        with self._lock:
            self._sources[source] = status
            if self.show:
                self._refresh()

    def source_done(self, source: str, count: int) -> None:
        """Mark a source as complete."""
        with self._lock:
            self._sources[source] = f"done ({count} items)"
            if self.show:
                self._refresh()

    def source_error(self, source: str, error: str) -> None:
        """Mark a source as failed."""
        with self._lock:
            self._sources[source] = f"error: {error[:50]}"
            if self.show:
                self._refresh()

    def _refresh(self) -> None:
        """Redraw the progress display."""
        self._clear_lines(self._line_count)
        elapsed = time.time() - self._start_time

        lines = [f"\n{BOLD}Researching: {self.topic}{NC}\n"]
        for source, status in sorted(self._sources.items()):
            if "done" in status:
                icon = f"{GREEN}✓{NC}"
            elif "error" in status:
                icon = f"{YELLOW}✗{NC}"
            elif "fetching" in status or "searching" in status:
                icon = f"{CYAN}⋯{NC}"
            else:
                icon = f"{DIM}○{NC}"
            lines.append(f"  {icon} {source:15s} {status}\n")

        lines.append(f"{DIM}  Elapsed: {elapsed:.1f}s{NC}\n")
        self._line_count = len(lines)
        self._write("".join(lines))

    def show_complete(
        self,
        source_counts: Dict[str, int],
        total_items: int,
        total_clusters: int,
        cache_hits: int = 0,
        new_findings: int = 0,
    ) -> None:
        """Show completion summary."""
        if not self.show:
            return

        elapsed = time.time() - self._start_time
        self._clear_lines(self._line_count)

        self._write(f"\n{GREEN}✓ Research complete in {elapsed:.1f}s{NC}\n")
        self._write(f"  {total_items} items, {total_clusters} clusters")

        if cache_hits > 0:
            self._write(f", {cache_hits} cache hits")
        if new_findings > 0:
            self._write(f", {new_findings} new")

        self._write("\n  Sources: ")
        active = [f"{s} ({c})" for s, c in sorted(source_counts.items()) if c > 0]
        self._write(", ".join(active) if active else "none")
        self._write("\n\n")

    def end_processing(self) -> None:
        """End processing phase."""
        pass  # show_complete handles this
