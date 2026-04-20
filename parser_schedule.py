from __future__ import annotations

import json
import re
import ssl
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Dict, List

from config import DAYS_OF_WEEK, PAIR_TIMES

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.base import CipherContext
from cryptography.hazmat.backends import default_backend


_BPC_COOKIE_VALUE: str | None = None


def _hex_to_bytes(hex_str: str) -> bytes:
    return bytes.fromhex(hex_str)


def _bytes_to_hex(data: bytes) -> str:
    return data.hex()


def _decrypt_bpc(cipher_hex: str, key_hex: str, iv_hex: str) -> str:
    """
    Расшифровка значения BPC cookie аналогично .NET библиотеке:
    AES-CBC, Padding=None, берём первые 16 байт результата и возвращаем hex.
    """
    cipher_bytes = _hex_to_bytes(cipher_hex)
    key = _hex_to_bytes(key_hex)
    iv = _hex_to_bytes(iv_hex)

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor: CipherContext = cipher.decryptor()
    out = decryptor.update(cipher_bytes) + decryptor.finalize()
    return _bytes_to_hex(out[:16])


_VAR_RE = re.compile(
    r'(?P<name>[\w\d]+)\s*=\s*toNumbers\s*\(\s*"(?P<value>\w*)"\s*\)',
    re.IGNORECASE,
)


def _extract_js_vars(html: str) -> dict[str, str]:
    return {m.group("name"): m.group("value") for m in _VAR_RE.finditer(html)}


def _is_html(content_type: str | None, body: bytes) -> bool:
    if content_type and "text/html" in content_type.lower():
        return True
    # На всякий случай: антибот может возвращать HTML без content-type
    sample = body[:300].lower()
    return b"<html" in sample or b"toNumbers" in sample


def _http_get(url: str) -> bytes:
    """
    GET с попыткой пройти антибот (BPC cookie).
    Хранит BPC cookie в памяти процесса.
    """
    global _BPC_COOKIE_VALUE

    ctx = ssl.create_default_context()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
    }

    def _make_request(cookie_value: str | None) -> tuple[bytes, str | None]:
        req = urllib.request.Request(url, headers=headers, method="GET")
        if cookie_value is not None:
            req.add_header("Cookie", f"BPC={cookie_value}")
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            body = r.read()
            ct = r.headers.get("content-type")
            return body, ct

    # 1) Пробуем с сохранённым cookie или пустым
    try:
        body, ct = _make_request(_BPC_COOKIE_VALUE if _BPC_COOKIE_VALUE is not None else "")
    except urllib.error.HTTPError as e:
        body = e.read() if hasattr(e, "read") else b""
        ct = e.headers.get("content-type") if hasattr(e, "headers") else None

    if not _is_html(ct, body):
        return body

    # 2) Это HTML-антибот. Достаём переменные a,b,c и рассчитываем BPC, затем повторяем.
    html = body.decode("utf-8", errors="ignore")
    vars_ = _extract_js_vars(html)
    if {"a", "b", "c"} <= vars_.keys():
        _BPC_COOKIE_VALUE = _decrypt_bpc(cipher_hex=vars_["c"], key_hex=vars_["a"], iv_hex=vars_["b"])
        body2, ct2 = _make_request(_BPC_COOKIE_VALUE)
        return body2

    # Если антибот изменился — вернём что есть (дальше будет ошибка парсинга)
    return body


def _get_json(url: str) -> Any:
    body = _http_get(url)
    # иногда возвращается пустой массив/объект
    text = body.decode("utf-8", errors="ignore").strip()
    return json.loads(text) if text else None


def _safe_int(x: Any) -> int | None:
    try:
        return int(x)
    except Exception:
        return None


def get_week_start(date: datetime | None = None) -> datetime:
    """
    Вернуть понедельник недели для указанной даты.
    Если дата не указана – взять сегодняшнюю.
    """
    if date is None:
        date = datetime.now()
    # weekday(): понедельник = 0, воскресенье = 6
    return date - timedelta(days=date.weekday())


def get_courses(faculty_id: str) -> List[int]:
    """
    Список курсов для divisionId.
    Endpoint: https://oreluniver.ru/schedule/{divisionId}/kurslist
    """
    division_id = _safe_int(faculty_id)
    if not division_id:
        return [1, 2, 3, 4, 5, 6]

    url = f"https://oreluniver.ru/schedule/{division_id}/kurslist"
    try:
        data = _get_json(url)
        # обычно это список чисел или объектов
        if isinstance(data, list):
            courses: list[int] = []
            for item in data:
                if isinstance(item, int):
                    courses.append(item)
                elif isinstance(item, str) and item.isdigit():
                    courses.append(int(item))
                elif isinstance(item, dict):
                    n = _safe_int(item.get("kurs") or item.get("course") or item.get("number"))
                    if n:
                        courses.append(n)
            return sorted(set(courses)) or [1, 2, 3, 4, 5, 6]
    except Exception:
        pass
    return [1, 2, 3, 4, 5, 6]


def get_groups(faculty_id: str, course: int) -> List[Dict[str, Any]]:
    """
    Список групп для divisionId + course.
    Endpoint: https://oreluniver.ru/schedule/{divisionId}/{course}/grouplist
    """
    division_id = _safe_int(faculty_id)
    if not division_id:
        return []

    url = f"https://oreluniver.ru/schedule/{division_id}/{int(course)}/grouplist"
    try:
        data = _get_json(url)
    except Exception:
        return []

    if not isinstance(data, list):
        return []

    groups: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue

        gid = item.get("idgruop") or item.get("idGroup") or item.get("id") or item.get("idGruop")
        title = item.get("title") or item.get("Title") or item.get("name")
        direction = item.get("Codedirection") or item.get("direction") or item.get("DirectionCode") or ""
        level = item.get("levelEducation") or item.get("EducationLevel") or item.get("level") or ""

        if gid is None or not title:
            continue

        groups.append(
            {
                "id": str(gid),
                "name": str(title),
                "direction": str(direction or ""),
                "level": str(level or ""),
            }
        )

    # Сортируем: сначала по level, потом по имени
    groups.sort(key=lambda g: (g.get("level", ""), g.get("name", "")))
    return groups


def _lesson_to_internal(item: dict[str, Any]) -> dict[str, Any]:
    # Приводим к формату, который использует текущий бот
    pair = _safe_int(item.get("NumberLesson") or item.get("number") or item.get("Number")) or 0
    date_str = str(item.get("DateLesson") or item.get("Date") or "")
    subject = str(item.get("TitleSubject") or item.get("SubjectTitle") or "")
    lesson_type = str(item.get("TypeLesson") or item.get("LessonType") or "")
    classroom = str(item.get("NumberRoom") or item.get("Classroom") or "")
    building = item.get("Korpus") or item.get("BuildingNumber")

    surname = str(item.get("Family") or item.get("EmployeeSurname") or "")
    name = str(item.get("Name") or item.get("EmployeeName") or "")
    patronymic = str(item.get("SecondName") or item.get("EmployeePatronymic") or "")
    teacher = " ".join([x for x in [surname, name, patronymic] if x]).strip()

    room = classroom
    if building not in (None, "", 0):
        room = f"корп. {building}, ауд. {classroom}".strip().strip(",")

    return {
        "pair": pair,
        "date": date_str,
        "subject": subject,
        "type": lesson_type,
        "room": room,
        "teacher": teacher,
        "subgroup": item.get("NumberSubGruop") or item.get("SubgroupNumber"),
        "link": item.get("link") or item.get("Link") or "",
        "pass": item.get("pass") or item.get("LinkPassword") or "",
        "zoom_link": item.get("zoom_link") or item.get("ZoomLink") or "",
        "zoom_password": item.get("zoom_password") or item.get("ZoomLinkPassword") or "",
    }


def _normalize_date_str(date_str: str) -> str:
    """
    API может возвращать дату как 'YYYY-MM-DD' или 'DD.MM.YYYY'.
    Приводим к 'DD.MM.YYYY'.
    """
    s = (date_str or "").strip()
    if not s:
        return ""
    # ISO: 2026-03-16
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        try:
            d = datetime.strptime(s, "%Y-%m-%d")
            return d.strftime("%d.%m.%Y")
        except Exception:
            return s
    return s


def parse_schedule(group_id: str, week_start: datetime) -> Dict[str, Any]:
    """
    Расписание на 6 учебных дней (Пн–Сб) начиная с week_start.

    Используем endpoint printschedule, который возвращает JSON с занятиями.
    """
    gid = _safe_int(group_id)
    if not gid:
        return {"group_id": group_id, "week_start": week_start, "days": {}, "dates": {}, "error": "Некорректный group_id"}

    # API в стороннем клиенте использует dateTime-1day, иначе текущий день может не вернуться
    ms = int((week_start - timedelta(days=1)).timestamp() * 1000)
    url = f"https://oreluniver.ru/schedule//{gid}///{ms}/printschedule"

    try:
        raw = _get_json(url)
    except Exception as e:
        return {"group_id": group_id, "week_start": week_start, "days": {}, "dates": {}, "error": str(e)}

    lessons_raw: list[dict[str, Any]] = []
    if isinstance(raw, list):
        lessons_raw = [x for x in raw if isinstance(x, dict)]
    elif isinstance(raw, dict):
        # формат как у .NET converter: объект, внутри значения-уроки
        lessons_raw = [x for x in raw.values() if isinstance(x, dict)]

    # Сгруппируем по дате (dd.mm.yyyy) и затем сопоставим с днями недели
    by_date: dict[str, list[dict[str, Any]]] = {}
    for item in lessons_raw:
        date_str_raw = str(item.get("DateLesson") or item.get("Date") or "").strip()
        date_key = _normalize_date_str(date_str_raw)
        if not date_key:
            continue
        lesson = _lesson_to_internal(item)
        # тоже нормализуем поле date внутри урока, чтобы формат совпадал везде
        lesson["date"] = date_key
        by_date.setdefault(date_key, []).append(lesson)

    # Сортируем пары внутри дня
    for d in by_date.values():
        d.sort(key=lambda x: (x.get("pair") or 0, str(x.get("subject") or "")))

    days: Dict[str, List[Dict[str, Any]]] = {}
    dates: Dict[str, str] = {}

    for i, day_name in enumerate(DAYS_OF_WEEK):
        day_date = week_start + timedelta(days=i)
        date_key = day_date.strftime("%d.%m.%Y")
        dates[day_name] = date_key
        days[day_name] = by_date.get(date_key, [])

    return {"group_id": str(gid), "week_start": week_start, "days": days, "dates": dates, "error": ""}


def get_schedule_for_date(group_id: str, date: datetime) -> List[Dict[str, Any]]:
    """
    Получить расписание для конкретной даты.
    Использует недельное расписание и выбирает нужный день.
    """
    week_start = get_week_start(date)
    schedule = parse_schedule(group_id, week_start)
    weekday = date.weekday()

    # Для воскресенья просто вернём пустой список
    if weekday == 6:
        return []

    day_name = DAYS_OF_WEEK[weekday]
    return schedule.get("days", {}).get(day_name, [])


def format_lesson(lesson: Dict[str, Any]) -> str:
    """
    Преобразовать одну пару в человекочитаемый текст для Telegram.
    Предполагается, что lesson содержит поля:
    - pair (номер пары)
    - subject
    - room
    - teacher
    - type
    """
    pair_num = lesson.get("pair")
    time_str = PAIR_TIMES.get(pair_num, "")

    subject = lesson.get("subject", "Предмет не указан")
    room = lesson.get("room", "аудитория не указана")
    teacher = lesson.get("teacher", "преподаватель не указан")
    lesson_type = lesson.get("type", "")

    header = f"#{pair_num} ({time_str})" if time_str else f"#{pair_num}"
    type_part = f" ({lesson_type})" if lesson_type else ""

    return (
        f"🕒 <b>{header}</b>\n"
        f"📚 {subject}{type_part}\n"
        f"🏫 {room}\n"
        f"👨‍🏫 {teacher}"
    )


def format_day_schedule(
    lessons: List[Dict[str, Any]],
    day_name: str,
    date_str: str,
) -> str:
    """
    Сформировать текст расписания на день для Telegram.
    Используется и в боте, и в WebApp.
    """
    header = f"📅 <b>{day_name}</b> ({date_str})\n\n"

    if not lessons:
        return header + "❌ Занятий нет."

    parts = [header]
    for lesson in lessons:
        parts.append(format_lesson(lesson))
        parts.append("")  # пустая строка между парами

    return "\n".join(parts).strip()
