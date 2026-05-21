"""
pages/5_🚦_Monitoramento_de_Limites.py
=======================================
Painel de monitoramento de limites por mesa, com gauges, alertas e
classificação verde/amarelo/vermelho.
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
    calcular_retornos_carteira, var_parametrico, var_opcoes_montecarlo,
    classificar_utilizacao
)
from utils.session_init import init_session_state
from scipy import stats

st.set_page_config(page_title="Monitoramento de Limites", page_icon="🚦", layout="wide")

# Inicializa session_state se necessário (multi-page navigation safety)
init_session_state()

st.title("🚦 Monitoramento de Limites por Mesa")
st.markdown(
    "Comparação entre VaR calculado e limite aprovado, com classificação "
    "verde/amarelo/vermelho e alertas para excesso de risco."
)

# Validações
if st.session_state.get('posicoes') is None or st.session_state.get('retornos') is None:
    st.error("❌ Configure posições e parâmetros antes desta análise.")
    st.stop()

posicoes = st.session_state['posicoes']
retornos = st.session_state['retornos']
cov_amostral = st.session_state['cov_amostral']
params = st.session_state['parametros']

# ============================================================
# CALCULAR VaR DE TODAS AS MESAS
# ============================================================
todas_mesas = posicoes['mesa'].unique().tolist()
resultados_mesas = []

with st.spinner("Calculando VaR para todas as mesas..."):
    for mesa in todas_mesas:
        df_m = posicoes[posicoes['mesa'] == mesa].copy()
        limite = df_m['limite_var'].iloc[0]

        # Determinar se é mesa de opções
        tem_opcoes = df_m['tipo'].isin(['call', 'put']).any()
        tem_acoes = (df_m['tipo'] == 'acao').any()

        if tem_opcoes:
            # Mesa de opções → MC vega-aware
            df_op = df_m[df_m['tipo'].isin(['call', 'put'])].copy()
            df_op['T_anos'] = df_op['vencimento_dias_uteis'] / 252
            try:
                r = var_opcoes_montecarlo(
                    df_op, retornos,
                    nivel_confianca=params['nivel_confianca'],
                    horizonte_dias=params['horizonte_dias'],
                    taxa_juros=params['taxa_juros'],
                    n_simulacoes=params['n_simulacoes'],
                    chocar_vol=True, vol_choque_anual=0.10, seed=42
                )
                var_fin = r['var_financeiro']
                metodologia = 'MC vega-aware'
            except Exception:
                var_fin = 0
                metodologia = 'N/A'

            # Adicionar VaR das ações na mesma mesa, se houver
            if tem_acoes:
                df_ac = df_m[df_m['tipo'] == 'acao'].copy()
                exposicoes_ac = df_ac.set_index('ativo')['valor_posicao']
                valor_ac = exposicoes_ac.abs().sum()
                if valor_ac > 0:
                    pesos_ac = exposicoes_ac / valor_ac
                    pesos_alin = pesos_ac.reindex(cov_amostral.index).fillna(0.0).values
                    var_p_ac = float(pesos_alin @ cov_amostral.values @ pesos_alin)
                    vol_p_ac = np.sqrt(max(var_p_ac, 0)) * np.sqrt(params['horizonte_dias'])
                    var_acoes = stats.norm.ppf(params['nivel_confianca']) * vol_p_ac * valor_ac
                    var_fin += var_acoes  # Soma simples (conservadora)

            valor_bruto = (df_m['quantidade'] * df_m['preco']).abs().sum()

        else:
            # Mesa pura de ações → Paramétrico
            exposicoes = df_m.set_index('ativo')['valor_posicao']
            valor_bruto = exposicoes.abs().sum()
            if valor_bruto > 0:
                pesos = exposicoes / valor_bruto
                pesos_alin = pesos.reindex(cov_amostral.index).fillna(0.0).values
                var_p = float(pesos_alin @ cov_amostral.values @ pesos_alin)
                vol_p = np.sqrt(max(var_p, 0))
                var_fin = stats.norm.ppf(params['nivel_confianca']) * vol_p * valor_bruto * np.sqrt(params['horizonte_dias'])
                metodologia = 'Paramétrico'
            else:
                var_fin = 0
                metodologia = 'N/A'

        classif = classificar_utilizacao(var_fin, limite)
        resultados_mesas.append({
            'Mesa': mesa,
            'Metodologia': metodologia,
            'Exposição (R$)': valor_bruto,
            'VaR (R$)': var_fin,
            'Limite (R$)': limite,
            'Limite Disponível (R$)': classif['limite_disponivel'],
            'Utilização (%)': classif['utilizacao_pct'],
            'Status': f"{classif['cor']} {classif['status']}",
            'Breach': classif['breach'],
        })

df_resumo = pd.DataFrame(resultados_mesas).sort_values('Utilização (%)', ascending=False)

# ============================================================
# CARDS DE RESUMO
# ============================================================
n_total = len(df_resumo)
n_breach = df_resumo['Breach'].sum()
n_amarelo = ((df_resumo['Utilização (%)'] > 70) & (df_resumo['Utilização (%)'] <= 100)).sum()
n_verde = (df_resumo['Utilização (%)'] <= 70).sum()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total de Mesas", n_total)
with col2:
    st.metric("🟢 Verde", n_verde)
with col3:
    st.metric("🟡 Amarelo", n_amarelo)
with col4:
    st.metric("🔴 Vermelho (Breach)", n_breach,
              delta="ATENÇÃO" if n_breach > 0 else None,
              delta_color="inverse" if n_breach > 0 else "normal")

# ============================================================
# TABELA CONSOLIDADA
# ============================================================
st.divider()
st.subheader("📊 Painel Consolidado")

def aplicar_cor_status(val):
    if 'Verde' in str(val):
        return 'background-color: #d4edda; color: #155724'
    elif 'Amarelo' in str(val):
        return 'background-color: #fff3cd; color: #856404'
    elif 'Vermelho' in str(val):
        return 'background-color: #f8d7da; color: #721c24'
    return ''

st.dataframe(
    df_resumo.drop(columns=['Breach']).style
    .format({
        'Exposição (R$)': 'R$ {:,.2f}',
        'VaR (R$)': 'R$ {:,.2f}',
        'Limite (R$)': 'R$ {:,.2f}',
        'Limite Disponível (R$)': 'R$ {:,.2f}',
        'Utilização (%)': '{:.1f}%',
    }).map(aplicar_cor_status, subset=['Status']),
    use_container_width=True, hide_index=True
)

# ============================================================
# GAUGES INTERATIVOS
# ============================================================
st.divider()
st.subheader("🎯 Gauges de Utilização")

n_mesas = len(df_resumo)
fig_gauges = make_subplots(
    rows=1, cols=n_mesas,
    specs=[[{'type': 'indicator'}] * n_mesas],
    subplot_titles=df_resumo['Mesa'].tolist()
)

for i, (_, row) in enumerate(df_resumo.iterrows()):
    util = row['Utilização (%)']
    cor = 'green' if util <= 70 else ('orange' if util <= 100 else 'red')
    fig_gauges.add_trace(go.Indicator(
        mode='gauge+number',
        value=util,
        number={'suffix': '%', 'font': {'size': 24}},
        gauge={
            'axis': {'range': [0, 150]},
            'bar': {'color': cor},
            'steps': [
                {'range': [0, 70], 'color': 'rgba(0,200,0,0.15)'},
                {'range': [70, 100], 'color': 'rgba(255,165,0,0.20)'},
                {'range': [100, 150], 'color': 'rgba(255,0,0,0.20)'},
            ],
            'threshold': {
                'line': {'color': 'red', 'width': 4},
                'thickness': 0.75, 'value': 100
            }
        }
    ), row=1, col=i+1)

fig_gauges.update_layout(
    title='Utilização do Limite de VaR por Mesa',
    height=380, template='plotly_white'
)
st.plotly_chart(fig_gauges, use_container_width=True)

# ============================================================
# RANKING DE CONSUMO
# ============================================================
st.subheader("🏆 Ranking de Consumo de Risco")

fig_rank = go.Figure()
cores_bar = []
for _, r in df_resumo.iterrows():
    u = r['Utilização (%)']
    cores_bar.append('green' if u <= 70 else ('orange' if u <= 100 else 'red'))

fig_rank.add_trace(go.Bar(
    x=df_resumo['VaR (R$)'],
    y=df_resumo['Mesa'],
    orientation='h',
    marker_color=cores_bar,
    text=[f"R$ {v:,.0f} ({u:.0f}%)" for v, u in
          zip(df_resumo['VaR (R$)'], df_resumo['Utilização (%)'])],
    textposition='auto'
))

# Linhas tracejadas do limite
for i, (_, r) in enumerate(df_resumo.iterrows()):
    fig_rank.add_shape(
        type='line', x0=r['Limite (R$)'], x1=r['Limite (R$)'],
        y0=i-0.4, y1=i+0.4,
        line=dict(color='black', width=2, dash='dash')
    )

fig_rank.update_layout(
    title='Ranking de Mesas por Consumo de Risco<br><sub>Linhas pretas tracejadas: limite aprovado por mesa</sub>',
    xaxis_title='VaR (R$)', template='plotly_white', height=420
)
fig_rank.update_xaxes(tickformat=',.0f')
st.plotly_chart(fig_rank, use_container_width=True)

# ============================================================
# ALERTAS
# ============================================================
st.divider()
st.subheader("🚨 Alertas")

breaches = df_resumo[df_resumo['Breach']]
amarelo = df_resumo[(df_resumo['Utilização (%)'] > 70) & (df_resumo['Utilização (%)'] <= 100)]

if len(breaches) > 0:
    st.error("### 🔴 BREACH DE LIMITE")
    for _, r in breaches.iterrows():
        excesso = r['VaR (R$)'] - r['Limite (R$)']
        st.markdown(
            f"- **{r['Mesa']}** → utilização {r['Utilização (%)']:.1f}% — "
            f"excesso de **R$ {excesso:,.2f}**"
        )
    st.markdown(
        "**Ação requerida:** escalonar ao CRO em D+1, iniciar processo de "
        "redução de exposição. Reportar evento ao Comitê de Risco em até 48h."
    )

if len(amarelo) > 0:
    st.warning("### 🟡 ZONA DE ATENÇÃO")
    for _, r in amarelo.iterrows():
        st.markdown(
            f"- **{r['Mesa']}** → utilização {r['Utilização (%)']:.1f}% — "
            f"monitoramento intensificado recomendado"
        )

verdes = df_resumo[df_resumo['Utilização (%)'] <= 70]
if len(verdes) > 0:
    st.success(f"### 🟢 SITUAÇÃO CONFORTÁVEL ({len(verdes)} mesas)")
    for _, r in verdes.iterrows():
        st.markdown(
            f"- **{r['Mesa']}** → utilização {r['Utilização (%)']:.1f}%"
        )

# Salvar consolidado
st.session_state['dashboard_resumo'] = df_resumo
