import signal
import json
import math
import os
import csv
from datetime import datetime, timezone
from collections import defaultdict
from confluent_kafka import Consumer, KafkaException
from river import compose, preprocessing, anomaly
from src.proto import ebpf_event_pb2
from src.common.config import get_config


file_handles = {}
csv_writers = {}
def get_writer(container):
    """Return a CSV writer for this container (create file if needed)."""
    global file_handles, csv_writers
    # Sanitize container name for filename (remove / and :)
    safe_name = container.replace("/", "_").replace(":", "_")
    filename = f"logs/{safe_name}.csv"

    if container not in file_handles:
        os.makedirs("logs", exist_ok=True)
        f = open(filename, "a", newline="")
        writer = csv.writer(f)

        # Write header only once, if file is empty
        if os.stat(filename).st_size == 0:
            writer.writerow([
                "timestamp", "container",
                "pid", "ppid", "user", "gid",
                "comm", "event_type", "node",
                "score", "is_anomaly", "phase"
            ])

        file_handles[container] = f
        csv_writers[container] = writer

    return csv_writers[container]

def close_writers():
    """Close all open file handles."""
    for f in file_handles.values():
        f.close()


# === Graceful shutdown ===
running = True
MAX_SYSCALLS = 500
def shutdown(sig, frame):
    global running
    running = False
    print("Shutting down...")

def on_assign(consumer, partitions):
    print("✅ Successfully connected to Kafka and assigned partitions:", partitions)

# === Model builder ===
def build_ocsvm_model():
    return compose.Pipeline(
        preprocessing.StandardScaler(),
        anomaly.QuantileFilter(
            anomaly.OneClassSVM(nu=0.2),
            q=0.99
        )
    )

# === Helper: parse syscall vector into fixed length ===
def parse_syscall_vector(json_str):
    try:
        raw = json.loads(json_str)
    except Exception:
        return {str(i): 0 for i in range(MAX_SYSCALLS)}

    vec = {str(i): 0 for i in range(MAX_SYSCALLS)}
    for k, v in raw.items():
        try:
            idx = int(k)
            if idx < MAX_SYSCALLS:
                vec[str(idx)] = int(v)
        except Exception:
            continue
    return vec


def run_consumer():
    global running
    # === Config ===
    cfg = get_config("frequency")
    print(f"✅ Loaded config: {cfg}")

    # === Constants ===
    WARMUP_EVENTS = cfg["warmup"]["size_per_container"]


    # === Per-container models ===
    models = defaultdict(build_ocsvm_model)
    seen_counts = defaultdict(int)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # === Kafka consumer setup ===
    conf = {
        "bootstrap.servers": cfg["kafka"]["broker"],
        "group.id": "percontainer-syscall-detector",
        "auto.offset.reset": cfg["kafka"]["auto_offset_reset"],
    }
    consumer = Consumer(conf)
    consumer.subscribe([cfg["kafka"]["topic"]], on_assign=on_assign)

    print(f" Listening on topic {cfg['kafka']['topic']} for syscall frequency events...")

        # === Main loop ===
    while running:
        msg = consumer.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            raise KafkaException(msg.error())

        try:
            event = ebpf_event_pb2.EbpfEvent()
            event.ParseFromString(msg.value())

            if event.HasField("syscall_freq_agg"):
                container = event.container_image
                if not container or (isinstance(container, float) and math.isnan(container)):
                    continue

                # Convert JSON string ÔåÆ fixed-length vector
                features = parse_syscall_vector(event.syscall_freq_agg.vector_json)

                model = models[container]
                seen_counts[container] += 1
                idx = seen_counts[container]

                if idx < WARMUP_EVENTS:
                    model.learn_one(features)
                    continue
                if idx == WARMUP_EVENTS:
                    print(f"✅ Container {container} finished warm-up ({idx} events)")
                    iso_time = datetime.now(timezone.utc)
                    writer = get_writer(container)
                    writer.writerow([
                    iso_time.isoformat(),
                    container,
                    event.pid,
                    event.ppid,
                    event.user,
                    event.gid,
                    event.comm,
                    event.event_type,
                    event.node_name,
                    0,
                    0,
                    "warmup"
                    ])

                score = model.score_one(features)
                is_anomaly = model["QuantileFilter"].classify(score) or (score < 0)
                model.learn_one(features)
                iso_time = datetime.now(timezone.utc)
                writer = get_writer(container)
                writer.writerow([
                iso_time.isoformat(),
                container,
                event.pid,
                event.ppid,
                event.user,
                event.gid,
                event.comm,
                event.event_type,
                event.node_name,
                f"{score:.4f}",
                int(is_anomaly),
                "detection"
                ])

                if is_anomaly:
                    print(
                        f"🚨 ALERT [{container}] Syscall anomaly "
                        f"Score={score:.4f} | PID={event.pid} COMM={event.comm} USER={event.user} "
                        f"| Node={event.node_name}"
                    )
                    

        except Exception as e:
            print(f" Error decoding/processing message: {e}")

    consumer.close()
    close_writers()
    print("👋 Consumer closed cleanly")

