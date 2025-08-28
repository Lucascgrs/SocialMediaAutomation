import argparse
import io
import os
import threading
from typing import Optional

import torch
from flask import Flask, request, jsonify, send_file

# Diffusers gère SD 1.5, SDXL, etc. via AutoPipelineForText2Image
from diffusers import AutoPipelineForText2Image

app = Flask(__name__)

pipe = None           # chargé après parsing des arguments
device = "cpu"
dtype = torch.float32
lock = threading.Lock()

DEFAULT_NEGATIVE = "low quality, blurry, deformed, watermark, text"
DEFAULT_STEPS = 28
DEFAULT_GUIDANCE = 7.0


def _round_to_multiple_of_8(x: int) -> int:
    return max(8, (x // 8) * 8)


@app.route("/health", methods=["GET"])
def health():
    ok = pipe is not None
    return jsonify({"ok": ok, "device": device, "dtype": str(dtype), "model_loaded": ok})


@app.route("/generate", methods=["POST"])
def generate_image():
    """
    JSON attendu:
    {
      "prompt": "a cinematic photo of ...",
      "negative_prompt": "optional",
      "height": 1024,
      "width": 1024,
      "num_inference_steps": 28,
      "guidance_scale": 7.0,
      "seed": 42,
      "return": "image" | "json",
      "save_path": "optional/path.png"
    }
    Réponse par défaut: image/png binaire
    Si return=json: {"saved_to": "..."} ou {"error": "..."}
    """
    if pipe is None:
        return jsonify({"error": "Model not loaded"}), 500

    data = request.get_json(silent=True) or {}
    prompt: Optional[str] = data.get("prompt")
    if not prompt:
        return jsonify({"error": "Missing 'prompt'"}), 400

    negative_prompt = data.get("negative_prompt", DEFAULT_NEGATIVE)
    height = int(data.get("height", 1024))
    width = int(data.get("width", 1024))
    num_inference_steps = int(data.get("num_inference_steps", DEFAULT_STEPS))
    guidance_scale = float(data.get("guidance_scale", DEFAULT_GUIDANCE))
    seed = data.get("seed", None)
    return_mode = data.get("return", "image")
    save_path = data.get("save_path", None)

    # Sécurité: SD/SDXL attend des dimensions multiples de 8
    h_adj = _round_to_multiple_of_8(height)
    w_adj = _round_to_multiple_of_8(width)
    if (h_adj, w_adj) != (height, width):
        height, width = h_adj, w_adj

    try:
        generator = torch.Generator(device=device)
        if seed is not None:
            generator = generator.manual_seed(int(seed))

        with lock, torch.inference_mode():
            out = pipe(
                prompt=prompt,
                negative_prompt=negative_prompt,
                height=height,
                width=width,
                num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale,
                generator=generator,
            )
            image = out.images[0]

        # Sauvegarde éventuelle
        if save_path:
            os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
            image.save(save_path)

        if return_mode == "json":
            resp = {"height": height, "width": width}
            if save_path:
                resp["saved_to"] = save_path
            else:
                # Pas de base64 par défaut pour garder la réponse légère
                resp["message"] = "Image generated (no save_path provided). Use return=image to get PNG bytes."
            return jsonify(resp)

        # Retour image/png binaire
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        buf.seek(0)
        return send_file(buf, mimetype="image/png")

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def load_model(model_id: str, use_cpu_offload: bool, enable_xformers: bool):
    global pipe, device, dtype

    has_cuda = torch.cuda.is_available()
    device = "cuda" if has_cuda and not use_cpu_offload else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32

    # Chargement unique des poids (mis en cache localement par Hugging Face)
    pipe = AutoPipelineForText2Image.from_pretrained(
        model_id,
        torch_dtype=dtype,
        use_safetensors=True,
    )

    if use_cpu_offload:
        # Déporte automatiquement les poids sur CPU quand pas utilisés
        pipe.enable_model_cpu_offload()
        device = "cuda" if has_cuda else "cpu"  # le générateur peut rester sur cuda si dispo
    else:
        if device == "cuda":
            pipe.to(device)
            if enable_xformers:
                try:
                    pipe.enable_xformers_memory_efficient_attention()
                except Exception:
                    # xFormers optionnel
                    pass
        else:
            pipe.enable_attention_slicing()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        default="stabilityai/stable-diffusion-xl-base-1.0",
        help="ID du modèle Diffusers (ex: runwayml/stable-diffusion-v1-5, stabilityai/stable-diffusion-xl-base-1.0)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host Flask")
    parser.add_argument("--port", type=int, default=5000, help="Port Flask")
    parser.add_argument("--cpu-offload", action="store_true", help="Réduire la VRAM en offloadant sur CPU (plus lent)")
    parser.add_argument("--xformers", action="store_true", help="Activer l'attention mémoire-efficiente (CUDA)")
    args = parser.parse_args()

    print(f"[INFO] Chargement du modèle: {args.model}")
    load_model(args.model, use_cpu_offload=args.cpu_offload, enable_xformers=args.xformers)
    print(f"[INFO] Modèle chargé. Device={device}, dtype={dtype}")

    app.run(host=args.host, port=args.port)

#curl -X POST http://127.0.0.1:5000/generate -H "Content-Type: application/json" -d '{"prompt":"cozy cabin in snowy woods, volumetric light", "save_path":"outputs/cabin.png", "return":"json"}'