"""Unit tests for :mod:`auxd_api.providers.errors` (T052)."""

from __future__ import annotations

import pytest

from auxd_api.providers.errors import (
    ProviderAuthRevoked,
    ProviderError,
    ProviderNotFound,
    ProviderRateLimited,
    ProviderUnavailable,
)


class TestProviderErrorHierarchy:
    @pytest.mark.parametrize(
        "subclass",
        [
            ProviderUnavailable,
            ProviderRateLimited,
            ProviderAuthRevoked,
            ProviderNotFound,
        ],
    )
    def test_all_subclasses_inherit_from_base(self, subclass: type[ProviderError]) -> None:
        assert issubclass(subclass, ProviderError)
        assert issubclass(subclass, Exception)

    def test_concrete_subclasses_can_be_caught_via_base(self) -> None:
        with pytest.raises(ProviderError):
            raise ProviderUnavailable("boom")
        with pytest.raises(ProviderError):
            raise ProviderRateLimited("rate limit")
        with pytest.raises(ProviderError):
            raise ProviderAuthRevoked("revoked")
        with pytest.raises(ProviderError):
            raise ProviderNotFound("missing")

    def test_subclasses_do_not_catch_each_other(self) -> None:
        """ProviderUnavailable should NOT catch ProviderRateLimited and vice versa."""
        with pytest.raises(ProviderRateLimited):
            try:
                raise ProviderRateLimited("rate limit")
            except ProviderUnavailable:  # pragma: no cover - intentional miss
                pytest.fail("ProviderUnavailable should not catch ProviderRateLimited")


class TestProviderField:
    def test_provider_field_defaults_none(self) -> None:
        exc = ProviderUnavailable("boom")
        assert exc.provider is None

    def test_provider_field_set(self) -> None:
        exc = ProviderRateLimited("rate limit", provider="musicbrainz")
        assert exc.provider == "musicbrainz"
        assert str(exc) == "rate limit"

    def test_repr_includes_provider_when_set(self) -> None:
        exc = ProviderUnavailable("boom", provider="discogs")
        rendered = repr(exc)
        assert "ProviderUnavailable" in rendered
        assert "discogs" in rendered
        assert "boom" in rendered

    def test_repr_omits_provider_when_unset(self) -> None:
        exc = ProviderNotFound("missing")
        rendered = repr(exc)
        assert "ProviderNotFound" in rendered
        assert "provider=" not in rendered

    def test_empty_message_repr(self) -> None:
        exc = ProviderError()
        rendered = repr(exc)
        assert "<no message>" in rendered
