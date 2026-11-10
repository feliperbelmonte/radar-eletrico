#!/usr/bin/env python3
"""Abertura das conversas novas do dia no WhatsApp Web (roteiro: prospeccao/envio-whatsapp.md).

O Felipe só aperta Enter; a Claude abre cada conversa com a mensagem já escrita.

  fila    → as empresas novas de hoje (mesma regra da "Fila de hoje" do painel: cotas por trilha,
            ordem de prioridade, descontando quem já foi contatado hoje), com o link do WhatsApp Web
            e a mensagem com "Bom dia/Boa tarde/Boa noite" aplicada.
  marcar  → monta o documento de status "contatado" de uma empresa (para o ArtifactData "set").

Uso:
  python prospeccao/envio.py fila   --painel index.html --status DIR [--agora ISO] [--meta 15]
  python prospeccao/envio.py marcar --painel index.html --cnpj CNPJ --saida DIR [--status DIR] [--pulada "motivo"]
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

BRT = timezone(timedelta(hours=-3))
ORDEM_TRILHAS = ("licitacao", "pericia", "projeto")


def ler_painel(painel: Path) -> tuple[list[dict], dict]:
    txt = painel.read_text(encoding="utf-8")
    m = re.search(r"const LEADS = (\[.*?\]);\nconst RESUMO = .*?;\nconst FILA = (\{.*?\});\n", txt, re.S)
    if not m:
        raise SystemExit("painel sem o bloco LEADS/RESUMO/FILA")
    return json.loads(m.group(1)), json.loads(m.group(2))


def ler_colecao(pasta: Path | None) -> dict[str, dict]:
    if not pasta or not pasta.exists():
        return {}
    return {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in sorted(pasta.glob("*.json"))}


def saudacao(agora: datetime) -> str:
    h = agora.astimezone(BRT).hour
    return "Bom dia" if h < 12 else "Boa tarde" if h < 18 else "Boa noite"


def dia_brt(iso: str | None):
    if not iso:
        return None
    try:
        t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return (t.astimezone(BRT) if t.tzinfo else t).date()
    except ValueError:
        return None


def trilha(l: dict) -> str:
    return l.get("trilha") or "projeto"


def montar_fila(leads: list[dict], fila_cfg: dict, status: dict, agora: datetime, meta: int | None = None) -> list[dict]:
    hoje = agora.astimezone(BRT).date()
    meta = meta or fila_cfg.get("meta") or 15
    cotas = {"licitacao": fila_cfg.get("licitacao", 5), "pericia": fila_cfg.get("pericia", 4),
             "projeto": fila_cfg.get("projeto", 6)}
    feitos_por: dict[str, int] = {}
    feitos = 0
    for l in leads:
        if dia_brt(status.get(l["cnpj"], {}).get("contatadoEm")) == hoje:
            feitos += 1
            feitos_por[trilha(l)] = feitos_por.get(trilha(l), 0) + 1
    vagas = max(0, meta - feitos)
    livres = {t: [] for t in ORDEM_TRILHAS}
    for l in leads:
        if status.get(l["cnpj"], {}).get("status", "a_contatar") == "a_contatar" and l.get("celular"):
            livres.get(trilha(l), livres["projeto"]).append(l)
    escolhidos: list[dict] = []
    for t in ORDEM_TRILHAS:
        n = max(0, cotas.get(t, 0) - feitos_por.get(t, 0))
        for l in livres[t][:n]:
            if len(escolhidos) < vagas:
                escolhidos.append(l)
    for t in ORDEM_TRILHAS:
        for l in livres[t]:
            if len(escolhidos) >= vagas:
                break
            if l not in escolhidos:
                escolhidos.append(l)
    escolhidos.sort(key=lambda l: ORDEM_TRILHAS.index(trilha(l)) if trilha(l) in ORDEM_TRILHAS else 9)
    sd = saudacao(agora)
    out = []
    for l in escolhidos:
        msg = l["mensagem"].replace("{saudacao}", sd)
        if msg.startswith("Bom dia!"):  # mensagens antigas de perícia geradas com "Bom dia!" fixo
            msg = sd + msg[len("Bom dia"):]
        out.append({"cnpj": l["cnpj"], "empresa": l["empresa"], "cidade": f'{l.get("cidade", "")}/{l.get("uf", "")}',
                    "trilha": trilha(l), "mensagem": msg, "inicio": msg[:40],
                    "url": f'https://web.whatsapp.com/send?phone=55{l["celular"]}&text={quote(msg)}'})
    return out


def doc_contatado(l: dict, agora: datetime, atual: dict | None = None, pulada: str | None = None) -> dict:
    iso = agora.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    d = {**(atual or {}), "empresa": l.get("empresa", ""), "segmento": l.get("segmento", ""), "uf": l.get("uf", ""),
         "cidade": l.get("cidade", ""), "modelo": l.get("modelo", 0), "trilha": trilha(l), "quando": iso}
    if l.get("celular"):
        d["celular"] = l["celular"]
    if pulada:
        d["status"] = "pulada"
        d["nota"] = pulada[:200]
    else:
        d["status"] = "contatado"
        d["contatadoEm"] = iso
        d["enviadoPor"] = "chrome"
    return d


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a1 = sub.add_parser("fila")
    a1.add_argument("--painel", type=Path, required=True)
    a1.add_argument("--status", type=Path, required=True)
    a1.add_argument("--agora")
    a1.add_argument("--meta", type=int)
    a2 = sub.add_parser("marcar")
    a2.add_argument("--painel", type=Path, required=True)
    a2.add_argument("--cnpj", required=True)
    a2.add_argument("--saida", type=Path, required=True)
    a2.add_argument("--status", type=Path)
    a2.add_argument("--agora")
    a2.add_argument("--pulada", help="motivo para marcar como pulada (ex.: número sem WhatsApp)")
    a = ap.parse_args(argv)
    agora = datetime.fromisoformat(a.agora) if a.agora else datetime.now(timezone.utc)
    if agora.tzinfo is None:
        agora = agora.replace(tzinfo=BRT)
    leads, fila_cfg = ler_painel(a.painel)
    if a.cmd == "fila":
        itens = montar_fila(leads, fila_cfg, ler_colecao(a.status), agora, a.meta)
        out = Path(a.status).parent / "fila_envio.json"
        out.write_text(json.dumps(itens, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"# {len(itens)} conversas para abrir (detalhes com url em {out})")
        for n, i in enumerate(itens, 1):
            print(f'{n}. {i["cnpj"]} | {i["empresa"]} | {i["cidade"]} | {i["trilha"]}')
        return 0
    cnpj = re.sub(r"\D", "", a.cnpj)
    l = next((x for x in leads if x["cnpj"] == cnpj), None)
    if not l:
        raise SystemExit(f"{cnpj} não está no painel")
    atual = ler_colecao(a.status).get(cnpj) if a.status else None
    d = doc_contatado(l, agora, atual, a.pulada)
    a.saida.mkdir(parents=True, exist_ok=True)
    f = a.saida / f"{cnpj}.json"
    f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"collection": "status", "doc_id": cnpj, "file_path": str(f.resolve()), "existe": atual is not None}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
