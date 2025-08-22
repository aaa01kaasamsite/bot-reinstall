import os
import paramiko
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- Konfigurasi ---
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Simpan state sementara
user_state = {}

# --- Dummy HTTP server untuk Render ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_http_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), DummyHandler)
    server.serve_forever()

threading.Thread(target=run_http_server, daemon=True).start()

# --- Command /warn ---
async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("Format salah!\nGunakan: /warn <IP> <ROOT_PASS>")
        return

    ip, root_pass = context.args
    user_id = update.effective_user.id
    user_state[user_id] = {"ip": ip, "root_pass": root_pass}

    # Pilihan OS
    keyboard = [
        [InlineKeyboardButton("Windows 2012", callback_data="os_win2012")],
        [InlineKeyboardButton("Windows 2016", callback_data="os_win2016")],
        [InlineKeyboardButton("Windows 2019", callback_data="os_win2019")],
        [InlineKeyboardButton("Windows 2022", callback_data="os_win2022")],
        [InlineKeyboardButton("Custom URL", callback_data="os_custom")],
    ]
    await update.message.reply_text(
        f"Reinstall VPS {ip}\n\nPilih OS yang ingin diinstall:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

# --- Handler pilih OS ---
async def choose_os(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = user_state.get(user_id)

    os_map = {
        "os_win2012": "https://download1588.mediafire.com/.../w2012r2.gz",
        "os_win2016": "joko/win2016.gz",
        "os_win2019": "joko/win2019.gz",
        "os_win2022": "joko/win2022.gz",
    }

    if query.data == "os_custom":
        await query.edit_message_text("Kirim URL ISO custom:")
        state["next"] = "awaiting_custom_url"
        return

    state["os_url"] = os_map.get(query.data)
    await ask_rdp_password(query, state)

async def handle_custom_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = user_state.get(user_id)
    if state and state.get("next") == "awaiting_custom_url":
        url = update.message.text.strip()
        if not url.startswith("http"):
            await update.message.reply_text("URL tidak valid, harus mulai dengan http/https.")
            return
        state["os_url"] = url
        await ask_rdp_password(update.message, state)

# --- Input password RDP ---
async def ask_rdp_password(target, state):
    keyboard = [
        [InlineKeyboardButton("Gunakan default (Warning1@)", callback_data="pass_default")],
        [InlineKeyboardButton("Input manual", callback_data="pass_manual")],
    ]
    await target.reply_text("Pilih password RDP:", reply_markup=InlineKeyboardMarkup(keyboard))

async def choose_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = user_state.get(user_id)

    if query.data == "pass_default":
        state["rdp_pass"] = "Warning1@"
        await ask_rdp_port(query, state)
    else:
        await query.edit_message_text("Ketik password RDP yang kamu inginkan (kosong = default Warning1@):")
        state["next"] = "awaiting_rdp_pass"

async def handle_pass_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = user_state.get(user_id)
    if state and state.get("next") == "awaiting_rdp_pass":
        txt = update.message.text.strip()
        state["rdp_pass"] = txt if txt else "Warning1@"
        await ask_rdp_port(update.message, state)

# --- Input port RDP ---
async def ask_rdp_port(target, state):
    keyboard = [
        [InlineKeyboardButton("Gunakan default (6969)", callback_data="port_default")],
        [InlineKeyboardButton("Input manual", callback_data="port_manual")],
    ]
    await target.reply_text("Pilih port RDP:", reply_markup=InlineKeyboardMarkup(keyboard))

async def choose_port(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = user_state.get(user_id)

    if query.data == "port_default":
        state["rdp_port"] = "6969"
        await confirm_reinstall(query, state)
    else:
        await query.edit_message_text("Ketik port RDP (1024–65535, kosong = 6969):")
        state["next"] = "awaiting_rdp_port"

async def handle_port_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = user_state.get(user_id)
    if state and state.get("next") == "awaiting_rdp_port":
        txt = update.message.text.strip()
        if not txt:
            state["rdp_port"] = "6969"
        elif txt.isdigit() and 1024 <= int(txt) <= 65535:
            state["rdp_port"] = txt
        else:
            await update.message.reply_text("Port tidak valid, masukkan angka 1024–65535 atau kosong untuk default.")
            return
        await confirm_reinstall(update.message, state)

# --- Konfirmasi ---
async def confirm_reinstall(target, state):
    ip, os_url, rdp_pass, rdp_port = state["ip"], state["os_url"], state["rdp_pass"], state["rdp_port"]
    msg = (
        f"Konfirmasi reinstall VPS:\n\n"
        f"IP: {ip}\n"
        f"OS: {os_url}\n"
        f"RDP Pass: {rdp_pass}\n"
        f"RDP Port: {rdp_port}\n\n"
        f"Klik OK untuk mulai reinstall."
    )
    keyboard = [[InlineKeyboardButton("✅ OK", callback_data="do_reinstall")]]
    await target.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

# --- Eksekusi reinstall ---
async def do_reinstall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = user_state.get(user_id)

    ip, root_pass = state["ip"], state["root_pass"]
    os_url, rdp_pass, rdp_port = state["os_url"], state["rdp_pass"], state["rdp_port"]

    await query.edit_message_text("🔄 Menjalankan reinstall di VPS...")

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username="root", password=root_pass, timeout=20)

        cmd = f"bash reinstall.sh dd --rdp-port {rdp_port} --password {rdp_pass} --img {os_url}"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode() + stderr.read().decode()
        ssh.close()

        msg = f"✅ Reinstall dijalankan di {ip}\n\nCek progres: http://{ip}"
        if output:
            msg += f"\n\nLog awal:\n{output[:500]}..."  # potong biar gak kepanjangan
        await query.message.reply_text(msg)
    except Exception as e:
        await query.message.reply_text(f"❌ Gagal reinstall VPS: {e}")

# --- Main ---
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("warn", warn))
    app.add_handler(CallbackQueryHandler(choose_os, pattern="^os_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_url))
    app.add_handler(CallbackQueryHandler(choose_pass, pattern="^pass_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_pass_input))
    app.add_handler(CallbackQueryHandler(choose_port, pattern="^port_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_port_input))
    app.add_handler(CallbackQueryHandler(do_reinstall, pattern="^do_reinstall$"))

    app.run_polling()

if __name__ == "__main__":
    main()
