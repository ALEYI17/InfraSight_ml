import signal
import time
from confluent_kafka import Consumer, KafkaException
from src.proto import ebpf_event_pb2
import math
from collections import defaultdict
from river import compose, preprocessing, anomaly
from src.common.config import get_config
from src.common.model_factory import get_model

running = True
def shutdown(sig, frame):
    global running
    running = False
    print("Shutting down...")


# === Per-container models ===
def build_ocsvm_model():
    return compose.Pipeline(
        preprocessing.StandardScaler(),
        anomaly.QuantileFilter(
            anomaly.OneClassSVM(nu=0.2),
            q=0.95
        )
    )

def run_consumer():
    global running
    # === Config ===
    cfg = get_config("resource")
    print(f"⚙️ Loaded config: {cfg}")


    models = defaultdict(build_ocsvm_model)
    seen_counts = defaultdict(int)
    WARMUP_EVENTS = cfg["warmup"]["size_per_container"]  # warm-up per container

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # === Kafka consumer setup ===
    conf = {
        "bootstrap.servers": cfg["kafka"]["broker"],
        "group.id": "percontainer-anomaly-detector",
        "auto.offset.reset": cfg["kafka"]["auto_offset_reset"],
    }
        
    consumer = Consumer(conf)
    consumer.subscribe([cfg["kafka"]["topic"]])

    print(f"Listening on topic {cfg['kafka']['topic']} for per-container models...")

    while running:
        msg = consumer.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            raise KafkaException(msg.error())

        try:
            event = ebpf_event_pb2.EbpfEvent()
            event.ParseFromString(msg.value())

            if event.HasField("resource"):
                res = event.resource
                features = {
                    "cpu_ns": res.CpuNs,
                    "user_faults": res.UserFaults,
                    "kernel_faults": res.KernelFaults,
                    "vm_mmap_bytes": res.VmMmapBytes,
                    "vm_munmap_bytes": res.VmMunmapBytes,
                    "vm_brk_grow_bytes": res.VmBrkGrowBytes,
                    "vm_brk_shrink_bytes": res.VmBrkShrinkBytes,
                    "bytes_written": res.BytesWritten,
                    "bytes_read": res.BytesRead,
                }
                container = event.container_image
                if not container or (isinstance(container, float) and math.isnan(container)):
                    continue

                model = models[container]
                seen_counts[container] += 1
                idx = seen_counts[container]

                if idx < WARMUP_EVENTS:
                    model.learn_one(features)
                    continue
                if idx == WARMUP_EVENTS:
                    print(f"🔥 Container {container} finished warm-up ({idx} events)")

                score = model.score_one(features)
                is_anomaly = model["QuantileFilter"].classify(score)
                model.learn_one(features)

                if is_anomaly:
                    print(
                        f"🚨 ALERT [{container}] Score={score:.4f} | "
                        f"PID={event.pid} COMM={event.comm} USER={event.user} | Node={event.node_name}"
                    )

        except Exception as e:
            print(f" Error decoding/processing message: {e}")

    consumer.close()
    print("✅ Consumer closed cleanly")
