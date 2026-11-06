import re


LEGAL_NAME_PATTERNS = (
    r'публичное акционерное общество',
    r'акционерное общество',
    r'непубличное акционерное общество',
    r'общество с ограниченной ответственностью',
    r'общество с дополнительной ответственностью',
    r'коммерческий банк',
    r'кредитный банк',
    r'\bпао\b',
    r'\bоао\b',
    r'\bао\b',
    r'\bзао\b',
    r'\bнпао\b',
    r'\bооо\b',
    r'\bодо\b',
    r'\bтоо\b',
    r'\bкб\b',
    r'\bакб\b',
    r'\bбанк\b',
)


def _normalize_name(value):
    """Normalize a bank or program name for exact text comparisons."""
    return re.sub(r'\s+', ' ', value).strip().lower()


def normalize_bank_match_name(value):
    """Normalize a bank name for matching developer offer imports."""
    normalized_value = _normalize_name(value).replace('ё', 'е')
    normalized_value = normalized_value.replace('&quot;', '').replace(
        '&nbsp;',
        ' ',
    )
    normalized_value = re.sub(r'[«»"“”„]', '', normalized_value)
    normalized_value = re.sub(r'\([^)]*\)', ' ', normalized_value)

    for pattern in LEGAL_NAME_PATTERNS:
        if pattern == r'\bбанк\b':
            continue
        normalized_value = re.sub(pattern, ' ', normalized_value)

    normalized_value = re.sub(r'[^a-zа-я0-9]+', '', normalized_value)
    if normalized_value.startswith('банк') and len(normalized_value) > 4:
        normalized_value = normalized_value[4:]

    aliases = {
        'сбер': 'сбербанк',
        'сбербанкроссии': 'сбербанк',
        'тбанк': 'тбанк',
        'тинькофф': 'тбанк',
        'тинькоффбанк': 'тбанк',
        'домрф': 'домрф',
        'россельхоз': 'россельхозбанк',
    }
    return aliases.get(normalized_value, normalized_value)
