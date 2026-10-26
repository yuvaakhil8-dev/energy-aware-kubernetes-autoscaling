"""Dataset integrity tests for experiment_results_v2.json."""
import collections
import hashlib
import json
import os

import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BASE_DIR)


def _dataset(name):
    """Prefer the tracked data/ copy so tests work in a clean checkout."""
    tracked = os.path.join(BASE_DIR, 'data', name)
    return tracked if os.path.exists(tracked) else os.path.join(PROJECT_ROOT, name)


V2 = _dataset('experiment_results_v2.json')

STRATEGIES = {'static', 'hpa', 'energy_aware'}
WORKLOADS = {'light', 'medium', 'heavy'}


@pytest.fixture(scope='module')
def records():
    with open(V2, encoding='utf-8') as fh:
        return json.load(fh)


def test_record_count(records):
    assert len(records) == 27


def test_unique_ids(records):
    ids = [r.get('experiment_id') for r in records]
    assert len(set(ids)) == 27
    assert all(ids)


def test_full_factorial_coverage(records):
    cells = collections.Counter((r['mode'], r['workload']) for r in records)
    assert len(cells) == 9
    assert all(count == 3 for count in cells.values())


def test_strategies_and_workloads(records):
    assert {r['mode'] for r in records} == STRATEGIES
    assert {r['workload'] for r in records} == WORKLOADS


def test_repetition_identifiers(records):
    for r in records:
        assert r.get('repetition') in (1, 2, 3), r.get('experiment_id')
    per_cell = collections.defaultdict(set)
    for r in records:
        per_cell[(r['mode'], r['workload'])].add(r['repetition'])
    assert all(v == {1, 2, 3} for v in per_cell.values())


def test_numeric_fields_present(records):
    for r in records:
        assert isinstance(r.get('average_replicas'), (int, float)), r['experiment_id']
        assert isinstance(r.get('avg_cpu'), (int, float)), r['experiment_id']
        assert isinstance(r.get('avg_energy_per_request'), (int, float)), r['experiment_id']
        assert isinstance(r.get('average_latency_ms'), (int, float)), r['experiment_id']
        assert 0 <= r['avg_cpu'] <= 100


def test_no_measured_energy_claim(records):
    """Every record must be explicitly marked as simulation, not measurement."""
    for r in records:
        assert r.get('execution_mode') == 'simulation', r.get('experiment_id')


def test_pseudo_replication_is_flagged(records):
    """Guard the known limitation: repetitions are identical per cell.

    If a future run produces genuinely independent repetitions this test will
    fail on purpose, prompting the report to be updated.
    """
    identical = 0
    cells = collections.defaultdict(list)
    for r in records:
        cells[(r['mode'], r['workload'])].append(r)
    for rows in cells.values():
        fingerprints = {
            (r['avg_cpu'], r['avg_energy_per_request'],
             r['average_latency_ms'], r['average_replicas'])
            for r in rows
        }
        if len(fingerprints) == 1:
            identical += 1
    # Known state of the current dataset: all 9 cells are pseudo-replicated.
    assert identical == 9, (
        'Dataset changed: repetitions now differ. Update DATASET_INTEGRITY_REPORT.md '
        f'(identical cells = {identical}).'
    )


def test_legacy_dataset_untouched():
    legacy = _dataset('experiment_results.json')
    assert os.path.exists(legacy)
    with open(legacy, encoding='utf-8') as fh:
        data = json.load(fh)
    assert isinstance(data, list)
    assert len(data) == 18


def test_tracked_dataset_hashes():
    expected = {
        'experiment_results_v2.json':
            '6279D01DC92D9C4FBE2EBB2C5BA0C12A7DA3EA7CA985E9FA762E88A11F34234E',
        'experiment_results.json':
            'C4BF4BFFFA8D0242395D2A2FB966C16DBC4884078BE7E82395E778EF87968451',
    }
    for name, digest in expected.items():
        with open(_dataset(name), 'rb') as fh:
            actual = hashlib.sha256(fh.read()).hexdigest().upper()
        assert actual == digest, name
