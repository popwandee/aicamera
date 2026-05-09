# GUARDRAIL.md — Safety Rules for Claude Code
> Claude Code MUST read and follow these rules before modifying any code.

---

## 🔴 HARD RULES (Never violate)

1. **Tag before touching** — `git tag stable-before-dualbranch-lpr` on aicamera1 BEFORE any code change.
2. **No credentials in code** — passwords, IPs, and `camera_id` stay in `.env`, never committed.
3. **Never modify vehicle/LP detection** — only the OCR step (Stage 3) is in scope.
4. **Never remove ThaiLPROCR fallback** — `DualBranchLPROCR` is a primary engine, ThaiLPROCR stays as backup.
5. **Never use PaddleOCR or EasyOCR** — both segfault on ARM64 / have large download issues.
6. **Always activate `edge/venv_hailo`** before running any Python on the device.
7. **Never `git push --force`** to main branch.

---

## 🟡 CAUTION RULES

8. **Device sharing** — DualBranchLPROCR uses `hailo_platform` directly alongside degirum.
   - OCR runs AFTER detection (sequential). Never run both simultaneously.
   - If `VDevice` open fails with "device busy", enable the Hailo multi-process service:
     ```bash
     hailortcli service start   # run once; persists across reboots with systemd
     ```

9. **Character/Province vocabulary** — `LPR_CHARS` and `THAI_PROVINCES_SORTED` in
   `dual_branch_lpr_ocr.py` MUST match the training labels exactly.
   - If output looks garbled, check character ordering first.
   - Add a `--verify-vocab` flag test before integrating into production.

10. **CTC blank index** — default is index 0. Some training configs put blank at last index (47).
    If all output is empty, try `CTC_BLANK_IDX = 47` in `dual_branch_lpr_ocr.py`.

11. **Input normalization** — HEF is compiled with quantization. Pass raw uint8 (0–255) with
    `quantized=True, format_type=FormatType.UINT8`. Do NOT divide by 255 before passing.

12. **Preprocessing channel order** — preprocess_for_lprnet() converts BGR→RGB before resize.
    Hailo models compiled from ONNX (trained on ImageNet-normalized data) expect RGB.

---

## 🟢 ALLOWED CHANGES

- Create new files in `edge/src/components/`
- Modify `parallel_ocr_processor.py` to accept `dual_branch_ocr` parameter
- Modify `detection_processor.py` load_models() and cleanup() only
- Update `.env` / `.env.example` to add `DUALBRANCH_HEF_PATH`
- Update `edge/CLAUDE.md` to document the new pipeline

---

## Rollback Procedure
```bash
# On aicamera1:
cd /home/camuser/aicamera
git stash          # save uncommitted changes
git checkout stable-before-dualbranch-lpr
sudo systemctl restart aicamera_lpr.service
# Verify old pipeline is running:
sudo journalctl -u aicamera_lpr -n 30
```

---

## Test Checklist (before declaring success)
- [ ] `python3 test_dual_branch_lpr.py` passes all 4 checks on aicamera1
- [ ] CTC character vocabulary verified against training labels
- [ ] Province vocabulary verified against training labels
- [ ] `ocr_method` field in SQLite shows `dualbranch` for real plates
- [ ] ThaiLPROCR still used when DualBranchLPROCR returns empty
- [ ] Service starts cleanly: `sudo systemctl start aicamera_lpr.service`
- [ ] No `VDevice` device-busy errors in `/var/log/aicamera/edge.log`
- [ ] Latency per plate ≤ 20ms on Hailo-8 (check `processing_time` in logs)
