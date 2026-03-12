import re


def normalize_phone_number(phone_number):
    raw_phone = (phone_number or '').strip()
    if not raw_phone:
        return ''

    has_plus_prefix = raw_phone.startswith('+')
    digits = re.sub(r'\D', '', raw_phone)
    if not digits:
        return ''

    if has_plus_prefix:
        return f'+{digits}'
    return digits
