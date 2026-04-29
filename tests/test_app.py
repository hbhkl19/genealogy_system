from app import create_app
from app.config import TestingConfig


def test_app_routes_load():
    app = create_app(TestingConfig)
    routes = {rule.rule for rule in app.url_map.iter_rules()}

    assert "/register" in routes
    assert "/login" in routes
    assert "/genealogies" in routes
    assert "/relationship/path" in routes
