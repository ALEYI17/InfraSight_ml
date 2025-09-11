from river import anomaly, preprocessing, compose

def build_ocsvm_model():
    """Builds a Half-Space Trees anomaly detector with preprocessing."""
    return compose.Pipeline(
            preprocessing.StandardScaler(),
            anomaly.QuantileFilter(
                anomaly.OneClassSVM(nu=0.2),
                q=0.95
                )
            )
