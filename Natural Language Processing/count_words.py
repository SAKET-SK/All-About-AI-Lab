"""Count words."""
import re

def count_words(text):
    """Count how many times each unique word occurs in text."""
    counts = dict()

    # Convert to lowercase
    text = text.lower()

    # Split text into tokens (words), leaving out punctuation
    words = re.split(r'[^a-z0-9]+', text)

    # Aggregate word counts using a dictionary
    for word in words:
        if word:  # skip empty strings
            counts[word] = counts.get(word, 0) + 1

    return counts
