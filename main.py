import sys
import os
import logging
import pandas as pd
from typing import List, Dict, Union

# Configuration du logger principal
logging.basicConfig(level=logging.INFO, format='>>> %(message)s')
logger = logging.getLogger("MainController")

# =============================================================================
# 1. GESTION DES IMPORTS ET CHEMINS
# =============================================================================
# On ajoute les sous-dossiers au path pour que Python trouve les modules
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, 'content_finder'))
sys.path.append(os.path.join(current_dir, 'utils'))
sys.path.append(os.path.join(current_dir, 'instagram'))
sys.path.append(os.path.join(current_dir, 'tiktok'))

# Importation de VOS modules
try:
    # Modules de recherche
    from content_finder.reddit_finder import RedditCollector
    from content_finder.youtube_finder import YouTubeManager
    from content_finder.ai_generator import AIContentGenerator

    # Modules d'édition
    from utils.video_editor import VideoEditor

    # Bots sociaux
    from instagram.instagram_bot import InstagramBot
    from tiktok.tiktok_bot import TikTokBot

    logger.info("Tous les modules ont été importés avec succès.")

except ImportError as e:
    logger.critical(f"Erreur d'importation : {e}")
    sys.exit(1)


# =============================================================================
# 2. FONCTIONS DE RECHERCHE (SANS TÉLÉCHARGEMENT)
# =============================================================================

def find_content(
        topics: List[str],
        content_types: List[str] = ['video', 'photo'],
        reddit_filters: Dict[str, str] = None,
        youtube_max_results: int = 5,
        subreddit_max: int = 5,
        max_results_by_sub: int = 5,
        youtube_min_duration: int = 0,  # NOUVEAU
        youtube_max_duration: int = None,  # NOUVEAU
        account_identifier_reddit: str = "MonCompteReddit") -> Dict[str, Union[pd.DataFrame, List[str]]]:
    """
    Recherche du contenu sur Reddit et YouTube sans le télécharger.

    Args:
        topics: Liste de mots-clés (ex: ['chats', 'espace']).
        content_types: Liste contenant 'video' et/ou 'photo'.
        reddit_filters: Filtres pandas (ex: {"score": "score > 1000"}).
        youtube_max_results: Nombre max de vidéos YouTube par sujet.

    Returns:
        Dictionnaire contenant les résultats trouvés :
        {
            'reddit': DataFrame (Posts filtrés),
            'youtube': List[str] (URLs trouvées)
        }
    """
    results = {
        'reddit': pd.DataFrame(),
        'youtube': []
    }

    # --- A. RECHERCHE REDDIT ---
    if 'photo' in content_types or 'video' in content_types:
        logger.info(f"--- Recherche Reddit sur : {topics} ---")
        try:
            reddit_bot = RedditCollector(account_identifier_reddit)

            # Déterminer le type prioritaire pour la recherche
            # Si on veut les deux, on laisse 'any', sinon on précise
            search_type = 'any'
            if 'video' in content_types and 'photo' not in content_types:
                search_type = 'video'
            elif 'photo' in content_types and 'video' not in content_types:
                search_type = 'photo'

            # 1. Trouver les subreddits pertinents
            subs_df = reddit_bot.search_subreddits(keywords=topics, limit=subreddit_max, save_excel=False)

            if not subs_df.empty:
                sub_names = subs_df['name'].tolist()

                posts_df = reddit_bot.get_subreddit_posts(
                    sub_names,
                    target_limit=max_results_by_sub,
                    content_type=search_type
                )

                if not posts_df.empty:
                    # 3. Appliquer les filtres de qualité (Score, Ratio...)
                    if reddit_filters:
                        posts_df = reddit_bot.filter_posts(posts_df, reddit_filters)

                    results['reddit'] = posts_df
                    logger.info(f"Reddit : {len(posts_df)} posts retenus au total.")

        except Exception as e:
            logger.error(f"Erreur lors de la recherche Reddit : {e}")

    # --- B. RECHERCHE YOUTUBE ---
    if 'video' in content_types:
        logger.info(f"--- Recherche YouTube sur : {topics} ---")
        try:
            yt_bot = YouTubeManager()
            all_urls = []

            for topic in topics:
                # Appel avec les nouveaux filtres de durée
                urls = yt_bot.search_videos(
                    topic,
                    max_results=youtube_max_results,
                    min_duration=youtube_min_duration,
                    max_duration=youtube_max_duration,
                    save_excel=False
                )
                all_urls.extend(urls)

            results['youtube'] = list(set(all_urls))
            logger.info(f"YouTube : {len(results['youtube'])} vidéos trouvées au total.")

        except Exception as e:
            logger.error(f"Erreur lors de la recherche YouTube : {e}")

    return results


# =============================================================================
# 3. FONCTION DE TÉLÉCHARGEMENT
# =============================================================================

def download_content(
        content_data: Dict[str, Union[pd.DataFrame, List[str]]],
        account_identifier_reddit: str = "MonCompteReddit"
):
    """
    Télécharge le contenu trouvé précédemment via find_content.
    """
    logger.info("--- Démarrage des téléchargements ---")

    # 1. Téléchargement Reddit
    df_reddit = content_data.get('reddit')
    if df_reddit is not None and not df_reddit.empty:
        logger.info("Téléchargement depuis Reddit...")
        reddit_bot = RedditCollector(account_identifier_reddit)
        # Le bot reddit utilise le DataFrame pour gérer les noms de fichiers et métadonnées
        reddit_bot.download_all_media(df_reddit, max_workers=5)
    else:
        logger.info("Pas de contenu Reddit à télécharger.")

    # 2. Téléchargement YouTube
    youtube_urls = content_data.get('youtube', [])
    if youtube_urls:
        logger.info("Téléchargement depuis YouTube...")
        yt_bot = YouTubeManager()
        # Le bot youtube prend une liste d'URLs
        yt_bot.download_multiple_videos(youtube_urls)
    else:
        logger.info("Pas de contenu YouTube à télécharger.")


# =============================================================================
# 4. EXEMPLE D'UTILISATION (ORCHESTRATION)
# =============================================================================

if __name__ == "__main__":

    # --- CONFIGURATION ---
    MES_SUJETS = ["Espace", "Astronomie"]
    TYPES_SOUHAITES = ["video"]  # ou ["photo"] ou ["video", "photo"]

    # Filtres spécifiques Reddit (Syntaxe pandas query)
    FILTRES_REDDIT = {
        "qualité": "score > 500",
        "ratio": "upvote_ratio > 0.85"
    }

    # --- ETAPE 1 : RECHERCHE ---
    # On récupère les liens et les métadonnées sans télécharger
    resultats = find_content(
        topics=MES_SUJETS,
        content_types=TYPES_SOUHAITES,
        reddit_filters=FILTRES_REDDIT,
        youtube_max_results=3,
        subreddit_max=0,
        max_results_by_sub=0,
        youtube_min_duration=60,  # Minimum 60 secondes
        youtube_max_duration=300,  # Maximum 10 minutes (600s)
        account_identifier_reddit="No-Cookie-3706"
    )

    # Affichage pour vérification
    print("\n=== RÉSUMÉ AVANT TÉLÉCHARGEMENT ===")
    if not resultats['reddit'].empty:
        print(f"Reddit: {len(resultats['reddit'])} posts prêts.")
        print(resultats['reddit'][['title', 'url']].head())

    if resultats['youtube']:
        print(f"YouTube: {len(resultats['youtube'])} liens prêts.")
        print(resultats['youtube'])
    print("===================================\n")

    # --- ETAPE 2 : TÉLÉCHARGEMENT (Optionnel) ---
    user_input = input("Voulez-vous lancer le téléchargement ? (y/n) : ")
    if user_input.lower() == 'y':
        download_content(resultats, account_identifier_reddit="No-Cookie-3706")
        print("Téléchargements terminés. Vérifiez le dossier 'videos'.")
    else:
        print("Opération annulée.")

    # --- ETAPE 3 : AUTOMATISATION ÉDITION (SPLIT + TRANSCRIPTION + SOUS-TITRES) ---
    user_input_edit = input("\nVoulez-vous traiter les vidéos (Split + Sous-titres) ? (y/n) : ")

    if user_input_edit.lower() == 'y':
        # Initialisation de l'éditeur (Assurez-vous que WhisperServer.py est lancé !)
        editor = VideoEditor(whisper_api_url="http://127.0.0.1:5000/transcribe", language="fr")

        base_videos_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'videos')

        # On liste uniquement les fichiers MP4 à la racine du dossier 'videos'
        # (pour ne pas re-traiter les segments qui sont déjà dans des sous-dossiers)
        video_files = [
            os.path.join(base_videos_dir, f) for f in os.listdir(base_videos_dir)
            if f.endswith('.mp4') and os.path.isfile(os.path.join(base_videos_dir, f))
        ]

        if not video_files:
            logger.warning(f"Aucune vidéo trouvée à la racine de : {base_videos_dir}")
        else:
            logger.info(f"Début du traitement pour {len(video_files)} vidéo(s).")

            for video_path in video_files:
                video_name = os.path.basename(video_path)
                logger.info(f"\n>>> TRAITEMENT DE : {video_name}")

                # 1. DÉCOUPAGE (Split)
                # La fonction split_video crée automatiquement un dossier au nom de la vidéo
                logger.info(" -> 1. Découpage en segments de 61s...")
                split_paths = editor.split_video(video_path, duration=61)

                if not split_paths:
                    logger.warning(" -> Aucun segment généré (vidéo trop courte ou erreur).")
                    continue

                # 2. BOUCLE SUR CHAQUE SEGMENT
                for i, segment_path in enumerate(split_paths, 1):
                    segment_name = os.path.basename(segment_path)
                    logger.info(f"   -> Segment {i}/{len(split_paths)} : {segment_name}")

                    try:
                        # A. Charger le segment en tant que vidéo courante
                        editor.load_video(segment_path)

                        # B. Extraire l'audio
                        logger.info("      Extraction audio...")
                        audio_path = editor.extract_audio(segment_path)

                        if audio_path:
                            # C. Transcription (Appel Serveur Whisper)
                            logger.info("      Envoi au serveur Whisper...")
                            transcription = editor.transcribe(
                                audio_path,
                                max_gap=0.5,  # Ajustable pour le rythme
                                max_words=4,  # Peu de mots pour le style TikTok dynamique
                                max_duration=2
                            )

                            if transcription:
                                # D. Création vidéo sous-titrée
                                logger.info("      Incrustation des sous-titres (Style TikTok)...")
                                final_path = editor.create_subtitled_video(
                                    video_path=segment_path,
                                    style_name="tiktok"  # Utilise le style défini dans VideoEditor
                                )

                                if final_path:
                                    logger.info(f"      [SUCCÈS] Vidéo prête : {os.path.basename(final_path)}")
                            else:
                                logger.warning(
                                    "      [ÉCHEC] Pas de transcription reçue (Vérifiez le serveur Whisper).")

                    except Exception as e:
                        logger.error(f"      [ERREUR] Problème sur le segment {segment_name}: {e}")

    print("\n=== PROCESSUS GLOBAL TERMINÉ ===")