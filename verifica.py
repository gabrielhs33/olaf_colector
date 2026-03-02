import os
import json
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from yt_dlp import YoutubeDL
from Olaf import Olaf, OlafCommand
import re
import unicodedata
import time
import random
import subprocess
import tempfile
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC



GOOGLE_EMAIL = "goodcollector33@gmail.com"
GOOGLE_SENHA = "sua_senha"
PERFIL_DIR   = "/tmp/chrome_persona"

# =====================================

MUSICS_FOLDER     = "musics"
JSON_FOLDER       = "youtube_videos_collection"
OUTPUT_FOLDER     = "new_youtube_collection"
CSV_FILE          = "resultados.csv"
TMP_FOLDER        = "tmp"
CHECKPOINT_FILE   = "checkpoint.json"
MAX_WORKERS       = 3

os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(TMP_FOLDER, exist_ok=True)
os.makedirs(PERFIL_DIR, exist_ok=True)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/537.36 Chrome/118.0.0.0 Safari/537.36",
]

# ─────────────────────────────────────────────
# AUTENTICAÇÃO VIA SELENIUM
# ─────────────────────────────────────────────

_cookies_autenticados = None   # cache global para reusar cookies na sessão

def criar_driver():
    opts = Options()
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1280,800")
    opts.add_argument(f"--user-data-dir={PERFIL_DIR}")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    for binary in ["chromium-browser", "google-chrome", "chromium"]:
        if os.path.exists(f"/usr/bin/{binary}"):
            opts.binary_location = f"/usr/bin/{binary}"
            break
    driver = webdriver.Chrome(options=opts)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def ja_esta_logado(driver):
    driver.get("https://www.youtube.com")
    time.sleep(4)
    cookies = driver.get_cookies()
    auth = ["SID", "SAPISID", "__Secure-3PSID", "SIDCC"]
    return any(c["name"] in auth for c in cookies), cookies

def fazer_login(driver):
    wait = WebDriverWait(driver, 30)
    driver.get("https://accounts.google.com/ServiceLogin?service=youtube&hl=en")
    time.sleep(3)

    wait.until(EC.presence_of_element_located((By.ID, "identifierId")))
    driver.find_element(By.ID, "identifierId").send_keys(GOOGLE_EMAIL)
    driver.find_element(By.ID, "identifierNext").click()
    time.sleep(3)

    wait.until(EC.presence_of_element_located((By.NAME, "Passwd")))
    driver.find_element(By.NAME, "Passwd").send_keys(GOOGLE_SENHA)
    driver.find_element(By.ID, "passwordNext").click()
    time.sleep(8)

    if "challenge/selection" in driver.current_url:
        print("   Tela de seleção — clicando em SMS...")
        try:
            driver.find_element(By.XPATH,
                "//*[contains(text(), 'Get a verification code') or contains(text(), 'verification code')]").click()
            time.sleep(4)
        except Exception as e:
            print(f"   Erro seleção: {e}")

    if "challenge" in driver.current_url:
        print("\n📱 Digite o código SMS recebido no celular:\n")
        codigo = input("   Código SMS: ").strip()
        try:
            campo = driver.find_element(By.CSS_SELECTOR,
                "input[type='tel'], input[name='code'], input[id='idvPin'], input[type='number']")
            campo.clear()
            campo.send_keys(codigo)
            time.sleep(1)
            driver.find_element(By.XPATH,
                "//button[contains(., 'Next') or contains(., 'Verify')]").click()
            time.sleep(6)
        except Exception as e:
            print(f"   Erro código: {e}")
            return False

    return "challenge" not in driver.current_url

def cookies_para_arquivo(cookies):
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    tmp.write("# Netscape HTTP Cookie File\n")
    for c in cookies:
        domain      = c.get("domain", ".youtube.com")
        secure      = "TRUE" if c.get("secure") else "FALSE"
        expiry      = str(int(c.get("expiry", 2147483647)))
        path        = c.get("path", "/")
        domain_flag = "TRUE" if domain.startswith(".") else "FALSE"
        httponly    = "#HttpOnly_" if c.get("httpOnly") else ""
        tmp.write(f"{httponly}{domain}\t{domain_flag}\t{path}\t{secure}\t{expiry}\t{c['name']}\t{c['value']}\n")
    tmp.close()
    return tmp.name

def autenticar():
    """
    Retorna um arquivo temporário de cookies autenticados.
    Reutiliza sessão salva em PERFIL_DIR se ainda válida.
    Pede SMS apenas se necessário.
    """
    global _cookies_autenticados

    # Reutiliza cookies já obtidos nesta sessão
    if _cookies_autenticados:
        return cookies_para_arquivo(_cookies_autenticados)

    driver = criar_driver()
    try:
        logado, cookies = ja_esta_logado(driver)
        if logado:
            print("   ✅ Sessão salva ainda ativa.")
        else:
            print("   Sessão expirada — fazendo login...")
            ok = fazer_login(driver)
            if not ok:
                print("   ⚠️  Login não completou.")
                return None
            driver.get("https://www.youtube.com")
            time.sleep(3)
            cookies = driver.get_cookies()

        auth = ["SID", "SAPISID", "__Secure-3PSID", "SIDCC"]
        encontrados = [c["name"] for c in cookies if c["name"] in auth]
        print(f"   Cookies de auth: {encontrados}")

        _cookies_autenticados = cookies
        return cookies_para_arquivo(cookies)

    finally:
        driver.quit()

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def normaliza_nome(name):
    if name.lower().endswith(".mp3"):
        name = name[:-4]
    name = name.replace(" ", "_")
    name = re.sub(r'[\\\/\:\*\?\"\<\>\|]', '', name)
    name = ''.join(ch for ch in name if unicodedata.category(ch)[0] != "C")
    if not name.strip("_"):
        return "untitled"
    if name.endswith("."):
        name = name[:-1]
    return name or "untitled"

def ydl_opts_base(output_path):
    return {
        'format': 'bestaudio/best',
        'outtmpl': output_path,
        'quiet': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'retries': 3,
        'sleep_interval': 2,
        'max_sleep_interval': 5,
        'remote_components': ['ejs:github'],
        'ffmpeg_location': '/usr/bin',
        'http_headers': {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept-Language': 'en-US,en;q=0.9',
        },
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128',
        }]
    }

# ─────────────────────────────────────────────
# DOWNLOAD COM FALLBACK PARA AGE-GATE
# ─────────────────────────────────────────────

def baixar_e_verificar(short, musica_path):
    video_id = short["video_id"]
    output_path = os.path.join(TMP_FOLDER, f"{video_id}.%(ext)s")
    audio_path = os.path.join(TMP_FOLDER, f"{video_id}.mp3")

    time.sleep(random.uniform(2, 8))

    cookies_file = None

    try:
        # ── Tentativa 1: sem autenticação ────────────────────────
        opts = ydl_opts_base(output_path)
        try:
            with YoutubeDL(opts) as ydl:
                ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

        except Exception as e:
            erro = str(e).lower()

            # ── Fallback: age-gate detectado → autentica ─────────
            if any(k in erro for k in ["age", "sign in", "restricted", "login", "403", "401"]):
                print(f"\n🔞 Age-gate em {video_id} — autenticando...")
                cookies_file = autenticar()

                if not cookies_file:
                    print(f"   ⚠️  Autenticação falhou para {video_id}")
                    return False, short

                opts_auth = ydl_opts_base(output_path)
                opts_auth['cookiefile'] = cookies_file

                with YoutubeDL(opts_auth) as ydl:
                    ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

            else:
                # Outros erros (429, rede, etc.)
                if any(k in erro for k in ["429", "too many"]):
                    print(f"   Rate limit — aguardando 60s...")
                    time.sleep(random.uniform(30, 60))
                raise

        # ── Verifica com Olaf ─────────────────────────────────────
        achou = Olaf(OlafCommand.QUERY, audio_path).do()
        return achou, short

    except Exception as e:
        print(f"Erro em {video_id}: {str(e)[:80]}")
        return False, short

    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)
        if cookies_file and os.path.exists(cookies_file):
            os.unlink(cookies_file)

# ─────────────────────────────────────────────
# AUTENTICAÇÃO INICIAL (ao iniciar o script)
# ─────────────────────────────────────────────

print("=" * 50)
print("  INICIANDO — verificando autenticação")
print("=" * 50)
cookies_iniciais = autenticar()
if cookies_iniciais:
    os.unlink(cookies_iniciais)   # só verificou, descarta
    print("✅ Autenticação OK — iniciando coleta\n")
else:
    print("⚠️  Autenticação falhou — vídeos com age-gate serão pulados\n")

# ─────────────────────────────────────────────
# PROCESSAMENTO PRINCIPAL
# ─────────────────────────────────────────────

if not os.path.exists(CSV_FILE):
    pd.DataFrame(columns=["song", "video_quantity", "video_with_song"]).to_csv(CSV_FILE, index=False)

if os.path.exists(CHECKPOINT_FILE):
    with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
        checkpoint = json.load(f)
else:
    checkpoint = []

for musica in os.listdir(MUSICS_FOLDER):

    if not musica.endswith(".mp3"):
        continue

    if musica in checkpoint:
        print(f"  Pulando {musica}, já processada")
        continue

    print(f"\n Processando música: {musica}")

    musica_path = os.path.join(MUSICS_FOLDER, musica)
    musica_nome = normaliza_nome(musica)

    subprocess.run(["olaf", "clear", "-f"], capture_output=True)
    Olaf(OlafCommand.STORE, musica_path).do()

    videos_analisados = 0
    videos_com_musica = 0

    json_file = f"{musica_nome}.json"
    json_path = os.path.join(JSON_FOLDER, json_file)

    if not os.path.exists(json_path):
        print(f" JSON não encontrado para {musica}")
        continue

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    novos_shorts = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(baixar_e_verificar, short, musica_path)
            for short in data.get("shorts", [])
        ]
        for future in as_completed(futures):
            try:
                achou, short = future.result()
                videos_analisados += 1
                if achou:
                    videos_com_musica += 1
                    novos_shorts.append(short)
            except Exception as e:
                print(f"Erro em thread: {e}")

    novo_json_path = os.path.join(OUTPUT_FOLDER, json_file)
    with open(novo_json_path, "w", encoding="utf-8") as f:
        json.dump({"shorts": novos_shorts}, f, indent=4, ensure_ascii=False)

    df = pd.read_csv(CSV_FILE)
    df.loc[len(df)] = [musica, videos_analisados, videos_com_musica]
    df.to_csv(CSV_FILE, index=False)

    checkpoint.append(musica)
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, indent=4, ensure_ascii=False)

    print(f"Finalizado {musica}")
    print(f"   Vídeos analisados: {videos_analisados}")
    print(f"   Vídeos com música: {videos_com_musica}")

    time.sleep(random.uniform(20, 40))

print("\nProcessamento finalizado.")
