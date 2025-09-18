import signal
import time
from confluent_kafka import Consumer, KafkaException
from src.proto import ebpf_event_pb2
from src.common.model_factory import get_model
from src.common.config import get_config


# === Graceful shutdown ===
running = True
def shutdown(sig, frame):
    global running
    running = False
    print("Shutting down...")


def run_consumer():
    global running
    # === Config ===
    cfg = get_config("resource")
    print(f"✅ Loaded config: {cfg}")

    # === Model ===
    model = get_model("hst")

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # === Kafka consumer setup ===
    conf = {
        "bootstrap.servers": cfg["kafka"]["broker"],
        "group.id": "hst-anomaly-detector",
        "auto.offset.reset": cfg["kafka"]["auto_offset_reset"],
    }

    consumer = Consumer(conf)
    consumer.subscribe([cfg["kafka"]["topic"]])

    # Warm-up parameters
    WARMUP_SIZE = cfg["warmup"]["size"]
    WARMUP_TIME = cfg["warmup"]["time"]

    count = 0
    start_time = time.time()

    print(f"Listening on topic {cfg['kafka']['topic']}...")
    while running:
        msg = consumer.poll(1.0)  # timeout = 1s
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

                count +=1.0
                elapsed = time.time() - start_time
                in_warmup = count <= WARMUP_SIZE and elapsed < WARMUP_TIME

                if in_warmup:
                    model.learn_one(features)
                    if count % 100 == 0:
                        print(f"­ƒöÑ Warm-up: {count} events, {elapsed:.1f}s elapsed")
                else:
                    score = model.score_one(features)
                    is_anomaly = model["QuantileFilter"].classify(score)
                    model.learn_one(features)
                    if is_anomaly:
                        print(
                            f"­ƒÜ¿ ALERT: anomaly detected "
                            f"Score={score:.4f} | "
                            f"PID={event.pid} (PPID={event.ppid}) | COMM={event.comm} | USER={event.user} | UID={event.uid} | "
                            f"Container={event.container_id[:12]} ({event.container_image}) | "
                            f"Node={event.node_name} | "
                        )
        except Exception as e:
                print(f"ÔÜá´©Å Error decoding/processing message: {e}")
    consumer.close()
    print("Ô£à Consumer closed cleanly")
