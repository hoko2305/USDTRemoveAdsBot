# api/bot.py
from telegram import Update, ChatPermissions
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler
from telegram.request import HTTPXRequest
from datetime import timedelta
from dotenv import load_dotenv
import os
import json
from http.server import BaseHTTPRequestHandler

# 加载环境变量
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
# Vercel 分配的域名（后续部署后替换）
VERCEL_URL = os.getenv("VERCEL_URL")

# 广告关键词库
AD_KEYWORDS = [
    "赚米", "兼职", "刷单", "彩票", "投资", "理财", "微商",
    "代理", "推广", "扫码", "加我", "私聊", "领取", "福利"
]
WARNING_MESSAGE = "?? 你发送了违规内容，已被禁言24小时！"

# 初始化 Bot 应用
request = HTTPXRequest(con_pool_size=8)
application = Application.builder().token(BOT_TOKEN).request(request).build()

async def handle_violation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理违规消息逻辑（和之前一致）"""
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not user or not chat:
        return

    # 管理员豁免
    try:
        chat_member = await context.bot.get_chat_member(chat.id, user.id)
        if chat_member.status in ["administrator", "creator"]:
            return
    except Exception as e:
        print(f"权限检测失败: {e}")
        return

    # 违规检测
    is_violation = False
    if message.forward_origin:
        is_violation = True
    else:
        text = (message.text or message.caption or "").lower()
        link_keywords = ["http", "https", "t.me", "telegram.me"]
        if any(link in text for link in link_keywords) or any(kw in text for kw in AD_KEYWORDS):
            is_violation = True

    # 执行处罚
    if is_violation:
        try:
            await message.delete()
            # 24小时禁言
            restricted_perms = ChatPermissions(send_messages=False)
            await context.bot.restrict_chat_member(
                chat_id=chat.id,
                user_id=user.id,
                permissions=restricted_perms,
                until_date=timedelta(hours=24)
            )
            await context.bot.send_message(chat_id=user.id, text=WARNING_MESSAGE)
        except Exception as e:
            print(f"处罚执行失败: {e}")

# 注册消息处理器
application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_violation))

# Vercel Serverless 入口
class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(200)
        self.end_headers()
        # 解析请求体并传递给 Bot
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        update = Update.de_json(body, application.bot)
        application.process_update(update)
        self.wfile.write(b"OK")
        return

# 设置 Webhook（首次部署后执行一次）
async def set_webhook():
    await application.bot.set_webhook(url=f"{VERCEL_URL}/api/bot")
    print(f"Webhook 设置完成: {VERCEL_URL}/api/bot")

# 本地测试用（可选）
if __name__ == "__main__":
    import asyncio
    asyncio.run(set_webhook())
    application.run_polling()