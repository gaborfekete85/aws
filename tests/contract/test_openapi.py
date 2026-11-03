"""docs/openapi.yaml must describe exactly the routes Terraform deploys (ZAP API scan input)."""

import re
from pathlib import Path

import yaml
from openapi_spec_validator import validate

ROOT = Path(__file__).resolve().parents[2]
SPEC = yaml.safe_load((ROOT / "docs" / "openapi.yaml").read_text())


def terraform_routes() -> dict[str, bool]:
    """route -> public, from every lambda-service `routes` block."""
    routes: dict[str, bool] = {}
    pattern = re.compile(r'route_key = "([A-Z]+ [^"]+)"(?:, public = (true))?')
    for tf in (ROOT / "infra" / "modules" / "stack").glob("*.tf"):
        for match in pattern.finditer(tf.read_text()):
            routes[match.group(1)] = match.group(2) == "true"
    return routes


def spec_routes() -> dict[str, bool]:
    routes: dict[str, bool] = {}
    for path, item in SPEC["paths"].items():
        for method, op in item.items():
            if method in {"get", "post", "put", "patch", "delete"}:
                routes[f"{method.upper()} {path}"] = op.get("security") == []
    return routes


def test_spec_is_valid_openapi() -> None:
    validate(SPEC)


def test_every_deployed_route_is_documented_and_vice_versa() -> None:
    assert set(terraform_routes()) == set(spec_routes())


def test_public_routes_match() -> None:
    """A route public in Terraform (no JWT) must be marked `security: []` in the spec."""
    deployed, documented = terraform_routes(), spec_routes()
    mismatched = {r for r in deployed if deployed[r] != documented.get(r)}
    assert not mismatched, f"public/protected mismatch: {sorted(mismatched)}"
