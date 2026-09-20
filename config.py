import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

COMMANDS_FILE = Path(__file__).resolve().parent / "commands.yaml"


@dataclass
class ArgSpec:
    name: str
    type: str = "str"
    choices: list[str] | None = None
    pattern: str | None = None
    min: int | None = None
    max: int | None = None
    default: str | None = None

    def validate(self, raw: str | None) -> str:
        value = raw if raw is not None else self.default
        if value is None:
            raise ValueError(f"{self.name} is required")
        if self.type == "int":
            try:
                n = int(value)
            except ValueError:
                raise ValueError(f"{self.name} must be a number") from None
            if self.min is not None and n < self.min:
                raise ValueError(f"{self.name} must be >= {self.min}")
            if self.max is not None and n > self.max:
                raise ValueError(f"{self.name} must be <= {self.max}")
            return str(n)
        if self.choices is not None and value not in self.choices:
            raise ValueError(f"{self.name} must be one of: {', '.join(self.choices)}")
        if self.pattern is not None and not re.fullmatch(self.pattern, value):
            raise ValueError(f"{self.name} has an invalid format")
        return value


@dataclass
class Command:
    name: str
    description: str
    type: str  # "script" | "api"
    args: list[ArgSpec] = field(default_factory=list)
    sudo: bool = False
    check: bool = True
    path: str | None = None
    argv: list[str] = field(default_factory=list)
    method: str = "GET"
    url: str | None = None
    auth: dict | None = None

    def build_argv(self, raw_args: list[str]) -> list[str]:
        values = {}
        for i, spec in enumerate(self.args):
            raw = raw_args[i] if i < len(raw_args) else None
            values[spec.name] = spec.validate(raw)
        return [part.format(**values) for part in self.argv]


def _load_command(entry: dict, base_dir: Path) -> Command:
    args = [ArgSpec(**a) for a in entry.get("args", [])]
    cmd = Command(
        name=entry["name"],
        description=entry["description"],
        type=entry["type"],
        args=args,
        sudo=entry.get("sudo", False),
        check=entry.get("check", True),
        path=str((base_dir / entry["path"]).resolve()) if "path" in entry else None,
        argv=[str(part) for part in entry.get("argv", [])],
        method=entry.get("method", "GET"),
        url=entry.get("url"),
        auth=entry.get("auth"),
    )

    declared = {a.name for a in cmd.args}
    used = {name for part in cmd.argv for name in re.findall(r"\{(\w+)\}", part)}
    unknown = used - declared
    if unknown:
        raise ValueError(f"command {cmd.name!r}: argv references undeclared args {unknown}")

    return cmd


def load_commands(path: Path = COMMANDS_FILE) -> list[Command]:
    raw = yaml.safe_load(path.read_text()) or {}
    base_dir = path.parent
    return [_load_command(entry, base_dir) for entry in raw.get("commands", [])]
