"""
pages/3_📈_Cálculo_de_VaR.py
============================
Cálculo de VaR por mesa nas três metodologias, com decomposição
Component VaR e visualizações comparativas.
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
    calcular_retornos_carteira, var_historico, var_historico_ewma,
    var_parametrico, var_monte_carlo_acoes, component_var,
    expected_shortfall_historico, expected_shortfall_normal,
)
from utils.session_init import init_session_state

st.set_page_config(page_title="Cálculo de VaR", page_icon="📈", layout="wide")

# Inicializa session_state se necessário (multi-page navigation safety)
init_session_state()

st.title("📈 Cálculo de VaR por Mesa")
st.markdown(
    "Cálculo do VaR para cada mesa usando as três metodologias canônicas. "
    "Inclui decomposição Component VaR e Expected Shortfall."
)

# Validações
if st.session_state.get('posicoes') is None:
    st.error("❌ Posições não cadastradas. Vá para **Cadastro de Posições**.")
    st.stop()
if st.session_state.get('retornos') is None:
    st.error("❌ Dados de mercado não carregados. Vá para **Parâmetros de Risco**.")
    st.stop()

posicoes = st.session_state['posicoes']
retornos = st.session_state['retornos']
cov_amostral = st.session_state['cov_amostral']
cov_ewma = st.session_state['cov_ewma']
params = st.session_state['parametros']

# Filtrar apenas posições de ações (opções têm página dedicada)
posicoes_acoes = posicoes[posicoes['tipo'] == 'acao'].copy()
mesas_acoes = posicoes_acoes['mesa'].unique().tolist()

if not mesas_acoes:
    st.warning(
        "⚠️ Nenhuma posição em ações encontrada. Esta página calcula VaR para "
        "mesas com ações. Para opções, use a página **VaR de Opções**."
    )
    st.stop()

# ============================================================
# SELEÇÃO DE MESA
# ============================================================
mesa_selecionada = st.selectbox(
    "Selecione a mesa para análise detalhada",
    mesas_acoes,
    help="Cada mesa é avaliada individualmente. O dashboard executivo consolida todas."
)

df_mesa = posicoes_acoes[posicoes_acoes['mesa'] == mesa_selecionada].copy()
limite_mesa = df_mesa['limite_var'].iloc[0]

# Exposições e pesos (suporta long/short)
df_mesa['valor_posicao'] = df_mesa['quantidade'] * df_mesa['preco']
exposicoes = df_mesa.set_index('ativo')['valor_posicao']
valor_bruto = exposicoes.abs().sum()
valor_liquido = exposicoes.sum()
pesos = exposicoes / valor_bruto

# ============================================================
# CABEÇALHO DA MESA
# ============================================================
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Mesa", mesa_selecionada)
with col2:
    st.metric("Posições", len(df_mesa))
with col3:
    st.metric("Exposição Bruta", f"R$ {valor_bruto:,.2f}")
with col4:
    st.metric("Limite VaR", f"R$ {limite_mesa:,.2f}")

st.markdown("**Posições da mesa:**")
st.dataframe(
    df_mesa[['ativo', 'tipo', 'quantidade', 'preco', 'valor_posicao', 'limite_var']],
    use_container_width=True, hide_index=True
)

st.divider()

# ============================================================
# CÁLCULO DAS TRÊS METODOLOGIAS
# ============================================================
st.subheader("Cálculo das Três Metodologias")

with st.spinner("Calculando VaR pelas três metodologias..."):
    # Retornos da carteira
    retornos_carteira = calcular_retornos_carteira(retornos, pesos)

    # VaR Histórico
    r_hist = var_historico(
        retornos_carteira, valor_bruto,
        params['nivel_confianca'], params['horizonte_dias']
    )
    # VaR Histórico EWMA
    r_hist_ewma = var_historico_ewma(
        retornos_carteira, valor_bruto,
        params['nivel_confianca'], 0.97, params['horizonte_dias']
    )
    # VaR Paramétrico Normal (amostral)
    r_param = var_parametrico(
        pesos, cov_amostral, valor_bruto,
        params['nivel_confianca'], params['horizonte_dias']
    )
    # VaR Paramétrico EWMA
    r_param_ewma = var_parametrico(
        pesos, cov_ewma, valor_bruto,
        params['nivel_confianca'], params['horizonte_dias']
    )
    # VaR Monte Carlo
    qtd = df_mesa.set_index('ativo')['quantidade']
    precos_atuais = df_mesa.set_index('ativo')['preco']
    cov_filtrada = cov_amostral.loc[qtd.index, qtd.index]
    r_mc = var_monte_carlo_acoes(
        precos_atuais, qtd, cov_filtrada,
        n_simulacoes=params['n_simulacoes'],
        nivel_confianca=params['nivel_confianca'],
        horizonte_dias=params['horizonte_dias'],
        seed=42
    )

    # Expected Shortfall
    es_hist = expected_shortfall_historico(retornos_carteira, valor_bruto, 0.975)
    es_normal = expected_shortfall_normal(pesos, cov_amostral, valor_bruto, 0.975)

# ============================================================
# TABELA DE RESULTADOS
# ============================================================
st.markdown("#### Resultados Comparativos")
resultados = pd.DataFrame([
    {'Metodologia': r_hist['metodologia'],
     'VaR (R$)': r_hist['var_financeiro'],
     '% Carteira': r_hist['var_pct'] * 100},
    {'Metodologia': r_hist_ewma['metodologia'],
     'VaR (R$)': r_hist_ewma['var_financeiro'],
     '% Carteira': r_hist_ewma['var_pct'] * 100},
    {'Metodologia': r_param['metodologia'],
     'VaR (R$)': r_param['var_financeiro'],
     '% Carteira': r_param['var_pct'] * 100},
    {'Metodologia': 'Paramétrico EWMA',
     'VaR (R$)': r_param_ewma['var_financeiro'],
     '% Carteira': r_param_ewma['var_pct'] * 100},
    {'Metodologia': r_mc['metodologia'],
     'VaR (R$)': r_mc['var_financeiro'],
     '% Carteira': r_mc['var_pct'] * 100},
])
resultados['% Limite'] = resultados['VaR (R$)'] / limite_mesa * 100

st.dataframe(
    resultados.style.format({
        'VaR (R$)': 'R$ {:,.2f}',
        '% Carteira': '{:.2f}%',
        '% Limite': '{:.2f}%',
    }).background_gradient(subset=['VaR (R$)'], cmap='YlOrRd'),
    use_container_width=True, hide_index=True
)

# ============================================================
# EXPECTED SHORTFALL
# ============================================================
st.markdown("#### Expected Shortfall (97.5%)")
col_es1, col_es2 = st.columns(2)
with col_es1:
    st.metric(
        "ES Histórico (média da cauda)",
        f"R$ {es_hist['es_financeiro']:,.2f}",
        delta=f"{(es_hist['es_financeiro']/r_hist['var_financeiro'] - 1)*100:+.1f}% vs VaR Hist 95%"
    )
with col_es2:
    st.metric(
        "ES Normal (fórmula fechada)",
        f"R$ {es_normal['es_financeiro']:,.2f}",
        delta=f"{(es_normal['es_financeiro']/r_param['var_financeiro'] - 1)*100:+.1f}% vs VaR Param 95%"
    )

st.caption(
    "💡 O ES (Expected Shortfall, também CVaR) é a média das perdas que excedem "
    "o VaR. Sob o FRTB (Basileia IV), o ES a 97,5% substitui o VaR a 99% como "
    "métrica regulatória, por ser uma medida coerente de risco (subaditividade)."
)

st.divider()

# ============================================================
# GRÁFICO COMPARATIVO
# ============================================================
st.markdown("#### Comparação Visual entre Metodologias")

fig = go.Figure()
cores = ['#1f77b4', '#9467bd', '#ff7f0e', '#d62728', '#2ca02c']
fig.add_trace(go.Bar(
    x=resultados['Metodologia'],
    y=resultados['VaR (R$)'],
    marker_color=cores,
    text=[f"R$ {v:,.0f}" for v in resultados['VaR (R$)']],
    textposition='outside',
))
fig.add_hline(
    y=limite_mesa, line=dict(color='red', dash='dash', width=2),
    annotation_text=f"Limite: R$ {limite_mesa:,.0f}",
    annotation_position='top right'
)
fig.update_layout(
    title=f"VaR {params['nivel_confianca']*100:.0f}% — Mesa {mesa_selecionada}",
    yaxis_title='VaR (R$)',
    template='plotly_white', height=460, showlegend=False
)
fig.update_yaxes(tickformat=',.0f')
st.plotly_chart(fig, use_container_width=True)

# ============================================================
# COMPONENT VaR
# ============================================================
st.divider()
st.subheader("🎯 Decomposição por Component VaR")
st.caption(
    "O Component VaR atribui a cada ativo sua contribuição exata ao VaR total — "
    "soma-se exatamente ao VaR da carteira. Ativos com Component VaR > peso "
    "financeiro são consumidores desproporcionais de risco."
)

cvar_df = component_var(
    pesos, cov_amostral, valor_bruto,
    params['nivel_confianca'], params['horizonte_dias']
)

if not cvar_df.empty:
    # Tabela
    cvar_display = cvar_df[['ativo', 'peso', 'component_var_financeiro', 'contribuicao_pct']].copy()
    cvar_display.columns = ['Ativo', 'Peso (%)', 'Component VaR (R$)', 'Contribuição (%)']
    cvar_display['Peso (%)'] = cvar_display['Peso (%)'] * 100
    st.dataframe(
        cvar_display.style.format({
            'Peso (%)': '{:+.2f}%',
            'Component VaR (R$)': 'R$ {:,.2f}',
            'Contribuição (%)': '{:.2f}%',
        }),
        use_container_width=True, hide_index=True
    )

    # Gráfico peso vs. contribuição
    fig_cv = go.Figure()
    fig_cv.add_trace(go.Bar(
        name='Peso financeiro (%)', x=cvar_df['ativo'],
        y=cvar_df['peso'] * 100, marker_color='steelblue'
    ))
    fig_cv.add_trace(go.Bar(
        name='Contribuição ao VaR (%)', x=cvar_df['ativo'],
        y=cvar_df['contribuicao_pct'], marker_color='crimson'
    ))
    fig_cv.update_layout(
        title='Peso Financeiro vs. Contribuição ao VaR',
        yaxis_title='Percentual (%)',
        barmode='group', template='plotly_white', height=420
    )
    st.plotly_chart(fig_cv, use_container_width=True)
else:
    st.warning("Decomposição não disponível (carteira com volatilidade zero).")

# ============================================================
# DISTRIBUIÇÃO DOS RETORNOS DA CARTEIRA
# ============================================================
st.divider()
st.subheader("📊 Distribuição Empírica dos Retornos da Carteira")

var_95_ret = r_hist['percentil_retorno']

fig_dist = go.Figure()
fig_dist.add_trace(go.Histogram(
    x=retornos_carteira * 100, nbinsx=60,
    marker_color='steelblue', opacity=0.7,
    name='Retornos diários (%)'
))
fig_dist.add_vline(
    x=var_95_ret * 100,
    line=dict(color='red', width=3, dash='dash'),
    annotation_text=f"VaR {params['nivel_confianca']*100:.0f}% = {var_95_ret*100:.2f}%",
    annotation_position='top left'
)
# Sombrear cauda
cauda = retornos_carteira[retornos_carteira <= var_95_ret] * 100
fig_dist.add_trace(go.Histogram(
    x=cauda, nbinsx=20,
    marker_color='red', opacity=0.5,
    name=f"Cauda (perdas > VaR {params['nivel_confianca']*100:.0f}%)"
))
fig_dist.update_layout(
    title=f"Distribuição dos Retornos Diários — {mesa_selecionada}",
    xaxis_title='Retorno Diário (%)', yaxis_title='Frequência',
    template='plotly_white', height=420, barmode='overlay'
)
st.plotly_chart(fig_dist, use_container_width=True)

# ============================================================
# SALVAR RESULTADOS NO SESSION STATE
# ============================================================
if 'resultados_var' not in st.session_state:
    st.session_state['resultados_var'] = {}

st.session_state['resultados_var'][mesa_selecionada] = {
    'var_historico': r_hist['var_financeiro'],
    'var_paramétrico': r_param['var_financeiro'],
    'var_montecarlo': r_mc['var_financeiro'],
    'var_oficial': resultados[resultados['Metodologia'].str.contains(
        params['metodologia'].split()[0], case=False
    )]['VaR (R$)'].iloc[0] if not resultados[
        resultados['Metodologia'].str.contains(params['metodologia'].split()[0], case=False)
    ].empty else r_param['var_financeiro'],
    'limite': limite_mesa,
    'valor_bruto': valor_bruto,
    'es_historico': es_hist['es_financeiro'],
    'es_normal': es_normal['es_financeiro'],
}

st.info(
    f"💾 Resultados da mesa **{mesa_selecionada}** salvos. "
    "Veja todas consolidadas no **Dashboard Executivo**."
)
