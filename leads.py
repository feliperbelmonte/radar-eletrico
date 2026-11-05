#!/usr/bin/env python3
"""Prospecção Elétrica — lista empresas que precisam de projeto elétrico, a partir dos dados abertos de CNPJ.

Uso:
    python leads.py --saida saida-leads              # baixa os zips da Receita
    python leads.py --saida saida-leads --local DIR  # usa zips já baixados em DIR
    python leads.py ... --contratos ARQ.json         # contratos do PNCP de um arquivo (testes)

Trilhas (cada empresa cai em uma, com textos próprios):
    licitacao  venceu contrato público recente na área elétrica (API de contratos do PNCP)
    pericia    escritórios de advocacia (laudo/parecer técnico, assistente técnico)
    projeto    demais segmentos que contratam projeto elétrico

Gera em --saida:
    painel.html   painel de prospecção com as empresas (contém dados de contato: o
                  workflow criptografa antes de publicar, porque o repositório é público)
    resumo.json   só contagens, sem dados de contato

Só biblioteca padrão do Python (3.11+).
"""
from __future__ import annotations

import argparse
import base64
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
import xml.etree.ElementTree as ET
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
SIMPLES_OPCAO, SIMPLES_MEI = 1, 4
API_CONTRATOS = "https://pncp.gov.br/api/consulta/v1/contratos"
PORTES = {"00": "Não informado", "01": "Microempresa", "03": "Pequeno porte", "05": "Demais"}

SUFIXOS = re.compile(
    r"\b(ltda|me|epp|eireli|s/?a|s\.a\.?|ss|slu|sociedade unipessoal|limitada|"
    r"microempresa|empresa individual)\b\.?", re.I)


def log(msg: str) -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------- download
# A Receita publica os dados num compartilhamento público do Nextcloud
# (https://arquivos.receitafederal.gov.br/index.php/s/<token>), acessado por WebDAV
# com o token como usuário. O token muda de tempos em tempos: fica no prospeccao.toml.

def _auth(token: str) -> str:
    return "Basic " + base64.b64encode(f"{token}:".encode()).decode()


def _abrir(url: str, cfg: dict, metodo: str = "GET", auth: str | None = None, extra: dict | None = None):
    cab = {"User-Agent": UA, **(extra or {})}
    if auth:
        cab["Authorization"] = auth
    req = urllib.request.Request(url, method=metodo, headers=cab)
    return urllib.request.urlopen(req, timeout=cfg["timeout_segundos"])


def baixar(url: str, destino: Path, cfg: dict, auth: str | None = None) -> None:
    ultimo = "erro desconhecido"
    for tentativa in range(cfg["tentativas"]):
        try:
            with _abrir(url, cfg, auth=auth) as r, open(destino, "wb") as f:
                while bloco := r.read(1 << 20):
                    f.write(bloco)
            # o servidor da Receita às vezes corta a transferência sem erro: zip truncado
            if destino.suffix == ".zip" and not zipfile.is_zipfile(destino):
                raise OSError(f"zip incompleto ({destino.stat().st_size / 1e6:.0f} MB)")
            return
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            ultimo = f"{type(e).__name__}: {e}"
            log(f"  falha baixando {url} ({ultimo}), tentativa {tentativa + 1}")
            time.sleep(min(120, 10 * 3 ** tentativa))
    raise RuntimeError(f"não consegui baixar {url}: {ultimo}")


def ler_multistatus(xml: str) -> list[tuple[str, bool]]:
    """Resposta de PROPFIND → [(nome, é_pasta)], sem a própria pasta consultada."""
    ns = {"d": "DAV:"}
    itens = []
    for resp in ET.fromstring(xml).findall("d:response", ns):
        href = resp.findtext("d:href", default="", namespaces=ns)
        nome = urllib.parse.unquote(href.rstrip("/")).rsplit("/", 1)[-1]
        pasta = resp.find(".//d:resourcetype/d:collection", ns) is not None
        if nome:
            itens.append((nome, pasta))
    return itens[1:] if itens else itens  # o primeiro é a pasta consultada


def propfind(url: str, token: str, cfg: dict) -> list[tuple[str, bool]]:
    with _abrir(url, cfg, "PROPFIND", _auth(token), {"Depth": "1"}) as r:
        return ler_multistatus(r.read().decode("utf-8", "replace"))


def listar_html(url: str, cfg: dict) -> str:
    with _abrir(url, cfg) as r:
        return r.read().decode("utf-8", "replace")


def achar_pasta_mais_recente(cfg: dict) -> tuple[str, str | None]:
    """(URL da pasta AAAA-MM mais recente com os zips, cabeçalho de autenticação ou None)."""
    erros = []
    servidor = cfg["servidor"].rstrip("/")
    for comp in cfg.get("compartilhamentos", []):
        token, raiz = comp["token"], comp.get("raiz", "").strip("/")
        raiz = raiz + "/" if raiz else ""
        for base in (f"{servidor}/public.php/dav/files/{token}/{raiz}", f"{servidor}/public.php/webdav/{raiz}"):
            try:
                meses = sorted((n for n, pasta in propfind(base, token, cfg) if pasta and re.fullmatch(r"\d{4}-\d{2}", n)),
                               reverse=True)
                for mes in meses[:3]:
                    nomes = {n for n, _ in propfind(base + mes + "/", token, cfg)}
                    if "Estabelecimentos0.zip" in nomes:
                        log(f"Usando {base}{mes}/ (compartilhamento {token})")
                        return base + mes + "/", _auth(token)
                erros.append(f"{base}: nenhuma pasta mensal completa ({', '.join(meses[:3]) or 'sem meses'})")
            except Exception as e:  # noqa: BLE001 — tenta o próximo caminho
                erros.append(f"{base}: {type(e).__name__}: {e}")
    for base in cfg.get("espelhos", []):
        try:
            meses = sorted(set(re.findall(r'href="(?:[^"]*/)?(\d{4}-\d{2})/?"', listar_html(base, cfg))), reverse=True)
            for mes in meses[:3]:
                pasta = urllib.parse.urljoin(base, mes + "/")
                if "Estabelecimentos0.zip" in listar_html(pasta, cfg):
                    log(f"Usando espelho {pasta}")
                    return pasta, None
            erros.append(f"{base}: nenhuma pasta mensal com Estabelecimentos0.zip")
        except Exception as e:  # noqa: BLE001
            erros.append(f"{base}: {type(e).__name__}: {e}")
    raise RuntimeError(
        "dados de CNPJ não encontrados. Se a Receita trocou o link, pegue o token novo em "
        "https://arquivos.receitafederal.gov.br (Dados > Cadastros > CNPJ: a URL fica .../index.php/s/<token>) "
        "e atualize [fonte].compartilhamentos no prospeccao.toml. Tentativas: " + " | ".join(erros))


class Fonte:
    """Entrega os zips um de cada vez (baixando e apagando) ou de uma pasta local."""

    def __init__(self, cfg: dict, local: Path | None):
        self.cfg, self.local = cfg, local
        self.pasta, self.auth = (None, None) if local else achar_pasta_mais_recente(cfg)
        self.tmp = Path(tempfile.mkdtemp(prefix="cnpj-"))

    def abrir(self, nome: str) -> Path:
        if self.local:
            return self.local / nome
        destino = self.tmp / nome
        t0 = time.time()
        baixar(self.pasta + nome, destino, self.cfg, self.auth)
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


def modelo_de(cnpj: str, n: int) -> int:
    """Índice (0..n-1) do modelo de mensagem desta empresa — fixo pelo CNPJ."""
    return int(hashlib.sha1(cnpj.encode()).hexdigest(), 16) % n


def montar_mensagem(modelos: list[str], remetente: dict, empresa: str, cidade: str, cnpj: str,
                    atividade: str = "instalações elétricas") -> str:
    i = modelo_de(cnpj, len(modelos))
    return modelos[i].format(nome=remetente["nome"], registro=remetente["registro"], empresa=empresa,
                             cidade=cidade, atividade=atividade)


# ---------------------------------------------------------------- contratos do PNCP (trilha licitacao)

def _norm(txt: str) -> str:
    return re.sub(r"\s+", " ", sem_acento(txt or "").lower()).strip()


def _casa(texto: str, termos: list[str]) -> bool:
    """Termo com * no fim casa prefixo de palavra; sem *, palavra/expressão inteira."""
    for t in termos:
        t = _norm(t)
        padrao = re.escape(t[:-1]) + r"\w*" if t.endswith("*") else re.escape(t)
        if re.search(r"(?<!\w)" + padrao + r"(?!\w)", texto):
            return True
    return False


def classificar_contrato(item: dict, lic: dict) -> dict | None:
    """Contrato do PNCP → sinal para a empresa vencedora, ou None se não interessa."""
    ni = re.sub(r"\D", "", str(item.get("niFornecedor") or ""))
    if len(ni) != 14 or (item.get("tipoPessoa") or "PJ") != "PJ":
        return None
    objeto = _norm(item.get("objetoContrato") or "")
    if not objeto or not _casa(objeto, lic["termos"]) or _casa(objeto, lic.get("excluir", [])):
        return None
    if lic.get("exige_servico") and not _casa(objeto, lic["exige_servico"]):
        return None
    valor = float(item.get("valorGlobal") or item.get("valorInicial") or 0)
    if valor and valor < lic.get("valor_minimo", 0):
        return None
    orgao = (item.get("orgaoEntidade") or {}).get("razaoSocial") or ""
    uo = item.get("unidadeOrgao") or {}
    cnpj_org = (item.get("orgaoEntidade") or {}).get("cnpj") or ""
    ano, seq = item.get("anoContrato"), item.get("sequencialContrato")
    bruto = (item.get("objetoContrato") or "").strip()
    curto = re.sub(r"\s+", " ", bruto)
    if len(curto) > lic.get("max_caracteres_objeto", 90):
        curto = curto[: lic.get("max_caracteres_objeto", 90)].rsplit(" ", 1)[0] + "…"
    return {
        "cnpj": ni,
        "orgao": titulo(orgao),
        "orgao_uf": uo.get("ufSigla") or "",
        "objeto": (curto.lower() if curto.isupper() else curto[:1].lower() + curto[1:]),
        "valor": valor,
        "assinatura": (item.get("dataAssinatura") or "")[:10],
        "link": f"https://pncp.gov.br/app/contratos/{cnpj_org}/{ano}/{seq}" if cnpj_org and ano and seq else "",
    }


def baixar_contratos(lic: dict, hoje: date) -> tuple[list[dict], dict]:
    """Contratos publicados nos últimos N dias (do mais recente para trás), até o limite de páginas."""
    itens, info = [], {"paginas": 0, "falhas": 0, "truncado": False}
    for d in range(1, lic["dias"] + 1):
        dia = (hoje - timedelta(days=d)).strftime("%Y%m%d")
        pagina, total = 1, 1
        while pagina <= total:
            if info["paginas"] >= lic["max_paginas"]:
                info["truncado"] = True
                return itens, info
            q = urllib.parse.urlencode({"dataInicial": dia, "dataFinal": dia, "pagina": pagina,
                                        "tamanhoPagina": lic["tamanho_pagina"]})
            dados = None
            for tentativa in range(lic["tentativas"]):
                try:
                    req = urllib.request.Request(f"{API_CONTRATOS}?{q}", headers={"User-Agent": UA, "Accept": "application/json"})
                    with urllib.request.urlopen(req, timeout=lic["timeout_segundos"]) as r:
                        corpo = r.read()
                    dados = json.loads(corpo) if corpo.strip() else {"data": [], "totalPaginas": 0}
                    break
                except (urllib.error.URLError, TimeoutError, ConnectionError, OSError, json.JSONDecodeError) as e:
                    log(f"  contratos {dia} p{pagina}: {type(e).__name__}: {e} (tentativa {tentativa + 1})")
                    limite = getattr(e, "code", None) == 429  # PNCP limita requisições: esperar mais
                    time.sleep(30 * (tentativa + 1) if limite else min(60, 5 * 3 ** tentativa))
            info["paginas"] += 1
            if dados is None:
                info["falhas"] += 1
                break
            itens.extend(dados.get("data") or [])
            total = int(dados.get("totalPaginas") or 0)
            pagina += 1
            time.sleep(lic.get("pausa_entre_paginas", 0.2))
    return itens, info


def sinais_licitacao(cfg: dict, hoje: date, arquivo: Path | None) -> tuple[dict[str, dict], dict]:
    """{cnpj_basico: sinal} das empresas que venceram contrato recente na área (o mais recente fica)."""
    lic = cfg.get("licitacoes") or {}
    if not lic.get("ativo"):
        return {}, {"ativo": False}
    if arquivo:
        brutos, info = json.loads(arquivo.read_text(encoding="utf-8")).get("data", []), {"arquivo": str(arquivo)}
    else:
        brutos, info = baixar_contratos(lic, hoje)
    sinais: dict[str, dict] = {}
    for item in brutos:
        s = classificar_contrato(item, lic)
        if s and (s["cnpj"][:8] not in sinais or s["assinatura"] > sinais[s["cnpj"][:8]]["assinatura"]):
            sinais[s["cnpj"][:8]] = s
    info.update({"contratos_lidos": len(brutos), "empresas_com_sinal": len(sinais)})
    log(f"Contratos PNCP: {info}")
    return sinais, info


def regras_da_trilha(cfg: dict, trilha: str) -> dict:
    return {**cfg["filtro"], **(cfg.get("filtro_trilha", {}).get(trilha) or {})}


# ---------------------------------------------------------------- pipeline

def coletar(fonte: Fonte, cfg: dict, hoje: date, sinais: dict[str, dict] | None = None) -> tuple[list[dict], dict]:
    f, cfgf = cfg["filtro"], cfg["fonte"]
    sinais = sinais or {}
    segmento_de = {c: i for i, seg in enumerate(cfg["segmento"]) for c in seg["cnaes"]}
    usar_sec = f.get("usar_cnae_secundario", False)
    ufs = set(f.get("ufs") or [])
    marcadores = [c.encode() for c in segmento_de]
    trilhas = {seg.get("trilha", "projeto") for seg in cfg["segmento"]} | ({"licitacao"} if sinais else set())
    menor_anos = min(regras_da_trilha(cfg, t)["anos_minimos_atividade"] for t in trilhas)
    limite_inicio = (hoje - timedelta(days=365 * menor_anos)).strftime("%Y%m%d")
    stats = {"estabelecimentos_lidos": 0, "cnae_ativos": 0, "sem_celular": 0, "muito_novos": 0}

    candidatos: dict[str, dict] = {}
    for parte in range(cfgf["partes"]):
        nome = f"Estabelecimentos{parte}.zip"
        caminho = fonte.abrir(nome)
        for linha in linhas_zip(caminho):
            stats["estabelecimentos_lidos"] += 1
            sinal = sinais.get(linha[1:9].decode("latin-1")) if sinais else None
            if not sinal and not any(m in linha for m in marcadores):
                continue
            c = campos(linha)
            if len(c) < 28 or c[E_SITUACAO] != "02":
                continue
            principal = c[E_CNAE] in segmento_de
            if principal:
                seg = segmento_de[c[E_CNAE]]
            elif usar_sec and (secs := [segmento_de[x] for x in c[E_CNAE_SEC].split(",") if x in segmento_de]):
                seg = min(secs)
            elif sinal:
                seg = None
            else:
                continue
            if ufs and c[E_UF] not in ufs and not sinal:
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
                "trilha": "licitacao" if sinal else cfg["segmento"][seg].get("trilha", "projeto"), "sinal": sinal,
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

    # Simples Nacional e MEI
    caminho = fonte.abrir("Simples.zip")
    for linha in linhas_zip(caminho):
        basico = linha[1:9].decode("latin-1")
        if basico in candidatos:
            c = campos(linha)
            candidatos[basico]["simples"] = c[SIMPLES_OPCAO] == "S"
            candidatos[basico]["mei"] = c[SIMPLES_MEI] == "S"
    fonte.liberar(caminho)

    # nomes de municípios
    municipios = {}
    caminho = fonte.abrir("Municipios.zip")
    for linha in linhas_zip(caminho):
        c = campos(linha)
        if len(c) >= 2:
            municipios[c[0]] = c[1]
    fonte.liberar(caminho)

    excluir = [_norm(t) for t in f.get("excluir_nomes", [])]
    empresas = []

    def corta(motivo: str) -> None:
        stats[motivo] = stats.get(motivo, 0) + 1

    for e in candidatos.values():
        r = regras_da_trilha(cfg, e["trilha"])
        limite = (hoje - timedelta(days=365 * r["anos_minimos_atividade"])).strftime("%Y%m%d")
        if e["inicio"] and e["inicio"] > limite:
            corta("muito_novos")
            continue
        if e.get("porte") not in set(r["portes"]):
            corta("fora_do_porte")
            continue
        if e.get("mei") and not r["incluir_mei"]:
            corta("mei")
            continue
        if r.get("exigir_simples") and not e.get("simples"):
            corta("fora_do_simples")
            continue
        nomes = _norm(f"{e.get('razao', '')} {e.get('fantasia', '')}")
        if excluir and any(t in nomes for t in excluir):
            corta("nome_excluido")
            continue
        e["cidade"] = municipios.get(e["mun"], e["mun"])
        empresas.append(e)
    stats["aprovadas"] = len(empresas)
    for t in sorted({e["trilha"] for e in empresas}):
        stats[f"aprovadas_{t}"] = sum(1 for e in empresas if e["trilha"] == t)
    return empresas, stats


def priorizar(empresas: list[dict], cfg: dict) -> list[dict]:
    ufs = cfg["prioridade"]["ufs"]
    cidades = [sem_acento(c).replace(" / ", "/") for c in cfg["prioridade"].get("cidades", [])]

    def chave(e):
        cid = f"{sem_acento(e['cidade'])}/{e['uf']}"
        cid_rank = cidades.index(cid) if cid in cidades else len(cidades)
        uf_rank = ufs.index(e["uf"]) if e["uf"] in ufs else len(ufs)
        porte_rank = {"05": 0, "03": 1, "01": 2}.get(e.get("porte"), 3)  # maiores primeiro: mais demanda
        if e["trilha"] == "licitacao":  # contrato mais recente primeiro: é quando o aperto acontece
            return (-int((e["sinal"] or {}).get("assinatura", "0").replace("-", "") or 0), cid_rank, uf_rank)
        return (cid_rank, uf_rank, e["segmento"], not e["cnae_principal"], porte_rank, not e["email"], e["inicio"])

    return sorted(empresas, key=chave)


def modelos_da_trilha(cfg: dict, trilha: str) -> list[str]:
    modelos = [m["texto"] for m in cfg["mensagem"] if m.get("trilha", "projeto") == trilha]
    return modelos or [m["texto"] for m in cfg["mensagem"] if m.get("trilha", "projeto") == "projeto"]


def para_painel(e: dict, cfg: dict) -> dict:
    empresa = nome_empresa(e.get("fantasia", ""), e.get("razao", ""))
    cidade = titulo(e["cidade"])
    seg = cfg["segmento"][e["segmento"]] if e["segmento"] is not None else cfg["licitacoes"]["segmento"]
    modelos = modelos_da_trilha(cfg, e["trilha"])
    sinal = e.get("sinal") or {}
    i = modelo_de(e["cnpj"], len(modelos))
    msg = modelos[i].format(nome=cfg["remetente"]["nome"], registro=cfg["remetente"]["registro"], empresa=empresa,
                            cidade=cidade, atividade=seg["atividade"], orgao=sinal.get("orgao", ""),
                            objeto=sinal.get("objeto", ""))
    rotulo = cfg["licitacoes"]["segmento"]["rotulo"] if e["trilha"] == "licitacao" else seg["rotulo"]
    extra = {}
    if sinal:
        data = sinal["assinatura"]
        extra["sinal"] = {"orgao": sinal["orgao"], "uf": sinal["orgao_uf"], "objeto": sinal["objeto"],
                          "valor": sinal["valor"], "assinatura": f"{data[8:10]}/{data[5:7]}/{data[:4]}" if data else "",
                          "link": sinal["link"]}
    return {
        **extra,
        "trilha": e["trilha"],
        "cnpj": e["cnpj"],
        "empresa": empresa,
        "razao": titulo(e.get("razao", "")),
        "cidade": cidade,
        "uf": e["uf"],
        "bairro": titulo(e["bairro"]),
        "segmento": rotulo,
        "porte": PORTES.get(e.get("porte", ""), "—"),
        "desde": e["inicio"][:4] if e["inicio"] else "",
        "celular": e["celular"],
        "email": e["email"],
        "mensagem": msg,
        "modelo": i + 1,  # dentro da trilha: para medir qual texto responde melhor
    }


def montar_painel(template: str, itens: list[dict], resumo: dict, fila: dict | None = None) -> str:
    ini, fim = template.find(MARCA_INI), template.find(MARCA_FIM)
    if ini < 0 or fim < 0:
        raise SystemExit("template sem os marcadores LEADS_DATA_START/END")

    def js(v):
        return json.dumps(v, ensure_ascii=False).replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")

    bloco = f"{MARCA_INI}\nconst LEADS = {js(itens)};\nconst RESUMO = {js(resumo)};\nconst FILA = {js(fila or {})};\n"
    return template[:ini] + bloco + template[fim:]


def executar(saida: Path, config: Path, local: Path | None, hoje: date | None = None,
             contratos: Path | None = None) -> dict:
    cfg = tomllib.loads(config.read_text(encoding="utf-8"))
    hoje = hoje or datetime.now(BRT).date()
    try:
        sinais, info_lic = sinais_licitacao(cfg, hoje, contratos)
    except Exception as e:  # noqa: BLE001 — sem o PNCP a lista sai só com as outras trilhas
        log(f"[WARN] contratos do PNCP indisponíveis: {type(e).__name__}: {e}")
        sinais, info_lic = {}, {"erro": f"{type(e).__name__}: {e}"}
    fonte = Fonte(cfg["fonte"], local)
    empresas, stats = coletar(fonte, cfg, hoje, sinais)
    empresas = priorizar(empresas, cfg)
    limites = cfg["saida"].get("max_por_trilha", {})
    selecionadas, usadas = [], {}
    for e in empresas:
        t = e["trilha"]
        if usadas.get(t, 0) < limites.get(t, cfg["saida"]["max_empresas"]) and len(selecionadas) < cfg["saida"]["max_empresas"]:
            selecionadas.append(e)
            usadas[t] = usadas.get(t, 0) + 1
    por_uf: dict[str, int] = {}
    por_segmento: dict[str, int] = {}
    for e in empresas:
        por_uf[e["uf"]] = por_uf.get(e["uf"], 0) + 1
        rot = cfg["licitacoes"]["segmento"]["rotulo"] if e["trilha"] == "licitacao" else cfg["segmento"][e["segmento"]]["rotulo"]
        por_segmento[rot] = por_segmento.get(rot, 0) + 1
    resumo = {
        "geradoEm": datetime.now(BRT).isoformat(timespec="seconds"),
        "fonte": fonte.pasta or "local",
        "totalAprovadas": len(empresas),
        "noPainel": len(selecionadas),
        "porUf": dict(sorted(por_uf.items(), key=lambda kv: -kv[1])),
        "porSegmento": dict(sorted(por_segmento.items(), key=lambda kv: -kv[1])),
        "porTrilha": usadas,
        "licitacoes": info_lic,
        "etapas": stats,
    }
    saida.mkdir(parents=True, exist_ok=True)
    template = (RAIZ / "prospeccao" / "template.html").read_text(encoding="utf-8")
    itens = [para_painel(e, cfg) for e in selecionadas]
    (saida / "painel.html").write_text(montar_painel(template, itens, resumo, cfg.get("fila")), encoding="utf-8")
    (saida / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"Pronto: {len(empresas)} empresas aprovadas, {len(selecionadas)} no painel. Etapas: {stats}")
    return resumo


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--saida", type=Path, default=RAIZ / "saida-leads")
    p.add_argument("--config", type=Path, default=RAIZ / "prospeccao.toml")
    p.add_argument("--local", type=Path, help="pasta com os zips da Receita já baixados")
    p.add_argument("--contratos", type=Path, help="JSON no formato da API de contratos do PNCP (em vez de baixar)")
    a = p.parse_args()
    executar(a.saida, a.config, a.local, contratos=a.contratos)
    return 0


if __name__ == "__main__":
    sys.exit(main())
