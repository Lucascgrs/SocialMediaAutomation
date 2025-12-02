import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, Optional, List, Any
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

# Configuration du logger
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class AIContentGenerator:
    """
    Générateur de contenu utilisant l'API OpenAI.
    Gère la création de quiz, faits, histoires et scripts vidéo.
    """

    def __init__(self, api_key: Optional[str] = None):
        load_dotenv()

        # Initialisation du client OpenAI (nouvelle syntaxe v1.x)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("⚠️ Aucune clé API OpenAI trouvée. Le générateur ne fonctionnera pas.")
            self.client = None
        else:
            self.client = OpenAI(api_key=self.api_key)

        # Dossiers de sortie
        self.base_dir = Path(__file__).parent.parent
        self.output_folder = self.base_dir / "generated_content"
        self.output_folder.mkdir(exist_ok=True)

    def _call_openai(self, system_prompt: str, user_prompt: str, model: str = "gpt-3.5-turbo-1106") -> Optional[
        Dict[str, Any]]:
        """
        Méthode utilitaire pour appeler l'API OpenAI avec retour JSON garanti.
        """
        if not self.client:
            logger.error("Client OpenAI non initialisé.")
            return None

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                response_format={"type": "json_object"}  # Force le JSON valide
            )

            content = response.choices[0].message.content
            if not content:
                return None

            return json.loads(content)

        except OpenAIError as e:
            logger.error(f"Erreur API OpenAI : {e}")
            return None
        except json.JSONDecodeError:
            logger.error("L'API a retourné un JSON invalide.")
            return None
        except Exception as e:
            logger.error(f"Erreur inattendue : {e}")
            return None

    def _save_content(self, content_type: str, data: Dict[str, Any]) -> Optional[Path]:
        """Sauvegarde le résultat dans un fichier JSON."""
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            folder = self.output_folder / content_type
            folder.mkdir(exist_ok=True)

            filename = folder / f"{content_type}_{timestamp}.json"

            # Ajout métadonnées
            data["generated_at"] = timestamp

            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"Contenu sauvegardé : {filename}")
            return filename
        except Exception as e:
            logger.error(f"Erreur sauvegarde : {e}")
            return None

    # =========================================================================
    # GÉNÉRATEURS
    # =========================================================================

    def generate_trivia_question(self, category: str = "Culture Générale", difficulty: str = "Moyen") -> Optional[Dict]:
        """
        Génère une question de type Quiz/Trivia.
        """
        system_prompt = "Tu es un générateur de quiz pour application mobile. Tu réponds exclusivement en JSON."
        user_prompt = f"""
        Génère une question sur le thème '{category}' (Difficulté: {difficulty}).
        Format JSON attendu :
        {{
            "question": "Texte de la question",
            "options": ["Choix A", "Choix B", "Choix C", "Choix D"],
            "correct_answer": "Le texte exact de la bonne réponse parmi les options",
            "explanation": "Brève explication ludique"
        }}
        """

        result = self._call_openai(system_prompt, user_prompt)
        if result:
            self._save_content("trivia", result)
        return result

    def generate_fun_fact(self, topic: str = "Insolite") -> Optional[Dict]:
        """
        Génère un fait intéressant type 'Le Saviez-vous ?'.
        """
        system_prompt = "Tu es un expert en faits insolites pour réseaux sociaux. Réponds en JSON."
        user_prompt = f"""
        Donne un fait surprenant et véridique sur : {topic}.
        Format JSON attendu :
        {{
            "title": "Titre accrocheur (max 7 mots)",
            "fact": "Le fait détaillé (max 2 phrases)",
            "source": "Source approximative (ex: NASA, Étude 2023...)"
        }}
        """

        result = self._call_openai(system_prompt, user_prompt)
        if result:
            self._save_content("fun_fact", result)
        return result

    def generate_story(self, theme: str = "Motivation") -> Optional[Dict]:
        """
        Génère une courte histoire ou anecdote.
        """
        system_prompt = "Tu es un conteur pour vidéos courtes (Shorts/Reels). Réponds en JSON."
        user_prompt = f"""
        Écris une histoire courte et captivante sur le thème : {theme}.
        Format JSON attendu :
        {{
            "title": "Titre",
            "story_text": "Texte de l'histoire (environ 150 mots)",
            "moral": "La leçon à retenir en une phrase",
            "suggested_visuals": "Description de l'ambiance visuelle"
        }}
        """

        result = self._call_openai(system_prompt, user_prompt)
        if result:
            self._save_content("story", result)
        return result

    def generate_script(self, topic: str, duration_sec: int = 30) -> Optional[Dict]:
        """
        Génère un script vidéo complet structuré.
        """
        system_prompt = "Tu es un scénariste expert pour TikTok et YouTube Shorts. Réponds en JSON."
        user_prompt = f"""
        Écris un script de vidéo virale sur : {topic}.
        Durée estimée : {duration_sec} secondes.
        Format JSON attendu :
        {{
            "hook": "Phrase d'accroche (0-3s) très percutante",
            "body": "Corps du script découpé en paragraphes",
            "call_to_action": "Phrase de fin pour l'abonnement",
            "visual_cues": ["Liste d'idées visuelles pour le montage"],
            "hashtags": ["tag1", "tag2", "tag3"]
        }}
        """

        result = self._call_openai(system_prompt, user_prompt)
        if result:
            self._save_content("script", result)
        return result


if __name__ == "__main__":
    # Test rapide
    generator = AIContentGenerator()

    if generator.client:
        print("Génération d'un fait insolite...")
        fact = generator.generate_fun_fact("Espace")
        print(json.dumps(fact, indent=2, ensure_ascii=False))

        # print("Génération d'un quiz...")
        # quiz = generator.generate_trivia_question("Jeux Vidéo", "Difficile")
        # print(json.dumps(quiz, indent=2, ensure_ascii=False))