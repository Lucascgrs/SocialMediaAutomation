import logging
import os
import json
import time
from typing import List, Dict, Optional, Union, Tuple
import requests
import random
from pathlib import Path
import openai
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class AIContentGenerator:
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialiser le générateur de contenu basé sur l'IA

        Args:
            api_key: Clé API OpenAI (si non fournie, cherche dans les variables d'environnement)
        """
        load_dotenv()  # Charger les variables d'environnement depuis un fichier .env

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("Aucune clé API OpenAI trouvée. Certaines fonctionnalités seront limitées.")
        else:
            openai.api_key = self.api_key

        self.output_folder = os.path.join(os.getcwd(), "generated_content")
        os.makedirs(self.output_folder, exist_ok=True)

        # Historique des contenus générés
        self.history_file = os.path.join(self.output_folder, "generation_history.json")
        self.history = self._load_history()

    def generate_trivia_question(self, category: str = None, difficulty: str = "medium") -> Dict:
        """
        Générer une question de culture générale avec choix multiples

        Args:
            category: Catégorie de la question (optionnel)
            difficulty: Niveau de difficulté ('easy', 'medium', 'hard')

        Returns:
            Dict: Question générée avec choix et réponse correcte
        """
        try:
            # Définir des catégories si aucune n'est spécifiée
            categories = [
                "Histoire", "Science", "Géographie", "Art et Littérature",
                "Sport", "Musique", "Cinéma", "Technologie", "Nature",
                "Gastronomie", "Célébrités", "Culture Pop"
            ]

            if not category:
                category = random.choice(categories)

            if self.api_key:
                # Utiliser OpenAI pour générer une question
                prompt = f"""
                Crée une question de culture générale de niveau {difficulty} sur le thème "{category}" avec 4 réponses possibles.
                Assure-toi que la question est factuelle et qu'une seule réponse est correcte.

                Réponds uniquement au format JSON suivant:
                {{
                  "question": "Ta question ici",
                  "options": ["Option A", "Option B", "Option C", "Option D"],
                  "correct_answer": "L'option correcte exactement comme écrite dans les options",
                  "explanation": "Brève explication de pourquoi c'est la bonne réponse"
                }}
                """

                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "system",
                               "content": "Tu es un expert en culture générale qui crée des questions précises et intéressantes."},
                              {"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=300
                )

                content = response['choices'][0]['message']['content']

                # Extraire le JSON de la réponse
                try:
                    # Supprimer les backticks s'il y en a
                    if content.startswith("```json") and content.endswith("```"):
                        content = content[7:-3]
                    elif content.startswith("```") and content.endswith("```"):
                        content = content[3:-3]

                    result = json.loads(content)

                    # Ajouter des métadonnées
                    result["category"] = category
                    result["difficulty"] = difficulty
                    result["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

                    # Enregistrer dans l'historique
                    self._save_to_history("trivia_question", result)

                    return result
                except json.JSONDecodeError as e:
                    logger.error(f"Erreur de décodage JSON: {e}")
                    logger.error(f"Contenu reçu: {content}")
                    return self._generate_fallback_trivia(category, difficulty)

            else:
                # Utiliser l'API gratuite Open Trivia DB comme fallback
                return self._generate_fallback_trivia(category, difficulty)

        except Exception as e:
            logger.error(f"Erreur lors de la génération de la question de culture générale: {e}")
            return self._generate_fallback_trivia(category, difficulty)

    def generate_fun_fact(self, category: str = None) -> Dict:
        """
        Générer un fait intéressant ou insolite

        Args:
            category: Catégorie du fait (optionnel)

        Returns:
            Dict: Fait intéressant généré
        """
        try:
            # Définir des catégories si aucune n'est spécifiée
            categories = [
                "Histoire", "Science", "Espace", "Nature", "Corps humain",
                "Animaux", "Technologie", "Psychologie", "Océans", "Records"
            ]

            if not category:
                category = random.choice(categories)

            if self.api_key:
                # Utiliser OpenAI pour générer un fait intéressant
                prompt = f"""
                Partage un fait insolite, fascinant et véridique sur la catégorie "{category}".
                Le fait doit être surprenant et mémorable, idéal pour une vidéo virale sur les réseaux sociaux.
                Il doit être court (2-3 phrases maximum) et facilement compréhensible.

                Réponds uniquement au format JSON suivant:
                {{
                  "fact": "Le fait insolite ici",
                  "source": "Source de l'information si disponible",
                  "title": "Un titre accrocheur pour ce fait (maximum 7 mots)"
                }}
                """

                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "system",
                               "content": "Tu es un créateur de contenu spécialisé dans les faits surprenants et captivants."},
                              {"role": "user", "content": prompt}],
                    temperature=0.8,
                    max_tokens=200
                )

                content = response['choices'][0]['message']['content']

                # Extraire le JSON de la réponse
                try:
                    # Supprimer les backticks s'il y en a
                    if content.startswith("```json") and content.endswith("```"):
                        content = content[7:-3]
                    elif content.startswith("```") and content.endswith("```"):
                        content = content[3:-3]

                    result = json.loads(content)

                    # Ajouter des métadonnées
                    result["category"] = category
                    result["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

                    # Enregistrer dans l'historique
                    self._save_to_history("fun_fact", result)

                    return result
                except json.JSONDecodeError as e:
                    logger.error(f"Erreur de décodage JSON: {e}")
                    logger.error(f"Contenu reçu: {content}")
                    return self._generate_fallback_fun_fact(category)

            else:
                # Utiliser un fallback pour les faits intéressants
                return self._generate_fallback_fun_fact(category)

        except Exception as e:
            logger.error(f"Erreur lors de la génération du fait intéressant: {e}")
            return self._generate_fallback_fun_fact(category)

    def generate_story(self, theme: str = None, duration: str = "short") -> Dict:
        """
        Générer une histoire courte ou anecdote engageante

        Args:
            theme: Thème de l'histoire (optionnel)
            duration: Longueur de l'histoire ('short', 'medium', 'long')

        Returns:
            Dict: Histoire générée
        """
        try:
            # Définir des thèmes si aucun n'est spécifié
            themes = [
                "Leçon de vie", "Inspiration", "Courage", "Amitié", "Persévérance",
                "Mystère", "Surprise", "Coïncidence incroyable", "Acte de bonté",
                "Découverte", "Transformation"
            ]

            if not theme:
                theme = random.choice(themes)

            # Définir les longueurs de texte selon la durée
            tokens = {"short": 150, "medium": 300, "long": 500}
            max_tokens = tokens.get(duration, 150)

            if self.api_key:
                # Utiliser OpenAI pour générer une histoire
                prompt = f"""
                Crée une histoire courte captivante sur le thème "{theme}". 
                L'histoire doit être engageante et adaptée pour une vidéo de réseau social.

                Pour une histoire de durée "{duration}", garde-la concise et percutante.

                Réponds uniquement au format JSON suivant:
                {{
                  "title": "Titre accrocheur pour l'histoire",
                  "story": "Le texte de l'histoire",
                  "moral": "Une courte morale ou leçon de l'histoire (une phrase)",
                  "hashtags": ["hashtag1", "hashtag2", "hashtag3"]
                }}
                """

                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "system",
                               "content": "Tu es un conteur talentueux qui crée des histoires émotionnelles et mémorables."},
                              {"role": "user", "content": prompt}],
                    temperature=0.9,
                    max_tokens=max_tokens
                )

                content = response['choices'][0]['message']['content']

                # Extraire le JSON de la réponse
                try:
                    # Supprimer les backticks s'il y en a
                    if content.startswith("```json") and content.endswith("```"):
                        content = content[7:-3]
                    elif content.startswith("```") and content.endswith("```"):
                        content = content[3:-3]

                    result = json.loads(content)

                    # Ajouter des métadonnées
                    result["theme"] = theme
                    result["duration"] = duration
                    result["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

                    # Enregistrer dans l'historique
                    self._save_to_history("story", result)

                    return result
                except json.JSONDecodeError as e:
                    logger.error(f"Erreur de décodage JSON: {e}")
                    logger.error(f"Contenu reçu: {content}")
                    return self._generate_fallback_story(theme, duration)

            else:
                # Utiliser un fallback pour les histoires
                return self._generate_fallback_story(theme, duration)

        except Exception as e:
            logger.error(f"Erreur lors de la génération de l'histoire: {e}")
            return self._generate_fallback_story(theme, duration)

    def generate_script(self, topic: str = None, duration: str = "short", style: str = "informative") -> Dict:
        """
        Générer un script pour une vidéo

        Args:
            topic: Sujet du script (optionnel)
            duration: Durée cible ('short': 15-30s, 'medium': 30-60s, 'long': 1-3min)
            style: Style du script ('informative', 'funny', 'dramatic', 'tutorial')

        Returns:
            Dict: Script généré
        """
        try:
            # Définir des sujets si aucun n'est spécifié
            topics = [
                "Astuces quotidiennes", "Faits étonnants", "Comment faire",
                "Mode de vie", "Santé", "Technologie", "Tendances actuelles",
                "Psychologie", "Motivation", "Développement personnel"
            ]

            if not topic:
                topic = random.choice(topics)

            # Définir les longueurs de texte selon la durée
            durations = {"short": "15-30 secondes", "medium": "30-60 secondes", "long": "1-3 minutes"}
            target_duration = durations.get(duration, "15-30 secondes")

            tokens = {"short": 200, "medium": 400, "long": 800}
            max_tokens = tokens.get(duration, 200)

            if self.api_key:
                # Utiliser OpenAI pour générer un script
                prompt = f"""
                Crée un script pour une vidéo TikTok/Instagram sur le sujet "{topic}".

                La vidéo doit durer {target_duration} et le style doit être {style}.

                Réponds uniquement au format JSON suivant:
                {{
                  "title": "Titre accrocheur pour la vidéo",
                  "hook": "Une phrase d'accroche puissante pour démarrer la vidéo",
                  "script": "Le script complet avec indications de transitions/effets entre [crochets]",
                  "call_to_action": "Une invitation à l'action finale pour engager les spectateurs",
                  "hashtags": ["hashtag1", "hashtag2", "hashtag3"]
                }}
                """

                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "system",
                               "content": "Tu es un scénariste expert en création de contenu viral pour les réseaux sociaux."},
                              {"role": "user", "content": prompt}],
                    temperature=0.8,
                    max_tokens=max_tokens
                )

                content = response['choices'][0]['message']['content']

                # Extraire le JSON de la réponse
                try:
                    # Supprimer les backticks s'il y en a
                    if content.startswith("```json") and content.endswith("```"):
                        content = content[7:-3]
                    elif content.startswith("```") and content.endswith("```"):
                        content = content[3:-3]

                    result = json.loads(content)

                    # Ajouter des métadonnées
                    result["topic"] = topic
                    result["duration"] = duration
                    result["style"] = style
                    result["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

                    # Enregistrer dans l'historique
                    self._save_to_history("script", result)

                    return result
                except json.JSONDecodeError as e:
                    logger.error(f"Erreur de décodage JSON: {e}")
                    logger.error(f"Contenu reçu: {content}")
                    return self._generate_fallback_script(topic, duration, style)

            else:
                # Utiliser un fallback pour les scripts
                return self._generate_fallback_script(topic, duration, style)

        except Exception as e:
            logger.error(f"Erreur lors de la génération du script: {e}")
            return self._generate_fallback_script(topic, duration, style)

    def generate_trending_ideas(self, platform: str = "all", count: int = 5) -> List[Dict]:
        """
        Générer des idées de contenu tendance

        Args:
            platform: Plateforme cible ('tiktok', 'instagram', 'all')
            count: Nombre d'idées à générer

        Returns:
            List[Dict]: Liste d'idées de contenu tendance
        """
        try:
            platforms = {
                "tiktok": "TikTok",
                "instagram": "Instagram",
                "all": "TikTok et Instagram"
            }
            target = platforms.get(platform.lower(), "TikTok et Instagram")

            if self.api_key:
                # Utiliser OpenAI pour générer des idées tendance
                prompt = f"""
                Propose {count} idées de contenu viral innovantes et actuelles pour {target}.
                Chaque idée doit être réalisable facilement et avoir un fort potentiel d'engagement.

                Réponds uniquement au format JSON suivant:
                {{
                  "ideas": [
                    {{
                      "title": "Titre de l'idée 1",
                      "description": "Description courte de l'idée",
                      "format": "Format de vidéo (ex: challenge, tutorial, réaction, etc)",
                      "target_audience": "Public cible principal",
                      "viral_potential": "Score de 1 à 10"
                    }},
                    ... (autres idées)
                  ]
                }}
                """

                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "system",
                               "content": "Tu es un expert en marketing de contenu spécialisé dans les tendances virales des réseaux sociaux."},
                              {"role": "user", "content": prompt}],
                    temperature=0.9,
                    max_tokens=800
                )

                content = response['choices'][0]['message']['content']

                # Extraire le JSON de la réponse
                try:
                    # Supprimer les backticks s'il y en a
                    if content.startswith("```json") and content.endswith("```"):
                        content = content[7:-3]
                    elif content.startswith("```") and content.endswith("```"):
                        content = content[3:-3]

                    result = json.loads(content)

                    # Ajouter des métadonnées à chaque idée
                    for idea in result["ideas"]:
                        idea["platform"] = platform
                        idea["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

                    # Enregistrer dans l'historique
                    self._save_to_history("trending_ideas", result)

                    return result["ideas"]
                except json.JSONDecodeError as e:
                    logger.error(f"Erreur de décodage JSON: {e}")
                    logger.error(f"Contenu reçu: {content}")
                    return self._generate_fallback_trending_ideas(platform, count)

            else:
                # Utiliser un fallback pour les idées tendance
                return self._generate_fallback_trending_ideas(platform, count)

        except Exception as e:
            logger.error(f"Erreur lors de la génération des idées tendance: {e}")
            return self._generate_fallback_trending_ideas(platform, count)

    def export_content_to_file(self, content: Dict, content_type: str, file_format: str = "txt") -> str:
        """
        Exporter le contenu généré dans un fichier

        Args:
            content: Contenu généré
            content_type: Type de contenu ('trivia', 'fact', 'story', 'script', 'ideas')
            file_format: Format du fichier ('txt', 'json', 'md')

        Returns:
            str: Chemin du fichier créé
        """
        try:
            # Créer un nom de fichier basé sur le type et l'horodatage
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            folder_path = os.path.join(self.output_folder, content_type)
            os.makedirs(folder_path, exist_ok=True)

            file_path = os.path.join(folder_path, f"{content_type}_{timestamp}.{file_format}")

            # Écrire le contenu dans le fichier selon le format
            if file_format.lower() == "json":
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(content, f, ensure_ascii=False, indent=2)

            elif file_format.lower() == "md":
                with open(file_path, "w", encoding="utf-8") as f:
                    if content_type == "trivia_question":
                        f.write(f"# {content.get('question', 'Question de culture générale')}\n\n")
                        f.write("## Options\n\n")
                        for i, option in enumerate(content.get("options", [])):
                            f.write(f"- {option}\n")
                        f.write(f"\n## Réponse correcte\n\n{content.get('correct_answer', '')}\n\n")
                        f.write(f"## Explication\n\n{content.get('explanation', '')}\n")

                    elif content_type == "fun_fact":
                        f.write(f"# {content.get('title', 'Fait intéressant')}\n\n")
                        f.write(f"{content.get('fact', '')}\n\n")
                        f.write(f"Source: {content.get('source', 'Non spécifiée')}\n")

                    elif content_type == "story":
                        f.write(f"# {content.get('title', 'Histoire')}\n\n")
                        f.write(f"{content.get('story', '')}\n\n")
                        f.write(f"**Morale**: {content.get('moral', '')}\n\n")
                        hashtags = " ".join([f"#{tag}" for tag in content.get("hashtags", [])])
                        f.write(f"{hashtags}\n")

                    elif content_type == "script":
                        f.write(f"# {content.get('title', 'Script vidéo')}\n\n")
                        f.write(f"**Accroche**: {content.get('hook', '')}\n\n")
                        f.write("## Script\n\n")
                        f.write(f"{content.get('script', '')}\n\n")
                        f.write(f"**Call to action**: {content.get('call_to_action', '')}\n\n")
                        hashtags = " ".join([f"#{tag}" for tag in content.get("hashtags", [])])
                        f.write(f"{hashtags}\n")

                    else:
                        f.write(f"# Contenu généré: {content_type}\n\n")
                        f.write(str(content))

            else:  # Format texte par défaut
                with open(file_path, "w", encoding="utf-8") as f:
                    if content_type == "trivia_question":
                        f.write(f"QUESTION: {content.get('question', '')}\n\n")
                        f.write("OPTIONS:\n")
                        for option in content.get("options", []):
                            f.write(f"- {option}\n")
                        f.write(f"\nRÉPONSE CORRECTE: {content.get('correct_answer', '')}\n\n")
                        f.write(f"EXPLICATION: {content.get('explanation', '')}\n")

                    elif content_type == "fun_fact":
                        f.write(f"{content.get('title', '').upper()}\n\n")
                        f.write(f"{content.get('fact', '')}\n\n")
                        f.write(f"Source: {content.get('source', 'Non spécifiée')}\n")

                    elif content_type == "story":
                        f.write(f"{content.get('title', '').upper()}\n\n")
                        f.write(f"{content.get('story', '')}\n\n")
                        f.write(f"Morale: {content.get('moral', '')}\n\n")
                        hashtags = " ".join([f"#{tag}" for tag in content.get("hashtags", [])])
                        f.write(f"{hashtags}\n")

                    elif content_type == "script":
                        f.write(f"{content.get('title', '').upper()}\n\n")
                        f.write(f"ACCROCHE: {content.get('hook', '')}\n\n")
                        f.write(f"SCRIPT:\n{content.get('script', '')}\n\n")
                        f.write(f"CALL TO ACTION: {content.get('call_to_action', '')}\n\n")
                        hashtags = " ".join([f"#{tag}" for tag in content.get("hashtags", [])])
                        f.write(f"{hashtags}\n")

                    else:
                        f.write(str(content))

            logger.info(f"Contenu exporté avec succès dans {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Erreur lors de l'exportation du contenu: {e}")
            return ""

    def _load_history(self) -> List[Dict]:
        """Charger l'historique des générations depuis le fichier"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return []
        return []

    def _save_to_history(self, content_type: str, content: Dict):
        """Sauvegarder le contenu dans l'historique"""
        history_entry = {
            "type": content_type,
            "content": content,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        self.history.append(history_entry)

        # Limiter la taille de l'historique
        if len(self.history) > 100:
            self.history = self.history[-100:]

        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de l'historique: {e}")

    def _generate_fallback_trivia(self, category: str, difficulty: str) -> Dict:
        """Générer une question de culture générale en fallback"""
        # Utiliser l'API Open Trivia DB comme fallback
        try:
            # Mapper les catégories vers celles d'Open Trivia DB
            category_mapping = {
                "Histoire": 23, "Science": 17, "Géographie": 22, "Art": 25,
                "Littérature": 10, "Sport": 21, "Musique": 12, "Cinéma": 11
            }

            # Mapper les difficultés
            difficulty_mapping = {
                "easy": "easy", "medium": "medium", "hard": "hard"
            }

            # Construire l'URL
            cat_id = category_mapping.get(category, "")
            diff = difficulty_mapping.get(difficulty, "medium")
            url = f"https://opentdb.com/api.php?amount=1&type=multiple"

            if cat_id:
                url += f"&category={cat_id}"
            if diff:
                url += f"&difficulty={diff}"

            response = requests.get(url)
            data = response.json()

            if data["response_code"] == 0 and data["results"]:
                question = data["results"][0]
                options = question["incorrect_answers"] + [question["correct_answer"]]
                random.shuffle(options)

                return {
                    "question": question["question"],
                    "options": options,
                    "correct_answer": question["correct_answer"],
                    "explanation": "Aucune explication disponible pour cette question.",
                    "category": question["category"],
                    "difficulty": question["difficulty"],
                    "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
            else:
                # Si l'API échoue, générer une question simple
                return {
                    "question": "Quelle est la capitale de la France?",
                    "options": ["Berlin", "Londres", "Paris", "Madrid"],
                    "correct_answer": "Paris",
                    "explanation": "Paris est la capitale de la France depuis le Xème siècle.",
                    "category": category,
                    "difficulty": difficulty,
                    "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
        except Exception as e:
            logger.error(f"Erreur lors du fallback de question: {e}")
            return {
                "question": "Quelle est la capitale de la France?",
                "options": ["Berlin", "Londres", "Paris", "Madrid"],
                "correct_answer": "Paris",
                "explanation": "Paris est la capitale de la France depuis le Xème siècle.",
                "category": category,
                "difficulty": difficulty,
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }

    def _generate_fallback_fun_fact(self, category: str) -> Dict:
        """Générer un fait intéressant en fallback"""
        facts = [
            {
                "fact": "Les koalas ont des empreintes digitales presque identiques à celles des humains, au point que sur une scène de crime, elles pourraient être confondues.",
                "source": "National Geographic",
                "title": "Koalas: Criminels parfaits",
                "category": "Animaux"
            },
            {
                "fact": "Le miel ne se périme jamais. Des archéologues ont trouvé des pots de miel dans des tombes égyptiennes vieux de plus de 3000 ans, et il était encore parfaitement comestible.",
                "source": "Smithsonian Magazine",
                "title": "Le miel: immortel",
                "category": "Nourriture"
            },
            {
                "fact": "Une journée sur Vénus est plus longue qu'une année sur Vénus. Il faut 243 jours terrestres pour que Vénus fasse une rotation complète sur elle-même, mais seulement 225 jours pour qu'elle fasse le tour du Soleil.",
                "source": "NASA",
                "title": "Vénus, reine de la lenteur",
                "category": "Espace"
            },
            {
                "fact": "Le cerveau humain est tellement actif qu'il pourrait alimenter une ampoule à faible consommation. Il génère environ 23 watts d'énergie lorsqu'il est éveillé.",
                "source": "Scientific American",
                "title": "Cerveau: centrale électrique",
                "category": "Corps humain"
            },
            {
                "fact": "Les océans produisent entre 50% et 80% de l'oxygène de la Terre, principalement grâce au phytoplancton qui y vit.",
                "source": "National Ocean Service",
                "title": "Les vraies usines à oxygène",
                "category": "Nature"
            }
        ]

        # Sélectionner un fait correspondant à la catégorie, ou un au hasard
        matching_facts = [f for f in facts if f["category"].lower() == category.lower()]
        if matching_facts:
            fact = random.choice(matching_facts)
        else:
            fact = random.choice(facts)

        fact["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        fact["category"] = category

        return fact

    def _generate_fallback_story(self, theme: str, duration: str) -> Dict:
        """Générer une histoire en fallback"""
        stories = [
            {
                "title": "La gentillesse inattendue",
                "story": "Un homme pressé bouscula une femme dans la rue. Au lieu de se fâcher, elle lui offrit un sourire et l'aida à ramasser ses affaires tombées. Touché par ce geste, il changea d'attitude et passa la journée à aider les autres. Un acte de gentillesse avait créé une réaction en chaîne de bonté.",
                "moral": "La gentillesse est contagieuse.",
                "hashtags": ["kindness", "humanity", "payitforward"],
                "theme": "Acte de bonté"
            },
            {
                "title": "Le choix du jardinier",
                "story": "Un jardinier passait chaque jour devant une pierre énorme qui l'empêchait d'accéder à une partie de son terrain. Pendant des années, il s'en plaignit. Un jour, plutôt que de continuer à se lamenter, il décida de transformer cette pierre en une fontaine magnifique. Ce qui était un obstacle devint la pièce maîtresse de son jardin.",
                "moral": "Les obstacles peuvent devenir des opportunités.",
                "hashtags": ["mindset", "opportunity", "perspective"],
                "theme": "Transformation"
            },
            {
                "title": "L'écho de nos actions",
                "story": "Une petite fille remarqua un sans-abri assis seul dans un parc. Sans hésiter, elle partagea son sandwich avec lui. Un homme d'affaires observant la scène fut si ému qu'il contacta une association et finança un projet d'aide aux sans-abri. Des années plus tard, la petite fille devenue grande découvrit que le projet avait aidé des centaines de personnes, tout ça grâce à un simple sandwich partagé.",
                "moral": "Aucun acte de bonté n'est jamais trop petit.",
                "hashtags": ["impact", "giving", "community"],
                "theme": "Inspiration"
            }
        ]

        # Sélectionner une histoire correspondant au thème, ou une au hasard
        matching_stories = [s for s in stories if s["theme"].lower() == theme.lower()]
        if matching_stories:
            story = random.choice(matching_stories)
        else:
            story = random.choice(stories)

        story["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        story["theme"] = theme
        story["duration"] = duration

        return story

    def _generate_fallback_script(self, topic: str, duration: str, style: str) -> Dict:
        """Générer un script en fallback"""
        scripts = [
            {
                "title": "3 astuces pour être plus productif",
                "hook": "Tu n'as jamais assez de temps? Ces 3 astuces vont changer ta vie!",
                "script": "Salut à tous! [Transition rapide] Aujourd'hui je partage mes 3 astuces pour booster ta productivité! [Zoom sur visage]\n\n1. La technique Pomodoro: travaille 25 minutes, pause 5 minutes. [Montrer un chronomètre]\n\n2. Prépare ta journée la veille. [Montrer un agenda]\n\n3. Élimine les distractions. [Montrer un téléphone en mode silencieux]\n\n[Transition] J'utilise ces techniques tous les jours et ma productivité a triplé!",
                "call_to_action": "Commente ta technique préférée et abonne-toi pour plus d'astuces!",
                "hashtags": ["productivité", "astuces", "organisation"],
                "topic": "Astuces quotidiennes",
                "style": "informative"
            },
            {
                "title": "Le secret des gens qui ne stressent jamais",
                "hook": "Voici pourquoi certaines personnes restent calmes même dans le chaos total!",
                "script": "[Démarrer avec une scène stressante] Tout le monde panique SAUF cette personne... [Zoom dramatique]\n\nLe secret? La respiration 4-7-8. [Démonstration]\n\nInhale 4 secondes [Compteur à l'écran]\nRetiens 7 secondes [Compteur continue]\nExhale 8 secondes [Compteur termine]\n\n[Transition douce] Fais ça 3 fois et ton corps ne peut physiologiquement PAS rester en état de stress. [Montrer avant/après avec des graphiques]\n\nLes neuroscientifiques ont prouvé que cette technique réduit le cortisol instantanément!",
                "call_to_action": "Essaie maintenant et dis-moi en commentaire si ça a fonctionné pour toi!",
                "hashtags": ["antistress", "santé", "bienêtre", "technique"],
                "topic": "Santé",
                "style": "informative"
            },
            {
                "title": "Ce que ta posture révèle sur ta personnalité",
                "hook": "Ta façon de t'asseoir révèle tout sur toi... même ce que tu caches!",
                "script": "[Montrer différentes postures assises] Savais-tu que ta posture révèle ta vraie personnalité? [Transition]\n\nPosition 1: Jambes croisées [Zoom] = Tu es protecteur et réservé\n\nPosition 2: Pieds à plat [Zoom] = Tu es confiant et direct\n\nPosition 3: Jambe repliée [Zoom] = Tu es créatif mais impatient\n\n[Transition avec effet] La psychologie corporelle peut prédire tes comportements avec 93% de précision! [Statistique à l'écran]\n\n[Effet de surprise] Et toi, quelle est ta position préférée?",
                "call_to_action": "Commente ta position habituelle et je te dirai ce qu'elle révèle spécifiquement sur toi!",
                "hashtags": ["psychologie", "personnalité", "posture", "comportement"],
                "topic": "Psychologie",
                "style": "funny"
            }
        ]

        # Sélectionner un script correspondant au sujet et au style, ou un au hasard
        matching_scripts = [s for s in scripts if
                            s["topic"].lower() == topic.lower() and s["style"].lower() == style.lower()]
        if matching_scripts:
            pass