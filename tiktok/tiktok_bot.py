import datetime
import logging
import os
import time
import json
from typing import List, Optional
import pandas as pd
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


class TikTokBot:
    def __init__(self):
        self.api = None
        self.logged_in = False
        self.username = None
        self.user_id = None
        self.playwright = None
        self.browser = None
        self.page = None
        self.VideoNumber = 1

        # Dossier pour stocker les données persistantes du navigateur
        self.user_data_dir = os.path.join(os.path.expanduser('~'), 'tiktok_browser_data')
        self.utils_directory = os.getcwd() + '\\..\\utils'
        self.Connection_file_name = os.path.join(self.utils_directory, 'login_data.json')
        self.login_data = {}

        self.GlobalXPaths = {'homepage': '//*[@id="app"]/div[2]/div/div/div[3]/div[1]/h2[1]/div/a/button', 'explore': '//*[@id="app"]/div[2]/div/div/div[3]/div[1]/h2[2]/div/a/button', 'activity': '//*[@id="app"]/div[2]/div[1]/div/div[3]/div[1]/div[6]/button', 'profile': '//*[@id="app"]/div[2]/div[1]/div/div[3]/div[1]/div[9]/a/button', 'upload': '//*[@id="app"]/div[2]/div[1]/div/div[3]/div[1]/div[8]/a/button', 'seek': '//*[@id="app"]/div[2]/div/div/div[2]/div[2]/button', 'main': '//*[@id="app"]/div[2]/div/div/div[2]/div[1]/a', 'AcceptCookies': '/html/body/tiktok-cookie-banner//div/div[2]/button[2]', "Logout": '//*[@id="floating-ui-5"]/div/div/span'}
        self.CurrentTikTokXPaths = {'CreatorName': '//*[@id="one-column-item-REPLACE"]/div/div[3]/div[2]/div[2]/div[1]/div[1]/div/a/div', 'Description': '//*[@id="one-column-item-REPLACE"]/div/div[3]/div[2]/div[2]/div[1]/div[2]/div/div/div/span', "follow": '//*[@id="column-list-container"]/article[REPLACE]/div/section[2]/div[1]/button', 'LikeNumber': '//*[@id="column-list-container"]/article[REPLACE]/div/section[2]/button[1]/strong', 'Like': '//*[@id="column-list-container"]/article[REPLACE]/div/section[2]/button[1]', 'CommentNumber': '//*[@id="column-list-container"]/article[REPLACE]/div/section[2]/button[2]/strong', 'OpenCommentSection': '//*[@id="column-list-container"]/article[REPLACE]/div/section[2]/button[2]', 'Favorite': '//*[@id="column-list-container"]/article[REPLACE]/div/section[2]/div[2]/button', 'FavoriteNumber': '//*[@id="column-list-container"]/article[REPLACE]/div/section[2]/div[2]/button/strong', 'Share': '//*[@id="column-list-container"]/article[REPLACE]/div/section[2]/button[3]', 'ShareNumer': '//*[@id="column-list-container"]/article[REPLACE]/div/section[2]/button[3]/strong', 'Next':'//*[@id="main-content-homepage_hot"]/aside/div/div[2]/button', 'Previous': '//*[@id="main-content-homepage_hot"]/aside/div/div[1]/button', 'HashTags': '//*[@id="one-column-item-REPLACE"]/div/div[3]/div[2]/div[2]/div[1]/div[2]/div/div/div/a[REEPLACE]'}
        self.UserProfileXPaths = {'Followers': '//*[@id="main-content-others_homepage"]/div/div[1]/div[2]/div[3]/h3/div[2]/strong', 'Following': '//*[@id="main-content-others_homepage"]/div/div[1]/div[2]/div[3]/h3/div[1]/strong', 'Likes': '//*[@id="main-content-others_homepage"]/div/div[1]/div[2]/div[3]/h3/div[1]/strong', 'LikesNumber': '//*[@id="main-content-others_homepage"]/div/div[1]/div[2]/div[3]/h3/div[3]/strong', 'Follow': '//*[@id="main-content-others_homepage"]/div/div[1]/div[2]/div[2]/div/button', 'Video': '//*[@id="column-item-video-container-REPLACE"]', 'URLVideo': '//*[@id="column-item-video-container-REPLACE"]/div/div/div/a', 'LabelFollowingButton': '//*[@id="main-content-others_homepage"]/div/div[1]/div[2]/div[2]/div/button/div/div'}

    # ------------------ GESTION DES COOKIES ----------------

    def accept_cookies(self):
        """
        Accepter les cookies s'ils sont proposés
        """
        try:
            if self.page:
                self.page.wait_for_selector(self.GlobalXPaths['AcceptCookies'], state='visible', timeout=10000)
                self.page.click(self.GlobalXPaths['AcceptCookies'])
                logger.info("Cookies acceptés")
        except:
            logger.info("Pas de pop-up de cookies ou erreur lors de l'acceptation")

    def save_cookies(self):
        """
        Sauvegarder les cookies pour une utilisation ultérieure
        """
        try:
            if self.browser and self.page:
                cookies = self.page.context.cookies()
                with open(os.path.join(self.user_data_dir, 'cookies.json'), 'w') as f:
                    json.dump(cookies, f)
                logger.info("Cookies sauvegardés avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des cookies: {e}")

    def load_cookies(self):
        """
        Charger les cookies sauvegardés
        """
        cookies_path = os.path.join(self.user_data_dir, 'cookies.json')
        try:
            if os.path.exists(cookies_path):
                with open(cookies_path, 'r') as f:
                    cookies = json.load(f)
                self.page.context.add_cookies(cookies)
                logger.info("Cookies chargés avec succès")
                return True
            return False
        except Exception as e:
            logger.error(f"Erreur lors du chargement des cookies: {e}")
            return False

    # ------------------ CONNEXION ----------------

    def login(self, account_identifier) -> bool:
        """
        Ouvre une fenêtre de navigateur contrôlable pour TikTok

        Returns:
            bool: True si le navigateur a été ouvert avec succès
        """
        try:

            # Charger les données de connexion
            self.get_user_login(account_identifier)

            # Créer le dossier pour les données persistantes s'il n'existe pas
            os.makedirs(self.user_data_dir, exist_ok=True)

            # Initialiser Playwright
            self.playwright = sync_playwright().start()

            # CORRECTION: Utiliser une des deux méthodes suivantes pour la persistance

            # MÉTHODE 1: Utiliser launch_persistent_context (RECOMMANDÉ)
            context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=self.user_data_dir,
                headless=False,
                slow_mo=50,
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
                args=['--disable-blink-features=AutomationControlled']
            )
            self.browser = None  # Pas de browser séparé avec cette méthode
            self.page = context.pages[0] if context.pages else context.new_page()

            self.page.goto('https://www.tiktok.com')
            time.sleep(2)

            # Vérifier si déjà connecté
            if self.is_logged_in():
                logger.info(f"Déjà connecté à TikTok avec la session sauvegardée")
                self.logged_in = True
                time.sleep(2)
                self.accept_cookies()
                return True

            self.accept_cookies()

            self.page.wait_for_selector('#top-right-action-bar-login-button', state='visible', timeout=10000)
            self.page.click('#top-right-action-bar-login-button')

            time.sleep(2)

            self.page.wait_for_selector('//*[@id="loginContainer"]/div[1]/div/div/div[2]/div[2]/div[2]', state='visible', timeout=10000)
            self.page.click('//*[@id="loginContainer"]/div[1]/div/div/div[2]/div[2]/div[2]')

            time.sleep(2)

            self.page.wait_for_selector('//*[@id="loginContainer"]/div[1]/div/a', state='visible', timeout=10000)
            self.page.click('//*[@id="loginContainer"]/div[1]/div/a')

            time.sleep(2)

            self.page.wait_for_selector('//*[@id="loginContainer"]/div[2]/form/div[1]/input', state='visible', timeout=10000)
            self.page.fill('//*[@id="loginContainer"]/div[2]/form/div[1]/input', account_identifier)

            time.sleep(2)

            self.page.wait_for_selector('//*[@id="loginContainer"]/div[2]/form/div[2]/div/input', state='visible', timeout=10000)
            self.page.fill('//*[@id="loginContainer"]/div[2]/form/div[2]/div/input', self.login_data)

            time.sleep(2)

            self.page.wait_for_selector('//*[@id="loginContainer"]/div[2]/form/button', state='visible', timeout=10000)
            self.page.click('//*[@id="loginContainer"]/div[2]/form/button')

            self.logged_in = True

            return True

        except Exception as e:
            logger.error(f"Erreur lors de l'ouverture du navigateur: {e}")
            self.cleanup_browser()
            return False

    def logout(self):
        """
        Déconnecter l'utilisateur de TikTok
        """
        self._check_login()
        try:
            self.page.wait_for_selector(self.GlobalXPaths['Logout'], state='visible', timeout=10000)
            self.page.click(self.GlobalXPaths['Logout'])
            logger.info("Déconnexion réussie")
            self.logged_in = False
            self.cleanup_browser()
        except Exception as e:
            logger.error(f"Erreur lors de la déconnexion: {e}")
            self.cleanup_browser()

    def is_logged_in(self):
        """
        Vérifier si l'utilisateur est déjà connecté à TikTok
        """
        try:
            if self.page.query_selector('//*[@id="top-right-action-bar"]/div[5]/button/div/div/div/img') is not None:
                return True

            return False
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de l'état de connexion: {e}")
            return False

    def cleanup_browser(self):
        """Nettoyer les ressources du navigateur"""
        try:
            if self.page and self.page.context:
                self.page.context.close()
            if self.browser:  # Seulement si on utilise la méthode 2
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage du navigateur: {e}")

    def _check_login(self):
        """Vérifier si l'utilisateur est connecté"""
        if not self.logged_in or not self.page:
            raise Exception("Vous devez être connecté pour utiliser cette fonction")

    # ------------------ NAVIGATION ----------------

    def go_homepage(self):
        """
        Aller à la page d'accueil de TikTok
        """
        self._check_login()
        try:
            self.page.wait_for_selector(self.GlobalXPaths['homepage'], state='visible', timeout=10000)
            self.page.click(self.GlobalXPaths['homepage'])
            logger.info("Navigué vers la page d'accueil")
        except Exception as e:
            logger.error(f"Erreur lors de la navigation vers la page d'accueil : {e}")
            self.cleanup_browser()

    def go_explore(self):
        """
        Aller à la page Explorer de TikTok
        """
        self._check_login()
        try:
            self.page.goto('https://www.tiktok.com/explore')
            self.page.wait_for_selector(self.GlobalXPaths['explore'], state='visible', timeout=5000)
            self.page.click(self.GlobalXPaths['explore'])
            logger.info("Navigué vers la page Explorer")
        except Exception as e:
            logger.error(f"Erreur lors de la navigation vers la page Explorer : {e}")
            #self.cleanup_browser()

    def go_activity(self):
        """
        Aller à la page Activité de TikTok
        """
        self._check_login()
        try:
            self.page.goto('https://www.tiktok.com/activity')
            self.page.wait_for_selector(self.GlobalXPaths['activity'], state='visible', timeout=5000)
            self.page.click(self.GlobalXPaths['activity'])
            logger.info("Navigué vers la page Activité")
        except Exception as e:
            logger.error(f"Erreur lors de la navigation vers la page Activité : {e}")
            #self.cleanup_browser()

    def go_profile(self):
        """
        Aller à la page Profil de TikTok
        """
        self._check_login()
        try:
            self.page.goto('https://www.tiktok.com/@' + self.username)
            self.page.wait_for_selector(self.GlobalXPaths['profile'], state='visible', timeout=5000)
            self.page.click(self.GlobalXPaths['profile'])
            logger.info("Navigué vers la page Profil")
        except Exception as e:
            logger.error(f"Erreur lors de la navigation vers la page Profil : {e}")
            #self.cleanup_browser()

    def go_upload(self):
        """
        Aller à la page de téléchargement de TikTok
        """
        self._check_login()
        try:
            self.page.goto('https://www.tiktok.com/upload')
            self.page.wait_for_selector(self.GlobalXPaths['upload'], state='visible', timeout=5000)
            self.page.click(self.GlobalXPaths['upload'])
            logger.info("Navigué vers la page de téléchargement")
        except Exception as e:
            logger.error(f"Erreur lors de la navigation vers la page de téléchargement : {e}")
            #self.cleanup_browser()

    def go_seek(self):
        """
        Aller à la page de recherche de TikTok
        """
        self._check_login()
        try:
            self.page.goto('https://www.tiktok.com/search')
            self.page.wait_for_selector(self.GlobalXPaths['seek'], state='visible', timeout=5000)
            self.page.click(self.GlobalXPaths['seek'])
            logger.info("Navigué vers la page de recherche")
        except Exception as e:
            logger.error(f"Erreur lors de la navigation vers la page de recherche : {e}")
            #self.cleanup_browser()

    def go_main(self):
        """
        Aller à la page principale de TikTok
        """
        self._check_login()
        try:
            self.page.goto('https://www.tiktok.com')
            self.page.wait_for_selector(self.GlobalXPaths['main'], state='visible', timeout=5000)
            self.page.click(self.GlobalXPaths['main'])
            logger.info("Navigué vers la page principale")
        except Exception as e:
            logger.error(f"Erreur lors de la navigation vers la page principale : {e}")
            #self.cleanup_browser()

    # ------------------ INTERACTIONS AVEC LES VIDÉOS ----------------

    def is_video_or_live(self, VideoNumber=-1):
        """
        Détermine si le contenu actuel est une vidéo ou un live stream.

        Args:
            VideoNumber: Numéro de la vidéo à vérifier (par défaut -1 pour la vidéo actuelle)

        Returns:
            str: "video" si c'est une vidéo normale, "live" si c'est un live stream
        """
        self._check_login()

        if VideoNumber == -1:
            VideoNumber = self.VideoNumber

        try:
            self.page.wait_for_selector(self.CurrentTikTokXPaths['Like'].replace('REPLACE', str(VideoNumber)), timeout=10000)
            like = self.page.query_selector(self.CurrentTikTokXPaths['Like'].replace('REPLACE', str(VideoNumber))).inner_text()
            if like:
                return "video"
            else:
                logger.info("Contenu actuel est un live stream")
                return "live"
        except Exception as e:
            logger.error(f"Erreur lors de la vérification du type de contenu : {e}")
            return "Live"

    def like_current_video(self, VideoNumber=-1):
        """
        Liker une vidéo TikTok

        Args:
            video_id: ID de la vidéo

        Returns:
            bool: True si le like a réussi
        """
        self._check_login()

        if VideoNumber == -1:
            VideoNumber = self.VideoNumber

        try:
            if self.is_video_or_live() == 'video':
                selector = self.CurrentTikTokXPaths['Like'].replace('REPLACE', str(VideoNumber))
                self.page.wait_for_selector(selector, timeout=10000)
                self.page.click(selector)
                logger.info(f"Vidéo {VideoNumber} likée avec succès")
            else:
                logger.error("Le contenu actuel est un live stream, le like n'est pas applicable.")

        except Exception as e:
            logger.error(f"Erreur lors du like : {e}")
            #self.cleanup_browser()

    def follow_current_creator(self, VideoNumber=-1):
        """
        Suivre le créateur de la vidéo actuelle

        Args:
            VideoNumber: Numéro de la vidéo (par défaut -1 pour la vidéo actuelle)

        Returns:
            bool: True si le suivi a réussi
        """
        self._check_login()

        if VideoNumber == -1:
            VideoNumber = self.VideoNumber

        try:
            if self.is_video_or_live() == 'video':
                self.page.wait_for_selector(self.CurrentTikTokXPaths['follow'].replace('REPLACE', str(VideoNumber)), state='visible', timeout=5000)
                self.page.click(self.CurrentTikTokXPaths['follow'].replace('REPLACE', str(VideoNumber)))
                logger.info(f"Créateur de la vidéo {VideoNumber} suivi avec succès")
                return True
        except Exception as e:
            logger.error(f"Erreur lors du suivi du créateur : {e}")
            return False

    def add_favorite_current_video(self, VideoNumber=-1):
        """
        Ajouter la vidéo actuelle aux favoris

        Args:
            VideoNumber: Numéro de la vidéo (par défaut -1 pour la vidéo actuelle)

        Returns:
            bool: True si l'ajout aux favoris a réussi
        """
        self._check_login()

        if VideoNumber == -1:
            VideoNumber = self.VideoNumber

        try:
            if self.is_video_or_live() == 'video':
                self.page.wait_for_selector(self.CurrentTikTokXPaths['Favorite'].replace('REPLACE', str(VideoNumber)), state='visible', timeout=5000)
                self.page.click(self.CurrentTikTokXPaths['Favorite'].replace('REPLACE', str(VideoNumber)))
                logger.info(f"Vidéo {VideoNumber} ajoutée aux favoris avec succès")
                return True
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout aux favoris : {e}")
            return False

    def share_current_video(self, VideoNumber=-1):
        """
        Partager la vidéo actuelle

        Args:
            VideoNumber: Numéro de la vidéo (par défaut -1 pour la vidéo actuelle)

        Returns:
            bool: True si le partage a réussi
        """
        self._check_login()

        if VideoNumber == -1:
            VideoNumber = self.VideoNumber

        try:
            if self.is_video_or_live() == 'video':
                self.page.wait_for_selector(self.CurrentTikTokXPaths['Share'].replace('REPLACE', str(VideoNumber)), state='visible', timeout=5000)
                self.page.click(self.CurrentTikTokXPaths['Share'].replace('REPLACE', str(VideoNumber)))
                logger.info(f"Vidéo {VideoNumber} partagée avec succès")
                return True
        except Exception as e:
            logger.error(f"Erreur lors du partage de la vidéo : {e}")
            return False

    def go_next_video(self):
        """
        Aller à la vidéo suivante
        """
        self._check_login()
        try:
            self.page.wait_for_selector(self.CurrentTikTokXPaths['Next'], state='visible', timeout=5000)
            self.page.click(self.CurrentTikTokXPaths['Next'])
            self.VideoNumber += 1
            logger.info(f"Passé à la vidéo {self.VideoNumber}")
        except Exception as e:
            logger.error(f"Erreur lors du passage à la vidéo suivante : {e}")
            self.cleanup_browser()

    def go_previous_video(self):
        """
        Aller à la vidéo précédente
        """
        self._check_login()
        try:
            self.page.wait_for_selector(self.CurrentTikTokXPaths['Previous'], state='visible', timeout=5000)
            self.page.click(self.CurrentTikTokXPaths['Previous'])
            if self.VideoNumber > 0:
                self.VideoNumber -= 1
            logger.info(f"Revenu à la vidéo {self.VideoNumber}")
        except Exception as e:
            logger.error(f"Erreur lors du retour à la vidéo précédente : {e}")
            self.cleanup_browser()

    def get_current_creator(self, VideoNumber=-1):
        """
        Obtenir le nom du créateur de la vidéo actuelle

        Returns:
            str: Nom du créateur
        """

        self._check_login()

        if VideoNumber == -1:
            VideoNumber = self.VideoNumber

        try:
            if self.is_video_or_live() == 'video':
                creator_name = self.page.query_selector(self.CurrentTikTokXPaths['CreatorName'].replace('REPLACE', str(VideoNumber - 1))).inner_text()
                logger.info(f"Créateur actuel : {creator_name}")
                return creator_name
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du créateur : {e}")
            return None

    def get_current_description(self, VideoNumber=-1):
        """
        Obtenir la description de la vidéo actuelle

        Returns:
            str: Description de la vidéo
        """

        self._check_login()

        if VideoNumber == -1:
            VideoNumber = self.VideoNumber

        try:
            if self.is_video_or_live() == 'video':
                description = self.page.query_selector(self.CurrentTikTokXPaths['Description'].replace('REPLACE', str(VideoNumber - 1))).inner_text()
                logger.info(f"Description actuelle : {description}")
                return description
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la description : {e}")
            return None

    def get_current_hashtags(self, VideoNumber=-1):
        """
        Obtenir les hashtags de la vidéo actuelle

        Returns:
            List[str]: Liste des hashtags
        """

        self._check_login()

        if VideoNumber == -1:
            VideoNumber = self.VideoNumber

        try:
            if self.is_video_or_live() == 'video':
                hashtags_list = []
                indexhashtags = 1
                while True:
                    hashtag = self.page.query_selector(self.CurrentTikTokXPaths['HashTags'].replace('REPLACE', str(VideoNumber - 1)).replace('REEPLACE', str(indexhashtags)))
                    if hashtag:
                        hashtags_list.append(hashtag.inner_text())
                        indexhashtags += 1
                    else:
                        break
                return hashtags_list
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des hashtags : {e}")
            return []

    def get_current_likes_number(self, VideoNumber=-1):
        """
        Obtenir le nombre de likes de la vidéo actuelle

        Returns:
            int: Nombre de likes
        """

        self._check_login()

        if VideoNumber == -1:
            VideoNumber = self.VideoNumber

        try:
            if self.is_video_or_live() == 'video':
                likes = self.page.query_selector(self.CurrentTikTokXPaths['LikeNumber'].replace('REPLACE', str(VideoNumber))).inner_text()
                logger.info(f"Nombre de likes actuel : {likes}")
                return likes
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du nombre de likes : {e}")
            return 0

    def get_current_comments_number(self, VideoNumber=-1):
        """
        Obtenir le nombre de commentaires de la vidéo actuelle

        Returns:
            int: Nombre de commentaires
        """

        self._check_login()

        if VideoNumber == -1:
            VideoNumber = self.VideoNumber

        try:
            if self.is_video_or_live() == 'video':
                comments = self.page.query_selector(self.CurrentTikTokXPaths['CommentNumber'].replace('REPLACE', str(VideoNumber))).inner_text()
                logger.info(f"Nombre de commentaires actuel : {comments}")
                return comments
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du nombre de commentaires : {e}")
            return 0

    def get_current_favorites_number(self, VideoNumber=-1):
        """
        Obtenir le nombre de favoris de la vidéo actuelle

        Returns:
            int: Nombre de favoris
        """

        self._check_login()

        if VideoNumber == -1:
            VideoNumber = self.VideoNumber

        try:
            if self.is_video_or_live() == 'video':
                favorites = self.page.query_selector(self.CurrentTikTokXPaths['FavoriteNumber'].replace('REPLACE', str(VideoNumber))).inner_text()
                logger.info(f"Nombre de favoris actuel : {favorites}")
                return favorites
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du nombre de favoris : {e}")
            return 0

    def get_current_shares_number(self, VideoNumber=-1):
        """
        Obtenir le nombre de partages de la vidéo actuelle

        Returns:
            int: Nombre de partages
        """

        self._check_login()

        if VideoNumber == -1:
            VideoNumber = self.VideoNumber

        try:
            if self.is_video_or_live() == 'video':
                shares = self.page.query_selector(self.CurrentTikTokXPaths['ShareNumer'].replace('REPLACE', str(VideoNumber))).inner_text()
                logger.info(f"Nombre de partages actuel : {shares}")
                return shares
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du nombre de partages : {e}")
            return 0

    def collect_fyp_data(self, start_video_number=1, video_count=10, filename='tiktok_fyp_data.xlsx'):
        """
        Collecte les données de plusieurs vidéos TikTok et les enregistre dans un fichier Excel

        Args:
            start_video_number: Numéro de la vidéo de départ (default: 1)
            video_count: Nombre de vidéos à analyser (default: 10)
            filename: Nom du fichier Excel pour les données (default: 'tiktok_fyp_data.xlsx')

        Returns:
            pd.DataFrame: Dataframe contenant les données collectées
        """

        filename = os.path.join(os.getcwd(), filename)

        self._check_login()

        # Définir le numéro de vidéo actuel
        self.VideoNumber = start_video_number

        # Préparer la structure pour stocker les données
        data = []

        # Fonction helper pour obtenir une donnée avec gestion d'erreur
        def safe_get(getter_func, error_message="Erreur lors de la récupération"):
            try:
                return getter_func()
            except Exception as e:
                logger.error(f"{error_message}: {e}")
                return None

        print(f"Début de la collecte de données pour {video_count} vidéos, à partir de la vidéo #{start_video_number}")

        # Parcourir les vidéos
        for i in range(video_count):
            video_num = start_video_number + i
            print(f"Collecte des données pour la vidéo #{video_num} ({i + 1}/{video_count})")

            # Collecter les données de la vidéo actuelle
            video_data = {
                'date_collecte': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'video_number': video_num,
                'type_contenu': safe_get(lambda: self.is_video_or_live(), "Erreur de détermination du type"),
                'createur': safe_get(lambda: self.get_current_creator(), "Erreur récupération créateur"),
                'description': safe_get(lambda: self.get_current_description(), "Erreur récupération description"),
                'hashtags': safe_get(lambda: ','.join(self.get_current_hashtags()), "Erreur récupération hashtags"),
                'likes': safe_get(lambda: self.get_current_likes_number(), "Erreur récupération likes"),
                'commentaires': safe_get(lambda: self.get_current_comments_number(), "Erreur récupération commentaires"),
                'favoris': safe_get(lambda: self.get_current_favorites_number(), "Erreur récupération favoris"),
                'partages': safe_get(lambda: self.get_current_shares_number(), "Erreur récupération partages"),
                'url': safe_get(lambda: self.page.url, "Erreur récupération URL")
            }

            # Ajouter les données à notre liste
            data.append(video_data)

            # Afficher un résumé des données collectées
            print(f"✓ Vidéo #{video_num} - {video_data['createur'] or 'Créateur inconnu'}")
            print(f"   Engagement: {video_data['likes'] or 0} likes, {video_data['commentaires'] or 0} commentaires")

            # Passer à la vidéo suivante (sauf pour la dernière itération)
            if i < video_count - 1:
                try:
                    self.go_next_video()
                    # Attendre un peu pour que la vidéo se charge
                    time.sleep(5)
                except Exception as e:
                    logger.error(f"Erreur lors du passage à la vidéo suivante: {e}")
                    print("⚠️ Impossible de passer à la vidéo suivante, arrêt de la collecte.")
                    break

        # Convertir les données en DataFrame
        df = pd.DataFrame(data)

        # Vérifier si le fichier Excel existe déjà
        file_exists = os.path.isfile(filename)

        if file_exists:
            # Charger les données existantes
            try:
                existing_df = pd.read_excel(filename)
                # Fusionner avec les nouvelles données
                df = pd.concat([existing_df, df], ignore_index=True)
                print(f"Ajout de {len(data)} vidéos aux données existantes dans {filename}")
            except Exception as e:
                logger.error(f"Erreur lors de la lecture du fichier Excel existant: {e}")
                print(f"⚠️ Impossible de lire le fichier existant {filename}, création d'un nouveau fichier.")
        else:
            print(f"Création d'un nouveau fichier Excel: {filename}")

        # Sauvegarder les données dans le fichier Excel
        try:
            df.to_excel(filename, index=False)
            print(f"✅ Données sauvegardées avec succès dans {filename}")
            print(f"   Total: {len(df)} vidéos dans le fichier")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des données dans Excel: {e}")
            print(f"❌ Échec de la sauvegarde des données: {e}")
            # Sauvegarder dans un fichier CSV comme solution de repli
            backup_file = filename.replace('.xlsx', '.csv')
            df.to_csv(backup_file, index=False)
            print(f"⚠️ Données sauvegardées dans un fichier CSV de secours: {backup_file}")

        return df

    # ------------------ INTERACTIONS WITH USERS ----------------

    def go_to_user_profile(self, username: str):
        """
        Aller au profil d'un utilisateur spécifique

        Args:
            username: Nom d'utilisateur TikTok
        """
        self._check_login()
        try:
            user_url = f"https://www.tiktok.com/@{username}"
            self.page.goto(user_url)
            logger.info(f"Navigué vers le profil de l'utilisateur {username}")
        except Exception as e:
            logger.error(f"Erreur lors de la navigation vers le profil de l'utilisateur {username} : {e}")
            self.cleanup_browser()

    def get_number_user_followers(self):
        """
        Obtenir le nombre de followers de l'utilisateur actuel

        Returns:
            int: Nombre de followers
        """
        self._check_login()
        try:
            followers = self.page.query_selector(self.UserProfileXPaths['Followers']).inner_text()
            logger.info(f"Nombre de followers actuel : {followers}")
            return followers
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du nombre de followers : {e}")
            return 0

    def get_number_user_following(self):
        """
        Obtenir le nombre de personnes suivies par l'utilisateur actuel

        Returns:
            int: Nombre de personnes suivies
        """
        self._check_login()
        try:
            following = self.page.query_selector(self.UserProfileXPaths['Following']).inner_text()
            logger.info(f"Nombre de personnes suivies actuel : {following}")
            return following
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du nombre de personnes suivies : {e}")
            return 0

    def get_number_user_likes(self):
        """
        Obtenir le nombre de likes de l'utilisateur actuel

        Returns:
            int: Nombre de likes
        """
        self._check_login()
        try:
            likes = self.page.query_selector(self.UserProfileXPaths['LikesNumber']).inner_text()
            logger.info(f"Nombre de likes actuel : {likes}")
            return likes
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du nombre de likes : {e}")
            return 0

    def get_user_video_url(self, username: str, index: int):
        """
        Obtenir une vidéo spécifique d'un utilisateur TikTok

        Args:
            username: Nom d'utilisateur TikTok
            index: Index de la vidéo à récupérer (0 pour la première vidéo)

        Returns:
            str: URL de la vidéo ou None si la vidéo n'existe pas
        """
        self._check_login()
        try:
            self.page.wait_for_selector(self.UserProfileXPaths['Video'].replace('REPLACE', str(index)), timeout=10000)
            video_url = self.page.query_selector(self.UserProfileXPaths['URLVideo'].replace('REPLACE', str(index))).get_attribute('href')
            logger.info(f"URL de la vidéo {index} de {username} : {video_url}")
            return video_url
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la vidéo {index} de {username} : {e}")
            return None

    def get_all_user_videos_url(self, username: str, limit: int) -> List[str]:
        """
        Obtenir toutes les vidéos d'un utilisateur TikTok

        Args:
            username: Nom d'utilisateur TikTok

        Returns:
            List[str]: Liste des URLs des vidéos de l'utilisateur
        """
        self._check_login()
        list_videos = []
        try:
            self.page.goto(f"https://www.tiktok.com/@{username}")
            index = 0
            while True and index < limit:
                video = self.get_user_video_url(username, index)
                if video:
                    list_videos.append(video)
                    index += 1
                    self.scroll_by_pixels(200, smooth=True)

            return list_videos

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des vidéos de l'utilisateur {username} : {e}")
            return list_videos

    def am_i_following_user(self, username: str) -> bool:
        """
        Vérifier si l'utilisateur actuel suit un utilisateur TikTok

        Args:
            username: Nom d'utilisateur TikTok à vérifier

        Returns:
            bool: True si l'utilisateur suit, False sinon
        """
        self._check_login()
        try:
            self.page.goto(f"https://www.tiktok.com/@{username}")
            self.page.wait_for_selector(self.UserProfileXPaths['LabelFollowingButton'], state='visible', timeout=10000)
            follow_button = self.page.query_selector(self.UserProfileXPaths['LabelFollowingButton'])
            is_following = follow_button.inner_text() in ["Following", "Suivis"]
            logger.info(f"Am I following {username}? {'Yes' if is_following else 'No'}")
            return is_following
        except Exception as e:
            logger.error(f"Erreur lors de la vérification du suivi de l'utilisateur {username} : {e}")
            return False

    def follow_user(self, username: str):
        """
        Suivre un utilisateur TikTok

        Args:
            username: Nom d'utilisateur TikTok à suivre
        """
        self._check_login()
        try:
            self.page.goto(f"https://www.tiktok.com/@{username}")
            self.page.wait_for_selector(self.UserProfileXPaths['Follow'], state='visible', timeout=10000)
            self.page.click(self.UserProfileXPaths['Follow'])
            logger.info(f"Utilisateur {username} suivi avec succès")
        except Exception as e:
            logger.error(f"Erreur lors du suivi de l'utilisateur {username} : {e}")
            self.cleanup_browser()

    def get_video_id(self, video_url: str) -> Optional[str]:
        """
        Extraire l'ID de la vidéo à partir de l'URL

        Args:
            video_url: URL de la vidéo TikTok

        Returns:
            Optional[str]: ID de la vidéo ou None si l'URL est invalide
        """
        try:
            if "/" in video_url:
                return video_url.split("/")[-1].split("?")[0]
            else:
                logger.error("URL de vidéo invalide")
                return None
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction de l'ID de la vidéo : {e}")
            return None

    def get_all_user_videos_ids(self, url_list) -> List[str]:
        """
        Obtenir tous les IDs de vidéos d'un utilisateur TikTok

        Args:
            username: Nom d'utilisateur TikTok
            limit: Nombre maximum de vidéos à récupérer

        Returns:
            List[str]: Liste des IDs des vidéos de l'utilisateur
        """
        if type(url_list) is not list:
            url_list = []

        self._check_login()
        list_videos_ids = []
        for url in url_list:
            try:
                video_id = self.get_video_id(url)
                if video_id:
                    list_videos_ids.append(video_id)
                else:
                    logger.error(f"Impossible d'extraire l'ID de la vidéo pour l'URL : {url}")
            except Exception as e:
                logger.error(f"Erreur lors de l'extraction de l'ID de la vidéo pour l'URL {url} : {e}")
        return list_videos_ids

    def collect_users_data(self, usernames, max_videos_per_user=10, filename='tiktok_user_data.xlsx'):
        """
        Collecte des données sur plusieurs profils utilisateur TikTok

        Args:
            usernames: Liste des noms d'utilisateurs TikTok à analyser
            max_videos_per_user: Nombre maximum de vidéos à récupérer par utilisateur
            filename: Nom du fichier Excel pour sauvegarder les données

        Returns:
            tuple: (users_df, videos_df) les dataframes contenant les données
        """
        self._check_login()

        # Préparer les structures pour stocker les données
        users_data = []
        videos_data = []

        # Fonction helper pour obtenir une donnée avec gestion d'erreur
        def safe_get(getter_func, error_message="Erreur lors de la récupération", default=None):
            try:
                result = getter_func()
                return result
            except Exception as e:
                logger.error(f"{error_message}: {e}")
                return default

        print(f"Début de la collecte de données pour {len(usernames)} utilisateurs")

        # Parcourir les utilisateurs
        for idx, username in enumerate(usernames):
            print(f"\n[{idx + 1}/{len(usernames)}] Collecte des données pour @{username}")

            # Visiter le profil de l'utilisateur
            try:
                self.go_to_user_profile(username)
                time.sleep(5)  # Attendre le chargement du profil
            except Exception as e:
                logger.error(f"Erreur lors de l'accès au profil {username}: {e}")
                print(f"⚠️ Impossible d'accéder au profil de @{username}, passage au suivant.")
                continue

            # Collecter les données de l'utilisateur
            user_data = {
                'date_collecte': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'username': username,
                'url_profil': self.page.url,
                'followers': safe_get(lambda: self.get_number_user_followers(),
                                      f"Erreur récupération followers de {username}", 0),
                'following': safe_get(lambda: self.get_number_user_following(),
                                      f"Erreur récupération following de {username}", 0),
                'likes': safe_get(lambda: self.get_number_user_likes(), f"Erreur récupération likes de {username}", 0),
                'est_suivi': safe_get(lambda: self.am_i_following_user(username),
                                      f"Erreur vérification suivi de {username}", False),
            }

            # Ajouter les données utilisateur à notre liste
            users_data.append(user_data)

            # Afficher un résumé des données utilisateur
            print(
                f"✓ @{username}: {user_data['followers']} followers, {user_data['following']} following, {user_data['likes']} likes")
            print(f"  Statut suivi: {'Suivi' if user_data['est_suivi'] else 'Non suivi'}")

            # Récupérer les URLs des vidéos de l'utilisateur
            print(f"  Récupération des vidéos (max {max_videos_per_user})...")
            video_urls = safe_get(
                lambda: self.get_all_user_videos_url(username, max_videos_per_user),
                f"Erreur récupération vidéos de {username}",
                []
            )

            # Si des URLs ont été trouvées, récupérer les IDs et ajouter aux données
            if video_urls:
                video_ids = safe_get(
                    lambda: self.get_all_user_videos_ids(video_urls),
                    f"Erreur récupération IDs vidéos de {username}",
                    [None] * len(video_urls)
                )

                # Pour chaque vidéo trouvée, ajouter ses données
                for i, (url, video_id) in enumerate(zip(video_urls, video_ids)):
                    video_data = {
                        'date_collecte': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'username': username,
                        'video_index': i + 1,
                        'video_url': url,
                        'video_id': video_id
                    }
                    videos_data.append(video_data)

                print(f"  ✓ {len(video_urls)} vidéos récupérées")
            else:
                print(f"  ⚠️ Aucune vidéo trouvée pour @{username}")

        # Convertir les données en DataFrames
        users_df = pd.DataFrame(users_data)
        videos_df = pd.DataFrame(videos_data)

        # Sauvegarder les données dans Excel (avec gestion des fichiers existants)
        try:
            # Créer un writer Excel
            with pd.ExcelWriter(filename, engine='openpyxl', mode='a' if os.path.exists(filename) else 'w') as writer:
                if os.path.exists(filename):
                    # Charger le fichier existant
                    book = writer.book

                    # Vérifier si les feuilles existent déjà
                    sheet_names = book.sheetnames

                    # Utilisateurs
                    if 'Utilisateurs' in sheet_names:
                        # Charger les données existantes
                        existing_users = pd.read_excel(filename, sheet_name='Utilisateurs')
                        # Fusionner avec les nouvelles données
                        users_df = pd.concat([existing_users, users_df], ignore_index=True)
                        # Supprimer l'ancienne feuille
                        idx = sheet_names.index('Utilisateurs')
                        book.remove(book.worksheets[idx])

                    # Vidéos
                    if 'Videos' in sheet_names:
                        # Charger les données existantes
                        existing_videos = pd.read_excel(filename, sheet_name='Videos')
                        # Fusionner avec les nouvelles données
                        videos_df = pd.concat([existing_videos, videos_df], ignore_index=True)
                        # Supprimer l'ancienne feuille
                        idx = sheet_names.index('Videos')
                        book.remove(book.worksheets[idx])

                # Écrire les DataFrames mis à jour
                users_df.to_excel(writer, sheet_name='Utilisateurs', index=False)
                videos_df.to_excel(writer, sheet_name='Videos', index=False)

            print(f"\n✅ Données sauvegardées avec succès dans {filename}")
            print(f"   - {len(users_df)} utilisateurs (total)")
            print(f"   - {len(videos_df)} vidéos (total)")

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des données dans Excel: {e}")
            print(f"❌ Échec de la sauvegarde des données: {e}")

            # Sauvegarder dans un fichier CSV comme solution de repli
            users_backup = filename.replace('.xlsx', '_users.csv')
            videos_backup = filename.replace('.xlsx', '_videos.csv')
            users_df.to_csv(users_backup, index=False)
            videos_df.to_csv(videos_backup, index=False)
            print(f"⚠️ Données sauvegardées dans des fichiers CSV de secours:")
            print(f"   - {users_backup}")
            print(f"   - {videos_backup}")

        return users_df, videos_df

    # ------------------ UTILS ----------------

    def scroll_by_pixels(self, pixels=500, smooth=True):
        """
        Fait défiler la page d'un nombre spécifique de pixels

        Args:
            pixels: Nombre de pixels à défiler (positif pour descendre, négatif pour monter)
            smooth: Utiliser un défilement fluide (True) ou instantané (False)

        Returns:
            bool: True si l'opération a réussi, False sinon
        """
        self._check_login()

        try:
            if smooth:
                # Méthode 1: Défilement fluide avec JavaScript
                self.page.evaluate(f"""
                    window.scrollBy({{
                        top: {pixels},
                        left: 0,
                        behavior: 'smooth'
                    }});
                """)
                time.sleep(0.5)
            else:
                # Méthode 2: Défilement instantané
                self.page.evaluate(f"window.scrollBy(0, {pixels});")

            return True

        except Exception as e:
            logger.error(f"Erreur lors du défilement : {e}")
            return False

    def get_user_login(self, account_identifier):
        try:
            login_data_file = open(self.Connection_file_name, 'r')
            self.login_data = json.load(login_data_file)['Tiktok'][account_identifier]
            login_data_file.close()
        except:
            print("Identifiants de connexion non trouvés, veuillez les ajouter dans le fichier 'login_data.json' dans le dossier utils.")


def StartTiktokBot(account_identifier):
    import logging

    # Configuration du logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Créer et initialiser le bot
    bot = TikTokBot()

    try:

        login_success = bot.login(account_identifier)

        if login_success:
            return bot
        else:
            print("Échec de la connexion à TikTok. Veuillez vérifier vos identifiants.")
            return None

    except Exception as e:
        print(f"Une erreur s'est produite: {e}")
        bot.cleanup_browser()


"""bot = StartTiktokBot("utilisateurde7@outlook.fr")
time.sleep(5)
bot.like_current_video()"""

#faut rajouter le logout et les méthodes pour uploader des vidéos