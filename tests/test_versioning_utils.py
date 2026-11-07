from core.versioning import copy_take, find_take, next_take_number, remove_take


def test_take_metadata_helpers_handle_numeric_and_string_ids():
    takes = [{"take": "1", "path": "one"}, {"take": 3, "path": "three"}]

    assert find_take(takes, 1) == takes[0]
    assert find_take(takes, 2) is None
    assert next_take_number(takes, [2, 5]) == 6
    assert remove_take(takes, 1) == [takes[1]]
    assert takes == [{"take": "1", "path": "one"}, {"take": 3, "path": "three"}]


def test_copy_take_creates_destination_directory(tmp_path):
    source = tmp_path / "source.bin"
    destination = tmp_path / "nested" / "take.bin"
    source.write_bytes(b"take-data")

    copy_take(source, destination)

    assert destination.read_bytes() == b"take-data"
