---
name: repo-radar-eletrico
description: Mapa do repositório radar-eletrico — robô no GitHub Actions que varre a API do PNCP por licitações de elétrica/solar para o Felipe e gera o painel publicado pela tarefa agendada da Claude.
---

# radar-eletrico

## O que é

Duas peças:
1. **GitHub Actions** (`.github/workflows/radar.yml`, 09:17 e 19:17 UTC = 06h17/16h17 Brasília) roda `radar.py`: consulta a API oficial do PNCP, filtra pelo `config.toml` e faz force-push do resultado para o branch `dados` (`licitacoes.json`, `painel.html`, `notificacao.txt`, `README.md`).
2. **Tarefa agendada da Claude** (trigger `trig_011ofHaz7uWYbZpgPTCRRYam`, cron `0 11,21 * * *` UTC = 08h/18h) baixa esses arquivos via raw.githubusercontent.com, publica o `painel.html` no Artifact https://claude.ai/code/artifact/3acf32e4-7a26-420c-927e-b638ded6802f e envia a notificação. Prompt em `prompt-tarefa-agendada.md`.

Motivo da divisão: o ambiente da Claude não alcança `pncp.gov.br` (403 no proxy de egress), mas alcança `raw.githubusercontent.com`. Por isso o repositório precisa ser **público** (raw de repo privado exige token).

## Arquivos

| Arquivo | Onde mexer |
|---|---|
| `config.toml` | **Mudar o foco da busca**: escopos (`[[escopo]]`, ordem importa: Grupo 2 antes do Grupo 1), `excluir`, `compra`/`servico`, modalidades, janela, limites |
| `radar.py` | Coleta (`coletar_modalidade`, `baixar_json`), regras (`classificar`), saídas (`montar_painel`, `montar_notificacao`, `montar_readme`) |
| `painel/template.html` | Visual do painel. Não remover os marcadores `/* LICITACOES_DATA_START */` e `/* LICITACOES_DATA_END */` |
| `.github/workflows/radar.yml` | Horário e publicação no branch `dados` |
| `prompt-tarefa-agendada.md` | Prompt da tarefa da Claude (v2). Mudou aqui → `update_trigger` no mesmo passo |
| `tests/test_radar.py`, `tests/fixtures/api_exemplo.json` | Testes offline; fixture no formato da API de consulta |
| `docs/prompt-v1-claude-sozinho.md` | Histórico: prompt antigo em que a Claude buscava sozinha |

## Premissas de negócio

- Felipe: engenheiro eletricista, CREA-PR, CNPJ ME/EPP, CNAE 7112-0/00, começando em licitações.
- Grupo 1 (só projeto/laudo): projeto elétrico, SPDA, NR-10, prontuário, laudos, iluminação. Se o objeto incluir execução/obra → status `atencao`, não descartar.
- Grupo 2 (projeto e/ou execução, tem ART/atestado): solar até 75 kWp, subestação até 1 MVA, instalações elétricas residenciais. Potência citada acima do limite → descarta. Escala grande (plural "usinas"/"subestações" ou valor > R$ 1,5 mi) → `atencao`.
- Prioriza dispensa (limite engenharia ~R$ 130.984,20) e credenciamento — pesa na ordem dos destaques da notificação.
- Só editais com prazo de proposta futuro; sem prazo → descarta.
- Status: `urgente` (≤7 dias) > `atencao` > `novo` (publicado ≤3 dias) > `normal`.

## Como testar

- `python -m unittest discover -s tests` (o workflow também roda antes da varredura).
- Ponta a ponta offline: `python radar.py --saida saida --fixture tests/fixtures/api_exemplo.json --agora 2026-10-29T06:17:00-03:00`.
- Real: aba Actions → "Radar Elétrico" → Run workflow; conferir o branch `dados`.
- Tarefa da Claude: `fire_trigger` com `trig_011ofHaz7uWYbZpgPTCRRYam`.

## Pontos de atenção

- Campos da API usados: `objetoCompra`, `informacaoComplementar`, `dataEncerramentoProposta`, `dataPublicacaoPncp`, `valorTotalEstimado`, `modalidadeId/Nome`, `orgaoEntidade.cnpj/razaoSocial`, `unidadeOrgao.ufSigla/municipioNome/nomeUnidade`, `anoCompra`, `sequencialCompra`, `numeroControlePNCP`. Se a API mudar, ajustar em `classificar`.
- Pregão eletrônico nacional tem muitas páginas; `max_paginas_por_modalidade` limita, e a nota da rodada avisa quando truncou.
- Datas do PNCP vêm sem fuso: tratadas como horário de Brasília (UTC-3).

## Histórico

- 2026-10-29: repositório criado, documentando a v1 (Claude buscando sozinha).
- 2026-10-29: busca movida para GitHub Actions (`radar.py` + `config.toml` + workflow + template do painel); prompt da Claude v2 só publica e notifica. Felipe avisou que o foco da busca vai mudar em breve: fazer isso no `config.toml`.
