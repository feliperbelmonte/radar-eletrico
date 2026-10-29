# Radar Elétrico

Dois robôs para um engenheiro eletricista que presta serviço de projeto:

1. **Radar de licitações** (`radar.py`, 2x por dia): varre a API oficial do PNCP e filtra licitações com proposta aberta (projeto elétrico, SPDA, NR-10, solar até 75 kWp, subestação até 1 MVA, instalações residenciais).
2. **Prospecção de empresas** (`leads.py`, 1x por mês): lista empresas de instalação elétrica (dados abertos de CNPJ da Receita Federal) que podem terceirizar projeto, com uma mensagem curta pronta e um botão para abrir o WhatsApp. O envio é sempre manual, uma empresa de cada vez.

## Prospecção de empresas

- Plano de automação do contato (WhatsApp/e-mail) e checklist: [`docs/automacao-whatsapp.md`](./docs/automacao-whatsapp.md).

- Filtros em [`prospeccao.toml`](./prospeccao.toml): CNAE (padrão 4321-5/00), porte, MEI, anos de atividade, UFs, prioridade por UF/cidade, quantidade no painel e os modelos de mensagem.
- O workflow `leads.yml` roda todo dia 20 (a Receita atualiza a base uma vez por mês) e publica no branch `leads` o painel **criptografado** (`painel.html.enc`), porque a lista tem telefones e este repositório é público. A chave fica no secret `LEADS_KEY`.
- O painel (Claude Artifact) guarda o andamento de cada empresa (contatado, respondeu, cliente, sem interesse) e mostra a meta de contatos do dia.
- Quem pedir para não receber mais mensagens deve ser marcado como "Sem interesse".

## Radar de licitações

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
| `leads.py` | Prospecção: baixa e filtra os dados abertos de CNPJ, gera o painel de empresas |
| `prospeccao.toml` | Filtros e mensagens da prospecção |
| `prospeccao/template.html` | Painel de prospecção; o bloco entre `LEADS_DATA_START/END` é reescrito a cada lista |
| `.github/workflows/leads.yml` | Agendamento semanal, criptografia e publicação no branch `leads` |
| `skills/` | Skills do funil de prospecção, com as lições aprendidas de cada etapa |
