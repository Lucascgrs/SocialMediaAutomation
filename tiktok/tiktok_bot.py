import os
import time
import json
import random
import logging
from pathlib import Path
from typing import Optional, List
from playwright.sync_api import sync_playwright, Page, BrowserContext, Playwright

# Configuration du logger
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class TikTokBot:
    """
    Bot pour automatiser les interactions sur TikTok via Playwright.
    Gère le login, la navigation, les likes, commentaires, follows et l'upload.
    """

    def __init__(self):
        # Chemins et Fichiers
        self.base_dir = Path(__file__).parent.parent
        self.user_data_dir = Path.home() / 'tiktok_browser_data'
        self.credentials_path = self.base_dir / 'utils' / 'login_data.json'

        # État interne
        self.playwright: Optional[Playwright] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.logged_in = False
        self.password: Optional[str] = None

        # XPaths (Gardés mais centralisés)
        self.selectors = {
            'cookies_accept': '//button[contains(text(), "Tout refuser") or contains(text(), "Tout accepter")]',
            # Générique
            'login_btn_main': '#top-right-action-bar-login-button',
            'upload_btn_nav': 'a[href*="/upload"]',
            'comment_input': 'div[contenteditable="true"]',
            'post_comment': 'div[data-e2e="comment-post"]',
            'like_btn': 'span[data-e2e="like-icon"]',
            'follow_btn': 'button[data-e2e="follow-button"]',
            'next_video': 'button[data-e2e="arrow-right"]',
            'iframe_upload': 'iframe'
        }

    # =========================================================================
    # SETUP & AUTHENTIFICATION
    # =========================================================================

    def _load_password(self, account_identifier: str) -> bool:
        """Charge le mot de passe depuis le JSON."""
        if not self.credentials_path.exists():
            logger.error(f"Fichier de config introuvable : {self.credentials_path}")
            return False
        try:
            with open(self.credentials_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.password = data.get('Tiktok', {}).get(account_identifier)
            return bool(self.password)
        except Exception as e:
            logger.error(f"Erreur lecture password : {e}")
            return False

    def start_browser(self):
        """Lance le navigateur avec persistance des données (cookies/cache)."""
        try:
            self.user_data_dir.mkdir(exist_ok=True)
            self.playwright = sync_playwright().start()

            # Lancement avec contexte persistant (garde la session active entre les lancements)
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.user_data_dir),
                headless=False,  # Mettre à True pour cacher le navigateur
                channel="chrome",  # Utilise Chrome installé si possible (moins détectable)
                args=['--disable-blink-features=AutomationControlled', '--start-maximized'],
                viewport={"width": 1280, "height": 800}  # Viewport par défaut, sera ignoré si start-maximized
            )

            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()

            # Masquage des indicateurs d'automatisation
            self.page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            logger.info("Navigateur lancé.")
        except Exception as e:
            logger.critical(f"Impossible de lancer le navigateur : {e}")
            self.cleanup()

    def login(self, account_identifier: str) -> bool:
        """
        Tente de se connecter. Si les cookies sont valides, passe directement.
        Sinon, effectue le processus de connexion.
        """
        if not self._load_password(account_identifier):
            return False

        self.start_browser()
        if not self.page: return False

        logger.info("Navigation vers TikTok...")
        self.page.goto('https://www.tiktok.com')
        self.handle_cookie_banner()
        time.sleep(2)

        # Vérification connexion existante
        if self.is_logged_in():
            logger.info("Déjà connecté (Session restaurée).")
            self.logged_in = True
            return True

        logger.info("Connexion nécessaire. Tentative d'automatisation...")

        try:
            # Note: L'automatisation pure du login TikTok est très difficile à cause des Captchas.
            # Le mieux est souvent de laisser l'utilisateur se connecter manuellement la première fois
            # grâce au 'launch_persistent_context', puis de réutiliser la session.

            self.page.click(self.selectors['login_btn_main'])
            time.sleep(2)

            # Séquence login email/user (fragile si TikTok change l'UI)
            # Ici, on clique sur "Utiliser téléphone / email / nom d'utilisateur"
            self.page.click('xpath=//div[contains(text(), "Utiliser téléphone")]/..')
            time.sleep(1)

            # Clic sur l'onglet "Email / Nom d'utilisateur"
            self.page.click('a[href*="/login/phone-or-email/email"]')
            time.sleep(1)

            # Remplissage (Sélecteurs génériques 'name' souvent plus stables)
            self.page.fill('input[name="username"]', account_identifier)
            self.page.fill('input[type="password"]', self.password)

            # Clic Login
            self.page.click('button[type="submit"]')

            # Pause longue pour laisser l'utilisateur résoudre un éventuel CAPTCHA manuellement
            logger.warning("⚠ PAUSE 15s : Résolvez le CAPTCHA si nécessaire ⚠")
            time.sleep(15)

            if self.is_logged_in():
                self.logged_in = True
                return True
            else:
                logger.error("Échec connexion. Le Captcha a peut-être bloqué l'accès.")
                return False

        except Exception as e:
            logger.error(f"Erreur durant le processus de login : {e}")
            return False

    def logout(self):
        """Déconnecte l'utilisateur et ferme le navigateur."""
        if not self.page: return
        try:
            self.page.goto("https://www.tiktok.com/logout")
            time.sleep(3)  # Laisser le temps à la requête de partir
            logger.info("Déconnexion demandée.")
        except Exception as e:
            logger.error(f"Erreur logout : {e}")
        finally:
            self.cleanup()

    def is_logged_in(self) -> bool:
        """Vérifie la présence de l'avatar utilisateur."""
        try:
            # On cherche l'avatar en haut à droite
            return self.page.is_visible('#header-more-menu-icon') or self.page.is_visible('img[class*="Avatar"]')
        except:
            return False

    def cleanup(self):
        """Ferme proprement les ressources."""
        if self.context: self.context.close()
        if self.playwright: self.playwright.stop()
        self.logged_in = False
        logger.info("Navigateur fermé.")

    # =========================================================================
    # NAVIGATION & UTILITAIRES
    # =========================================================================

    def handle_cookie_banner(self):
        """Ferme la bannière cookies si présente."""
        try:
            # Recherche de boutons contenant "Refuser" ou "Accepter" dans une bannière
            # C'est une approche générique
            banner = self.page.get_by_text("Refuser tout", exact=False).first
            if banner.is_visible():
                banner.click()
                logger.info("Cookies gérés.")
        except:
            pass

    def go_home(self):
        self.page.goto('https://www.tiktok.com')

    def go_profile(self, username: str):
        self.page.goto(f'https://www.tiktok.com/@{username}')

    def scroll_smooth(self, pixels=500):
        """Défilement JS pour simuler un humain."""
        self.page.evaluate(f"window.scrollBy({{ top: {pixels}, behavior: 'smooth' }});")
        time.sleep(random.uniform(0.5, 1.5))

    # =========================================================================
    # INTERACTIONS (LIKE, COMMENT, FOLLOW)
    # =========================================================================

    def like_current_video(self):
        """Like la vidéo en cours de visionnage."""
        try:
            # Double clic au centre fonctionne souvent mieux que le bouton spécifique sur TikTok
            # ou cibler le bouton coeur
            btn = self.page.locator(self.selectors['like_btn']).first
            if btn.is_visible():
                btn.click()
                logger.info("Vidéo likée.")
            else:
                # Fallback: double tap
                self.page.mouse.dblclick(600, 400)
                logger.info("Vidéo likée (via double-clic).")
        except Exception as e:
            logger.error(f"Erreur like : {e}")

    def comment_current_video(self, text: str):
        """Poste un commentaire sur la vidéo ouverte."""
        try:
            # Il faut parfois cliquer sur la zone de texte d'abord
            area = self.page.locator(self.selectors['comment_input']).first
            if area.is_visible():
                area.click()
                time.sleep(0.5)
                area.type(text, delay=50)  # Délai pour simuler la frappe
                time.sleep(0.5)
                self.page.keyboard.press("Enter")
                logger.info(f"Commentaire envoyé : {text}")
            else:
                logger.warning("Zone de commentaire introuvable.")
        except Exception as e:
            logger.error(f"Erreur commentaire : {e}")

    def follow_current_user(self):
        """Suit l'utilisateur de la vidéo ou du profil actuel."""
        try:
            btn = self.page.locator(self.selectors['follow_btn']).first
            if btn.is_visible() and "Suivre" in btn.inner_text():
                btn.click()
                logger.info("Utilisateur suivi.")
            else:
                logger.info("Déjà suivi ou bouton introuvable.")
        except Exception as e:
            logger.error(f"Erreur follow : {e}")

    def unfollow_user(self, username: str):
        """Va sur le profil et se désabonne."""
        self.go_profile(username)
        time.sleep(2)
        try:
            # Le bouton change de texte/classe quand on est abonné
            # On cherche un bouton qui contient une icône d'utilisateur + check ou texte "Abonné"
            btn = self.page.locator('button[data-e2e="follow-button"]').first
            # Logique simplifiée: si le bouton a une certaine classe ou texte, on clique
            btn.click()
            # Souvent une popup de confirmation apparait
            time.sleep(1)
            confirm = self.page.get_by_text("Se désabonner").first
            if confirm.is_visible():
                confirm.click()
            logger.info(f"Unfollow {username} effectué.")
        except Exception as e:
            logger.error(f"Erreur unfollow : {e}")

    def next_video(self):
        """Passe à la vidéo suivante (Flèche bas ou bouton)."""
        try:
            self.page.keyboard.press("ArrowDown")
            logger.info("Vidéo suivante.")
            time.sleep(1)
        except Exception as e:
            logger.error(f"Erreur navigation : {e}")

    # =========================================================================
    # UPLOAD (NOUVELLE FONCTIONNALITÉ)
    # =========================================================================

    def upload_video(self, file_path: str, description: str):
        """
        Upload une vidéo sur TikTok.

        Args:
            file_path: Chemin vers le fichier vidéo.
            description: Texte de la légende (caption).
        """
        full_path = Path(file_path).resolve()
        if not full_path.exists():
            logger.error(f"Fichier vidéo introuvable : {full_path}")
            return

        logger.info("Début procédure upload...")
        self.page.goto('https://www.tiktok.com/upload')
        time.sleep(3)  # Chargement page

        try:
            # TikTok utilise une iframe pour l'uploadur
            # La méthode la plus robuste avec Playwright est d'attendre le FileChooser
            # Ou de forcer l'input s'il est présent dans le DOM (souvent caché)

            # On cherche l'iframe principale si elle existe
            # Sinon on interagit avec la page principale

            # Étape 1 : Upload du fichier
            # On utilise set_input_files sur l'input file caché, c'est plus robuste que de cliquer
            file_input = self.page.locator('input[type="file"]')
            if file_input.count() > 0:
                file_input.set_input_files(str(full_path))
            else:
                # Si l'input est dans une iframe
                frame = self.page.frame_locator('iframe').first
                frame.locator('input[type="file"]').set_input_files(str(full_path))

            logger.info("Fichier vidéo envoyé au navigateur. Attente du chargement...")

            # Attendre que l'upload soit traité (apparition de la barre de progression ou changement UI)
            # On attend généralement que le bouton "Publier" devienne cliquable ou que la preview apparaisse
            time.sleep(10)  # Ajuster selon la taille de la vidéo

            # Étape 2 : Description
            # La zone de légende est souvent un div contenteditable
            # On essaie de trouver la zone de caption
            caption_area = self.page.locator('.public-DraftEditor-content')
            if not caption_area.is_visible():
                # Tentative dans l'iframe
                caption_area = self.page.frame_locator('iframe').locator('.public-DraftEditor-content')

            if caption_area.is_visible():
                caption_area.click()
                caption_area.type(description)
                logger.info("Description ajoutée.")
            else:
                logger.warning("Impossible de trouver la zone de description.")

            # Étape 3 : Publication
            post_btn = self.page.locator('button:has-text("Publier")')
            if not post_btn.is_visible():
                post_btn = self.page.frame_locator('iframe').locator('button:has-text("Publier")')

            if post_btn.is_visible():
                # Scroll vers le bouton si nécessaire
                post_btn.scroll_into_view_if_needed()
                post_btn.click()
                logger.info("Bouton Publier cliqué.")

                # Attendre la confirmation
                time.sleep(5)
                logger.info("[✔] Upload terminé (théorique - vérifier manuellement si erreur).")
            else:
                logger.error("Bouton Publier introuvable.")

        except Exception as e:
            logger.error(f"[✘] Erreur critique lors de l'upload : {e}")


def start_tiktok_bot(account_identifier: str) -> Optional[TikTokBot]:
    bot = TikTokBot()
    if bot.login(account_identifier):
        return bot
    else:
        bot.cleanup()
        return None


if __name__ == "__main__":
    # Exemple d'usage
    # bot = start_tiktok_bot("mon_email@gmail.com")
    # if bot:
    #     bot.upload_video("C:/Videos/test.mp4", "Ceci est un test #fyp")
    #     bot.logout()
    pass