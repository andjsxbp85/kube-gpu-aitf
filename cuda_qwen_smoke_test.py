import os
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


MODEL_ID = os.getenv("MODEL_ID", "Qwen/Qwen2.5-0.5B-Instruct")
MAX_LENGTH = int(os.getenv("MAX_LENGTH", "128"))
STEPS = int(os.getenv("STEPS", "3"))
LR = float(os.getenv("LR", "2e-5"))


def print_cuda_info() -> str:
    print("=== CUDA CHECK ===")
    print(f"PyTorch version      : {torch.__version__}")
    print(f"CUDA available       : {torch.cuda.is_available()}")

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA tidak tersedia. Pastikan pod memang melihat GPU NVIDIA.")

    device = "cuda"
    gpu_name = torch.cuda.get_device_name(0)
    props = torch.cuda.get_device_properties(0)
    print(f"GPU name             : {gpu_name}")
    print(f"GPU total memory     : {props.total_memory / 1024**3:.2f} GB")
    print(f"CUDA device count    : {torch.cuda.device_count()}")

    x = torch.randn((2048, 2048), device=device)
    y = torch.randn((2048, 2048), device=device)
    torch.cuda.synchronize()
    start = time.time()
    z = x @ y
    torch.cuda.synchronize()
    elapsed = time.time() - start
    print(f"GPU matmul test      : OK ({elapsed:.4f}s)")
    print(f"Sample tensor mean   : {z.mean().item():.6f}")
    print()
    return device


def build_dataset():
    samples = [
        "User: Jelaskan apa itu GPU untuk training model.\nAssistant: GPU mempercepat operasi tensor dan backpropagation.",
        "User: Mengapa CUDA penting untuk deep learning?\nAssistant: CUDA memungkinkan komputasi paralel di GPU NVIDIA.",
        "User: Apa fungsi optimizer saat training?\nAssistant: Optimizer memperbarui bobot model untuk menurunkan loss.",
        "User: Mengapa batch kecil dipakai untuk uji coba?\nAssistant: Batch kecil lebih hemat memori dan cocok untuk smoke test.",
    ]
    return samples


def run_training(device: str) -> None:
    print("=== LOAD MODEL ===")
    print(f"Model ID             : {MODEL_ID}")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    dtype = torch.float16 if device == "cuda" else torch.float32
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        torch_dtype=dtype,
        trust_remote_code=True,
    )
    model.to(device)
    model.train()

    optimizer = torch.optim.AdamW(model.parameters(), lr=LR)
    texts = build_dataset()

    print("=== TRAINING SMOKE TEST ===")
    for step in range(STEPS):
        text = texts[step % len(texts)]
        batch = tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            padding="max_length",
            max_length=MAX_LENGTH,
        )
        batch = {k: v.to(device) for k, v in batch.items()}
        batch["labels"] = batch["input_ids"].clone()

        optimizer.zero_grad(set_to_none=True)
        outputs = model(**batch)
        loss = outputs.loss
        loss.backward()
        optimizer.step()

        allocated = torch.cuda.memory_allocated(0) / 1024**3
        reserved = torch.cuda.memory_reserved(0) / 1024**3
        print(
            f"step={step + 1}/{STEPS} "
            f"loss={loss.item():.4f} "
            f"allocated={allocated:.2f}GB "
            f"reserved={reserved:.2f}GB"
        )

    print()
    print("Training smoke test selesai.")
    print("Kesimpulan: CUDA aktif, model berhasil dimuat, dan backward/update berjalan.")


if __name__ == "__main__":
    active_device = print_cuda_info()
    run_training(active_device)
