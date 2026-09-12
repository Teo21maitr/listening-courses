Je veux que tu développes une application web locale permettant de transformer un fichier PDF en livre audio grâce à une synthèse vocale entièrement locale et gratuite.

L'objectif de cette V1 est volontairement simple :

- L'utilisateur importe un PDF.
- Il précise si le PDF est en français ou en anglais.
- Le backend extrait le texte du PDF.
- Le texte est nettoyé pour être agréable à écouter.
- Une synthèse vocale locale génère un fichier audio.
- L'utilisateur peut écouter l'audio depuis l'application et le télécharger.
- Aucune traduction n'est nécessaire dans cette V1.
- Je ne veux utiliser aucune API payante ni aucun service cloud pour le traitement du PDF ou la génération de voix.

## Stack technique

Frontend :
- React
- TypeScript
- Vite
- CSS simple et propre
- Tu peux utiliser Tailwind CSS si cela simplifie le développement, mais évite les dépendances inutiles.

Backend :
- Python
- FastAPI
- Uvicorn

PDF :
- PyMuPDF / `fitz`

Text-to-Speech :
- Piper TTS
- Le moteur doit fonctionner localement.
- Prévoir au minimum une voix française et une voix anglaise.
- Les modèles Piper ne doivent pas être hardcodés de manière fragile : créer une configuration permettant d'associer une langue à un modèle.

Structure générale :

React frontend
↓
FastAPI REST API
↓
PyMuPDF
↓
Nettoyage du texte
↓
Découpage en chunks
↓
Piper TTS
↓
Assemblage audio
↓
WAV ou MP3 final

Tout doit fonctionner localement sur macOS, en particulier Apple Silicon / MacBook M4.

---

# Fonctionnalités V1

## 1. Import d'un PDF

Créer une interface avec :

- une zone de drag & drop ;
- un bouton pour sélectionner un fichier ;
- uniquement les fichiers `.pdf` doivent être acceptés ;
- afficher le nom du fichier sélectionné ;
- afficher éventuellement sa taille.

Limiter par exemple la taille des fichiers à 100 MB avec une constante facilement configurable.

---

## 2. Sélection de la langue

Avant de lancer la génération, l'utilisateur doit obligatoirement sélectionner :

- 🇫🇷 Français
- 🇬🇧 Anglais

Cela représente la langue DU DOCUMENT.

Il n'y a aucune traduction.

Exemple :

PDF anglais + langue anglaise
→ voix anglaise

PDF français + langue française
→ voix française

Dans l'API, utiliser par exemple :

```json
{
  "language": "fr"
}
```

ou

```json
{
  "language": "en"
}
```

Ne fais PAS pour l'instant de détection automatique de langue.

---

# 3. Extraction du texte du PDF

Utiliser PyMuPDF.

Créer un service dédié, par exemple :

```text
backend/app/services/pdf_service.py
```

avec quelque chose comme :

```python
extract_text_from_pdf(file_path) -> str
```

L'extraction doit parcourir les pages dans leur ordre.

Garder également la possibilité d'obtenir :

```python
[
    {
        "page": 1,
        "text": "..."
    }
]
```

même si la V1 utilise ensuite principalement le texte concaténé.

Si aucun texte exploitable n'est trouvé, retourner une erreur claire indiquant que le PDF semble probablement être scanné.

Ne mets pas encore d'OCR dans cette V1.

Préparer néanmoins l'architecture pour pouvoir ajouter Tesseract ou un autre OCR plus tard.

---

# 4. Nettoyage du texte

C'est une partie importante du projet.

Un PDF extrait directement contient souvent des éléments inutiles pour une lecture audio.

Créer :

```text
backend/app/services/text_cleaner.py
```

Le nettoyage doit notamment essayer de supprimer ou corriger :

- numéros de pages isolés ;
- espaces multiples ;
- lignes vides excessives ;
- retours à la ligne artificiels au milieu des phrases ;
- mots séparés par une césure en fin de ligne ;
- headers et footers répétés lorsque cela est raisonnablement détectable ;
- URLs très longues ;
- caractères inutiles ou artefacts PDF.

Exemple :

```text
This is an impor-
tant concept.
```

doit devenir :

```text
This is an important concept.
```

Mais ne détruis pas les paragraphes naturels.

Créer des fonctions unitaires plutôt qu'une énorme fonction monolithique.

---

# 5. Découpage du texte

Piper ne doit pas recevoir un document entier en une seule fois.

Créer :

```text
backend/app/services/text_chunker.py
```

Le texte doit être découpé intelligemment.

Objectif :
- conserver les phrases entières autant que possible ;
- éviter de couper au milieu d'une phrase ;
- faire des chunks de taille raisonnable ;
- par exemple autour de 1 000 à 2 000 caractères ;
- rendre la taille configurable.

Priorité pour les coupures :

1. paragraphes ;
2. fins de phrases ;
3. espaces ;
4. découpe brute uniquement en dernier recours.

Fonction :

```python
chunk_text(text: str, max_chars: int) -> list[str]
```

---

# 6. Piper TTS

Créer un service :

```text
backend/app/services/tts_service.py
```

Il doit permettre quelque chose comme :

```python
generate_audio(
    text_chunks: list[str],
    language: str,
    output_path: str
)
```

Configurer les modèles Piper dans un fichier centralisé.

Exemple :

```python
VOICE_MODELS = {
    "fr": {
        "model": "...",
        "config": "..."
    },
    "en": {
        "model": "...",
        "config": "..."
    }
}
```

Ne mets pas de chemins absolus dépendant de mon ordinateur.

Utiliser des chemins relatifs ou des variables d'environnement.

Prévoir par exemple :

```text
backend/models/piper/fr/
backend/models/piper/en/
```

Documenter clairement comment télécharger et installer les modèles.

Ne télécharge pas silencieusement des modèles au lancement du serveur.

Si un modèle manque, retourner un message d'erreur clair.

---

# 7. Génération des morceaux audio

Pour chaque chunk :

```text
chunk_001.wav
chunk_002.wav
chunk_003.wav
...
```

Générer les morceaux dans un dossier temporaire associé au job.

Puis concaténer les morceaux dans le bon ordre.

Utiliser FFmpeg pour l'assemblage et, si pertinent, la conversion finale.

Format final souhaité :

```text
MP3
```

Par exemple :
- bitrate 128 kbps ;
- mono ou stéréo selon ce qui est pertinent pour de la voix ;
- paramètres configurables.

Si produire d'abord un WAV puis convertir vers MP3 est plus fiable, fais-le.

---

# 8. Traitement asynchrone

La génération d'un gros PDF peut prendre du temps.

Je ne veux PAS que la requête HTTP d'upload reste ouverte pendant toute la génération.

Créer un système simple de jobs.

Pour cette V1, inutile d'ajouter Redis/Celery.

Utiliser les capacités de FastAPI ou un mécanisme Python simple pour traiter la tâche en arrière-plan.

Un job doit avoir :

```text
id
status
progress
message
filename
language
created_at
audio_url
error
```

Statuts possibles :

```text
queued
extracting
cleaning
generating_audio
assembling
completed
failed
```

API possible :

```http
POST /api/jobs
```

multipart/form-data :

```text
file
language
```

Réponse :

```json
{
  "id": "uuid",
  "status": "queued"
}
```

Puis :

```http
GET /api/jobs/{id}
```

Exemple :

```json
{
  "id": "...",
  "status": "generating_audio",
  "progress": 62,
  "message": "Generating audio 31/50",
  "audio_url": null
}
```

Une fois terminé :

```json
{
  "status": "completed",
  "progress": 100,
  "audio_url": "/api/jobs/.../audio"
}
```

Puis :

```http
GET /api/jobs/{id}/audio
```

pour récupérer le MP3.

---

# 9. Progression

Je veux voir une vraie progression.

Exemple :

```text
Extracting PDF...
Cleaning text...
Generating audio 12 / 48...
Generating audio 13 / 48...
Assembling audio...
Done.
```

Calcul possible :

- extraction : 0 → 5 %
- nettoyage : 5 → 10 %
- génération des chunks : 10 → 90 %
- assemblage : 90 → 99 %
- terminé : 100 %

Le frontend doit poll :

```http
GET /api/jobs/{id}
```

toutes les 1 ou 2 secondes tant que le job n'est pas terminé.

---

# 10. Frontend

Je veux une interface très simple, moderne et mobile-first.

Page unique.

Exemple visuel :

```text
PDF to Audio

Turn a PDF into an audiobook locally.

┌─────────────────────────────────────┐
│                                     │
│          Drop your PDF here         │
│                                     │
│          or select a file           │
│                                     │
└─────────────────────────────────────┘

document.pdf

Document language

[ 🇫🇷 Français ]  [ 🇬🇧 English ]

[ Generate audiobook ]

Generating audiobook...

████████████████░░░░ 72%

Generating audio 34 / 48


Audio ready

▶ ━━━━━━━━━━━━━━━━━━━━━━━━━

01:32 / 1:47:21

[ Download MP3 ]
```

Je veux quelque chose de sobre.

Pas besoin :
- d'authentification ;
- de comptes ;
- de base de données ;
- de dashboard ;
- de sidebar ;
- de fonctionnalités inutiles.

---

# 11. Lecteur audio

Quand le fichier est prêt, afficher un lecteur HTML5 :

```html
<audio controls />
```

Permettre également :

```text
Download MP3
```

Le nom du fichier généré peut être basé sur le PDF original.

Exemple :

```text
agile_project_management.pdf
```

→

```text
agile_project_management_audio_en.mp3
```

---

# 12. Gestion des erreurs

Prévoir des messages propres pour :

- fichier non PDF ;
- fichier trop gros ;
- PDF vide ;
- PDF protégé / impossible à lire ;
- PDF composé uniquement d'images ;
- langue inconnue ;
- Piper absent ;
- modèle Piper absent ;
- FFmpeg absent ;
- erreur pendant la génération ;
- erreur pendant l'assemblage.

Ne jamais simplement retourner une stack trace au frontend.

Logger néanmoins les détails côté backend.

---

# 13. Sécurité

Même si l'application est locale :

- vérifier l'extension ;
- vérifier le MIME type lorsque possible ;
- ne jamais utiliser directement le nom envoyé par l'utilisateur comme chemin système ;
- utiliser UUID pour les dossiers temporaires ;
- empêcher les path traversal ;
- nettoyer les fichiers temporaires ;
- limiter la taille maximale des uploads.

---

# 14. Architecture du projet

Je veux une structure claire du type :

```text
pdf-to-audio/
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── PdfUploader.tsx
│   │   │   ├── LanguageSelector.tsx
│   │   │   ├── Progress.tsx
│   │   │   └── AudioPlayer.tsx
│   │   ├── api/
│   │   │   └── jobs.ts
│   │   ├── types/
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── ...
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/
│   │   │   └── jobs.py
│   │   ├── models/
│   │   │   └── job.py
│   │   ├── services/
│   │   │   ├── pdf_service.py
│   │   │   ├── text_cleaner.py
│   │   │   ├── text_chunker.py
│   │   │   ├── tts_service.py
│   │   │   └── audio_service.py
│   │   └── jobs/
│   │       └── manager.py
│   ├── models/
│   │   └── piper/
│   ├── tests/
│   ├── requirements.txt
│   └── ...
│
├── .gitignore
├── README.md
└── docker-compose.yml
```

Tu peux adapter légèrement cette architecture si tu as une bonne raison.

---

# 15. Configuration

Utiliser `.env` lorsque nécessaire.

Exemple :

```env
MAX_PDF_SIZE_MB=100
TEXT_CHUNK_MAX_CHARS=1500
OUTPUT_AUDIO_BITRATE=128k
TEMP_DIR=./tmp
```

Créer :

```text
.env.example
```

Ne jamais commit les fichiers `.env`.

---

# 16. Développement local

Je suis sur macOS Apple Silicon.

Je veux pouvoir lancer quelque chose comme :

Backend :

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend :

```bash
cd frontend
npm install
npm run dev
```

Prévoir CORS correctement pour le développement.

Par exemple :

```text
frontend : http://localhost:5173
backend  : http://localhost:8000
```

---

# 17. Docker

Je veux également un `docker-compose.yml`, mais NE commence pas par Docker.

Fais d'abord fonctionner l'application nativement.

Ensuite seulement, ajoute Docker si cela reste simple.

Important : Piper et FFmpeg doivent continuer de fonctionner.

---

# 18. README

Le README est important.

Il doit expliquer :

1. ce que fait l'application ;
2. la stack ;
3. les prérequis ;
4. comment installer FFmpeg sur macOS ;
5. comment installer Piper ;
6. où récupérer les modèles de voix français et anglais ;
7. où mettre les modèles ;
8. comment lancer le backend ;
9. comment lancer le frontend ;
10. comment tester l'application ;
11. les limitations actuelles.

Mentionner notamment :

```text
Current limitations:
- No translation
- No OCR for scanned PDFs
- French and English only
- Local processing only
```

---

# 19. Tests

Ajouter au minimum des tests backend pour :

```text
text_cleaner
text_chunker
PDF extraction
job states
```

Pour les tests Piper, éviter de dépendre systématiquement d'un vrai modèle de plusieurs centaines de Mo.

Créer une abstraction permettant de mocker la génération audio.

---

# 20. Qualité du code

Je veux :

- Python typé autant que raisonnablement possible ;
- TypeScript strict ;
- fonctions courtes ;
- responsabilités séparées ;
- pas de duplication ;
- noms explicites ;
- commentaires uniquement lorsqu'ils apportent quelque chose ;
- pas d'over-engineering.

Ne crée pas de système de plugins, repository pattern, DDD, microservices ou architecture inutile pour cette V1.

---

# 21. Très important : ordre d'implémentation

Ne développe pas tout aveuglément en une fois.

Commence par inspecter le repository actuel.

S'il est vide, initialise correctement le projet.

Ensuite travaille dans cet ordre :

### Phase 1
Créer le backend minimal.

Faire fonctionner :

```text
PDF → extraction du texte
```

Tester.

### Phase 2
Ajouter :

```text
texte → chunks
```

Tester.

### Phase 3
Ajouter Piper :

```text
texte → WAV
```

avec un petit texte de test.

Vérifier réellement que la voix fonctionne.

### Phase 4
Ajouter :

```text
PDF → chunks → plusieurs WAV → MP3 final
```

Tester sur un petit PDF.

### Phase 5
Ajouter le système de jobs et progression.

### Phase 6
Créer le frontend React.

### Phase 7
Connecter frontend et backend.

### Phase 8
Ajouter validation, erreurs et nettoyage des fichiers.

### Phase 9
Ajouter tests, README et éventuellement Docker.

À chaque étape, vérifie que ce qui existe fonctionne avant de continuer.

---

# 22. Ne pas implémenter maintenant

Ne développe surtout pas encore :

- traduction ;
- OCR ;
- authentification ;
- comptes utilisateur ;
- base de données ;
- stockage cloud ;
- historique persistant ;
- partage des fichiers ;
- IA / LLM ;
- résumé automatique ;
- génération de chapitres ;
- application mobile.

Mais construis le code suffisamment proprement pour pouvoir ajouter plus tard :

```text
PDF anglais
↓
extraction
↓
traduction anglaise → française
↓
TTS français
```

sans réécrire toute l'application.

---

# 23. Première tâche

Commence maintenant par :

1. inspecter le repository ;
2. me dire brièvement ce qui existe déjà ;
3. proposer la structure finale du projet ;
4. initialiser les parties nécessaires ;
5. implémenter la Phase 1 ;
6. lancer les tests et/ou effectuer un vrai test d'extraction PDF ;
7. corriger les erreurs éventuelles ;
8. continuer ensuite progressivement vers les phases suivantes.

Ne me donne pas simplement du code à copier.

Tu dois modifier directement le projet, lancer les commandes nécessaires, tester réellement l'application et corriger les problèmes rencontrés.

Quand tu fais un choix technique non évident, explique-le brièvement.

Priorité absolue :

```text
Simplicité
→ fonctionnement réel
→ architecture propre
→ expérience utilisateur
→ fonctionnalités supplémentaires
```