# Leitor diário do DOU — Reforma Tributária e legislação tributária

Todo dia útil, este robô baixa o Diário Oficial da União completo pelo **INLABS** (serviço
oficial e gratuito da Imprensa Nacional), lê ato por ato e separa o que interessa:

| Nível | O que entra |
|---|---|
| **Reforma Tributária** | CBS, IBS, Imposto Seletivo, CGIBS, LC 214/2025, LC 227/2026, EC 132/2023, split payment, DeRE… em qualquer órgão |
| **Tributário — normativo** | Leis, decretos, INs, atos conjuntos, soluções de consulta, convênios/ajustes do Confaz etc. com tema tributário |
| **Tributário — outros** | Demais atos da Receita, PGFN, Confaz, CARF, CGSN… (exceto pessoal e rotina) |

Roda **na nuvem do GitHub, de graça** — não precisa deixar computador ligado.
Horários (seg a sex): 06h40, 16h00 e 19h30 (as duas últimas pegam as edições extras).

O resultado fica gravado no próprio repositório:

- `boletins/AAAA-MM-DD.md` — boletim do dia, legível no próprio site do GitHub
- `dados/AAAA-MM-DD.json` e `dados/ultimos.json` — os mesmos dados, para a tarefa do Claude
  ler, resumir, juntar com as notícias oficiais e te notificar.

---

## Instalação (uns 15 minutos, uma vez só)

> **INLABS fora do ar ou sem cadastro?** O robô funciona mesmo assim: sem login (ou com o
> INLABS em manutenção) ele lê a página pública de leitura do DOU em in.gov.br. Essa página traz
> título, órgão e o trecho inicial de cada ato; o INLABS traz o texto completo, por isso vale
> cadastrar quando ele voltar.

### 1. Cadastro no INLABS (recomendado, mas opcional)
1. Acesse **https://inlabs.in.gov.br** e clique em cadastrar.
2. Confirme o e-mail. Guarde o e-mail e a senha — vão no passo 3.

### 2. Repositório
Já criado e com o código: este repositório (`schimittiago/monitor-tributario`).

### 3. Guardar o login do INLABS como segredo
No repositório: **Settings → Secrets and variables → Actions → New repository secret**
- Nome `INLABS_EMAIL` → valor: seu e-mail do INLABS
- Nome `INLABS_SENHA` → valor: sua senha do INLABS

### 4. Testar
**Actions** → (se pedir, clique em *I understand… enable them*) → **Leitor DOU tributário**
→ **Run workflow** → **Run workflow**. Em 1–2 minutos deve ficar verde ✅ e aparecer
o arquivo do dia na pasta `boletins/`.

- ❌ "Login no INLABS falhou" → confira os Secrets do passo 3.
- ❌ erro no "git push" → **Settings → Actions → General → Workflow permissions →
  Read and write permissions** → Save.

### 5. Pronto
As tarefas agendadas do Claude (8h e 17h30) já leem `dados/ultimos.json` deste repositório.

---

## Ajustes

- **Termos e órgãos**: edite `termos.yaml` direto no GitHub (ícone de lápis). Cada linha é um termo.
- **Seções**: em `termos.yaml`, `secoes` (padrão DO1 e DO1E). Acrescente `DO2`, `DO3` se quiser.
- **Horários**: linhas `cron` em `.github/workflows/monitor.yml` (estão em UTC = Brasília + 3h).
- **Reprocessar um dia**: Actions → Run workflow → preencha a data `AAAA-MM-DD`
  (o INLABS guarda os últimos 4 meses).

Observação: o GitHub desativa agendamentos de repositórios sem nenhuma atividade por 60 dias.
Como o robô faz commits todo dia útil, isso não deve acontecer; se acontecer, o GitHub manda
e-mail e basta clicar em "Enable".

## Teste local (opcional)
```bash
pip install -r requirements.txt
python tests/gerar_exemplo.py /tmp/zips
python monitor_dou.py --data 2026-11-13 --pasta-xml /tmp/zips
```
