import yt_dlp
from typing import Optional, Dict, Any
import pandas as pd
import threading
from moviepy.editor import VideoFileClip
import re
import os
from pathlib import Path
import requests
import json
from googleapiclient.discovery import build
import os
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors



class YouTubeTranscriber:

    def __init__(self, whisper_model: str = "base", language:  Optional[str] = None, yt_dlp_options: Optional[Dict[str, Any]] = None):
        """
        Initialise le transcripteur YouTube.

        Args:
            whisper_model: Le modèle Whisper à utiliser ("tiny", "base", "small", "medium", "large")
            output_dir: Répertoire où sauvegarder les fichiers (si None, utilise un dossier temporaire)
            language: Code de langue pour la transcription (ex: "fr", "en", None pour auto-détection)
            yt_dlp_options: Options supplémentaires pour yt_dlp
        """
        # Configuration des répertoires
        self.output_dir = os.path.normpath(os.path.join(os.getcwd(), '..', 'videos'))
        os.makedirs(self.output_dir, exist_ok=True)

        # Configuration de Whisper
        self.whisper_model_name = whisper_model
        self.whisper_model = None
        self.language = language
        self.items_data_df = None
        self.utils_directory = os.getcwd() + '\\..\\utils'
        self.Connection_file_name = os.path.join(self.utils_directory, 'login_data.json')
        self.login_data = {}
        self.get_user_login()
        self.scopes = ["https://www.googleapis.com/auth/youtube.readonly"]
        self.youtube = None

        # Configuration de yt-dlp
        self.yt_dlp_options = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'ffmpeg_location':'C:\\Users\\LucasCONGRAS\\AppData\\Local\\Microsoft\\WinGet\\Packages\\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\\ffmpeg-8.0-full_build\\bin',
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4'
            }],
            'outtmpl': os.path.join(self.output_dir, '%(id)s.mp4'),
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'ignoreerrors': True,
            'geo_bypass': True,
            'socket_timeout': 15,
            'retries': 10,
            'cleanup': True  # supprime les fragments audio/vidéo après fusion
        }

        # Mettre à jour avec les options personnalisées
        if yt_dlp_options:
            self.yt_dlp_options.update(yt_dlp_options)

    def extract_video_id(self, url: str):
        try:

            patterns = [
                r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',  # youtube.com/watch?v=ID ou youtube.com/v/ID
                r'(?:embed\/)([0-9A-Za-z_-]{11})',  # youtube.com/embed/ID
                r'(?:shorts\/)([0-9A-Za-z_-]{11})',  # youtube.com/shorts/ID
                r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})'  # youtu.be/ID
            ]

            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    return match.group(1)

            print(f"Impossible d'extraire l'ID de la vidéo YouTube de l'URL: {url}")
        except:
            return None

    def extract_several_video_ids(self, urls: list) -> list:
        """
        Extrait les IDs de plusieurs vidéos YouTube à partir d'une liste d'URLs.

        Args:
            urls: Liste d'URLs YouTube

        Returns:
            list: Liste des IDs de vidéos extraits
        """
        video_ids = []
        for url in urls:
            video_id = self.extract_video_id(url)
            if video_id:
                video_ids.append(video_id)
            else:
                print(f"Impossible d'extraire l'ID de la vidéo YouTube de l'URL: {url}")
        return video_ids

    def download_video(self, video_id_or_url: str) -> str:
        # Déterminer l'ID et l'URL finale
        if 'youtube.com/' in video_id_or_url or 'youtu.be/' in video_id_or_url:
            video_id = self.extract_video_id(video_id_or_url)
        else:
            video_id = video_id_or_url

        url = f"https://www.youtube.com/watch?v={video_id}"

        try:
            # Récupérer les informations de la vidéo
            info_options = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
            }
            with yt_dlp.YoutubeDL(info_options) as ydl:
                info = ydl.extract_info(url, download=False)

            # Nettoyer le titre pour en faire un nom de fichier valide
            video_title = info.get('title', f'video_{video_id}')
            clean_title = re.sub(r'[\\/*?:"<>|]', "_", video_title)[:100]

            # Options de téléchargement
            download_options = self.yt_dlp_options.copy()
            download_options['outtmpl'] = os.path.join(self.output_dir, f"{clean_title}.mp4")
            download_options['http_headers'] = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }

            # Télécharger la vidéo
            with yt_dlp.YoutubeDL(download_options) as ydl:
                ydl.download([url])

            # Vérifier la présence du fichier
            output_path = os.path.join(self.output_dir, f"{clean_title}.mp4")
            if not os.path.exists(output_path):
                possible_files = [f for f in os.listdir(self.output_dir) if f.startswith(clean_title[:50]) and f.endswith('.mp4')]
                if possible_files:
                    output_path = os.path.join(self.output_dir, possible_files[0])
                else:
                    raise FileNotFoundError(f"Le fichier téléchargé est introuvable: {output_path}")

            return output_path

        except Exception as e:
            raise Exception(f"Erreur lors du téléchargement de la vidéo {video_id}: {str(e)}")

    def download_several_videos(self, video_ids_or_urls: list):
        """
        Télécharge plusieurs vidéos YouTube à partir d'une liste d'IDs ou d'URLs.

        Args:
            video_ids_or_urls: Liste d'IDs ou d'URLs de vidéos YouTube

        Returns:
            list: Liste des chemins des fichiers vidéo téléchargés
        """
        threads = []
        for index, video_id_or_url in enumerate(video_ids_or_urls):
            thread = threading.Thread(target=self.download_video, args=(video_id_or_url,))
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

    def collect_videos_data(self, video_id_or_url: str) -> pd.DataFrame:
        """
        Récupère toutes les informations possibles d'une vidéo YouTube et les enregistre dans un fichier Excel.

        Args:
            video_id_or_url: ID ou URL de la vidéo YouTube

        Returns:
            DataFrame: DataFrame contenant les informations de la vidéo

        Raises:
            Exception: Si la récupération des informations échoue
        """
        if 'youtube.com/' in video_id_or_url or 'youtu.be/' in video_id_or_url:
            video_id = self.extract_video_id(video_id_or_url)
        else:
            video_id = video_id_or_url

        url = f"https://www.youtube.com/watch?v={video_id}"

        try:
            info_options = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'extract_flat': False,
                'ignoreerrors': False,
            }

            with yt_dlp.YoutubeDL(info_options) as ydl:
                video_info = ydl.extract_info(url, download=False)

            flat_info = {}
            if 'chapters' in video_info and video_info['chapters']:
                chapters = [f"{chapter['start_time']} - {chapter['title']}" for chapter in video_info['chapters']]
                flat_info['chapters'] = ', '.join(chapters)

            if 'automatic_captions' in video_info:
                available_langs = list(video_info['automatic_captions'].keys())
                flat_info['automatic_captions_langs'] = ', '.join(available_langs)

                url_template = None
                lang_placeholder = "{LANG_CODE}"
                for lang, formats in video_info['automatic_captions'].items():
                    if formats:
                        vtt_format = next((fmt for fmt in formats if fmt.get('ext') == 'srv2'), None)
                        selected_format = vtt_format or formats[0]

                        if 'url' in selected_format:
                            url = selected_format['url']

                            if "&tlang=" + lang in url:
                                url_template = url.replace("&tlang=" + lang, "&tlang=" + lang_placeholder)
                            else:
                                # Si on ne peut pas déterminer où est le code de langue, utiliser l'URL telle quelle
                                url_template = url
                            break

                # Ajouter le modèle d'URL au dictionnaire
                if url_template:
                    flat_info['automatic_caption_url_template'] = url_template

            # Fonction récursive pour aplatir les structures de données imbriquées
            def flatten_dict(d, parent_key=''):
                for k, v in d.items():
                    key = f"{parent_key}_{k}" if parent_key else k

                    if isinstance(v, dict):
                        flatten_dict(v, key)
                    elif isinstance(v, list):
                        # Pour les listes, on les convertit en chaînes
                        if v and not isinstance(v[0], (dict, list)):
                            flat_info[key] = ', '.join(str(item) for item in v)
                    else:
                        flat_info[key] = v

            flatten_dict(video_info)

            # Ajouter l'ID explicitement
            flat_info['id'] = video_id

            # Créer le DataFrame
            video_df = pd.DataFrame([flat_info])

            return video_df

        except Exception as e:
            raise Exception(f"Erreur lors de la récupération des informations de la vidéo {video_id}: {str(e)}")

    def get_quality_filters(self):
        """
        Retourne un dictionnaire de filtres pour sélectionner des vidéos de qualité.
        Les valeurs sont des seuils minimums pour chaque métrique.

        Returns:
            dict: Dictionnaire de filtres pour la sélection de vidéos
        """
        return {
            # Métriques d'engagement
            "view_count": "view_count>10000",  # Plus de 10K vues
            "like_count": "like_count>500",  # Plus de 500 likes
            "comment_count": "comment_count>50",  # Plus de 50 commentaires

            # Qualité de la vidéo
            "height": "height>720",  # Au moins 720p
            "duration": "61<duration<1800",  # Entre 1 et 30 minutes
            "fps": "fps>24",  # Au moins 24 images par seconde

            # Crédibilité du créateur
            "channel_follower_count": "channel_follower_count>5000",  # Chaîne avec au moins 5K abonnés

            # Autres filtres
            "age_limit": "age_limit<18",  # Contenu tout public
            "is_live": "is_live==False",  # Pas de livestreams
            #"upload_date": ">20220101", # Téléchargée après le 1er janvier 2022
        }

    def get_authenticated_service(self):
        flow = google_auth_oauthlib.flow.Flow.from_client_config(
            client_config={
                "installed": {
                    "client_id": self.login_data['Client_id'],
                    "client_secret": self.login_data['Secret'],
                    "redirect_uris": ["http://localhost"]
                }
            },
            scopes=self.scopes
        )

        auth_url, _ = flow.authorization_url(prompt='consent')

        print(f"Allez sur ce lien pour autoriser l'accès : {auth_url}")
        code = input("Entrez le code d'autorisation : ")

        flow.fetch_token(code=code)

        credentials = flow.credentials
        youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)

        return youtube

    def get_subscriptions(self, max_results=10):
        if self.youtube is None:
            try:
                self.get_authenticated_service()
            except Exception as e:
                print(e)
                return

            self.get_subscriptions(max_results)

        request = self.youtube.subscriptions().list(
            part="snippet",
            mine=True,  # Récupérer les abonnements de l'utilisateur connecté
            maxResults=max_results
        )

        response = request.execute()

        # Afficher les abonnements
        subscriptions = []
        for item in response["items"]:
            channel_title = item["snippet"]["title"]
            channel_id = item["snippet"]["resourceId"]["channelId"]
            subscriptions.append({
                "channel_title": channel_title,
                "channel_id": channel_id,
                "channel_url": f"https://www.youtube.com/channel/{channel_id}"
            })

        return subscriptions

    def search_youtube_videos(self, query: str, max_results: int = 10, excel_filename="DataYoutubeVideos.xlsx") -> list:
        """
        Recherche des vidéos YouTube et retourne les liens des x premiers résultats.

        Args:
            query: Terme de recherche
            max_results: Nombre maximum de résultats à retourner
            excel_filename: Nom du fichier Excel pour enregistrer les données

        Returns:
            list: Liste de liens YouTube des vidéos trouvées
        """
        try:
            videos = []
            # Créer un DataFrame vide pour collecter les données
            videos_data = pd.DataFrame()

            # Augmenter légèrement le nombre de résultats recherchés pour compenser les vidéos indisponibles
            search_max = max_results + 0

            # Utilisation de yt-dlp pour la recherche
            search_url = f"ytsearch{search_max}:{query}"
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'skip_download': True
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(search_url, download=False)

                # Compteur pour les vidéos valides trouvées
                valid_count = 0

                for k in range(min(search_max, len(result['entries']))):
                    if valid_count >= max_results:
                        break

                    entry = result['entries'][k]

                    # Vérifier que l'URL est bien formée
                    if 'url' not in entry or not entry['url'] or 'youtube.com/watch?v=' not in entry['url']:
                        continue

                    video_url = entry['url']

                    try:
                        # Récupérer les données sous forme de DataFrame
                        video_df = self.collect_videos_data(video_url)

                        # Si on arrive ici, la vidéo est disponible
                        videos.append(video_url)
                        valid_count += 1

                        # Concaténer avec le DataFrame principal
                        videos_data = pd.concat([videos_data, video_df], ignore_index=True)

                    except Exception as video_error:
                        # Juste ignorer cette vidéo et continuer
                        print(f"Vidéo indisponible ignorée: {video_url} - {str(video_error)}")
                        continue

                # Enregistrer le DataFrame s'il contient des données
                if not videos_data.empty:
                    self.save_to_excel(videos_data, excel_filename, key_column='id')
                else:
                    print("Aucune donnée trouvée pour la recherche.")

                return videos

        except Exception as e:
            if videos:  # Si on a déjà trouvé des vidéos, les retourner
                print(f"Erreur partielle lors de la recherche: {str(e)}")
                return videos
            else:
                raise Exception(f"Erreur lors de la recherche YouTube: {str(e)}")

    def search_trending_by_category(self, region='FR', max_results=20):
        yt = build('youtube', 'v3', developerKey=self.login_data['API_Key'])

        # Récupérer les catégories disponibles
        categories_req = yt.videoCategories().list(
            part="snippet",
            regionCode=region
        )
        categories_res = categories_req.execute()

        categories = [
            cat['id'] for cat in categories_res.get('items', [])
            if cat['snippet']['assignable']
        ]

        if not categories:
            return []

        per_cat = max_results // len(categories) or 1
        results = []

        for cat_id in categories:
            try:
                req = yt.videos().list(
                    part='snippet,contentDetails,statistics',
                    chart='mostPopular',
                    regionCode=region,
                    videoCategoryId=cat_id,
                    maxResults=per_cat
                )
                res = req.execute()
                results.extend(
                    [f"https://www.youtube.com/watch?v={item['id']}" for item in res.get('items', [])]
                )
            except Exception as e:
                # Pas d'emoji → texte simple compatible Windows
                print(f"[WARN] Catégorie {cat_id} ignorée : {e}")

        return results

    def split_video(self, video_id_or_url_or_filename: str, duration: int = 61, use_timecodes: bool = False, datafilename: str = None) -> list:
        """
        Découpe une vidéo YouTube en segments de durée égale ou selon les timecodes.

        Args:
            video_id_or_url_or_filename: ID YouTube, URL, chemin de fichier local ou titre de vidéo
            duration: Durée de chaque segment en secondes (par défaut: 61)
            use_timecodes: Si True, utilise les timecodes de la vidéo pour le découpage (si disponibles)
            datafilename: Nom du fichier Excel contenant les données des vidéos

        Returns:
            list: Liste des chemins vers les fichiers vidéo créés
        """
        # --- 1. INITIALISATION ---
        video_info = None
        is_local_file = os.path.exists(video_id_or_url_or_filename)
        video_path = video_id_or_url_or_filename if is_local_file else None
        video_id = None
        youtube_url = None
        chapters = []
        output_files = []

        # --- 2. RECHERCHE DANS LA BASE DE DONNÉES ---
        if datafilename:
            try:
                # Charger les données du fichier Excel
                df = self.load_from_excel(datafilename)

                # Préparer le terme de recherche
                search_term = Path(video_id_or_url_or_filename).stem if is_local_file else video_id_or_url_or_filename

                # Nettoyer le terme de recherche et les titres pour une comparaison plus robuste
                clean_search_term = ''.join(c for c in search_term if c.isalnum()).lower()
                df['clean_title'] = df['title'].apply(lambda x: ''.join(c for c in str(x) if c.isalnum()).lower() if isinstance(x, str) else '')

                # Rechercher dans la base de données
                potential_matches = df[df['clean_title'].str.contains(clean_search_term, na=False)]

                # Traiter la correspondance si trouvée
                if not potential_matches.empty:
                    match = potential_matches.iloc[0]

                    # Récupérer les métadonnées
                    video_info = {'title': match['title']}
                    if 'webpage_url' in match and not pd.isna(match['webpage_url']):
                        youtube_url = match['webpage_url']

                    # Extraire les chapitres si disponibles
                    if 'chapters' in match and match['chapters'] and isinstance(match['chapters'], str):
                        chapters_str = match['chapters']
                        chapter_entries = [entry.strip() for entry in chapters_str.split(',')]

                        # Traiter chaque entrée de chapitre
                        for entry in chapter_entries:
                            pattern = r'(\d+(?:\.\d+)?)\s+-\s+(.+?)(?:$|\')'
                            match_result = re.match(pattern, entry)

                            if match_result:
                                time_str = match_result.group(1)
                                title = match_result.group(2).strip()
                                chapters.append({'start_time': float(time_str), 'title': title})
            except Exception as e:
                print(f"Erreur lors de la recherche dans la base de données: {e}")

        # --- 3. OBTENIR LA VIDÉO ---
        if not is_local_file:
            # Déterminer l'ID ou l'URL YouTube
            if youtube_url:
                video_url = youtube_url
            elif 'youtube.com/' in video_id_or_url_or_filename or 'youtu.be/' in video_id_or_url_or_filename:
                video_url = video_id_or_url_or_filename
                video_id = self.extract_video_id(video_id_or_url_or_filename)
            else:
                video_id = video_id_or_url_or_filename
                video_url = f"https://www.youtube.com/watch?v={video_id}"

            # Obtenir les infos de la vidéo si nécessaire
            if not video_info:
                try:
                    info_options = {'quiet': True, 'no_warnings': True, 'skip_download': True}

                    with yt_dlp.YoutubeDL(info_options) as ydl:
                        video_info = ydl.extract_info(video_url, download=False)

                        # Extraire les chapitres des métadonnées YouTube si demandé
                        if use_timecodes and 'chapters' in video_info and video_info['chapters']:
                            for chapter in video_info['chapters']:
                                start_time = chapter.get('start_time', 0)
                                title = chapter.get('title', f'chapter_{start_time}')
                                chapters.append({'start_time': start_time, 'title': title})
                except Exception as e:
                    print(f"Erreur lors de la récupération des informations YouTube: {e}")

            # Télécharger la vidéo
            try:
                video_path = self.download_video(video_id or self.extract_video_id(video_url))
            except Exception as e:
                print(f"Erreur lors du téléchargement: {e}")
                return []

        # --- 4. PRÉPARATION DE LA VIDÉO ET DU DOSSIER DE SORTIE ---
        try:
            video_clip = VideoFileClip(video_path)
            video_duration = video_clip.duration

            # Déterminer le nom du dossier de sortie
            if video_info and 'title' in video_info:
                folder_name = re.sub(r'[\\/*?:"<>|]', "_", video_info.get('title'))[:100]
            else:
                folder_name = Path(video_path).stem  # Nom du fichier sans extension

            # Créer le dossier de sortie
            output_folder = os.path.join(os.path.dirname(video_path), folder_name)
            os.makedirs(output_folder, exist_ok=True)

        except Exception as e:
            print(f"Erreur lors du chargement de la vidéo: {e}")
            return []

        # --- 5. DÉCOUPAGE DE LA VIDÉO ---
        try:
            # A. DÉCOUPAGE PAR TIMECODES
            if use_timecodes:
                # Extraire les timecodes de la description si nécessaire
                if not chapters and video_info and 'description' in video_info:
                    description = video_info['description']

                    # Différents formats de timecodes couramment utilisés
                    timecode_patterns = [
                        r'(\d{1,2}):(\d{2}):(\d{2})\s+(.*?)(?=\n\d{1,2}:\d{2}:\d{2}|\Z)',  # HH:MM:SS Titre
                        r'(\d{1,2}):(\d{2})\s+(.*?)(?=\n\d{1,2}:\d{2}|\Z)',  # MM:SS Titre
                        r'\[(\d{1,2}):(\d{2}):(\d{2})\]\s+(.*?)(?=\n\[\d{1,2}:\d{2}:\d{2}|\Z)',  # [HH:MM:SS] Titre
                        r'\[(\d{1,2}):(\d{2})\]\s+(.*?)(?=\n\[\d{1,2}:\d{2}|\Z)'  # [MM:SS] Titre
                    ]

                    for pattern in timecode_patterns:
                        matches = re.findall(pattern, description, re.MULTILINE)
                        if matches:
                            for match in matches:
                                if len(match) == 4:  # HH:MM:SS format
                                    hours, minutes, seconds, title = match
                                    total_seconds = int(hours) * 3600 + int(minutes) * 60 + int(seconds)
                                elif len(match) == 3:  # MM:SS format
                                    minutes, seconds, title = match
                                    total_seconds = int(minutes) * 60 + int(seconds)
                                else:
                                    continue

                                title = title.strip()
                                chapters.append({'start_time': total_seconds, 'title': title})
                            break  # Si un pattern a fonctionné, on s'arrête

                # Découper selon les chapitres si disponibles
                if chapters:
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
                else:
                    # Si pas de chapitres, utiliser le découpage par durée fixe
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
        finally:
            # Fermer la vidéo source
            try:
                video_clip.close()
            except:
                pass

        return output_files

    def split_all_videos_in_a_folder(self, folder_path: str, duration: int = 61, use_timecodes: bool = False, datafilename: str = None) -> list:
        """
        Découpe toutes les vidéos dans un dossier en segments de durée égale ou selon les timecodes.

        Args:
            folder_path: Chemin du dossier contenant les vidéos
            duration: Durée de chaque segment en secondes (par défaut: 60)
            use_timecodes: Si True, utilise les timecodes de la vidéo pour le découpage (si disponibles)

        Returns:
            list: Liste des chemins vers les fichiers vidéo créés
        """
        output_files = []
        for filename in os.listdir(folder_path):
            if filename.endswith('.mp4'):
                video_path = os.path.join(folder_path, filename)
                segments = self.split_video(video_path, duration, use_timecodes, datafilename)
                output_files.extend(segments)

        return output_files

    def get_automatic_captions(self, video_id_or_url: str, language: str = 'fr', datafilename: str = None, max_segment_gap: float = 1) -> str:
        """
        Récupère les sous-titres automatiques d'une vidéo YouTube.

        Args:
            video_id_or_url: ID YouTube ou URL complète
            language: Code de langue pour les sous-titres (par défaut: 'fr')
            datafilename: Nom du fichier Excel contenant les données des vidéos (optionnel)

        Returns:
            dict: Contenu des sous-titres automatiques

        Raises:
            Exception: Si les sous-titres ne peuvent pas être récupérés
        """
        # Extraire l'ID vidéo si une URL est fournie
        video_id = self.extract_video_id(video_id_or_url) if ('youtube.com/' in video_id_or_url or 'youtu.be/' in video_id_or_url) else video_id_or_url

        # Récupérer les données de la vidéo
        video_data = None

        if datafilename is None:
            # Collecter les données directement depuis YouTube
            videos_data = self.collect_videos_data(video_id)

            if not videos_data.empty and 'id' in videos_data.columns:
                video_data = videos_data[videos_data['id'] == video_id]
        else:
            # Charger les données depuis le fichier Excel
            df = self.load_from_excel(datafilename)

            if 'id' in df.columns:
                video_data = df[df['id'] == video_id]

        # Vérifier si les données ont été trouvées
        if video_data is None or video_data.empty:
            raise Exception(f"Impossible de trouver les données pour la vidéo: {video_id}")

        # Récupérer l'URL du modèle de sous-titres automatiques
        if 'automatic_caption_url_template' not in video_data.columns:
            raise Exception(f"La colonne 'automatic_caption_url_template' est manquante dans les données")

        caption_url_template = video_data['automatic_caption_url_template'].iloc[0]

        if not caption_url_template or pd.isna(caption_url_template):
            raise Exception(f"Pas de sous-titres automatiques disponibles pour cette vidéo")

        # Remplacer le code de langue dans l'URL
        caption_url = caption_url_template.replace("{LANG_CODE}", language)

        try:
            # Faire une requête pour récupérer les sous-titres
            response = requests.get(caption_url)
            response.raise_for_status()  # Lever une exception si la requête échoue

            # Parser les sous-titres XML
            parsed_captions = self.parse_youtube_captions(response.text, max_segment_gap)

            # Mettre à jour avec les métadonnées
            parsed_captions["source"] = "youtube_automatic_captions"
            parsed_captions["video_id"] = video_id
            parsed_captions["language"] = language

            return parsed_captions

        except Exception as e:
            print(e)

    def parse_youtube_captions(self, caption_xml: str, max_segment_gap: float = 0.7) -> Dict[str, Any]:
        """
        Parse les sous-titres automatiques YouTube au format XML.

        Args:
            caption_xml: Contenu XML des sous-titres
            max_segment_gap: Temps maximum en secondes entre les mots avant de créer un nouveau segment

        Returns:
            Dict: Résultat structuré avec texte et segments temporels, similaire à la sortie de transcribe()
        """
        try:
            from xml.etree import ElementTree as ET
            import html

            # Analyser le XML
            root = ET.fromstring(caption_xml)

            # Extraire tous les éléments <text>
            text_elements = root.findall(".//text")

            # Convertir en format de mots avec timestamps
            words = []
            full_text = ""

            for element in text_elements:
                # Extraire les attributs temporels et le texte
                start_ms = int(element.get("t", "0"))
                duration_ms = int(element.get("d", "0"))
                end_ms = start_ms + duration_ms

                # Convertir en secondes
                start_sec = start_ms / 1000
                end_sec = end_ms / 1000

                # Extraire et décodifier le texte
                text = html.unescape(element.text) if element.text else ""

                # Déterminer si c'est un append ou un nouveau texte
                is_append = element.get("append") == "1"

                # Ajouter à la liste des mots
                word_info = {
                    "word": text,
                    "start": start_sec,
                    "end": end_sec,
                    "is_append": is_append
                }
                words.append(word_info)

                # Ajouter au texte complet
                if not is_append:
                    full_text += " " + text if full_text else text
                else:
                    full_text += text

            # Créer des segments basés sur max_segment_gap
            segments = []
            if words:
                current_segment = {
                    "start": words[0]["start"],
                    "end": words[0]["end"],
                    "text": words[0]["word"],
                    "words": [words[0]]
                }

                prev_end = words[0]["end"]

                # Parcourir les mots restants
                for word in words[1:]:
                    word_start = word["start"]

                    # Si l'écart est trop grand ou si ce n'est pas un append, créer un nouveau segment
                    if word_start - prev_end > max_segment_gap or not word["is_append"]:
                        current_segment["end"] = prev_end
                        segments.append(current_segment.copy())

                        # Nouveau segment
                        current_segment = {
                            "start": word_start,
                            "end": word["end"],
                            "text": word["word"],
                            "words": [word]
                        }
                    else:
                        # Ajouter le mot au segment actuel
                        current_segment["text"] += word["word"]
                        current_segment["end"] = word["end"]
                        current_segment["words"].append(word)

                    prev_end = word["end"]

                # Ajouter le dernier segment
                segments.append(current_segment)

            # Construire le résultat final
            result = {
                "text": full_text.strip(),
                "segments": segments,
                "language": "fr",  # Présumer la langue basée sur l'entrée
                "words": words
            }

            return result

        except Exception as e:
            print(e)

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

    def get_user_login(self):
        try:
            login_data_file = open(self.Connection_file_name, 'r')
            self.login_data = json.load(login_data_file)['Youtube']
            login_data_file.close()
        except:
            print("Identifiants de connexion non trouvés, veuillez les ajouter dans le fichier 'login_data.json' dans le dossier utils.")



def StartYoutubeBot():
    return YouTubeTranscriber()


bot = StartYoutubeBot()
channels = bot.get_subscriptions()
#urls = bot.search_youtube_videos('abc', max_results=1, excel_filename="DataYoutubeVideos.xlsx")
#urls = bot.search_trending_by_category(max_results=1)
#print(urls)
#bot.download_several_videos(urls)  #bot.get_quality_filters()
#print(bot.get_automatic_captions(urls[0], language='fr'))
#bot.split_all_videos_in_a_folder(bot.output_dir, duration=61, use_timecodes=True, datafilename="DataYoutubeVideos.xlsx")
