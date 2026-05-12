from prometheus_client import Counter, Histogram, Info
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import REGISTRY

from app.database import engine

# Syzygy probe는 마이크로초 단위. 하한을 10μs까지 내려 분포를 캡처.
_SYZYGY_BUCKETS = (
    0.00001, 0.00005, 0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0,
)

tablebase_operation_seconds = Histogram(
    "tablebase_operation_seconds",
    "Syzygy tablebase operation wall-clock latency (lock wait included). "
    "Use tablebase_lock_wait_seconds to separate contention from probe cost.",
    ["operation"],
    buckets=_SYZYGY_BUCKETS,
)

tablebase_lock_wait_seconds = Histogram(
    "tablebase_lock_wait_seconds",
    "Time spent waiting to acquire the Syzygy tablebase lock",
    ["operation"],
    buckets=_SYZYGY_BUCKETS,
)

endgame_move_total = Counter(
    "endgame_move_total",
    "Total moves processed by /move endpoint, labeled by outcome",
    ["outcome"],
)

endgame_move_errors_total = Counter(
    "endgame_move_errors_total",
    "Total /move requests that failed before producing an outcome",
    ["reason"],
)

app_info = Info("zugzwang_app", "Application metadata")
app_info.info({"version": "0.1.0"})


class _DBPoolCollector:
    """Expose SQLAlchemy connection pool state as db_pool_connections{state=...}."""

    # (label, pool method, clamp negative→0)
    # overflow는 SQLAlchemy 내부 카운터라 초기엔 -size 값. 사용자 관점에서
    # "size 한계를 초과한 활성 커넥션 수"가 되도록 0으로 클램프.
    _STATES = (
        ("checked_out", "checkedout", False),
        ("checked_in", "checkedin", False),
        ("overflow", "overflow", True),
        ("size", "size", False),
    )

    def collect(self):
        pool = engine.pool
        gauge = GaugeMetricFamily(
            "db_pool_connections",
            "SQLAlchemy connection pool state",
            labels=["state"],
        )
        for state, method, clamp_nonneg in self._STATES:
            fn = getattr(pool, method, None)
            if fn is None:
                continue
            try:
                value = fn()
            except Exception:
                continue
            if clamp_nonneg and value < 0:
                value = 0
            gauge.add_metric([state], value)
        yield gauge


REGISTRY.register(_DBPoolCollector())
