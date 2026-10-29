#!/usr/bin/env python3
"""Radar Elétrico — varre a API de consulta do PNCP e gera o painel de licitações.

Uso:
    python radar.py --saida saida                 # consulta a API do PNCP
    python radar.py --saida saida --fixture X.json  # roda offline com dados salvos

Gera em --saida:
    licitacoes.json   dados completos da rodada (itens + estatísticas)
    painel.html       painel pronto para publicar no Claude Artifact
    notificacao.txt   texto da notificação ao Felipe
    README.md         resumo legível no GitHub

Só usa a biblioteca padrão do Python (3.11+).
"""
from __future__ import annotations

import argparse
import http.client
import json
import re
import sys
import time
import tomllib
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
API = "https://pncp.gov.br/api/consulta/v1/contratacoes/proposta"
BRT = timezone(timedelta(hours=-3))  # Brasil sem horário de verão desde 2019
MARCA_INI = "/* LICITACOES_DATA_START */"
MARCA_FIM = "/* LICITACOES_DATA_END */"
MODALIDADES = {
    1: "Leilão Eletrônico", 2: "Diálogo Competitivo", 3: "Concurso",
    4: "Concorrência Eletrônica", 5: "Concorrência Presencial", 6: "Pregão Eletrônico",
    7: "Pregão Presencial", 8: "Dispensa de Licitação", 9: "Inexigibilidade",
    10: "Manifestação de Interesse", 11: "Pré-qualificação", 12: "Credenciamento",
    13: "Leilão Presencial",
}


# ---------------------------------------------------------------- texto

def normalizar(txt: str | None) -> str:
    """Minúsculas, sem acento, hífen/barra viram espaço, espaços simples."""
    txt = unicodedata.normalize("NFKD", txt or "")
    txt = "".join(c for c in txt if not unicodedata.combining(c)).lower()
    txt = re.sub(r"[-/_]", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()


def compilar(termos: list[str]) -> re.Pattern | None:
    """Lista de termos → regex. Palavra inteira; '*' no fim = prefixo."""
    partes = []
    for termo in termos:
        prefixo = termo.endswith("*")
        base = normalizar(termo.rstrip("*"))
        if not base:
            continue
        padrao = r"\b" + re.escape(base)
        if not prefixo:
            padrao += r"\b"
        partes.append(padrao)
    return re.compile("|".join(partes)) if partes else None


def casa(regex: re.Pattern | None, texto: str) -> bool:
    return bool(regex and regex.search(texto))


RE_POTENCIA = re.compile(
    r"(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)\s*(kwp|kw|mwp|mw|kva|mva)\b"
)


def _numero(s: str) -> float:
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", s):
        s = s.replace(".", "")
    return float(s)


def potencias(texto_normalizado: str) -> tuple[list[float], list[float]]:
    """Potências citadas no texto: (lista em kW, lista em kVA). Ignora kWh."""
    kw, kva = [], []
    for numero, unidade in RE_POTENCIA.findall(texto_normalizado):
        valor = _numero(numero)
        if unidade in ("kw", "kwp"):
            kw.append(valor)
        elif unidade in ("mw", "mwp"):
            kw.append(valor * 1000)
        elif unidade == "kva":
            kva.append(valor)
        else:
            kva.append(valor * 1000)
    return kw, kva


def parse_data(valor: str | None) -> datetime | None:
    """Datas do PNCP vêm sem fuso ('2026-11-10T10:00:00'): são horário de Brasília."""
    if not valor:
        return None
    try:
        dt = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = datetime.strptime(valor[:10], "%Y-%m-%d")
        except ValueError:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=BRT)


# ---------------------------------------------------------------- configuração

@dataclass
class Escopo:
    id: str
    grupo: int
    rotulo: str
    termos: re.Pattern
    exige_tambem: re.Pattern | None = None
    execucao: re.Pattern | None = None
    escala: re.Pattern | None = None
    potencia_max_kw: float | None = None
    potencia_max_kva: float | None = None


@dataclass
class Regras:
    cfg: dict
    escopos: list[Escopo]
    excluir: re.Pattern | None
    compra: re.Pattern | None
    servico: re.Pattern | None
    atestado: re.Pattern = field(default_factory=lambda: compilar(["atestado*"]))


def carregar_regras(caminho: Path) -> Regras:
    cfg = tomllib.loads(caminho.read_text(encoding="utf-8"))
    escopos = []
    for e in cfg["escopo"]:
        escopos.append(Escopo(
            id=e["id"], grupo=int(e["grupo"]), rotulo=e["rotulo"],
            termos=compilar(e["termos"]),
            exige_tambem=compilar(e.get("exige_tambem", [])),
            execucao=compilar(e.get("execucao", [])),
            escala=compilar(e.get("escala", [])),
            potencia_max_kw=e.get("potencia_max_kw"),
            potencia_max_kva=e.get("potencia_max_kva"),
        ))
    f = cfg.get("filtros", {})
    return Regras(cfg=cfg, escopos=escopos, excluir=compilar(f.get("excluir", [])),
                  compra=compilar(f.get("compra", [])), servico=compilar(f.get("servico", [])))


# ---------------------------------------------------------------- classificação

def link_pncp(item: dict) -> str | None:
    cnpj = re.sub(r"\D", "", str((item.get("orgaoEntidade") or {}).get("cnpj") or ""))
    ano, seq = item.get("anoCompra"), item.get("sequencialCompra")
    if cnpj and str(ano).isdigit() and str(seq).isdigit():
        return f"https://pncp.gov.br/app/editais/{cnpj}/{int(ano)}/{int(seq)}"
    return None


def classificar(item: dict, regras: Regras, agora: datetime) -> tuple[dict | None, str]:
    """Devolve (item do painel, "ok") ou (None, motivo do descarte)."""
    cfg = regras.cfg
    encerra = parse_data(item.get("dataEncerramentoProposta"))
    if encerra is None:
        return None, "sem_prazo"
    if encerra <= agora:
        return None, "prazo_vencido"

    objeto = (item.get("objetoCompra") or "").strip()
    texto = normalizar(f"{objeto} {item.get('informacaoComplementar') or ''}")

    if casa(regras.excluir, texto):
        return None, "termo_excluido"
    if casa(regras.compra, texto) and not casa(regras.servico, texto):
        return None, "compra_de_material"

    escopo = next((e for e in regras.escopos
                   if casa(e.termos, texto) and (e.exige_tambem is None or casa(e.exige_tambem, texto))),
                  None)
    if escopo is None:
        return None, "fora_do_escopo"

    kw, kva = potencias(texto)
    if escopo.potencia_max_kw and kw and max(kw) > escopo.potencia_max_kw:
        return None, "potencia_acima"
    if escopo.potencia_max_kva and kva and max(kva) > escopo.potencia_max_kva:
        return None, "potencia_acima"

    valor = item.get("valorTotalEstimado")
    valor = float(valor) if isinstance(valor, (int, float)) and valor > 0 else None

    alertas = []
    if escopo.grupo == 1 and casa(escopo.execucao, texto):
        alertas.append("inclui execução/obra, fora do seu atestado")
    if escopo.grupo == 2:
        if casa(escopo.escala, texto) or (valor and valor > cfg["perfil"]["valor_escala_grande"]):
            alertas.append("escala grande para um profissional")
    exige_atestado = escopo.grupo == 1 and casa(regras.atestado, texto)
    if exige_atestado:
        alertas.append("cita atestado de capacidade técnica")

    hoje = agora.astimezone(BRT).date()
    dias = (encerra.astimezone(BRT).date() - hoje).days
    publicado = parse_data(item.get("dataPublicacaoPncp"))
    if dias <= cfg["status"]["dias_urgente"]:
        status = "urgente"
    elif alertas:
        status = "atencao"
    elif publicado and (hoje - publicado.astimezone(BRT).date()).days <= cfg["status"]["dias_novo"]:
        status = "novo"
    else:
        status = "normal"

    limite = cfg["perfil"]["limite_dispensa_engenharia"]
    dentro_dispensa = None if valor is None else valor <= limite
    modalidade = item.get("modalidadeNome") or MODALIDADES.get(item.get("modalidadeId"), "—")

    max_chars = cfg["saida"]["max_caracteres_objeto"]
    resumo = objeto if len(objeto) <= max_chars else objeto[:max_chars].rsplit(" ", 1)[0] + "…"
    texto_objeto = f"[{escopo.rotulo}] {resumo}"
    if alertas:
        texto_objeto += " — ATENÇÃO: " + "; ".join(alertas) + "."

    fonte = ["API PNCP", modalidade]
    if dentro_dispensa:
        fonte.append("dentro do limite de dispensa")
    if kw or kva:
        fonte.append("potência citada: " + ", ".join(
            [f"{v:g} kW" for v in kw] + [f"{v:g} kVA" for v in kva]))

    unidade = item.get("unidadeOrgao") or {}
    orgao = (item.get("orgaoEntidade") or {}).get("razaoSocial") or unidade.get("nomeUnidade") or "—"

    pontos = 2 * (escopo.grupo == 2) + 2 * bool(dentro_dispensa) \
        + (item.get("modalidadeId") in (8, 12)) + (status == "urgente") - 2 * bool(alertas)

    return {
        "numeroControlePNCP": item.get("numeroControlePNCP"),
        "status": status,
        "grupo": escopo.grupo,
        "escopo": escopo.id,
        "orgao": orgao.strip(),
        "unidade": (unidade.get("nomeUnidade") or "").strip(),
        "municipio": unidade.get("municipioNome") or "",
        "uf": unidade.get("ufSigla") or "",
        "objeto": texto_objeto,
        "modalidade": modalidade,
        "valorEstimado": valor,
        "dentroLimiteDispensa": dentro_dispensa,
        "dataEncerramentoProposta": item.get("dataEncerramentoProposta"),
        "dataPublicacaoPncp": item.get("dataPublicacaoPncp"),
        "diasParaPrazo": dias,
        "link": link_pncp(item) or item.get("linkSistemaOrigem"),
        "exigeAtestado": exige_atestado,
        "alertas": alertas,
        "fonte": " · ".join(fonte),
        "achadoEm": hoje.isoformat(),
        "pontuacao": pontos,
    }, "ok"


# ---------------------------------------------------------------- coleta

def baixar_json(url: str, busca: dict) -> dict | None:
    """GET com novas tentativas para timeout/5xx/429. 204 → None."""
    ultimo_erro = "erro desconhecido"
    for tentativa in range(busca["tentativas_por_pagina"]):
        try:
            req = urllib.request.Request(url, headers={
                "Accept": "application/json",
                "User-Agent": "radar-eletrico (github.com/feliperbelmonte/radar-eletrico)",
            })
            with urllib.request.urlopen(req, timeout=busca["timeout_segundos"]) as resp:
                if resp.status == 204:
                    return None
                corpo = resp.read()
                return json.loads(corpo) if corpo.strip() else None
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500:
                raise RuntimeError(f"HTTP {e.code}") from None
            ultimo_erro = f"HTTP {e.code}"
        except (urllib.error.URLError, TimeoutError, ConnectionError,
                http.client.HTTPException, json.JSONDecodeError) as e:
            ultimo_erro = f"{type(e).__name__}: {e}"
        if tentativa + 1 < busca["tentativas_por_pagina"]:
            time.sleep(min(60, 5 * 3 ** tentativa))
    raise RuntimeError(ultimo_erro)


def coletar_modalidade(codigo: int, data_final: str, busca: dict, log) -> tuple[list[dict], dict]:
    itens, falhas = [], []
    pagina, total_paginas, seguidas, lidas = 1, None, 0, 0
    while pagina <= busca["max_paginas_por_modalidade"] and (total_paginas is None or pagina <= total_paginas):
        url = API + "?" + urllib.parse.urlencode({
            "dataFinal": data_final, "codigoModalidadeContratacao": codigo,
            "pagina": pagina, "tamanhoPagina": busca["tamanho_pagina"],
        })
        try:
            dados = baixar_json(url, busca)
        except RuntimeError as e:
            falhas.append(f"página {pagina}: {e}")
            log(f"  modalidade {codigo} página {pagina}: falhou ({e})")
            seguidas += 1
            if seguidas >= 3:
                falhas.append("3 páginas seguidas falharam; modalidade interrompida")
                break
            pagina += 1
            continue
        seguidas = 0
        if not dados or not dados.get("data"):
            break
        itens.extend(dados["data"])
        total_paginas = int(dados.get("totalPaginas") or 1)
        lidas += 1
        if pagina == 1 or pagina % 20 == 0:
            log(f"  modalidade {codigo}: página {pagina}/{total_paginas} ({len(itens)} itens)")
        pagina += 1
        time.sleep(busca["pausa_entre_paginas"])
    truncado = total_paginas is not None and total_paginas > busca["max_paginas_por_modalidade"]
    return itens, {
        "codigo": codigo, "nome": MODALIDADES.get(codigo, str(codigo)),
        "paginasLidas": lidas, "totalPaginas": total_paginas, "registros": len(itens),
        "truncado": truncado, "falhas": falhas,
        "ok": lidas > 0 or (total_paginas is None and not falhas),
    }


def coletar(regras: Regras, agora: datetime, fixture: Path | None, log) -> tuple[list[dict], list[dict]]:
    busca = regras.cfg["busca"]
    if fixture:
        bruto = json.loads(fixture.read_text(encoding="utf-8"))
        itens = bruto["data"] if isinstance(bruto, dict) else bruto
        return itens, [{"codigo": 0, "nome": f"fixture {fixture.name}", "paginasLidas": 1,
                        "totalPaginas": 1, "registros": len(itens), "truncado": False,
                        "falhas": [], "ok": True}]
    data_final = (agora.astimezone(BRT) + timedelta(days=busca["dias_a_frente"])).strftime("%Y%m%d")
    todos, stats = [], []
    for codigo in busca["modalidades"]:
        log(f"Modalidade {codigo} ({MODALIDADES.get(codigo, '?')})")
        itens, st = coletar_modalidade(codigo, data_final, busca, log)
        todos.extend(itens)
        stats.append(st)
    return todos, stats


# ---------------------------------------------------------------- saída

def fmt_brl(v: float | None) -> str:
    if v is None:
        return "valor não informado"
    s = f"{v:,.0f}".replace(",", ".")
    return f"R$ {s}"


def fmt_prazo(iso: str | None) -> str:
    dt = parse_data(iso)
    if not dt:
        return "—"
    dt = dt.astimezone(BRT)
    return dt.strftime("%d/%m %Hh%M") if (dt.hour or dt.minute) else dt.strftime("%d/%m")


def nota_da_rodada(stats: list[dict], analisados: int, relevantes: int, agora: datetime) -> dict:
    quando = agora.astimezone(BRT).strftime("%d/%m, %Hh%M")
    ok = [s for s in stats if s["ok"]]
    nomes = ", ".join(s["nome"] for s in stats)
    texto = (f"robô no GitHub consultou a API oficial do PNCP ({nomes}) e analisou "
             f"{analisados} contratações com proposta aberta; {relevantes} passaram nos filtros "
             f"de escopo e prazo futuro.")
    problemas = []
    for s in stats:
        if not s["ok"]:
            problemas.append(f"{s['nome']} falhou ({'; '.join(s['falhas'][-2:]) or 'sem resposta'})")
        elif s["falhas"]:
            problemas.append(f"{s['nome']}: {len(s['falhas'])} página(s) com erro")
        if s["truncado"]:
            problemas.append(f"{s['nome']}: só as primeiras {s['paginasLidas']} de {s['totalPaginas']} páginas foram lidas")
    if problemas:
        texto += " Cobertura parcial: " + "; ".join(problemas) + "."
    nivel = "crit" if not ok else ("atencao" if problemas else "ok")
    return {"nivel": nivel, "titulo": f"Varredura de {quando}:", "texto": texto}


def montar_painel(template: str, itens: list[dict], agora: datetime, nota: dict, cfg: dict) -> str:
    ini, fim = template.find(MARCA_INI), template.find(MARCA_FIM)
    if ini < 0 or fim < 0:
        raise SystemExit("template do painel sem os marcadores LICITACOES_DATA_START/END")

    def js(valor) -> str:  # JSON seguro dentro de <script>
        return (json.dumps(valor, ensure_ascii=False)
                .replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))

    bloco = "\n".join([
        MARCA_INI,
        f"const DATA = {js(itens)};",
        f"const LAST_RUN = {js(agora.astimezone(BRT).isoformat(timespec='seconds'))};",
        f"const NEXT_RUN_LABEL = {js(cfg['saida']['proxima_execucao'])};",
        f"const RUN_NOTE = {js(nota)};",
        "",
    ])
    return template[:ini] + bloco + template[fim:]


def montar_notificacao(itens: list[dict], nota: dict, cfg: dict) -> str:
    titulo = nota["titulo"]
    url = cfg["saida"]["painel_url"]
    if not itens:
        msg = f"{titulo} nenhum edital relevante aberto no momento. Painel: {url}"
    else:
        g1 = sum(1 for i in itens if i["grupo"] == 1)
        g2 = len(itens) - g1
        urg = sum(1 for i in itens if i["status"] == "urgente")
        linhas = [
            f"{titulo} {len(itens)} edita{'l' if len(itens) == 1 else 'is'} relevante{'s' if len(itens) != 1 else ''} "
            f"aberto{'s' if len(itens) != 1 else ''} ({g1} só projeto · {g2} projeto/execução — solar, subestação ou residencial). "
            f"{urg} com prazo em até {cfg['status']['dias_urgente']} dias.",
            "",
            "Destaques:",
        ]
        top = sorted(itens, key=lambda i: (-i["pontuacao"], i["dataEncerramentoProposta"] or "9"))
        for n, i in enumerate(top[: cfg["saida"]["destaques_na_notificacao"]], 1):
            local = f"{i['municipio']}/{i['uf']}" if i["municipio"] else i["uf"]
            objeto = i["objeto"] if len(i["objeto"]) <= 160 else i["objeto"][:160].rsplit(" ", 1)[0] + "…"
            linhas.append(f"{n}. {i['orgao']} ({local}) — {objeto} — {fmt_brl(i['valorEstimado'])} — "
                          f"prazo {fmt_prazo(i['dataEncerramentoProposta'])} — {i['link'] or 'sem link'}")
        linhas += ["", f"Painel: {url}"]
        msg = "\n".join(linhas)
    if nota["nivel"] != "ok":
        msg += "\n\nObs.: " + nota["texto"]
    return msg + "\n"


def montar_readme(itens: list[dict], nota: dict, stats: list[dict]) -> str:
    linhas = ["# Radar Elétrico — última varredura", "", f"**{nota['titulo']}** {nota['texto']}", "",
              "| Status | Prazo | Órgão | Objeto | Valor | Link |", "|---|---|---|---|---|---|"]
    ordem = {"urgente": 0, "atencao": 1, "novo": 2, "normal": 3}
    for i in sorted(itens, key=lambda i: (ordem[i["status"]], i["dataEncerramentoProposta"] or "9")):
        obj = i["objeto"].replace("|", "/")
        linhas.append(f"| {i['status']} | {fmt_prazo(i['dataEncerramentoProposta'])} | {i['orgao'].replace('|', '/')} "
                      f"({i['municipio']}/{i['uf']}) | {obj} | {fmt_brl(i['valorEstimado'])} | "
                      f"{'[PNCP](' + i['link'] + ')' if i['link'] else '—'} |")
    if not itens:
        linhas.append("| — | — | — | Nenhum edital relevante aberto | — | — |")
    linhas += ["", "## Modalidades consultadas", ""]
    for s in stats:
        linhas.append(f"- {s['nome']}: {s['registros']} registros, {s['paginasLidas']}/{s['totalPaginas'] or 0} páginas"
                      + (f", {len(s['falhas'])} falha(s)" if s["falhas"] else ""))
    return "\n".join(linhas) + "\n"


# ---------------------------------------------------------------- main

def executar(saida: Path, config: Path, fixture: Path | None, agora: datetime | None = None, log=print) -> dict:
    regras = carregar_regras(config)
    agora = agora or datetime.now(timezone.utc)
    brutos, stats = coletar(regras, agora, fixture, log)

    vistos, itens, descartes = set(), [], {}
    for bruto in brutos:
        chave = bruto.get("numeroControlePNCP") or json.dumps(bruto, sort_keys=True)[:200]
        if chave in vistos:
            continue
        vistos.add(chave)
        item, motivo = classificar(bruto, regras, agora)
        if item:
            itens.append(item)
        else:
            descartes[motivo] = descartes.get(motivo, 0) + 1

    nota = nota_da_rodada(stats, len(vistos), len(itens), agora)
    saida.mkdir(parents=True, exist_ok=True)
    resultado = {
        "geradoEm": agora.astimezone(BRT).isoformat(timespec="seconds"),
        "analisados": len(vistos),
        "relevantes": len(itens),
        "descartes": descartes,
        "modalidades": stats,
        "nota": nota,
        "itens": itens,
    }
    (saida / "licitacoes.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    template = (RAIZ / "painel" / "template.html").read_text(encoding="utf-8")
    (saida / "painel.html").write_text(montar_painel(template, itens, agora, nota, regras.cfg), encoding="utf-8")
    (saida / "notificacao.txt").write_text(montar_notificacao(itens, nota, regras.cfg), encoding="utf-8")
    (saida / "README.md").write_text(montar_readme(itens, nota, stats), encoding="utf-8")
    log(f"Pronto: {len(vistos)} analisados, {len(itens)} relevantes, descartes {descartes}")
    return resultado


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--saida", type=Path, default=RAIZ / "saida")
    p.add_argument("--config", type=Path, default=RAIZ / "config.toml")
    p.add_argument("--fixture", type=Path, help="JSON com itens no formato da API (roda offline)")
    p.add_argument("--agora", help="data/hora de referência ISO (testes)")
    a = p.parse_args()
    agora = parse_data(a.agora) if a.agora else None
    executar(a.saida, a.config, a.fixture, agora, log=lambda m: print(m, flush=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
