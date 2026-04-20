# -*- coding: utf-8 -*-
import asyncio, logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from config import BOT_TOKEN, WEBAPP_URL, FACULTIES, FACULTY_FULL_NAMES, DAYS_OF_WEEK
from database import init_db, get_user, save_user, delete_user
from parser_schedule import parse_schedule, get_courses, get_groups, get_schedule_for_date, format_day_schedule, get_week_start

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()

class Setup(StatesGroup):
    faculty = State()
    course = State()
    group = State()

def main_kb(uid):
    u = get_user(uid)
    gid = str(u.get("group_id","")) if u else ""
    ok = bool(gid) and gid.isdigit()
    b = []
    if u and ok:
        b.append([KeyboardButton(text="\U0001f4c5 \u0421\u0435\u0433\u043e\u0434\u043d\u044f"), KeyboardButton(text="\U0001f4c5 \u0417\u0430\u0432\u0442\u0440\u0430")])
        b.append([KeyboardButton(text="\U0001f4cb \u041d\u0430 \u043d\u0435\u0434\u0435\u043b\u044e")])
        b.append([KeyboardButton(text="\U0001f310 \u0420\u0430\u0441\u043f\u0438\u0441\u0430\u043d\u0438\u0435", web_app=WebAppInfo(url=f"{WEBAPP_URL}/schedule/{gid}"))])
        b.append([KeyboardButton(text="\u2699\ufe0f \u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438"), KeyboardButton(text="\u2139\ufe0f \u041f\u0440\u043e\u0444\u0438\u043b\u044c")])
    else:
        b.append([KeyboardButton(text="\U0001f527 \u041d\u0430\u0441\u0442\u0440\u043e\u0438\u0442\u044c")])
    return ReplyKeyboardMarkup(keyboard=b, resize_keyboard=True)

def fac_kb(page=0):
    items = list(FACULTIES.items()); ps = 8
    tp = (len(items)+ps-1)//ps; s = page*ps; e = min(s+ps, len(items))
    b = []
    for fid,fn in items[s:e]:
        full = FACULTY_FULL_NAMES.get(fid,fn)
        b.append([InlineKeyboardButton(text=f"{fn} \u2014 {full[:40]}", callback_data=f"fac:{fid}")])
    nav = []
    if page > 0: nav.append(InlineKeyboardButton(text="\u25c0\ufe0f", callback_data=f"fp:{page-1}"))
    if page < tp-1: nav.append(InlineKeyboardButton(text="\u25b6\ufe0f", callback_data=f"fp:{page+1}"))
    if nav: b.append(nav)
    b.append([InlineKeyboardButton(text="\u274c", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=b)

def crs_kb(fid):
    cs = get_courses(fid) or [1,2,3,4]
    b, r = [], []
    for c in cs:
        r.append(InlineKeyboardButton(text=str(c), callback_data=f"crs:{c}"))
        if len(r)>=3: b.append(r); r=[]
    if r: b.append(r)
    b.append([InlineKeyboardButton(text="\u25c0\ufe0f", callback_data="back_fac")])
    b.append([InlineKeyboardButton(text="\u274c", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=b)

def grp_kb(groups, page=0):
    ps = 10; tp = max(1,(len(groups)+ps-1)//ps); s = page*ps; e = min(s+ps,len(groups))
    b, cl = [], ""
    for g in groups[s:e]:
        lv = g.get("level","")
        if lv and lv != cl: cl=lv; b.append([InlineKeyboardButton(text=f"\U0001f4ce {lv}", callback_data="noop")])
        d = g.get("direction",""); lb = g["name"]
        if d: lb += f" ({d})"
        b.append([InlineKeyboardButton(text=lb, callback_data=f"grp:{g['id']}:{g['name']}:{d}")])
    nav = []
    if page>0: nav.append(InlineKeyboardButton(text="\u25c0\ufe0f", callback_data=f"gp:{page-1}"))
    if page<tp-1: nav.append(InlineKeyboardButton(text="\u25b6\ufe0f", callback_data=f"gp:{page+1}"))
    if nav: b.append(nav)
    b.append([InlineKeyboardButton(text="\u25c0\ufe0f \u041a\u0443\u0440\u0441", callback_data="back_crs")])
    b.append([InlineKeyboardButton(text="\u274c", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=b)

@router.message(Command("start"))
async def cmd_start(msg: types.Message):
    u = get_user(msg.from_user.id)
    gid = str(u.get("group_id","")) if u else ""
    if u and gid.isdigit():
        await msg.answer(f"\U0001f44b \u041f\u0440\u0438\u0432\u0435\u0442!\n\U0001f3eb {u.get('faculty_name','')}\n\U0001f465 {u.get('group_name','')}", reply_markup=main_kb(msg.from_user.id))
    else:
        await msg.answer("\U0001f44b \u041f\u0440\u0438\u0432\u0435\u0442! \u041d\u0430\u0436\u043c\u0438 \u043a\u043d\u043e\u043f\u043a\u0443 \u043d\u0438\u0436\u0435 \u0438\u043b\u0438 /setup", reply_markup=main_kb(msg.from_user.id))

@router.message(Command("setup"))
@router.message(F.text.contains("\u041d\u0430\u0441\u0442\u0440\u043e\u0438\u0442\u044c"))
@router.message(F.text.contains("\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438"))
async def cmd_setup(msg: types.Message, state: FSMContext):
    await state.set_state(Setup.faculty)
    await msg.answer("\U0001f3eb <b>\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0438\u043d\u0441\u0442\u0438\u0442\u0443\u0442:</b>", reply_markup=fac_kb(0), parse_mode=ParseMode.HTML)

@router.callback_query(F.data=="noop")
async def noop(cb: types.CallbackQuery): await cb.answer()

@router.callback_query(F.data.startswith("fp:"))
async def fac_page(cb: types.CallbackQuery):
    await cb.message.edit_reply_markup(reply_markup=fac_kb(int(cb.data.split(":")[1]))); await cb.answer()

@router.callback_query(F.data.startswith("fac:"), Setup.faculty)
async def fac_chosen(cb: types.CallbackQuery, state: FSMContext):
    fid = cb.data.split(":")[1]
    fn = FACULTY_FULL_NAMES.get(fid, FACULTIES.get(fid,""))
    await state.update_data(faculty_id=fid, faculty_name=fn)
    await state.set_state(Setup.course)
    await cb.message.edit_text(f"\U0001f3eb <b>{fn}</b>\n\n\U0001f4da \u041a\u0443\u0440\u0441:", reply_markup=crs_kb(fid), parse_mode=ParseMode.HTML)
    await cb.answer()

@router.callback_query(F.data=="back_fac")
async def back_fac(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(Setup.faculty)
    await cb.message.edit_text("\U0001f3eb <b>\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0438\u043d\u0441\u0442\u0438\u0442\u0443\u0442:</b>", reply_markup=fac_kb(0), parse_mode=ParseMode.HTML)
    await cb.answer()

@router.callback_query(F.data.startswith("crs:"), Setup.course)
async def crs_chosen(cb: types.CallbackQuery, state: FSMContext):
    c = int(cb.data.split(":")[1]); d = await state.get_data()
    await state.update_data(course=c)
    await cb.message.edit_text("\u23f3 \u0417\u0430\u0433\u0440\u0443\u0436\u0430\u044e...", parse_mode=ParseMode.HTML)
    groups = get_groups(d["faculty_id"], c)
    if not groups:
        await cb.message.edit_text("\u274c \u041d\u0435\u0442 \u0433\u0440\u0443\u043f\u043f", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="\u25c0\ufe0f", callback_data="back_crs")]]), parse_mode=ParseMode.HTML)
        await cb.answer(); return
    await state.update_data(groups=groups); await state.set_state(Setup.group)
    await cb.message.edit_text(f"\U0001f3eb <b>{d['faculty_name']}</b>\n\U0001f4da \u041a\u0443\u0440\u0441: {c}\n\n\U0001f465 \u0413\u0440\u0443\u043f\u043f\u0430:", reply_markup=grp_kb(groups,0), parse_mode=ParseMode.HTML)
    await cb.answer()

@router.callback_query(F.data=="back_crs")
async def back_crs(cb: types.CallbackQuery, state: FSMContext):
    d = await state.get_data(); await state.set_state(Setup.course)
    await cb.message.edit_text(f"\U0001f3eb <b>{d.get('faculty_name','')}</b>\n\n\U0001f4da \u041a\u0443\u0440\u0441:", reply_markup=crs_kb(d.get("faculty_id","")), parse_mode=ParseMode.HTML)
    await cb.answer()

@router.callback_query(F.data.startswith("gp:"), Setup.group)
async def grp_page(cb: types.CallbackQuery, state: FSMContext):
    d = await state.get_data()
    await cb.message.edit_reply_markup(reply_markup=grp_kb(d.get("groups",[]), int(cb.data.split(":")[1]))); await cb.answer()

@router.callback_query(F.data.startswith("grp:"), Setup.group)
async def grp_chosen(cb: types.CallbackQuery, state: FSMContext):
    p = cb.data.split(":",3); gid=p[1]; gn=p[2] if len(p)>2 else ""; dr=p[3] if len(p)>3 else ""
    d = await state.get_data()
    save_user(cb.from_user.id, faculty_id=d["faculty_id"], faculty_name=d["faculty_name"], course=d["course"], group_id=gid, group_name=gn, direction=dr, setup_step=None)
    await state.clear()
    await cb.message.edit_text(f"\u2705 <b>\u0413\u043e\u0442\u043e\u0432\u043e!</b>\n\U0001f3eb {d['faculty_name']}\n\U0001f4da \u041a\u0443\u0440\u0441: {d['course']}\n\U0001f465 {gn}\n\U0001f4cb {dr}", parse_mode=ParseMode.HTML)
    await cb.message.answer("\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435:", reply_markup=main_kb(cb.from_user.id))
    await cb.answer("\u2705")

@router.callback_query(F.data=="cancel")
async def cancel(cb: types.CallbackQuery, state: FSMContext):
    await state.clear(); await cb.message.edit_text("\u274c \u041e\u0442\u043c\u0435\u043d\u0435\u043d\u043e.")
    await cb.message.answer("\u041c\u0435\u043d\u044e:", reply_markup=main_kb(cb.from_user.id)); await cb.answer()

@router.message(F.text.contains("\u0421\u0435\u0433\u043e\u0434\u043d\u044f"))
async def today(msg: types.Message):
    u = get_user(msg.from_user.id)
    if not u or not u.get("group_id"): await msg.answer("\u26a0\ufe0f /setup", reply_markup=main_kb(msg.from_user.id)); return
    await _show_day(msg, u, datetime.now())

@router.message(F.text.contains("\u0417\u0430\u0432\u0442\u0440\u0430"))
async def tomorrow(msg: types.Message):
    u = get_user(msg.from_user.id)
    if not u or not u.get("group_id"): await msg.answer("\u26a0\ufe0f /setup", reply_markup=main_kb(msg.from_user.id)); return
    await _show_day(msg, u, datetime.now()+timedelta(days=1))

async def _show_day(msg, u, date):
    w = await msg.answer("\u23f3 \u0417\u0430\u0433\u0440\u0443\u0436\u0430\u044e...")
    wd = date.weekday()
    if wd == 6:
        await w.edit_text(f"\U0001f4c5 <b>\u0412\u043e\u0441\u043a\u0440\u0435\u0441\u0435\u043d\u044c\u0435</b> ({date.strftime('%d.%m.%Y')})\n\n\U0001f634 \u0412\u044b\u0445\u043e\u0434\u043d\u043e\u0439!", parse_mode=ParseMode.HTML); return
    ls = get_schedule_for_date(u["group_id"], date)
    dn = DAYS_OF_WEEK[wd] if wd<6 else "\u0412\u043e\u0441\u043a\u0440\u0435\u0441\u0435\u043d\u044c\u0435"
    await w.edit_text(f"\U0001f465 <b>{u['group_name']}</b>\n\n" + format_day_schedule(ls, dn, date.strftime("%d.%m.%Y")), parse_mode=ParseMode.HTML, disable_web_page_preview=True)

@router.message(F.text.contains("\u043d\u0435\u0434\u0435\u043b"))
async def week(msg: types.Message):
    u = get_user(msg.from_user.id)
    if not u or not u.get("group_id"): await msg.answer("\u26a0\ufe0f /setup", reply_markup=main_kb(msg.from_user.id)); return
    w = await msg.answer("\u23f3 \u0417\u0430\u0433\u0440\u0443\u0436\u0430\u044e \u043d\u0435\u0434\u0435\u043b\u044e...")
    ws = get_week_start(datetime.now()); sch = parse_schedule(u["group_id"], ws)
    if sch.get("error"): await w.edit_text(f"\u274c {sch['error']}", parse_mode=ParseMode.HTML); return
    hdr = f"\U0001f465 <b>{u['group_name']}</b>\n\U0001f4c5 {ws.strftime('%d.%m')} \u2014 {(ws+timedelta(days=5)).strftime('%d.%m.%Y')}\n"
    await w.edit_text(hdr, parse_mode=ParseMode.HTML)
    for dn in DAYS_OF_WEEK:
        ls = sch.get("days",{}).get(dn,[]); ds = sch.get("dates",{}).get(dn,"")
        await msg.answer(format_day_schedule(ls, dn, ds), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        await asyncio.sleep(0.3)
    await msg.answer("\U0001f4c5 \u041d\u0430\u0432\u0438\u0433\u0430\u0446\u0438\u044f:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="\u25c0\ufe0f", callback_data=f"wk:{(ws-timedelta(days=7)).strftime('%Y%m%d')}"),
        InlineKeyboardButton(text="\u25b6\ufe0f", callback_data=f"wk:{(ws+timedelta(days=7)).strftime('%Y%m%d')}")]]))

@router.callback_query(F.data.startswith("wk:"))
async def nav_week(cb: types.CallbackQuery):
    u = get_user(cb.from_user.id)
    if not u or not u.get("group_id"): await cb.answer("\u26a0\ufe0f"); return
    ws = datetime.strptime(cb.data.split(":")[1], "%Y%m%d")
    await cb.answer("\u23f3")
    sch = parse_schedule(u["group_id"], ws)
    if sch.get("error"): await cb.message.edit_text(f"\u274c {sch['error']}", parse_mode=ParseMode.HTML); return
    hdr = f"\U0001f465 <b>{u['group_name']}</b>\n\U0001f4c5 {ws.strftime('%d.%m')} \u2014 {(ws+timedelta(days=5)).strftime('%d.%m.%Y')}\n"
    await cb.message.edit_text(hdr, parse_mode=ParseMode.HTML)
    for dn in DAYS_OF_WEEK:
        ls = sch.get("days",{}).get(dn,[]); ds = sch.get("dates",{}).get(dn,"")
        await cb.message.answer(format_day_schedule(ls, dn, ds), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        await asyncio.sleep(0.3)
    await cb.message.answer("\U0001f4c5", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="\u25c0\ufe0f", callback_data=f"wk:{(ws-timedelta(days=7)).strftime('%Y%m%d')}"),
        InlineKeyboardButton(text="\u25b6\ufe0f", callback_data=f"wk:{(ws+timedelta(days=7)).strftime('%Y%m%d')}")]]))

@router.message(F.text.contains("\u041f\u0440\u043e\u0444\u0438\u043b"))
async def profile(msg: types.Message):
    u = get_user(msg.from_user.id)
    if not u or not u.get("group_id"): await msg.answer("\u26a0\ufe0f /setup", reply_markup=main_kb(msg.from_user.id)); return
    await msg.answer(f"\U0001f464 <b>\u041f\u0440\u043e\u0444\u0438\u043b\u044c</b>\n\n\U0001f3eb {u.get('faculty_name','')}\n\U0001f4da \u041a\u0443\u0440\u0441: {u.get('course','')}\n\U0001f465 {u.get('group_name','')}\n\U0001f4cb {u.get('direction','')}", parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="\U0001f504 \u0418\u0437\u043c\u0435\u043d\u0438\u0442\u044c", callback_data="chg")],[InlineKeyboardButton(text="\U0001f5d1 \u0421\u0431\u0440\u043e\u0441", callback_data="rst")]]))

@router.callback_query(F.data=="chg")
async def chg(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(Setup.faculty)
    await cb.message.edit_text("\U0001f3eb <b>\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0438\u043d\u0441\u0442\u0438\u0442\u0443\u0442:</b>", reply_markup=fac_kb(0), parse_mode=ParseMode.HTML)
    await cb.answer()

@router.callback_query(F.data=="rst")
async def rst(cb: types.CallbackQuery):
    await cb.message.edit_text("\u26a0\ufe0f \u0421\u0431\u0440\u043e\u0441\u0438\u0442\u044c?", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="\u2705 \u0414\u0430", callback_data="rst_y"), InlineKeyboardButton(text="\u274c \u041d\u0435\u0442", callback_data="rst_n")]]))
    await cb.answer()

@router.callback_query(F.data=="rst_y")
async def rst_y(cb: types.CallbackQuery):
    delete_user(cb.from_user.id); await cb.message.edit_text("\u2705 \u0421\u0431\u0440\u043e\u0448\u0435\u043d\u043e.")
    await cb.message.answer("/setup", reply_markup=main_kb(cb.from_user.id)); await cb.answer()

@router.callback_query(F.data=="rst_n")
async def rst_n(cb: types.CallbackQuery): await cb.message.edit_text("\U0001f44c"); await cb.answer()

@router.message(Command("help"))
async def help_cmd(msg: types.Message):
    await msg.answer("\U0001f4d6 <b>\u041f\u043e\u043c\u043e\u0449\u044c</b>\n\n/setup \u2014 \u041d\u0430\u0441\u0442\u0440\u043e\u0438\u0442\u044c\n\U0001f4c5 \u0421\u0435\u0433\u043e\u0434\u043d\u044f/\u0417\u0430\u0432\u0442\u0440\u0430\n\U0001f4cb \u041d\u0430 \u043d\u0435\u0434\u0435\u043b\u044e\n\U0001f310 WebApp", parse_mode=ParseMode.HTML)

async def main():
    init_db(); dp.include_router(router)
    logger.info("Bot starting..."); await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())