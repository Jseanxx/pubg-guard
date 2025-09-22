# guard/app.py
import logging, asyncio
import discord
from discord.ext import commands

from .config import load_config
from .rules import load_rules
from .state import init_state
from .detectors.avatar import load_refs
from .handlers.on_message_qr import handle_message_qr
from .handlers.messages import handle_message
from .handlers.threads import handle_thread_create
from .handlers.members import handle_member_join, handle_member_update, handle_user_update

def create_bot():
    cfg = load_config()
    logging.basicConfig(level=(logging.DEBUG if cfg.debug else logging.INFO))
    log = logging.getLogger("guard.app")

    intents = discord.Intents.default()
    intents.guilds = True
    intents.members = True
    intents.message_content = True  # 텍스트 감시 채널에서만 사용
    bot = commands.Bot(command_prefix="!", intents=intents)
    ALLOW_NONE = discord.AllowedMentions.none()

    rules = load_rules(cfg.rules_path)
    state = init_state(cfg.qr_sem, cfg.phash_sem)

    @bot.event
    async def on_ready():
        log.info("로그인: %s (%s)", bot.user, getattr(bot.user, 'id', '?'))
        try:
            n = load_refs(cfg)
            log.info("아바타 레퍼런스 로드: %d개", n)
        except Exception as e:
            log.warning("레퍼런스 로드 실패: %s", e)

    @bot.event
    async def on_message(msg: discord.Message):
        try:
            await handle_message_qr(bot, cfg, rules, state, msg)     # 첨부 QR 상시
            await handle_message(bot, cfg, rules, state, msg)        # 텍스트 파이프라인
        except Exception:
            logging.getLogger("guard.app").exception("on_message 오류")

    @bot.event
    async def on_message_edit(before: discord.Message, after: discord.Message):
        try:
            await handle_message_qr(bot, cfg, rules, state, after)
            await handle_message(bot, cfg, rules, state, after)
        except Exception:
            logging.getLogger("guard.app").exception("on_message_edit 오류")

    @bot.event
    async def on_thread_create(thread: discord.Thread):
        try:
            await handle_thread_create(bot, cfg, rules, state, thread)
        except Exception:
            logging.getLogger("guard.app").exception("on_thread_create 오류")

    @bot.event
    async def on_member_join(m: discord.Member):
        try:
            await handle_member_join(cfg, rules, state, m)
        except Exception:
            logging.getLogger("guard.app").exception("on_member_join 오류")

    @bot.event
    async def on_member_update(before: discord.Member, after: discord.Member):
        try:
            await handle_member_update(cfg, rules, state, before, after)
        except Exception:
            logging.getLogger("guard.app").exception("on_member_update 오류")

    @bot.event
    async def on_user_update(before: discord.User, after: discord.User):
        try:
            await handle_user_update(cfg, rules, state, bot, before, after)
        except Exception:
            logging.getLogger("guard.app").exception("on_user_update 오류")

    # 외부에서 start() 호출용
    bot._guard_cfg = cfg      # optional: 디버그/명령에서 접근
    bot._guard_rules = rules
    bot._guard_state = state
    return bot

async def main():
    bot = create_bot()
    cfg = bot._guard_cfg
    if not (cfg.token and cfg.guild_id and (cfg.log_qr_channel_id or cfg.log_phish_channel_id)):
        raise SystemExit("환경변수(DISCORD_TOKEN/GUILD_ID/LOG_*_CHANNEL_ID) 필요")
    await bot.start(cfg.token)

if __name__ == "__main__":
    asyncio.run(main())
