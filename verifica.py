import os
import json
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from yt_dlp import YoutubeDL
from Olaf import Olaf, OlafCommand
import re, unicodedata

MUSICS_FOLDER = "musics"
JSON_FOLDER = "youtube_videos_collection"
OUTPUT_FOLDER = "new_youtube_collection"
CSV_FILE = "resultados.csv"
TMP_FOLDER = "tmp"
CHECKPOINT_FILE = "checkpoint.json"
MAX_WORKERS = 8  

os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(TMP_FOLDER, exist_ok=True)

# def normaliza_nome(nome):
#     nome = os.path.splitext(nome)[0]
#     nome = unicodedata.normalize('NFD', nome).encode('ascii','ignore').decode()
#     nome = re.sub(r"[().]", " ", nome)      
#     nome = nome.replace("&", "_")          
#     nome = re.sub(r"[^A-Za-z0-9\s_]", "", nome)  
#     nome = re.sub(r"\s+", "_", nome)        
#     return nome.strip("_")


def normaliza_nome(name):
    if name.lower().endswith(".mp3"):
        name = name[:-4]

    name = name.replace(" ", "_")

    forbidden = r'[\\\/\:\*\?\"\<\>\|]'
    name = re.sub(forbidden, '', name)

    name = ''.join(ch for ch in name if unicodedata.category(ch)[0] != "C")

    if not name.strip("_"):
        return "untitled"

    if name.endswith("."):
        name = name[:-1]

    if not name:
        return "untitled"

    return name


def baixar_e_verificar(short, musica_path):
    import time, random
    video_id = short["video_id"]
    output_path = os.path.join(TMP_FOLDER, f"{video_id}.%(ext)s")
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_path,
        'quiet': True,
        'cookiefile': 'cookies.txt',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128',
        }]
    }
    time.sleep(random.uniform(10, 90))
    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
        audio_path = output_path.replace("%(ext)s", "mp3")
        achou = Olaf(OlafCommand.QUERY, audio_path).do()
        os.remove(audio_path)  
        return achou, short
    except Exception as e:
        return False, short

# Inicializa CSV se não existir
if not os.path.exists(CSV_FILE):
    pd.DataFrame(columns=["song", "video_quantity", "video_with_song"]).to_csv(CSV_FILE, index=False)

# Inicializa checkpoint
if os.path.exists(CHECKPOINT_FILE):
    with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
        checkpoint = json.load(f)
else:
    checkpoint = []

for musica in os.listdir(MUSICS_FOLDER):
    if not musica.endswith(".mp3"):
        continue

    if musica in checkpoint:
        print(f"Pular {musica}, já processada anteriormente")
        continue

    musica_path = os.path.join(MUSICS_FOLDER, musica)
    musica_nome = normaliza_nome(musica)  

    Olaf(OlafCommand.STORE, musica_path).do()

    videos_analisados = 0
    videos_com_musica = 0

    json_file = f"{musica_nome}.json"
    json_path = os.path.join(JSON_FOLDER, json_file)

    if not os.path.exists(json_path):
        print(f"JSON {musica}nao encontrado")
        continue

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    novos_shorts = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(baixar_e_verificar, short, musica_path) for short in data.get("shorts", [])]

        for future in as_completed(futures):
            achou, short = future.result()
            videos_analisados += 1
            if achou:
                videos_com_musica += 1
                novos_shorts.append(short)


    novo_json_path = os.path.join(OUTPUT_FOLDER, json_file)
    with open(novo_json_path, "w", encoding="utf-8") as f:
        json.dump({"shorts": novos_shorts}, f, indent=4, ensure_ascii=False)


    df = pd.read_csv(CSV_FILE)
    df.loc[len(df)] = [musica, videos_analisados, videos_com_musica]
    df.to_csv(CSV_FILE, index=False)

    checkpoint.append(musica)
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, indent=4, ensure_ascii=False)


