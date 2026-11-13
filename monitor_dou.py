#!/usr/bin/env python3
"""
Leitor diário do Diário Oficial da União (DOU) focado em Reforma Tributária
e legislação tributária.

Baixa as edições do dia pelo INLABS (serviço oficial e gratuito da Imprensa
Nacional), lê cada ato em XML, filtra pelos termos/órgãos de termos.yaml e grava:

  dados/AAAA-MM-DD.json   -> todos os atos relevantes do dia (acumula entre execuções)
  dados/ultimos.json      -> atos dos últimos 15 dias (usado pela tarefa do Claude)
  boletins/AAAA-MM-DD.md  -> boletim legível do dia

Uso:
  INLABS_EMAIL=... INLABS_SENHA=... python monitor_dou.py            # hoje
  python monitor_dou.py --data 2026-11-13                             # outro dia
  python monitor_dou.py --pasta-xml ./zips                            # processar zips locais (teste)
"""
from __future__ import annotations

import argparse
import html
import io
import json
import os
import re
import sys
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
URL_LOGIN = "https://inlabs.in.gov.br/logar.php"
URL_DOWNLOAD = "https://inlabs.in.gov.br/index.php?p="
FUSO_BR = timezone(timedelta(hours=-3))  # Brasília (sem horário de verão desde 2019)
NIVEL_ORDEM = {"alta": 0, "media": 1, "baixa": 2}
NIVEL_NOME = {"alta": "Reforma Tributária", "media": "Tributário — normativo", "baixa": "Tributário — outros"}


# ----------------------------------------------------------------- utilidades
CONTEXTO_TRIB = re.compile(r"(?<![a-z])(imposto|contribuic|tribut|aliquota|fiscal|fiscais|bens e servicos|comite gestor)")

def normalizar(txt: str) -> str:
    """minúsculas, sem acento, 'nº 214' -> '214', espaços simples."""
    txt = unicodedata.normalize("NFKD", txt or "")
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    txt = txt.lower()
    # "nº 214" (NFKD vira "no 214"), "n° 214", "n.º 214" -> "214"
    txt = re.sub(r"\bn\s*[\.o°]{0,3}\s*(?=\d)", "", txt)
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip()


def compilar(termos: list[str]) -> list[tuple[str, re.Pattern]]:
    saida = []
    for t in termos or []:
        prefixo = t.endswith("*")
        base = normalizar(t.rstrip("*"))
        fim = "" if prefixo else r"(?![a-z0-9])"
        saida.append((t, re.compile(r"(?<![a-z0-9])" + re.escape(base) + fim)))
    return saida


def compilar_siglas(siglas: list[str]) -> list[tuple[str, re.Pattern]]:
    return [(s, re.compile(r"(?<![A-Za-z0-9])" + re.escape(s) + r"(?![A-Za-z0-9])")) for s in siglas or []]


def texto_limpo(fragmento_html: str) -> str:
    sem_tags = re.sub(r"<[^>]+>", " ", fragmento_html or "")
    return re.sub(r"\s+", " ", html.unescape(sem_tags)).strip()


def carregar_config() -> dict:
    import yaml  # pyyaml
    with open(RAIZ / "termos.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return {
        "secoes": cfg.get("secoes") or ["DO1", "DO1E"],
        "reforma": compilar(cfg.get("reforma")),
        "siglas": compilar_siglas(cfg.get("siglas_reforma")),
        "tributario": compilar(cfg.get("tributario")),
        "orgaos": [normalizar(o) for o in cfg.get("orgaos") or []],
        "tipos": [normalizar(t) for t in cfg.get("tipos_normativos") or []],
        "ruido": compilar(cfg.get("ruido")),
    }


# ----------------------------------------------------------------- download
def baixar_zips(data_iso: str, secoes: list[str]) -> dict[str, bytes]:
    import requests

    email, senha = os.environ.get("INLABS_EMAIL"), os.environ.get("INLABS_SENHA")
    if not email or not senha:
        raise RuntimeError("INLABS_EMAIL/INLABS_SENHA não definidos")

    s = requests.Session()
    for tentativa in range(3):
        try:
            s.post(URL_LOGIN, data={"email": email, "password": senha},
                   headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=60)
            break
        except requests.RequestException as e:
            print(f"Falha no login (tentativa {tentativa + 1}): {e}")
    cookie = s.cookies.get("inlabs_session_cookie")
    if not cookie:
        raise RuntimeError("login no INLABS falhou (serviço em manutenção ou e-mail/senha incorretos)")

    zips = {}
    for secao in secoes:
        nome = f"{data_iso}-{secao}.zip"
        url = f"{URL_DOWNLOAD}{data_iso}&dl={nome}"
        r = s.get(url, headers={"Cookie": f"inlabs_session_cookie={cookie}", "origem": "736372697074"}, timeout=180)
        if r.status_code == 200 and r.content[:2] == b"PK":
            zips[secao] = r.content
            print(f"Baixado {nome} ({len(r.content) // 1024} KB)")
        else:
            print(f"Sem arquivo {nome} (HTTP {r.status_code}) — normal se não houve edição.")
    return zips


URL_LEITURA = "https://www.in.gov.br/leiturajornal?data={data}&secao={secao}"
URL_ATO = "https://www.in.gov.br/web/dou/-/{slug}"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}


def parse_leitura(pagina_html: str, secao: str) -> list[dict]:
    """Extrai os atos do JSON embutido na página pública de leitura do DOU."""
    m = re.search(r'<script[^>]*id="params"[^>]*>(.*?)</script>', pagina_html, re.S)
    if not m:
        return []
    try:
        dados = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    atos = []
    for it in dados.get("jsonArray") or []:
        slug = it.get("urlTitle") or ""
        resumo = texto_limpo(it.get("content") or "")
        atos.append({
            "id": "web-" + (slug or str(it.get("classPK") or len(atos))),
            "secao": it.get("pubName") or secao.upper(),
            "data_publicacao": it.get("pubDate", ""),
            "edicao": str(it.get("editionNumber", "")),
            "pagina": str(it.get("numberPage", "")),
            "tipo": it.get("artType", ""),
            "orgao": it.get("hierarchyStr", ""),
            "titulo": texto_limpo(it.get("title") or it.get("titulo") or ""),
            "ementa": "",
            "texto": resumo,
            "url": URL_ATO.format(slug=slug) if slug else "",
        })
    return atos


def ler_pagina_publica(data_iso: str, secoes: list[str]) -> list[dict]:
    """Plano B sem login: página in.gov.br/leiturajornal (traz título, órgão e trecho inicial de cada ato)."""
    import requests

    d = datetime.fromisoformat(data_iso).strftime("%d-%m-%Y")
    atos = []
    for secao in secoes:
        url = URL_LEITURA.format(data=d, secao=secao.lower())
        try:
            r = requests.get(url, headers=UA, timeout=90)
        except requests.RequestException as e:
            print(f"Página pública {secao}: erro {e}")
            continue
        lidos = parse_leitura(r.text, secao) if r.ok else []
        print(f"Página pública {secao}: HTTP {r.status_code}, {len(lidos)} atos")
        atos += lidos
    return atos


# ----------------------------------------------------------------- leitura
def ler_atos(zips: dict[str, bytes]):
    for secao, conteudo in zips.items():
        with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
            for nome in z.namelist():
                if not nome.lower().endswith(".xml"):
                    continue
                try:
                    raiz = ET.fromstring(z.read(nome))
                except ET.ParseError:
                    continue
                art = raiz if raiz.tag == "article" else raiz.find(".//article")
                if art is None:
                    continue
                corpo = art.find("body")
                pega = lambda tag: (corpo.findtext(tag) if corpo is not None else "") or ""
                texto_html = pega("Texto")
                ementa = texto_limpo(pega("Ementa"))
                if not ementa:
                    m = re.search(r'<p[^>]*class="[^"]*ementa[^"]*"[^>]*>(.*?)</p>', texto_html, re.S | re.I)
                    ementa = texto_limpo(m.group(1)) if m else ""
                yield {
                    "id": art.get("id") or art.get("idMateria") or nome,
                    "secao": art.get("pubName") or secao,
                    "data_publicacao": art.get("pubDate", ""),
                    "edicao": art.get("editionNumber", ""),
                    "pagina": art.get("numberPage", ""),
                    "tipo": art.get("artType", ""),
                    "orgao": art.get("artCategory", ""),
                    "titulo": texto_limpo(pega("Identifica")) or art.get("name", ""),
                    "ementa": ementa,
                    "texto": texto_limpo(texto_html),
                    "url": art.get("pdfPage", ""),
                }


# ----------------------------------------------------------------- filtro
def classificar(ato: dict, cfg: dict) -> dict | None:
    bruto = " ".join([ato["titulo"], ato["ementa"], ato["texto"][:20000]])
    alvo = normalizar(bruto)
    orgao = normalizar(ato["orgao"])
    tipo = normalizar(ato["tipo"])

    hits_reforma = [t for t, p in cfg["reforma"] if p.search(alvo)]
    if CONTEXTO_TRIB.search(alvo):
        hits_reforma += [s for s, p in cfg["siglas"] if p.search(bruto)]
    hits_trib = [t for t, p in cfg["tributario"] if p.search(alvo)]
    do_orgao = any(o in orgao for o in cfg["orgaos"])
    normativo = any(tipo.startswith(t) for t in cfg["tipos"])

    if not (hits_reforma or hits_trib or do_orgao):
        return None
    if not (hits_reforma or hits_trib):
        # entrou só pelo órgão: precisa ser ato normativo e não ser pessoal/rotina
        if not normativo:
            return None
        cabeca = normalizar(ato["titulo"] + " " + ato["ementa"] + " " + ato["texto"][:600])
        if any(p.search(cabeca) for _, p in cfg["ruido"]):
            return None

    if hits_reforma:
        nivel = "alta"
    elif normativo and (hits_trib or do_orgao):
        nivel = "media"
    elif hits_trib and do_orgao:
        nivel = "media"
    else:
        nivel = "baixa"

    resumo = ato["ementa"] or ato["texto"][:400]
    return {
        **{k: v for k, v in ato.items() if k not in ("texto", "_fonte")},
        "resumo": resumo[:600],
        "nivel": nivel,
        "termos": sorted(set(hits_reforma + hits_trib))[:12],
        "fonte": ato.get("_fonte", "DOU (INLABS)"),
    }


# ----------------------------------------------------------------- saída
def gravar(data_iso: str, novos: list[dict]) -> list[dict]:
    pasta_dados = RAIZ / "dados"
    pasta_bol = RAIZ / "boletins"
    pasta_dados.mkdir(exist_ok=True)
    pasta_bol.mkdir(exist_ok=True)

    arq_dia = pasta_dados / f"{data_iso}.json"
    existentes = json.loads(arq_dia.read_text("utf-8")) if arq_dia.exists() else []
    por_id = {a["id"]: a for a in existentes}
    agora = datetime.now(FUSO_BR).isoformat(timespec="minutes")
    for a in novos:
        if a["id"] not in por_id:
            a["coletado_em"] = agora
            por_id[a["id"]] = a
    atos = sorted(por_id.values(), key=lambda a: (NIVEL_ORDEM[a["nivel"]], a["secao"], a["orgao"], a["titulo"]))
    arq_dia.write_text(json.dumps(atos, ensure_ascii=False, indent=1), "utf-8")

    # últimos 15 dias consolidados
    limite = (datetime.fromisoformat(data_iso) - timedelta(days=15)).date().isoformat()
    todos = []
    for f in sorted(pasta_dados.glob("20*.json")):
        if f.stem >= limite:
            for a in json.loads(f.read_text("utf-8")):
                a.setdefault("data_iso", f.stem)
                todos.append(a)
    (pasta_dados / "ultimos.json").write_text(
        json.dumps({"atualizado_em": agora, "atos": todos}, ensure_ascii=False, indent=1), "utf-8")

    # boletim markdown
    linhas = [f"# Boletim DOU — {datetime.fromisoformat(data_iso).strftime('%d/%m/%Y')}", "",
              f"Atualizado em {agora}. {len(atos)} ato(s) relevante(s).", ""]
    for nivel in ("alta", "media", "baixa"):
        grupo = [a for a in atos if a["nivel"] == nivel]
        if not grupo:
            continue
        linhas += [f"## {NIVEL_NOME[nivel]} ({len(grupo)})", ""]
        for a in grupo:
            linhas.append(f"- **{a['titulo']}** — {a['orgao']} ({a['secao']}, p. {a['pagina']})")
            if a["resumo"]:
                linhas.append(f"  {a['resumo']}")
            if a["url"]:
                linhas.append(f"  [Ver no DOU]({a['url']})")
            linhas.append("")
    if not atos:
        linhas.append("Nenhum ato relevante encontrado nas seções monitoradas.")
    (pasta_bol / f"{data_iso}.md").write_text("\n".join(linhas), "utf-8")
    return atos


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", help="AAAA-MM-DD (padrão: hoje, horário de Brasília)")
    ap.add_argument("--pasta-xml", help="processa os .zip desta pasta em vez de baixar (teste)")
    args = ap.parse_args()

    data_iso = args.data or datetime.now(FUSO_BR).date().isoformat()
    cfg = carregar_config()

    if args.pasta_xml:
        zips = {p.stem.split("-")[-1]: p.read_bytes() for p in Path(args.pasta_xml).glob("*.zip")}
        fonte_atos = list(ler_atos(zips))
    else:
        fonte_atos = []
        try:
            fonte_atos = list(ler_atos(baixar_zips(data_iso, cfg["secoes"])))
        except Exception as e:  # noqa: BLE001
            print(f"INLABS indisponível: {e}")
        if not fonte_atos:
            print("Usando o plano B: página pública de leitura do DOU (in.gov.br).")
            fonte_atos = ler_pagina_publica(data_iso, cfg["secoes"])
            for a in fonte_atos:
                a["_fonte"] = "DOU (in.gov.br)"

    lidos, relevantes = 0, []
    for ato in fonte_atos:
        lidos += 1
        r = classificar(ato, cfg)
        if r:
            relevantes.append(r)

    if lidos == 0:
        sys.exit(f"{data_iso}: nenhum ato lido (INLABS e página pública indisponíveis, ou dia sem edição). "
                 "Nada foi gravado.")
    atos = gravar(data_iso, relevantes)
    alta = sum(a["nivel"] == "alta" for a in atos)
    print(f"{data_iso}: {lidos} atos lidos, {len(relevantes)} relevantes nesta execução, "
          f"{len(atos)} no dia ({alta} de Reforma Tributária).")


if __name__ == "__main__":
    main()
