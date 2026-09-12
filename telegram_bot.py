import os, io, asyncio, logging, threading, http.server, socketserver
from dotenv import load_dotenv
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from core import run_council, run_mega_scan, build_html_report, parse_ticker_list

load_dotenv(".env")
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

MEMORY = {}
CAP = 8

def _health_server():
    try:
        port = int(os.environ.get("PORT", "8000"))
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200); self.end_headers(); self.wfile.write(b"SUPERGOD ALIVE")
            def log_message(self, *a): pass
        with socketserver.TCPServer(("0.0.0.0", port), H) as s:
            s.serve_forever()
    except Exception as e:
        print("health server skipped:", e)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    MEMORY[str(update.message.chat_id)] = []
    await update.message.reply_text("🚀 *Supergod Council v3!*\nMemory: ON.\nMega Scan: paste a numbered ticker list (4+ tickers) and I will return a full HTML report file!", parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat_id)
    user_id = str(update.message.from_user.id)
    text = update.message.text
    tickers = parse_ticker_list(text)
    if len(tickers) >= 4 or text.strip().upper().startswith("MEGASCAN"):
        await update.message.reply_text(f"🛰 MEGA SCAN started: {len(tickers)} emitens. This takes some minutes, hold tight...")
        results = await asyncio.to_thread(run_mega_scan, tickers)
        html = build_html_report(results)
        summary = "\n".join(f"{r['TICKER']}: {r['VERDICT']}" for r in results)
        for i in range(0, len(summary), 4000):
            await update.message.reply_text(summary[i:i+4000])
        await update.message.reply_document(document=InputFile(io.BytesIO(html.encode()), filename="supergod_megascan.html"))
        return
    hist = MEMORY.setdefault(chat_id, [])
    await update.message.chat.send_action(action="typing")
    response = await asyncio.to_thread(run_council, user_id, text, hist)
    hist.append({"role":"user","content":text})
    hist.append({"role":"assistant","content":response})
    while len(hist) > CAP: hist.pop(0)
    for i in range(0, len(response), 4000):
        chunk = response[i:i+4000]
        try: await update.message.reply_text(chunk, parse_mode="Markdown")
        except Exception: await update.message.reply_text(chunk)

def main():
    threading.Thread(target=_health_server, daemon=True).start()
    app = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 Telegram Bot v3 running (memory + megascan + health port)...")
    app.run_polling()

if __name__ == "__main__":
    main()
