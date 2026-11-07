"""TypeSafe AI (Jev System One) client for semantic audio judgment and movement matching."""
from __future__ import annotations

import json
import logging
from typing import Any

import requests
from core.config import get_secret
from core.logging_setup import log

API_URL = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"


class TypeSafeUnavailableError(RuntimeError):
    """Raised when TypeSafe AI API is not configured or unavailable (ADR 0017 strict fail-fast)."""
    pass


class TypeSafeClient:
    def __init__(self, api_key: str | None = None, timeout: float = 30.0):
        self.api_key = (api_key or get_secret("TYPESAFE_API_KEY") or get_secret("TYPESAFE_KEY") or "").strip()
        self.timeout = timeout

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _require_configured(self) -> None:
        if not self.is_configured():
            raise TypeSafeUnavailableError(
                "TypeSafe AI API key is not configured. Please set TYPESAFE_API_KEY in Settings or .env "
                "(ADR 0017: strict fail-fast policy for background music matching)."
            )

    def system_one(
        self,
        state: dict[str, Any] | str,
        questions: dict[str, Any],
        model: str = DEFAULT_MODEL,
    ) -> dict[str, Any]:
        """Execute structured System One questions against a provided state payload."""
        self._require_configured()

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "state": state,
            "questions": questions,
        }

        try:
            resp = requests.post(API_URL, headers=headers, json=payload, timeout=self.timeout)
        except Exception as e:
            raise TypeSafeUnavailableError(f"Failed to connect to TypeSafe AI service: {e}") from e

        if resp.status_code != 200:
            err_msg = f"TypeSafe AI API error [{resp.status_code}]: {resp.text}"
            log.error(err_msg)
            raise TypeSafeUnavailableError(err_msg)

        data = resp.json()
        return data.get("answers", {})

    def evaluate_track_fitness(
        self,
        audio_profile: dict[str, Any],
        track_meta: dict[str, Any],
    ) -> dict[str, Any]:
        """Grade a single music track's voiceover suitability, cognitive distraction, and movement role."""
        state = {
            "id": track_meta.get("id"),
            "name": track_meta.get("name"),
            "category": track_meta.get("category"),
            "description": track_meta.get("description", ""),
            "mood": track_meta.get("mood", ""),
            "duration_sec": audio_profile.get("duration_sec", 0),
            "rms_db": audio_profile.get("rms_db"),
            "peak_db": audio_profile.get("peak_db"),
            "dynamic_range_db": audio_profile.get("dynamic_range_db"),
            "filename_tags": audio_profile.get("filename_tags", []),
            "has_vocals": audio_profile.get("has_vocals", False),
            "vocal_type": audio_profile.get("vocal_type", "instrumental"),
        }

        questions = {
            "is_distracting": {
                "type": "noul",
                "instructions": (
                    "Does this music track have elements (such as singing, vocal textures, harsh brass drops, "
                    "abrasive solos, or chaotic percussion) that would distract viewers from hearing dense informational speech?"
                ),
            },
            "voiceover_fitness": {
                "type": "score",
                "instructions": (
                    "Grade how suitable this music track is as an ambient background bed under spoken informational narration."
                ),
                "criteria": [
                    "Disruptive: prominent lead vocals, chaotic drums, abrasive solos, or jarring drops.",
                    "Borderline: noticeable background vocals or busy instruments that mildly compete with speech.",
                    "Neutral: standard acoustic carpet or low-key instrumental; non-intrusive.",
                    "Supportive: steady minimalist pulse, soft rhythmic groove, clean synth bed that helps focus.",
                    "Ideal underscore: spacious, transparent, zero vocal clashes, perfect for data-rich explainers.",
                ],
            },
            "movement_role": {
                "type": "choice",
                "instructions": (
                    "Which narrative movement role in an educational documentary is this track best suited for?"
                ),
                "criteria": {
                    "intro_context": "Opening exposition, curiosity, atmosphere, setting the stage.",
                    "deep_dive_tension": "Investigative inquiry, conflict, rising tension, data exploration.",
                    "climax_resolution": "Uplifting resolution, breakthrough, takeaway, inspiring conclusion.",
                    "unfit_for_voiceover": "Only suitable for speech-free stingers, credits, or high-energy montages.",
                },
            },
        }

        answers = self.system_one(state=state, questions=questions)

        distraction_prob = float(answers.get("is_distracting", {}).get("noul", 0.5))
        # Note: TypeSafe score returns a 0.0 - 4.0 scale for a 5-item criteria list.
        # We normalize to 1.0 - 5.0 scale to match ADR 0017 specifications.
        raw_score = float(answers.get("voiceover_fitness", {}).get("score", 2.0))
        normalized_fitness = round(raw_score + 1.0, 2)

        movement_role_choice = answers.get("movement_role", {}).get("choice", "intro_context")

        # ADR 0017 Threshold: voiceover_fitness >= 3.0 and distraction_prob <= 0.40
        is_ready = bool(normalized_fitness >= 3.0 and distraction_prob <= 0.40 and movement_role_choice != "unfit_for_voiceover")

        return {
            "distraction_prob": round(distraction_prob, 3),
            "voiceover_fitness": normalized_fitness,
            "movement_role": movement_role_choice,
            "is_voiceover_ready": is_ready,
            "speech_intrusive": not is_ready,
            "confidence": answers.get("voiceover_fitness", {}).get("confidence", 0.0),
        }

    def rank_candidate_tracks(
        self,
        candidates: list[dict[str, Any]],
        topic: str,
        chapter_synopsis: str,
        movement_name: str,
    ) -> list[dict[str, Any]]:
        """Rank candidate tracks semantically for a specific narrative movement."""
        if not candidates:
            return []
        if len(candidates) == 1:
            return candidates

        self._require_configured()

        state = {
            "video_topic": topic,
            "chapter_synopsis": chapter_synopsis,
            "target_movement": movement_name,
            "candidate_tracks": [
                {
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "mood": c.get("mood"),
                    "category": c.get("category"),
                    "description": c.get("description"),
                    "voiceover_fitness": c.get("voiceover_fitness", 3.5),
                }
                for c in candidates
            ],
        }

        candidate_ids = [c["id"] for c in candidates if "id" in c]
        if not candidate_ids:
            return candidates

        criteria = {
            cid: f"Track '{next((c.get('name') for c in candidates if c.get('id') == cid), cid)}' matches {movement_name} tension"
            for cid in candidate_ids
        }

        questions = {
            "best_track": {
                "type": "choice",
                "instructions": (
                    f"Given the video topic and chapter synopsis, which candidate track best matches the emotional tension "
                    f"and narrative tone required for the '{movement_name}' movement?"
                ),
                "criteria": criteria,
            }
        }

        try:
            answers = self.system_one(state=state, questions=questions)
            best_id = answers.get("best_track", {}).get("choice")
            probs = answers.get("best_track", {}).get("probabilities", {})

            # Attach rank probability and sort candidates descending
            for c in candidates:
                c["rank_prob"] = float(probs.get(c.get("id"), 0.0))
            ranked = sorted(
                candidates,
                key=lambda c: (c.get("rank_prob", 0.0), c.get("voiceover_fitness", 0)),
                reverse=True,
            )
            return ranked
        except Exception as e:
            log.warning("TypeSafe ranking failed (%s); preserving natural candidate order", e)
            raise

    def classify_topic_category(
        self,
        topic: str,
        context_text: str = "",
    ) -> str | None:
        """Classify a video topic and synopsis into the best matching documentary music category."""
        if not self.is_configured():
            return None

        state = {
            "video_topic": topic,
            "context_summary": (context_text or "")[:600],
        }

        questions = {
            "category": {
                "type": "choice",
                "instructions": (
                    "Which documentary music genre best fits the tone, subject matter, and mood of this video topic?"
                ),
                "criteria": {
                    "cinematic_documentary": "Historical chronicle, civic affairs, urban planning, housing, government policy, society, culture, biography.",
                    "dramatic_tension": "High-stakes crisis, controversy, financial scam, investigation, deadlock, conflict, tension.",
                    "tech_futuristic": "Technology, AI, semiconductors, software engineering, digital innovation, cyber, quantum physics.",
                    "mystery_cosmic": "Astronomy, cosmos, deep ocean mysteries, astrophysics, unsolved enigmas.",
                    "uplifting_inspirational": "Human triumph, hope, medical breakthroughs, optimism, inspiring journeys, visionary futures.",
                    "calm_focus": "Tutorials, educational deep work, psychology, philosophy, habits, calm mindfulness.",
                },
            }
        }

        try:
            answers = self.system_one(state=state, questions=questions)
            choice = answers.get("category", {}).get("choice")
            valid_cats = {
                "cinematic_documentary",
                "dramatic_tension",
                "tech_futuristic",
                "mystery_cosmic",
                "uplifting_inspirational",
                "calm_focus",
            }
            if choice in valid_cats:
                return choice
        except Exception as e:
            log.warning("TypeSafe topic categorization failed (%s)", e)

        return None
