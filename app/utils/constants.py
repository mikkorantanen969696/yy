"""Shared constants and enums-like values."""
from __future__ import annotations

ROLES = {
    "admin": "admin",
    "manager": "manager",
    "master": "master",
}

ORDER_STATUSES = {
    "created": "created",
    "published": "published",
    "assigned": "assigned",
    "in_progress": "in_progress",
    "completed": "completed",
    "cancelled": "cancelled",
}

CITY_CHOICES = {
    "moscow": "Москва",
    "spb": "Санкт-Петербург",
    "novosibirsk": "Новосибирск",
    "chelyabinsk": "Челябинск",
    "ufa": "Уфа",
    "kazan": "Казань",
    "omsk": "Омск",
    "krasnoyarsk": "Красноярск",
    "nizhny_novgorod": "Нижний Новгород",
    "voronezh": "Воронеж",
}

CLEANING_TYPES = {
    "maintenance": "Поддерживающая",
    "general": "Генеральная",
    "post_renovation": "После ремонта",
    "other": "Другое",
}

EQUIPMENT_OPTIONS = {
    "with_equipment": "С оборудованием",
    "no_equipment": "Без оборудования",
}

CONDITION_OPTIONS = {
    "percent_60": "60% мастеру",
    "percent_70": "70% мастеру",
    "fixed": "Фикс",
    "other": "Иное",
}
