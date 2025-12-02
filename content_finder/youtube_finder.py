import os
import sys
import re
import json
import time
import html
import pickle
import logging
import threading
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

import pandas as pd
import yt_dlp
from moviepy.editor import VideoFileClip
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Configuration du logger
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class YouTubeManager:
    """
    Gère le téléchargement, la recherche, le découpage et la récupération
    de données/sous-titres sur YouTube.
    """

    def __init__(self, output_dir: str = "videos"):
        # Chemins
        self.base_dir = Path(__file__).parent.parent
        self.utils_dir = self.base_dir / 'utils'
        self.credentials_path = self.utils_dir / 'login_data.json'
        self.output_dir = self.base_dir / output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Données de connexion
        self.login_data = {}
        self._load_credentials()

        # Google API
        self.youtube_client = None
        self.scopes = ["https://www.googleapis.com/auth/youtube.readonly"]

        # Options par défaut yt-dlp
        self.yt_dlp_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'outtmpl': str(self.output_dir / '%(title)s_%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'geo_bypass': True,
            'socket_timeout': 30,
            'retries': 10,
            # Suppression du chemin hardcodé ffmpeg
        }

    # =========================================================================
    # AUTHENTIFICATION (Google API)
    # =========================================================================

    def _load_credentials(self):
        """Charge les clés API depuis le JSON."""
        try:
            if self.credentials_path.exists():
                with open(self.credentials_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.login_data = data.get('Youtube', {})
            else:
                logger.warning(f"Fichier {self.credentials_path} introuvable.")
        except Exception as e:
            logger.error(f"Erreur lecture credentials : {e}")

    def authenticate_google_api(self):
        """Authentification OAuth2 pour l'API officielle (pour les abonnements)."""
        if self.youtube_client: return self.youtube_client

        try:
            client_config = {
                "installed": {
                    "client_id": self.login_data.get("Client_id"),
                    "client_secret": self.login_data.get("Secret"),
                    "redirect_uris": ["http://localhost"],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            }

            flow = InstalledAppFlow.from_client_config(client_config, self.scopes)
            credentials = flow.run_local_server(port=8080, prompt='consent')

            self.youtube_client = build('youtube', 'v3', credentials=credentials)
            logger.info("Authentification Google API réussie.")
            return self.youtube_client

        except Exception as e:
            logger.error(f"Échec authentification Google API : {e}")
            return None

    # =========================================================================
    # UTILITAIRES URL / ID
    # =========================================================================

    def extract_video_id(self, url: str) -> Optional[str]:
        """Extrait l'ID vidéo depuis n'importe quelle URL YouTube."""
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
            r'(?:embed\/)([0-9A-Za-z_-]{11})',
            r'(?:shorts\/)([0-9A-Za-z_-]{11})',
            r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match: return match.group(1)
        return url if len(url) == 11 else None

    # =========================================================================
    # TÉLÉCHARGEMENT
    # =========================================================================

    def download_video(self, url: str, subfolder: str = "") -> Optional[str]:
        """Télécharge une vidéo unique."""
        video_id = self.extract_video_id(url)
        full_url = f"https://www.youtube.com/watch?v={video_id}"

        target_dir = self.output_dir / subfolder
        target_dir.mkdir(parents=True, exist_ok=True)

        # Configuration spécifique pour ce téléchargement
        opts = self.yt_dlp_opts.copy()
        opts['outtmpl'] = str(target_dir / '%(title)s_%(id)s.%(ext)s')

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(full_url, download=True)
                filename = ydl.prepare_filename(info)
                logger.info(f"Téléchargement réussi : {filename}")
                return filename
        except Exception as e:
            logger.error(f"Erreur téléchargement {url}: {e}")
            return None

    def download_multiple_videos(self, urls: List[str]):
        """Télécharge plusieurs vidéos en parallèle."""
        threads = []
        for url in urls:
            t = threading.Thread(target=self.download_video, args=(url,))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

    # =========================================================================
    # RECHERCHE & DATA (Sans dépendance Excel en lecture)
    # =========================================================================

    def search_videos(self, query: str, max_results: int = 5, save_excel: bool = True) -> List[str]:
        """
        Recherche des vidéos via yt-dlp (pas de quota API).
        Retourne une liste d'URLs.
        Optionnellement, sauvegarde les infos dans un Excel pour consultation.
        """
        search_query = f"ytsearch{max_results}:{query}"
        opts = {
            'quiet': True,
            'extract_flat': True,
            'skip_download': True,
            'ignoreerrors': True
        }

        found_urls = []
        video_data_list = []

        logger.info(f"Recherche de : {query}")

        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                result = ydl.extract_info(search_query, download=False)
                if 'entries' in result:
                    for entry in result['entries']:
                        if not entry: continue
                        url = entry.get('url')
                        if url:
                            found_urls.append(url)
                            # Collecte infos pour Excel (informatif)
                            video_data_list.append({
                                'id': entry.get('id'),
                                'title': entry.get('title'),
                                'url': url,
                                'duration': entry.get('duration'),
                                'uploader': entry.get('uploader'),
                                'view_count': entry.get('view_count'),
                                'search_query': query
                            })
            except Exception as e:
                logger.error(f"Erreur recherche : {e}")

        if save_excel and video_data_list:
            self._save_to_excel(pd.DataFrame(video_data_list), "DataYoutubeVideos.xlsx")

        return found_urls

    def get_video_metadata(self, url: str) -> Dict[str, Any]:
        """Récupère les métadonnées complètes d'une vidéo (Chapitres, Description...)."""
        opts = {'quiet': True, 'skip_download': True, 'ignoreerrors': True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False) or {}

    # =========================================================================
    # ABONNEMENTS (API OFFICIELLE)
    # =========================================================================

    def get_subscriptions_videos(self, n_videos: int = 1, limit_channels: int = 10) -> Dict[str, List[str]]:
        """
        Récupère les dernières vidéos des abonnements de l'utilisateur.
        Nécessite authenticate_google_api().
        """
        if not self.youtube_client:
            if not self.authenticate_google_api():
                return {}

        # 1. Récupérer les chaînes
        channels = []
        try:
            request = self.youtube_client.subscriptions().list(
                part="snippet", mine=True, maxResults=limit_channels
            )
            response = request.execute()
            for item in response.get("items", []):
                channels.append({
                    "title": item["snippet"]["title"],
                    "id": item["snippet"]["resourceId"]["channelId"]
                })
        except Exception as e:
            logger.error(f"Erreur récupération abonnements : {e}")
            return {}

        # 2. Récupérer les vidéos pour chaque chaîne
        results = {}
        for channel in channels:
            try:
                req = self.youtube_client.search().list(
                    part="snippet", channelId=channel["id"],
                    maxResults=n_videos, order="date", type="video"
                )
                res = req.execute()
                video_ids = [item["id"]["videoId"] for item in res.get("items", [])]
                results[channel["title"]] = video_ids
            except Exception as e:
                logger.error(f"Erreur chaîne {channel['title']}: {e}")

        return results

    # =========================================================================
    # DÉCOUPAGE (SPLIT)
    # =========================================================================

    def split_video(self, input_source: str, duration: int = 60, use_chapters: bool = False) -> List[str]:
        """
        Découpe une vidéo (fichier local ou URL).

        Args:
            input_source: Chemin fichier local OU URL Youtube.
            duration: Durée des segments (si pas de chapitres).
            use_chapters: Si True, tente de récupérer les chapitres via yt-dlp.

        Returns:
            Liste des fichiers créés.
        """
        output_files = []
        video_path = str(input_source)
        metadata = {}

        # 1. Si URL, télécharger d'abord, mais récupérer les métadonnées AVANT pour les chapitres
        if "http" in input_source:
            logger.info("URL détectée, récupération métadonnées...")
            metadata = self.get_video_metadata(input_source)
            logger.info("Téléchargement de la vidéo source...")
            video_path = self.download_video(input_source, subfolder="temp_split")
            if not video_path: return []

        # 2. Détection des chapitres (sans Excel)
        chapters = []
        if use_chapters:
            # Option A: Chapitres natifs YouTube
            if metadata.get('chapters'):
                for chap in metadata['chapters']:
                    chapters.append({
                        'start': chap.get('start_time'),
                        'end': chap.get('end_time'),
                        'title': chap.get('title')
                    })
            # Option B: Parsing Description (Timecodes)
            elif metadata.get('description'):
                # Regex simple pour HH:MM:SS ou MM:SS
                matches = re.findall(r'(\d{1,2}:?\d{2}:\d{2}|\d{1,2}:\d{2})\s+(.*)', metadata['description'])
                for time_str, title in matches:
                    # Conversion simple en secondes (à implémenter si besoin de robustesse)
                    parts = list(map(int, time_str.split(':')))
                    seconds = parts[0] * 60 + parts[1] if len(parts) == 2 else parts[0] * 3600 + parts[1] * 60 + parts[
                        2]
                    chapters.append({'start': float(seconds), 'title': title.strip()})

            # Trier les chapitres
            chapters.sort(key=lambda x: x['start'])

        # 3. Traitement Vidéo
        try:
            clip = VideoFileClip(video_path)
            duration_sec = clip.duration

            # Dossier de sortie spécifique
            base_name = Path(video_path).stem
            split_dir = self.output_dir / "splits" / base_name
            split_dir.mkdir(parents=True, exist_ok=True)

            # Cas A : Découpage par Chapitres
            if use_chapters and chapters:
                logger.info(f"Découpage selon {len(chapters)} chapitres trouvés.")
                for i, chap in enumerate(chapters):
                    start = chap['start']
                    # Fin du chapitre = début du suivant ou fin vidéo
                    end = chapters[i + 1]['start'] if i < len(chapters) - 1 else duration_sec

                    if end > duration_sec: end = duration_sec
                    if start >= end: continue

                    safe_title = "".join([c for c in chap['title'] if c.isalnum() or c in ' _-'])[:30]
                    out_name = split_dir / f"{i + 1}_{safe_title}.mp4"

                    self._save_subclip(clip, start, end, str(out_name))
                    output_files.append(str(out_name))

            # Cas B : Découpage par Durée fixe
            else:
                logger.info(f"Découpage par segments de {duration}s.")
                for i, start in enumerate(range(0, int(duration_sec), duration)):
                    end = min(start + duration, duration_sec)
                    out_name = split_dir / f"part_{i + 1}.mp4"

                    self._save_subclip(clip, start, end, str(out_name))
                    output_files.append(str(out_name))

            clip.close()

        except Exception as e:
            logger.error(f"Erreur lors du découpage : {e}")

        return output_files

    def _save_subclip(self, clip, start, end, out_path):
        """Helper pour sauvegarder un clip."""
        sub = clip.subclip(start, end)
        sub.write_videofile(
            out_path,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile='temp-audio.m4a',
            remove_temp=True,
            verbose=False,
            logger=None
        )
        logger.info(f"Segment créé : {out_path}")

    # =========================================================================
    # SOUS-TITRES
    # =========================================================================

    def get_automatic_captions(self, url: str, lang: str = 'fr') -> Dict:
        """
        Récupère et parse les sous-titres automatiques.
        Retourne un dictionnaire structuré.
        """
        video_id = self.extract_video_id(url)
        cache_path = self.output_dir / "captions" / f"{video_id}_{lang}.vtt"
        cache_path.parent.mkdir(exist_ok=True)

        # 1. Téléchargement
        opts = {
            'skip_download': True,
            'writeautomaticsub': True,
            'subtitleslangs': [lang],
            'outtmpl': str(self.output_dir / "captions" / f"{video_id}"),
            'quiet': True
        }

        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

        # yt-dlp ajoute l'extension de langue (ex: .fr.vtt)
        # On cherche le fichier généré
        generated_file = next(cache_path.parent.glob(f"{video_id}*.vtt"), None)

        if not generated_file:
            logger.warning("Pas de sous-titres trouvés.")
            return {}

        # 2. Parsing simple VTT
        captions = []
        with open(generated_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Parsing très basique (à améliorer si besoin de précision XML)
        buffer_text = []
        start_time = None

        for line in lines:
            line = line.strip()
            if '-->' in line:
                start_time = line.split('-->')[0].strip()
            elif line and not line.startswith(('WEBVTT', 'Kind:', 'Language:')):
                # Nettoyage balises <c>
                text = re.sub(r'<[^>]+>', '', line)
                captions.append({'time': start_time, 'text': text})

        return {'video_id': video_id, 'lang': lang, 'captions': captions}

    # =========================================================================
    # EXCEL HELPERS (Informatif uniquement)
    # =========================================================================

    def _save_to_excel(self, df: pd.DataFrame, filename: str):
        """Enregistre les données dans un Excel pour consultation."""
        path = self.base_dir / filename
        try:
            if path.exists():
                existing = pd.read_excel(path)
                df = pd.concat([existing, df]).drop_duplicates(subset=['id'], keep='last')
            df.to_excel(path, index=False)
            logger.info(f"[Info] Données sauvegardées dans {filename}")
        except Exception as e:
            logger.error(f"Erreur Excel : {e}")


if __name__ == "__main__":
    # Exemple d'utilisation
    bot = YouTubeManager()

    # Recherche
    urls = bot.search_videos("Tutoriel Python", max_results=2)
    print("Vidéos trouvées :", urls)

    # Téléchargement
    # if urls:
    #     bot.download_video(urls[0])

    # Split (découpe la vidéo téléchargée ou via URL)
    # bot.split_video(urls[0], duration=30, use_chapters=False)
