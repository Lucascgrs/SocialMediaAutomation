import argparse
import whisper
from flask import Flask, request, jsonify

app = Flask(__name__)
model = None  # sera chargé après parsing des arguments


@app.route("/transcribe", methods=["POST"])
def transcribe_audio():
    audio_path = request.json["audio_path"]
    print(audio_path)
    options = request.json.get("options", {})
    result = model.transcribe(audio_path, **options)
    return jsonify(result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        default="base",
        help="Nom du modèle Whisper à utiliser (tiny, base, small, medium, large)"
    )
    args = parser.parse_args()

    print(f"[INFO] Chargement du modèle Whisper : {args.model}")
    model = whisper.load_model(args.model)

    app.run(host="127.0.0.1", port=5000)
