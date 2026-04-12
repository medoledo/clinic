from rapidfuzz import process, fuzz
from django.core.cache import cache
from .models import MedicalDictionary, TranscriptionCorrection


def get_dictionary_words():
    """Returns all words from MedicalDictionary, cached for 1 hour."""
    cached = cache.get('medical_dictionary_words')
    if cached is not None:
        return cached
    words = list(MedicalDictionary.objects.values_list('word', flat=True))
    cache.set('medical_dictionary_words', words, timeout=3600)
    return words


def apply_personal_corrections(text, doctor):
    """
    Applies learned personal corrections automatically.
    Goes word by word and replaces known wrong words with their corrections.
    Returns corrected text.
    """
    corrections = TranscriptionCorrection.objects.filter(
        doctor=doctor
    ).values('wrong_word', 'correct_word')

    correction_map = {c['wrong_word']: c['correct_word'] for c in corrections}
    if not correction_map:
        return text

    words = text.split()
    corrected = []
    for word in words:
        # Strip punctuation to get clean word for lookup
        clean_word = word.strip('.,،؛؟!()[]')
        if clean_word in correction_map:
            # Replace only the clean part, preserve surrounding punctuation
            corrected_word = word.replace(clean_word, correction_map[clean_word], 1)
            corrected.append(corrected_word)
        else:
            corrected.append(word)

    return ' '.join(corrected)


def find_suggestions(text, doctor, threshold=70):
    """
    Finds words in the text that are close to (but not exact matches for)
    words in the MedicalDictionary, and have not already been corrected.

    Returns a list of suggestion objects:
    [
        {
            'original': 'ميوكوتيك',
            'suggestion': 'ميوكوتك',
            'score': 88,
            'position': 3  # word index in text
        },
        ...
    ]
    """
    # First apply personal corrections
    corrected_text = apply_personal_corrections(text, doctor)

    dictionary_words = get_dictionary_words()
    if not dictionary_words:
        return corrected_text, []

    # Get personal correction map to skip already-known corrections
    known_corrections = set(
        TranscriptionCorrection.objects.filter(doctor=doctor)
        .values_list('wrong_word', flat=True)
    )

    # Get exact dictionary words set for fast lookup
    dictionary_set = set(w.lower() for w in dictionary_words)

    words = corrected_text.split()
    suggestions = []

    for i, word in enumerate(words):
        clean_word = word.strip('.,،؛?!()[]')
        if not clean_word or len(clean_word) < 3:
            continue

        # Skip if already in dictionary exactly
        if clean_word.lower() in dictionary_set:
            continue

        # Skip if already a known correction
        if clean_word in known_corrections:
            continue

        # Find closest match
        result = process.extractOne(
            clean_word,
            dictionary_words,
            scorer=fuzz.WRatio,
            score_cutoff=threshold
        )

        if result:
            match_word, score, _ = result
            if match_word.lower() != clean_word.lower():
                suggestions.append({
                    'original': clean_word,
                    'suggestion': match_word,
                    'score': score,
                    'position': i
                })

    return corrected_text, suggestions

import re
import json

def regex_parse_transcript(text):
    """
    A robust regex-based fallback for when the AI is down.
    Identifies fields based on the same trigger words used in the prompt.
    """
    fields = {
        "chief_complaint": "",
        "symptoms": "",
        "diagnosis": "",
        "treatment": "",
        "doctor_notes": "",
        "temperature": "",
        "blood_pressure": "",
        "pulse": "",
        "weight": "",
        "next_checkup_date": ""
    }
    
    # Trigger mapping (reduced set for regex efficiency)
    patterns = {
        "chief_complaint": r"(?:شكوى|الشكوى|شكوة)(.*?)(?=أعراض|الأعراض|علامات|تشخيص|علاج|وصفة|ملاحظات|حرارة|ضغط|نبض|وزن|استشارة|$)",
        "symptoms": r"(?:أعراض|الأعراض|علامات)(.*?)(?=شكوى|تشخيص|علاج|وصفة|ملاحظات|حرارة|ضغط|نبض|وزن|استشارة|$)",
        "diagnosis": r"(?:تشخيص|التشخيص|تشخيصي)(.*?)(?=شكوى|أعراض|علاج|وصفة|ملاحظات|حرارة|ضغط|نبض|وزن|استشارة|$)",
        "treatment": r"(?:علاج|العلاج|وصفة|الوصفة|دواء)(.*?)(?=شكوى|أعراض|تشخيص|ملاحظات|حرارة|ضغط|نبض|وزن|استشارة|$)",
        "doctor_notes": r"(?:ملاحظات|ملاحظات خاصة|نوت|نوتس)(.*?)(?=شكوى|أعراض|تشخيص|علاج|حرارة|ضغط|نبض|وزن|استشارة|$)",
        "temperature": r"(?:حرارة|درجة الحرارة)\s*(\d+(?:\.\d+)?)",
        "blood_pressure": r"(?:ضغط|الضغط)\s*(\d+\s*/\s*\d+|\d+\s*على\s*\d+)",
        "pulse": r"(?:نبض|النبض|دقات القلب)\s*(\d+)",
        "weight": r"(?:وزن|الوزن)\s*(\d+)",
        "next_checkup_date": r"(?:استشارة|موعد القادم|استشارة بعد|استشارة في)\s*(\d{4}-\d{2}-\d{2})"
    }
    
    for field, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            val = match.group(1).strip()
            if field == "blood_pressure":
                 val = val.replace("على", "/")
            fields[field] = val
            
    return fields
