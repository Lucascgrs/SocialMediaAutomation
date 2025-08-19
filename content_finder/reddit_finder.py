import urllib.request
import os
import time
import queue
import praw
import threading
import urllib.request
from urllib.parse import urlparse
import datetime
import pandas as pd
from yt_dlp import YoutubeDL
import json


class RedditCollector:
    def __init__(self, account_identifier):
        self.utils_directory = os.getcwd() + '\\..\\utils'
        self.Connection_file_name = os.path.join(self.utils_directory, 'login_data.json')
        self.login_data = {}
        self.items_data_df = None

        self.account_identifier = account_identifier
        self.get_user_login(self.account_identifier)

        self.client_id = 'MhNAI4AXxIFqpWu5JteGmA'
        self.client_secret = 'v_Z8OU8iO-82i--JMOJdV59InlAbKA'
        self.user_agent = 'MyRedditImageDownloader/1.0'

        self.IMAGES_PER_SUB = 100
        self.NUM_SUBREDDITS = 10
        self.VIDEO_EXTS = ('.mp4', '.webm')
        self.MAX_RETRIES = 5
        self.RETRY_DELAY = 5
        self.SAVE_DIR = os.path.normpath(os.path.join(os.getcwd(), '..', 'videos'))

        self.lock = threading.Lock()
        self.seen_urls = set()
        self.download_queue = queue.Queue()

        self.YDL_OPTS = {
            "quiet": True,
            "outtmpl": os.path.join("%(dirname)s", "%(title)s_%(id)s.%(ext)s"),
            "noplaylist": True,
            "merge_output_format": "mp4",
            "ignoreerrors": True,
            "no_warnings": True,
            "extract_flat": True,
            "retries": 3,
            "fragment_retries": 3,
            "file_access_retries": 3,
            "extractor_retries": 3,
            "socket_timeout": 10,
        }

        os.makedirs(self.SAVE_DIR, exist_ok=True)
        
    def get_user_login(self, account_identifier):
        try:
            login_data_file = open(self.Connection_file_name, 'r')
            self.login_data = json.load(login_data_file)['Reddit'][account_identifier]
            login_data_file.close()
        except:
            print("Identifiants de connexion non trouvés, veuillez les ajouter dans le fichier 'login_data.json' dans le dossier utils.")

    def init_praw(self):
        """Initialise l'API Reddit avec gestion des erreurs."""
        for attempt in range(self.MAX_RETRIES):
            try:
                reddit = praw.Reddit(
                    username=self.account_identifier,
                    password=self.login_data,
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    user_agent=self.user_agent
                )
                reddit.user.me()
                return reddit
            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
                else:
                    raise Exception("Échec de connexion à Reddit. Vérifiez vos identifiants.") from e

    def search_subreddits(self, keyword=None, limit=100, collect_data=True, sort_by="subscribers", time_filter="all"):
        """
        Recherche des subreddits et collecte leurs données générales.

        Args:
            keyword (str, optional): Mot-clé de recherche. Si None, récupère les subreddits populaires.
            limit (int): Nombre de subreddits à récupérer.
            collect_data (bool): Si True, collecte les données détaillées de chaque subreddit.
            sort_by (str): Critère de tri ('subscribers', 'created_utc', 'name', etc.)
            time_filter (str): Filtre temporel ('all', 'day', 'month', 'year', etc.)

        Returns:
            list or DataFrame: Liste de subreddits avec leurs données ou DataFrame si collect_data=True
        """
        try:
            reddit = self.init_praw()
            subreddit_objects = []

            for attempt in range(self.MAX_RETRIES):
                try:
                    if keyword:
                        subreddit_objects = list(reddit.subreddits.search(keyword, limit=limit * 2))
                    else:
                        subreddit_objects = list(reddit.subreddits.popular(limit=limit * 2))
                    break
                except Exception:
                    if attempt < self.MAX_RETRIES - 1:
                        time.sleep(self.RETRY_DELAY)
                    else:
                        raise

            subreddit_objects = subreddit_objects[:limit]

            if not collect_data:
                return subreddit_objects

            subreddit_data = []
            for i, subreddit in enumerate(subreddit_objects):
                try:
                    data = {
                        'name': subreddit.display_name,
                        'title': subreddit.title,
                        'description': subreddit.description if hasattr(subreddit, 'description') else subreddit.public_description,
                        'subscribers': subreddit.subscribers,
                        'created_utc': datetime.datetime.fromtimestamp(subreddit.created_utc).strftime('%Y-%m-%d %H:%M:%S'),
                        'is_nsfw': subreddit.over18,
                        'url': f'https://www.reddit.com/r/{subreddit.display_name}/',
                        'id': subreddit.id
                    }

                    try:
                        rules = list(subreddit.rules)
                        data['rules_count'] = len(rules)
                        data['rules'] = [rule['short_name'] for rule in rules]
                    except:
                        data['rules_count'] = 0
                        data['rules'] = []

                    try:
                        moderators = list(subreddit.moderator())
                        data['moderators_count'] = len(moderators)
                    except:
                        data['moderators_count'] = 0

                    try:
                        data['active_user_count'] = subreddit.active_user_count if hasattr(subreddit, 'active_user_count') else None
                    except:
                        data['active_user_count'] = None

                    if data['is_nsfw'] == False:
                        subreddit_data.append(data)
                    time.sleep(0.5)

                except Exception as e:
                    subreddit_data.append({'name': subreddit.display_name, 'error': str(e)})

            df = pd.DataFrame(subreddit_data)

            if sort_by in df.columns:
                df = df.sort_values(by=sort_by, ascending=False)

            return df

        except Exception:
            return [] if not collect_data else pd.DataFrame()

    def search_several_subreddits(self, keywords, limit=100, collect_data=True, sort_by="subscribers", time_filter="all"):
        """
        Recherche plusieurs subreddits en fonction d'une liste de mots-clés.

        Args:
            keywords (list): Liste de mots-clés pour la recherche.
            limit (int): Nombre maximum de subreddits à récupérer par mot-clé.
            collect_data (bool): Si True, collecte les données détaillées de chaque subreddit.
            sort_by (str): Critère de tri ('subscribers', 'created_utc', 'name', etc.)
            time_filter (str): Filtre temporel ('all', 'day', 'month', 'year', etc.)

        Returns:
            list or DataFrame: Liste de subreddits avec leurs données ou DataFrame si collect_data=True
        """
        all_subreddits = []
        for keyword in keywords:
            subreddits = self.search_subreddits(keyword=keyword, limit=limit, collect_data=collect_data, sort_by=sort_by, time_filter=time_filter)
            if isinstance(subreddits, pd.DataFrame):
                all_subreddits.append(subreddits)
            else:
                all_subreddits.extend(subreddits)

        if isinstance(all_subreddits, list) and all_subreddits and isinstance(all_subreddits[0], dict):
            return pd.DataFrame(all_subreddits)
        return pd.concat(all_subreddits, ignore_index=True) if all_subreddits else pd.DataFrame()

    def get_reddit_items_url(self, sub_name, limit=None):
        """Collecte les éléments d'un subreddit avec gestion des erreurs."""
        if limit is None:
            limit = self.IMAGES_PER_SUB

        try:
            reddit = self.init_praw()
            items = []
            items_data_list = []
            n = 0

            for attempt in range(self.MAX_RETRIES):
                try:
                    for sub in reddit.subreddit(sub_name).top(limit=limit, time_filter='all'):
                        url = sub.url
                        items_data_list.append(self.collect_post_data(sub))

                        if url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.mp4', '.webm')):
                            items.append(url)
                        elif sub.is_video and sub.media:
                            vid = sub.media.get('reddit_video', {})
                            if vid.get('fallback_url'):
                                items.append(vid['fallback_url'])
                        elif any(x in url for x in ('imgur.com', 'reddit.com/gallery', 'gfycat', 'redgifs', 'youtube', 'youtu.be', 'streamable')):
                            items.append(url)

                        n += 1
                        if n >= limit:
                            break
                    break
                except Exception:
                    if attempt < self.MAX_RETRIES - 1:
                        time.sleep(self.RETRY_DELAY)
                    else:
                        raise
            self.save_to_excel(df=pd.DataFrame(items_data_list), filename="DataPosts.xlsx", key_column='id')
            return items
        except Exception:
            print(f"Erreur lors de la récupération des éléments du subreddit {sub_name}.")
            return []

    def get_several_reddit_items_url(self, sub_names, limit=None):
        """
        Collecte les éléments de plusieurs subreddits.

        Args:
            sub_names (list): Liste des noms de subreddits.
            limit (int, optional): Nombre maximum d'éléments à récupérer par subreddit. Par défaut, utilise IMAGES_PER_SUB.

        Returns:
            list: Liste des URLs des éléments collectés.
        """
        if limit is None:
            limit = self.IMAGES_PER_SUB

        all_items = []
        for sub_name in sub_names:
            items = self.get_reddit_items_url(sub_name, limit)
            all_items.extend(items)

        return all_items

    def collect_post_data(self, sub):
        """
        Collecte toutes les données disponibles d'une soumission Reddit (post).

        Args:
            sub: Objet soumission Reddit (praw.models.Submission)

        Returns:
            dict: Dictionnaire contenant toutes les données du post
        """
        try:
            # Extraction des données de base
            post_data = {
                'id': sub.id,
                'title': sub.title,
                'author': str(sub.author) if sub.author else '[deleted]',
                'author_id': sub.author.id if sub.author else None,
                'created_utc': datetime.datetime.fromtimestamp(sub.created_utc).strftime('%Y-%m-%d %H:%M:%S'),
                'score': sub.score,
                'upvote_ratio': sub.upvote_ratio,
                'num_comments': sub.num_comments,
                'permalink': f'https://www.reddit.com{sub.permalink}',
                'url': sub.url,

                # Attributs de catégorisation
                'subreddit': sub.subreddit.display_name,
                'subreddit_id': sub.subreddit_id,
                'subreddit_subscribers': sub.subreddit.subscribers if hasattr(sub.subreddit, 'subscribers') else None,
                'over_18': sub.over_18,
                'spoiler': sub.spoiler,
                'pinned': sub.pinned if hasattr(sub, 'pinned') else None,
                'stickied': sub.stickied,
                'locked': sub.locked,
                'archived': sub.archived if hasattr(sub, 'archived') else None,

                # Attributs de métadonnées
                'edited': bool(sub.edited),
                'edited_timestamp': datetime.datetime.fromtimestamp(sub.edited).strftime('%Y-%m-%d %H:%M:%S') if isinstance(sub.edited, (int, float)) else None,
                'ratio_subscribers_score': sub.score / sub.subreddit.subscribers
            }

            if hasattr(sub, 'post_hint') and sub.post_hint == 'image':
                post_data['media_type'] = 'image'

            # Extraction d'informations sur les médias
            if sub.media:
                if 'reddit_video' in sub.media:
                    post_data['media_type'] = 'reddit_video'
                    post_data['media_url'] = sub.media['reddit_video'].get('fallback_url', '')
                    post_data['media_height'] = sub.media['reddit_video'].get('height', 0)
                    post_data['media_width'] = sub.media['reddit_video'].get('width', 0)
                    post_data['media_duration'] = sub.media['reddit_video'].get('duration', 0)
                    post_data['media_duration_secure'] = sub.secure_media['reddit_video'].get('duration', 0)
                elif 'oembed' in sub.media:
                    post_data['media_type'] = 'oembed'
                    post_data['media_url'] = sub.media['oembed'].get('url', '')
                    post_data['media_provider'] = sub.media['oembed'].get('provider_name', '')
                    post_data['media_author'] = sub.media['oembed'].get('author_name', '')

            # Images et galeries
            try:
                if hasattr(sub, 'preview') and sub.preview:
                    images = sub.preview.get('images', [])
                    if images:
                        post_data['has_preview_images'] = True
                        post_data['preview_image_url'] = images[0]['source'].get('url', '')
                        post_data['preview_image_width'] = images[0]['source'].get('width', 0)
                        post_data['preview_image_height'] = images[0]['source'].get('height', 0)
            except:
                post_data['has_preview_images'] = False

            # Informations sur les galeries
            try:
                if hasattr(sub, 'is_gallery') and sub.is_gallery:
                    post_data['is_gallery'] = True
                    post_data['gallery_item_count'] = len(sub.gallery_data['items'])
                    post_data['gallery_urls'] = []

                    for item in sub.gallery_data['items']:
                        media_id = item['media_id']
                        if media_id in sub.media_metadata:
                            image_data = sub.media_metadata[media_id]
                            if 's' in image_data:
                                url = image_data['s'].get('u', '')
                                post_data['gallery_urls'].append(url)
            except:
                post_data['is_gallery'] = False

            return post_data

        except Exception as e:
            # En cas d'erreur, retourner un dictionnaire minimal avec l'erreur
            return {
                'id': sub.id if hasattr(sub, 'id') else 'unknown',
                'error': str(e)
            }

    def download_media(self, url, dest_dir, apply_filter=None, filenamedatapost="DataPosts.xlsx"):
        """Télécharge un média depuis l'URL donnée"""
        if url in self.seen_urls:
            return
        self.seen_urls.add(url)

        if self.items_data_df is None:
            self.items_data_df = self.load_from_excel(filenamedatapost)

        data_media = self.items_data_df[self.items_data_df['url'] == url]
        for key in apply_filter:
            if key in data_media.columns:
                try:
                    data_media = data_media.query(apply_filter[key])
                except:
                    pass

        if not data_media.empty or apply_filter is None:

            try:
                if url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.mp4', '.webm')):
                    ext = os.path.splitext(urlparse(url).path)[1] or '.bin'
                    filename = f"media_{url.split(ext)[0][-13:]}{ext}"
                    path = os.path.join(dest_dir, filename)
                    if not os.path.exists(path):
                        try:
                            urllib.request.urlretrieve(url, path)
                        except Exception as error:
                            print(f"Erreur lors du téléchargement de {url}: {error}")
                else:
                    ydl_opts = {
                        **self.YDL_OPTS,
                        "paths": {"home": dest_dir}
                    }

                    with YoutubeDL(ydl_opts) as ydl:
                        try:
                            ydl.download([url])
                        except Exception as error:
                            print(f"Erreur lors du téléchargement de {url} avec yt-dlp: {error}")

            except Exception:
                pass

    def download_severals_media(self, urls, apply_filter, filenamedatapost, dest_dir=None):
        """
        Télécharge plusieurs médias à partir d'une liste d'URLs.

        Args:
            urls (list): Liste d'URLs de médias à télécharger.
            dest_dir (str, optional): Répertoire de destination pour les téléchargements.
                                      Si None, utilise le répertoire par défaut.
        """
        if dest_dir is None:
            dest_dir = self.SAVE_DIR

        os.makedirs(dest_dir, exist_ok=True)

        threads = []
        for index, url in enumerate(urls):
            thread = threading.Thread(target=self.download_media, args=(url, dest_dir, apply_filter, filenamedatapost))
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

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


def StartRedditBot(account_identifier):
    return RedditCollector(account_identifier)


"""bot = StartRedditBot(account_identifier="No-Cookie-3706")
subs = bot.search_several_subreddits(keywords=["photo", "politique"], limit=4)
bot.save_to_excel(subs, key_column='id', filename="DataSubReddits.xlsx")
df = bot.load_from_excel(filename="DataSubReddits.xlsx").copy()
urls = bot.get_several_reddit_items_url(df['name'].tolist(), limit=5)
bot.download_severals_media(urls, apply_filter={"score": "score > 5000", "upvote_ratio": "upvote_ratio > 0.90", "ratio_subscribers_score": "ratio_subscribers_score > 0.00001"}, filenamedatapost="DataPosts.xlsx")
"""