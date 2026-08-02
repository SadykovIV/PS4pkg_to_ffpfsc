from __future__ import annotations

import json

import pytest

from ps4ffpsc.sfo import (
    SfoError,
    build_param_json,
    choose_title,
    make_sfo,
    parse_sfo_bytes,
    validate_shadowmount_param_json,
)


def test_sfo_round_trip_and_localized_title() -> None:
    source = {
        "APP_VER": "01.23",
        "CATEGORY": "gd",
        "CONTENT_ID": "EP9000-CUSA12345_00-ABCDEFGHIJKLMNOP",
        "SYSTEM_VER": 0x02508000,
        "TITLE_08": "Игра",
        "TITLE_ID": "CUSA12345",
    }
    parsed = parse_sfo_bytes(make_sfo(source))
    assert parsed == source
    assert choose_title(parsed, preferred_index=8) == "Игра"


def test_choose_title_prefers_us_english_before_other_localized_titles() -> None:
    parsed = parse_sfo_bytes(
        make_sfo(
            {
                "TITLE_00": "日本語タイトル",
                "TITLE_01": "English title",
                "TITLE_08": "Русское название",
                "TITLE_ID": "CUSA12345",
            }
        )
    )

    assert choose_title(parsed) == "English title"
    assert choose_title(parsed, preferred_index=8) == "Русское название"


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"not a psf",
        make_sfo({"TITLE_ID": "CUSA12345"})[:24],
    ],
)
def test_corrupt_sfo_rejected(data: bytes) -> None:
    with pytest.raises(SfoError):
        parse_sfo_bytes(data)


def test_param_json_is_deterministic_unicode_utf8_without_bom() -> None:
    first = build_param_json("CUSA12345", "Путешествие ™")
    second = build_param_json("CUSA12345", "Путешествие ™")
    assert first == second
    assert not first.startswith(b"\xef\xbb\xbf")
    parsed = validate_shadowmount_param_json(first, "CUSA12345")
    assert parsed["localizedParameters"]["en-US"]["titleName"] == "Путешествие ™"


def test_param_json_uses_the_minimal_native_ps4_projection() -> None:
    generated = build_param_json("CUSA12345", "Game")

    assert json.loads(generated) == {
        "localizedParameters": {
            "defaultLanguage": "en-US",
            "en-US": {"titleName": "Game"},
        },
        "titleId": "CUSA12345",
        "titleName": "Game",
    }


def test_nonzero_sfo_user_parameters_are_mirrored_for_image_compatibility() -> None:
    generated = build_param_json(
        "CUSA13801",
        "Sekiro™: Shadows Die Twice",
        sfo_values={
            "USER_DEFINED_PARAM_1": 2,
            "USER_DEFINED_PARAM_2": 0,
            "USER_DEFINED_PARAM_3": 545259552,
        },
    )

    payload = json.loads(generated)
    assert payload["userDefinedParam1"] == 2
    assert payload["userDefinedParam3"] == 545259552
    assert "userDefinedParam2" not in payload


def test_param_json_title_mismatch_rejected() -> None:
    with pytest.raises(ValueError, match="mismatch"):
        validate_shadowmount_param_json(build_param_json("CUSA12345", "Game"), "CUSA54321")


def test_param_json_preserves_existing_game_metadata() -> None:
    original = json.dumps(
        {
            "gameIntent": {
                "permittedIntents": [{"intentType": "joinSession"}],
            }
        }
    ).encode()

    generated = build_param_json("CUSA16746", "It Takes Two", original)
    parsed = validate_shadowmount_param_json(generated, "CUSA16746")

    assert parsed["gameIntent"]["permittedIntents"] == [
        {"intentType": "joinSession"}
    ]
    assert parsed["titleName"] == "It Takes Two"


@pytest.mark.parametrize("original", [b"not json", b"\xef\xbb\xbfbad"])
def test_invalid_existing_param_json_is_safely_replaced(original: bytes) -> None:
    generated = build_param_json("CUSA12345", "Game", original)
    parsed = validate_shadowmount_param_json(generated, "CUSA12345")
    assert parsed["titleName"] == "Game"
