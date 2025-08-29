import os
import pandas as pd
from typing import Optional, List, Dict, Any
from pathlib import Path
import re
import requests
import subprocess
import os
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
import tempfile
import sys
import shutil
import cv2

from moviepy.config import change_settings
change_settings({"IMAGEMAGICK_BINARY": r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"})


class VideoEditor:
    """
    Classe pour éditer et manipuler des fichiers vidéo, avec support pour la transcription via Whisper.

    Cette classe fournit des fonctionnalités pour:
    - Charger et traiter des fichiers vidéo
    - Extraire l'audio des vidéos
    - Transcription automatique via Whisper
    - Édition et manipulation des vidéos (découpage, fusion, ajout de sous-titres, etc.)
    - Exportation des vidéos modifiées
    """

    def __init__(self, whisper_model: str = "medium", language: Optional[str] = None):
        """
        Initialise l'éditeur vidéo.

        Args:
            whisper_model: Nom du modèle Whisper à utiliser pour la transcription ('tiny', 'base', 'small', 'medium', 'large')
            language: Code de langue pour la transcription (None pour détection automatique)
        """
        # Configuration des répertoires
        self.output_dir = os.path.normpath(os.path.join(os.getcwd(), '..', 'videos'))
        os.makedirs(self.output_dir, exist_ok=True)

        # Configuration de Whisper
        self.whisper_model_name = whisper_model
        self.whisper_model = None  # Sera chargé à la demande
        self.language = language

        # Stockage des données
        self.items_data_df = None  # DataFrame pour stocker les métadonnées et informations des vidéos

        # Variables d'état
        self.current_video = None
        self.current_audio = None
        self.current_transcription = None

        # Configuration d'encodage
        self.video_codec = 'libx264'
        self.audio_codec = 'aac'

        self.style_elegant = {
            'font': 'Montserrat',
            'fontsize': 24,
            'color': 'white',
            'bg_color': '#000000',
            'bg_opacity': 0.4,
            'position': 'bottom',
            'align': 'center',
            'stroke_color': 'black',
            'stroke_width': 1.0,
            'interline': 3,
            'method': 'segment',
            'max_lines': 2
        }

        self.style_tiktok = {
            'font': 'Impact',
            'fontsize': 40,
            'color': 'white',
            'bg_color': '#FF0050',  # Rose TikTok
            'bg_opacity': 0.8,
            'position': 'bottom',
            'align': 'center',
            'stroke_color': 'black',
            'stroke_width': 2.0,
            'method': 'segment',
            'max_lines': 1  # Une seule ligne pour éviter trop de texte
        }

        self.style_animated = {
            'font': 'Arial-Bold',
            'fontsize': 36,
            'color': '#FFFFFF',
            'bg_color': '#0000AA',
            'bg_opacity': 0.7,
            'position': 'center',  # Au centre de l'écran
            'method': 'word_by_word',
            'stroke_color': 'black',
            'stroke_width': 2.0
        }

    def load_whisper_model(self):
        subprocess.Popen(
            [sys.executable, "WhisperServer.py", "--model", self.whisper_model],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            close_fds=True
        )

    def load_video(self, video_path: str) -> VideoFileClip:
        """
        Charge un fichier vidéo.

        Args:
            video_path: Chemin vers le fichier vidéo

        Returns:
            VideoFileClip: Objet représentant la vidéo chargée

        Raises:
            FileNotFoundError: Si le fichier vidéo n'existe pas
            Exception: Si le fichier ne peut pas être chargé comme une vidéo
        """
        try:
            # Charger la vidéo avec VideoFileClip
            video_clip = VideoFileClip(video_path)

            # Stocker la vidéo comme vidéo courante
            self.current_video = video_clip

            return video_clip

        except Exception as e:
            print(e)

    def extract_audio(self, video_path: str, output_path: Optional[str] = None) -> str:
        """
        Extrait l'audio d'une vidéo.

        Args:
            video_path: Chemin vers le fichier vidéo
            output_path: Chemin où sauvegarder le fichier audio (optionnel)

        Returns:
            str: Chemin vers le fichier audio extrait

        Raises:
            FileNotFoundError: Si le fichier vidéo n'existe pas
            Exception: Si l'extraction échoue
        """
        try:
            # Si le chemin de sortie n'est pas spécifié, créer un nom par défaut
            if output_path is None:
                video_filename = os.path.basename(video_path)
                video_name = os.path.splitext(video_filename)[0]
                output_path = os.path.join('\\'.join(video_path.split('\\')[:-1]), f"{video_name}_audio.wav")

            # Créer le dossier de sortie s'il n'existe pas
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Charger la vidéo si ce n'est pas déjà fait
            if self.current_video is None or self.current_video.filename != video_path:
                video = VideoFileClip(video_path)
            else:
                video = self.current_video

            # Extraire l'audio
            audio = video.audio

            # Enregistrer l'audio
            audio.write_audiofile(
                output_path,
                codec='pcm_s16le',  # Format non compressé pour une meilleure qualité
                ffmpeg_params=["-ac", "1"],  # Mono-canal pour une meilleure compatibilité avec Whisper
                logger=None  # Supprimer la sortie détaillée
            )

            # Stocker l'audio comme audio courant
            self.current_audio = output_path

            # Libérer la mémoire si nous avons chargé la vidéo localement
            if self.current_video is None or self.current_video.filename != video_path:
                video.close()

            return output_path

        except Exception as e:
            print(e)

    def transcribe(self, audio_path: str, max_segment_gap: float = 0.7, max_words_per_segment: int = 5, max_segment_duration: float = 2) -> Dict[str, Any]:
        """
        Transcrit un fichier audio en utilisant Whisper via un serveur local.

        Args:
            audio_path: Chemin vers le fichier audio
            max_segment_gap: Temps maximum en secondes entre les mots avant de créer un nouveau segment
            max_words_per_segment: Nombre maximum de mots par segment (0 = illimité)
            max_segment_duration: Durée maximale d'un segment en secondes (0 = illimitée)

        Returns:
            Dict: Résultat de la transcription avec texte et segments temporels
        """
        # Vérifier que le fichier audio existe
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Le fichier audio n'existe pas: {audio_path}")

        try:
            # Options de transcription pour Whisper
            transcribe_options = {
                "language": self.language,
                "verbose": False,
                "word_timestamps": True,  # Important pour obtenir les timestamps par mot
                "beam_size": 5,
                "best_of": 5,
                "temperature": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
                "compression_ratio_threshold": 2.4,
                "condition_on_previous_text": True,
                "suppress_tokens": [-1],
                "fp16": False,
                "max_initial_timestamp": None
            }

            response = requests.post("http://127.0.0.1:5000/transcribe", json={"audio_path": audio_path, "options": transcribe_options})

            response.raise_for_status()
            result = response.json()

            all_words = []
            for segment in result["segments"]:
                if "words" in segment and segment["words"]:
                    all_words.extend(segment["words"])

            # Nouvelle liste pour stocker les segments restructurés
            new_segments = []

            # Variables pour suivre le segment actuel
            current_words = []
            word_count = 0
            segment_start = None

            # Parcourir tous les mots et créer de nouveaux segments
            for i, word in enumerate(all_words):
                # Initialisation du premier segment
                if segment_start is None:
                    segment_start = word.get("start", 0)

                # Ajouter le mot actuel
                current_words.append(word)
                word_count += 1

                # Critères pour terminer un segment et en commencer un nouveau
                create_new_segment = False

                # 1. Vérifier l'écart avec le mot suivant
                if i < len(all_words) - 1:
                    next_word = all_words[i + 1]
                    gap = next_word.get("start", 0) - word.get("end", 0)
                    if gap > max_segment_gap:
                        create_new_segment = True

                # 2. Vérifier le nombre maximum de mots
                if max_words_per_segment > 0 and word_count >= max_words_per_segment:
                    create_new_segment = True

                # 3. Vérifier la durée maximale du segment
                current_duration = word.get("end", 0) - segment_start
                if max_segment_duration > 0 and current_duration >= max_segment_duration:
                    create_new_segment = True

                # 4. Derniers mots ou fin de la liste
                is_last_word = (i == len(all_words) - 1)

                # Créer un nouveau segment si nécessaire ou si c'est le dernier mot
                if create_new_segment or is_last_word:
                    # Construction du texte du segment
                    segment_text = ""
                    for i in range(len(current_words)):
                        w = current_words[i]
                        word = w.get("word", "").strip()

                        # Premier mot: pas d'espace avant
                        if i == 0:
                            segment_text = word
                        else:
                            # Ne pas ajouter d'espace si le mot actuel commence ou termine par une apostrophe ou un tiret
                            if word.startswith(("'", "-")) or word.endswith(("'", "-")):
                                segment_text += word
                            else:
                                segment_text += " " + word

                    # Nettoyer les espaces en trop
                    segment_text = segment_text.strip()

                    # Ajouter le segment à la liste
                    new_segment = {
                        "start": segment_start,
                        "end": w.get("end", w.get("start", 0)),
                        "text": segment_text,
                        "words": current_words.copy()  # Copie pour éviter la référence
                    }
                    new_segments.append(new_segment)

                    # Réinitialiser pour le prochain segment
                    current_words = []
                    word_count = 0
                    segment_start = None if not is_last_word else None

            transcription_result = {
                "text": result.get("text", ""),
                "segments": new_segments,
                "language": result.get("language", ""),
                "audio_path": audio_path
            }

            self.current_transcription = transcription_result
            return transcription_result

        except Exception as e:
            print(e)

    def split_video(self, video_path: str, duration: int = 61, use_timecodes: bool = False, segments: List[Dict[str, Any]] = None) -> List[str]:
        """
        Découpe une vidéo locale en segments de durée égale ou selon les timecodes.

        Args:
            video_path: Chemin vers le fichier vidéo local
            duration: Durée de chaque segment en secondes (par défaut: 61)
            use_timecodes: Si True, tente d'utiliser les timecodes du fichier vidéo
            segments: Liste optionnelle de segments personnalisés au format [{"start_time": float, "title": str}, ...]

        Returns:
            List[str]: Liste des chemins vers les fichiers vidéo créés
        """
        # Vérifier que le fichier existe
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Le fichier vidéo n'existe pas: {video_path}")

        output_files = []
        chapters = segments or []

        try:
            # Charger la vidéo
            video_clip = VideoFileClip(video_path)
            video_duration = video_clip.duration

            # Créer le dossier de sortie basé sur le nom du fichier
            folder_name = Path(video_path).stem
            output_folder = os.path.join(os.path.dirname(video_path), folder_name)
            os.makedirs(output_folder, exist_ok=True)

            # DÉCOUPAGE DE LA VIDÉO
            try:
                # A. DÉCOUPAGE PAR TIMECODES
                if use_timecodes and chapters:
                    # Trier les chapitres par temps de début
                    chapters.sort(key=lambda x: x['start_time'])

                    # Ajouter la fin de la vidéo comme point de fin du dernier chapitre
                    chapters.append({'start_time': video_duration, 'title': 'end'})

                    # Découper chaque segment
                    for i in range(len(chapters) - 1):
                        start_time = chapters[i]['start_time']
                        end_time = chapters[i + 1]['start_time']
                        title = chapters[i]['title']

                        # Formater le titre pour le nom de fichier
                        safe_title = re.sub(r'[\\/*?:"<>|]', "_", title.replace(' ', '_'))[:50]

                        # Découper et sauvegarder le segment
                        segment = video_clip.subclip(start_time, end_time)
                        output_file = os.path.join(output_folder, f"{safe_title}_part_{i + 1}.mp4")

                        segment.write_videofile(output_file,
                                                codec='libx264',
                                                audio_codec='aac',
                                                temp_audiofile=f"{output_file}.temp-audio.m4a",
                                                remove_temp=True,
                                                threads=6)
                        output_files.append(output_file)
                # B. DÉCOUPAGE PAR DURÉE FIXE
                else:
                    num_segments = int(video_duration // duration) + (1 if video_duration % duration > 0 else 0)

                    for i in range(num_segments):
                        start_time = i * duration
                        end_time = min((i + 1) * duration, video_duration)

                        segment = video_clip.subclip(start_time, end_time)
                        output_file = os.path.join(output_folder, f"part_{i + 1}.mp4")

                        segment.write_videofile(output_file,
                                                codec='libx264',
                                                audio_codec='aac',
                                                temp_audiofile=f"{output_file}.temp-audio.m4a",
                                                remove_temp=True,
                                                threads=6)
                        output_files.append(output_file)

            except Exception as e:
                print(f"Erreur lors du découpage: {e}")
                import traceback
                print(traceback.format_exc())
            finally:
                # Fermer la vidéo source
                try:
                    video_clip.close()
                except:
                    pass

            return output_files

        except Exception as e:
            print(f"Erreur lors du chargement de la vidéo: {e}")
            return []

    def create_subtitled_video(self, video_path=None, subtitle_style=None, output_path=None):
        """
        Crée une vidéo avec des sous-titres basés sur la transcription disponible.

        Args:
            video_path (str, optional): Chemin vers le fichier vidéo. Si None, utilise self.current_video
            subtitle_style (dict, optional): Dictionnaire de paramètres pour personnaliser les sous-titres.
                Paramètres disponibles:
                    - 'font': Police de caractères (par défaut: 'Arial')
                    - 'fontsize': Taille de la police (par défaut: 30)
                    - 'color': Couleur du texte (par défaut: 'white')
                    - 'bg_color': Couleur de fond (par défaut: 'black')
                    - 'position': Position verticale ('bottom', 'top', 'center', par défaut: 'bottom')
                    - 'align': Alignement horizontal ('center', 'left', 'right', par défaut: 'center')
                    - 'margin': Marge en pixels (par défaut: 20)
                    - 'stroke_color': Couleur du contour du texte (par défaut: 'black')
                    - 'stroke_width': Épaisseur du contour (par défaut: 1.5)
                    - 'interline': Espacement entre les lignes (par défaut: 5)
                    - 'method': Méthode d'affichage ('segment', 'word_by_word', par défaut: 'segment')
                    - 'max_lines': Nombre maximum de lignes par sous-titre (par défaut: 2)
            output_path (str, optional): Chemin de sortie pour la vidéo sous-titrée.
                                         Si None, génère un nom basé sur le fichier original

        Returns:
            str: Chemin vers la vidéo sous-titrée
        """
        from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
        import os
        from datetime import datetime
        import textwrap

        # ------------------------------------------------------------
        # 1. VALIDATION DES ENTRÉES ET INITIALISATION
        # ------------------------------------------------------------

        # Vérifications préalables
        if not self.current_transcription:
            raise ValueError("Aucune transcription disponible. Utilisez d'abord la méthode transcribe().")

        # Utiliser la vidéo fournie ou la vidéo actuelle
        video = None
        if video_path:
            video = VideoFileClip(video_path)
        elif self.current_video:
            video = self.current_video
        else:
            raise ValueError("Aucune vidéo disponible. Chargez une vidéo ou fournissez un chemin.")

        # Paramètres par défaut pour les sous-titres
        default_style = {
            'font': 'Arial',
            'fontsize': 30,
            'color': 'white',
            'bg_color': 'black',
            'position': 'bottom',
            'align': 'center',
            'margin': 20,
            'stroke_color': 'black',
            'stroke_width': 1.5,
            'interline': 5,
            'method': 'segment',
            'max_lines': 2,
        }

        # Fusionner avec les paramètres fournis
        if subtitle_style:
            for key, value in subtitle_style.items():
                default_style[key] = value

        # Convertir explicitement tous les paramètres numériques en nombres
        for key in ['fontsize', 'margin', 'max_lines', 'interline']:
            if key in default_style:
                default_style[key] = int(default_style[key])

        for key in ['stroke_width']:
            if key in default_style:
                default_style[key] = float(default_style[key])

        # ------------------------------------------------------------
        # 2. CONFIGURATION DES CHEMINS ET SORTIES
        # ------------------------------------------------------------

        # Définir le chemin de sortie si non spécifié
        if not output_path:
            if video_path:
                base_name = os.path.splitext(os.path.basename(video_path))[0]
                output_dir = os.path.dirname(video_path)
            elif hasattr(self.current_video, 'filename') and self.current_video.filename:
                base_name = os.path.splitext(os.path.basename(self.current_video.filename))[0]
                output_dir = os.path.dirname(self.current_video.filename)
            else:
                base_name = f"subtitled_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                output_dir = self.output_dir

            output_path = os.path.join(output_dir, f"{base_name}_subtitled.mp4")

        # ------------------------------------------------------------
        # 3. CALCUL DES POSITIONS ET DIMENSIONS
        # ------------------------------------------------------------

        # Calculer les positions et dimensions
        max_text_width = video.w - (2 * default_style['margin'])

        # Déterminer la position verticale
        if default_style['position'] == 'bottom':
            y_pos = video.h - default_style['fontsize'] * (default_style['max_lines'] + 1) - default_style['margin']
        elif default_style['position'] == 'top':
            y_pos = default_style['margin']
        else:  # center
            y_pos = (video.h - default_style['fontsize'] * default_style['max_lines']) // 2

        # ------------------------------------------------------------
        # 4. CRÉATION DES SOUS-TITRES (SELON LA MÉTHODE)
        # ------------------------------------------------------------

        # Liste pour stocker les clips de sous-titres
        subtitle_clips = []

        # Méthode d'affichage par segment (par défaut)
        if default_style['method'] == 'segment':
            segments = self.current_transcription.get("segments", [])

            for segment in segments:
                start_time = segment.get("start", 0)
                end_time = segment.get("end", 0)
                text = segment.get("text", "")

                # Découper le texte en lignes si nécessaire
                chars_per_line = max_text_width // (default_style['fontsize'] // 2)
                lines = textwrap.wrap(text, width=int(chars_per_line))

                # Limiter le nombre de lignes
                if len(lines) > default_style['max_lines']:
                    lines = lines[:default_style['max_lines']]
                    lines[-1] = lines[-1][:len(lines[-1]) - 3] + "..."

                # Joindre les lignes avec des sauts de ligne
                wrapped_text = '\n'.join(lines)

                try:
                    # Approche simplifiée: utiliser directement bg_color dans TextClip
                    txt_clip = TextClip(
                        wrapped_text,
                        font=default_style['font'],
                        fontsize=default_style['fontsize'],
                        color=default_style['color'],
                        bg_color=default_style['bg_color'],  # Fond simple sans opacité
                        stroke_color=default_style['stroke_color'],
                        stroke_width=default_style['stroke_width'],
                        method='caption',
                        align=default_style['align'],
                        interline=default_style['interline']
                    )

                    # Positionner horizontalement selon l'alignement
                    if default_style['align'] == 'center':
                        x_pos = 'center'
                    elif default_style['align'] == 'left':
                        x_pos = default_style['margin']
                    else:  # right
                        x_pos = video.w - default_style['margin'] - txt_clip.w

                    # Finaliser la position et le timing du clip
                    txt_clip = txt_clip.set_position((x_pos, y_pos))
                    txt_clip = txt_clip.set_start(start_time).set_end(end_time)
                    subtitle_clips.append(txt_clip)
                except Exception as e:
                    print(f"Erreur lors de la création du sous-titre: {e}")
                    continue

        # Méthode d'affichage mot par mot
        elif default_style['method'] == 'word_by_word':
            # Récupérer les mots de chaque segment
            all_words = []
            for segment in self.current_transcription.get("segments", []):
                if "words" in segment:
                    all_words.extend(segment["words"])

            # Si aucun mot n'a été trouvé, essayer la propriété words au niveau racine
            if not all_words and "words" in self.current_transcription:
                all_words = self.current_transcription.get("words", [])

            # Si toujours pas de mots, revenir à la méthode par segment
            if not all_words:
                print("Aucun timing mot par mot trouvé. Utilisation de la méthode par segment.")
                return self.create_subtitled_video(video_path, {**subtitle_style, 'method': 'segment'}, output_path)

            # Créer un clip pour chaque mot
            for word_info in all_words:
                word = word_info.get("word", "").strip()
                start = word_info.get("start", 0)
                end = word_info.get("end", 0)

                # Ignorer les mots vides
                if not word:
                    continue

                try:
                    # Créer le TextClip pour le mot (approche simplifiée)
                    word_clip = TextClip(
                        word,
                        font=default_style['font'],
                        fontsize=default_style['fontsize'],
                        color=default_style['color'],
                        bg_color=default_style['bg_color'],
                        stroke_color=default_style['stroke_color'],
                        stroke_width=default_style['stroke_width']
                    )

                    # Finaliser la position et le timing du clip
                    word_clip = word_clip.set_position(('center', y_pos))
                    word_clip = word_clip.set_start(start).set_end(end)
                    subtitle_clips.append(word_clip)
                except Exception as e:
                    print(f"Erreur lors de la création du sous-titre mot: {e}")
                    continue

        # ------------------------------------------------------------
        # 5. FINALISATION ET EXPORT
        # ------------------------------------------------------------

        # Vérifier qu'il y a des sous-titres à ajouter
        if not subtitle_clips:
            print("Aucun sous-titre n'a été créé. Vérifiez la transcription.")
            return None

        # Combiner la vidéo avec les sous-titres
        print(f"Création d'une vidéo sous-titrée avec {len(subtitle_clips)} sous-titres...")
        final_video = CompositeVideoClip([video] + subtitle_clips)

        # Conserver la durée originale
        final_video = final_video.set_duration(video.duration)

        # Sauvegarder la vidéo sous-titrée
        print(f"Sauvegarde de la vidéo sous-titrée vers: {output_path}")
        final_video.write_videofile(
            output_path,
            codec=self.video_codec,
            audio_codec=self.audio_codec,
            temp_audiofile=f"{output_path}.temp-audio.m4a",
            remove_temp=True,
            threads=6
        )

        # Fermer les clips pour libérer les ressources
        if video_path:  # Ne fermer que si nous avons créé un nouveau clip
            video.close()
        final_video.close()

        return output_path

    def save_to_excel(self, df, filename, key_column='id'):
        """
        Enregistre un DataFrame dans un fichier Excel.
        Si le fichier existe déjà, les données sont mises à jour selon la colonne clé.

        Args:
            df (DataFrame): Le DataFrame à sauvegarder
            filename (str): Nom du fichier Excel
            key_column (str): Nom de la colonne à utiliser comme identifiant unique pour la mise à jour

        Returns:
            bool: True si l'opération a réussi, False sinon
        """
        try:
            # Vérifier si le DataFrame n'est pas vide
            if df.empty:
                return False

            # Si le fichier existe, le lire et mettre à jour les données
            if os.path.exists(filename):
                try:
                    existing_df = pd.read_excel(filename)

                    # Vérifier que la colonne clé existe dans les deux DataFrames
                    if key_column in existing_df.columns and key_column in df.columns:
                        # Identifier les entrées à mettre à jour (qui existent déjà)
                        existing_keys = set(existing_df[key_column])
                        update_mask = df[key_column].isin(existing_keys)
                        new_entries = df[~update_mask]

                        # Pour les entrées existantes, supprimer les anciennes et ajouter les nouvelles
                        if not update_mask.empty:
                            update_entries = df[update_mask]
                            existing_df = existing_df[~existing_df[key_column].isin(update_entries[key_column])]

                        # Concaténer l'ancien DataFrame (sans les entrées mises à jour) avec les nouvelles entrées
                        combined_df = pd.concat([existing_df, df], ignore_index=True)

                        # Supprimer les doublons potentiels (garder la dernière occurrence)
                        final_df = combined_df.drop_duplicates(subset=[key_column], keep='last')

                        # Sauvegarder le DataFrame final
                        final_df.to_excel(filename, index=False)
                    else:
                        # Si la colonne clé n'existe pas, simplement ajouter les nouvelles données
                        combined_df = pd.concat([existing_df, df], ignore_index=True)
                        combined_df.to_excel(filename, index=False)
                except Exception:
                    # En cas d'erreur de lecture du fichier existant, écraser avec les nouvelles données
                    df.to_excel(filename, index=False)
            else:
                # Si le fichier n'existe pas, le créer
                df.to_excel(filename, index=False)

            return True

        except Exception:
            return False

    def load_from_excel(self, filename, sheet_name=0):
        """
        Charge un fichier Excel et retourne son contenu sous forme de DataFrame.

        Args:
            filename (str): Nom du fichier Excel à charger
            sheet_name (str ou int, optional): Nom ou index de la feuille à charger. Par défaut 0 (première feuille)

        Returns:
            DataFrame: DataFrame contenant les données du fichier Excel
            None: En cas d'erreur ou si le fichier n'existe pas
        """
        try:
            if not os.path.exists(filename):
                return None

            # Charger toutes les colonnes du fichier Excel
            df = pd.read_excel(filename, sheet_name=sheet_name)
            return df

        except Exception:
            return None


def StartVideoEditor(language: Optional[str] = "fr", whisper_model: Optional[str] = "large") -> VideoEditor:
    return VideoEditor(language=language, whisper_model=whisper_model)


video_editor = StartVideoEditor(whisper_model="medium", language="fr")

video_path = "C:\\Users\lucas\PycharmProjects\PROJECT\SocialMediaAutomation\\videos\Les meufs vs les gars 🤣🤣 Audio_ @jeremouquoi #shorts #animation #humour #drole #sketch.mp4"
video_editor.load_video(video_path=video_path)
audio_path = video_editor.extract_audio(video_path=video_path)
#paths = video_editor.split_video(video_path=video_path)
"""for path in paths:
    audio_path = video_editor.extract_audio(path)
    print(video_editor.transcribe(audio_path, max_segment_gap=2))"""

print(video_editor.transcribe(audio_path, max_words_per_segment=5, max_segment_duration=2))
video_editor.create_subtitled_video(subtitle_style=video_editor.style_tiktok)