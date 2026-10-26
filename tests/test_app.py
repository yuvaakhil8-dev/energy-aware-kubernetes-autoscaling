"""HTTP contract tests for every Flask route."""
import hashlib
import json
import os

DASHBOARD_ROUTES = [
    '/',
    '/eaes-diagnostics',
    '/methodology',
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
    '/api/v1/research/results',
    '/api/v1/research/diagnostic',
    '/api/v1/research/methodology',
    '/api/v1/research/cluster',
    '/api/v1/research/tables/descriptive',
    '/api/v1/research/tables/paired',
    '/api/v1/research/tables/headline',
    '/api/v1/research/tables/paired_headline',
    '/api/v1/research/timeseries?workload=steady&strategy=eaes&seed=1',
    '/api/v1/research/controller-trace?workload=variable&strategy=forecasting_eaes&seed=1',
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
    for asset in ('/static/dashboard.css', '/static/dashboard.js',
                  '/static/research.css', '/static/research.js',
                  '/static/vendor/chart.umd.min.js'):
        response = client.get(asset)
        assert response.status_code == 200, asset
        assert len(response.get_data()) > 0


def test_research_results_payload_is_generated(client):
    payload = client.get('/api/v1/research/results').get_json()
    assert payload['available'] is True
    assert payload['run']['run_id']
    assert payload['run']['execution_mode'] == 'simulation'
    assert payload['kpis']['runs'] == 300
    assert payload['kpis']['seeds'] == 10
    assert payload['descriptive_primary']
    assert payload['warnings']


def test_research_diagnostic_payload(client):
    payload = client.get('/api/v1/research/diagnostic').get_json()
    assert payload['available'] is True
    assert payload['comparisons']
    assert payload['forecast_comparison']
    assert payload['conservation_max_error_j'] is not None


def test_research_timeseries_is_real_backend_data(client):
    payload = client.get(
        '/api/v1/research/timeseries?workload=bursty&strategy=forecasting_eaes&seed=1'
    ).get_json()
    assert payload['available'] is True
    assert payload['workload'] == 'bursty'
    assert payload['summary']['n_runs'] == 10
    series = payload['series']
    assert len(series['time_s']) == 60
    assert len(series['offered_rps']) == 60
    assert len(series['cpu_percent']) == 60
    assert len(series['ready_replicas']) == 60
    assert any(v is not None and v > 0 for v in series['forecast_rps'])
    assert any(v is not None and v > 0 for v in series['actual_forward_rps'])


def test_research_timeseries_rejects_unknown_filters(client):
    response = client.get(
        '/api/v1/research/timeseries?workload=not-a-workload&strategy=eaes&seed=1'
    )
    assert response.status_code == 400
    assert 'Unknown workload' in response.get_json()['error']


def test_research_controller_trace_exposes_decision_and_history(client):
    payload = client.get(
        '/api/v1/research/controller-trace?workload=variable&strategy=eaes&seed=1'
    ).get_json()
    assert payload['available'] is True
    latest = payload['latest']
    for key in (
        'observed_rps', 'cpu_percent', 'ready_replicas', 'desired_replicas',
        'scaling_action', 'rule_fired', 'decision_reason', 'cooldown_status',
        'sla_margin', 'decision_details',
    ):
        assert key in latest
    assert payload['behavior']['ticks'] == 60
    assert isinstance(payload['history'], list)


def test_results_payload_exposes_chart_choices(client):
    payload = client.get('/api/v1/research/results').get_json()
    assert payload['choices']['workloads']
    assert payload['choices']['default_strategy'] == 'eaes'
    for metric in (
        'energy_per_served_request_j', 'energy_per_offered_request_j',
        'drop_rate', 'sla_violation_rate', 'replica_hours', 'p95_latency_ms',
    ):
        assert metric in payload['chart']['metrics']


def test_research_methodology_payload(client):
    payload = client.get('/api/v1/research/methodology').get_json()
    assert payload['configs']['sla']['latency_sla_ms'] == 500.0
    assert payload['configs']['simulation']['pods_per_node'] == 4
    assert payload['dataset_hashes']['experiment_results_v2.json']
    assert 'hpa_formula' in payload['strategy_distinctions']
    assert payload['architecture']['layers']
    assert payload['execution_flow']
    assert payload['execution_modes']['simulation']
    assert any(api['path'].startswith('/api/v1/research/timeseries') for api in payload['api_endpoints'])
    assert payload['kubernetes_integration']['native_hpa']


def test_research_table_whitelist(client):
    ok = client.get('/api/v1/research/tables/descriptive')
    assert ok.status_code == 200
    assert ok.get_json()['rows']
    bad = client.get('/api/v1/research/tables/not-a-table')
    assert bad.status_code == 404


def test_cluster_validation_is_labelled(client):
    payload = client.get('/api/v1/research/cluster').get_json()
    assert payload['execution_mode'] == 'kubernetes_validation'
    assert payload['available'] is True
    assert 'not measured power' in payload['energy_note']


def test_app_local_dataset_copies_are_byte_identical(app_module):
    expected = {
        'experiment_results_v2.json': '6279D01DC92D9C4FBE2EBB2C5BA0C12A7DA3EA7CA985E9FA762E88A11F34234E',
        'experiment_results.json': 'C4BF4BFFFA8D0242395D2A2FB966C16DBC4884078BE7E82395E778EF87968451',
    }
    for name, digest in expected.items():
        path = os.path.join(app_module.BASE_DIR, 'data', name)
        with open(path, 'rb') as fh:
            assert hashlib.sha256(fh.read()).hexdigest().upper() == digest


def test_loader_uses_app_local_copies(monkeypatch, app_module):
    monkeypatch.setattr(app_module, 'PROJECT_ROOT', app_module.BASE_DIR)
    app_module._load_experiment_data()
    assert len(app_module.EXPERIMENT_RESULTS) == 27
    assert app_module.DATASET_FILE == 'experiment_results_v2.json'
    assert app_module.DATASET_IS_FALLBACK is False


def test_unknown_route_returns_404_html(client):
    response = client.get('/definitely-not-a-route')
    assert response.status_code == 404
    assert response.content_type.startswith('text/html')
