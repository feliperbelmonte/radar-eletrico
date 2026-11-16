# Prompt da tarefa "Prospecção Elétrica — demandas em plataformas" (todo dia, 07h41)

> Tarefa `trig_01YF5Y5vQwziDM2dueEhNnf3`. Roteiro detalhado: skill `skills/prospeccao-plataformas/SKILL.md`.

## Histórico de decisões

- 05/11/2026 — Criada para rodar terça e quinta às 07h41: busca demandas na Workana e no 99Freelas pelo navegador embutido do app Claude e grava as novas na coleção `demandas` do painel Prospecção Elétrica. Somente leitura nas plataformas.
- 16/11/2026 — O Felipe teve o cadastro de freelancer aprovado na Workana e pediu:
  - varredura **todo dia** pelo navegador (agenda mudou para `CRON_TZ=America/Sao_Paulo 41 7 * * *`);
  - só serviço de **projeto/home office**: ele não quer sair de casa para nada (visita técnica, levantamento em campo, instalação, diária presencial ficam fora);
  - não faz projeto arquitetônico (recebe pronto e trabalha em BIM no QiBuilder); demanda mista entra só pela parte elétrica.
  - Na mesma conversa foi feita uma varredura manual: 15 termos, 123 demandas únicas na Workana, ~20 no escopo. Método de leitura atualizado para o JSON `results-initials` (ver Lições da skill).

## Passo a passo do que a tarefa faz

1. Abre o navegador embutido do app Claude no computador do Felipe (sem controle do computador; se pedir login/captcha, avisa por push e encerra).
2. Busca na Workana (JSON `results-initials`, até 5 páginas por termo, mais a busca por habilidade Engenharia Elétrica) e no 99Freelas, com os termos da skill.
3. Filtra pelo escopo home office e abre a página de cada demanda que entra (só leitura).
4. Grava as novas na coleção `demandas` do painel (https://claude.ai/artifact/BAJojSBRshrr1MRC4Eoujg), sem alterar as que já existem.
5. Manda uma notificação de uma linha com o total do dia e o destaque.

## Prompt atual (16/11/2026)

```
Ver o prompt completo na tarefa agendada (list_triggers). Resumo dos blocos: contexto e decisão de 16/11 (diário, home office, somente leitura) · NAVEGADOR (embutido, sem controle do computador, push se pedir login) · PASSO 1 Buscar (Workana via results-initials, 99Freelas via links, 14 termos) · PASSO 2 Filtrar (lista do que entra e do que fica fora) · PASSO 3 Gravar no banco do painel (coleção demandas, só novas) · PASSO 4 Mensagem final de uma linha.
```
