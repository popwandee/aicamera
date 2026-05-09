"""
DualBranchLPRNet — Thai License Plate Recognition  (Phase 3)
=============================================================
Architecture:
  Shared backbone  : ResNet18 (pretrained ImageNet), truncated at layer2
                     Output: (B, 128, 10, 38) for input (B, 3, 75, 300)
  Channel projection: Conv2d(128→512, 1×1) + GN + ReLU
                     Output: (B, 512, 10, 38)

  Branch 1 — CTC (consonants + digits):
    feat_top = features[:, :, :5, :]          (B, 512, 5, 38)  — top half of feature map
    → mean over height dim → (B, 512, 38)
    → Conv1d head → (B, LPR_NUM_CLASSES, 38)   CTC logits

  Branch 2 — Province Classifier:
    feat_gap = features.mean(dim=[2,3])        (B, 512)         — global avg pool
    → Linear(512, N_PROVINCES)                (B, N_PROVINCES)  classification logits

Rationale:
  - Province text occupies the bottom row of the plate.
    Using full feature map for province (not just bottom slice) because
    height=10 is too small to reliably split at 5 for province alone.
  - CTC branch uses only top-half features to reduce province interference.
  - Province classification (77 classes) is far easier than CTC decoding
    of province names — no vowel/tone ambiguity at low resolution.

LPR character set (Branch 1):
  CHARS[0:10]  — digits  0-9       (indices 0-9)
  CHARS[10:48] — Thai consonants   (indices 10-47)
  LPR_BLANK    = 48
  LPR_NUM_CLASSES = 49
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models as tvm

from charset import CHARS, BLANK_LABEL, NUM_CLASSES
from province_map import N_PROVINCES, UNKNOWN_PROV

# ── LPR-only charset (consonants + digits, no vowels) ────────────────────────
LPR_CHARS       = CHARS[:48]          # digits[0:10] + consonants[10:48]
LPR_BLANK       = 48
LPR_NUM_CLASSES = 49                  # 48 chars + 1 blank


def _gn(channels: int) -> nn.GroupNorm:
    for g in [8, 4, 2, 1]:
        if channels % g == 0:
            return nn.GroupNorm(g, channels)
    return nn.GroupNorm(1, channels)


# ── Model ─────────────────────────────────────────────────────────────────────

class DualBranchLPRNet(nn.Module):
    """
    Input:  (B, 3, 75, 300)
    Output: (lpr_logits: (B, LPR_NUM_CLASSES, 38),
             prov_logits: (B, N_PROVINCES))
    """

    def __init__(self, dropout_rate: float = 0.3, n_provinces: int = N_PROVINCES):
        super().__init__()

        # ── Shared backbone: ResNet18 truncated at layer2 ────────────────────
        # Spatial trace for (B, 3, 75, 300):
        #   conv1  7×7 s2  → (B, 64,  38, 150)
        #   maxpool 3×3 s2 → (B, 64,  19,  75)
        #   layer1 s1      → (B, 64,  19,  75)
        #   layer2 s2      → (B, 128, 10,  38)   ← output used
        resnet = tvm.resnet18(weights=tvm.ResNet18_Weights.IMAGENET1K_V1)
        self.feature_extractor = nn.Sequential(
            resnet.conv1,
            resnet.bn1,
            resnet.relu,
            resnet.maxpool,
            resnet.layer1,
            resnet.layer2,
        )

        # ── Channel projection: 128 → 512 ────────────────────────────────────
        self.proj = nn.Sequential(
            nn.Conv2d(128, 512, kernel_size=1, bias=False),
            _gn(512),
            nn.ReLU(inplace=True),
        )

        # ── CTC head (Branch 1) ───────────────────────────────────────────────
        # Input: (B, 512, 38)  [after height-mean of top-half features]
        self.lpr_head = nn.Sequential(
            nn.Conv1d(512, 256, kernel_size=1, bias=False),
            nn.GroupNorm(8, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout_rate),
            nn.Conv1d(256, LPR_NUM_CLASSES, kernel_size=1),
        )

        # ── Province head (Branch 2) ──────────────────────────────────────────
        # Input: (B, 512)  [after global average pool]
        self.province_head = nn.Sequential(
            nn.Dropout(dropout_rate),
            nn.Linear(512, n_provinces),
        )

        self._init_new_weights()

    def _init_new_weights(self):
        """Initialise only the new layers (proj + heads); backbone keeps pretrained weights."""
        for m in [self.proj, self.lpr_head, self.province_head]:
            for layer in m.modules():
                if isinstance(layer, (nn.Conv2d, nn.Conv1d)):
                    nn.init.kaiming_normal_(layer.weight, mode='fan_out', nonlinearity='relu')
                    if layer.bias is not None:
                        nn.init.constant_(layer.bias, 0)
                elif isinstance(layer, (nn.GroupNorm,)):
                    nn.init.constant_(layer.weight, 1)
                    nn.init.constant_(layer.bias, 0)
                elif isinstance(layer, nn.Linear):
                    nn.init.xavier_uniform_(layer.weight)
                    if layer.bias is not None:
                        nn.init.constant_(layer.bias, 0)

    def forward(self, x: torch.Tensor):
        feat = self.feature_extractor(x)   # (B, 128, 10, 38)
        feat = self.proj(feat)             # (B, 512, 10, 38)

        # CTC branch — top 5 rows of feature map (≈ top half of plate image)
        feat_top = feat[:, :, :5, :]       # (B, 512,  5, 38)
        feat_top = feat_top.mean(dim=2)    # (B, 512,     38)
        lpr_logits = self.lpr_head(feat_top)   # (B, LPR_NUM_CLASSES, 38)

        # Province branch — global average pool over full feature map
        feat_gap = feat.mean(dim=[2, 3])        # (B, 512)
        prov_logits = self.province_head(feat_gap)  # (B, N_PROVINCES)

        return lpr_logits, prov_logits


# ── CTC Loss (LPR branch only) ────────────────────────────────────────────────

class LPRCTCLoss(nn.Module):
    """CTC loss for LPR branch.  blank=LPR_BLANK (not BLANK_LABEL from charset)."""

    def __init__(self):
        super().__init__()
        self.ctc = nn.CTCLoss(blank=LPR_BLANK, reduction='mean', zero_infinity=True)

    def forward(self, logits, targets, target_lengths):
        logits_t  = logits.permute(2, 0, 1).float()     # (T, B, C)
        log_probs = F.log_softmax(logits_t, dim=2)
        T, B      = log_probs.shape[:2]
        input_lens = torch.full((B,), T, dtype=torch.long, device=logits.device)
        targets_flat = torch.cat(
            [targets[i, :target_lengths[i]] for i in range(B)]
        )
        return self.ctc(log_probs, targets_flat, input_lens, target_lengths)


# ── CTC decoder (LPR branch) ──────────────────────────────────────────────────

def lpr_ctc_decode(logits: torch.Tensor) -> list:
    """Greedy CTC decode for LPR branch.  Returns list[list[int]] of char indices."""
    predictions = []
    for b in range(logits.size(0)):
        seq  = logits[b].argmax(dim=0).tolist()
        prev, pred = -1, []
        for label in seq:
            if label != LPR_BLANK and label != prev:
                pred.append(label)
            prev = label
        predictions.append(pred)
    return predictions


def lpr_decode_to_string(indices: list) -> str:
    """Convert LPR index list → consonants+digits string."""
    return ''.join(LPR_CHARS[i] for i in indices if 0 <= i < len(LPR_CHARS))


if __name__ == '__main__':
    model = DualBranchLPRNet()
    total = sum(p.numel() for p in model.parameters())
    print(f'DualBranchLPRNet  params: {total:,}')
    x = torch.randn(2, 3, 75, 300)
    lpr, prov = model(x)
    print(f'  lpr_logits  : {tuple(lpr.shape)}   (expect [2, {LPR_NUM_CLASSES}, 38])')
    print(f'  prov_logits : {tuple(prov.shape)}   (expect [2, {N_PROVINCES}])')
