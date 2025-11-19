import signal
import json
import joblib
import numpy as np
import pandas as pd
from confluent_kafka import Consumer, KafkaException
from src.proto import gpu_event_pb2
from src.common.config import get_config

running = True


def shutdown(sig, frame):
    global running
    running = False
    print("Shutting down...")


def extract_features(tw: gpu_event_pb2.GpuTimeWindow, FEATURE_LIST) -> np.ndarray:
    feat = {}
    for key in FEATURE_LIST:
        if hasattr(tw, key):
            feat[key] = getattr(tw, key)
        else:
            feat[key] = 0.0
    df = pd.DataFrame([feat], columns=FEATURE_LIST)
    return df


def run_consumer():
    global running

    # === Config ===
    cfg = get_config("gpu_fingerprint")
    print(f"Loaded config: {cfg}")

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Load ML model
    rf = joblib.load("src/models/rf_model.pkl")
    scaler = joblib.load("src/models/scaler.pkl")

    MODEL_FEATURES = list(rf.feature_names_in_)

    conf = {
        "bootstrap.servers": cfg["kafka"]["broker"],
        "group.id": "rf-gpu-fingerprint",
        "auto.offset.reset": cfg["kafka"]["auto_offset_reset"],
    }

    consumer = Consumer(conf)
    consumer.subscribe([cfg["kafka"]["topic"]])
    print(f"Listening on topic {cfg['kafka']['topic']}...")

    while running:
        msg = consumer.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            raise KafkaException(msg.error())

        try:
            event = gpu_event_pb2.GpuEvent()
            event.ParseFromString(msg.value())

            if event.WhichOneof("payload") != "tw":
                continue

            # Extract × scale features
            features = extract_features(event.tw, MODEL_FEATURES)
            print(features)
            X_scaled_np = scaler.transform(features)
            X_scaled = pd.DataFrame(X_scaled_np, columns=MODEL_FEATURES)

            # Predictions
            pred = rf.predict(X_scaled)[0]
            prob = rf.predict_proba(X_scaled)[0][1]

            if pred == 1:
                print(
                    f"⚠️ Malign GPU event detected | "
                    f"prob={prob:.4f} | PID={event.pid} | COMM={event.comm}"
                )

        except Exception as e:
            print(f"Error decoding/processing message: {e}")

    consumer.close()
    print("Consumer closed cleanly")

