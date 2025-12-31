import requests, threading, os, json, time, urllib.parse, sys
from flask import Flask, request, Response, render_template_string

try:
    from telegram.ext import (
        ApplicationBuilder, CommandHandler, MessageHandler,
        ContextTypes, filters, CallbackQueryHandler
    )
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("⚠️ Warning: python-telegram-bot not installed. Telegram bot features disabled.")

# ========================
# CONFIGURATION
# ========================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8419010897:AAFBf7NBkWcDk9JYvCCUsjyQpFy6RqW3Ozg")
PORT = int(os.environ.get("PORT", 8080))

# Get Render external URL or use a placeholder for local testing
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "")
PUBLIC_URL = RENDER_EXTERNAL_URL if RENDER_EXTERNAL_URL else f"http://localhost:{PORT}"
RAW_URL = f"{PUBLIC_URL}/raw"

# Enhanced data storage with metadata
SAVED_DATA = ""
DATA_METADATA = {
    "last_updated": "",
    "size": 0,
    "format": "text",
    "author": "",
    "views": 0
}

# History tracking (last 10 updates)
DATA_HISTORY = []

# User sessions
user_sessions = {}

# ========================
# UTILITY FUNCTIONS
# ========================
def safe_encode_header(value):
    """Safely encode header values to avoid encoding issues"""
    if not value:
        return ""
    # Remove emojis and non-ASCII characters for header safety
    import re
    # Keep only ASCII characters for headers
    safe_value = re.sub(r'[^\x00-\x7F]+', '', str(value))
    return safe_value[:50]  # Limit header length

def detect_format(text):
    """Detect the format of the input text"""
    text = text.strip()
    if text.startswith('{') and text.endswith('}'):
        try:
            json.loads(text)
            return "json"
        except:
            pass
    elif text.startswith('<') and text.endswith('>'):
        return "xml/html"
    elif '```' in text:
        return "code"
    return "text"

def is_public_url(url):
    """Check if URL is publicly accessible (not localhost)"""
    return url and 'localhost' not in url and '127.0.0.1' not in url

# ========================
# SERVER (Enhanced Endpoints)
# ========================
app = Flask(__name__)

@app.route("/")
def home():
    """HTML interface for viewing raw data"""
    # Increment view counter
    DATA_METADATA["views"] = DATA_METADATA.get("views", 0) + 1
    
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>📁 RAW Data Viewer</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta charset="UTF-8">
        <style>
            :root {
                --primary: #667eea;
                --secondary: #764ba2;
                --success: #10b981;
                --info: #3b82f6;
                --warning: #f59e0b;
                --danger: #ef4444;
            }
            
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: 'Segoe UI', system-ui, sans-serif;
                background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
                min-height: 100vh;
                color: #333;
                padding: 20px;
            }
            
            .container {
                max-width: 1200px;
                margin: 0 auto;
            }
            
            header {
                text-align: center;
                margin-bottom: 30px;
                padding: 20px;
                background: rgba(255, 255, 255, 0.95);
                border-radius: 20px;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
            }
            
            h1 {
                color: var(--primary);
                font-size: 2.5rem;
                margin-bottom: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 15px;
            }
            
            h1::before {
                content: '📁';
                font-size: 3rem;
            }
            
            .subtitle {
                color: #666;
                font-size: 1.1rem;
                margin-bottom: 20px;
            }
            
            .dashboard {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            
            .card {
                background: rgba(255, 255, 255, 0.95);
                padding: 25px;
                border-radius: 15px;
                box-shadow: 0 5px 20px rgba(0, 0, 0, 0.08);
                transition: transform 0.3s, box-shadow 0.3s;
            }
            
            .card:hover {
                transform: translateY(-5px);
                box-shadow: 0 15px 30px rgba(0, 0, 0, 0.15);
            }
            
            .card h3 {
                color: var(--primary);
                margin-bottom: 15px;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            
            .stat-grid {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 15px;
            }
            
            .stat-item {
                text-align: center;
                padding: 15px;
                background: rgba(102, 126, 234, 0.1);
                border-radius: 10px;
            }
            
            .stat-value {
                font-size: 1.8rem;
                font-weight: bold;
                color: var(--primary);
                display: block;
            }
            
            .stat-label {
                font-size: 0.9rem;
                color: #666;
                margin-top: 5px;
            }
            
            .data-container {
                background: rgba(255, 255, 255, 0.95);
                border-radius: 15px;
                padding: 30px;
                margin-bottom: 30px;
                box-shadow: 0 5px 20px rgba(0, 0, 0, 0.08);
            }
            
            pre {
                background: #f8f9fa;
                padding: 20px;
                border-radius: 10px;
                overflow-x: auto;
                font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
                font-size: 14px;
                line-height: 1.5;
                max-height: 500px;
                overflow-y: auto;
                border: 1px solid #e9ecef;
                white-space: pre-wrap;
                word-wrap: break-word;
            }
            
            .empty-data {
                text-align: center;
                color: #666;
                padding: 40px;
                font-size: 1.2rem;
            }
            
            .empty-data::before {
                content: '📭';
                font-size: 3rem;
                display: block;
                margin-bottom: 15px;
            }
            
            .actions {
                display: flex;
                flex-wrap: wrap;
                gap: 15px;
                justify-content: center;
                margin-top: 30px;
            }
            
            .btn {
                padding: 12px 24px;
                border: none;
                border-radius: 10px;
                font-size: 1rem;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s;
                text-decoration: none;
                display: inline-flex;
                align-items: center;
                gap: 10px;
                color: white;
            }
            
            .btn-primary {
                background: var(--primary);
            }
            
            .btn-primary:hover {
                background: #5a6fd8;
                transform: translateY(-2px);
            }
            
            .btn-success {
                background: var(--success);
            }
            
            .btn-success:hover {
                background: #0da271;
                transform: translateY(-2px);
            }
            
            .btn-info {
                background: var(--info);
            }
            
            .btn-info:hover {
                background: #2563eb;
                transform: translateY(-2px);
            }
            
            .btn-warning {
                background: var(--warning);
            }
            
            .btn-warning:hover {
                background: #e59409;
                transform: translateY(-2px);
            }
            
            footer {
                text-align: center;
                margin-top: 40px;
                color: rgba(255, 255, 255, 0.8);
                font-size: 0.9rem;
            }
            
            .copy-btn {
                position: absolute;
                top: 10px;
                right: 10px;
                background: var(--primary);
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 5px;
                cursor: pointer;
                font-size: 0.9rem;
            }
            
            .url-display {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 10px;
                margin: 20px 0;
                position: relative;
                border: 1px solid #e9ecef;
                font-family: monospace;
                word-break: break-all;
            }
            
            @media (max-width: 768px) {
                h1 {
                    font-size: 2rem;
                }
                
                .dashboard {
                    grid-template-columns: 1fr;
                }
                
                .btn {
                    width: 100%;
                    justify-content: center;
                }
                
                .actions {
                    flex-direction: column;
                }
            }
        </style>
        <script>
            function copyToClipboard(text) {
                navigator.clipboard.writeText(text).then(() => {
                    alert('URL copied to clipboard!');
                });
            }
            
            function downloadData() {
                const data = `{{ data|safe }}`;
                const blob = new Blob([data], { type: 'text/plain' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'raw_data_{{ timestamp }}.txt';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
            }
        </script>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>RAW Data Viewer</h1>
                <p class="subtitle">Store, share, and access your data with a permanent URL</p>
            </header>
            
            <div class="dashboard">
                <div class="card">
                    <h3>📊 Statistics</h3>
                    <div class="stat-grid">
                        <div class="stat-item">
                            <span class="stat-value">{{ metadata.size }}</span>
                            <span class="stat-label">Bytes</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-value">{{ metadata.views }}</span>
                            <span class="stat-label">Views</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-value">{{ metadata.format }}</span>
                            <span class="stat-label">Format</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-value">{{ history_count }}</span>
                            <span class="stat-label">History</span>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <h3>📅 Information</h3>
                    <p><strong>Last Updated:</strong><br>{{ metadata.last_updated }}</p>
                    {% if metadata.author %}
                    <p style="margin-top: 10px;"><strong>Author:</strong><br>{{ metadata.author }}</p>
                    {% endif %}
                    <p style="margin-top: 10px;"><strong>Status:</strong><br>
                        <span style="color: var(--success); font-weight: bold;">● Active</span>
                    </p>
                </div>
                
                <div class="card">
                    <h3>🔗 Quick Links</h3>
                    <div class="url-display">
                        {{ raw_url }}
                        <button class="copy-btn" onclick="copyToClipboard('{{ raw_url }}')">Copy</button>
                    </div>
                    <p style="margin-top: 15px; font-size: 0.9rem; color: #666;">
                        Use this URL to access your data from anywhere
                    </p>
                </div>
            </div>
            
            <div class="data-container">
                <h3 style="margin-bottom: 20px; display: flex; align-items: center; gap: 10px;">
                    📄 Stored Data
                    <span style="font-size: 0.9rem; color: #666; font-weight: normal;">
                        ({{ metadata.size }} bytes)
                    </span>
                </h3>
                
                {% if data %}
                <pre>{{ data }}</pre>
                {% else %}
                <div class="empty-data">
                    No data stored yet. {% if telegram_available %}Send data via Telegram bot{% else %}Use API{% endif %} to get started!
                </div>
                {% endif %}
            </div>
            
            <div class="actions">
                <button class="btn btn-primary" onclick="downloadData()">
                    <span>📥</span> Download Data
                </button>
                <a href="{{ raw_url }}" class="btn btn-success" target="_blank">
                    <span>🔗</span> Open RAW URL
                </a>
                <a href="{{ raw_url }}?format=json" class="btn btn-info" target="_blank">
                    <span>📊</span> JSON Format
                </a>
                <a href="/stats" class="btn btn-warning">
                    <span>📈</span> Detailed Stats
                </a>
                {% if telegram_available %}
                <a href="https://t.me/{{ bot_username }}" class="btn btn-primary" target="_blank">
                    <span>🤖</span> Telegram Bot
                </a>
                {% endif %}
            </div>
            
            <footer>
                <p>Powered by Flask | {{ timestamp }}</p>
                <p style="margin-top: 5px; font-size: 0.8rem;">
                    Data is stored permanently until cleared
                </p>
            </footer>
        </div>
    </body>
    </html>
    """
    
    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    return render_template_string(
        html_template,
        data=SAVED_DATA,
        metadata=DATA_METADATA,
        raw_url=RAW_URL,
        timestamp=current_time,
        history_count=len(DATA_HISTORY),
        telegram_available=TELEGRAM_AVAILABLE,
        bot_username="your_bot_username"  # Replace with your bot username
    )

@app.route("/raw", methods=["GET"])
def read_raw():
    """Enhanced raw endpoint with format options"""
    format_type = request.args.get('format', 'text')
    
    if format_type == 'json':
        return Response(
            json.dumps({
                "data": SAVED_DATA,
                "metadata": DATA_METADATA,
                "history_count": len(DATA_HISTORY),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }, indent=2),
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )
    elif format_type == 'html':
        return f"<pre>{SAVED_DATA}</pre>"
    else:
        return Response(
            SAVED_DATA,
            mimetype="text/plain",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )

@app.route("/raw", methods=["POST"])
def write_raw():
    """Enhanced write endpoint with metadata"""
    global SAVED_DATA, DATA_METADATA, DATA_HISTORY
    
    try:
        # Get data from request
        data = request.data.decode("utf-8")
        
        # Save to history (keep last 10)
        if SAVED_DATA:
            DATA_HISTORY.append({
                "data": SAVED_DATA[:100] + "..." if len(SAVED_DATA) > 100 else SAVED_DATA,
                "timestamp": DATA_METADATA["last_updated"],
                "size": DATA_METADATA["size"]
            })
            if len(DATA_HISTORY) > 10:
                DATA_HISTORY.pop(0)
        
        # Update data
        SAVED_DATA = data
        
        # Get author safely
        author = safe_encode_header(request.headers.get('X-Author', 'Unknown'))
        
        # Update metadata
        DATA_METADATA.update({
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "size": len(SAVED_DATA),
            "format": detect_format(SAVED_DATA),
            "author": author,
            "views": DATA_METADATA.get("views", 0)
        })
        
        return json.dumps({
            "status": "success",
            "message": "Data updated successfully",
            "metadata": DATA_METADATA,
            "url": RAW_URL
        })
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e)
        }), 400

@app.route("/stats")
def stats():
    """Statistics endpoint"""
    stats_data = {
        "current_size": len(SAVED_DATA),
        "history_entries": len(DATA_HISTORY),
        "metadata": DATA_METADATA,
        "access_url": RAW_URL,
        "web_interface": PUBLIC_URL,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "server_status": "running",
        "telegram_bot": "available" if TELEGRAM_AVAILABLE else "not_available"
    }
    return json.dumps(stats_data, indent=2)

@app.route("/health")
def health():
    """Health check endpoint"""
    return json.dumps({
        "status": "healthy",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "data_exists": bool(SAVED_DATA),
        "public_url": is_public_url(PUBLIC_URL),
        "telegram_bot": "available" if TELEGRAM_AVAILABLE else "not_available"
    })

@app.route("/update", methods=["POST"])
def update_data():
    """Simple API endpoint to update data"""
    global SAVED_DATA, DATA_METADATA
    
    try:
        data = request.get_data(as_text=True)
        if not data:
            return json.dumps({"status": "error", "message": "No data provided"}), 400
        
        SAVED_DATA = data
        DATA_METADATA.update({
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "size": len(SAVED_DATA),
            "format": detect_format(SAVED_DATA),
            "author": request.headers.get('X-Author', 'API'),
            "views": DATA_METADATA.get("views", 0)
        })
        
        return json.dumps({
            "status": "success",
            "message": "Data updated via API",
            "url": RAW_URL,
            "size": len(SAVED_DATA)
        })
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}), 500

def run_server():
    """Run Flask server"""
    print(f"🌐 Starting Flask server on port {PORT}...")
    print(f"📡 Server URL: {PUBLIC_URL}")
    print(f"🔗 RAW Endpoint: {RAW_URL}")
    print(f"📊 Statistics: {PUBLIC_URL}/stats")
    print(f"🏥 Health Check: {PUBLIC_URL}/health")
    print(f"🤖 Telegram Bot: {'Available' if TELEGRAM_AVAILABLE else 'Not available'}")
    
    if not TELEGRAM_AVAILABLE:
        print("⚠️  Note: To enable Telegram bot, install python-telegram-bot and set BOT_TOKEN")
    
    app.run(host="0.0.0.0", port=PORT, debug=False)

# ========================
# TELEGRAM BOT FUNCTIONS
# ========================
if TELEGRAM_AVAILABLE:
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command with inline keyboard"""
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name
        user_sessions[user_id] = {
            "waiting_for_data": False,
            "username": username
        }
        
        # Create keyboard dynamically based on whether URL is public
        keyboard = [
            [
                InlineKeyboardButton("📝 Update Data", callback_data="update_data"),
                InlineKeyboardButton("📊 View Data", callback_data="view_data")
            ],
            [
                InlineKeyboardButton("🔗 Get Raw Link", callback_data="get_link"),
                InlineKeyboardButton("📈 Statistics", callback_data="stats")
            ],
            [
                InlineKeyboardButton("❓ Help", callback_data="help"),
                InlineKeyboardButton("🔄 History", callback_data="history")
            ]
        ]
        
        # Only add web interface button if URL is public
        if is_public_url(PUBLIC_URL):
            keyboard.append([
                InlineKeyboardButton("🌐 Web Interface", url=PUBLIC_URL)
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = (
            f"🤖 **Welcome to RAW Data Bot, {username}!**\n\n"
            "✨ **Features:**\n"
            "• 📝 Store any text/data permanently\n"
            "• 🔗 Get a public RAW link\n"
            "• 📊 View data statistics\n"
            "• 📜 Data history tracking\n"
        )
        
        # Add web interface info if available
        if is_public_url(PUBLIC_URL):
            welcome_text += "• 🌐 Beautiful web interface\n\n"
        else:
            welcome_text += "\n"
        
        welcome_text += "💡 *Select an option below:*"
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard button clicks"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if query.data == "update_data":
            user_sessions[user_id]["waiting_for_data"] = True
            await query.edit_message_text(
                "📝 **Send me the data/text you want to store:**\n\n"
                "You can send:\n"
                "• 📄 Plain text\n"
                "• 📊 JSON data\n"
                "• ⚙️ Configuration files\n"
                "• 💻 Code snippets\n"
                "• 🔗 URLs or lists\n\n"
                "💡 *Type /cancel to abort.*",
                parse_mode="Markdown"
            )
        
        elif query.data == "view_data":
            if SAVED_DATA:
                # Create a more informative preview
                lines = SAVED_DATA.split('\n')
                preview_lines = lines[:5]  # Show first 5 lines
                preview = '\n'.join(preview_lines)
                
                if len(lines) > 5:
                    preview += f"\n[... and {len(lines) - 5} more lines]"
                
                # Format info
                format_icon = {
                    "json": "📊",
                    "code": "💻",
                    "xml/html": "🔖",
                    "text": "📄"
                }.get(DATA_METADATA.get("format", "text"), "📄")
                
                message_text = (
                    f"{format_icon} **Stored Data Preview:**\n\n"
                    f"```\n{preview}\n```\n\n"
                    f"📏 **Size:** {len(SAVED_DATA):,} bytes\n"
                    f"⏰ **Last Updated:** {DATA_METADATA.get('last_updated', 'Never')}\n"
                    f"👤 **Author:** {DATA_METADATA.get('author', 'Unknown')}\n"
                    f"👁️ **Views:** {DATA_METADATA.get('views', 0)}\n\n"
                    f"🔗 **RAW URL:** `{RAW_URL}`"
                )
                
                # Add web interface link only if public
                if is_public_url(PUBLIC_URL):
                    message_text += f"\n🌐 **Web:** `{PUBLIC_URL}`"
                
                await query.edit_message_text(
                    message_text,
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                )
            else:
                await query.edit_message_text(
                    "📭 **No data stored yet!**\n\n"
                    "Use the *'Update Data'* button to store your first data.",
                    parse_mode="Markdown"
                )
        
        elif query.data == "get_link":
            message_text = f"🔗 **Permanent RAW Links:**\n\n📄 **Text Format:**\n`{RAW_URL}`\n\n📊 **JSON Format:**\n`{RAW_URL}?format=json`\n\n"
            
            if is_public_url(PUBLIC_URL):
                message_text += f"🌐 **Web Interface:**\n`{PUBLIC_URL}`\n\n📊 **Statistics:**\n`{PUBLIC_URL}/stats`\n\n"
            
            message_text += "💡 *Click or copy the links to access your data!*"
            
            await query.edit_message_text(
                message_text,
                parse_mode="Markdown"
            )
        
        elif query.data == "stats":
            stats_text = (
                f"📊 **Statistics:**\n\n"
                f"• 📏 **Data Size:** {DATA_METADATA.get('size', 0):,} bytes\n"
                f"• 📝 **Format:** {DATA_METADATA.get('format', 'text')}\n"
                f"• ⏰ **Last Updated:** {DATA_METADATA.get('last_updated', 'Never')}\n"
                f"• 📜 **History Entries:** {len(DATA_HISTORY)}\n"
                f"• 👤 **Author:** {DATA_METADATA.get('author', 'Not specified')}\n"
                f"• 👁️ **Total Views:** {DATA_METADATA.get('views', 0)}\n\n"
                f"🔗 **RAW URL:** `{RAW_URL}`"
            )
            
            await query.edit_message_text(stats_text, parse_mode="Markdown", disable_web_page_preview=True)
        
        elif query.data == "history":
            if DATA_HISTORY:
                history_text = "📜 **Last 10 Updates:**\n\n"
                for i, entry in enumerate(reversed(DATA_HISTORY), 1):
                    history_text += f"**{i}. {entry['timestamp']}**\n"
                    history_text += f"   📏 Size: {entry['size']:,} bytes\n"
                    history_text += f"   📄 Preview: {entry['data'][:50]}...\n\n"
            else:
                history_text = "📭 No history available yet. Update some data first!"
            
            await query.edit_message_text(history_text, parse_mode="Markdown")
        
        elif query.data == "help":
            help_text = (
                "❓ **Help Guide**\n\n"
                "**Commands:**\n"
                "/start - Show main menu\n"
                "/cancel - Cancel current operation\n"
                "/link - Get all RAW links\n"
                "/stats - View statistics\n"
                "/clear - Clear all data\n"
                "/health - Check server status\n\n"
                "**Features:**\n"
                "• 📝 Store any text/data permanently\n"
                "• 🔗 Public RAW URL for sharing\n"
                "• 📊 Multiple format outputs (JSON, Text, HTML)\n"
                "• 📜 Data history tracking\n"
                "• 📈 Real-time statistics\n"
            )
            
            if is_public_url(PUBLIC_URL):
                help_text += "• 🌐 Beautiful web interface\n\n"
            else:
                help_text += "\n"
            
            help_text += (
                "**Tips:**\n"
                "• Use inline keyboard for easy navigation\n"
                "• Links work in any browser\n"
                "• No size limits (within reason)\n"
                "• Data persists until cleared\n\n"
                "**Need Help?**\nContact the bot admin"
            )
            
            await query.edit_message_text(help_text, parse_mode="Markdown")
        
        elif query.data == "menu":
            # Return to main menu
            keyboard = [
                [
                    InlineKeyboardButton("📝 Update Data", callback_data="update_data"),
                    InlineKeyboardButton("📊 View Data", callback_data="view_data")
                ],
                [
                    InlineKeyboardButton("🔗 Get Raw Link", callback_data="get_link"),
                    InlineKeyboardButton("📈 Statistics", callback_data="stats")
                ],
                [
                    InlineKeyboardButton("❓ Help", callback_data="help"),
                    InlineKeyboardButton("🔄 History", callback_data="history")
                ]
            ]
            
            # Only add web interface button if URL is public
            if is_public_url(PUBLIC_URL):
                keyboard.append([
                    InlineKeyboardButton("🌐 Web Interface", url=PUBLIC_URL)
                ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "📋 **Main Menu**\n\n"
                "Select an option:",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )

    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user messages"""
        user_id = update.effective_user.id
        
        if user_id in user_sessions and user_sessions[user_id].get("waiting_for_data"):
            # User is sending data to store
            text = update.message.text
            
            if text == "/cancel":
                user_sessions[user_id]["waiting_for_data"] = False
                await update.message.reply_text("❌ Operation cancelled.")
                return
            
            # Send data to server with safe headers
            headers = {
                "X-Author": safe_encode_header(update.effective_user.first_name),
                "Content-Type": "text/plain; charset=utf-8"
            }
            
            try:
                # Use localhost for internal communication
                internal_url = f"http://localhost:{PORT}/raw"
                response = requests.post(internal_url, data=text.encode("utf-8"), headers=headers)
                
                if response.status_code == 200:
                    # Success
                    user_sessions[user_id]["waiting_for_data"] = False
                    
                    response_data = response.json()
                    
                    # Create keyboard dynamically
                    keyboard = [
                        [
                            InlineKeyboardButton("🔗 Get Links", callback_data="get_link"),
                            InlineKeyboardButton("📊 View Stats", callback_data="stats")
                        ],
                        [
                            InlineKeyboardButton("📄 View Data", callback_data="view_data"),
                            InlineKeyboardButton("🔄 Update Again", callback_data="update_data")
                        ]
                    ]
                    
                    # Only add web interface button if URL is public
                    if is_public_url(PUBLIC_URL):
                        keyboard.append([
                            InlineKeyboardButton("🌐 Web Interface", url=PUBLIC_URL)
                        ])
                    
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    success_message = (
                        "✅ **Data stored successfully!** 🎉\n\n"
                        f"📏 **Size:** {len(text):,} bytes\n"
                        f"📝 **Format:** {detect_format(text)}\n"
                        f"⏰ **Timestamp:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"🔗 **URL:** `{RAW_URL}`\n\n"
                    )
                    
                    if not is_public_url(PUBLIC_URL):
                        success_message += "💡 *Note: Web interface requires public URL (deploy to Render/Heroku)*\n\n"
                    
                    success_message += "💡 *Choose your next action:*"
                    
                    await update.message.reply_text(
                        success_message,
                        reply_markup=reply_markup,
                        parse_mode="Markdown"
                    )
                else:
                    await update.message.reply_text(
                        f"❌ **Error storing data!**\n"
                        f"Status Code: {response.status_code}\n"
                        f"Error: {response.text}",
                        parse_mode="Markdown"
                    )
            except Exception as e:
                await update.message.reply_text(
                    f"❌ **Connection Error!**\n"
                    f"Error: {str(e)}\n\n"
                    f"Make sure the server is running on port {PORT}.",
                    parse_mode="Markdown"
                )
        else:
            # Regular message - show main menu
            keyboard = [[InlineKeyboardButton("📋 Main Menu", callback_data="menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "🤖 **RAW Data Bot**\n\n"
                "Type /start to begin or use the button below:",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )

    async def link_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Direct link command"""
        message_text = f"🔗 **Available Links:**\n\n📄 **RAW Text:** `{RAW_URL}`\n📊 **JSON View:** `{RAW_URL}?format=json`\n"
        
        if is_public_url(PUBLIC_URL):
            message_text += f"🌐 **Web Interface:** `{PUBLIC_URL}`\n📊 **Statistics:** `{PUBLIC_URL}/stats`\n\n"
        else:
            message_text += "\n"
        
        message_text += "💡 *Click or copy to access your data!*"
        
        await update.message.reply_text(
            message_text,
            parse_mode="Markdown"
        )

    async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Direct stats command"""
        stats_text = (
            f"📊 **Current Statistics:**\n\n"
            f"• 📏 **Data Size:** {len(SAVED_DATA):,} bytes\n"
            f"• 📝 **Format:** {DATA_METADATA.get('format', 'text')}\n"
            f"• ⏰ **Last Updated:** {DATA_METADATA.get('last_updated', 'Never')}\n"
            f"• 📦 **Storage:** {'📭 Empty' if not SAVED_DATA else '✅ Contains data'}\n"
            f"• 📜 **History:** {len(DATA_HISTORY)} past entries\n"
            f"• 👁️ **Views:** {DATA_METADATA.get('views', 0)}\n\n"
            f"🔗 **RAW URL:** `{RAW_URL}`"
        )
        
        if is_public_url(PUBLIC_URL):
            stats_text += f"\n🌐 **Web:** `{PUBLIC_URL}`"
        
        await update.message.reply_text(stats_text, parse_mode="Markdown", disable_web_page_preview=True)

    async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Clear all data with confirmation"""
        user_id = update.effective_user.id
        
        if user_id not in user_sessions:
            user_sessions[user_id] = {"confirm_clear": True}
        else:
            user_sessions[user_id]["confirm_clear"] = True
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes, Clear All", callback_data="confirm_clear"),
                InlineKeyboardButton("❌ No, Cancel", callback_data="cancel_clear")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "⚠️ **Warning: This will clear ALL stored data!**\n\n"
            f"📏 Current size: {len(SAVED_DATA):,} bytes\n"
            f"📜 History entries: {len(DATA_HISTORY)}\n\n"
            "Are you sure you want to continue?",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Health check command"""
        health_status = {
            "bot": "✅ Running",
            "server": "✅ Running" if SAVED_DATA is not None else "⚠️ Unknown",
            "data": f"✅ {len(SAVED_DATA):,} bytes" if SAVED_DATA else "📭 Empty",
            "history": f"📜 {len(DATA_HISTORY)} entries",
            "uptime": time.strftime("%Y-%m-%d %H:%M:%S"),
            "public_url": "✅ Available" if is_public_url(PUBLIC_URL) else "⚠️ Local only"
        }
        
        health_text = "🏥 **Health Check:**\n\n"
        for key, value in health_status.items():
            health_text += f"• **{key.title()}:** {value}\n"
        
        health_text += f"\n🔗 **Server:** {PUBLIC_URL}"
        
        await update.message.reply_text(health_text, parse_mode="Markdown")

    async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel current operation"""
        user_id = update.effective_user.id
        if user_id in user_sessions:
            user_sessions[user_id]["waiting_for_data"] = False
            user_sessions[user_id].pop("confirm_clear", None)
        await update.message.reply_text("❌ Current operation cancelled.")

    async def clear_confirmation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle clear confirmation"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "confirm_clear":
            global SAVED_DATA, DATA_METADATA, DATA_HISTORY
            
            # Save to history before clearing
            if SAVED_DATA:
                DATA_HISTORY.append({
                    "data": "[CLEARED BY USER]",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "size": 0,
                    "action": "cleared"
                })
            
            old_size = len(SAVED_DATA)
            SAVED_DATA = ""
            DATA_METADATA = {
                "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
                "size": 0,
                "format": "empty",
                "author": "",
                "views": 0
            }
            
            await query.edit_message_text(
                f"🗑️ **All data cleared successfully!**\n\n"
                f"📏 Cleared: {old_size:,} bytes\n"
                f"⏰ Time: {time.strftime('%H:%M:%S')}\n\n"
                f"💡 *Use /start to store new data.*",
                parse_mode="Markdown"
            )
        
        elif query.data == "cancel_clear":
            await query.edit_message_text("❌ Clear operation cancelled.")

    def run_bot():
        """Run the enhanced Telegram bot"""
        app_ = ApplicationBuilder().token(BOT_TOKEN).build()
        
        # Command handlers
        app_.add_handler(CommandHandler("start", start))
        app_.add_handler(CommandHandler("link", link_command))
        app_.add_handler(CommandHandler("stats", stats_command))
        app_.add_handler(CommandHandler("clear", clear_command))
        app_.add_handler(CommandHandler("health", health_command))
        app_.add_handler(CommandHandler("cancel", cancel_command))
        
        # Callback query handlers
        app_.add_handler(CallbackQueryHandler(button_handler, pattern="^(update_data|view_data|get_link|stats|help|history|menu)$"))
        app_.add_handler(CallbackQueryHandler(clear_confirmation_handler, pattern="^(confirm_clear|cancel_clear)$"))
        
        # Message handler
        app_.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        print("🤖 Telegram Bot Starting...")
        app_.run_polling()

# ========================
# MAIN ENTRY POINT
# ========================
if __name__ == "__main__":
    print("🚀 Starting RAW Data Service...")
    print("=" * 50)
    
    # Start server in background thread
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()
    
    # Give server time to start
    print("⏳ Waiting for server to start...")
    time.sleep(2)
    
    # Start bot if available
    if TELEGRAM_AVAILABLE and BOT_TOKEN and BOT_TOKEN != "8419010897:AAFBf7NBkWcDk9JYvCCUsjyQpFy6RqW3Ozg":
        try:
            bot_thread = threading.Thread(target=run_bot)
            bot_thread.daemon = True
            bot_thread.start()
            print("✅ Telegram bot started successfully!")
        except Exception as e:
            print(f"❌ Failed to start Telegram bot: {e}")
            print("ℹ️  Web interface and API are still available")
    elif TELEGRAM_AVAILABLE:
        print("⚠️  Telegram bot token not configured. Using default token for local testing.")
        try:
            bot_thread = threading.Thread(target=run_bot)
            bot_thread.daemon = True
            bot_thread.start()
            print("✅ Telegram bot started with default token (local testing only)")
        except Exception as e:
            print(f"❌ Failed to start Telegram bot: {e}")
    else:
        print("ℹ️  Telegram bot not available. Web interface and API are running.")
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")