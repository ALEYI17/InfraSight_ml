import os

def get_config(topicDefault):
    """Read configuration from environment variables with sensible defaults."""

    return {
        # ML model selection (hst | ocsvm)
        "ml_model": os.getenv("ML_MODEL", "hst").lower(),

        # Kafka settings
        "kafka": {
            "broker": os.getenv("KAFKA_BROKER", "localhost:9092"),
            "topic": os.getenv("KAFKA_TOPIC", topicDefault),
            "auto_offset_reset": os.getenv("KAFKA_AUTO_OFFSET_RESET", "earliest"),
        },

        # Warm-up settings
        "warmup": {
            "size": int(os.getenv("WARMUP_SIZE", "3000")),
            "time": int(os.getenv("WARMUP_TIME", "240")),  # seconds
            "size_per_container": int(os.getenv("WARMUP_SIZE_PC","50")),
        },

        # Logging / alerts
        "log_level": os.getenv("LOG_LEVEL", "info"),
    }
