"""family.py — RA Family Constitution type group definitions.

Defines the I Family, S Family, and Complex Family type groups
that the RA language uses for family-level validation.

I Family (numeric):
    I — Integer
    F — Float / Decimal
    D — Double
    L — Long

S Family (string/text):
    S       — String
    DC      — Double Character
    TC      — Triple Character
    Line    — Full line input
    Paragraph — Paragraph object
    Text    — Text / buffer content

Complex Family (complex):
    C       — Canonical Complex Family identifier
    Cx      — Complex Number
    Cs      — Complex Standard Equation
    Ca      — Complex Algebra Equation
    Cm      — Complex Magnitude
"""

# ── Family groups ──────────────────────────────────────────────────────────

I_FAMILY_TYPES: frozenset[str] = frozenset({
    "I",   # Integer
    "F",   # Float
    "D",   # Double
    "L",   # Long
})

S_FAMILY_TYPES: frozenset[str] = frozenset({
    "S",        # String
    "DC",       # Double character
    "TC",       # Triple character
    "Line",     # Line input
    "Paragraph", # Paragraph object
    "Text",     # Text content
})

COMPLEX_FAMILY_TYPES: frozenset[str] = frozenset({
    "C",   # Canonical Complex Family identifier
    "Cx",  # Complex Number
    "Cs",  # Complex Standard Equation
    "Ca",  # Complex Algebra Equation
    "Cm",  # Complex Magnitude
})

TF_FAMILY_TYPES: frozenset[str] = frozenset({
    "TF",   # Truth/Falsehood canonical identifier
    "bool", # Boolean datatype
})

YN_FAMILY_TYPES: frozenset[str] = frozenset({
    "YN",  # Yes/No canonical identifier
    "yn",  # Yes/No datatype
})

# ── Family membership helpers ──────────────────────────────────────────────


def type_family(type_name: str | None) -> str | None:
    """Return the family name (``\"I\"``, ``\"S\"``, ``\"C\"``, ``\"TF\"``, ``\"YN\"``, or ``None``) for *type_name*.

    Examples
    --------
    >>> type_family("I")
    'I'
    >>> type_family("F")
    'I'
    >>> type_family("S")
    'S'
    >>> type_family("C")
    'C'
    >>> type_family("Cx")
    'C'
    >>> type_family("Cs")
    'C'
    >>> type_family("TF")
    'TF'
    >>> type_family("YN")
    'YN'
    >>> type_family(None)
    None
    """
    if type_name is None:
        return None
    if type_name in I_FAMILY_TYPES:
        return "I"
    if type_name in S_FAMILY_TYPES:
        return "S"
    if type_name in COMPLEX_FAMILY_TYPES:
        return "C"
    if type_name in TF_FAMILY_TYPES:
        return "TF"
    if type_name in YN_FAMILY_TYPES:
        return "YN"
    return None


def same_family(a: str | None, b: str | None) -> bool:
    """Return ``True`` when *a* and *b* belong to the same type family.

    Two types belong to the same family when:

    * Both are ``None`` (plain re-assignment).
    * Both are the same type (e.g. ``"TF"`` == ``"TF"``).
    * Their ``type_family`` values are identical and not ``None``
      (e.g. ``"I"`` and ``"F"`` both resolve to family ``"I"``).

    Examples
    --------
    >>> same_family("I", "F")
    True
    >>> same_family("I", "D")
    True
    >>> same_family("S", "C")
    False
    >>> same_family("Cx", "Cs")
    True
    >>> same_family("I", "S")
    False
    >>> same_family("I", "TF")
    False
    >>> same_family("TF", "bool")
    True
    >>> same_family("YN", "yn")
    True
    >>> same_family("TF", "YN")
    False
    >>> same_family(None, None)
    True
    >>> same_family("I", None)
    False
    """
    if a is None and b is None:
        return True
    if a is not None and a == b:
        return True
    fa = type_family(a)
    fb = type_family(b)
    return fa is not None and fb is not None and fa == fb
