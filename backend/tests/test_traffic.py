"""
Tests for traffic system.
"""
import pytest
from traffic.scoring import TrafficScorer
from traffic.weights import WeightCalculator
from traffic.presence import PresenceManager


class TestTrafficScorer:
    """Test traffic scoring."""

    def setup_method(self):
        self.scorer = TrafficScorer()

    def test_classify_low(self):
        assert self.scorer.classify_by_count(0) == 'LOW'
        assert self.scorer.classify_by_count(3) == 'LOW'

    def test_classify_moderate(self):
        assert self.scorer.classify_by_count(4) == 'MODERATE'
        assert self.scorer.classify_by_count(7) == 'MODERATE'

    def test_classify_high(self):
        assert self.scorer.classify_by_count(8) == 'HIGH'
        assert self.scorer.classify_by_count(12) == 'HIGH'

    def test_classify_severe(self):
        assert self.scorer.classify_by_count(13) == 'SEVERE'
        assert self.scorer.classify_by_count(100) == 'SEVERE'

    def test_crowd_ratio(self):
        assert self.scorer.calculate_crowd_ratio(5, 10) == 0.5
        assert self.scorer.calculate_crowd_ratio(0, 10) == 0.0

    def test_congestion_factor(self):
        assert self.scorer.calculate_congestion_factor(0.0) == 1.0
        assert self.scorer.calculate_congestion_factor(0.5) == 2.0
        assert self.scorer.calculate_congestion_factor(1.0) == 3.0

    def test_current_time_calculation(self):
        base = 100.0
        # 0 users -> 1.0x -> 100s
        assert self.scorer.calculate_current_time(base, 0) == 100.0
        # 5 users, capacity 10 -> 0.5 ratio -> 2.0x -> 200s
        assert self.scorer.calculate_current_time(base, 5, 10) == 200.0

    def test_traffic_state(self):
        state = self.scorer.get_traffic_state(5, 10)
        assert state['active_users'] == 5
        assert state['traffic_level'] == 'MODERATE'
        assert state['crowd_ratio'] == 0.5
        assert state['congestion_factor'] == 2.0


class TestWeightCalculator:
    """Test weight calculator."""

    def setup_method(self):
        self.calc = WeightCalculator()

    def test_update_edge_weight(self):
        edge = {'id': 'e1', 'base_time_sec': 100.0, 'current_time_sec': 100.0}
        new_time = self.calc.update_edge_weight(edge, 5)
        assert new_time == 200.0
        assert edge['current_time_sec'] == 200.0
        assert edge['traffic_level'] == 'MODERATE'

    def test_base_time_unchanged(self):
        edge = {'id': 'e1', 'base_time_sec': 100.0, 'current_time_sec': 100.0}
        self.calc.update_edge_weight(edge, 10)
        assert edge['base_time_sec'] == 100.0


class TestPresenceMemoryFallback:
    def test_presence_updates_and_expires_without_redis(self, monkeypatch):
        monkeypatch.setattr('traffic.presence.get_redis_client', lambda: None)
        manager = PresenceManager()
        now = [1000.0]
        monkeypatch.setattr('traffic.presence.time.time', lambda: now[0])
        session_id = 'test-memory-presence'
        edge_id = 'test-memory-edge'

        manager.update_presence(session_id, edge_id, 9.57, 77.68)
        assert manager.get_edge_count(edge_id) == 1
        assert manager.get_session_edge(session_id) == edge_id

        manager.update_presence(session_id, 'test-memory-edge-next', 9.58, 77.69)
        assert manager.get_edge_count(edge_id) == 0
        assert manager.get_edge_count('test-memory-edge-next') == 1

        now[0] += manager.ttl + 1
        assert manager.cleanup_expired() == 1
        assert manager.get_session_edge(session_id) is None
