# Farmácia Brasil — Consulta de Balcão

Dashboard de apoio ao atendimento no balcão da Farmácia Brasil: busca de medicamentos, ficha/bula resumida com link para o Bulário da ANVISA, comparativo entre remédios e busca por doença/sintoma.

App 100% client-side (HTML + JSON). Funciona:
- **Local:** servido por `farmacia_dashboard.py` na porta **8775**.
- **Online:** GitHub Pages.

## ⚠️ Aviso importante

Ferramenta de **apoio**. **Não substitui** o farmacêutico responsável nem a prescrição médica. A base de dados é uma **versão inicial curada** e deve ser **validada pelo farmacêutico responsável** antes do uso real. A bula completa e oficial está no **Bulário Eletrônico da ANVISA**.

## Dados

- `medicamentos.json` — base de medicamentos (princípio ativo, classe, tarja, indicações, enfermidades, contraindicações, alertas).
- Fontes previstas: **ANVISA (Dados Abertos)** e **ABCFarma** (via importadores no projeto).

## Tarjas

- 🟢 **Livre** — isento de prescrição (MIP), venda livre
- 🔴 **Vermelha** — venda sob prescrição médica
- 🔴 **Vermelha (retenção)** — antibióticos, com retenção de receita
- ⚫ **Preta / Controlada** — Notificação de Receita (Portaria 344/98)
