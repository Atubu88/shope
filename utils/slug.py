import re
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories.salon_repository import SalonRepository


def slugify(text: str) -> str:
    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }
    text = text.lower()
    text = ''.join(translit_map.get(ch, ch) for ch in text)
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')


async def generate_unique_slug(session: AsyncSession, text: str) -> str:
    base = slugify(text)
    slug = base
    repo = SalonRepository(session)
    counter = 1
    while await repo.get_salon_by_slug(slug):
        slug = f"{base}-{counter}"
        counter += 1
    return slug
