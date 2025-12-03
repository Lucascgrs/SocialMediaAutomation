import os
import time
import json
import logging
import threading
import urllib.request
from urllib.parse import urlparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Union, Any

import pandas as pd
import praw
from yt_dlp import YoutubeDL

# Configuration du logger
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class RedditCollector:
    """
    Classe pour rechercher, collecter et télécharger du contenu depuis Reddit.
    Gère les images et les vidéos (via yt-dlp).
    """

    def __init__(self, account_identifier: str):
        self.account_identifier = account_identifier

        # Chemins
        self.base_dir = Path(__file__).parent.parent
        self.utils_dir = self.base_dir / 'utils'
        self.credentials_path = self.utils_dir / 'login_data.json'
        self.save_dir = self.base_dir / 'videos'
        self.save_dir.mkdir(parents=True, exist_ok=True)

        # Configuration API Reddit (À sécuriser idéalement via variables d'env)
        self.client_id = 'MhNAI4AXxIFqpWu5JteGmA'
        self.client_secret = 'v_Z8OU8iO-82i--JMOJdV59InlAbKA'
        self.user_agent = 'MyRedditImageDownloader/1.0'

        # État interne
        self.reddit: Optional[praw.Reddit] = None
        self.password: Optional[str] = None
        self.seen_urls = set()
        self.lock = threading.Lock()

        # Configuration Téléchargement
        self.ydl_opts = {
            "quiet": True,
            "outtmpl": str(self.save_dir / "%(title)s_%(id)s.%(ext)s"),
            "noplaylist": True,
            "merge_output_format": "mp4",
            "ignoreerrors": True,
            "no_warnings": True,
            "retries": 3,
            "socket_timeout": 15,
        }

        # Chargement et Connexion initiaux
        self._load_credentials()
        self.login()

    # =========================================================================
    # AUTHENTIFICATION
    # =========================================================================

    def _load_credentials(self):
        """Charge le mot de passe depuis le fichier JSON."""
        try:
            if not self.credentials_path.exists():
                logger.error(f"Fichier introuvable : {self.credentials_path}")
                return

            with open(self.credentials_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.password = data.get('Reddit', {}).get(self.account_identifier)
        except Exception as e:
            logger.error(f"Erreur lecture identifiants : {e}")

    def login(self):
        """Initialise l'instance PRAW."""
        if not self.password:
            logger.error("Mot de passe manquant. Impossible de se connecter.")
            return

        try:
            self.reddit = praw.Reddit(
                username=self.account_identifier,
                password=self.password,
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent
            )
            # Vérification simple
            logger.info(f"Connecté en tant que : {self.reddit.user.me()}")
        except Exception as e:
            logger.error(f"Échec connexion Reddit : {e}")

    # =========================================================================
    # RECHERCHE DE SUBREDDITS
    # =========================================================================

    def search_subreddits(self, keywords: List[str], limit: int = 10, save_excel: bool = True) -> pd.DataFrame:
        """
        Recherche intelligente des subreddits :
        1. Cherche d'abord strictement dans le NOM du subreddit (Priorité absolue).
        2. Complète avec une recherche large, MAIS vérifie que le mot-clé est dans le Titre ou la Description.
        """
        if not self.reddit: return pd.DataFrame()

        all_subs_data = []
        seen_names = set()

        for keyword in keywords:
            logger.info(f"Recherche intelligente pour : '{keyword}'")
            keyword_lower = keyword.lower().strip()

            subs_found_for_keyword = []

            try:
                # On demande BEAUCOUP de résultats (x10) pour pouvoir filtrer agressivement ensuite
                # Cela permet d'aller chercher les "petits" subs pertinents cachés derrière les gros subs populaires
                broad_results = list(self.reddit.subreddits.search(keyword, limit=limit * 10))

                # --- ETAPE 1 : Filtrage Strict (Le nom contient le mot-clé) ---
                strict_matches = []
                for sub in broad_results:
                    if keyword_lower in sub.display_name.lower():
                        strict_matches.append(sub)

                # On trie les stricts par nombre d'abonnés
                strict_matches.sort(key=lambda x: getattr(x, 'subscribers', 0) or 0, reverse=True)

                for sub in strict_matches:
                    if len(subs_found_for_keyword) >= limit: break
                    if sub.display_name not in seen_names:
                        subs_found_for_keyword.append(sub)
                        seen_names.add(sub.display_name)

                logger.info(f" -> {len(subs_found_for_keyword)} résultats stricts (Nom) trouvés.")

                # --- ETAPE 2 : Complément Sélectif ---
                if len(subs_found_for_keyword) < limit:
                    remaining_needed = limit - len(subs_found_for_keyword)

                    # On trie le reste par pertinence (abonnés)
                    broad_results.sort(key=lambda x: getattr(x, 'subscribers', 0) or 0, reverse=True)

                    for sub in broad_results:
                        if remaining_needed <= 0: break

                        if sub.display_name in seen_names:
                            continue

                        # VÉRIFICATION SUPPLÉMENTAIRE :
                        # Le mot clé DOIT être dans le titre public ou la description
                        # Sinon on rejette (ça évite r/france pour "espace")
                        title_match = keyword_lower in (sub.title or "").lower()
                        desc_match = keyword_lower in (sub.public_description or "").lower()

                        if title_match or desc_match:
                            subs_found_for_keyword.append(sub)
                            seen_names.add(sub.display_name)
                            remaining_needed -= 1

                logger.info(f" -> Total retenu pour '{keyword}': {len(subs_found_for_keyword)}")

                # Extraction des données
                for sub in subs_found_for_keyword:
                    try:
                        data = {
                            'name': sub.display_name,
                            'title': sub.title,
                            'subscribers': getattr(sub, 'subscribers', 0),
                            'description': getattr(sub, 'public_description', '') or '',
                            'created_utc': datetime.fromtimestamp(sub.created_utc).strftime('%Y-%m-%d'),
                            'is_nsfw': sub.over18,
                            'url': f"https://reddit.com{sub.url}"
                        }
                        all_subs_data.append(data)
                    except Exception as e:
                        logger.warning(f"Erreur lecture sub {sub}: {e}")

            except Exception as e:
                logger.error(f"Erreur recherche mot-clé {keyword}: {e}")

        df = pd.DataFrame(all_subs_data)

        if save_excel and not df.empty:
            self.save_to_excel(df, "DataSubReddits.xlsx", key_column='name')

        return df

    # =========================================================================
    # COLLECTE DES POSTS
    # =========================================================================

    def get_subreddit_posts(self, sub_names: List[str], target_limit: int = 10, content_type: str = 'any') -> pd.DataFrame:
        """
        Récupère les posts de plusieurs subreddits jusqu'à atteindre la limite désirée
        pour un type de contenu spécifique.

        Args:
            sub_names: Liste des noms de subreddits.
            target_limit: Nombre de posts SOUHAITÉS par subreddit (après filtrage).
            content_type: 'video', 'photo' ou 'any'.
        """
        if not self.reddit: return pd.DataFrame()

        all_posts = []

        for sub_name in sub_names:
            logger.info(f"Récupération r/{sub_name} (Cible: {target_limit} {content_type}s)...")

            valid_posts_for_sub = []
            try:
                subreddit = self.reddit.subreddit(sub_name)

                # On utilise un générateur pour parcourir les posts un par un sans limite initiale stricte
                # mais on met une limite de sécurité (ex: 500) pour ne pas boucler à l'infini si le sub est vide
                post_generator = subreddit.top(limit=500, time_filter='all')

                for post in post_generator:
                    # Si on a assez de posts pour ce sub, on arrête
                    if len(valid_posts_for_sub) >= target_limit:
                        break

                    post_data = self._extract_post_data(post)
                    if not post_data:
                        continue

                    is_valid = True
                    if content_type == 'video' and not post_data['is_video']:
                        is_valid = False
                    elif content_type == 'photo' and post_data[
                        'is_video']:  # Si c'est une vidéo, ce n'est pas une photo
                        is_valid = False

                    if is_valid:
                        valid_posts_for_sub.append(post_data)

                logger.info(f" -> Trouvé {len(valid_posts_for_sub)} posts valides sur r/{sub_name}")
                all_posts.extend(valid_posts_for_sub)

            except Exception as e:
                logger.error(f"Erreur sur r/{sub_name}: {e}")

        df = pd.DataFrame(all_posts)
        if not df.empty:
            self.save_to_excel(df, "DataPosts.xlsx", key_column='id')

        return df

    def _extract_post_data(self, post) -> Optional[Dict]:
        """Extrait proprement les données d'un objet Submission."""
        try:
            # Détection du type de média
            url = post.url
            is_video = False
            is_image = False

            if url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                is_image = True
            elif post.is_video or any(d in url for d in ['youtu', 'v.redd.it', 'gfycat', 'redgifs']):
                is_video = True
                # Si c'est une vidéo Reddit, on prend l'URL de fallback si possible
                if hasattr(post, 'media') and post.media and 'reddit_video' in post.media:
                    url = post.media['reddit_video'].get('fallback_url', url)

            # Si ce n'est ni image ni vidéo exploitable, on ignore (souvent du texte ou liens externes)
            if not is_image and not is_video:
                return None

            return {
                'id': post.id,
                'title': post.title,
                'url': url,
                'permalink': f"https://reddit.com{post.permalink}",
                'score': post.score,
                'num_comments': post.num_comments,
                'upvote_ratio': post.upvote_ratio,
                'subreddit': str(post.subreddit),
                'subscribers': getattr(post.subreddit, 'subscribers', 1),  # 1 pour éviter division par zéro
                'created_utc': datetime.fromtimestamp(post.created_utc).strftime('%Y-%m-%d %H:%M:%S'),
                'is_video': is_video,
                'is_nsfw': post.over_18,
                # Métrique personnalisée
                'engagement_ratio': post.score / (getattr(post.subreddit, 'subscribers', 1) or 1)
            }
        except Exception as e:
            logger.debug(f"Erreur extraction post {getattr(post, 'id', 'unknown')}: {e}")
            return None

    # =========================================================================
    # FILTRAGE ET TÉLÉCHARGEMENT
    # =========================================================================

    def filter_posts(self, df: pd.DataFrame, filters: Dict[str, str]) -> pd.DataFrame:
        """
        Filtre le DataFrame selon des critères.
        Exemple filters: {"score": "score > 1000", "ratio": "upvote_ratio > 0.9"}
        """
        if df.empty: return df

        filtered_df = df.copy()
        try:
            for name, query_str in filters.items():
                original_len = len(filtered_df)
                filtered_df = filtered_df.query(query_str)
                logger.info(f"Filtre '{name}' appliqué : {original_len} -> {len(filtered_df)} posts restants.")
        except Exception as e:
            logger.error(f"Erreur dans la requête de filtrage : {e}")

        return filtered_df

    def download_all_media(self, df: pd.DataFrame, max_workers: int = 5):
        """
        Télécharge les médias listés dans le DataFrame en utilisant des threads.
        """
        if df.empty:
            logger.warning("Aucun post à télécharger.")
            return

        urls_to_download = df['url'].tolist()
        titles = df['title'].tolist()
        ids = df['id'].tolist()

        logger.info(f"Démarrage du téléchargement de {len(urls_to_download)} fichiers...")

        threads = []
        # Zip pour avoir URL, Titre et ID ensemble
        items = list(zip(urls_to_download, titles, ids))

        # Découpage simple pour l'exemple (on pourrait utiliser ThreadPoolExecutor pour faire mieux)
        # Ici je garde ta logique manuelle de threads pour ne pas trop changer la structure

        # On traite par lots pour ne pas lancer 1000 threads d'un coup
        chunk_size = max_workers
        for i in range(0, len(items), chunk_size):
            chunk = items[i:i + chunk_size]
            batch_threads = []

            for url, title, post_id in chunk:
                t = threading.Thread(target=self._download_single_media, args=(url, title, post_id))
                batch_threads.append(t)
                t.start()

            for t in batch_threads:
                t.join()

        logger.info("Tous les téléchargements sont terminés.")

    def _download_single_media(self, url: str, title: str, post_id: str):
        """Logique unitaire de téléchargement."""
        # Nettoyage du titre pour le nom de fichier
        clean_title = "".join([c for c in title if c.isalnum() or c in (' ', '-', '_')]).strip()[:50]

        # Vérification doublon URL
        with self.lock:
            if url in self.seen_urls: return
            self.seen_urls.add(url)

        try:
            # Cas 1 : Vidéo (Youtube, Reddit Video, etc) -> yt-dlp
            # On détecte si c'est une image simple par l'extension
            parsed = urlparse(url)
            ext = os.path.splitext(parsed.path)[1]

            is_simple_image = ext.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']

            if is_simple_image:
                filename = f"{clean_title}_{post_id}{ext}"
                filepath = self.save_dir / filename
                if not filepath.exists():
                    urllib.request.urlretrieve(url, filepath)
                    logger.info(f"[IMG] Téléchargé : {filename}")
            else:
                # C'est probablement une vidéo -> yt-dlp
                # On met à jour le template pour ce fichier spécifique
                opts = self.ydl_opts.copy()
                # On force un nom de fichier spécifique
                opts['outtmpl'] = str(self.save_dir / f"{clean_title}_{post_id}.%(ext)s")

                with YoutubeDL(opts) as ydl:
                    ydl.download([url])
                logger.info(f"[VID] Téléchargé : {clean_title}")

        except Exception as e:
            logger.error(f"Échec téléchargement {url}: {e}")

    # =========================================================================
    # UTILITAIRES EXCEL
    # =========================================================================

    def save_to_excel(self, df: pd.DataFrame, filename: str, key_column: str = 'id'):
        """Sauvegarde intelligente (mise à jour des existants, ajout des nouveaux)."""
        path = self.base_dir / filename
        try:
            if path.exists():
                existing_df = pd.read_excel(path)
                # Concaténation
                combined = pd.concat([existing_df, df])
                # Suppression doublons basée sur la clé, on garde le dernier (le plus récent)
                final_df = combined.drop_duplicates(subset=[key_column], keep='last')
            else:
                final_df = df

            final_df.to_excel(path, index=False)
            logger.info(f"Données sauvegardées dans {filename}")
        except Exception as e:
            logger.error(f"Erreur Excel : {e}")

    def load_from_excel(self, filename: str) -> pd.DataFrame:
        path = self.base_dir / filename
        if path.exists():
            return pd.read_excel(path)
        return pd.DataFrame()


def start_reddit_bot(account_identifier: str) -> RedditCollector:
    return RedditCollector(account_identifier)


if __name__ == "__main__":
    # Exemple d'utilisation
    # bot = start_reddit_bot("MonCompteReddit")
    # if bot.reddit:
    #     df = bot.get_subreddit_posts(["france", "space"], limit=10)
    #     filtered = bot.filter_posts(df, {"score": "score > 100"})
    #     bot.download_all_media(filtered)
    pass