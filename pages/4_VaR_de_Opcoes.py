"""
pages/4_🎯_VaR_de_Opções.py
============================
Tratamento dedicado para mesas com opções. Implementa as quatro abordagens
canônicas de VaR para opções, com comparação numérica e visual.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.risk_engine import (
    BlackScholes,
    var_opcoes_delta, var_opcoes_delta_gamma,
    var_opcoes_full_valuation_historico, var_opcoes_montecarlo,
)
from utils.session_init import init_session_state

st.set_page_config(page_title="VaR de Opções", page_icon="🎯", layout="wide")

init_session_state()

st.title("🎯 VaR de Opções — Quatro Abordagens Comparadas")
st.markdown(
    "Análise dedicada para mesas com opções. As quatro abordagens canônicas — "
    "Delta, Delta-Gamma, Full Valuation Histórico e Monte Carlo — não são "
    "intercambiáveis. Formam uma hierarquia de qualidade e revelam onde "
    "aproximações simples falham."
)

# ============================================================
# VALIDAÇÕES
# ============================================================
if st.session_state.get('posicoes') is None:
    st.error("❌ Posições não cadastradas.")
    st.stop()
if st.session_state.get('retornos') is None:
    st.error("❌ Dados de mercado não carregados.")
    st.stop()

posicoes     = st.session_state['posicoes']
retornos     = st.session_state['retornos']
cov_amostral = st.session_state['cov_amostral']
params       = st.session_state['parametros']

opcoes = posicoes[posicoes['tipo'].isin(['call', 'put'])].copy()

if opcoes.empty:
    st.warning(
        "⚠️ Nenhuma posição em opções encontrada. Esta página é dedicada a mesas "
        "com calls e puts. Use o template completo (com a mesa de Volatilidade) "
        "para ver esta análise em ação."
    )
    st.stop()

# ============================================================
# UTILITÁRIO: normaliza tickers de underlying → formato yfinance
# ============================================================
def _normalizar_ticker(ticker: str, colunas_retornos: set) -> str:
    """
    Tenta casar o ticker do cadastro com as colunas de retornos carregadas.
    Ordem de tentativa:
      1. Exato                  → 'PETR4.SA' já existe
      2. Com sufixo .SA         → 'PETR4'    vira 'PETR4.SA'
      3. Sem sufixo .SA         → 'PETR4.SA' vira 'PETR4'
    Se não encontrar nenhum, retorna o original (o validador do risk_engine
    vai reportar o ticker faltante com mensagem clara).
    """
    if ticker in colunas_retornos:
        return ticker
    com_sa = ticker + '.SA'
    if com_sa in colunas_retornos:
        return com_sa
    sem_sa = ticker.replace('.SA', '')
    if sem_sa in colunas_retornos:
        return sem_sa
    return ticker  # mantém original — será reportado como ausente


# ============================================================
# SELEÇÃO DA MESA DE OPÇÕES
# ============================================================
mesas_opcoes = opcoes['mesa'].unique().tolist()
mesa_op = st.selectbox(
    "Selecione a mesa de opções",
    mesas_opcoes,
    help="Cada mesa de opções é analisada com as quatro abordagens em separado."
)

df_mesa_op  = opcoes[opcoes['mesa'] == mesa_op].copy()
limite_op   = df_mesa_op['limite_var'].iloc[0]

# ── Normalização de tickers ────────────────────────────────
cols_retornos = set(retornos.columns)
df_mesa_op['underlying'] = df_mesa_op['underlying'].apply(
    lambda t: _normalizar_ticker(t, cols_retornos)
)

# Avisa se ainda houver underlyings sem dados após a normalização
underlyings_sem_dados = [
    u for u in df_mesa_op['underlying'].unique()
    if u not in cols_retornos
]
if underlyings_sem_dados:
    st.warning(
        f"⚠️ **Underlyings sem dados históricos carregados:** "
        f"`{', '.join(underlyings_sem_dados)}`\n\n"
        "Opções desses subjacentes serão ignoradas nos cálculos de VaR "
        "Histórico e Monte Carlo. Verifique o formato do ticker no cadastro "
        "(deve ser igual ao retornado pelo yfinance, ex: `PETR4.SA`) e "
        "recarregue os dados em **Parâmetros de Risco**."
    )

# T_anos calculado aqui — evita depender da coluna existir no cadastro
df_mesa_op['T_anos'] = df_mesa_op['vencimento_dias_uteis'] / 252

# ============================================================
# OVERVIEW DA MESA
# ============================================================
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Mesa", mesa_op)
with col2:
    st.metric("Opções", len(df_mesa_op))
with col3:
    st.metric("Limite VaR", f"R$ {limite_op:,.2f}")

st.markdown("**Estrutura da mesa:**")
display_cols = ['ativo', 'tipo', 'underlying', 'strike',
                'vencimento_dias_uteis', 'vol_implicita',
                'quantidade', 'preco', 'valor_posicao']
display_cols = [c for c in display_cols if c in df_mesa_op.columns]
st.dataframe(df_mesa_op[display_cols], use_container_width=True, hide_index=True)

# ============================================================
# GREEKS AGREGADOS POR SUBJACENTE
# ============================================================
st.divider()
st.subheader("📐 Greeks Agregados por Subjacente")
st.caption(
    "Os Greeks agregados são a foto operacional que uma mesa de opções olha o "
    "dia inteiro. Gamma negativo indica perfil short-vol; vega negativo, "
    "sensibilidade adversa a aumentos de volatilidade implícita."
)

greeks_list = []
for sub in df_mesa_op['underlying'].unique():
    df_sub  = df_mesa_op[df_mesa_op['underlying'] == sub]
    delta_t = gamma_t = vega_t = theta_t = 0
    for _, op in df_sub.iterrows():
        bs = BlackScholes(
            S=op['preco_subjacente'], K=op['strike'],
            T=op['T_anos'],
            r=params['taxa_juros'], sigma=op['vol_implicita'],
            tipo=op['tipo']
        )
        delta_t += op['quantidade'] * bs.delta
        gamma_t += op['quantidade'] * bs.gamma
        vega_t  += op['quantidade'] * bs.vega
        theta_t += op['quantidade'] * bs.theta
    S0 = df_sub['preco_subjacente'].iloc[0]
    greeks_list.append({
        'Subjacente': sub,
        'S0 (R$)': S0,
        'Δ Delta (R$/+1%S)': delta_t * S0 / 100,
        'Γ Gamma (R$/(+1%S)²)': gamma_t * (S0 ** 2) / 10000,
        'ν Vega (R$/+1%vol)': vega_t,
        'Θ Theta (R$/dia)': theta_t,
    })

df_greeks = pd.DataFrame(greeks_list)
st.dataframe(
    df_greeks.style.format({
        'S0 (R$)': 'R$ {:,.2f}',
        'Δ Delta (R$/+1%S)': 'R$ {:,.2f}',
        'Γ Gamma (R$/(+1%S)²)': 'R$ {:,.2f}',
        'ν Vega (R$/+1%vol)': 'R$ {:,.2f}',
        'Θ Theta (R$/dia)': 'R$ {:,.2f}',
    }).background_gradient(
        subset=['Δ Delta (R$/+1%S)', 'Γ Gamma (R$/(+1%S)²)',
                'ν Vega (R$/+1%vol)', 'Θ Theta (R$/dia)'],
        cmap='RdYlGn'
    ),
    use_container_width=True, hide_index=True
)

# ============================================================
# CÁLCULO DAS QUATRO ABORDAGENS
# ============================================================
st.divider()
st.subheader("🔬 Comparação das Quatro Abordagens de VaR")

with st.spinner("Calculando as cinco variantes (Delta, Delta-Gamma, Full Val Hist, MC vol const, MC vega-aware)..."):

    r_delta = var_opcoes_delta(
        df_mesa_op, cov_amostral,
        nivel_confianca=params['nivel_confianca'],
        horizonte_dias=params['horizonte_dias'],
        taxa_juros=params['taxa_juros']
    )

    try:
        r_dg = var_opcoes_delta_gamma(
            df_mesa_op, retornos,
            nivel_confianca=params['nivel_confianca'],
            horizonte_dias=params['horizonte_dias'],
            taxa_juros=params['taxa_juros'],
            n_simulacoes=params['n_simulacoes'], seed=42
        )
    except ValueError as e:
        st.error(f"**Delta-Gamma:** {e}")
        st.stop()

    try:
        r_fvh = var_opcoes_full_valuation_historico(
            df_mesa_op, retornos,
            nivel_confianca=params['nivel_confianca'],
            horizonte_dias=params['horizonte_dias'],
            taxa_juros=params['taxa_juros']
        )
    except ValueError as e:
        st.error(f"**Full Valuation Histórico:** {e}")
        st.stop()

    try:
        r_mc_const = var_opcoes_montecarlo(
            df_mesa_op, retornos,
            nivel_confianca=params['nivel_confianca'],
            horizonte_dias=params['horizonte_dias'],
            taxa_juros=params['taxa_juros'],
            n_simulacoes=params['n_simulacoes'],
            chocar_vol=False, seed=42
        )
        r_mc_vega = var_opcoes_montecarlo(
            df_mesa_op, retornos,
            nivel_confianca=params['nivel_confianca'],
            horizonte_dias=params['horizonte_dias'],
            taxa_juros=params['taxa_juros'],
            n_simulacoes=params['n_simulacoes'],
            chocar_vol=True, vol_choque_anual=0.10, seed=42
        )
    except ValueError as e:
        st.error(f"**Monte Carlo:** {e}")
        st.stop()

# ── Tabela de resultados ───────────────────────────────────
comparacao = pd.DataFrame([
    {'Abordagem': r_delta['metodologia'],    'VaR (R$)': r_delta['var_financeiro']},
    {'Abordagem': r_dg['metodologia'],       'VaR (R$)': r_dg['var_financeiro']},
    {'Abordagem': r_fvh['metodologia'],      'VaR (R$)': r_fvh['var_financeiro']},
    {'Abordagem': r_mc_const['metodologia'], 'VaR (R$)': r_mc_const['var_financeiro']},
    {'Abordagem': r_mc_vega['metodologia'],  'VaR (R$)': r_mc_vega['var_financeiro']},
])
comparacao['Razão vs. Delta'] = (
    comparacao['VaR (R$)'] / r_delta['var_financeiro']
    if r_delta['var_financeiro'] > 0 else np.nan
)
comparacao['% Limite'] = comparacao['VaR (R$)'] / limite_op * 100

st.dataframe(
    comparacao.style.format({
        'VaR (R$)': 'R$ {:,.2f}',
        'Razão vs. Delta': '{:.2f}x',
        '% Limite': '{:.2f}%',
    }).background_gradient(subset=['VaR (R$)'], cmap='YlOrRd'),
    use_container_width=True, hide_index=True
)

# ============================================================
# GRÁFICO COMPARATIVO
# ============================================================
cores = ['#d62728', '#ff7f0e', '#2ca02c', '#1f77b4', '#9467bd']
fig = go.Figure()
fig.add_trace(go.Bar(
    x=comparacao['Abordagem'],
    y=comparacao['VaR (R$)'],
    marker_color=cores,
    text=[f"R$ {v:,.0f}" for v in comparacao['VaR (R$)']],
    textposition='outside',
))
fig.add_hline(
    y=limite_op, line=dict(color='red', dash='dash', width=2),
    annotation_text=f"Limite: R$ {limite_op:,.0f}",
    annotation_position='top right'
)
fig.update_layout(
    title=(
        f"VaR {params['nivel_confianca']*100:.0f}% — {mesa_op}<br>"
        "<sub>A aproximação Delta subestima sistematicamente em carteiras "
        "com gamma significativo</sub>"
    ),
    yaxis_title='VaR (R$)',
    template='plotly_white', height=480, showlegend=False
)
fig.update_yaxes(tickformat=',.0f')
st.plotly_chart(fig, use_container_width=True)

# ============================================================
# DISTRIBUIÇÃO DE P&L
# ============================================================
st.divider()
st.subheader("📊 Distribuição de P&L — Delta-Gamma vs. Monte Carlo")

fig_pnl = go.Figure()
fig_pnl.add_trace(go.Histogram(
    x=r_dg['pnl_simulado'], nbinsx=80,
    name='Delta-Gamma (aproximação)',
    marker_color='orange', opacity=0.55
))
fig_pnl.add_trace(go.Histogram(
    x=r_mc_const['pnl_simulado'], nbinsx=80,
    name='Monte Carlo (full valuation)',
    marker_color='steelblue', opacity=0.55
))
fig_pnl.add_vline(
    x=-r_dg['var_financeiro'],
    line=dict(color='orange', width=2, dash='dash'),
    annotation_text=f"VaR DG = R$ {r_dg['var_financeiro']:,.0f}",
    annotation_position='top left'
)
fig_pnl.add_vline(
    x=-r_mc_const['var_financeiro'],
    line=dict(color='steelblue', width=2, dash='dash'),
    annotation_text=f"VaR MC = R$ {r_mc_const['var_financeiro']:,.0f}",
    annotation_position='top right'
)
fig_pnl.update_layout(
    title='Distribuição de P&L Simulado',
    xaxis_title='P&L (R$)', yaxis_title='Frequência',
    template='plotly_white', height=460, barmode='overlay'
)
fig_pnl.update_xaxes(tickformat=',.0f')
st.plotly_chart(fig_pnl, use_container_width=True)

st.info(
    "💡 **Interpretação:** a cauda esquerda mais pesada no Monte Carlo (azul) "
    "reflete o **gamma negativo** da mesa — para carteiras short-gamma, o "
    "Delta-Gamma (laranja) subestima sistematicamente a perda em movimentos "
    "grandes do subjacente. Para mesas com long-gamma, o padrão se inverte: "
    "cauda direita mais pesada (ganhos potenciais maiores que a aproximação prevê)."
)

# ============================================================
# RECOMENDAÇÃO METODOLÓGICA
# ============================================================
st.divider()
st.subheader("📋 Recomendação Metodológica")

gamma_total = sum(df_greeks['Γ Gamma (R$/(+1%S)²)'])
vega_total  = sum(df_greeks['ν Vega (R$/+1%vol)'])

if r_delta['var_financeiro'] > 0:
    razao_mc_delta = r_mc_vega['var_financeiro'] / r_delta['var_financeiro']
else:
    razao_mc_delta = float('nan')

if abs(gamma_total) > 1000 or abs(vega_total) > 1000:
    st.warning(
        f"⚠️ **A mesa {mesa_op} apresenta sensibilidades não-lineares significativas:**\n\n"
        f"- **Gamma agregado:** R$ {gamma_total:,.2f} por (+1%S)²\n"
        f"- **Vega agregado:** R$ {vega_total:,.2f} por +1pp vol\n\n"
        f"**Recomendação:** adotar **Monte Carlo vega-aware** como métrica oficial "
        f"(VaR = R$ {r_mc_vega['var_financeiro']:,.2f}). A aproximação Delta-Only "
        f"subestima o risco em {razao_mc_delta:.1f}× neste caso — "
        f"inaceitável para reporte ao comitê de risco."
    )
else:
    st.success(
        "✅ A mesa tem sensibilidades não-lineares moderadas. Delta-Gamma ou "
        "Full Valuation Histórico são adequados como métrica de gestão diária."
    )

# ============================================================
# SALVAR
# ============================================================
if 'resultados_opcoes' not in st.session_state:
    st.session_state['resultados_opcoes'] = {}

st.session_state['resultados_opcoes'][mesa_op] = {
    'var_delta':        r_delta['var_financeiro'],
    'var_delta_gamma':  r_dg['var_financeiro'],
    'var_full_val_hist': r_fvh['var_financeiro'],
    'var_mc_const':     r_mc_const['var_financeiro'],
    'var_mc_vega':      r_mc_vega['var_financeiro'],
    'var_oficial':      r_mc_vega['var_financeiro'],
    'limite':           limite_op,
    'greeks':           df_greeks.to_dict('records'),
}

st.info(f"💾 Resultados de **{mesa_op}** salvos para o Dashboard Executivo.")
