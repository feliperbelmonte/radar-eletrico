#!/usr/bin/env python3
"""Prospecção Elétrica — lista empresas que precisam de projeto elétrico, a partir dos dados abertos de CNPJ.

Uso:
    python leads.py --saida saida-leads              # baixa os zips da Receita
    python leads.py --saida saida-leads --local DIR  # usa zips já baixados em DIR

Gera em --saida:
    painel.html   painel de prospecção com as empresas (contém dados de contato: o
                  workflow criptografa antes de publicar, porque o repositório é público)
    resumo.json   só contagens, sem dados de contato

Só biblioteca padrão do Python (3.11+).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import tempfile
import time
import tomllib
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
BRT = timezone(timedelta(hours=-3))
MARCA_INI = "/* LEADS_DATA_START */"
MARCA_FIM = "/* LEADS_DATA_END */"
UA = "radar-eletrico-leads (github.com/feliperbelmonte/radar-eletrico)"

# Layout dos CSVs da Receita (sem cabeçalho, ';', latin-1). Índices das colunas usadas.
E_BASICO, E_ORDEM, E_DV, E_MATRIZ, E_FANTASIA, E_SITUACAO = 0, 1, 2, 3, 4, 5
E_INICIO, E_CNAE, E_CNAE_SEC = 10, 11, 12
E_TIPO_LOG, E_LOG, E_NUM, E_COMPL, E_BAIRRO, E_CEP, E_UF, E_MUN = 13, 14, 15, 16, 17, 18, 19, 20
E_DDD1, E_TEL1, E_DDD2, E_TEL2, E_EMAIL = 21, 22, 23, 24, 27
EMP_RAZAO, EMP_PORTE = 1, 5
SIMPLES_MEI = 4
PORTES = {"00": "Não informado", "01": "Microempresa", "03": "Pequeno porte", "05": "Demais"}

SUFIXOS = re.compile(
    r"\b(ltda|me|epp|eireli|s/?a|s\.a\.?|ss|slu|sociedade unipessoal|limitada|"
    r"microempresa|empresa individual)\b\.?", re.I)


def log(msg: str) -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------- download

def baixar(url: str, destino: Path, cfg: dict) -> None:
    ultimo = "erro desconhecido"
    for tentativa in range(cfg["tentativas"]):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=cfg["timeout_segundos"]) as r, open(destino, "wb") as f:
                while bloco := r.read(1 << 20):
                    f.write(bloco)
            return
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            ultimo = f"{type(e).__name__}: {e}"
            log(f"  falha baixando {url} ({ultimo}), tentativa {tentativa + 1}")
            time.sleep(min(120, 10 * 3 ** tentativa))
    raise RuntimeError(f"não consegui baixar {url}: {ultimo}")


def listar(url: str, cfg: dict) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=cfg["timeout_segundos"]) as r:
        return r.read().decode("utf-8", "replace")


def achar_pasta_mais_recente(cfg: dict) -> str:
    """Devolve a URL da pasta AAAA-MM mais recente que tenha os zips."""
    erros = []
    for base in cfg["bases"]:
        try:
            meses = sorted(set(re.findall(r'href="(?:[^"]*/)?(\d{4}-\d{2})/?"', listar(base, cfg))), reverse=True)
            for mes in meses[:3]:
                pasta = urllib.parse.urljoin(base, mes + "/")
                if "Estabelecimentos0.zip" in listar(pasta, cfg):
                    log(f"Usando {pasta}")
                    return pasta
            erros.append(f"{base}: nenhuma pasta mensal com Estabelecimentos0.zip")
        except Exception as e:  # noqa: BLE001 — tenta a próxima base
            erros.append(f"{base}: {type(e).__name__}: {e}")
    raise RuntimeError("dados de CNPJ não encontrados: " + " | ".join(erros))


class Fonte:
    """Entrega os zips um de cada vez (baixando e apagando) ou de uma pasta local."""

    def __init__(self, cfg: dict, local: Path | None):
        self.cfg, self.local = cfg, local
        self.pasta = None if local else achar_pasta_mais_recente(cfg)
        self.tmp = Path(tempfile.mkdtemp(prefix="cnpj-"))

    def abrir(self, nome: str) -> Path:
        if self.local:
            return self.local / nome
        destino = self.tmp / nome
        t0 = time.time()
        baixar(self.pasta + nome, destino, self.cfg)
        log(f"  {nome}: {destino.stat().st_size / 1e6:.0f} MB em {time.time() - t0:.0f}s")
        return destino

    def liberar(self, caminho: Path) -> None:
        if not self.local:
            caminho.unlink(missing_ok=True)


def linhas_zip(caminho: Path):
    """Linhas cruas (bytes) do CSV dentro do zip."""
    with zipfile.ZipFile(caminho) as z:
        for nome in z.namelist():
            with z.open(nome) as f:
                yield from io.BufferedReader(f, 1 << 20)


def campos(linha: bytes) -> list[str]:
    return next(csv.reader([linha.decode("latin-1").rstrip("\r\n")], delimiter=";", quotechar='"'))


# ---------------------------------------------------------------- regras

def celular(ddd: str, tel: str) -> str | None:
    """'41','991234567' → '41991234567'. Só celular (provável WhatsApp)."""
    ddd = re.sub(r"\D", "", ddd or "").lstrip("0")
    tel = re.sub(r"\D", "", tel or "")
    if len(ddd) != 2 or not 11 <= int(ddd) <= 99:
        return None
    if len(tel) == 9 and tel[0] == "9":
        return ddd + tel
    if len(tel) == 8 and tel[0] in "6789":  # cadastro antigo, sem o nono dígito
        return ddd + "9" + tel
    return None


def titulo(txt: str) -> str:
    pequenas = {"de", "da", "do", "das", "dos", "e", "em"}
    palavras = txt.lower().split()
    return " ".join(p if (i and p in pequenas) else p[:1].upper() + p[1:] for i, p in enumerate(palavras))


def nome_empresa(fantasia: str, razao: str) -> str:
    base = fantasia.strip() if fantasia.strip() and fantasia.strip() not in ("*", "-", ".") else razao
    base = re.sub(r"^[\d.\-/ ]+", "", base)            # MEI/EI começam com CPF/CNPJ
    base = SUFIXOS.sub("", base)
    base = re.sub(r"[\s\-–,.]+$", "", re.sub(r"\s{2,}", " ", base)).strip()
    return titulo(base) if base.isupper() or base.islower() else base


def sem_acento(txt: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", txt) if not unicodedata.combining(c)).upper()


def montar_mensagem(modelos: list[str], remetente: dict, empresa: str, cidade: str, cnpj: str,
                    atividade: str = "instalações elétricas") -> str:
    i = int(hashlib.sha1(cnpj.encode()).hexdigest(), 16) % len(modelos)
    return modelos[i].format(nome=remetente["nome"], registro=remetente["registro"], empresa=empresa,
                             cidade=cidade, atividade=atividade)


# ---------------------------------------------------------------- pipeline

def coletar(fonte: Fonte, cfg: dict, hoje: date) -> tuple[list[dict], dict]:
    f, cfgf = cfg["filtro"], cfg["fonte"]
    segmento_de = {c: i for i, seg in enumerate(cfg["segmento"]) for c in seg["cnaes"]}
    usar_sec = f.get("usar_cnae_secundario", False)
    ufs = set(f.get("ufs") or [])
    marcadores = [c.encode() for c in segmento_de]
    limite_inicio = (hoje - timedelta(days=365 * f["anos_minimos_atividade"])).strftime("%Y%m%d")
    stats = {"estabelecimentos_lidos": 0, "cnae_ativos": 0, "sem_celular": 0, "muito_novos": 0}

    candidatos: dict[str, dict] = {}
    for parte in range(cfgf["partes"]):
        nome = f"Estabelecimentos{parte}.zip"
        caminho = fonte.abrir(nome)
        for linha in linhas_zip(caminho):
            stats["estabelecimentos_lidos"] += 1
            if not any(m in linha for m in marcadores):
                continue
            c = campos(linha)
            if len(c) < 28 or c[E_SITUACAO] != "02":
                continue
            principal = c[E_CNAE] in segmento_de
            if principal:
                seg = segmento_de[c[E_CNAE]]
            elif usar_sec:
                secs = [segmento_de[x] for x in c[E_CNAE_SEC].split(",") if x in segmento_de]
                if not secs:
                    continue
                seg = min(secs)
            else:
                continue
            if ufs and c[E_UF] not in ufs:
                continue
            stats["cnae_ativos"] += 1
            if c[E_INICIO] and c[E_INICIO] > limite_inicio:
                stats["muito_novos"] += 1
                continue
            cel = celular(c[E_DDD1], c[E_TEL1]) or celular(c[E_DDD2], c[E_TEL2])
            if not cel:
                stats["sem_celular"] += 1
                continue
            basico = c[E_BASICO]
            atual = candidatos.get(basico)
            if atual and not (c[E_MATRIZ] == "1" and atual["matriz"] != "1"):
                continue  # um contato por empresa, preferindo a matriz
            candidatos[basico] = {
                "cnpj": basico + c[E_ORDEM] + c[E_DV], "matriz": c[E_MATRIZ], "fantasia": c[E_FANTASIA],
                "inicio": c[E_INICIO], "uf": c[E_UF], "mun": c[E_MUN], "bairro": c[E_BAIRRO].strip(),
                "celular": cel, "email": c[E_EMAIL].strip().lower(), "cnae_principal": principal, "segmento": seg,
            }
        fonte.liberar(caminho)
        log(f"{nome}: {len(candidatos)} empresas candidatas até agora")

    # razão social e porte
    for parte in range(cfgf["partes"]):
        caminho = fonte.abrir(f"Empresas{parte}.zip")
        for linha in linhas_zip(caminho):
            basico = linha[1:9].decode("latin-1")
            if basico in candidatos:
                c = campos(linha)
                candidatos[basico]["razao"] = c[EMP_RAZAO]
                candidatos[basico]["porte"] = c[EMP_PORTE]
        fonte.liberar(caminho)

    # MEI (Simples)
    caminho = fonte.abrir("Simples.zip")
    for linha in linhas_zip(caminho):
        basico = linha[1:9].decode("latin-1")
        if basico in candidatos:
            candidatos[basico]["mei"] = campos(linha)[SIMPLES_MEI] == "S"
    fonte.liberar(caminho)

    # nomes de municípios
    municipios = {}
    caminho = fonte.abrir("Municipios.zip")
    for linha in linhas_zip(caminho):
        c = campos(linha)
        if len(c) >= 2:
            municipios[c[0]] = c[1]
    fonte.liberar(caminho)

    portes = set(f["portes"])
    empresas = []
    for e in candidatos.values():
        if e.get("porte") not in portes:
            stats["fora_do_porte"] = stats.get("fora_do_porte", 0) + 1
            continue
        if e.get("mei") and not f["incluir_mei"]:
            stats["mei"] = stats.get("mei", 0) + 1
            continue
        e["cidade"] = municipios.get(e["mun"], e["mun"])
        empresas.append(e)
    stats["aprovadas"] = len(empresas)
    return empresas, stats


def priorizar(empresas: list[dict], cfg: dict) -> list[dict]:
    ufs = cfg["prioridade"]["ufs"]
    cidades = [sem_acento(c) for c in cfg["prioridade"].get("cidades", [])]

    def chave(e):
        uf_rank = ufs.index(e["uf"]) if e["uf"] in ufs else len(ufs)
        cid = sem_acento(e["cidade"])
        cid_rank = cidades.index(cid) if cid in cidades else len(cidades)
        porte_rank = {"05": 0, "03": 1, "01": 2}.get(e.get("porte"), 3)  # maiores primeiro: mais demanda
        return (uf_rank, cid_rank, e["segmento"], not e["cnae_principal"], porte_rank, not e["email"], e["inicio"])

    return sorted(empresas, key=chave)


def para_painel(e: dict, cfg: dict) -> dict:
    empresa = nome_empresa(e.get("fantasia", ""), e.get("razao", ""))
    cidade = titulo(e["cidade"])
    seg = cfg["segmento"][e["segmento"]]
    msg = montar_mensagem([m["texto"] for m in cfg["mensagem"]], cfg["remetente"], empresa, cidade, e["cnpj"],
                          seg["atividade"])
    return {
        "cnpj": e["cnpj"],
        "empresa": empresa,
        "razao": titulo(e.get("razao", "")),
        "cidade": cidade,
        "uf": e["uf"],
        "bairro": titulo(e["bairro"]),
        "segmento": seg["rotulo"],
        "porte": PORTES.get(e.get("porte", ""), "—"),
        "desde": e["inicio"][:4] if e["inicio"] else "",
        "celular": e["celular"],
        "email": e["email"],
        "mensagem": msg,
    }


def montar_painel(template: str, itens: list[dict], resumo: dict) -> str:
    ini, fim = template.find(MARCA_INI), template.find(MARCA_FIM)
    if ini < 0 or fim < 0:
        raise SystemExit("template sem os marcadores LEADS_DATA_START/END")

    def js(v):
        return json.dumps(v, ensure_ascii=False).replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")

    bloco = f"{MARCA_INI}\nconst LEADS = {js(itens)};\nconst RESUMO = {js(resumo)};\n"
    return template[:ini] + bloco + template[fim:]


def executar(saida: Path, config: Path, local: Path | None, hoje: date | None = None) -> dict:
    cfg = tomllib.loads(config.read_text(encoding="utf-8"))
    hoje = hoje or datetime.now(BRT).date()
    fonte = Fonte(cfg["fonte"], local)
    empresas, stats = coletar(fonte, cfg, hoje)
    empresas = priorizar(empresas, cfg)
    selecionadas = empresas[: cfg["saida"]["max_empresas"]]
    por_uf: dict[str, int] = {}
    por_segmento: dict[str, int] = {}
    for e in empresas:
        por_uf[e["uf"]] = por_uf.get(e["uf"], 0) + 1
        rot = cfg["segmento"][e["segmento"]]["rotulo"]
        por_segmento[rot] = por_segmento.get(rot, 0) + 1
    resumo = {
        "geradoEm": datetime.now(BRT).isoformat(timespec="seconds"),
        "fonte": fonte.pasta or "local",
        "totalAprovadas": len(empresas),
        "noPainel": len(selecionadas),
        "porUf": dict(sorted(por_uf.items(), key=lambda kv: -kv[1])),
        "porSegmento": dict(sorted(por_segmento.items(), key=lambda kv: -kv[1])),
        "etapas": stats,
    }
    saida.mkdir(parents=True, exist_ok=True)
    template = (RAIZ / "prospeccao" / "template.html").read_text(encoding="utf-8")
    itens = [para_painel(e, cfg) for e in selecionadas]
    (saida / "painel.html").write_text(montar_painel(template, itens, resumo), encoding="utf-8")
    (saida / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"Pronto: {len(empresas)} empresas aprovadas, {len(selecionadas)} no painel. Etapas: {stats}")
    return resumo


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--saida", type=Path, default=RAIZ / "saida-leads")
    p.add_argument("--config", type=Path, default=RAIZ / "prospeccao.toml")
    p.add_argument("--local", type=Path, help="pasta com os zips da Receita já baixados")
    a = p.parse_args()
    executar(a.saida, a.config, a.local)
    return 0


if __name__ == "__main__":
    sys.exit(main())
