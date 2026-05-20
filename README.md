# Calculadora de VaR para Mesas de Trading

Aplicação Streamlit para cálculo, monitoramento e interpretação do Value at
Risk (VaR) de carteiras compostas por ações e opções, organizadas em mesas
de trading. Projeto final do curso de Gestão de Risco e Derivativos.

## Funcionalidades

- **Cadastro de Posições** via upload Excel/CSV ou inserção manual, com template para download
- **Três Metodologias de VaR** para ações: Histórico, Paramétrico Normal (com Component VaR), Monte Carlo
- **Quatro Abordagens de VaR** para opções: Delta, Delta-Gamma, Full Valuation Histórico, Monte Carlo com reprecificação
- **Greeks Analíticos** completos via Black-Scholes-Merton (Delta, Gamma, Vega, Theta, Rho)
- **Monitoramento de Limites** com classificação verde/amarelo/vermelho e gauges interativos
- **Stress Testing** com cenários históricos (Joesley Day, COVID Crash, Eleições 2018) e cenários personalizados
- **Dashboard Executivo** com KPIs consolidados e exportação Excel/CSV

## Estrutura do Projeto

```
streamlit_app/
├── app.py                                    # Página inicial
├── pages/
│   ├── 1_📋_Cadastro_de_Posições.py
│   ├── 2_⚙️_Parâmetros_de_Risco.py
│   ├── 3_📈_Cálculo_de_VaR.py
│   ├── 4_🎯_VaR_de_Opções.py
│   ├── 5_🚦_Monitoramento_de_Limites.py
│   ├── 6_⚡_Stress_Testing.py
│   └── 7_📊_Dashboard_Executivo.py
├── utils/
│   ├── risk_engine.py                        # Motor de cálculo (VaR, BS, Greeks)
│   └── data_loader.py                        # Ingestão yfinance + template
├── .streamlit/
│   └── config.toml                           # Configuração visual
├── requirements.txt                          # Dependências
└── README.md
```

## Como Executar Localmente

```bash
# Instalar dependências
pip install -r requirements.txt

# Rodar a aplicação
streamlit run app.py
```

A aplicação abrirá no navegador em `http://localhost:8501`.

## Como Fazer Deploy no Streamlit Cloud

### Passo 1 — Criar repositório no GitHub

1. Crie uma conta gratuita em [github.com](https://github.com) (se ainda não tiver)
2. Clique em **"New repository"**
3. Dê um nome (ex: `calculadora-var-mesas-trading`)
4. Marque como **público** (Streamlit Cloud gratuito exige repositório público)
5. Não inicialize com README (usaremos o nosso)
6. Clique em **"Create repository"**

### Passo 2 — Subir os arquivos

Há duas formas:

**Via interface web (mais simples para o projeto):**
1. Na página do repositório vazio, clique em **"uploading an existing file"**
2. Arraste **toda a estrutura de pastas** (app.py, pages/, utils/, .streamlit/, requirements.txt, README.md)
3. Escreva um commit message: `Versão inicial da calculadora de VaR`
4. Clique em **"Commit changes"**

**Via Git (se já tem familiaridade):**
```bash
cd streamlit_app
git init
git add .
git commit -m "Versão inicial da calculadora de VaR"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/calculadora-var-mesas-trading.git
git push -u origin main
```

### Passo 3 — Conectar ao Streamlit Cloud

1. Acesse [share.streamlit.io](https://share.streamlit.io)
2. Faça login com sua conta GitHub (autoriza o Streamlit Cloud a acessar seus repositórios)
3. Clique em **"New app"** (ou **"Create app"**)
4. Em **"Repository"**, selecione `SEU_USUARIO/calculadora-var-mesas-trading`
5. Em **"Branch"**, mantenha `main`
6. Em **"Main file path"**, digite `app.py`
7. Em **"App URL (optional)"**, escolha um identificador único — esse será o link do app:
   - Exemplo: `calculadora-var-mesas-trading` → URL final: `calculadora-var-mesas-trading.streamlit.app`
8. Clique em **"Deploy!"**

O deploy leva entre 2 e 5 minutos na primeira execução, enquanto o Streamlit Cloud instala todas as dependências do `requirements.txt`. Acompanhe os logs em tempo real na própria página.

### Passo 4 — Validação

Quando o status mudar para **"Your app is in the air!"**, abra a URL pública. A aplicação estará rodando 24/7 e pode ser acessada por qualquer pessoa com o link.

**Checklist de validação após deploy:**

- [ ] Página inicial carrega sem erros
- [ ] Página "Cadastro de Posições" — botão de download do template funciona
- [ ] Página "Parâmetros de Risco" — download de dados via yfinance funciona
- [ ] Página "Cálculo de VaR" — exibe os números das três metodologias
- [ ] Página "VaR de Opções" — exibe as cinco variantes comparadas
- [ ] Página "Monitoramento de Limites" — gauges renderizam corretamente
- [ ] Página "Stress Testing" — heatmap de cenários × mesas aparece
- [ ] Página "Dashboard Executivo" — exportação Excel funciona

## Fluxo de Uso Recomendado para Apresentação

1. **Abrir o link no navegador** (página inicial carrega)
2. **Cadastro de Posições** → "Usar dados do template" → "Carregar"
3. **Parâmetros de Risco** → manter padrões → "Baixar dados e calcular covariância"
4. **Cálculo de VaR** → selecionar mesa "Ações Brasil" → mostrar comparação entre metodologias e Component VaR
5. **VaR de Opções** → selecionar "Volatilidade" → mostrar diferença entre Delta-Only e MC vega-aware
6. **Monitoramento de Limites** → ver gauges e alertas
7. **Stress Testing** → aplicar cenário Joesley Day → ver heatmap completo
8. **Dashboard Executivo** → ver KPIs consolidados, respostas às perguntas do enunciado, baixar Excel

## Limitações Estruturais (a apresentar com honestidade)

- Todo VaR assume que o passado representa o futuro
- VaR Paramétrico subestima caudas (curtose > 0 em retornos reais)
- VaR Histórico não captura eventos ausentes da janela
- Monte Carlo herda risco de modelo da dinâmica GBM (volatilidade constante)
- Stress testing é complemento obrigatório, não substituto do VaR

> *"All models are wrong, but some are useful."* — George Box

## Tecnologias

- **Streamlit** 1.40 — interface web
- **Pandas / NumPy** — manipulação de dados
- **SciPy** — funções estatísticas (CDF normal, percentis)
- **yfinance** — dados de mercado via Yahoo Finance
- **Plotly** — visualizações interativas
- **openpyxl** — leitura/escrita de Excel

## Sobre o Projeto

Projeto desenvolvido para o curso de **Gestão de Risco e Derivativos**.
A aplicação reproduz o fluxo operacional de uma área de risco de mercado
em uma instituição financeira de médio porte, com tratamento profissional
de ações e opções, e respeitando o framework prudencial de Basileia.
