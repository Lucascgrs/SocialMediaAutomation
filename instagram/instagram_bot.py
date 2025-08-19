from instagrapi import Client
import time
import random
import os
import json

class InstagramBot:
    def __init__(self):
        self.client = Client()
        self.utils_directory = os.getcwd() + '\\..\\utils'
        self.Connection_file_name = os.path.join(self.utils_directory, 'login_data.json')
        self.login_data = {}

    def login(self, account_identifier):
        try:
            self.get_user_login(account_identifier)
            self.client.login(account_identifier, self.login_data)
            print("[✔] Connexion réussie")
        except Exception as e:
            print(f"[✘] Erreur connexion : {e}")

    # --------- UTILISATEUR ---------
    def get_user_info(self, username):
        """Récupère les infos d'un utilisateur (contourne le bug update_headers)"""
        try:
            user_id = self.client.user_id_from_username(username)
            info = self.client.user_info(user_id)
            return info.model_dump()
        except Exception as e:
            print(f"[✘] Impossible de récupérer les infos pour {username} : {e}")
            return None

    def get_user_followers(self, username, amount=10):
        try:
            user_id = self.client.user_id_from_username(username)
            return self.client.user_followers(user_id, amount)
        except Exception as e:
            print(f"[✘] Erreur récupération followers : {e}")
            return []

    def get_user_following(self, username, amount=10):
        try:
            user_id = self.client.user_id_from_username(username)
            return self.client.user_following(user_id, amount)
        except Exception as e:
            print(f"[✘] Erreur récupération following : {e}")
            return []

    # --------- MESSAGES ---------
    def send_dm(self, username, message):
        try:

            user_id = self.client.user_id_from_username(username)

            self.client.direct_send(message, [user_id])
            print(f"[✔] Message envoyé à {user_id}")
        except Exception as e:
            print(f"[✘] Erreur envoi message : {e}")

    # --------- MÉDIA ---------
    def upload_photo(self, path, caption=""):
        try:
            self.client.photo_upload(path, caption)
            print("[✔] Photo envoyée")
        except Exception as e:
            print(f"[✘] Erreur upload photo : {e}")

    def upload_video(self, path, caption=""):
        """
        Upload vidéo avec gestion des erreurs améliorée

        Args:
            path: Chemin vers le fichier vidéo
            caption: Légende de la vidéo
        """
        try:
            # Option 1: Utiliser l'upload avec thumbnail spécifique
            import os
            from pathlib import Path

            video_path = Path(path)
            thumbnail_path = f"{path}.jpg"  # Le chemin vers la miniature est déjà généré

            # Vérifier si la miniature existe, sinon créer une
            if not os.path.exists(thumbnail_path):
                print(f"Thumbnail non trouvée, utilisant une miniature par défaut")
                # Utiliser la méthode intégrée qui essaie de créer une thumbnail
                self.client.video_upload(path, caption)
            else:
                # Utiliser la miniature existante
                print(f"Utilisation de la thumbnail existante : {thumbnail_path}")
                self.client.video_upload(
                    path,
                    caption,
                    thumbnail=thumbnail_path
                )
            print("[✔] Vidéo envoyée")

        except ValueError as ve:
            # Gérer spécifiquement l'erreur de validation Pydantic
            if "scans_profile" in str(ve):
                print("[!] Erreur API Instagram (scans_profile manquant)")
                print("[i] Essai avec la méthode alternative...")
                try:
                    # Option 2: Alternative - poster comme reels
                    self.client.clip_upload(path, caption)
                    print("[✔] Vidéo envoyée comme Reels")
                    return
                except Exception as e2:
                    print(f"[✘] L'alternative a aussi échoué : {e2}")
            print(f"[✘] Erreur upload vidéo : {ve}")
        except Exception as e:
            print(f"[✘] Erreur upload vidéo : {e}")

    def like_media(self, media_id):
        try:
            self.client.media_like(media_id)
            print(f"[✔] Like sur {media_id}")
        except Exception as e:
            print(f"[✘] Erreur like : {e}")

    def comment_media(self, media_id, comment):
        try:
            self.client.media_comment(media_id, comment)
            print(f"[✔] Commentaire posté sur {media_id}")
        except Exception as e:
            print(f"[✘] Erreur commentaire : {e}")

    # --------- SUIVI ---------
    def follow_user(self, username):
        try:
            user_id = self.client.user_id_from_username(username)
            self.client.user_follow(user_id)
            print(f"[✔] Suivi de {username}")
        except Exception as e:
            print(f"[✘] Erreur follow : {e}")

    def unfollow_user(self, username):
        try:
            user_id = self.client.user_id_from_username(username)
            self.client.user_unfollow(user_id)
            print(f"[✔] Unfollow de {username}")
        except Exception as e:
            print(f"[✘] Erreur unfollow : {e}")

    # --------- STORIES ---------
    def upload_story(self, path):
        try:
            self.client.photo_upload_to_story(path)
            print("[✔] Story envoyée")
        except Exception as e:
            print(f"[✘] Erreur story : {e}")

    # --------- UTILITAIRES ---------
    def sleep_random(self, min_sec=2, max_sec=5):
        t = random.randint(min_sec, max_sec)
        print(f"[⏳] Pause {t} secondes...")
        time.sleep(t)

    def get_user_login(self, account_identifier):
        try:
            login_data_file = open(self.Connection_file_name, 'r')
            self.login_data = json.load(login_data_file)['Instagram'][account_identifier]
            login_data_file.close()
        except:
            print("Identifiants de connexion non trouvés, veuillez les ajouter dans le fichier 'login_data.json' dans le dossier utils.")


def StartInstagramBot(account_identifier):
    bot = InstagramBot()
    bot.login(account_identifier)
    return bot


"""bot = StartInstagramBot("elodie__.bqt")

user_info = bot.get_user_info("instagram")
if user_info:
    print(f"Nom complet : {user_info.get('full_name')}")
    print(f"Bio : {user_info.get('biography')}")

# 7. Test DM (⚠ à remplacer par un vrai username)
print("\n=== Message privé ===")
bot.send_dm("lucas_cgrs", "📩 Test DM via instagrapi")"""