"""
Training script for DualBranchLPRNet — Phase 3
===============================================================
Changes from train_lprnet.py:
  - Uses DualBranchLPRNet (ResNet18 backbone + CTC + Province classifier)
  - Dataset returns province label extracted from filename
  - Loss = CTC_loss + province_weight * CrossEntropy_province
  - Validation reports: plate acc, char acc, province acc
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim
from torch.cuda.amp import GradScaler, autocast
from torch.utils.data import Dataset, DataLoader
import torchvision.transforms as transforms
from tqdm import tqdm
from PIL import Image

from lprnet_dual_branch import (
    DualBranchLPRNet, LPRCTCLoss, lpr_ctc_decode, lpr_decode_to_string,
    LPR_CHARS, LPR_BLANK, LPR_NUM_CLASSES,
)
from charset import CHARS, CHAR_TO_IDX, BLANK_LABEL
from province_map import (
    PROVINCES, PROVINCE_TO_IDX, N_PROVINCES, UNKNOWN_PROV, province_label,
)
from train_lprnet import unroll_plate   # reuse unroll_plate from single-branch script


# ── Early Stopping ────────────────────────────────────────────────────────────

class EarlyStopping:
    """Stop training when val_loss has not improved for `patience` consecutive epochs."""

    def __init__(self, patience: int = 10, min_delta: float = 1e-4):
        self.patience   = patience
        self.min_delta  = min_delta
        self.counter    = 0
        self.best_loss  = float('inf')

    def step(self, val_loss: float) -> bool:
        """Return True if training should stop."""
        if val_loss < self.best_loss - self.min_delta:
            self.best_loss = val_loss
            self.counter   = 0
        else:
            self.counter += 1
        return self.counter >= self.patience


# ── Dataset ───────────────────────────────────────────────────────────────────

# LPR charset: digits (0-9) + Thai consonants (10-47) — no vowels in LPR branch
LPR_CHAR_TO_IDX = {c: i for i, c in enumerate(LPR_CHARS)}


class DualBranchDataset(Dataset):
    """
    Thai License Plate Dataset for dual-branch training.
    Returns image, lpr_target (consonants+digits only), province_label.
    """

    def __init__(self, img_dir, img_size=(75, 300), is_train=False):
        self.img_dir     = Path(img_dir)
        self.img_size    = img_size
        self.is_train    = is_train
        self.image_files = sorted([
            f for f in self.img_dir.iterdir()
            if f.suffix.lower() in ('.jpg', '.png')
        ])
        if not self.image_files:
            raise ValueError(f"No images found in {img_dir}")
        mode = "train+aug" if is_train else "val"
        print(f"  ✓ {len(self.image_files):,} images  [{mode}]  ←  {img_dir}")

    def __len__(self):
        return len(self.image_files)

    def __getitem__(self, idx):
        img_path = self.image_files[idx]

        img = Image.open(img_path).convert('RGB')
        img = unroll_plate(img)
        img = img.resize((self.img_size[1], self.img_size[0]), Image.BILINEAR)

        if self.is_train:
            img = transforms.RandomPerspective(distortion_scale=0.15, p=0.4)(img)
            img = transforms.RandomRotation(degrees=4)(img)
            img = transforms.ColorJitter(brightness=0.35, contrast=0.35, saturation=0.25)(img)
            img = transforms.GaussianBlur(kernel_size=3, sigma=(0.1, 1.5))(img)

        img_t = transforms.ToTensor()(img)
        img_t = transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5])(img_t)

        if self.is_train:
            img_t = transforms.RandomErasing(p=0.15, scale=(0.02, 0.08), ratio=(0.3, 3.0))(img_t)

        # Parse filename → full plate text
        parts = img_path.stem.split('_')
        if len(parts) >= 2 and parts[-1].isdigit() and len(parts[-1]) == 6:
            plate_text = ''.join(parts[:-1])
        else:
            plate_text = img_path.stem

        # LPR target: consonants + digits only (no vowels)
        lpr_indices = [LPR_CHAR_TO_IDX[c] for c in plate_text if c in LPR_CHAR_TO_IDX]
        lpr_target  = torch.tensor(lpr_indices, dtype=torch.long)

        # Province label
        prov_idx = province_label(plate_text)   # int, -1 if unknown

        return {
            'image':        img_t,
            'lpr_target':   lpr_target,
            'prov_label':   prov_idx,
            'plate_text':   plate_text,
            'filename':     img_path.name,
        }


def collate_fn(batch):
    images       = torch.stack([b['image'] for b in batch])
    lpr_targets  = [b['lpr_target'] for b in batch]
    lpr_lengths  = torch.tensor([len(t) for t in lpr_targets], dtype=torch.long)
    prov_labels  = torch.tensor([b['prov_label'] for b in batch], dtype=torch.long)

    max_len = max(len(t) for t in lpr_targets)
    padded  = torch.stack([
        torch.cat([t, torch.full((max_len - len(t),), LPR_BLANK, dtype=torch.long)])
        for t in lpr_targets
    ])

    return {
        'images':      images,
        'lpr_targets': padded,
        'lpr_lengths': lpr_lengths,
        'prov_labels': prov_labels,
        'plate_texts': [b['plate_text'] for b in batch],
        'filenames':   [b['filename']   for b in batch],
    }


# ── Training epoch ────────────────────────────────────────────────────────────

def train_epoch(model, loader, optimizer, scaler, device, epoch, log_file, prov_weight):
    model.train()
    ctc_fn   = LPRCTCLoss()
    ce_fn    = nn.CrossEntropyLoss(ignore_index=UNKNOWN_PROV)
    total_loss = nan_batches = 0

    progress = tqdm(loader, desc=f"Train  epoch {epoch:3d}")
    for batch_idx, batch in enumerate(progress):
        images      = batch['images'].to(device, non_blocking=True)
        lpr_targets = batch['lpr_targets'].to(device, non_blocking=True)
        lpr_lengths = batch['lpr_lengths'].to(device, non_blocking=True)
        prov_labels = batch['prov_labels'].to(device, non_blocking=True)

        optimizer.zero_grad(set_to_none=True)

        with autocast(enabled=(device.type == 'cuda')):
            lpr_logits, prov_logits = model(images)

        ctc_loss  = ctc_fn(lpr_logits, lpr_targets, lpr_lengths)
        prov_loss = ce_fn(prov_logits, prov_labels)
        loss      = ctc_loss + prov_weight * prov_loss

        if torch.isnan(loss) or torch.isinf(loss):
            nan_batches += 1
            if nan_batches <= 5:
                print(f"\n  ⚠  NaN/inf loss at batch {batch_idx}")
            continue

        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
        scaler.step(optimizer)
        scaler.update()

        total_loss += loss.item()
        progress.set_postfix({'loss': f'{loss.item():.4f}',
                              'ctc': f'{ctc_loss.item():.3f}',
                              'prov': f'{prov_loss.item():.3f}'})

    avg_loss = total_loss / max(len(loader) - nan_batches, 1)
    msg = f"Epoch {epoch:3d} | Train Loss: {avg_loss:.4f}"
    print(msg)
    with open(log_file, 'a') as f:
        f.write(msg + '\n')
    return avg_loss


# ── Validation ────────────────────────────────────────────────────────────────

def validate(model, loader, device, epoch, log_file, prov_weight):
    model.eval()
    ctc_fn   = LPRCTCLoss()
    ce_fn    = nn.CrossEntropyLoss(ignore_index=UNKNOWN_PROV)

    total_loss     = 0.0
    correct_plates = correct_chars = correct_prov = 0
    total_samples  = total_chars   = total_prov   = 0

    with torch.no_grad():
        progress = tqdm(loader, desc=f"  Val  epoch {epoch:3d}")
        for batch in progress:
            images      = batch['images'].to(device, non_blocking=True)
            lpr_targets = batch['lpr_targets'].to(device, non_blocking=True)
            lpr_lengths = batch['lpr_lengths'].to(device, non_blocking=True)
            prov_labels = batch['prov_labels'].to(device, non_blocking=True)

            with autocast(enabled=(device.type == 'cuda')):
                lpr_logits, prov_logits = model(images)

            ctc_loss  = ctc_fn(lpr_logits, lpr_targets, lpr_lengths)
            prov_loss = ce_fn(prov_logits, prov_labels)
            loss      = ctc_loss + prov_weight * prov_loss
            if not (torch.isnan(loss) or torch.isinf(loss)):
                total_loss += loss.item()

            # LPR accuracy
            preds = lpr_ctc_decode(lpr_logits.float().cpu())
            for i, pred in enumerate(preds):
                gt = lpr_targets[i, :lpr_lengths[i]].cpu().tolist()
                if pred == gt:
                    correct_plates += 1
                total_samples += 1
                min_len = min(len(pred), len(gt))
                correct_chars += sum(1 for j in range(min_len) if pred[j] == gt[j])
                total_chars   += max(len(pred), len(gt))

            # Province accuracy (ignore unknowns)
            prov_preds = prov_logits.argmax(dim=1).cpu()
            prov_gt    = prov_labels.cpu()
            mask       = prov_gt != UNKNOWN_PROV
            correct_prov += (prov_preds[mask] == prov_gt[mask]).sum().item()
            total_prov   += mask.sum().item()

    avg_loss   = total_loss  / max(len(loader), 1)
    plate_acc  = 100.0 * correct_plates / max(total_samples, 1)
    char_acc   = 100.0 * correct_chars  / max(total_chars,   1)
    prov_acc   = 100.0 * correct_prov   / max(total_prov,    1)

    msg = (f"Epoch {epoch:3d} | Val Loss: {avg_loss:.4f} "
           f"| Plate Acc: {plate_acc:.2f}% | Char Acc: {char_acc:.2f}% "
           f"| Prov Acc: {prov_acc:.2f}%")
    print(msg)
    with open(log_file, 'a') as f:
        f.write(msg + '\n')
    return avg_loss, plate_acc, char_acc, prov_acc


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Train DualBranchLPRNet')
    parser.add_argument('--train_dir',        required=True)
    parser.add_argument('--test_dir',         required=True)
    parser.add_argument('--max_epochs',       type=int,   default=150)
    parser.add_argument('--train_batch_size', type=int,   default=32)
    parser.add_argument('--test_batch_size',  type=int,   default=32)
    parser.add_argument('--learning_rate',    type=float, default=5e-4)
    parser.add_argument('--weight_decay',     type=float, default=1e-4)
    parser.add_argument('--dropout_rate',     type=float, default=0.3)
    parser.add_argument('--prov_weight',      type=float, default=0.3,
                        help='Weight for province CE loss (0 = disable)')
    parser.add_argument('--output_dir',   default='/mnt/pwd-data/runs/lprnet_dual')
    parser.add_argument('--device',       default='cuda' if torch.cuda.is_available() else 'cpu')
    parser.add_argument('--num_workers',  type=int,  default=4)
    parser.add_argument('--no_amp',       action='store_true')
    parser.add_argument('--es_patience',  type=int, default=10,
                        help='Early-stopping patience on val_loss (0 = disabled)')
    args = parser.parse_args()

    out_dir  = Path(args.output_dir)
    ckpt_dir = out_dir / 'checkpoints'
    out_dir.mkdir(parents=True, exist_ok=True)
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    log_file = out_dir / 'training.log'
    with open(log_file, 'w') as f:
        f.write(f"DualBranchLPRNet training  {datetime.now()}\n")
        f.write("=" * 80 + "\n")
        for k, v in vars(args).items():
            f.write(f"  {k}: {v}\n")
        f.write("=" * 80 + "\n")

    device  = torch.device(args.device)
    use_amp = (device.type == 'cuda') and not args.no_amp
    scaler  = GradScaler(enabled=use_amp)
    print(f"Device: {device}  |  AMP: {'enabled' if use_amp else 'disabled'}")

    print("\nLoading datasets…")
    train_ds = DualBranchDataset(args.train_dir, is_train=True)
    test_ds  = DualBranchDataset(args.test_dir,  is_train=False)

    train_loader = DataLoader(train_ds, batch_size=args.train_batch_size,
                              shuffle=True,  num_workers=args.num_workers,
                              collate_fn=collate_fn, pin_memory=True, drop_last=True)
    test_loader  = DataLoader(test_ds,  batch_size=args.test_batch_size,
                              shuffle=False, num_workers=args.num_workers,
                              collate_fn=collate_fn, pin_memory=True)

    print("\nInitialising model…")
    model = DualBranchLPRNet(
        dropout_rate=args.dropout_rate,
        n_provinces=N_PROVINCES,
    ).to(device)

    total_params = sum(p.numel() for p in model.parameters())
    print(f"Parameters: {total_params:,}")

    # Lower LR for pretrained backbone; higher for new heads
    backbone_params = list(model.feature_extractor.parameters())
    head_params     = (list(model.proj.parameters()) +
                       list(model.lpr_head.parameters()) +
                       list(model.province_head.parameters()))
    optimizer = optim.AdamW([
        {'params': backbone_params, 'lr': args.learning_rate * 0.1},
        {'params': head_params,     'lr': args.learning_rate},
    ], weight_decay=args.weight_decay)

    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', patience=15, factor=0.5, min_lr=1e-6,
    )

    early_stopping = EarlyStopping(patience=args.es_patience) if args.es_patience > 0 else None

    print("\nStarting training…\n")
    best_plate_acc = 0.0
    stats = {
        'start_time': datetime.now().isoformat(),
        'args':       vars(args),
        'epochs':     [],
    }

    for epoch in range(1, args.max_epochs + 1):
        train_loss = train_epoch(
            model, train_loader, optimizer, scaler,
            device, epoch, log_file, args.prov_weight,
        )
        val_loss, plate_acc, char_acc, prov_acc = validate(
            model, test_loader, device, epoch, log_file, args.prov_weight,
        )
        scheduler.step(val_loss)

        current_lr = optimizer.param_groups[0]['lr']
        stats['epochs'].append({
            'epoch':      epoch,
            'train_loss': float(train_loss),
            'val_loss':   float(val_loss),
            'plate_acc':  float(plate_acc),
            'char_acc':   float(char_acc),
            'prov_acc':   float(prov_acc),
            'lr':         float(current_lr),
        })

        ckpt_path = ckpt_dir / f'epoch_{epoch:03d}.pth'
        torch.save({
            'epoch':               epoch,
            'model_state_dict':    model.state_dict(),
            'optimizer_state_dict':optimizer.state_dict(),
            'train_loss':          train_loss,
            'val_loss':            val_loss,
            'plate_acc':           plate_acc,
            'char_acc':            char_acc,
            'prov_acc':            prov_acc,
        }, ckpt_path)

        if plate_acc > best_plate_acc:
            best_plate_acc = plate_acc
            torch.save(model.state_dict(), out_dir / 'best_model.pth')
            print(f"  🏆 Best  plate_acc={plate_acc:.2f}%  char_acc={char_acc:.2f}%"
                  f"  prov_acc={prov_acc:.2f}%  (epoch {epoch})")

        print(f"  LR backbone: {optimizer.param_groups[0]['lr']:.2e}"
              f"  heads: {optimizer.param_groups[1]['lr']:.2e}\n")

        if early_stopping is not None and early_stopping.step(val_loss):
            msg = (f"Early stopping triggered at epoch {epoch} "
                   f"(no val_loss improvement for {args.es_patience} consecutive epochs)")
            print(msg)
            with open(log_file, 'a') as f:
                f.write(msg + '\n')
            break

    stats['end_time']      = datetime.now().isoformat()
    stats['best_plate_acc'] = float(best_plate_acc)
    with open(out_dir / 'training_stats.json', 'w') as f:
        import json
        json.dump(stats, f, indent=2)

    print(f"\nTraining complete — best plate accuracy: {best_plate_acc:.2f}%")
    print(f"Checkpoints : {ckpt_dir}")


if __name__ == '__main__':
    main()
