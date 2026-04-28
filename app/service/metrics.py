from prometheus_client import Counter, Histogram

tablebase_operation_seconds = Histogram(
    "tablebase_operation_seconds",
    "Syzygy tablebase operation latency in seconds",
    ["operation"],
    buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0),
)

endgame_move_total = Counter(
    "endgame_move_total",
    "Total moves processed by /move endpoint, labeled by outcome",
    ["outcome"],
)
