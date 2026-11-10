"""The served security headers: the enforced CSP, COOP and CORP in web/public/_headers.

The hashes and the inventory below come from scanning the built site (every inline script, style
and handler, the external origins and the fetch targets). This test reads only the committed
_headers file and the constants below, so it never needs a build and never skips in CI. The daily
job checks the built site against the header (scripts/checks/csp_hashes.py, a warning only).

Hash stability: every hash is fixed until its source or the bundler changes. The teams/[code]
script reads its season from a data attribute, so it has one hash for all seasons. When inline
code changes, rebuild the site, rescan, and update them here.
"""

from pathlib import Path

import pytest

HEADERS = Path(__file__).resolve().parents[1] / "web" / "public" / "_headers"

# Inline <script> blocks that run: the classic and the module ones (JSON-LD and application/json
# blocks are data, not code, so no CSP applies to them).
INLINE_CLASSIC_SCRIPTS = (
    "sha256-3pJu0C1DctTV9XaDOgOoIMMSuIocxvwDnToV9thSfiM=",
    "sha256-z6WhmaLW8FoXGRlWSgZHo9FjVo0+3+tjRkYXyTKMSwE=",
    "sha256-SewhOhMawN/eW9gUoQfrwFglPOEy9OH4L0sEmUW72b8=",
    "sha256-rAvtN0kn2NTesEGjAwvL3XSjCPcookghdRTVy3VQHC8=",
    "sha256-pyGYNgq1qjnE74Nfn7vOjYILf+6aXRdAYQ9KW1PMqq0=",
)
INLINE_MODULE_SCRIPTS = (
    "sha256-EGBjaXg8dtKFMiUnFzns5J6Ig0uUlMfnaHZb5KaA+LI=",
    "sha256-EHIzbbOJQ4Ko4zjCvFuDvGdjhgq/zu/6c+m3ubvyVIE=",
    "sha256-aTvU5lg6RK40Uw3jBonx1QPgoAWus+ZvLuIEEHnW2y8=",
    "sha256-1r9OM0aBN/v81yeR84p3f4Ln+eEemhxyOM3sEoV3FaY=",
    "sha256-HWi/qCyAmq7zSN363PLNZjc6i0aIdijKzgCqMhD1wK4=",
    "sha256-pWfZIqSLn4cQzVAaqAZZPjhMlR5P87Uq/FENUr/8S+I=",
    "sha256-FiufgVSux4vYcK+IXqHUxfTADb0NRTpmCkPBpUdXcqQ=",
)
# Third parties: Cloudflare Web Analytics (beacon script injected at the edge, and the endpoint it
# reports to) and the Sentry ingest host from PUBLIC_SENTRY_DSN.
CF_BEACON_SCRIPT = "https://static.cloudflareinsights.com"
CF_BEACON_REPORT = "https://cloudflareinsights.com"
SENTRY_INGEST = "https://o4512259541499904.ingest.de.sentry.io"
# The <style> blocks in the pages.
INLINE_STYLES = (
    "sha256-N/8WhQYpTTWPzMsGjj/UMrpmkMog80EWJuTy/XWK7W4=",
    "sha256-/VRL5YTw56MD34zW8ggIrftSE8BA+2uiPF1/JkK1ku4=",
    "sha256-7Xcyi7btNYagBvHzLGAPFacX4SnpS9bDqx8A+Ie27fs=",
    "sha256-E1ERnBcJxUL3Plf46fcXhYOoEnSSSW6G1vNhqHbGObc=",
    "sha256-gpr1Z9U9/Z8o+u3Zx+u+fW9KImdXNZkJxI1W29dRbo8=",
    "sha256-BRkE0xdd7PtFxOVHUDaUQWqGyP01OuLMgv8CFnAPpfQ=",
    "sha256-3ZQr6yisei1eayV0w85Tn4+Ie+uCebE/NS8jxw92Vfg=",
    "sha256-3VHKYji75kuiFssporufcP+6w5EcyUUt4PlBkzIUaNw=",
    "sha256-RiaHRjII1AWyN9iza9wc/54k0/fNNUEBUFuwO9EGwPs=",
    "sha256-Ve+uJcTrDrjKm+oHxbdk4urfzA7dyEa8XxkyIyT4qAM=",
    "sha256-AnA5/QwE7jIxgQUJ6eigcKCnlKoqx9SYGqEJg9AN4d0=",
    "sha256-SAukp5KlkzID2R3tCbohD0UIQYp5W2IK53Vt2jxNNDc=",
)
# The one inline event handler value (onsubmit="return false" on the six forms).
INLINE_HANDLER = "sha256-GZIcz60Uwd6wT3vaYke/atSr53TehbYAPepOa3d03Vw="


def parse_headers(text: str) -> dict[str, dict[str, str]]:
    """Path -> header name -> value, in the Cloudflare _headers format."""
    rules: dict[str, dict[str, str]] = {}
    path = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if not raw.startswith(" "):
            path = raw.strip()
            rules.setdefault(path, {})
            continue
        assert path is not None, f"header before any path: {raw!r}"
        name, _, value = raw.strip().partition(":")
        rules[path][name.strip()] = value.strip()
    return rules


@pytest.fixture(scope="module")
def rules() -> dict[str, dict[str, str]]:
    return parse_headers(HEADERS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def policy(rules: dict[str, dict[str, str]]) -> dict[str, list[str]]:
    value = rules["/*"]["Content-Security-Policy"]
    return {d.split()[0]: d.split()[1:] for d in value.split(";") if d.strip()}


def test_the_csp_is_enforced_with_script_and_style_rules(
    rules: dict[str, dict[str, str]], policy: dict[str, list[str]]
) -> None:
    assert "Content-Security-Policy-Report-Only" not in rules["/*"]
    assert "script-src" in policy and "style-src" in policy


def test_policy_keeps_the_framing_base_object_and_form_rules(policy: dict[str, list[str]]) -> None:
    assert policy["default-src"] == ["'self'"]
    assert policy["frame-ancestors"] == ["'none'"]
    assert policy["base-uri"] == ["'self'"]
    assert policy["object-src"] == ["'none'"]
    assert policy["form-action"] == ["'self'"]


def test_scripts_and_styles_carry_exactly_the_inventoried_hashes(
    policy: dict[str, list[str]],
) -> None:
    assert policy["script-src"] == [
        "'self'",
        CF_BEACON_SCRIPT,
        *(f"'{h}'" for h in INLINE_CLASSIC_SCRIPTS + INLINE_MODULE_SCRIPTS),
    ]
    assert policy["style-src"] == ["'self'", *(f"'{h}'" for h in INLINE_STYLES)]
    assert policy["script-src-attr"] == ["'unsafe-hashes'", f"'{INLINE_HANDLER}'"]
    assert policy["style-src-attr"] == [
        "'unsafe-inline'"
    ]  # 8,032 style= attributes: no hash exists


def inventory() -> list[tuple[str, str]]:
    """(directive, source) for every resource class the built site uses, from the scan."""
    items = [("script-src", "'self'"), ("style-src", "'self'"), ("img-src", "'self'")]
    items += [("font-src", "'self'"), ("connect-src", "'self'"), ("form-action", "'self'")]
    items += [("manifest-src", "'self'")]
    items += [("script-src", CF_BEACON_SCRIPT), ("connect-src", CF_BEACON_REPORT)]
    items += [("connect-src", SENTRY_INGEST)]
    items += [("script-src", f"'{h}'") for h in INLINE_CLASSIC_SCRIPTS + INLINE_MODULE_SCRIPTS]
    items += [("style-src", f"'{h}'") for h in INLINE_STYLES]
    items += [("script-src-attr", f"'{INLINE_HANDLER}'")]
    items += [("style-src-attr", "'unsafe-inline'")]
    return items


def test_zero_predicted_violations_for_the_built_site(policy: dict[str, list[str]]) -> None:
    """Every resource the scan found is allowed by the directive it falls under."""
    violations = []
    for directive, source in inventory():
        allowed = policy.get(directive, policy["default-src"])
        if source not in allowed:
            violations.append(f"{directive} {source}")
    assert violations == []


def test_the_policy_fits_the_header_line_limit(rules: dict[str, dict[str, str]]) -> None:
    for path, headers in rules.items():
        for name, value in headers.items():
            assert len(f"{name}: {value}") < 2000, (path, name)


def test_cross_origin_policy_per_path(rules: dict[str, dict[str, str]]) -> None:
    assert rules["/*"]["Cross-Origin-Opener-Policy"] == "same-origin"
    assert rules["/_astro/*"]["Cross-Origin-Resource-Policy"] == "same-origin"
    # /data/* and /api/* are public on purpose (F-26): no CORP there, and no site-wide CORP,
    # because Cloudflare applies /* to them too.
    for path in ("/*", "/data/*", "/api/*"):
        assert "Cross-Origin-Resource-Policy" not in rules[path], path
    for path in ("/data/*", "/api/*"):
        assert "Access-Control-Allow-Origin" not in rules[path]  # no CORS today: unchanged


def test_existing_security_headers_are_unchanged(rules: dict[str, dict[str, str]]) -> None:
    assert (
        rules["/*"]["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains; preload"
    )
    assert rules["/*"]["X-Content-Type-Options"] == "nosniff"
    assert rules["/*"]["X-Frame-Options"] == "DENY"
    assert rules["/*"]["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert rules["/data/*"]["X-Robots-Tag"] == "noindex"
    assert rules["/api/*"]["X-Robots-Tag"] == "noindex"


def test_hsts_meets_the_preload_list_requirements(rules: dict[str, dict[str, str]]) -> None:
    """hstspreload.org needs max-age of at least one year, includeSubDomains and preload."""
    directives = [d.strip() for d in rules["/*"]["Strict-Transport-Security"].split(";")]
    max_age = int(next(d for d in directives if d.startswith("max-age=")).split("=")[1])
    assert max_age >= 31536000
    assert "includeSubDomains" in directives
    assert "preload" in directives
