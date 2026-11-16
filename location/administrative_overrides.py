"""Verified administrative links absent from the address hierarchy of GAR.

The Saint Petersburg address hierarchy skips administrative districts. Its
municipal formations also represent cities/settlements, but those municipal
roles must not replace the administrative district directory.
Source: https://www.gov.spb.ru/gov/otrasl/trud/socialnye-voprosy/siroti/perechen-vnutrigorodskih-municipalnyh-obrazovanij/
Verified: 2026-11-16. Existing legacy district identities are always retained.
"""

SPB_DISTRICTS = {
    'Пушкинский': [
        '110d6ad9-0b64-47cf-a2ee-7e935228799c',  # Пушкин
        '5c348da7-3a1e-47fe-be8d-52bac0887cd4',  # Павловск
        '06e63688-29c5-45f1-b8c8-40273527a601',  # Шушары
        'dcd167a4-d0e0-44a2-849f-96eb82a57c09',  # Тярлево
        'fd4781dc-f33b-4ccc-bd10-7f20b3385a7f',  # Александровская
    ],
    'Петродворцовый': [
        '3eece910-1326-4602-aa21-e4ee117275ad',  # Стрельна
        '8f238984-812b-4bb1-850b-49749fb5c56d',  # Петергоф
        '3c2827f3-63f3-4692-8c74-c1318ee524fd',  # Ломоносов
    ],
    'Колпинский': [
        '1e11a121-81c4-4b66-b11c-da8f47db2e1d',  # Колпино
        '94ca2daa-6c36-4196-9eed-39f6b9872335',  # Металлострой
        'b069b108-21ab-4171-a36b-ec2c6ef4daff',  # Петро-Славянка
        '1a759f7b-da52-49c5-961a-1e77d759ed5b',  # Понтонный
        '31863f3a-1677-4620-bcbb-c921e8e30edd',  # Саперный
        'c0e2e6ad-9161-4a9b-8cd3-b5194fe53f87',  # Усть-Ижора
    ],
    'Курортный': [
        'ac598324-b704-4957-a66e-e8142677981b',  # Зеленогорск
        'ee5e852c-1a4a-4aee-919a-54473a76fa4d',  # Сестрорецк
        '70b619a5-0aaa-46ae-a56f-b65132fa20c2',  # Белоостров
        '71a7dcf9-91c5-48d6-a862-ea3bf4cd1534',  # Комарово
        '2608a240-daa2-4a9f-91fb-85988d9551c4',  # Молодежное
        'cb77cc8b-1bb2-4c34-a7f7-51a46bc37725',  # Песочный
        '7ab808d0-32bb-4c20-ad1b-c7d38932cfe9',  # Репино
        'c6cbf7ed-f958-439e-b663-b8e869b69e29',  # Серово
        'eaced841-da25-4789-8d40-72c287391848',  # Смолячково
        'ebfecb5b-75ea-470e-9050-cb4eef832a92',  # Солнечное
        '5ed902e2-3e9e-426d-b6d5-367ea4329216',  # Ушково
    ],
    'Выборгский': [
        '769f0eae-05c3-4231-8c3b-a0bcb0ee8eaf',  # Левашово
        '3c370269-440f-4110-b677-96ab4ca31e00',  # Парголово
    ],
    'Приморский': [
        '43fdf07b-c22d-42af-9655-6684ee243c21',  # Лисий Нос
    ],
    'Красносельский': [
        'cced82af-3bdf-4a91-ab68-d654804767c0',  # Красное Село
    ],
    'Кронштадтский': [
        '7b1c7427-41b2-4ffc-bf39-550e8299b5cb',  # Кронштадт
    ],
}
