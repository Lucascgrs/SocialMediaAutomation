from instagrapi import Client
import time
import random
import json
from pathlib import Path
from typing import Optional, Dict, Any, List


class InstagramBot:
    """
    Classe gérant les interactions avec l'API Instagram via instagrapi.
    Permet le login, la récupération d'infos, l'envoi de messages et l'upload de médias.
    """

    def __init__(self):
        self.client = Client()
        # Utilisation de pathlib pour gérer les chemins de manière robuste et cross-platform
        # On remonte d'un niveau (..) puis on va dans 'utils'
        self.base_dir = Path(__file__).parent.parent
        self.credentials_path = self.base_dir / 'utils' / 'login_data.json'
        self.password: Optional[str] = None

    # =========================================================================
    # AUTHENTIFICATION
    # =========================================================================

    def _load_password(self, account_identifier: str) -> bool:
        """
        Charge le mot de passe depuis le fichier JSON de configuration.

        Args:
            account_identifier: Le nom d'utilisateur ou l'identifiant du compte dans le JSON.

        Returns:
            bool: True si le mot de passe est chargé, False sinon.
        """
        if not self.credentials_path.exists():
            print(f"[!] Le fichier de configuration n'existe pas : {self.credentials_path}")
            return False

        try:
            with open(self.credentials_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                # On suppose que la structure est {'Instagram': {'username': 'password'}}
                self.password = data.get('Instagram', {}).get(account_identifier)

            if not self.password:
                print(f"[!] Mot de passe introuvable pour '{account_identifier}' dans le fichier JSON.")
                return False
            return True

        except json.JSONDecodeError:
            print(f"[!] Erreur de décodage du fichier JSON : {self.credentials_path}")
            return False
        except Exception as e:
            print(f"[✘] Erreur lors de la lecture des identifiants : {e}")
            return False

    def login(self, username: str):
        """
        Connecte le client Instagram.

        Args:
            username: Le nom d'utilisateur Instagram.
        """
        try:
            if self._load_password(username):
                self.client.login(username, self.password)
                print(f"[✔] Connexion réussie pour : {username}")
            else:
                print("[✘] Échec de la connexion : Mot de passe manquant.")
        except Exception as e:
            print(f"[✘] Erreur critique lors de la connexion : {e}")

    # =========================================================================
    # UTILISATEUR (INFO & FOLLOW)
    # =========================================================================

    def get_user_info(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les informations complètes d'un utilisateur.
        """
        try:
            user_id = self.client.user_id_from_username(username)
            info = self.client.user_info(user_id)
            # model_dump() est spécifique aux versions récentes de Pydantic utilisées par instagrapi
            return info.model_dump()
        except Exception as e:
            print(f"[✘] Impossible de récupérer les infos pour {username} : {e}")
            return None

    def get_user_followers(self, username: str, amount: int = 10) -> Dict[str, Any]:
        """Récupère la liste des abonnés d'un utilisateur."""
        try:
            user_id = self.client.user_id_from_username(username)
            return self.client.user_followers(user_id, amount)
        except Exception as e:
            print(f"[✘] Erreur récupération followers : {e}")
            return {}

    def get_user_following(self, username: str, amount: int = 10) -> Dict[str, Any]:
        """Récupère la liste des abonnements d'un utilisateur."""
        try:
            user_id = self.client.user_id_from_username(username)
            return self.client.user_following(user_id, amount)
        except Exception as e:
            print(f"[✘] Erreur récupération following : {e}")
            return {}

    def follow_user(self, username: str):
        """S'abonne à un utilisateur."""
        try:
            user_id = self.client.user_id_from_username(username)
            self.client.user_follow(user_id)
            print(f"[✔] Suivi de {username}")
        except Exception as e:
            print(f"[✘] Erreur follow : {e}")

    def unfollow_user(self, username: str):
        """Se désabonne d'un utilisateur."""
        try:
            user_id = self.client.user_id_from_username(username)
            self.client.user_unfollow(user_id)
            print(f"[✔] Unfollow de {username}")
        except Exception as e:
            print(f"[✘] Erreur unfollow : {e}")

    # =========================================================================
    # MESSAGERIE (DM)
    # =========================================================================

    def send_dm(self, username: str, message: str):
        """
        Envoie un message privé (DM) à un utilisateur.
        """
        try:
            user_id = self.client.user_id_from_username(username)
            self.client.direct_send(message, [user_id])
            print(f"[✔] Message envoyé à {username} (ID: {user_id})")
        except Exception as e:
            print(f"[✘] Erreur envoi message à {username} : {e}")

    # =========================================================================
    # GESTION DES MÉDIAS (UPLOAD & INTERACTION)
    # =========================================================================

    def upload_photo(self, path: str, caption: str = ""):
        """Upload une photo sur le feed."""
        try:
            self.client.photo_upload(path, caption)
            print("[✔] Photo envoyée avec succès")
        except Exception as e:
            print(f"[✘] Erreur upload photo : {e}")

    def upload_video(self, path: str, caption: str = ""):
        """
        Upload une vidéo sur le feed. Tente d'utiliser une miniature si disponible,
        sinon bascule sur la méthode par défaut ou Reels en cas d'erreur.

        Args:
            path: Chemin absolu ou relatif vers le fichier vidéo.
            caption: Légende de la publication.
        """
        video_path = Path(path)
        # Convention: ma_video.mp4 -> ma_video.mp4.jpg
        thumbnail_path = video_path.with_name(f"{video_path.name}.jpg")

        try:
            if thumbnail_path.exists():
                print(f"[i] Miniature trouvée : {thumbnail_path}")
                self.client.video_upload(path, caption, thumbnail=str(thumbnail_path))
            else:
                print(f"[i] Pas de miniature personnalisée trouvée, utilisation par défaut.")
                self.client.video_upload(path, caption)

            print("[✔] Vidéo envoyée")

        except ValueError as ve:
            # Gestion spécifique pour l'erreur 'scans_profile' connue dans instagrapi
            if "scans_profile" in str(ve):
                print("[!] Erreur API Instagram (scans_profile manquant détecté).")
                print("[i] Tentative d'upload via la méthode Reels (clip_upload)...")
                try:
                    self.client.clip_upload(path, caption)
                    print("[✔] Vidéo envoyée comme Reels (Alternative)")
                except Exception as e2:
                    print(f"[✘] L'alternative Reels a aussi échoué : {e2}")
            else:
                print(f"[✘] Erreur ValueError lors de l'upload vidéo : {ve}")
        except Exception as e:
            print(f"[✘] Erreur générale upload vidéo : {e}")

    def upload_story(self, path: str):
        """Upload une photo ou vidéo en Story."""
        try:
            # Note: photo_upload_to_story gère souvent aussi les vidéos courtes selon la version
            # Si besoin de vidéo spécifique: client.video_upload_to_story(path)
            self.client.photo_upload_to_story(path)
            print("[✔] Story envoyée")
        except Exception as e:
            print(f"[✘] Erreur upload story : {e}")

    def like_media(self, media_id: str):
        """Like un média via son ID."""
        try:
            self.client.media_like(media_id)
            print(f"[✔] Like ajouté sur {media_id}")
        except Exception as e:
            print(f"[✘] Erreur like : {e}")

    def comment_media(self, media_id: str, comment: str):
        """Poste un commentaire sur un média."""
        try:
            self.client.media_comment(media_id, comment)
            print(f"[✔] Commentaire posté sur {media_id}")
        except Exception as e:
            print(f"[✘] Erreur commentaire : {e}")

    # =========================================================================
    # UTILITAIRES
    # =========================================================================

    def sleep_random(self, min_sec: int = 2, max_sec: int = 5):
        """Pause l'exécution pendant un temps aléatoire pour imiter un humain."""
        t = random.randint(min_sec, max_sec)
        print(f"[⏳] Pause {t} secondes...")
        time.sleep(t)


# =========================================================================
# FONCTION PRINCIPALE
# =========================================================================

def start_instagram_bot(account_identifier: str) -> InstagramBot:
    """Initialise le bot et lance la connexion."""
    bot = InstagramBot()
    bot.login(account_identifier)
    return bot


if __name__ == "__main__":
    # Bloc de test pour le développement
    # Ne s'exécute que si le fichier est lancé directement
    pass
    # Exemple d'utilisation :
    # bot = start_instagram_bot("mon_compte_instagram")
    # info = bot.get_user_info("instagram")
    # print(info)