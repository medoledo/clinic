from rapidfuzz import process, fuzz
from .models import MedicalDictionary, TranscriptionCorrection


def get_dictionary_words():
    """Returns all words from MedicalDictionary as a list."""
    return list(MedicalDictionary.objects.values_list('word', flat=True))


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

    words = text.split()
    corrected = []
    for word in words:
        clean_word = word.strip('.,،؛؟!()[]')
        if clean_word in correction_map:
            corrected.append(word.replace(clean_word, correction_map[clean_word]))
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
        clean_word = word.strip('.,،؛؟!()[]')
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