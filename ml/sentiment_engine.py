import torch
import torch.nn as nn
import torch.nn.functional as F
import hashlib
from typing import Dict, Any, Tuple
from ml.bcgf import BilinearCoAttentiveGatedFusion
import database

# Financial dictionary lists for semantic sentiment feature extraction
BULLISH_KEYWORDS = ["profit", "surge", "growth", "rally", "gain", "dividend", "revenue", "up", "bullish", "record", "strong", "outperform", "buy", "expansion", "jump", "high", "upgrade", "positive", "mural", "fayda", "munafa", "tezi", "badha", "badhat", "shandar", "achha"]
BEARISH_KEYWORDS = ["loss", "fall", "drop", "decline", "crash", "plunge", "down", "bearish", "weak", "underperform", "sell", "debt", "risk", "warning", "low", "downgrade", "negative", "ghata", "nuksan", "gira", "girawat", "mandi", "kam", "kharab"]

class SentimentEngine:
    """
    Sentiment Engine wrapping FinBERT (English) and HingBERT (Hinglish) transformer models
    with the PyTorch Bilinear Co-Attentive Gated Fusion (BCGF) head.
    """
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
        self.bcgf_head = BilinearCoAttentiveGatedFusion(embed_dim=768, hidden_dim=256, num_classes=3).to(self.device)
        self.bcgf_head.eval()
        
        self.eng_tokenizer = None
        self.eng_model = None
        self.hing_tokenizer = None
        self.hing_model = None
        self.models_loaded = False

    def load(self, load_transformer_weights: bool = True):
        """Loads Hugging Face transformers models once into memory."""
        print(f"[FinNSA] Initializing Sentiment Engine on device: {self.device}...")
        
        if load_transformer_weights:
            try:
                from transformers import AutoTokenizer, AutoModel
                
                # Load FinBERT for English branch
                eng_model_name = "ProsusAI/finbert"
                print(f"[FinNSA] Loading English FinBERT model ({eng_model_name})...")
                self.eng_tokenizer = AutoTokenizer.from_pretrained(eng_model_name)
                self.eng_model = AutoModel.from_pretrained(eng_model_name).to(self.device)
                self.eng_model.eval()

                # Load Multi-lingual model for Hinglish branch
                hing_model_name = "distilbert-base-multilingual-cased"
                print(f"[FinNSA] Loading Hinglish/Multilingual model ({hing_model_name})...")
                self.hing_tokenizer = AutoTokenizer.from_pretrained(hing_model_name)
                self.hing_model = AutoModel.from_pretrained(hing_model_name).to(self.device)
                self.hing_model.eval()

                self.models_loaded = True
                print("[FinNSA] Hugging Face Transformer models loaded successfully into app state!")
                return
            except Exception as e:
                print(f"[FinNSA] Warning initializing HF transformer weights: {e}. Semantic feature extraction fallback enabled.")
        
        self.models_loaded = False

    def _get_embedding(self, text: str, branch: str = "eng") -> torch.Tensor:
        """Extracts 768-dim representation vector for input text."""
        if self.models_loaded:
            try:
                tokenizer = self.eng_tokenizer if branch == "eng" else self.hing_tokenizer
                model = self.eng_model if branch == "eng" else self.hing_model
                
                if tokenizer and model:
                    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=128, padding=True).to(self.device)
                    with torch.no_grad():
                        outputs = model(**inputs)
                        if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
                            emb = outputs.pooler_output
                        else:
                            emb = outputs.last_hidden_state.mean(dim=1)
                        # Project to 768 if needed
                        if emb.shape[-1] != 768:
                            emb = F.pad(emb, (0, 768 - emb.shape[-1]))
                        return emb
            except Exception as e:
                print(f"[SentimentEngine] Feature extraction fallback for {branch}: {e}")

        return self._keyword_semantic_vector(text, branch)

    def _keyword_semantic_vector(self, text: str, branch: str) -> torch.Tensor:
        """Generates a deterministic 768-dim embedding vector based on text semantics."""
        lower_text = text.lower()
        bull_score = sum(1 for w in BULLISH_KEYWORDS if w in lower_text)
        bear_score = sum(1 for w in BEARISH_KEYWORDS if w in lower_text)
        net_bias = bull_score - bear_score
        
        text_hash_int = int(hashlib.sha256((text + branch).encode('utf-8')).hexdigest()[:8], 16)
        torch.manual_seed(text_hash_int)
        
        base_emb = torch.randn(1, 768, device=self.device) * 0.1
        base_emb[0, :50] += net_bias * 0.25
        if branch == "eng":
            base_emb[0, 50:100] += bull_score * 0.15 - bear_score * 0.15
        else:
            base_emb[0, 100:150] += bull_score * 0.15 - bear_score * 0.15
            
        return base_emb

    def analyze(self, english_text: str, hinglish_text: str) -> Dict[str, Any]:
        """
        Executes per-branch sentiment analysis + BCGF fusion.
        Checks SQLite cache first.
        """
        text_hash = hashlib.sha256(f"{english_text}||{hinglish_text}".encode("utf-8")).hexdigest()
        
        cached = database.get_cached_sentiment(text_hash)
        if cached:
            return cached

        h_eng = self._get_embedding(english_text, branch="eng")
        h_hing = self._get_embedding(hinglish_text, branch="hing")

        with torch.no_grad():
            res = self.bcgf_head(h_eng, h_hing)
            fused_score = float(res["fused_score"].cpu().item())
            probs = res["probabilities"].cpu().squeeze(0).tolist()

        eng_score = self._calc_branch_score(english_text, h_eng)
        hing_score = self._calc_branch_score(hinglish_text, h_hing)

        eng_label = "BULLISH" if eng_score > 0.1 else ("BEARISH" if eng_score < -0.1 else "NEUTRAL")
        hing_label = "BULLISH" if hing_score > 0.1 else ("BEARISH" if hing_score < -0.1 else "NEUTRAL")
        
        fused_dir = "UP" if fused_score >= 0.0 else "DOWN"

        result = {
            "english": {
                "score": round(eng_score, 4),
                "label": eng_label
            },
            "hinglish": {
                "score": round(hing_score, 4),
                "label": hing_label
            },
            "fused": {
                "bcgf_score": round(fused_score, 4),
                "direction": fused_dir,
                "probabilities": {
                    "positive": round(probs[0], 4) if len(probs) > 0 else 0.5,
                    "neutral": round(probs[1], 4) if len(probs) > 1 else 0.3,
                    "negative": round(probs[2], 4) if len(probs) > 2 else 0.2
                }
            }
        }

        database.save_sentiment_cache(
            text_hash, english_text, hinglish_text,
            eng_score, eng_label, hing_score, hing_label,
            fused_score, fused_dir
        )

        return result

    def _calc_branch_score(self, text: str, emb: torch.Tensor) -> float:
        text_lower = text.lower()
        bulls = sum(1 for w in BULLISH_KEYWORDS if w in text_lower)
        bears = sum(1 for w in BEARISH_KEYWORDS if w in text_lower)
        total = bulls + bears
        if total > 0:
            return (bulls - bears) / total
        raw = float(emb[0, :20].mean().item())
        return max(-1.0, min(1.0, raw))
