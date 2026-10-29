# Radar Elétrico

Robô que varre a API oficial do PNCP (Portal Nacional de Contratações Públicas) duas vezes por dia, filtra as licitações com proposta aberta que interessam a um engenheiro eletricista (projeto elétrico, SPDA, NR-10, solar até 75 kWp, subestação até 1 MVA, instalações residenciais) e gera um painel pronto para publicar.

## Como funciona

```
GitHub Actions (06h17 e 16h17, Brasília)
  └─ radar.py consulta a API do PNCP, aplica os filtros do config.toml
     e grava o resultado no branch "dados":
        licitacoes.json · painel.html · notificacao.txt · README.md
                     │
Tarefa agendada da Claude (08h e 18h, Brasília)
  └─ baixa o painel.html do branch "dados", publica no painel (Claude Artifact)
     e manda a notificação (push + e-mail)
```

A busca roda no GitHub porque o ambiente da Claude não consegue acessar a API do PNCP (bloqueio de rede). A Claude continua responsável só pela publicação no painel e pela notificação.

## Mudar o que o robô procura

Tudo está em [`config.toml`](./config.toml): escopos (termos, grupo, limites de potência), termos que excluem, modalidades consultadas, janela de dias, limites de status. Não é preciso mexer no `radar.py` para mudar o foco da busca.

## Rodar localmente

```bash
python radar.py --saida saida                                    # consulta a API real
python radar.py --saida saida --fixture tests/fixtures/api_exemplo.json --agora 2026-10-29T06:17:00-03:00
python -m unittest discover -s tests                             # testes
```

Só biblioteca padrão do Python 3.11+.

## Arquivos

| Arquivo | O que é |
|---|---|
| `radar.py` | Coleta (API PNCP, com novas tentativas), classificação e geração das saídas |
| `config.toml` | Filtros e parâmetros da busca |
| `painel/template.html` | Painel HTML; o bloco entre `LICITACOES_DATA_START/END` é reescrito a cada rodada |
| `.github/workflows/radar.yml` | Agendamento no GitHub Actions e publicação no branch `dados` |
| `prompt-tarefa-agendada.md` | Prompt da tarefa agendada da Claude (publica e notifica) |
| `tests/` | Testes offline e dados de exemplo no formato da API |
| `docs/prompt-v1-claude-sozinho.md` | Versão anterior, em que a Claude fazia a busca sozinha |
