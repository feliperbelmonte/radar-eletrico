---
name: repo-radar-eletrico
description: Mapa do repositório radar-eletrico — robôs no GitHub Actions do Felipe: radar de licitações de elétrica/solar no PNCP (2x/dia) e prospecção mensal de empresas de instalação elétrica (dados abertos de CNPJ) para oferecer serviço de projeto.
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
| `prospeccao.toml` | **Mudar o público da prospecção**: CNAEs, porte, MEI, UFs, prioridade, mensagens |
| `leads.py`, `prospeccao/template.html`, `.github/workflows/leads.yml`, `tests/test_leads.py` | Prospecção de empresas (ver seção própria) |

## Prospecção de empresas (leads)

- `leads.py` + `prospeccao.toml` + `prospeccao/template.html` + `.github/workflows/leads.yml` (toda segunda, 12:23 UTC, e manual; a base da Receita muda 1x por mês).
- Fonte: dados abertos de CNPJ da Receita (`Estabelecimentos0-9.zip`, `Empresas0-9.zip`, `Simples.zip`, `Municipios.zip`, pasta mensal `AAAA-MM`). Desde 2025 ficam num compartilhamento Nextcloud: WebDAV em `https://arquivos.receitafederal.gov.br/public.php/dav/files/<token>/` (PROPFIND com Basic auth `<token>:`). O caminho antigo `/dados/cnpj/dados_abertos_cnpj/` dá 404. Tokens em `[fonte].compartilhamentos` (mudam de tempos em tempos); espelho casadosdados é reserva. Nem a Receita nem o espelho são acessíveis do ambiente da Claude, só do Actions.
- Filtro padrão: segmentos `[[segmento]]` (instalação elétrica 4321500, arquitetura 7111100, construtora 4120400, engenharia 7112000, montagem industrial 3321000/4292802, redes 4221902/4221903, iluminação 4329104, climatização 4322302), situação ativa (02), todos os portes (Felipe pediu para incluir empresas maiores), sem MEI, ≥1 ano, com celular (9 dígitos começando com 9, ou 8 dígitos 6-9 sem o nono dígito). Um contato por CNPJ básico, preferindo a matriz. Ordem: cidades de `[prioridade].cidades` ("NOME/UF": região de Curitiba e litoral do PR primeiro), depois UFs (PR, SC, ...); Felipe prefere o PR porque o CREA dele é de lá (mora em Jaraguá do Sul/SC), ordem dos segmentos, CNAE principal, porte maior primeiro, com e-mail, mais antigas.
- Mensagem: um de 3 modelos em `[[mensagem]]` (serviço = projeto elétrico em geral, não só solar), escolhido pelo hash do CNPJ, com `{atividade}` do segmento; o painel monta o link `https://wa.me/55<ddd><cel>?text=...`. **Envio sempre manual** (decisão do Felipe, 29/10/2026): nada de disparo automático (risco de banimento do número, LGPD).
- Repo público + telefones: o workflow criptografa `painel.html` → `painel.html.enc` (`openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt`, senha no secret `LEADS_KEY`) e publica no branch `leads` com `resumo.json` (só contagens). Para abrir: `openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -in painel.html.enc -out painel.html -pass env:LEADS_KEY`.
- Painel: Artifact https://claude.ai/artifact/BAJojSBRshrr1MRC4Eoujg com capability `db` (regra: só owner/editores leem e escrevem). Coleção `status`, um documento por CNPJ: `status` (a_contatar, contatado, respondeu, qualificado, proposta, cliente, sem_interesse), `quando`, `contatadoEm`, `nota`, `empresa`, `segmento`, `uf`, `cidade`, `modelo`. Republicar com a mesma `url` mantém os status.
- Skills do funil em `skills/` (prospeccao-funil, -captacao, -resposta, -qualificacao, -proposta): cada uma tem "Lições aprendidas"; o procedimento de revisão está na prospeccao-funil. Atualizou uma skill → entregar o SKILL.md ao Felipe e commitar aqui.

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

- 2026-10-30: painel ganhou a aba "Fila de hoje" (15 novas + follow-ups vencidos, campo `followupEm`); tarefa `trig_01MFZpZoBARsPm33RxiFzMc5` manda push da fila seg–sex 08h37; check-in dos retornos na conversa do Felipe seg–sex 17h47. Detalhes em `docs/automacao-whatsapp.md`.

- 2026-10-29: skills do funil de prospecção (captação, resposta, qualificação, proposta e visão geral com o ciclo de aprendizado); painel ganhou status qualificado/proposta e grava segmento, região e modelo de mensagem em cada status.
- 2026-10-29: prioridade da prospecção: PR primeiro (CREA-PR), começando por Curitiba e litoral (mais perto de Jaraguá do Sul/SC, onde Felipe mora), depois SC; coleta semanal.
- 2026-10-29: 1ª rodada da prospecção falhou (404 no caminho antigo da Receita); download passou para o WebDAV do compartilhamento Nextcloud.
- 2026-10-29: 1ª rodada real do radar: API respondeu nas 5 modalidades (~25 mil contratações, ~55 min), 105 relevantes. Falsos positivos vinham de citações de passagem na informação complementar: escopo, exclusões e compra/serviço agora olham só o `objetoCompra`; novas exclusões (vigilância, seguro, poda, ar-condicionado, cursos...). Tarefa agendada da Claude passou para o prompt v2.
- 2026-10-29: repositório criado, documentando a v1 (Claude buscando sozinha).
- 2026-10-29: prospecção de empresas (leads.py, prospeccao.toml, painel com status em db, workflow mensal criptografado). Felipe quer renda extra fazendo só projeto (sem execução) para empresas de instalação elétrica.
- 2026-10-29: busca movida para GitHub Actions (`radar.py` + `config.toml` + workflow + template do painel); prompt da Claude v2 só publica e notifica. Felipe avisou que o foco da busca vai mudar em breve: fazer isso no `config.toml`.
