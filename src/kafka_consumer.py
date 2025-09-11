import signal
import time
from confluent_kafka import Consumer, KafkaException
from src.proto import ebpf_event_pb2
from src.model_factory import get_model


# === Config ===
KAFKA_BROKER = "localhost:9092"
KAFKA_TOPIC = "resource"
KAFKA_GROUP = "hst-anomaly-detector"

# === Model ===
model = get_model()

# === Graceful shutdown ===
running = True
def shutdown(sig, frame):
    global running
    running = False
    print("Shutting down...")
signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

# === Kafka consumer setup ===
conf = {
    "bootstrap.servers": KAFKA_BROKER,
    "group.id": KAFKA_GROUP,
    "auto.offset.reset": "earliest"
}

consumer = Consumer(conf)
consumer.subscribe([KAFKA_TOPIC])

# Warm-up parameters
WARMUP_SIZE = 3000
WARMUP_TIME = 240  # seconds
count = 0
start_time = time.time()

print(f"Listening on topic {KAFKA_TOPIC}...")

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
                    print(f"🔥 Warm-up: {count} events, {elapsed:.1f}s elapsed")
            else:
                score = model.score_one(features)
                is_anomaly = model["QuantileFilter"].classify(score)
                model.learn_one(features)
                if is_anomaly:
                    print(f"🚨 ALERT: anomaly detected "
                        f"Score={score:.4f} [PID={event.pid} | COMM={event.comm}]")
    except Exception as e:
            print(f"⚠️ Error decoding/processing message: {e}")
consumer.close()
print("✅ Consumer closed cleanly")
