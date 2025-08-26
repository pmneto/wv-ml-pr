# - Limpa images/ só 1x por sessão em modo público
# - Upload via st.form (evita reset no rerun)
# - Normaliza extensão p/ .jpg ao salvar
# - Mantém saída flat em ./output
# - Ordem manual por lote (st.data_editor) + botão para aplicar prefixos

import os
import io
import re
import sys
import shutil
import zipfile
import subprocess
from pathlib import Path
from typing import List
import re
import shutil


import streamlit as st
import pandas as pd
from PIL import Image

# Config & paths

PREFIX_RE = re.compile(r"^\d+_")
NAT_RE = re.compile(r"\d+|\D+")
MAX_PAGES_PER_RUN = 10  # limite máximo



ROOT = Path(__file__).resolve().parent
IMAGES_DIR = ROOT / "images"
OUTPUT_DIR = ROOT / "output"
LOGS_DIR = ROOT / "logs"
IMAGES_DIR.mkdir(exist_ok=True, parents=True)
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)
LOGS_DIR.mkdir(exist_ok=True, parents=True)

APP_MODE = os.getenv("APP_MODE", "public").lower()  # "local" ou "public"
MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", "10"))

st.set_page_config(page_title="Digitalizador de Documentos (Azure → OpenAI)", page_icon="🤖", layout="wide")

# Saneamento de nome
SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9_\-]")

def sanitize_name(name: str) -> str:
    name = name.strip().replace(" ", "_")
    name = SAFE_NAME_RE.sub("", name)
    return name[:64] if name else ""

# Lotes (images/<lote>/)
def ensure_lote_dir(lote: str) -> Path:
    p = IMAGES_DIR / lote
    p.mkdir(parents=True, exist_ok=True)
    return p

def list_lotes() -> List[str]:
    return sorted([p.name for p in IMAGES_DIR.iterdir() if p.is_dir()])


def _natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in NAT_RE.findall(s)]

def list_images(lote: str) -> List[Path]:
    p = IMAGES_DIR / lote
    if not p.exists():
        return []
    imgs = [f for f in p.iterdir() if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg"}]
    imgs = [f for f in imgs if not f.name.startswith("__tmp__")]  # <<< evita meio-termo da renomeação
    return sorted(imgs, key=lambda f: _natural_key(f.name))

def save_uploads(lote: str, files):
    dest = ensure_lote_dir(lote)
    saved = 0
    for f in files:
        try:
            size_ok = getattr(f, "size", None)
            if size_ok is not None and size_ok > MAX_FILE_MB * 1024 * 1024:
                st.warning(f"'{f.name}' ignorado: excede {MAX_FILE_MB} MB.")
                continue
            img = Image.open(f).convert("RGB")
            out_name = Path(f.name).with_suffix(".jpg").name  # normaliza extensão
            img.save(dest / out_name, format="JPEG", quality=95)
            saved += 1
        except Exception as e:
            st.error(f"Falha ao processar '{getattr(f, 'name', 'arquivo')}': {e}")
    return saved

# Output (flat em ./output)
def list_outputs_for_lote(lote: str) -> List[Path]:
    if not OUTPUT_DIR.exists():
        return []
    # Heurística: arquivos de saída que CONTÊM o nome do lote
    return sorted([p for p in OUTPUT_DIR.iterdir() if p.is_file() and lote.lower() in p.name.lower()])

def zip_outputs(files: List[Path]) -> bytes:
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in files:
            zf.write(p, arcname=p.name)
    mem.seek(0)
    return mem.read()

# Execução do main.py com logs
def run_main(lote: str, mode_label: str, lang_label: str) -> int:
    """
    Executa main.py como subprocesso, streamando logs na UI.
    Retorna o returncode.
    """
    # mapeia labels -> valores esperados pelo back
    mode_map = {"Impresso": "printed", "Manuscrito": "handwritten"}
    lang_map = {"Português 🇧🇷": "por", "Inglês 🇺🇸": "eng", "Espanhol 🇪🇸": "spa", "Francês 🇫🇷": "fra"}
    mode = mode_map.get(mode_label, "printed")
    lang = lang_map.get(lang_label, "por")

    input_dir = IMAGES_DIR / lote
    output_dir = OUTPUT_DIR  # flat
    cmd = [
        sys.executable, str(ROOT / "main.py"),
        "--input-dir", str(input_dir),
        "--output-dir", str(output_dir),
        "--mode", mode,
        "--lang", lang,
    ]

    log_box = st.empty()
    progress = st.progress(0, text="⏳ Executando pipeline...")

    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
        )
    except Exception as e:
        progress.empty()
        st.error(f"Não foi possível iniciar o processo: {e}")
        return 1

    full_log = []
    i = 0
    while True:
        line = proc.stdout.readline()
        if not line and proc.poll() is not None:
            break
        if line:
            full_log.append(line.rstrip())
            log_box.code("\n".join(full_log[-80:]), language="bash")
        # avança barra fake
        i = (i + 5) % 105
        progress.progress(min(i, 100), text="⏳ Executando pipeline...")

    returncode = proc.wait()
    progress.empty()

    if returncode == 0:
        st.success("Processamento concluído.")
    else:
        st.error(f"Falha no processamento (return code {returncode}).")

    # salva log em logs/ com prefixo do lote
    try:
        (LOGS_DIR / f"{lote}_run.log").write_text("\n".join(full_log), encoding="utf-8")
    except Exception as e:
        st.warning(f"Não consegui salvar log: {e}")

    return returncode

# Limpeza automática (inputs) — one-shot por sessão
if "did_wipe" not in st.session_state:
    st.session_state.did_wipe = False
if "did_wipe_outputs" not in st.session_state:
    st.session_state.did_wipe_outputs = False

def wipe_inputs_if_public_once():
    if APP_MODE != "local" and not st.session_state.did_wipe:
        try:
            if IMAGES_DIR.exists():
                shutil.rmtree(IMAGES_DIR, ignore_errors=True)
            IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            st.sidebar.warning("Modo público: dados limpos no primeiro carregamento desta sessão.")
            st.session_state.did_wipe = True
        except Exception as e:
            st.sidebar.error(f"Erro ao limpar 'images/': {e}")

def wipe_outputs_if_public_once():
    if APP_MODE != "local" and not st.session_state.get("did_wipe_outputs", False):
        try:
            if OUTPUT_DIR.exists():
                shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            st.sidebar.warning("Modo público: output/ limpo no primeiro carregamento desta sessão.")
            st.session_state.did_wipe_outputs = True
        except Exception as e:
            st.sidebar.error(f"Erro ao limpar output/: {e}")

def wipe_inputs_now():
    try:
        if IMAGES_DIR.exists():
            shutil.rmtree(IMAGES_DIR, ignore_errors=True)
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        st.sidebar.success("Diretório 'images/' limpo agora.")
    except Exception as e:
        st.sidebar.error(f"Erro ao limpar 'images/': {e}")

def wipe_outputs_now():
    """Limpa output/ sob comando do usuário (botão)."""
    try:
        shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        st.sidebar.success("Output limpo com sucesso.")
    except Exception as e:
        st.sidebar.error(f"Erro ao limpar output/: {e}")

# ---- helpers de ordem manual ----
def get_order_state_key(lote: str) -> str:
    return f"order_df__{lote}"

def ensure_order_state(lote: str, imgs: list[Path]) -> pd.DataFrame:
    key = get_order_state_key(lote)
    if key not in st.session_state:
        st.session_state[key] = pd.DataFrame({
            "arquivo": [p.name for p in imgs],
            "ordem": list(range(1, len(imgs) + 1))
        })
    else:
        # adiciona novas imagens ao DF com ordem ao final
        known = set(st.session_state[key]["arquivo"].tolist())
        for p in imgs:
            if p.name not in known:
                st.session_state[key] = pd.concat(
                    [st.session_state[key], pd.DataFrame([{
                        "arquivo": p.name,
                        "ordem": len(st.session_state[key]) + 1
                    }])],
                    ignore_index=True
                )
    return st.session_state[key]



def apply_prefix_order(lote: str, df: pd.DataFrame):
    base = IMAGES_DIR / lote
    df_sorted = df.sort_values("ordem").reset_index(drop=True)
    width = max(3, len(str(len(df_sorted))))

    temp_norm = []
    for row in df_sorted.itertuples(index=False):
        src = base / row.arquivo
        if not src.exists():
            continue
        clean_name = PREFIX_RE.sub("", src.name)
        tmp = base / f"__tmp__{clean_name}"
        src.rename(tmp)
        temp_norm.append((tmp, clean_name))

    new_names = []
    for i, (tmp, clean_name) in enumerate(temp_norm):
        prefix = str(i + 1).zfill(width)
        dst = base / f"{prefix}_{clean_name}"
        tmp.rename(dst)
        new_names.append(dst.name)

    # Atualiza a ordem no estado para os NOVOS nomes (1..N)
    order_key = get_order_state_key(lote)
    st.session_state[order_key] = pd.DataFrame({
        "arquivo": new_names,
        "ordem": list(range(1, len(new_names) + 1))
    })







# UI
st.sidebar.header("Sessão & Segurança")
st.sidebar.caption("LGPD: por padrão **nada é persistido** em modo público, tudo é excluído no load da sessão.")
if st.sidebar.button("❌ Limpar inputs agora"):
    wipe_inputs_now()
if st.sidebar.button("🗑️ Limpar outputs agora"):
    wipe_outputs_now()

st.title("📝 🔍 Digitalizador de Textos")
st.caption("Organize suas imagens e envie para digitalização, execute o processo e baixe os resultados.")

# limpeza automática: apenas 1x por sessão quando público
wipe_inputs_if_public_once()
wipe_outputs_if_public_once()

colA, colB = st.columns([1.2, 1], gap="large")

with colA:
    st.subheader("1) Criar lote")
    lote_name = st.text_input("Nome do lote", placeholder="ex.: caderno_01_assembleia", key="lote_name_in")
    lote_name = sanitize_name(lote_name)
    if st.button("Criar lote", key="btn_create_lote") and lote_name:
        ensure_lote_dir(lote_name)
        st.success(f"Lote criado: {lote_name}")

    st.subheader("2) Upload de imagens para o lote")
    lotes = list_lotes()
    if not lotes:
        st.info("Crie um lote primeiro.")
    else:
        lote_up = st.selectbox("Escolha o lote para upload", options=lotes, key="lote_up")
        # usa form para evitar rerun no meio do upload
        with st.form("upload_form", clear_on_submit=True):
            files = st.file_uploader(
                "Envie PNG/JPG (múltiplos)",
                type=["png", "jpg", "jpeg"],
                accept_multiple_files=True,
                key="uploader_files",
            )
            submitted = st.form_submit_button("Enviar para o lote selecionado")
        if submitted:
            if not files:
                st.warning("Selecione ao menos uma imagem.")
            else:
                saved = save_uploads(lote_up, files)
                st.success(f"{saved} arquivo(s) enviado(s) para {lote_up}.")

    st.subheader("3) Gerenciar lotes")
    lotes = list_lotes()
    if lotes:
        lote_mng = st.selectbox("Selecione um lote", options=lotes, key="lote_mng")
        imgs = list_images(lote_mng)
        st.write(f"**{len(imgs)}** imagem(ns) em `{lote_mng}`")

        # ======= ORDEM MANUAL =======
        st.markdown("**Ordem manual (edite a coluna e salve):**")
        order_df = ensure_order_state(lote_mng, imgs)
        edited = st.data_editor(
            order_df,
            column_config={
                "arquivo": st.column_config.TextColumn("Arquivo", disabled=True),
                "ordem": st.column_config.NumberColumn("Ordem", min_value=1, step=1),
            },
            num_rows="fixed",
            use_container_width=True,
            key=f"editor__{lote_mng}"
        )

        col_ord_a, col_ord_b, col_ord_c = st.columns([1,1,2])
        with col_ord_a:
            if st.button("💾 Salvar ordem", key=f"btn_save_order__{lote_mng}"):
                ords = edited["ordem"].tolist()
                if len(ords) != len(set(ords)):
                    st.error("A coluna 'Ordem' não pode ter números repetidos.")
                else:
                    edited = edited.sort_values("ordem").reset_index(drop=True)
                    st.session_state[get_order_state_key(lote_mng)] = edited
                    st.success("Ordem salva nesta sessão.")
        with col_ord_b:
            if st.button("✅ Aplicar ordem (prefixos)", key=f"btn_apply_prefix__{lote_mng}"):
                df_current = st.session_state.get(get_order_state_key(lote_mng))
                if df_current is None or df_current.empty:
                    st.error("Defina a ordem primeiro.")
                else:
                    apply_prefix_order(lote_mng, df_current)
                    st.success("Arquivos renomeados com prefixos numéricos.")
                    st.rerun()  # <<< força recarregar com os novos caminhos

        # aplica ordem manual somente para PREVIEW
        name_to_order = {r.arquivo: r.ordem for r in st.session_state[get_order_state_key(lote_mng)].itertuples()}
        imgs_sorted = sorted(imgs, key=lambda p: name_to_order.get(p.name, 9999))

        grid = st.columns(4)
        for i, p in enumerate(imgs_sorted):
            with grid[i % 4]:
                ord_lbl = name_to_order.get(p.name, "?")
                st.image(str(p), caption=f"{ord_lbl}. {p.name}", use_container_width=True)

        # ======= AÇÕES DO LOTE (inline) =======
        colm1, colm2, colm3 = st.columns([3,1,1])
        new_name = colm1.text_input("Renomear lote para", value=f"{lote_mng}_v2", key="new_name_in")
        if colm2.button("✏️ Renomear", key="btn_ren", use_container_width=True):
            nn = sanitize_name(new_name)
            if nn and nn != lote_mng:
                try:
                    (IMAGES_DIR / lote_mng).rename(IMAGES_DIR / nn)
                    st.success(f"Renomeado para {nn}. Atualize a seleção acima.")
                except Exception as e:
                    st.error(f"Falha ao renomear: {e}")
        if colm3.button("🗑️ Apagar", key="btn_del", use_container_width=True):
            shutil.rmtree(IMAGES_DIR / lote_mng, ignore_errors=True)
            st.error(f"Lote '{lote_mng}' apagado de images/. Saídas em output/ foram mantidas.")

with colB:
    st.subheader("4) Processar lote")
    lotes = list_lotes()
    if not lotes:
        st.info("Crie um lote com imagens para processar.")
    else:
        lote_run = st.selectbox("Lote para processar", options=lotes, key="lote_run")
        mode_label = st.selectbox("Tipo de Documento", ["Impresso", "Manuscrito"], index=0, key="mode_sel")
        lang_label = st.selectbox("Idioma", ["Português 🇧🇷", "Inglês 🇺🇸", "Espanhol 🇪🇸", "Francês 🇫🇷"], index=0, key="lang_sel")

        # NOVO: seleção de ordenação
        order_choice = st.radio(
            "Ordenar páginas por:",
            ["Nome (prefixo 001_...)", "Data de modificação", "Data de criação"],
            index=0,
            key="order_choice"
        )
        order_map = {
            "Nome (prefixo 001_...)": "name",
            "Data de modificação ": "mtime",
            "Data de criação": "ctime"
        }

        if st.button("Processar ✅", key="btn_run"):
            if len(list_images(lote_run)) == 0:
                st.error("Este lote não possui imagens.")
            else:
                images = list_images(lote_run)
                if len(images) > MAX_PAGES_PER_RUN:
                    st.error(f"🚨 Limite de {MAX_PAGES_PER_RUN} páginas por execução. "
                            "Quer testar mais? Fale comigo 😉")
                else:
                    rc = run_main(lote_run, mode_label, lang_label)
                    if rc == 0:
                       st.balloons()


    st.subheader("5) Resultados")
    if OUTPUT_DIR.exists():
        lotes_for_dl = list_lotes()
        if lotes_for_dl:
            lote_dl = st.selectbox("Filtrar saídas pelo lote", options=lotes_for_dl, key="lote_dl")
            outs = list_outputs_for_lote(lote_dl)
            if not outs:
                st.info(f"Nenhum arquivo em '{lote_dl}'. ")
            else:
                st.write(f"Arquivos gerados para o lote **{lote_dl}**:")
                for p in outs:
                    try:
                        with open(p, "rb") as f:
                            st.download_button(f"⬇️ {p.name}", f.read(), file_name=p.name)
                    except Exception as e:
                        st.error(f"Falha ao preparar download de {p.name}: {e}")
                if st.button("📦 Baixar tudo (ZIP)", key="btn_zip"):
                    data = zip_outputs(outs)
                    st.download_button("Download ZIP", data, file_name=f"{lote_dl}_outputs.zip", mime="application/zip")
    else:
        st.info("Pasta output/ ainda vazia.")
