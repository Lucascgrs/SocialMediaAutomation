import os
import sys
import re
import logging
import json
import requests
import textwrap
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

import pandas as pd
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, AudioFileClip
from moviepy.config import change_settings
IMAGEMAGICK_BINARY = r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"

if os.path.exists(IMAGEMAGICK_BINARY):
    change_settings({"IMAGEMAGICK_BINARY": IMAGEMAGICK_BINARY})
else:
    print(f"🛑 ERREUR CRITIQUE : ImageMagick introuvable au chemin : {IMAGEMAGICK_BINARY}")


# Configuration du logger
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION IMAGEMAGICK
# =============================================================================
# MoviePy a besoin d'ImageMagick pour les TextClip.
# Idéalement, installez ImageMagick et cochez "Install legacy utilities (convert)"
# Si le chemin n'est pas détecté automatiquement, décommentez et adaptez la ligne ci-dessous :
# change_settings({"IMAGEMAGICK_BINARY": r"C:\Program Files\ImageMagick-7.1.0-Q16-HDRI\magick.exe"})

class VideoEditor:
    """
    Classe pour l'édition vidéo (découpage, audio, sous-titres) et la transcription.
    Dépend d'un serveur Whisper local tournant sur le port 5000.
    """

    def __init__(self, whisper_api_url: str = "http://127.0.0.1:5000/transcribe", language: str = "fr"):

        # Chemins
        self.base_dir = Path(__file__).parent.parent
        self.output_dir = self.base_dir / 'videos'
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Config Whisper
        self.whisper_api_url = whisper_api_url
        self.language = language

        # État interne
        self.current_video: Optional[VideoFileClip] = None
        self.current_transcription: Optional[Dict] = None

        # Styles de sous-titres prédéfinis
        self.styles = {
            'tiktok': {
                'font': 'Impact',
                'fontsize': 70,
                'color': 'yellow',
                'stroke_color': 'black',
                'stroke_width': 3.0,
                'position_y': 0.30,
                'method': 'segment',
                'max_lines': 1
            }
        }

    # =========================================================================
    # CHARGEMENT & AUDIO
    # =========================================================================

    def load_video(self, video_path: str) -> Optional[VideoFileClip]:
        """Charge une vidéo en mémoire."""
        if not os.path.exists(video_path):
            logger.error(f"Fichier introuvable : {video_path}")
            return None
        try:
            # On ferme l'ancienne vidéo si elle existe pour libérer la ressource
            if self.current_video:
                self.current_video.close()

            self.current_video = VideoFileClip(str(video_path))
            logger.info(f"Vidéo chargée : {Path(video_path).name}")
            return self.current_video
        except Exception as e:
            logger.error(f"Erreur chargement vidéo : {e}")
            return None

    def extract_audio(self, video_path: str, output_path: Optional[str] = None) -> Optional[str]:
        """Extrait l'audio en WAV (PCM) pour une meilleure compatibilité Whisper."""
        p_video = Path(video_path)
        if not p_video.exists():
            return None

        if not output_path:
            output_path = str(p_video.with_name(f"{p_video.stem}_audio.wav"))

        temp_clip = None
        try:
            temp_clip = VideoFileClip(str(video_path))
            if not temp_clip.audio:
                logger.warning("La vidéo ne contient pas de piste audio.")
                return None

            temp_clip.audio.write_audiofile(
                output_path,
                codec='pcm_s16le',
                ffmpeg_params=["-ac", "1"],  # Mono
                verbose=False,
                logger=None
            )
            logger.info(f"Audio extrait : {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Erreur extraction audio : {e}")
            return None
        finally:
            if temp_clip: temp_clip.close()

    # =========================================================================
    # TRANSCRIPTION (APPEL API LOCAL)
    # =========================================================================

    def transcribe(self, audio_path: str,
                   max_gap: float = 0.7,
                   max_words: int = 5,
                   max_duration: float = 2.5) -> Optional[Dict]:
        """
        Envoie l'audio au serveur Whisper et restructure les segments.
        """
        if not Path(audio_path).exists():
            logger.error("Fichier audio introuvable.")
            return None

        # Options envoyées au serveur
        options = {
            "language": self.language,
            "word_timestamps": True
        }

        try:
            logger.info(f"Envoi au serveur Whisper ({self.whisper_api_url})...")
            with open(audio_path, 'rb') as f:
                # Note: Si le serveur lit un path local, on envoie le path.
                # Si le serveur attend un fichier uploadé, il faudrait utiliser files={'file': f}
                # Ici, on suit ta logique d'envoyer le path JSON
                response = requests.post(
                    self.whisper_api_url,
                    json={"audio_path": str(audio_path), "options": options},
                    timeout=600  # Timeout long pour les gros fichiers
                )

            response.raise_for_status()
            raw_result = response.json()

            # Post-traitement pour créer des sous-titres lisibles
            refined_segments = self._refine_segments(
                raw_result.get("segments", []),
                max_gap, max_words, max_duration
            )

            self.current_transcription = {
                "text": raw_result.get("text", ""),
                "segments": refined_segments,
                "language": raw_result.get("language", self.language)
            }

            logger.info(f"Transcription terminée : {len(refined_segments)} segments générés.")
            return self.current_transcription

        except requests.exceptions.ConnectionError:
            logger.critical("Impossible de se connecter au serveur Whisper. Vérifiez qu'il est lancé (port 5000).")
            return None
        except Exception as e:
            logger.error(f"Erreur transcription : {e}")
            return None

    def _refine_segments(self, original_segments: List[Dict], max_gap, max_words, max_dur) -> List[Dict]:
        """Réorganise les mots en segments courts et dynamiques."""
        all_words = []
        for seg in original_segments:
            all_words.extend(seg.get("words", []))

        if not all_words: return []

        new_segments = []
        current_chunk = []
        chunk_start = all_words[0].get("start", 0)

        for i, word_obj in enumerate(all_words):
            current_chunk.append(word_obj)

            # Conditions de coupure
            should_cut = False
            is_last = (i == len(all_words) - 1)

            if not is_last:
                next_start = all_words[i + 1].get("start", 0)
                curr_end = word_obj.get("end", 0)

                # 1. Silence trop long
                if (next_start - curr_end) > max_gap: should_cut = True
                # 2. Trop de mots
                if len(current_chunk) >= max_words: should_cut = True
                # 3. Durée trop longue
                if (curr_end - chunk_start) >= max_dur: should_cut = True

            if should_cut or is_last:
                text_content = " ".join([w["word"].strip() for w in current_chunk])
                new_segments.append({
                    "start": chunk_start,
                    "end": current_chunk[-1]["end"],
                    "text": text_content,
                    "words": current_chunk.copy()
                })
                # Reset
                if not is_last:
                    current_chunk = []
                    chunk_start = all_words[i + 1].get("start", 0)

        return new_segments

    # =========================================================================
    # ÉDITION (SPLIT)
    # =========================================================================

    def split_video(self, video_path: str, duration: int = 60, segments: List[Dict] = None) -> List[str]:
        """Découpe une vidéo locale."""
        p_path = Path(video_path)
        if not p_path.exists(): return []

        out_dir = p_path.parent / p_path.stem
        out_dir.mkdir(exist_ok=True)
        output_files = []

        try:
            clip = VideoFileClip(str(p_path))
            total_dur = clip.duration

            # Mode Segments personnalisés (Timecodes)
            if segments:
                segments.sort(key=lambda x: x['start_time'])
                # On ajoute une fin fictive pour le dernier segment
                checkpoints = segments + [{'start_time': total_dur, 'title': 'end'}]

                for i in range(len(checkpoints) - 1):
                    start = checkpoints[i]['start_time']
                    end = checkpoints[i + 1]['start_time']

                    if start >= end: continue

                    title = "".join([c for c in checkpoints[i]['title'] if c.isalnum()])
                    out_name = out_dir / f"{i + 1}_{title}.mp4"

                    self._save_subclip(clip, start, end, str(out_name))
                    output_files.append(str(out_name))

            # Mode Durée Fixe
            else:
                for i, start in enumerate(range(0, int(total_dur), duration)):
                    end = min(start + duration, total_dur)
                    out_name = out_dir / f"part_{i + 1}.mp4"
                    self._save_subclip(clip, start, end, str(out_name))
                    output_files.append(str(out_name))

            clip.close()
            return output_files

        except Exception as e:
            logger.error(f"Erreur split : {e}")
            return []

    def _save_subclip(self, clip, start, end, path):
        """Helper d'écriture pour éviter la duplication de code."""
        clip.subclip(start, end).write_videofile(
            path, codec='libx264', audio_codec='aac',
            temp_audiofile='temp-audio.m4a', remove_temp=True,
            verbose=False, logger=None
        )

    # =========================================================================
    # SOUS-TITRAGE (BURNING)
    # =========================================================================

    def create_subtitled_video(self, video_path: str = None, style_name: str = "tiktok", output_path: str = None):
        """
        Incruste les sous-titres sur la vidéo (Burn-in).
        Nécessite ImageMagick installé et configuré.
        """
        if not self.current_transcription:
            logger.error("Pas de transcription disponible.")
            return None

        # Sélection vidéo
        target_video_path = video_path if video_path else (self.current_video.filename if self.current_video else None)
        if not target_video_path:
            logger.error("Pas de vidéo source.")
            return None

        # Sélection style
        style = self.styles.get(style_name, self.styles['tiktok'])

        # Path de sortie
        if not output_path:
            p = Path(target_video_path)
            output_path = str(p.parent / f"{p.stem}_subtitled.mp4")

        try:
            video_clip = VideoFileClip(target_video_path)
            subtitle_clips = []

            # --- GÉNÉRATION DES CLIPS TEXTE ---
            # Mode 1: Segment par segment (Phrase entière)
            if style.get('method') == 'segment':
                for seg in self.current_transcription['segments']:
                    txt_clip = self._create_text_clip(seg['text'], style, video_clip.w)
                    if txt_clip:
                        txt_clip = txt_clip.set_start(seg['start']).set_end(seg['end'])
                        txt_clip = self._position_clip(txt_clip, style, video_clip.size)
                        subtitle_clips.append(txt_clip)

            # Mode 2: Mot par mot (Karaoké)
            elif style.get('method') == 'word_by_word':
                # On aplatit tous les mots
                all_words = []
                for s in self.current_transcription['segments']:
                    all_words.extend(s.get('words', []))

                for word_obj in all_words:
                    txt_clip = self._create_text_clip(word_obj['word'], style, video_clip.w)
                    if txt_clip:
                        txt_clip = txt_clip.set_start(word_obj['start']).set_end(word_obj['end'])
                        txt_clip = self._position_clip(txt_clip, style, video_clip.size)
                        subtitle_clips.append(txt_clip)

            # --- COMPOSITION ---
            if not subtitle_clips:
                logger.warning("Aucun sous-titre généré.")
                return None

            final = CompositeVideoClip([video_clip] + subtitle_clips)
            final.write_videofile(
                output_path, codec='libx264', audio_codec='aac',
                temp_audiofile='temp-subs.m4a', remove_temp=True,
                threads=6
            )

            video_clip.close()
            final.close()
            logger.info(f"Vidéo sous-titrée générée : {output_path}")
            return output_path

        except OSError as e:
            if "convert" in str(e) or "ImageMagick" in str(e):
                logger.critical(
                    "ERREUR IMAGEMAGICK : ImageMagick n'est pas détecté. Installez-le ou configurez le chemin.")
            else:
                logger.error(f"Erreur MoviePy : {e}")
            return None
        except Exception as e:
            logger.error(f"Erreur génération sous-titres : {e}")
            return None

    def _create_text_clip(self, text: str, style: Dict, max_w: int):
        """Helper pour créer un TextClip avec gestion des erreurs."""
        try:
            # Wrapper le texte si trop long
            char_limit = int((max_w - 40) / (style['fontsize'] * 0.5))
            wrapped_text = "\n".join(textwrap.wrap(text, width=char_limit)[:style.get('max_lines', 2)])

            bg_color = style.get('bg_color') if style.get('bg_color') else 'transparent'

            stroke_color = style.get('stroke_color')
            stroke_width = style.get('stroke_width', 0)

            if not stroke_color:
                stroke_width = 0
                stroke_color = None

            textclip = TextClip(
                wrapped_text,
                font=style.get('font', 'Arial'),
                fontsize=style['fontsize'],
                color=style['color'],
                bg_color=bg_color,
                stroke_color=stroke_color,
                stroke_width=stroke_width,
                method='label',
                align='center'
            )

            return textclip

        except Exception as e:
            print(f"ERREUR TextClip : {e}")
            return None

    def _position_clip(self, clip, style, video_size):
        """Positionne le clip selon le style (supporte % de hauteur)."""
        w, h = video_size

        # Si une position Y en pourcentage est fournie (ex: 0.70 pour 70%)
        if 'position_y' in style:
            perc = style['position_y']
            # On limite entre 0 et 1
            perc = max(0.0, min(1.0, perc))

            # Calcul en pixels : Hauteur * pourcentage
            # On centre le texte verticalement sur ce point
            y_pos = int(h * perc - (clip.h / 2))

            return clip.set_position(('center', y_pos))

        # Fallback sur l'ancien système (top/bottom) si pas de pourcentage
        pos = style.get('position', 'bottom')
        if pos == 'bottom':
            return clip.set_position(('center', h - clip.h - 80))
        elif pos == 'top':
            return clip.set_position(('center', 80))
        else:
            return clip.set_position('center')

    # =========================================================================
    # UTILS EXCEL
    # =========================================================================

    def save_to_excel(self, df: pd.DataFrame, filename: str):
        """Log informatif."""
        try:
            path = self.base_dir / filename
            if path.exists():
                old = pd.read_excel(path)
                df = pd.concat([old, df]).drop_duplicates(subset=['id'], keep='last')
            df.to_excel(path, index=False)
        except Exception:
            pass


if __name__ == "__main__":
    # Exemple
    editor = VideoEditor()
    # 1. Charger
    editor.load_video("C:\\Users\\LucasCONGRAS\\PycharmProjects\\PythonProject\\PROJECT\\SocialMediaAutomation\\videos\\J'ai codé un algorithme qui reconnaît les gens dans le métro_242A9AIZ3TY.mp4")
    # 2. Extraire Audio
    wav_path = editor.extract_audio("C:\\Users\\LucasCONGRAS\\PycharmProjects\\PythonProject\\PROJECT\\SocialMediaAutomation\\videos\\J'ai codé un algorithme qui reconnaît les gens dans le métro_242A9AIZ3TY.mp4")
    # 3. Transcrire (Nécessite le serveur Whisper lancé)
    if wav_path:
        res = editor.transcribe(wav_path, max_words=4)
        if res:
            editor.create_subtitled_video(style_name="tiktok")