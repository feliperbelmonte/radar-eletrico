#!/usr/bin/env python3
"""Triagem diária das conversas de WhatsApp da prospecção (roteiro: prospeccao/triagem-whatsapp.md).

Faz a parte mecânica para a Claude gastar tokens só lendo as conversas:

  lista   → cruza o painel (telefones) com o banco (status/triagem) e imprime, enxuto,
            quem conferir no WhatsApp Web hoje e a sugestão padrão de cada um.
  gravar  → valida os achados da Claude (JSON) e monta os arquivos para o ArtifactData
            "batch" na coleção "triagem" (só documentos novos: nunca altera status).

Uso:
  python prospeccao/triagem.py lista  --painel painel.html --status DIR --triagem DIR [--hoje AAAA-MM-DD]
  python prospeccao/triagem.py gravar --painel painel.html --achados achados.json --saida DIR [--agora ISO]

DIR = pasta onde o ArtifactData (action list, out_dir) salvou a coleção (um <id>.json por documento).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BRT = timezone(timedelta(hours=-3))
ATIVOS = ("contatado", "respondeu", "qualificado", "proposta")   # conversas em andamento
SUGERIVEIS = ("contatado", "respondeu", "qualificado", "proposta", "cliente", "futuro", "sem_interesse")
DIAS_SILENCIO = 10      # dias úteis depois do follow-up sem resposta → sugestão padrão
DIAS_FUTURO = 60        # retomada padrão de quem pediu "mais pra frente"
DIAS_FUTURO_SILENCIO = 90
MAX_RASCUNHO = 600
MAX_LOTE = 50


# ---------- datas ----------
def dia_brt(iso: str | None) -> date | None:
    if not iso:
        return None
    s = str(iso)
    try:
        if "T" in s:
            t = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return (t.astimezone(BRT) if t.tzinfo else t).date()
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def dias_uteis(ini: date, fim: date) -> int:
    n, d = 0, ini
    while d < fim:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def ddmm(d: date | None) -> str:
    return d.strftime("%d/%m") if d else "-"


# ---------- leitura ----------
def ler_leads(painel: Path) -> dict[str, dict]:
    txt = painel.read_text(encoding="utf-8")
    m = re.search(r"const LEADS = (\[.*?\]);\nconst RESUMO", txt, re.S)
    if not m:
        raise SystemExit("painel sem o bloco 'const LEADS = [...]' (é o painel.html decifrado ou o index.html do artifact?)")
    return {l["cnpj"]: l for l in json.loads(m.group(1))}


def ler_colecao(pasta: Path | None) -> dict[str, dict]:
    if not pasta or not pasta.exists():
        return {}
    return {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in sorted(pasta.glob("*.json"))}


def fone_wa(cel: str) -> str:
    """Como o WhatsApp Web mostra um número não salvo: +55 41 99999-8888."""
    c = re.sub(r"\D", "", cel or "")
    if len(c) == 11:
        return f"+55 {c[:2]} {c[2:7]}-{c[7:]}"
    if len(c) == 10:
        return f"+55 {c[:2]} {c[2:6]}-{c[6:]}"
    return "+55 " + c


def pendentes_triagem(triagem: dict[str, dict]) -> dict[str, dict]:
    p: dict[str, dict] = {}
    for d in triagem.values():
        if d.get("resolvido") or not d.get("cnpj"):
            continue
        if d["cnpj"] not in p or str(d.get("em", "")) > str(p[d["cnpj"]].get("em", "")):
            p[d["cnpj"]] = d
    return p


def ultima_vista(triagem: dict[str, dict]) -> dict[str, str]:
    """Data da última mensagem da empresa já triada (para não sugerir de novo a mesma coisa)."""
    v: dict[str, str] = {}
    for d in triagem.values():
        c, u = d.get("cnpj"), d.get("ultimaMsgEm") or ""
        if c and u > v.get(c, ""):
            v[c] = u
    return v


# ---------- regra padrão (sem ler a conversa) ----------
def sugestao_padrao(m: dict, hoje: date) -> dict | None:
    if m.get("status") != "contatado":
        return None
    fu = dia_brt(m.get("followupEm"))
    if not fu or dias_uteis(fu, hoje) < DIAS_SILENCIO:
        return None
    if m.get("retomadoEm"):
        return {"status": "sem_interesse", "motivo": "Sem resposta nem depois da retomada: encerrar."}
    return {"status": "futuro", "retomarEm": (hoje + timedelta(days=DIAS_FUTURO_SILENCIO)).isoformat(),
            "motivo": f"Sem resposta {DIAS_SILENCIO}+ dias úteis depois do follow-up: tentar uma vez daqui a 3 meses."}


def montar_lista(leads: dict, status: dict, triagem: dict, hoje: date) -> tuple[list[dict], dict]:
    pend = pendentes_triagem(triagem)
    vista = ultima_vista(triagem)
    itens, cont = [], {"conferir": 0, "com_sugestao_pendente": 0, "sem_telefone": 0}
    for cnpj, m in status.items():
        if m.get("status") not in ATIVOS or not m.get("contatadoEm"):
            continue
        if cnpj in pend:
            cont["com_sugestao_pendente"] += 1
            continue
        l = leads.get(cnpj) or {}
        cel = l.get("celular") or m.get("celular")
        if not cel:
            cont["sem_telefone"] += 1   # saiu da lista semanal antes de o painel guardar o número: buscar pelo nome
        ce = dia_brt(m.get("contatadoEm"))
        itens.append({
            "cnpj": cnpj, "fone": fone_wa(cel) if cel else "BUSCAR PELO NOME", "empresa": m.get("empresa") or l.get("empresa", ""),
            "cidade": f'{l.get("cidade") or m.get("cidade", "")}/{l.get("uf") or m.get("uf", "")}', "status": m["status"],
            "contatado": ddmm(ce), "followup": ddmm(dia_brt(m.get("followupEm"))),
            "jaVista": vista.get(cnpj, ""), "padrao": sugestao_padrao(m, hoje),
        })
    # quem tem conversa mais quente primeiro, depois os mais antigos
    peso = {"proposta": 0, "qualificado": 1, "respondeu": 2, "contatado": 3}
    itens.sort(key=lambda i: (peso[i["status"]], status[i["cnpj"]].get("contatadoEm", "")))
    cont["conferir"] = len(itens)
    return itens, cont


# ---------- gravar ----------
_RE_FONE = re.compile(r"(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}")
_RE_MAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def limpar(txt: str | None, n: int) -> str:
    t = _RE_MAIL.sub("[e-mail]", _RE_FONE.sub("[telefone]", str(txt or ""))).strip()
    return t[:n]


def validar(a: dict, leads: dict, hoje: date) -> tuple[dict | None, str | None]:
    cnpj = re.sub(r"\D", "", str(a.get("cnpj", "")))
    if cnpj not in leads:
        return None, f"{cnpj or '?'}: CNPJ fora do painel e do banco"
    st = a.get("status")
    if st not in SUGERIVEIS:
        return None, f"{cnpj}: status inválido {st!r}"
    d = {"cnpj": cnpj, "empresa": leads[cnpj].get("empresa", ""), "status": st,
         "motivo": limpar(a.get("motivo"), 300)}
    if not d["motivo"]:
        return None, f"{cnpj}: falta o motivo"
    if a.get("rascunho"):
        d["rascunho"] = limpar(a["rascunho"], MAX_RASCUNHO)
    if a.get("nota"):
        d["nota"] = limpar(a["nota"], 200)
    if st == "futuro":
        r = dia_brt(a.get("retomarEm")) or hoje + timedelta(days=DIAS_FUTURO)
        if r <= hoje:
            return None, f"{cnpj}: retomarEm precisa ser futuro"
        d["retomarEm"] = r.isoformat()
    if a.get("ultimaMsgEm"):
        d["ultimaMsgEm"] = str(a["ultimaMsgEm"])[:25]
    return d, None


def montar_gravacao(achados: list[dict], leads: dict, agora: datetime, saida: Path) -> tuple[list[list[dict]], list[str], dict]:
    hoje = agora.astimezone(BRT).date()
    carimbo = agora.astimezone(BRT).strftime("%Y%m%d%H%M")
    saida.mkdir(parents=True, exist_ok=True)
    writes, erros, cont, vistos = [], [], {}, set()
    for a in achados:
        d, err = validar(a, leads, hoje)
        if err:
            erros.append(err)
            continue
        if d["cnpj"] in vistos:
            erros.append(f'{d["cnpj"]}: repetido, fiquei com o primeiro')
            continue
        vistos.add(d["cnpj"])
        d["em"] = agora.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        d["origem"] = "triagem-whatsapp"
        doc_id = f'{d["cnpj"]}-{carimbo}'
        arq = saida / f"{doc_id}.json"
        arq.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        writes.append({"op": "set", "collection": "triagem", "doc_id": doc_id, "file_path": str(arq.resolve())})
        cont[d["status"]] = cont.get(d["status"], 0) + 1
    lotes = [writes[i:i + MAX_LOTE] for i in range(0, len(writes), MAX_LOTE)]
    for n, lote in enumerate(lotes, 1):
        (saida / f"lote{n}.json").write_text(json.dumps(lote, ensure_ascii=False), encoding="utf-8")
    return lotes, erros, cont


def resumo_notificacao(cont: dict) -> str:
    rot = {"respondeu": "responderam", "qualificado": "qualificadas", "proposta": "em proposta", "cliente": "clientes",
           "futuro": "para contato futuro", "sem_interesse": "para descartar", "contatado": "com nova mensagem sugerida"}
    partes = [f"{n} {rot[k]}" for k, n in sorted(cont.items(), key=lambda x: -x[1]) if n]
    return ", ".join(partes) if partes else "nenhuma novidade"


# ---------- CLI ----------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a1 = sub.add_parser("lista")
    a1.add_argument("--painel", type=Path, required=True)
    a1.add_argument("--status", type=Path, required=True)
    a1.add_argument("--triagem", type=Path)
    a1.add_argument("--hoje")
    a1.add_argument("--json", action="store_true", help="saída em JSON em vez de linhas")
    a2 = sub.add_parser("gravar")
    a2.add_argument("--painel", type=Path, required=True)
    a2.add_argument("--status", type=Path, help="pasta da coleção status (aceita empresas que saíram da lista semanal)")
    a2.add_argument("--achados", type=Path, required=True)
    a2.add_argument("--saida", type=Path, required=True)
    a2.add_argument("--agora")
    a = ap.parse_args(argv)

    leads = ler_leads(a.painel)
    if a.cmd == "lista":
        hoje = date.fromisoformat(a.hoje) if a.hoje else datetime.now(BRT).date()
        itens, cont = montar_lista(leads, ler_colecao(a.status), ler_colecao(a.triagem), hoje)
        if a.json:
            print(json.dumps({"hoje": hoje.isoformat(), "contagem": cont, "itens": itens}, ensure_ascii=False))
            return 0
        print(f"# Triagem {ddmm(hoje)} — conferir {cont['conferir']} conversas "
              f"(já com sugestão pendente no painel: {cont['com_sugestao_pendente']}; sem número guardado, buscar pelo nome da empresa: {cont['sem_telefone']})")
        print("# cnpj | número no WhatsApp | empresa | cidade | status | 1º contato | follow-up | última msg já triada | padrão se não houver resposta nova")
        for i in itens:
            p = i["padrao"]
            pad = f'{p["status"]}{" " + p["retomarEm"] if p.get("retomarEm") else ""}' if p else "-"
            print(f'{i["cnpj"]} | {i["fone"]} | {i["empresa"]} | {i["cidade"]} | {i["status"]} | {i["contatado"]} | '
                  f'{i["followup"]} | {i["jaVista"] or "-"} | {pad}')
        return 0

    agora = datetime.fromisoformat(a.agora) if a.agora else datetime.now(timezone.utc)
    if agora.tzinfo is None:
        agora = agora.replace(tzinfo=BRT)
    achados = json.loads(a.achados.read_text(encoding="utf-8"))
    if isinstance(achados, dict):
        achados = achados.get("achados", [])
    for c, m in ler_colecao(getattr(a, "status", None)).items():
        leads.setdefault(c, {"cnpj": c, "empresa": m.get("empresa", "")})
    lotes, erros, cont = montar_gravacao(achados, leads, agora, a.saida)
    for e in erros:
        print("ERRO", e, file=sys.stderr)
    print(json.dumps({"lotes": [str((a.saida / f"lote{n}.json").resolve()) for n in range(1, len(lotes) + 1)],
                      "documentos": sum(len(l) for l in lotes), "erros": len(erros), "contagem": cont,
                      "resumo": resumo_notificacao(cont)}, ensure_ascii=False))
    return 1 if erros and not lotes else 0


if __name__ == "__main__":
    raise SystemExit(main())
