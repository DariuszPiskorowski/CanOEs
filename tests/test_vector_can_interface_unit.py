import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from can_channel_manager import CANChannelManager
from vector_can_interface import CANMessage, VectorCANInterface


class DummyDLL:
    def __init__(self, status=0):
        self.status = status


def test_load_dll_requires_windows_without_loader(monkeypatch):
    vci = VectorCANInterface(dll_path="does_not_matter")
    with pytest.raises(RuntimeError):
        vci.load_dll()


def test_load_dll_uses_custom_loader():
    loader_calls = []

    def loader(path):
        loader_calls.append(path)
        return DummyDLL()

    vci = VectorCANInterface(dll_loader=loader)
    assert vci.load_dll() is True
    assert isinstance(vci.dll, DummyDLL)
    assert loader_calls == [vci.dll_path]


def test_can_message_rejects_too_long_payload():
    with pytest.raises(ValueError):
        CANMessage(id=0x1, data=b"012345678")


def test_can_message_requires_matching_dlc():
    with pytest.raises(ValueError):
        CANMessage(id=0x1, data=b"\x01\x02", dlc=1)


def test_can_message_rejects_standard_id_overflow():
    with pytest.raises(ValueError):
        CANMessage(id=0x1ABCDEF, data=b"\x01")


def test_can_message_accepts_extended_id_with_flag():
    msg = CANMessage(id=0x1ABCDEF, data=b"\x01", is_extended=True)
    assert msg.id == 0x1ABCDEF


def test_can_message_allows_remote_frame_with_dlc_and_no_payload():
    msg = CANMessage(id=0x100, data=b"", dlc=8, is_remote=True)
    assert msg.dlc == 8
    assert msg.data == b""


def test_can_message_rejects_remote_frame_with_payload_or_invalid_dlc():
    with pytest.raises(ValueError):
        CANMessage(id=0x100, data=b"\x01", is_remote=True)

    with pytest.raises(ValueError):
        CANMessage(id=0x100, data=b"", dlc=9, is_remote=True)


def test_can_message_coerces_bytearray_and_validates_type():
    payload = bytearray([0x01, 0x02])
    msg = CANMessage(id=0x10, data=payload)
    assert isinstance(msg.data, bytes)
    assert msg.data == b"\x01\x02"


def test_can_channel_manager_listen_messages_handles_limit():
    calls = []

    class FakeInterface:
        def __init__(self):
            self.is_on_bus = True
            self._call_count = 0

        def receive_message(self, timeout_ms=100):
            if self._call_count == 0:
                self._call_count += 1
                return CANMessage(id=0x1, data=b"\x01")
            return None

    manager = CANChannelManager(
        can_interface=FakeInterface(),
        input_func=lambda prompt="": "",
        output_func=lambda *args, **kwargs: None,
        sleep_func=lambda *_: None,
    )

    manager.listen_messages(max_messages=1, message_handler=lambda msg: calls.append(msg))

    assert len(calls) == 1
    assert calls[0].id == 0x1
