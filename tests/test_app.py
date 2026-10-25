"""HTTP contract tests for every Flask route."""
import json

DASHBOARD_ROUTES = [
    '/',
    '/autoscaling-comparison',
    '/energy-analysis',
    '/performance-analysis',
    '/experiment-explorer',
    '/research-methodology',
]

JSON_ROUTES = [
    '/api/status',
    '/health',
    '/ready',
    '/info',
    '/workload/status',
    '/status',
    '/controller/status',
    '/api/v1/experiments',
    '/api/v1/research-papers',
]


def test_root_is_html(client):
    response = client.get('/')
    assert response.status_code == 200
    assert response.content_type.startswith('text/html')
    body = response.get_data(as_text=True).lower()
    assert '<!doctype html>' in body
    assert 'dashboard' in body
    # Regression guard: the old JSON status must not be served at '/'
    assert 'energy-aware flask microservice is running' not in body


def test_exactly_one_root_endpoint(flask_app):
    roots = [rule for rule in flask_app.url_map.iter_rules() if rule.rule == '/']
    assert len(roots) == 1
    assert roots[0].endpoint == 'dashboard'


def test_dashboard_routes_html(client):
    for path in DASHBOARD_ROUTES:
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.content_type.startswith('text/html'), path
        assert '<!doctype html>' in response.get_data(as_text=True).lower(), path


def test_json_routes(client):
    for path in JSON_ROUTES:
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.content_type.startswith('application/json'), path
        json.loads(response.get_data(as_text=True))  # must parse


def test_api_status_payload(client):
    payload = client.get('/api/status').get_json()
    assert payload['message']
    assert 'cpu_percent' in payload
    assert 'workload' in payload


def test_workload_change(client):
    ok = client.post('/workload/change', json={'profile': 'heavy'})
    assert ok.status_code == 200
    assert ok.get_json()['cpu_percent'] == 85

    bad = client.post('/workload/change', json={'profile': 'nonsense'})
    assert bad.status_code == 400

    missing = client.post('/workload/change', data='not json',
                          content_type='text/plain')
    assert missing.status_code == 400

    # restore default for other tests
    client.post('/workload/change', json={'profile': 'light'})


def test_metrics_text(client):
    response = client.get('/metrics')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'flask_cpu_utilization_current' in body
    assert 'flask_experiments_loaded' in body


def test_static_assets(client):
    for asset in ('/static/dashboard.css', '/static/dashboard.js'):
        response = client.get(asset)
        assert response.status_code == 200, asset
        assert len(response.get_data()) > 0


def test_unknown_route_returns_404_html(client):
    response = client.get('/definitely-not-a-route')
    assert response.status_code == 404
    assert response.content_type.startswith('text/html')
