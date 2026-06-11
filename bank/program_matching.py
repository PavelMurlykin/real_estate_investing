import re


def normalize_mortgage_program_match_name(value):
    """Normalize a mortgage program name for duplicate-safe matching."""
    normalized_value = re.sub(r'\s+', ' ', value or '').strip().lower()
    normalized_value = normalized_value.replace('ё', 'е')
    normalized_value = normalized_value.replace('&quot;', '').replace(
        '&nbsp;',
        ' ',
    )

    if re.search(
        r'\b(?:it|ит|айти)\b',
        normalized_value,
        flags=re.IGNORECASE,
    ):
        return 'itипотека'
    if 'семей' in normalized_value:
        return 'семейнаяипотека'
    if 'дальневост' in normalized_value or 'аркти' in normalized_value:
        return 'дальневосточнаяарктическаяипотека'
    if 'сельск' in normalized_value:
        return 'сельскаяипотека'
    if 'военн' in normalized_value:
        return 'военнаяипотека'
    if 'господдерж' in normalized_value:
        return 'господдержкаипотека'
    if 'льгот' in normalized_value:
        return 'льготнаяипотека'

    normalized_value = re.sub(r'[«»"\'„“”‟‹›‚‘’′″＂]', '', normalized_value)
    normalized_value = re.sub(
        r'[\(\)\[\]\{\}<>〈〉《》「」『』【】〔〕]',
        ' ',
        normalized_value,
    )
    normalized_value = re.sub(
        r'\b(?:ипотека|ипотечная|ипотечный|программа|на|для|по)\b',
        ' ',
        normalized_value,
    )
    return re.sub(r'[^a-zа-я0-9]+', '', normalized_value)
