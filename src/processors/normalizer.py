"""Data normalization utilities."""

import re
import unicodedata
from typing import Optional


def normalize_text(text: str) -> str:
    """Normalize text for comparison.

    - Lowercase
    - Remove accents
    - Normalize whitespace
    """
    # Lowercase
    text = text.lower()

    # Remove accents
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def extract_numbers(text: str) -> list[float]:
    """Extract all numbers from text."""
    # Handle Argentine number format (1.234.567,89)
    numbers = []

    # Find patterns that look like numbers
    patterns = re.findall(r"[\d.,]+", text)

    for p in patterns:
        # Skip if too short or no digits
        if not any(c.isdigit() for c in p):
            continue

        # Determine format
        if "," in p and "." in p:
            # Full format: 1.234.567,89
            clean = p.replace(".", "").replace(",", ".")
        elif "," in p:
            # Could be decimal: 123,45 or thousand: 1,234
            parts = p.split(",")
            if len(parts[-1]) == 2:
                # Likely decimal
                clean = p.replace(",", ".")
            else:
                # Likely thousand separator
                clean = p.replace(",", "")
        else:
            # Only dots or plain number
            clean = p.replace(".", "")

        try:
            numbers.append(float(clean))
        except ValueError:
            pass

    return numbers


def clean_title(title: str) -> str:
    """Clean and normalize auction title."""
    # Remove common prefixes
    prefixes = [
        r"^lote\s*\d+[:\-\s]*",
        r"^exp\.\s*\d+[:\-\s]*",
        r"^expediente\s*\d+[:\-\s]*",
        r"^\d+[:\-\)\]\s]+",
    ]

    clean = title
    for prefix in prefixes:
        clean = re.sub(prefix, "", clean, flags=re.IGNORECASE)

    # Normalize whitespace
    clean = re.sub(r"\s+", " ", clean).strip()

    return clean


def parse_location(text: str) -> dict:
    """Extract location from text."""
    location = {"province": "", "city": ""}

    provinces = {
        "buenos aires": "Buenos Aires",
        "caba": "CABA",
        "capital federal": "CABA",
        "córdoba": "Córdoba",
        "cordoba": "Córdoba",
        "santa fe": "Santa Fe",
        "mendoza": "Mendoza",
        "tucumán": "Tucumán",
        "tucuman": "Tucumán",
        "entre ríos": "Entre Ríos",
        "entre rios": "Entre Ríos",
        "salta": "Salta",
        "misiones": "Misiones",
        "chaco": "Chaco",
        "corrientes": "Corrientes",
        "san juan": "San Juan",
        "jujuy": "Jujuy",
        "río negro": "Río Negro",
        "rio negro": "Río Negro",
        "neuquén": "Neuquén",
        "neuquen": "Neuquén",
        "formosa": "Formosa",
        "chubut": "Chubut",
        "san luis": "San Luis",
        "catamarca": "Catamarca",
        "la rioja": "La Rioja",
        "la pampa": "La Pampa",
        "santa cruz": "Santa Cruz",
        "tierra del fuego": "Tierra del Fuego",
    }

    text_lower = normalize_text(text)

    for key, value in provinces.items():
        if key in text_lower:
            location["province"] = value
            break

    return location
