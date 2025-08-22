import asyncio
import logging
import paramiko
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

# --- CONFIG ---
BOT_TOKEN = "8260974320:AAFJP2sGaXwWNz372eaH7YH_s9fqGLWuoSU"
DEFAULT_RDP_PASS = "Warning1@"
DEFAULT_RDP_PORT = "6969"

# --- LOGGER ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- STATES ---
CHOOSE_OS, CHOOSE_PASS, CHOOSE_PORT, CONFIRM = range(4)

# --- Pilihan OS ---
OS_OPTIONS = {
    "Windows 2012": "https://example.com/win2012.gz",
    "Windows 2016": "https://example.com/win2016.gz",
    "Windows 2019": "https://example.com/win2019.gz",
    "Windows 2022": "https://example.com/win2022.gz",
    "Custom ISO": "CUSTOM",
}

# --- Command /warn ---
async def warn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Gunakan format:\n`/warn <IP> <ROOT_PASS>`", parse_mode="Markdown")
        return ConversationHandler.END

    ip = context.args[0]
    root_pass = context.args[1]

    context.user_data["ip"] = ip
    context.user_data["root_pass"] = root_pass

    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"os|{key}")]
        for key, name in enumerate(OS_OPTIONS.keys())
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("🖥️ Pilih OS untuk reinstall VPS:", reply_markup=reply_markup)
    return CHOOSE_OS

# --- Pilih OS ---
async def choose_os(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, os_key = query.data.split("|")
    os_name = list(OS_OPTIONS.keys())[int(os_key)]
    context.user_data["os"] = os_name

    keyboard = [
        [InlineKeyboardButton("Gunakan default", callback_data="pass|default")],
        [InlineKeyboardButton("Input manual", callback_data="pass|manual")],
    ]
    await query.edit_message_text(f"🔑 Pilih metode password RDP:", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOOSE_PASS

# --- Pilih Password ---
async def choose_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, method = query.data.split("|")

    if method == "default":
        context.user_data["rdp_pass"] = DEFAULT_RDP_PASS
        return await ask_port(query, context)

    else:  # manual
        await query.edit_message_text(f"Ketik password RDP (Enter kosong = {DEFAULT_RDP_PASS}):")
        return CHOOSE_PASS

async def save_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip() if update.message.text.strip() else DEFAULT_RDP_PASS
    context.user_data["rdp_pass"] = password
    return await ask_port(update.message, context)

# --- Pilih Port ---
async def ask_port(source, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Gunakan default", callback_data="port|default")],
        [InlineKeyboardButton("Input manual", callback_data="port|manual")],
    ]
    if hasattr(source, "reply_text"):
        await source.reply_text("🔌 Pilih metode port RDP:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await source.edit_message_text("🔌 Pilih metode port RDP:", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOOSE_PORT

async def choose_port(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, method = query.data.split("|")

    if method == "default":
        context.user_data["rdp_port"] = DEFAULT_RDP_PORT
        return await confirm_reinstall(query, context)

    else:
        await query.edit_message_text(f"Ketik port RDP (Enter kosong = {DEFAULT_RDP_PORT}):")
        return CHOOSE_PORT

async def save_port(update: Update, context: ContextTypes.DEFAULT_TYPE):
    port = update.message.text.strip() if update.message.text.strip() else DEFAULT_RDP_PORT
    context.user_data["rdp_port"] = port
    return await confirm_reinstall(update.message, context)

# --- Konfirmasi ---
async def confirm_reinstall(source, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data
    msg = (
        f"⚡ Konfirmasi reinstall VPS ⚡\n\n"
        f"📡 IP VPS: {data['ip']}\n"
        f"🔑 Root Pass: {data['root_pass']}\n"
        f"🖥️ OS: {data['os']}\n"
        f"🔐 RDP Pass: {data['rdp_pass']}\n"
        f"🔌 RDP Port: {data['rdp_port']}\n\n"
        f"Lanjutkan reinstall?"
    )
    keyboard = [
        [InlineKeyboardButton("✅ YA", callback_data="confirm|yes")],
        [InlineKeyboardButton("❌ BATAL", callback_data="confirm|no")],
    ]
    if hasattr(source, "reply_text"):
        await source.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await source.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    return CONFIRM

# --- Eksekusi Reinstall ---
async def do_reinstall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, choice = query.data.split("|")

    if choice == "no":
        await query.edit_message_text("❌ Reinstall dibatalkan.")
        return ConversationHandler.END

    data = context.user_data
    ip = data["ip"]
    root_pass = data["root_pass"]
    os_img = data["os"]
    rdp_pass = data["rdp_pass"]
    rdp_port = data["rdp_port"]

    await query.edit_message_text("🚀 Memulai reinstall VPS...")

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username="root", password=root_pass, timeout=20)

        if os_img == "Custom ISO":
            iso_url = "https://example.com/custom.iso"  # bisa diganti untuk input manual
        else:
            iso_url = OS_OPTIONS[os_img]

        cmd = f"bash reinstall.sh dd --rdp-port {rdp_port} --password '{rdp_pass}' --img '{iso_url}'"
        stdin, stdout, stderr = ssh.exec_command(cmd)

        output = stdout.read().decode()
        error = stderr.read().decode()
        ssh.close()

        msg = (
            f"✅ Reinstall VPS berhasil dijalankan!\n\n"
            f"📡 IP VPS: {ip}\n"
            f"🖥️ OS: {os_img}\n"
            f"🔐 RDP Pass: {rdp_pass}\n"
            f"🔌 RDP Port: {rdp_port}\n\n"
            f"🌍 Cek progress reinstall di browser:\nhttp://{ip}\n"
        )
        if output:
            msg += f"\n📝 Log:\n<code>{output[:400]}</code>"
        if error:
            msg += f"\n⚠️ Error:\n<code>{error[:400]}</code>"

        await query.edit_message_text(msg, parse_mode="HTML")

    except Exception as e:
        await query.edit_message_text(f"❌ Gagal reinstall VPS:\n{str(e)}")

    return ConversationHandler.END

# --- MAIN ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("warn", warn_command)],
        states={
            CHOOSE_OS: [CallbackQueryHandler(choose_os, pattern="^os\\|")],
            CHOOSE_PASS: [
                CallbackQueryHandler(choose_pass, pattern="^pass\\|"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_pass),
            ],
            CHOOSE_PORT: [
                CallbackQueryHandler(choose_port, pattern="^port\\|"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_port),
            ],
            CONFIRM: [CallbackQueryHandler(do_reinstall, pattern="^confirm\\|")],
        },
        fallbacks=[],
    )

    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == "__main__":
    main()
