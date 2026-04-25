"""F19 · ProviderPresets — GLM / MiniMax / OpenAI / custom preset resolver.

Feature design §IC ProviderPresets.resolve / validate_base_url:
    * resolve(): builtin table → ``ProviderPreset``.
    * validate_base_url(): strict hostname whitelist + subdomain (``endswith(".<domain>")``)
      + reject private / loopback / link-local IPs for provider=custom
      (FR-021 AC-3 / ATS L182 SSRF defense).
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

from .errors import ProviderPresetError, SsrfBlockedError
from .models import ProviderLiteral, ProviderPreset


_WHITELIST_DOMAINS = (
    "open.bigmodel.cn",
    "api.minimax.chat",
    "api.openai.com",
)


_PRESETS: dict[str, ProviderPreset] = {
    "glm": ProviderPreset(
        name="glm",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        default_model="glm-4-plus",
        api_key_user_slot="glm",
    ),
    "minimax": ProviderPreset(
        name="minimax",
        base_url="https://api.minimax.chat/v1/",
        default_model="MiniMax-M2.7-highspeed",
        api_key_user_slot="minimax",
        # Wave 3 (FR-021 AC-4): MiniMax OpenAI-compat endpoint does NOT reliably
        # honour response_format=json_schema strict mode — capability bit OFF
        # so ClassifierService drops to prompt-only JSON suffix + tolerant parse.
        supports_strict_schema=False,
    ),
    "openai": ProviderPreset(
        name="openai",
        base_url="https://api.openai.com/v1/",
        default_model="gpt-4o-mini",
        api_key_user_slot="openai",
    ),
    "custom": ProviderPreset(
        name="custom",
        base_url="",
        default_model="",
        api_key_user_slot="custom",
    ),
}


class ProviderPresets:
    """Resolver + SSRF validator for OpenAI-compat providers."""

    def list(self) -> list[ProviderPreset]:
        return list(_PRESETS.values())

    def resolve(self, provider: str) -> ProviderPreset:
        try:
            return _PRESETS[provider]
        except KeyError as exc:
            raise ProviderPresetError(f"unknown provider: {provider!r}") from exc

    # ------------------------------------------------------------------
    # SSRF defense (FR-021 AC-3 / ATS L89/L182)
    # ------------------------------------------------------------------
    def validate_base_url(self, base_url: str) -> None:
        """Hostname whitelist + private-range defense (strict matching).

        Raises ``SsrfBlockedError`` on policy violation.
        """
        parsed = urlparse(base_url)
        scheme = (parsed.scheme or "").lower()
        hostname = (parsed.hostname or "").lower()

        if not scheme or not hostname:
            raise SsrfBlockedError(f"invalid base_url (scheme/host missing): {base_url!r}")

        # Whitelist hostname + subdomains (strict).
        for domain in _WHITELIST_DOMAINS:
            if hostname == domain or hostname.endswith("." + domain):
                if scheme != "https":
                    raise SsrfBlockedError(
                        f"whitelist domain {domain!r} requires https, got {scheme!r}"
                    )
                return

        # Off-whitelist: custom endpoint — reject private / loopback / link-local
        # and enforce https unless explicitly loopback (test scenario).
        try:
            ip = ipaddress.ip_address(hostname)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
            ):
                raise SsrfBlockedError(
                    f"ip {hostname!r} falls into private/loopback/link-local range"
                )
        except ValueError:
            # Hostname is a DNS name, not a raw IP.
            pass

        if scheme != "https":
            raise SsrfBlockedError(
                f"custom base_url must use https, got scheme={scheme!r} for host={hostname!r}"
            )


__all__ = ["ProviderPresets", "ProviderLiteral"]
