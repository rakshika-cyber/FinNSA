import torch
import torch.nn as nn
import torch.nn.functional as F

class BilinearCoAttentiveGatedFusion(nn.Module):
    """
    Bilinear Co-Attentive Gated Fusion (BCGF) PyTorch Module.
    Fuses representations from English FinBERT and Hinglish (MuRIL/HingBERT) branches.
    """
    def __init__(self, embed_dim: int = 768, hidden_dim: int = 256, num_classes: int = 3, dropout_prob: float = 0.2):
        super(BilinearCoAttentiveGatedFusion, self).__init__()
        
        self.embed_dim = embed_dim
        self.hidden_dim = hidden_dim
        
        # Linear projections for English and Hinglish embeddings if dimension scaling is needed
        self.proj_eng = nn.Linear(embed_dim, hidden_dim)
        self.proj_hing = nn.Linear(embed_dim, hidden_dim)
        
        # Bilinear Co-Attention Weight Matrix W_bilinear: (hidden_dim x hidden_dim)
        self.W_bilinear = nn.Parameter(torch.Tensor(hidden_dim, hidden_dim))
        nn.init.xavier_uniform_(self.W_bilinear)
        
        # Co-Attention transformation layers
        self.attn_eng = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.Tanh()
        )
        self.attn_hing = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.Tanh()
        )
        
        # Adaptive Gating Mechanism:
        # Input concatenation: [C_eng, C_hing, C_eng * C_hing, |C_eng - C_hing|] -> size = 4 * hidden_dim
        self.gate_fc = nn.Sequential(
            nn.Linear(4 * hidden_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout_prob),
            nn.Linear(hidden_dim, hidden_dim),
            nn.Sigmoid()
        )
        
        # Feature transformation before gating
        self.trans_eng = nn.Linear(hidden_dim, hidden_dim)
        self.trans_hing = nn.Linear(hidden_dim, hidden_dim)
        
        # Final classification head: Fused representation -> Sentiment Logits (Positive/Neutral/Negative) + Fused continuous score
        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim, 128),
            nn.LayerNorm(128),
            nn.ReLU(),
            nn.Dropout(dropout_prob),
            nn.Linear(128, num_classes)
        )
        
        self.score_head = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
            nn.Tanh()  # Produces score in range [-1.0, 1.0] (Bearish to Bullish)
        )

    def forward(self, h_eng: torch.Tensor, h_hing: torch.Tensor):
        """
        Forward pass for BCGF.
        Args:
            h_eng: Tensor of shape (batch_size, embed_dim)
            h_hing: Tensor of shape (batch_size, embed_dim)
        Returns:
            dict containing logits, sentiment probabilities, fused continuous score, and gate weights
        """
        # Ensure 2D tensor shape (batch_size, embed_dim)
        if h_eng.dim() == 1:
            h_eng = h_eng.unsqueeze(0)
        if h_hing.dim() == 1:
            h_hing = h_hing.unsqueeze(0)
            
        # 1. Project to common hidden dimension
        e_eng = F.relu(self.proj_eng(h_eng))    # (batch_size, hidden_dim)
        e_hing = F.relu(self.proj_hing(h_hing))  # (batch_size, hidden_dim)
        
        # 2. Bilinear Co-Attention Score
        # Bilinear mapping: e_eng @ W_bilinear @ e_hing.T
        bilinear_matrix = torch.matmul(e_eng, self.W_bilinear) # (batch_size, hidden_dim)
        co_attn_weights = torch.sigmoid(torch.sum(bilinear_matrix * e_hing, dim=-1, keepdim=True)) # (batch_size, 1)
        
        # Apply co-attention weights to contextual representations
        c_eng = e_eng + co_attn_weights * self.attn_eng(e_eng)
        c_hing = e_hing + (1.0 - co_attn_weights) * self.attn_hing(e_hing)
        
        # 3. Adaptive Gated Fusion
        concat_features = torch.cat([c_eng, c_hing, c_eng * c_hing, torch.abs(c_eng - c_hing)], dim=-1)
        g = self.gate_fc(concat_features) # Gate value (batch_size, hidden_dim) between 0 and 1
        
        # Gated fusion combination
        h_fused = g * self.trans_eng(c_eng) + (1.0 - g) * self.trans_hing(c_hing)
        
        # 4. Classification & Fused Sentiment Score
        logits = self.classifier(h_fused)
        probs = F.softmax(logits, dim=-1)
        score = self.score_head(h_fused).squeeze(-1) # [-1.0, 1.0]
        
        return {
            "logits": logits,
            "probabilities": probs,
            "fused_score": score,
            "gate_weights": g
        }
