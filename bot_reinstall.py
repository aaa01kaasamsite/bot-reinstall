import os
import asyncio
import paramiko
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler
from http.server import BaseHTTPRequestHandler, HTTPServer

# ===============================
# Environment Variable
# ===============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))  # Zeabur/Render butuh listen ke PORT

# ===============================
# State Machine Steps
# ===============================
CHOOSING_OS, CHOOSING_PASS, CHOOSING_PORT, CONFIRM = range(4)

# ===============================
# Fungsi SSH Reinstall
# ===============================
async def ssh_reinstall(ip, root_pass, img_url, rdp_pass, rdp_port):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username="root", password=root_pass, timeout=15)

        reinstall_cmd = f"""
        curl -fsSL https://raw.githubusercontent.com/kripul/reinstall/main/reinstall.sh -o reinstall.sh &&
        bash reinstall.sh dd --img '{img_url}' --password '{rdp_pass}' --rdp-port '{rdp_port}'
        """
        ssh.exec_command(reinstall_cmd)
        ssh.close()
        return True, None
    except Exception as e:
        return False, str(e)

# ===============================
# Command /warn <IP> <ROOT_PASS>
# ===============================
async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Format: /warn <IP> <ROOT_PASS>")
        return ConversationHandler.END

    ip = context.args[0]
    root_pass = context.args[1]
    context.user_data["ip"] = ip
    context.user_data["root_pass"] = root_pass

    # Pilihan OS (ISO)
    keyboard = [
        [InlineKeyboardButton("Windows 2012", callback_data="os_win2012")],
        [InlineKeyboardButton("Windows 2016", callback_data="os_win2016")],
        [InlineKeyboardButton("Windows 2019", callback_data="os_win2019")],
        [InlineKeyboardButton("Windows 2022", callback_data="os_win2022")],
        [InlineKeyboardButton("Custom URL", callback_data="os_custom")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Pilih OS yang ingin diinstall:", reply_markup=reply_markup
    )
    return CHOOSING_OS

# ===============================
# Handler Pilihan OS
# ===============================
async def os_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    os_map = {
        "os_win2012": "https://download1588.mediafire.com/.../w2012r2.gz",
        "os_win2016": "joko/win2016.gz",
        "os_win2019": "joko/win2019.gz",
        "os_win2022": "joko/win2022.gz",
    }

    if query.data == "os_custom":
        await query.edit_message_text("Kirim URL ISO kustom:")
        return CHOOSING_OS
    else:
        context.user_data["img_url"] = os_map[query.data]

    # Pilih Password RDP
    keyboard = [
        [InlineKeyboardButton("Gunakan Default (Warning1@)", callback_data="pass_default")],
        [InlineKeyboardButton("Masukkan Manual", callback_data="pass_manual")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text("Pilih password RDP:", reply_markup=reply_markup)
    return CHOOSING_PASS

# ===============================
# Handler Password
# ===============================
async def pass_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "pass_default":
        context.user_data["rdp_pass"] = "Warning1@"

        # lanjut pilih port
        keyboard = [
            [InlineKeyboardButton("Gunakan Default (6969)", callback_data="port_default")],
            [InlineKeyboardButton("Masukkan Manual", callback_data="port_manual")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text("Pilih port RDP:", reply_markup=reply_markup)
        return CHOOSING_PORT

    elif query.data == "pass_manual":
        await query.edit_message_text("Kirim password RDP manual:")
        return CHOOSING_PASS

async def set_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["rdp_pass"] = update.message.text

    # lanjut pilih port
    keyboard = [
        [InlineKeyboardButton("Gunakan Default (6969)", callback_data="port_default")],
        [InlineKeyboardButton("Masukkan Manual", callback_data="port_manual")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Pilih port RDP:", reply_markup=reply_markup)
    return CHOOSING_PORT

# ===============================
# Handler Port
# ===============================
async def port_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "port_default":
        context.user_data["rdp_port"] = "6969"

        return await confirm_settings(query, context)

    elif query.data == "port_manual":
        await query.edit_message_text("Kirim port RDP manual (1024-65535):")
        return CHOOSING_PORT

async def set_port(update: Update, context: ContextTypes.DEFAULT_TYPE):
    port = update.message.text
    if port.isdigit() and 1024 <= int(port) <= 65535:
        context.user_data["rdp_port"] = port
        return await confirm_settings(update, context)
    else:
        await update.message.reply_text("Port tidak valid, coba lagi:")
        return CHOOSING_PORT

# ===============================
# Konfirmasi
# ===============================
async def confirm_settings(update_or_query, context: ContextTypes.DEFAULT_TYPE):
    ip = context.user_data["ip"]
    root_pass = context.user_data["root_pass"]
    img_url = context.user_data["img_url"]
    rdp_pass = context.user_data["rdp_pass"]
    rdp_port = context.user_data["rdp_port"]

    text = (
        f"⚡ Konfirmasi reinstall VPS:\n"
        f"IP: {ip}\n"
        f"Root Pass: {root_pass}\n"
        f"IMG: {img_url}\n"
        f"RDP Pass: {rdp_pass}\n"
        f"RDP Port: {rdp_port}\n\n"
        f"Lanjutkan?"
    )

    keyboard = [
        [InlineKeyboardButton("✅ Ya, lanjutkan", callback_data="confirm_yes")],
        [InlineKeyboardButton("❌ Batal", callback_data="confirm_no")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if isinstance(update_or_query, Update):
        await update_or_query.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update_or_query.edit_message_text(text, reply_markup=reply_markup)

    return CONFIRM

# ===============================
# Handler Konfirmasi
# ===============================
async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_no":
        await query.edit_message_text("❌ Reinstall dibatalkan.")
        return ConversationHandler.END

    ip = context.user_data["ip"]
    root_pass = context.user_data["root_pass"]
    img_url = context.user_data["img_url"]
    rdp_pass = context.user_data["rdp_pass"]
    rdp_port = context.user_data["rdp_port"]

    await query.edit_message_text("🔄 Sedang menjalankan reinstall...")

    ok, err = await ssh_reinstall(ip, root_pass, img_url, rdp_pass, rdp_port)
    if ok:
        await query.message.reply_text(
            f"✅ Reinstall dimulai di {ip}.\n"
            f"👉 Cek progres: http://{ip}\n"
            f"RDP Port: {rdp_port}\nRDP Pass: {rdp_pass}"
        )
    else:
        await query.message.reply_text(f"❌ Gagal: {err}")

    return ConversationHandler.END

# ===============================
# Fallback
# ===============================
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Dibatalkan.")
    return ConversationHandler.END

# ===============================
# HTTP Server Dummy (untuk Render/Zeabur)
# ===============================
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_http_server():
    server = HTTPServer(("0.0.0.0", PORT), SimpleHandler)
    server.serve_forever()

# ===============================
# Main
# ===============================
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("warn", warn)],
        states={
            CHOOSING_OS: [
                CallbackQueryHandler(os_choice, pattern="^os_"),
                MessageHandler(None, os_choice),
            ],
            CHOOSING_PASS: [
                CallbackQueryHandler(pass_choice, pattern="^pass_"),
                MessageHandler(None, set_pass),
            ],
            CHOOSING_PORT: [
                CallbackQueryHandler(port_choice, pattern="^port_"),
                MessageHandler(None, set_port),
            ],
            CONFIRM: [CallbackQueryHandler(confirm, pattern="^confirm_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    # Jalankan bot dan HTTP server bersamaan
    loop = asyncio.get_event_loop()
    loop.create_task(application.run_polling())
    run_http_server()

if __name__ == "__main__":
    main()
