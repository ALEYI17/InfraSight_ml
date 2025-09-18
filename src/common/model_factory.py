import os
from src.common.model_hst import build_hst_model
from src.common.model_ocsvm import build_ocsvm_model

def get_model(defaultModel):
    model_name = os.getenv("ML_MODEL", defaultModel).lower()

    if model_name == "hst":
        print("✅ Using Half-Space Trees model")
        return build_hst_model()
    elif model_name == "ocsvm":
        print("✅ Using One-Class SVM model")
        return build_ocsvm_model()
    else:
        raise ValueError(f"❌ Unknown model: {model_name}")
