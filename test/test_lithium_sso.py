from unittest.mock import patch, ANY

import pytest

from pylithiumsso3 import lithium_sso
from pylithiumsso3.lithium_sso import LithiumSSO


@pytest.mark.parametrize(
    "client_id,client_domain,sso_hex_key,expected_error",
    [
        ("", ".blah", "0123456789ABCDEF123456789ABCDEF0", "Client id required"),
        ("some-id", "", "0123456789ABCDEF123456789ABCDEF0", "Client domain required"),
        ("some-id", ".some-domain", "", "SSO Hex key required"),
        (
            "some-id",
            ".some-domain",
            "012345",
            "SSO key must be 128-bit or 256-bit in length",
        ),
    ],
)
def test_constructor_error(client_id, client_domain, sso_hex_key, expected_error):
    with pytest.raises(ValueError) as e:
        LithiumSSO(client_id, client_domain, sso_hex_key)

    assert expected_error in e.value.args[0]


@pytest.mark.parametrize(
    "test_config",
    [
        {
            "client_id": "some-client",
            "client_domain": ".some-domain",
            "sso_hex_key": "0123456789ABCDEF123456789ABCDEF0",
            "time": 123456789.0123,
            "expected_sso_key": (
                b"\x01\x23\x45\x67\x89\xab\xcd\xef\x12\x34\x56\x78\x9a\xbc\xde\xf0"
            ),
            "expected_server_id_prefix": "34",
            "expected_tsid": 123456789000,
        },
        {
            "client_id": "other-client",
            "client_domain": ".some-other-domain",
            "sso_hex_key": "0123456789ABCDEF123456789ABCDEF0123456789ABCDEF023456789ABCDEF01",
            "server_id": "    ",
            "time": 56789012345.678,
            "expected_sso_key": (
                b"\x01\x23\x45\x67\x89\xab\xcd\xef\x12\x34\x56\x78\x9a\xbc\xde\xf0"
                b"\x12\x34\x56\x78\x9a\xbc\xde\xf0\x23\x45\x67\x89\xab\xcd\xef\x01"
            ),
            "expected_server_id_prefix": "34",
            "expected_tsid": 56789012345000,
        },
        {
            "client_id": "this-client",
            "client_domain": ".this-domain",
            "sso_hex_key": "123456789ABCDEF023456789ABCDEF01",
            "server_id": "  hi-mom  ",
            "time": 872389729.94549,
            "expected_sso_key": (
                b"\x12\x34\x56\x78\x9a\xbc\xde\xf0\x23\x45\x67\x89\xab\xcd\xef\x01"
            ),
            "expected_server_id_prefix": "hi-mom",
            "expected_tsid": 872389729000,
        },
        {
            "client_id": "my-client",
            "client_domain": ".my-domain",
            "sso_hex_key": "FEDCBA9876543210EDCBA9876543210F",
            "server_id": "some|stuff",
            "time": 75792837598.73847,
            "expected_sso_key": (
                b"\xfe\xdc\xba\x98\x76\x54\x32\x10\xed\xcb\xa9\x87\x65\x43\x21\x0f"
            ),
            "expected_server_id_prefix": "some-stuff",
            "expected_tsid": 75792837598000,
        },
    ],
)
def test_constructor(test_config, mock_time):
    mock_time.return_value = test_config["time"]

    args = (
        test_config["client_id"],
        test_config["client_domain"],
        test_config["sso_hex_key"],
    )
    if "server_id" in test_config:
        args += (test_config["server_id"],)

    client = LithiumSSO(*args)

    assert client.client_id == test_config["client_id"]
    assert client.client_domain == test_config["client_domain"]
    assert client.sso_key == test_config["expected_sso_key"]

    expected_server_id_prefix = f"{test_config['expected_server_id_prefix']}-"
    assert client.server_id.startswith(expected_server_id_prefix)
    assert len(client.server_id) == len(expected_server_id_prefix) + 32

    assert client.pg_key == b""

    assert client.tsid == test_config["expected_tsid"]


@pytest.mark.parametrize(
    "unique_id,login,email,expected_error",
    [
        ("", "some-login", "some.email@example.com", "Unique id required"),
        ("some-unique-id", "", "some.email@example.com", "Login name required"),
        ("some-unique-id", "some-login", "", "Email address required"),
    ],
)
def test_get_auth_token_value_for_bad_values(unique_id, login, email, expected_error):
    client = LithiumSSO(
        "some-client", ".some.domain", "00112233445566778899AABBCCDDEEFF"
    )
    with pytest.raises(ValueError) as e:
        client.get_auth_token_value(unique_id, login, email)

    assert expected_error in e.value.args[0]


@pytest.mark.parametrize(
    "test_config",
    [
        # No request info or settings
        {
            "client_id": "some-client",
            "client_domain": ".some-domain",
            "sso_hex_key": "0123456789ABCDEF123456789ABCDEF0",
            "unique_id": "12345",
            "login": "jdoe",
            "email": "jane.doe@example.com",
            "times": [12345, 12346],
            "expected_server_id_prefix": "34",
        },
        # Request info and settings
        {
            "client_id": "that-client",
            "client_domain": ".that-domain",
            "sso_hex_key": "123456789ABCDEF023456789ABCDEF01",
            "server_id": "hello|there",
            "unique_id": "foo|bar",
            "login": "baz|quux",
            "email": "ping|pong@example.com",
            "kwargs": {
                "req_user_agent": "that|user|agent",
                "req_referer": "that|referer",
                "req_remote_addr": "that|remote|addr",
                "settings": {
                    "key1": "value1",
                    "key2a|key2b": "value2a|value2b",
                    "key3": "value3",
                },
            },
            "times": [23456, 23457],
            "expected_server_id_prefix": "hello-there",
            "expected_req_user_agent": "that-user-agent",
            "expected_req_referer": "that-referer",
            "expected_req_remote_addr": "that-remote-addr",
            "expected_unique_id": "foo-bar",
            "expected_login": "baz-quux",
            "expected_email": "ping-pong@example.com",
            "expected_settings": [
                "key1=value1",
                "key2a-key2b=value2a-value2b",
                "key3=value3",
            ],
        },
    ],
)
def test_get_auth_token_value(test_config, mock_time, mock_encode):
    mock_encode.return_value = "some-value"
    mock_time.side_effect = test_config["times"]

    args = (
        test_config["client_id"],
        test_config["client_domain"],
        test_config["sso_hex_key"],
    )
    if "server_id" in test_config:
        args += (test_config["server_id"],)

    client = LithiumSSO(*args)
    assert (
        client.get_auth_token_value(
            test_config["unique_id"],
            test_config["login"],
            test_config["email"],
            **test_config.get("kwargs", {}),
        )
        == "some-value"
    )

    mock_encode.assert_called_once_with(ANY, client.sso_key)

    expected_tsid = test_config["times"][0] * 1000 + 1
    assert client.tsid == expected_tsid

    expected_server_id_prefix = f"{test_config['expected_server_id_prefix']}-"
    expected_encode_prefix = "|".join(
        [
            "Li",
            LithiumSSO.LITHIUM_VERSION,  # Version
            expected_server_id_prefix,  # Server ID prefix
        ]
    )
    expected_encode_suffix = "|".join(
        [
            "",
            f"{test_config['times'][0]}001",  # TSID
            f"{test_config['times'][1]}000",  # Timestamp
            test_config.get("expected_req_user_agent", " "),  # User Agent
            test_config.get("expected_req_referer", " "),  # Referer
            test_config.get("expected_req_remote_addr", " "),  # Remote Address
            test_config["client_domain"],  # Client Domain
            test_config["client_id"],  # Client ID
            test_config.get(
                "expected_unique_id", test_config["unique_id"]
            ),  # Unique ID
            test_config.get("expected_login", test_config["login"]),  # Login
            test_config.get("expected_email", test_config["email"]),  # Email
        ]
        + test_config.get("expected_settings", [])  # Settings
        + ["iL"]
    )
    value = mock_encode.call_args_list[0][0][0]
    assert value.startswith(expected_encode_prefix)
    assert value.endswith(expected_encode_suffix)
    assert len(value) == len(f"{expected_encode_prefix}{expected_encode_suffix}") + 32


@pytest.mark.parametrize(
    "value,decoded_value",
    [
        # Wrong number of items
        ("foo", ""),
        # Doesn't start with "Li|"
        ("bar", "|".join(["La"] * (2 + len(LithiumSSO.TOKEN_KEYS)))),
        # Doesn't end with "|iL"
        ("baz", "|".join(["Li"] * (2 + len(LithiumSSO.TOKEN_KEYS)))),
    ],
)
def test_decode_auth_token_value_error(value, decoded_value, mock_decode):
    mock_decode.return_value = decoded_value

    client = LithiumSSO(
        "some-client", ".some-domain", "0123456789ABCDEF123456789ABCDEF0"
    )
    with pytest.raises(ValueError) as e:
        client.decode_auth_token_value(value)

    assert "Invalid format" in e.value.args[0]
    mock_decode.assert_called_once_with(value, client.sso_key)


@pytest.mark.parametrize(
    "decoded_values,expected_value",
    [
        # No request info or settings
        (
            [
                LithiumSSO.LITHIUM_VERSION,  # version
                "some-server",  # server_id
                "56789001",  # tsid
                "67890000",  # timestamp
                " ",  # req_user_agent
                " ",  # req_referer
                " ",  # req_remote_addr
                ".some-domain",  # client_domain
                "some-client",  # client_id
                "some-id",  # unique_id
                "some-login",  # login
                "some-email@example.com",  # email
            ],
            {
                "version": LithiumSSO.LITHIUM_VERSION,
                "server_id": "some-server",
                "tsid": "56789001",
                "timestamp": "67890000",
                "req_user_agent": "",
                "req_referer": "",
                "req_remote_addr": "",
                "client_domain": ".some-domain",
                "client_id": "some-client",
                "unique_id": "some-id",
                "login": "some-login",
                "email": "some-email@example.com",
                "settings": {},
            },
        ),
        # Request info and settings
        (
            [
                LithiumSSO.LITHIUM_VERSION,  # version
                "this-server",  # server_id
                "87654001",  # tsid
                "98765000",  # timestamp
                "this-user-agent",  # req_user_agent
                "this-referer",  # req_referer
                "this-remote-addr",  # req_remote_addr
                ".this-domain",  # client_domain
                "this-client",  # client_id
                "this-id",  # unique_id
                "this-login",  # login
                "this-email@example.com",  # email
                "key1=value1",  # settings
                "key2=value2",
                "key3",
            ],
            {
                "version": LithiumSSO.LITHIUM_VERSION,
                "server_id": "this-server",
                "tsid": "87654001",
                "timestamp": "98765000",
                "req_user_agent": "this-user-agent",
                "req_referer": "this-referer",
                "req_remote_addr": "this-remote-addr",
                "client_domain": ".this-domain",
                "client_id": "this-client",
                "unique_id": "this-id",
                "login": "this-login",
                "email": "this-email@example.com",
                "settings": {"key1": "value1", "key2": "value2", "key3": ""},
            },
        ),
    ],
)
def test_decode_auth_token_value(decoded_values, expected_value, mock_decode):
    mock_decode.return_value = "|".join(["Li"] + decoded_values + ["iL"])

    client = LithiumSSO(
        "some-client", ".some-domain", "0123456789ABCDEF123456789ABCDEF0"
    )
    value = client.decode_auth_token_value("foo")
    assert value == expected_value


@pytest.mark.parametrize(
    "value",
    [
        # Doesn't start with "2~"
        "",
        # IV is too short
        "~2abc~abcdef",
        # IV has invalid characters
        "~2.XYZxyz123qwe#WE~zxczxc",
        # Token has invalid characters
        "~2asfuASFJer8uaiAS~+/as#ijfoiaiasf=",
    ],
)
def test_decode_error(value):
    with pytest.raises(ValueError) as e:
        LithiumSSO._decode(value, b"abcdefghijklmnop")

    assert "Invalid format" in e.value.args[0]


@pytest.mark.parametrize(
    "value,key",
    [
        ("Hello, World!", b"abcdefghijklmnop"),
        ("Goodbye, Universe!", b"abcdefghijklmnopqrstuvwxyz012345"),
    ],
)
def test_encode_and_decode(value, key):
    encoded_value = LithiumSSO._encode(value, key)
    assert encoded_value != value

    decoded_value = LithiumSSO._decode(encoded_value, key)
    assert decoded_value == value


@pytest.mark.parametrize("length", [42, 64])
def test_get_random_iv(length):
    chars = set()
    for _ in range(2000):
        iv = LithiumSSO._get_random_iv(length)
        chars |= set(iv)
        assert len(iv) == length

    assert chars == set(LithiumSSO.VALID_IV_CHARS.encode("ascii"))


def test_get_token_safe_string():
    assert LithiumSSO._get_token_safe_string("foo|bar|blah") == "foo-bar-blah"


@pytest.mark.parametrize(
    "pg_hex_key,expected_error",
    [
        ("", "PG Hex key required"),
        ("12345678", "PG key must be 128-bit or 256-bit in length"),
    ],
)
def test_init_smr_error(pg_hex_key, expected_error):
    client = LithiumSSO("my-client", ".my-domain", "0123456789ABCDEF123456789ABCDEF0")
    with pytest.raises(ValueError) as e:
        client.init_smr(pg_hex_key)

    assert expected_error in e.value.args[0]


@pytest.mark.parametrize(
    "pg_hex_key,expected_pg_key",
    [
        (
            "3456789ABCDEF012456789ABCDEF0123",
            b"\x34\x56\x78\x9a\xbc\xde\xf0\x12\x45\x67\x89\xab\xcd\xef\x01\x23",
        ),
        (
            "456789ABCDEF012356789ABCDEF012346789ABCDEF012345789ABCDEF0123456",
            b"\x45\x67\x89\xab\xcd\xef\x01\x23\x56\x78\x9a\xbc\xde\xf0\x12\x34"
            b"\x67\x89\xab\xcd\xef\x01\x23\x45\x78\x9a\xbc\xde\xf0\x12\x34\x56",
        ),
    ],
)
def test_init_smr(pg_hex_key, expected_pg_key):
    client = LithiumSSO(
        "that-client", ".that-domain", "0123456789ABCDEF123456789ABCDEF0"
    )
    client.init_smr(pg_hex_key)
    assert client.pg_key == expected_pg_key


def test_get_smr_field_no_pg_key():
    client = LithiumSSO(
        "what-client", ".what-domain", "0123456789ABCDEF123456789ABCDEF0"
    )
    assert not client.get_smr_field("foo")


def test_get_smr_field_with_pg_key():
    client = LithiumSSO("who-client", ".who-domain", "0123456789ABCDEF123456789ABCDEF0")
    client.init_smr("123456789ABCDEF023456789ABCDEF01")
    assert client.get_smr_field("bar").startswith("~2")


@pytest.mark.parametrize(
    "length,expected_length",
    [
        (2000, 2000),
        (2001, 2002),
    ],
)
def test_get_random_hex_string(length, expected_length):
    value = lithium_sso._get_random_hex_string(length)
    assert len(value) == expected_length
    assert set(value) == set("0123456789ABCDEF")


@pytest.fixture()
def mock_time():
    with patch("pylithiumsso3.lithium_sso.time.time") as mock:
        yield mock


@pytest.fixture()
def mock_encode():
    with patch("pylithiumsso3.lithium_sso.LithiumSSO._encode") as mock:
        yield mock


@pytest.fixture()
def mock_decode():
    with patch("pylithiumsso3.lithium_sso.LithiumSSO._decode") as mock:
        yield mock
