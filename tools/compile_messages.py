from __future__ import annotations

import ast
import struct
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCALE_DIR = PROJECT_ROOT / "locale"


def _unquote(value: str) -> str:
    return ast.literal_eval(value)


def parse_po(path: Path) -> dict[str, str]:
    messages: dict[str, str] = {}
    msgid_parts: list[str] | None = None
    msgstr_parts: list[str] | None = None
    section: str | None = None
    is_fuzzy = False

    def commit() -> None:
        nonlocal msgid_parts
        nonlocal msgstr_parts
        nonlocal section
        nonlocal is_fuzzy

        if msgid_parts is None or msgstr_parts is None:
            return
        msgid = "".join(msgid_parts)
        msgstr = "".join(msgstr_parts)
        if not is_fuzzy:
            messages[msgid] = msgstr
        msgid_parts = None
        msgstr_parts = None
        section = None
        is_fuzzy = False

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("#,") and "fuzzy" in line:
            is_fuzzy = True
            continue
        if line.startswith("#"):
            continue
        if not line:
            commit()
            continue
        if line.startswith("msgctxt"):
            raise ValueError(f"{path}: msgctxt is not supported.")
        if line.startswith("msgid_plural"):
            raise ValueError(f"{path}: plural entries are not supported.")
        if line.startswith("msgstr["):
            raise ValueError(f"{path}: plural translations are not supported.")
        if line.startswith("msgid"):
            commit()
            msgid_parts = [_unquote(line[len("msgid") :].strip())]
            msgstr_parts = []
            section = "msgid"
            continue
        if line.startswith("msgstr"):
            if msgid_parts is None:
                raise ValueError(f"{path}: msgstr found before msgid.")
            msgstr_parts = [_unquote(line[len("msgstr") :].strip())]
            section = "msgstr"
            continue
        if line.startswith('"'):
            if section == "msgid" and msgid_parts is not None:
                msgid_parts.append(_unquote(line))
                continue
            if section == "msgstr" and msgstr_parts is not None:
                msgstr_parts.append(_unquote(line))
                continue
        raise ValueError(f"{path}: unable to parse line: {raw_line}")

    commit()
    return messages


def build_mo(messages: dict[str, str]) -> bytes:
    keys = sorted(messages)
    ids = [key.encode("utf-8") for key in keys]
    values = [messages[key].encode("utf-8") for key in keys]

    count = len(keys)
    header_size = 7 * 4
    key_table_offset = header_size
    value_table_offset = key_table_offset + count * 8
    string_offset = value_table_offset + count * 8

    key_entries: list[tuple[int, int]] = []
    value_entries: list[tuple[int, int]] = []
    key_blob = bytearray()
    value_blob = bytearray()

    current_key_offset = string_offset
    for msgid in ids:
        key_entries.append((len(msgid), current_key_offset))
        key_blob.extend(msgid)
        key_blob.append(0)
        current_key_offset += len(msgid) + 1

    current_value_offset = string_offset + len(key_blob)
    for msgstr in values:
        value_entries.append((len(msgstr), current_value_offset))
        value_blob.extend(msgstr)
        value_blob.append(0)
        current_value_offset += len(msgstr) + 1

    output = bytearray()
    output.extend(
        struct.pack(
            "Iiiiiii",
            0x950412DE,
            0,
            count,
            key_table_offset,
            value_table_offset,
            0,
            0,
        )
    )
    for length, offset in key_entries:
        output.extend(struct.pack("ii", length, offset))
    for length, offset in value_entries:
        output.extend(struct.pack("ii", length, offset))
    output.extend(key_blob)
    output.extend(value_blob)
    return bytes(output)


def compile_po(path: Path) -> Path:
    if path.suffix != ".po":
        raise ValueError(f"{path}: expected a .po file.")

    mo_path = path.with_suffix(".mo")
    mo_path.write_bytes(build_mo(parse_po(path)))
    return mo_path


def main(argv: list[str] | None = None) -> int:
    args = list(argv) if argv is not None else sys.argv[1:]
    targets = [Path(argument) for argument in args] if args else sorted(LOCALE_DIR.glob("*/LC_MESSAGES/*.po"))
    for target in targets:
        mo_path = compile_po(target)
        print(f"Compiled {target} -> {mo_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
