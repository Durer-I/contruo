"""Liveblocks room parsing."""

import uuid

from app.services.liveblocks_service import parse_collaboration_room


def test_parse_collaboration_room_valid():
    oid = uuid.uuid4()
    pid = uuid.uuid4()
    room = f"contruo:{oid}:{pid}"
    parsed = parse_collaboration_room(room)
    assert parsed == (oid, pid)


def test_parse_collaboration_room_invalid():
    assert parse_collaboration_room("wrong") is None
    assert parse_collaboration_room("contruo:bad:uuid") is None
