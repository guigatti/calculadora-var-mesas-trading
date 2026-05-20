"""
app.py
======
Calculadora de VaR para Ações e Opções — Gestão de Mesas de Trading
Projeto Final do curso de Gestão de Risco e Derivativos.

Página inicial. As demais páginas estão em pages/ e aparecem
automaticamente na barra lateral.
"""
import streamlit as st

st.set_page_config(
    page_title="Calculadora de VaR — Mesas de Trading",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# INICIALIZAÇÃO DO SESSION STATE
# ============================================================
# Mantém estado entre páginas — fundamental para fluxo coerente.
if 'posicoes' not in st.session_state:
    st.session_state['posicoes'] = None
if 'precos' not in st.session_state:
    st.session_state['precos'] = None
if 'retornos' not in st.session_state:
    st.session_state['retornos'] = None
if 'parametros' not in st.session_state:
    st.session_state['parametros'] = {
        'nivel_confianca': 0.95,
        'horizonte_dias': 1,
        'metodologia': 'Paramétrico (Normal)',
        'lambda_ewma': 0.94,
        'n_simulacoes': 10_000,
        'taxa_juros': 0.115,
        'data_inicio': '2023-01-01',
    }

# ============================================================
# CABEÇALHO
# ============================================================
st.title("📊 Calculadora de VaR para Mesas de Trading")
st.subheader("Gestão de Risco de Mercado — Projeto Final")

st.markdown("""
Esta aplicação simula o funcionamento de uma **área de risco de mercado**
responsável por acompanhar diferentes mesas de trading. Cada mesa possui
posições próprias e um limite de **Value at Risk (VaR)** aprovado pela
diretoria. A área de risco deve monitorar diariamente se cada mesa está
operando dentro do limite autorizado.
""")

st.divider()

# ============================================================
# CARDS DE FUNCIONALIDADES
# ============================================================
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 📋 Cadastro de Posições")
    st.markdown("""
    - Upload de Excel/CSV
    - Cadastro manual de mesas
    - Template para download
    - Validação automática
    """)

with col2:
    st.markdown("### 📈 Cálculo de VaR")
    st.markdown("""
    - VaR Histórico
    - VaR Paramétrico (Normal)
    - VaR Monte Carlo
    - Component VaR
    - Expected Shortfall
    """)

with col3:
    st.markdown("### 🎯 Opções e Greeks")
    st.markdown("""
    - Black-Scholes-Merton
    - Greeks completos (Δ, Γ, ν, Θ, ρ)
    - Quatro abordagens de VaR
    - Stress test com vol implícita
    """)

st.divider()

# ============================================================
# COMO USAR
# ============================================================
st.markdown("### 🚀 Como Usar")
st.markdown("""
1. **Cadastro de Posições** — faça upload do seu arquivo Excel ou use o template; alternativamente, cadastre manualmente as mesas
2. **Parâmetros de Risco** — defina nível de confiança, horizonte temporal, metodologia e janela de dados
3. **Cálculo de VaR** — execute o motor sobre cada mesa e veja a decomposição por ativo
4. **VaR de Opções** — compare as quatro abordagens (Delta, Delta-Gamma, Full Valuation, Monte Carlo)
5. **Monitoramento de Limites** — veja quais mesas estão em zona verde/amarela/vermelha
6. **Stress Testing** — aplique cenários históricos (Joesley, COVID, Eleições)
7. **Dashboard Executivo** — visão consolidada para reporte à diretoria

Use o menu lateral à esquerda para navegar entre as páginas.
""")

# ============================================================
# STATUS DA SESSÃO
# ============================================================
st.divider()
st.markdown("### 📊 Status da Sessão")

col_s1, col_s2, col_s3 = st.columns(3)
with col_s1:
    if st.session_state.get('posicoes') is not None:
        n_pos = len(st.session_state['posicoes'])
        n_mesas = st.session_state['posicoes']['mesa'].nunique()
        st.metric("Posições cadastradas", f"{n_pos}", f"{n_mesas} mesas")
    else:
        st.metric("Posições cadastradas", "0", "Pendente")

with col_s2:
    if st.session_state.get('precos') is not None:
        n_dias = len(st.session_state['precos'])
        n_tickers = st.session_state['precos'].shape[1]
        st.metric("Dados de mercado", f"{n_dias} dias", f"{n_tickers} tickers")
    else:
        st.metric("Dados de mercado", "—", "Pendente")

with col_s3:
    params = st.session_state.get('parametros', {})
    nc = params.get('nivel_confianca', 0.95)
    met = params.get('metodologia', 'Paramétrico')
    st.metric("Configuração", f"VaR {nc*100:.0f}%", met)

# ============================================================
# CITAÇÃO E RODAPÉ
# ============================================================
st.divider()
st.markdown(
    "> *\"All models are wrong, but some are useful.\"* — George Box"
)
st.caption(
    "**Limitações estruturais reconhecidas:** todo VaR assume que o passado "
    "representa o futuro. O VaR Paramétrico subestima caudas; o Histórico não "
    "captura eventos ausentes da janela; o Monte Carlo herda o risco de modelo "
    "da dinâmica GBM. O stress testing existe como complemento obrigatório, "
    "não substituto, dessa limitação estrutural."
)
