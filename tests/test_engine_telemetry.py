"""Opt-in local telemetry: bounded histograms, spans and redaction."""
import json
import os
import time

from biopipe.engine.telemetry import Histogram, Metrics, bind_correlation, correlation, redact, span


def test_histogram_reports_nearest_rank_percentiles_and_bounds_samples():
    histogram = Histogram(limit=8)
    for value in range(1, 101):
        histogram.observe(value)
    summary = histogram.summary()
    assert summary['count'] == 100 and summary['retained'] == 8
    assert summary['min'] == 1
    assert summary['max'] == 100
    assert summary['p50'] is not None and summary['p95'] is not None


def test_metrics_are_disabled_unless_opted_in(monkeypatch):
    monkeypatch.delenv('BIOPIPE_ENGINE_METRICS', raising=False)
    disabled = Metrics()
    disabled.observe('x', 1)
    disabled.increment('y')
    assert disabled.snapshot()['histograms'] == {} and disabled.snapshot()['counters'] == {}
    monkeypatch.setenv('BIOPIPE_ENGINE_METRICS', '1')
    enabled = Metrics()
    enabled.observe('x', 4)
    enabled.observe('x', 8)
    enabled.increment('y', 2)
    enabled.gauge('queue', 3)
    snapshot = enabled.snapshot()
    assert snapshot['histograms']['x']['count'] == 2
    assert snapshot['counters'] == {'y': 2}
    assert snapshot['gauges'] == {'queue': 3}


def test_span_and_correlation_are_context_local():
    with span('control.dispatch', request_id='r1'):
        assert correlation()['request_id'] == 'r1'
    assert correlation() == {}


def test_redaction_removes_credentials_not_payload_keys():
    value = {'password': 'secret', 'token': 't', 'graph': {'node': 'x'},
             'nested': [{'passphrase': 'p'}]}
    cleaned = redact(value)
    assert cleaned['password'] == '<redacted>' and cleaned['token'] == '<redacted>'
    assert cleaned['graph'] == {'node': 'x'}
    assert cleaned['nested'][0]['passphrase'] == '<redacted>'
