from river import anomaly, preprocessing, compose

def build_hst_model():
    """Builds a Half-Space Trees anomaly detector with preprocessing."""
    return compose.Pipeline(
        preprocessing.MinMaxScaler(),  # required for HST
        anomaly.QuantileFilter(
            anomaly.HalfSpaceTrees(
            n_trees=25,
            height=8,
            window_size=250,
            seed=42
            ),
            q=0.95
        )
    )

