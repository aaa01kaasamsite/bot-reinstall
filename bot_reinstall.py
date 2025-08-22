import os
import asyncio
import paramiko
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# --- Konfigurasi ---
BOT_TOKEN = os.getenv("BOT_TOKEN")  # ambil dari Environment Variable
DEFAULT_PASSWORD_RDP = "Warning1@"   # default password RDP
DEFAULT_PORT_RDP = "6969"            # default port RDP

# List pilihan OS
OS_OPTIONS = {
    "2012": "https://download1588.mediafire.com/.../w2012r2.gz",
    "2016": "joko/win2016.gz",
    "2019": "joko/win2019.gz",
    "2022": "joko/win2022.gz",
    "custom": None
}

# --- State sementara untuk tiap user ---
user_state = {}


# === Fungsi SSH eksekusi reinstall ===
def run_reinstall(ip, root_pass, os_url, rdp_pass, rdp_port):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username="root", password=root_pass, timeout=10)

        cmd = (
            f"bash reinstall.sh dd "
            f"--rdp-port {rdp_port} "
            f"--password '{rdp_pass}' "
            f"--img '{os_url}'"
        )

        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode() + stderr.read().decode()
        ssh.close()

        return True, output
    except Exception as e:
        return False, str(e)


# === Command /warn ===
async def warn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ Format salah.\nGunakan:\n`/warn <IP> <ROOT_PASS>`", parse_mode="Markdown")
        return

    ip, root_pass = context.args[0], context.args[1]

    # Simpan state user
    user_state[update.effective_chat.id] = {
        "ip": ip,
        "root_pass": root_pass,
        "os": None,
        "rdp_pass": None,
        "rdp_port": None
    }

    # Inline menu pilihan OS
    keyboard = [
        [InlineKeyboardButton("Windows 2012", callback_data="os_2012")],
        [InlineKeyboardButton("Windows 2016", callback_data="os_2016")],
        [InlineKeyboardButton("Windows 2019", callback_data="os_2019")],
        [InlineKeyboardButton("Windows 2022", callback_data="os_2022")],
        [InlineKeyboardButton("Custom URL", callback_data="os_custom")]
    ]
    await update.message.reply_text(
        f"🖥️ Reinstall VPS `{ip}`\n\nPilih OS yang ingin diinstall:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# === Handler tombol OS ===
async def os_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id

    state = user_state.get(chat_id)
    if not state:
        await query.edit_message_text("⚠️ Session tidak ditemukan. Jalankan ulang perintah `/warn`.")
        return

    choice = query.data.replace("os_", "")
    if choice == "custom":
        state["os"] = "custom"
        await query.edit_message_text("🔗 Kirim URL ISO kustom untuk VPS:")
        return
    else:
        state["os"] = OS_OPTIONS[choice]

    # Lanjut ke input password RDP
    keyboard = [
        [InlineKeyboardButton("Gunakan default", callback_data="rdp_pass_default")],
        [InlineKeyboardButton("Input manual", callback_data="rdp_pass_manual")]
    ]
    await query.edit_message_text(
        f"🔑 Atur password RDP (default: `{DEFAULT_PASSWORD_RDP}`)",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# === Handler custom URL ===
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    state = user_state.get(chat_id)

    if state and state.get("os") == "custom" and not state.get("rdp_pass"):
        url = update.message.text.strip()
        if url.startswith("http://") or url.startswith("https://"):
            state["os"] = url
            # Lanjut ke input password RDP
            keyboard = [
                [InlineKeyboardButton("Gunakan default", callback_data="rdp_pass_default")],
                [InlineKeyboardButton("Input manual", callback_data="rdp_pass_manual")]
            ]
            await update.message.reply_text(
                f"🔑 Atur password RDP (default: `{DEFAULT_PASSWORD_RDP}`)",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text("❌ URL tidak valid. Pastikan diawali dengan http:// atau https://")


# === Handler password RDP ===
async def rdp_pass_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id
    state = user_state.get(chat_id)

    if query.data == "rdp_pass_default":
        state["rdp_pass"] = DEFAULT_PASSWORD_RDP
    else:
        await query.edit_message_text("✍️ Kirim password RDP yang ingin digunakan:")
        return

    # Lanjut ke port RDP
    keyboard = [
        [InlineKeyboardButton("Gunakan default", callback_data="rdp_port_default")],
        [InlineKeyboardButton("Input manual", callback_data="rdp_port_manual")]
    ]
    await query.edit_message_text(
        f"🔌 Atur port RDP (default: `{DEFAULT_PORT_RDP}`)",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# === Handler manual password RDP ===
async def handle_rdp_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    state = user_state.get(chat_id)

    if state and not state.get("rdp_pass"):
        state["rdp_pass"] = update.message.text.strip()
        # Lanjut ke port RDP
        keyboard = [
            [InlineKeyboardButton("Gunakan default", callback_data="rdp_port_default")],
            [InlineKeyboardButton("Input manual", callback_data="rdp_port_manual")]
        ]
        await update.message.reply_text(
            f"🔌 Atur port RDP (default: `{DEFAULT_PORT_RDP}`)",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


# === Handler port RDP ===
async def rdp_port_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id
    state = user_state.get(chat_id)

    if query.data == "rdp_port_default":
        state["rdp_port"] = DEFAULT_PORT_RDP
        await execute_reinstall(query, state)
    else:
        await query.edit_message_text("✍️ Kirim port RDP (1024–65535):")


# === Handler manual port RDP ===
async def handle_rdp_port(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    state = user_state.get(chat_id)

    if state and not state.get("rdp_port"):
        port = update.message.text.strip()
        if port.isdigit() and 1024 <= int(port) <= 65535:
            state["rdp_port"] = port
            await execute_reinstall(update, state)
        else:
            await update.message.reply_text("❌ Port tidak valid. Masukkan angka antara 1024–65535.")


# === Eksekusi reinstall ===
async def execute_reinstall(source, state):
    ip = state["ip"]
    root_pass = state["root_pass"]
    os_url = state["os"]
    rdp_pass = state["rdp_pass"]
    rdp_port = state["rdp_port"]

    msg = (
        f"🚀 Memulai reinstall VPS `{ip}`...\n\n"
        f"🖥️ OS: {os_url}\n"
        f"🔑 RDP Pass: {rdp_pass}\n"
        f"🔌 RDP Port: {rdp_port}"
    )

    if isinstance(source, Update):
        await source.message.reply_text(msg, parse_mode="Markdown")
    else:
        await source.edit_message_text(msg, parse_mode="Markdown")

    ok, result = run_reinstall(ip, root_pass, os_url, rdp_pass, rdp_port)

    if ok:
        text = (
            f"✅ Reinstall berhasil dijalankan!\n\n"
            f"📡 Cek progres di browser:\nhttp://{ip}\n\n"
            f"ℹ️ VPS akan reboot otomatis setelah selesai."
        )
    else:
        text = f"❌ Gagal menjalankan reinstall:\n{result}"

    if isinstance(source, Update):
        await source.message.reply_text(text)
    else:
        await source.edit_message_text(text)


# === Main Bot ===
async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("warn", warn_command))
    app.add_handler(CallbackQueryHandler(os_choice, pattern="^os_"))
    app.add_handler(CallbackQueryHandler(rdp_pass_choice, pattern="^rdp_pass_"))
    app.add_handler(CallbackQueryHandler(rdp_port_choice, pattern="^rdp_port_"))
    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("👋 Halo! Gunakan /warn <IP> <ROOT_PASS>")))
    app.add_handler(CommandHandler("help", lambda u, c: u.message.reply_text("ℹ️ Gunakan /warn <IP> <ROOT_PASS> untuk reinstall VPS")))

    # Handler input text
    app.add_handler(
        # Custom OS URL
        telegram.ext.MessageHandler(telegram.ext.filters.TEXT & ~telegram.ext.filters.COMMAND, handle_text)
    )
    app.add_handler(
        # Manual RDP Pass
        telegram.ext.MessageHandler(telegram.ext.filters.TEXT & ~telegram.ext.filters.COMMAND, handle_rdp_pass)
    )
    app.add_handler(
        # Manual RDP Port
        telegram.ext.MessageHandler(telegram.ext.filters.TEXT & ~telegram.ext.filters.COMMAND, handle_rdp_port)
    )

    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
