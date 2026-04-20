// webapp/static/app.js

// Telegram WebApp
const tg = window.Telegram?.WebApp;
if (tg) {
    tg.ready();
    tg.expand();

    // Применяем тему
    if (tg.colorScheme === 'dark') {
        document.body.classList.add('tg-theme-dark');
    }
}

// Состояние
let currentWeekStart = null;
let currentDayIndex = 0;
let scheduleData = null;

const SHORT_DAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];
const FULL_DAYS = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота'];

// Инициализация
document.addEventListener('DOMContentLoaded', () => {
    loadSchedule();

    document.getElementById('prevWeek').addEventListener('click', () => {
        if (scheduleData) {
            loadSchedule(scheduleData.prev_week);
        }
    });

    document.getElementById('nextWeek').addEventListener('click', () => {
        if (scheduleData) {
            loadSchedule(scheduleData.next_week);
        }
    });

    document.getElementById('todayBtn').addEventListener('click', () => {
        loadSchedule(); // Загрузить текущую неделю
    });

    // Свайпы
    let touchStartX = 0;
    let touchEndX = 0;

    document.addEventListener('touchstart', (e) => {
        touchStartX = e.changedTouches[0].screenX;
    });

    document.addEventListener('touchend', (e) => {
        touchEndX = e.changedTouches[0].screenX;
        handleSwipe();
    });

    function handleSwipe() {
        const diff = touchStartX - touchEndX;
        if (Math.abs(diff) < 50) return;

        if (diff > 0) {
            // Свайп влево — следующий день
            if (currentDayIndex < 5) {
                selectDay(currentDayIndex + 1);
            } else if (scheduleData) {
                loadSchedule(scheduleData.next_week);
            }
        } else {
            // Свайп вправо — предыдущий день
            if (currentDayIndex > 0) {
                selectDay(currentDayIndex - 1);
            } else if (scheduleData) {
                loadSchedule(scheduleData.prev_week);
            }
        }
    }
});

async function loadSchedule(date) {
    showLoading();

    let url = `/api/schedule/${GROUP_ID}`;
    if (date) {
        url += `?date=${date}`;
    }

    try {
        const response = await fetch(url);
        const data = await response.json();

        if (data.error) {
            showError(data.error);
            return;
        }

        scheduleData = data;
        currentWeekStart = data.week_start;

        // Обновляем заголовок
        document.getElementById('weekDates').textContent =
            `${data.week_start_display} — ${data.week_end_display}`;

        // Обновляем табы
        renderDayTabs(data.days);

        // Находим сегодняшний день или первый
        let todayIndex = data.days.findIndex(d => d.is_today);
        if (todayIndex === -1) todayIndex = 0;

        selectDay(todayIndex);
    } catch (err) {
        showError('Не удалось загрузить расписание');
        console.error(err);
    }
}

function renderDayTabs(days) {
    const container = document.getElementById('daysTabs');
    container.innerHTML = '';

    days.forEach((day, index) => {
        const tab = document.createElement('button');
        tab.className = 'day-tab';
        if (day.is_today) tab.classList.add('today');

        // Извлекаем дату (число)
        const dateParts = day.date.split('.');
        const dayNum = dateParts[0] || '';

        tab.innerHTML = `
            <div class="day-name">${SHORT_DAYS[index]}</div>
            <div class="day-date">${dayNum}</div>
        `;

        tab.addEventListener('click', () => selectDay(index));
        container.appendChild(tab);
    });
}

function selectDay(index) {
    currentDayIndex = index;

    // Обновляем активный таб
    const tabs = document.querySelectorAll('.day-tab');
    tabs.forEach((tab, i) => {
        tab.classList.toggle('active', i === index);
    });

    // Скроллим таб в видимость
    if (tabs[index]) {
        tabs[index].scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
    }

    // Отображаем расписание дня
    if (scheduleData && scheduleData.days[index]) {
        renderDaySchedule(scheduleData.days[index]);
    }
}

function renderDaySchedule(day) {
    const container = document.getElementById('scheduleContent');

    if (!day.lessons || day.lessons.length === 0) {
        container.innerHTML = `
            <div class="day-schedule">
                <div class="day-header">${day.name}</div>
                <div class="day-date-header">${day.date}</div>
                <div class="empty-day">
                    <div class="emoji">😴</div>
                    <p>Пар нет!</p>
                    <div class="sub">Отдыхайте и набирайтесь сил</div>
                </div>
            </div>
        `;
        return;
    }

    // Сортируем по номеру пары
    const lessons = [...day.lessons].sort((a, b) => a.pair_num - b.pair_num);

    let html = `
        <div class="day-schedule">
            <div class="day-header">${day.name}</div>
            <div class="day-date-header">${day.date}</div>
    `;

    lessons.forEach(lesson => {
        html += renderLessonCard(lesson);
    });

    html += '</div>';
    container.innerHTML = html;
}

function renderLessonCard(lesson) {
    const typeClass = lesson.type ? `type-${lesson.type}` : '';
    const typeBadgeClass = lesson.type || '';

    const typeLabels = {
        'лек': 'Лекция',
        'пр': 'Практика',
        'лаб': 'Лабораторная',
    };

    let typeLabel = typeLabels[lesson.type] || lesson.type || '';

    let html = `
        <div class="lesson-card ${typeClass}">
            <div class="lesson-header">
                <div class="lesson-pair-num">${lesson.pair_num}</div>
                <div class="lesson-time">${lesson.time || ''}</div>
            </div>
            <div class="lesson-subject">${escapeHtml(lesson.subject)}</div>
    `;

    if (typeLabel) {
        html += `<span class="lesson-type-badge ${typeBadgeClass}">${typeLabel}</span>`;
    }

    if (lesson.subgroup) {
        html += `<div class="lesson-subgroup">👥 ${escapeHtml(lesson.subgroup)}</div>`;
    }

    html += '<div class="lesson-details">';

    if (lesson.teacher) {
        const teacherContent = lesson.teacher_url
            ? `<a href="${escapeHtml(lesson.teacher_url)}" target="_blank">${escapeHtml(lesson.teacher)}</a>`
            : escapeHtml(lesson.teacher);
        html += `
            <div class="lesson-detail">
                <span class="icon">👤</span>
                <span>${teacherContent}</span>
            </div>
        `;
    }

    if (lesson.room) {
        html += `
            <div class="lesson-detail">
                <span class="icon">📍</span>
                <span>${escapeHtml(lesson.room)}</span>
            </div>
        `;
    }

    if (lesson.materials_url) {
        html += `
            <div class="lesson-detail">
                <span class="icon">📎</span>
                <a href="${escapeHtml(lesson.materials_url)}" target="_blank">Методические материалы</a>
            </div>
        `;
    }

    html += '</div></div>';

    return html;
}

function showLoading() {
    document.getElementById('scheduleContent').innerHTML = `
        <div class="loading">
            <div class="spinner"></div>
            <p>Загрузка расписания...</p>
        </div>
    `;
}

function showError(message) {
    document.getElementById('scheduleContent').innerHTML = `
        <div class="error-message">
            <div class="emoji">😕</div>
            <p>${escapeHtml(message)}</p>
            <p style="font-size: 14px; color: var(--text-muted); margin-top: 8px;">
                Попробуйте обновить страницу
            </p>
        </div>
    `;
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}