"""Domain data structures."""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class RepoTask:
    """A single repo execution task parsed from REPO-GROUPS.md."""

    repo_full: str
    repo_name: str
    group_folder: str
    group_name: str
    highland: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {
            "repo_full": self.repo_full,
            "repo_name": self.repo_name,
            "group_folder": self.group_folder,
            "group_name": self.group_name,
            "highland": self.highland,
        }

