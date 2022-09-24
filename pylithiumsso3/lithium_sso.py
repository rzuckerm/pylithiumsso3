"""
Python implementation of ``lithium_sso.php``, which has the following copyright:

    Copyright (C) 2006 Lithium Technologies, Inc.
    Emeryville, California, U.S.A.  All Rights Reserved.

    This software is the  confidential and proprietary information
    of  Lithium  Technologies,  Inc.  ("Confidential Information")
    You shall not disclose such Confidential Information and shall
    use  it  only in  accordance  with  the terms of  the  license
    agreement you entered into with Lithium.

Example Usage:

.. code-block:: python

    # Secret SSO key (128-bit or 256-bit) provided by Lithium
    sso_key = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"

    # (Optional) Secret PrivacyGuard key (128-bit or 256-bit) *NOT* to be shared with Lithium
    pg_key = ""

    # Initialize Lithium SSO Client
    from pylithiumsso3.lithium_sso import LithiumSSO

    lithium = LithiumSSO("example", ".example.com", sso_key)

    # (Optional) Additional user profile settings to pass to Lithium
    settings = {}

    # Example: Set the user's homepage URL
    settings["profile.url_homepage"] = "http://myhomepage.example.com"

    # Example: Grant the user the Moderator role
    settings["roles.grant"] = "Moderator"

    # Create the authentication token
    req_user_agent = "Mozilla/5.0"
    req_referer = "example.com"
    req_remote_addr = "10.11.12.13"
    li_token = lithium.get_auth_token_value(
        "1000", "myscreenname", "myemail@example.com", settings,
        req_user_agent, req_referer, req_remote_addr
    )

    # The token can either be passed directly through HTTP GET/POST, or through cookies.

    # If PrivacyGuard is enabled, you must initialize the PrivacyGuard key, and call the
    # encryption function for each token which requires PG encryption. Example:
    lithium.init_smr(pg_hex_key)
    pg_enc_parameter = lithium.get_smr_field("myemail@example.com");
    li_token = lithium.get_auth_token_value("1000", "myscreenname", pg_enc_parameter, settings)
"""

from typing import Optional, Dict, Any
import random
import string
import binascii
import time
import zlib
import base64
import re

from Crypto.Cipher import AES
from Crypto.Util import Padding


class LithiumSSO:
    """
    :ivar client_id: The client or community id to create an SSO token for
    :ivar client_domain: The domain name for this token, used when transporting via cookies
        (e.g., ".lithium.com")
    :ivar server_id: The server ID
    :ivar sso_key: The 128-bit or 256-bit secret key bytes
    :ivar pg_key: The 128-bit or 256-bit PrivacyGuard key bytes
    :ivar tsid: The timestamp ID

    :param client_id: The client or community id to create an SSO token for
    :param client_domain: The domain name for this token, used when transporting via cookies (e.g.,
        ".lithium.com")
    :param sso_hex_key: The 128-bit or 256-bit secret key, represented in hexadecimal
    :param server_id: The server id
    :raises: ValueError if invalid client ID, client domain, or SSO key
    """

    # Constants
    VALID_KEY_LENGTHS = (16, 32)
    LITHIUM_SEPARATOR = "|"
    LITHIUM_SEPARATOR_REPLACE = "-"
    LITHIUM_VERSION = "LiSSOv1.5"
    VALID_IV_CHARS = string.digits + string.ascii_letters
    IV_LEN = 16
    DEFAULT_SERVER_VAR_VALUE = " "
    _CRYPTO_PATTERN1 = "+/="
    _CRYPTO_PATTERN2 = "-_."
    ENCRYPT_REPLACE = str.maketrans(_CRYPTO_PATTERN1, _CRYPTO_PATTERN2)
    DECRYPT_REPLACE = str.maketrans(_CRYPTO_PATTERN2, _CRYPTO_PATTERN1)
    TOKEN_KEYS = [
        "version",
        "server_id",
        "tsid",
        "timestamp",
        "req_user_agent",
        "req_referer",
        "req_remote_addr",
        "client_domain",
        "client_id",
        "unique_id",
        "login",
        "email",
    ]

    # Allowed pattern for decoding
    DECODE_PATTERN = re.compile(
        f"^~2[{re.escape(VALID_IV_CHARS)}]{{{IV_LEN}}}~[0-9A-Za-z{re.escape(_CRYPTO_PATTERN2)}]*$"
    )

    def __init__(
        self, client_id: str, client_domain: str, sso_hex_key: str, server_id: str = ""
    ):
        if not client_id:
            raise ValueError(
                "Could not initialize Lithium SSO Client: Client id required"
            )

        if not client_domain:
            raise ValueError(
                "Could not initialize Lithium SSO Client: Client domain required"
            )

        self.client_id: str = client_id
        self.client_domain: str = client_domain
        self.server_id: str = self._parse_server_id(server_id)
        self.sso_key: bytes = self._parse_key(sso_hex_key, "SSO")
        self.pg_key: bytes = b""
        self.tsid: int = int(time.time()) * 1000

    def get_auth_token_value(
        self,
        unique_id: str,
        login: str,
        email: str,
        settings: Optional[dict] = None,
        req_user_agent: str = "",
        req_referer: str = "",
        req_remote_addr: str = "",
    ) -> str:
        """
        Returns a Lithium authentication token for the given user parameters

        :param unique_id: A non-changable id used to uniquely identify this user globally.
            This should be an non-reusable integer or other identifier. Email addresses can be
            used, but are not recommended as this value cannot be changed.
        :param login: The login name or screen name for this user.  This is usually a publicly
            visible field, so should not contain personally identifiable information.
        :param email: The email address for this user.
        :param settings: Profile settings where the key is the setting name and the value is
            the setting value. Examples of settings include:

            * roles.grant = Moderator (grants the Moderator role to user)
            * profile.name_first = John (sets first name to John)

            Contact Lithium for a list of valid settings.
        :param req_user_agent: User agent from request. Used for security identification
            information.
        :param req_referer: Referrer from request. Used for security identification information.
        :param req_remote_addr: Remote address from request. Used for security identification
            information.
        :return: the encrypted authentication token
        :raises: ValueError if invalid unique ID, login, or email
        """

        if not unique_id:
            raise ValueError("Could not create Lithium token: Unique id required")

        if not login:
            raise ValueError("Could not create Lithium token: Login name required")

        if not email:
            raise ValueError("Could not create Lithium token: Email address required")

        self.tsid += 1
        timestamp = int(time.time()) * 1000
        settings = settings or {}
        values = (
            [
                "Li",
                self.LITHIUM_VERSION,
                self.server_id,
                f"{self.tsid}",
                f"{timestamp}",
                self._get_server_value(req_user_agent),
                self._get_server_value(req_referer),
                self._get_server_value(req_remote_addr),
                self.client_domain,
                self.client_id,
                unique_id,
                login,
                email,
            ]
            + [f"{key}={value}" for key, value in settings.items()]
            + ["iL"]
        )
        value = self.LITHIUM_SEPARATOR.join(map(self._get_token_safe_string, values))

        return self._encode(value, self.sso_key)

    @staticmethod
    def _encode(value: str, key: bytes) -> str:
        """
        Returns an encrypted representation of the specified string.

        :param value: the string to encode
        :param key: the key to use
        :return: the encoded string
        """

        encoded_bytes = value.encode()

        # gzip compress
        encoded_bytes = zlib.compress(encoded_bytes)

        # AES encrypt
        iv = LithiumSSO._get_random_iv(LithiumSSO.IV_LEN)
        cipher = AES.new(key, mode=AES.MODE_CBC, IV=iv)
        encoded_bytes = cipher.encrypt(Padding.pad(encoded_bytes, LithiumSSO.IV_LEN))

        # URL base64 encode
        encoded_bytes = base64.b64encode(encoded_bytes)
        encoded_str = encoded_bytes.decode().translate(LithiumSSO.ENCRYPT_REPLACE)

        # Version and IV Prefix
        return f"~2{iv.decode()}~{encoded_str}"

    def decode_auth_token_value(self, value: str) -> Dict[str, Any]:
        """
        Returns decoded and parsed Lithium authentication token

        :param value: Lithium authentication token to decode
        :return: Dictionary containing the following:

            * "version" - Lithium token version

            * "server_id" - The server ID

            * "tsid" - The timestamp ID

            * "timestamp" - The timestamp of the request

            * "req_user_agent" - User agent from request

            * "req_referer" - Referrer from request

            * "req_remote_addr" - Remote address from request

            * "client_domain" - The domain name for this token, used when transporting via
              cookies (e.g., ".lithium.com")

            * "client_id" - The client or community id to create an SSO token for

            * "unique_id" - A non-changable id used to uniquely identify this user globally

            * "login" - The login name or screen name for this user

            * "email" - The email address for this user

            * "settings" - Profile settings where the key is the setting name and the value is
              the setting value
        :raises: ValueError if decoded value of Lithium authentication token is invalid
        """

        decoded_value = LithiumSSO._decode(value, self.sso_key)
        items = decoded_value.split(self.LITHIUM_SEPARATOR)
        if (
            len(items) < 2 + len(self.TOKEN_KEYS)
            or items[0] != "Li"
            or items[-1] != "iL"
        ):
            raise ValueError("Could not decode Lithium token: Invalid format")

        # Parse non-settings items (strip off "Li" and "iL"
        parsed_items: Dict[str, Any] = {}
        items = items[1:-1]
        for key, item in zip(self.TOKEN_KEYS, items):
            if key.startswith("req_") and item == self.DEFAULT_SERVER_VAR_VALUE:
                item = ""

            parsed_items[key] = item

        # Parse settings items
        settings = {}
        for item in items[len(self.TOKEN_KEYS) :]:
            settings_key, _, settings_value = item.partition("=")
            settings[settings_key] = settings_value

        parsed_items["settings"] = settings
        return parsed_items

    @staticmethod
    def _decode(value: str, key: bytes) -> str:
        """
        Returns an decrypted representation of the specified string.

        :param value: the string to decode
        :param key: the key to use
        :return: the decoded string
        :raises: ValueError if invalid string
        """

        if not LithiumSSO.DECODE_PATTERN.match(value):
            raise ValueError("Could not decode Lithium token: Invalid format")

        parts = value.split("~")
        iv = parts[1][1:].encode()
        decoded_str = parts[2]

        # URL base64 decode
        decoded_str = decoded_str.translate(LithiumSSO.DECRYPT_REPLACE)
        decoded_bytes = base64.b64decode(decoded_str)

        # AES decrypt
        cipher = AES.new(key, mode=AES.MODE_CBC, IV=iv)
        decoded_bytes = Padding.unpad(cipher.decrypt(decoded_bytes), LithiumSSO.IV_LEN)

        # zlib decompress
        decoded_bytes = zlib.decompress(decoded_bytes)
        return decoded_bytes.decode()

    @staticmethod
    def _parse_key(hex_key: str, key_type: str) -> bytes:
        """
        Parse encryption key

        :param hex_key: Encryption key in hexadecimal
        :param key_type: Key type to use in error message (e.g., "SSO")
        :return: Encyption key
        :value: ValueError if key is not 128-bit or 256-bit
        """

        if not hex_key:
            raise ValueError(f"{key_type} Hex key required")

        key = binascii.unhexlify(hex_key)
        if len(key) not in LithiumSSO.VALID_KEY_LENGTHS:
            raise ValueError(f"{key_type} key must be 128-bit or 256-bit in length")

        return key

    @staticmethod
    def _get_random_iv(length: int) -> bytes:
        """
        Returns a random initialization vector for AES with the specified length.
        The returned string is URL-safe.

        :param length: the length of the IV to return, in bytes
        :return: string the IV in string form
        """

        return "".join(
            random.choice(LithiumSSO.VALID_IV_CHARS) for _ in range(length)
        ).encode("ascii")

    @staticmethod
    def _get_token_safe_string(value: str) -> str:
        """
        Returns a token-safe representation of the specified string. Used to ensure that
        the token separator is not used inside a token.

        :param value: the string to return a token-safe representation for
        :return: String the token-safe representation of $string
        """

        return value.replace(
            LithiumSSO.LITHIUM_SEPARATOR, LithiumSSO.LITHIUM_SEPARATOR_REPLACE
        )

    def init_smr(self, pg_hex_key: str):
        """
        PrivacyGuard key init

        :param pg_hex_key: The 128-bit or 256-bit PrivacyGuard key, represented in hexadecimal
        """

        self.pg_key = self._parse_key(pg_hex_key, "PG")

    def get_smr_field(self, value: str) -> str:
        """
        PrivacyGuard parameter encrypt

        :param value: the string to return a PrivacyGuard encrypted token for
        :return: the PrivacyGuard encrypted value of string or "" if no key set
        """

        if self.pg_key:
            return self._encode(value, self.pg_key)

        return ""

    @staticmethod
    def _get_server_value(value: str) -> str:
        """
        Get server value

        :param value: Server value
        :return: Server value or " " if empty
        """

        return value or LithiumSSO.DEFAULT_SERVER_VAR_VALUE

    @staticmethod
    def _parse_server_id(server_id: str = "") -> str:
        """
        Parse server ID

        :param server_id: Server ID
        :return: Converted server ID
        """

        server_id = server_id.strip()
        if server_id:
            server_id = LithiumSSO._get_token_safe_string(server_id)
        else:
            server_id = "34"  # This is the default value that lithium_sso.php uses

        hex_string = _get_random_hex_string(32)
        return f"{server_id}-{hex_string}"


def _get_random_hex_string(length: int) -> str:
    return "".join(f"{random.randint(0, 255):02X}" for _ in range(0, length, 2))
