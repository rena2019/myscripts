#0. ollama run openbmb/minicpm-v4.6
#1. uvx --with ollama python minicpm.py <image>

import argparse
import ollama

parser = argparse.ArgumentParser(description="Bild mit MiniCPM-V beschreiben")
parser.add_argument(
    "bild",
    nargs="?",
    default="mein_bild.jpg",
    help="Pfad zur Bilddatei (Standard: mein_bild.jpg)",
)
args = parser.parse_args()

PROMPT = "Beschreibe, was auf diesem Bild zu sehen ist, auf Deutsch."

try:
    response = ollama.chat(
        model="openbmb/minicpm-v4.6",
        messages=[{
            "role": "user",
            "content": PROMPT,
            "images": [args.bild],
        }],
    )
    print(response.message.content)

except Exception as e:
    print(f"Fehler bei der Verarbeitung: {e}")
