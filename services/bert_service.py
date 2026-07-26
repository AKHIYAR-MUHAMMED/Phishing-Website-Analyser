"""
PyTorch BERT / RoBERTa Sequence Transformer NLP Dedicated Microservice.
Exposes POST /models/bert/predict endpoint analyzing character and token embeddings.
"""

from typing import Dict, Any
from nlp_transformer import encode_url_semantics, get_bert_model


class BERTService:
    @staticmethod
    def predict(url: str) -> Dict[str, Any]:
        model = get_bert_model()
        res = encode_url_semantics(url)
        return {
            "model_name": "BERT / RoBERTa Sequence Transformer",
            "bert_threat_score": res["bert_threat_score"],
            "semantic_intent_verdict": res["semantic_intent_verdict"]
        }
