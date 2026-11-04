"""Calculs sur les cotes décimales. Arithmétique pure : aucune prédiction sportive ici.

Conventions : cote décimale > 1 (mise incluse), probabilités dans [0, 1].
"""

from collections.abc import Sequence


def implied_probability(price: float) -> float:
    """Probabilité implicite brute (marge du bookmaker incluse)."""
    if price <= 1:
        raise ValueError("Une cote décimale doit être strictement supérieure à 1.")
    return 1.0 / price


def overround(prices: Sequence[float]) -> float:
    """Somme des probabilités implicites d'un marché COMPLET et exclusif (1.0 = sans marge)."""
    if len(prices) < 2:
        raise ValueError("Un marché complet comporte au moins deux issues.")
    return sum(implied_probability(p) for p in prices)


def margin(prices: Sequence[float]) -> float:
    """Marge du bookmaker = surrondation - 1 (ex. 0.05 = 5 %)."""
    return overround(prices) - 1.0


def remove_margin(prices: Sequence[float]) -> list[float]:
    """Probabilités « justes » par normalisation proportionnelle.

    Limite connue : cette méthode répartit la marge au prorata des probabilités, ce qui
    sous-estime légèrement les outsiders (biais favori/outsider). D'autres méthodes
    (puissance, Shin) pourront être ajoutées ; la normalisation reste la référence simple.
    """
    total = overround(prices)
    return [implied_probability(p) / total for p in prices]


def expected_value(probability: float, price: float) -> float:
    """Valeur espérée par unité misée : p * cote - 1 (> 0 = valeur théorique positive)."""
    if not 0.0 <= probability <= 1.0:
        raise ValueError("La probabilité doit être comprise entre 0 et 1.")
    if price <= 1:
        raise ValueError("Une cote décimale doit être strictement supérieure à 1.")
    return probability * price - 1.0


def edge(probability: float, price: float) -> float:
    """Écart entre la probabilité estimée et la probabilité implicite brute."""
    return probability - implied_probability(price)
